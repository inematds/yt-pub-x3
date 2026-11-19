#!/usr/bin/env python3
"""Painel. Por padrão só escuta em 127.0.0.1; com --rede abre uma porta à parte, com senha e só para redes privadas.

Não tem senha padrão nem rota que execute comandos.
"""
import base64
import binascii
import hmac
import ipaddress
import json
import os
import re
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from lib import canais as canais_mod, db, painel, vigia  # noqa: E402

HTML = os.path.join(RAIZ, 'dashboard', 'index.html')
USUARIO_REDE = 'x3'
SENHA_MINIMA = 16


class Painel(BaseHTTPRequestHandler):
    server_version = 'x3'

    def log_message(self, *a):
        pass

    def _json(self, codigo, dados):
        b = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def _host_ok(self):
        return (self.headers.get('Host') or '').split(':')[0] in ('127.0.0.1', 'localhost')

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {'erro': 'host recusado'})
        con = db.connect()
        try:
            canais = canais_mod.carregar()
            pedido = urlsplit(self.path)
            caminho, q = pedido.path, {k: v[0] for k, v in parse_qs(pedido.query).items()}
            if caminho == '/':
                with open(HTML, 'rb') as f:
                    b = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(b)))
                self.send_header('Content-Security-Policy', "default-src 'self' 'unsafe-inline'")
                self.end_headers()
                self.wfile.write(b)
            elif caminho == '/api/filas':
                self._json(200, {'canais': painel.filas(con, canais, busca=q.get('q', ''), tipo=q.get('tipo', ''), canal=q.get('canal', ''))})
            elif caminho == '/api/estado':
                self._json(200, painel.estado(con, canais))
            else:
                m = re.fullmatch(r'/api/canal/([\w-]+)', caminho)
                a = re.fullmatch(r'/api/vigia/([\w-]+)', caminho)
                if a and a.group(1) in canais:
                    self._json(200, vigia.analise(con, a.group(1)))
                elif m and m.group(1) in canais:
                    self._json(200, painel.itens_canal(con, m.group(1), q.get('q', ''), q.get('tipo', ''), q.get('status', '')))
                else:
                    self._json(404, {'erro': 'não encontrado'})
        finally:
            con.close()

    def do_POST(self):
        # O cabeçalho próprio impede que outra página aberta no navegador acione o painel.
        if not self._host_ok() or self.headers.get('X-X3') != '1':
            return self._json(403, {'erro': 'pedido recusado'})
        con = db.connect()
        try:
            m = re.fullmatch(r'/api/entrega/(\d+)/(pausar|retomar|pular|reenviar|confirmar)', self.path)
            if m:
                ok = db.acao(con, int(m.group(1)), m.group(2))
                return self._json(200 if ok else 409, {'ok': ok})
            m = re.fullmatch(r'/api/horarios/([\w-]+)/(youtube|clipes|rs|cortes)', self.path)
            if m and m.group(1) in canais_mod.carregar():
                try:
                    tamanho = int(self.headers.get('Content-Length') or 0)
                    if not 0 < tamanho <= 4096:
                        raise ValueError('tamanho inválido')
                    pedido = json.loads(self.rfile.read(tamanho))
                    return self._json(200, {'ok': True, 'horarios': painel.salvar_horarios(con, m.group(1), m.group(2), pedido.get('horarios'))})
                except (ValueError, AttributeError) as e:
                    return self._json(400, {'erro': str(e)})
            m = re.fullmatch(r'/api/destino/([\w-]+)/(youtube|rs)/(ligar|desligar)', self.path)
            if m and m.group(1) in canais_mod.carregar():
                db.definir_ligado(con, m.group(1), m.group(2), m.group(3) == 'ligar')
                return self._json(200, {'ok': True})
            m = re.fullmatch(r'/api/vigia/([\w-]+)/(youtube|rs)/(ligar|desligar|destravar)', self.path)
            if m and m.group(1) in canais_mod.carregar():
                if m.group(3) == 'destravar':
                    vigia.destravar(con, m.group(1), m.group(2))
                else:
                    vigia.ligar(con, m.group(1), m.group(2), m.group(3) == 'ligar')
                return self._json(200, {'ok': True})
            m = re.fullmatch(r'/api/vigia/([\w-]+)/cfg', self.path)
            if m and m.group(1) in canais_mod.carregar():
                try:
                    tamanho = int(self.headers.get('Content-Length') or 0)
                    if not 0 < tamanho <= 4096:
                        raise ValueError('tamanho inválido')
                    return self._json(200, {'ok': True, 'cfg': vigia.salvar_cfg(con, m.group(1), json.loads(self.rfile.read(tamanho)))})
                except (ValueError, TypeError, AttributeError) as e:
                    return self._json(400, {'erro': str(e)})
            self._json(404, {'erro': 'não encontrado'})
        finally:
            con.close()


class PainelRede(Painel):
    """Mesmo painel para a rede local: exige origem numa rede permitida e senha."""
    senha = ''
    redes = ()

    def _na_rede(self, texto):
        try:
            ip = ipaddress.ip_address(texto)
        except ValueError:
            return False
        return any(ip in r for r in self.redes)

    def _host_ok(self):
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0].lower()
        nome = socket.gethostname().lower()
        return self._na_rede(host) or host in (nome, f'{nome}.local')

    def _senha_ok(self):
        tipo, _, valor = (self.headers.get('Authorization') or '').partition(' ')
        if tipo.lower() != 'basic':
            return False
        try:
            usuario, _, senha = base64.b64decode(valor, validate=True).partition(b':')
        except (binascii.Error, ValueError):
            return False
        usuario_ok = hmac.compare_digest(usuario, USUARIO_REDE.encode())
        return hmac.compare_digest(senha, self.senha.encode()) and usuario_ok

    def _liberado(self):
        if not self._na_rede(self.client_address[0]):
            self._json(403, {'erro': 'rede recusada'})
            return False
        if self._senha_ok():
            return True
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="yt-pub-x3", charset="UTF-8"')
        self.send_header('Content-Length', '0')
        self.end_headers()
        return False

    def do_GET(self):
        if self._liberado():
            super().do_GET()

    def do_POST(self):
        if self._liberado():
            super().do_POST()


def ler_redes(texto):
    redes = [ipaddress.ip_network(x.strip(), strict=False) for x in (texto or '').split(',') if x.strip()]
    if not redes or not all(r.version == 4 and r.is_private for r in redes):
        raise ValueError('X3_PAINEL_REDES precisa listar só redes IPv4 privadas')
    return tuple(redes)


def criar(porta):
    return ThreadingHTTPServer(('127.0.0.1', porta), Painel)


def criar_rede(porta, senha, redes, endereco='0.0.0.0'):
    if len(senha or '') < SENHA_MINIMA:
        raise ValueError(f'X3_PAINEL_SENHA precisa de pelo menos {SENHA_MINIMA} caracteres')
    tratador = type('PainelRedeConfig', (PainelRede,), {'senha': senha, 'redes': ler_redes(redes)})
    return ThreadingHTTPServer((endereco, porta), tratador)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--rede']
    if '--rede' in sys.argv:
        porta = int(args[0]) if args else 8231
        try:
            srv = criar_rede(porta, os.environ.get('X3_PAINEL_SENHA'), os.environ.get('X3_PAINEL_REDES'))
        except ValueError as e:
            sys.exit(f'painel de rede não iniciado: {e}')
        print(f'painel na rede local, porta {porta}, com senha', flush=True)
    else:
        porta = int(args[0]) if args else 8230
        srv = criar(porta)
        print(f'painel em http://127.0.0.1:{porta}', flush=True)
    srv.serve_forever()
