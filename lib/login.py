"""Login próprio do YouTube no x3: cópia das credenciais, teste periódico e nova autorização pelo painel.

O x3 deixa de ler o login das pastas antigas: cada canal ganha <login_dir>/<canal>/ (fora do git, 700/600).
A cópia nunca altera a origem. A nova autorização só grava na pasta própria e só se a conta escolhida
no Google for a do canal (confere pelo id do canal).
"""
import base64
import hashlib
import html
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import canais as canais_mod, config, creds, db

ARQUIVOS = ('.env', 'credentials.enc', '.encryption_key')
EXTRAS = ('prompt_cortes.txt',)  # os cortes leem esse arquivo do config_dir
# Único retorno registrado nos 17 clientes OAuth (16 são do tipo "web"; conferido em 20/11/2026). É a porta do painel
# antigo; desde 27/11/2026 é o próprio painel do x3 que escuta nela (rota /api/auth/callback).
# De outro aparelho, localhost não abre: o Nei cola no x3 o endereço que ficou na barra.
REDIRECT = 'http://localhost:8090/api/auth/callback'
ESCOPOS = 'https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.upload'
AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'
VALIDADE_MIN = 15
INTERVALO_H = 6
RECUSAS = ('invalid_grant', 'disabled_client', 'invalid_client', 'unauthorized_client', 'deleted_client')

SCHEMA = """
CREATE TABLE IF NOT EXISTS login (
  canal TEXT PRIMARY KEY, estado TEXT NOT NULL DEFAULT '', msg TEXT NOT NULL DEFAULT '',
  testado_em TEXT NOT NULL DEFAULT '', ok_em TEXT NOT NULL DEFAULT '', renovado_em TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS login_pedidos (nonce TEXT PRIMARY KEY, canal TEXT NOT NULL, criado_em TEXT NOT NULL);
"""


def preparar(con):
    con.executescript(SCHEMA)


def pasta(nome):
    return os.path.join(config.login_dir(), nome)


def proprio(c):
    d = c.get('config_dir') or ''
    return bool(d) and os.path.abspath(d) == os.path.abspath(pasta(c['nome']))


def _sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def _grava(destino, dados):
    """Escreve com 600 e troca de uma vez, para nunca deixar arquivo pela metade."""
    tmp = f'{destino}.{os.getpid()}.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(dados)
    os.chmod(tmp, 0o600)
    os.replace(tmp, destino)


def _pastas(nome):
    os.makedirs(config.login_dir(), mode=0o700, exist_ok=True)
    os.chmod(config.login_dir(), 0o700)
    os.makedirs(pasta(nome), mode=0o700, exist_ok=True)
    os.chmod(pasta(nome), 0o700)


def copiar(canais, dir_canais=None):
    """Copia o login de cada canal para a pasta própria e aponta o config_dir para lá. Devolve [(canal, resultado)]."""
    out = []
    for nome, c in canais.items():
        orig, dst = c['config_dir'], pasta(nome)
        if proprio(c):
            out.append((nome, 'já usa o login próprio'))
            continue
        faltam = [a for a in ARQUIVOS if not os.path.isfile(os.path.join(orig, a))]
        if not orig or faltam:
            out.append((nome, f"origem sem {', '.join(faltam) or 'config_dir'}; nada copiado"))
            continue
        _pastas(nome)
        conflito = ''
        for a in ARQUIVOS + EXTRAS:
            s, d = os.path.join(orig, a), os.path.join(dst, a)
            if not os.path.isfile(s):
                continue
            if os.path.isfile(d):
                if _sha(d) != _sha(s):
                    conflito = a
                    break
                continue
            with open(s, 'rb') as f:
                _grava(d, f.read())
        if conflito:
            out.append((nome, f'{conflito} já existe na pasta própria e é diferente; config_dir não mudou'))
            continue
        if any(_sha(os.path.join(orig, a)) != _sha(os.path.join(dst, a)) for a in ARQUIVOS):
            out.append((nome, 'cópia não confere com a origem; config_dir não mudou'))
            continue
        canais_mod.definir_config_dir(nome, dst, dir_canais)
        out.append((nome, 'copiado'))
    return out


def estado(con, nome):
    r = con.execute('SELECT * FROM login WHERE canal=?', (nome,)).fetchone()
    return dict(r) if r else {'canal': nome, 'estado': '', 'msg': '', 'testado_em': '', 'ok_em': '', 'renovado_em': ''}


def _gravar(con, nome, **f):
    con.execute('INSERT OR IGNORE INTO login(canal) VALUES(?)', (nome,))
    con.execute(f"UPDATE login SET {', '.join(k + '=?' for k in f)} WHERE canal=?", (*f.values(), nome))


def _renovar(config_dir):
    return creds.access_token(config_dir, force=True)


def _limpar_pausa_login(con, nome):
    e = db.estado_destino(con, nome, 'youtube')
    if e['pausa_motivo'].startswith('login'):
        db.limpar_pausa(con, nome, 'youtube')


def testar(con, c, avisar=None, log=print):
    """Renova o token (sem cota). Só recusa do Google conta como login vencido; erro de rede não muda o estado."""
    nome, cfg = c['nome'], c['config_dir']
    antes = estado(con, nome)['estado']
    faltam = [a for a, ok in creds.check(cfg).items() if not ok] if cfg else list(ARQUIVOS)
    novo, msg = None, ''
    if faltam:
        novo, msg = 'vencido', f"faltam arquivos do login: {', '.join(faltam)}"
    else:
        try:
            _renovar(cfg)
            novo, msg = 'ok', 'token renovado'
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            msg = f'sem resposta do Google ({type(e).__name__}); estado mantido'
        except RuntimeError as e:
            t = str(e)
            if any(r in t for r in RECUSAS) or 'ausentes' in t:
                novo, msg = 'vencido', t[:300]
            else:
                msg = f'{t[:200]}; estado mantido'
        except Exception as e:
            novo, msg = 'vencido', f'{type(e).__name__}: {str(e)[:200]}'
    agora = db.agora()
    if novo is None:
        _gravar(con, nome, msg=msg, testado_em=agora)
        return f'não testado: {msg}'
    campos = {'estado': novo, 'msg': msg, 'testado_em': agora}
    if novo == 'ok':
        campos['ok_em'] = agora
        _limpar_pausa_login(con, nome)
    _gravar(con, nome, **campos)
    if avisar and novo != antes and (novo == 'vencido' or antes == 'vencido'):
        avisar(f'{nome}: login do YouTube {"VENCIDO: " + msg + ". Autentique no painel do canal." if novo == "vencido" else "voltou a funcionar."}', log)
    return f'{novo}: {msg}'


def iniciar(con, c):
    """URL do Google para autorizar de novo. O nonce fica no banco porque os painéis local e de rede são processos separados."""
    if not proprio(c):
        raise ValueError('o canal ainda lê o login da pasta antiga; rode primeiro: yt-pub-x3 login copiar')
    env = creds.load_env(c['config_dir'])
    if not env.get('CLIENT_ID') or not env.get('CLIENT_SECRET'):
        raise ValueError('CLIENT_ID/CLIENT_SECRET ausentes no .env do canal')
    if not _esperado(c, env):
        raise ValueError('canal sem destino_id: não dá para conferir a conta depois do login')
    limite = (datetime.now() - timedelta(minutes=VALIDADE_MIN)).strftime('%Y-%m-%d %H:%M:%S')
    con.execute('DELETE FROM login_pedidos WHERE criado_em<?', (limite,))
    nonce = secrets.token_urlsafe(24)
    con.execute('INSERT INTO login_pedidos VALUES(?,?,?)', (nonce, c['nome'], db.agora()))
    p = {'client_id': env['CLIENT_ID'], 'redirect_uri': REDIRECT, 'response_type': 'code', 'scope': ESCOPOS,
         'access_type': 'offline', 'prompt': 'consent', 'state': nonce}
    if env.get('GOOGLE_EMAIL'):
        p['login_hint'] = env['GOOGLE_EMAIL']
    return f'{AUTH_URL}?{urllib.parse.urlencode(p)}'


def _esperado(c, env=None):
    # Só o destino_id do canal: o YOUTUBE_CHANNEL_ID dos .env antigos foi copiado entre instâncias e não é confiável.
    return (c.get('destino_id') or '').strip()


def _trocar_codigo(env, code):
    body = urllib.parse.urlencode({'client_id': env['CLIENT_ID'], 'client_secret': env['CLIENT_SECRET'], 'code': code,
                                   'grant_type': 'authorization_code', 'redirect_uri': REDIRECT}).encode()
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(creds.TOKEN_URL, data=body), timeout=30).read())
    except urllib.error.HTTPError as e:
        raise ValueError(f'o Google recusou o código ({e.code}): {e.read().decode(errors="replace")[:200]}') from None


def _canais_da_conta(access_token):
    """Ids dos canais da conta que autorizou (1 unidade de cota)."""
    req = urllib.request.Request('https://www.googleapis.com/youtube/v3/channels?part=id&mine=true',
                                 headers={'Authorization': f'Bearer {access_token}'})
    return [x['id'] for x in json.loads(urllib.request.urlopen(req, timeout=30).read()).get('items', [])]


def _salvar(cfg, tokens):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    kp, cp = os.path.join(cfg, '.encryption_key'), os.path.join(cfg, 'credentials.enc')
    if os.path.isfile(kp):
        with open(kp) as f:
            chave = base64.b64decode(f.read().strip())
    else:
        chave = secrets.token_bytes(32)
        _grava(kp, base64.b64encode(chave))
    if os.path.isfile(cp):
        with open(cp, 'rb') as f:
            _grava(cp + '.bak', f.read())
    nonce = secrets.token_bytes(12)
    dados = json.dumps({'access_token': tokens.get('access_token', ''), 'refresh_token': tokens['refresh_token'],
                        'token_type': tokens.get('token_type', 'Bearer')}).encode()
    _grava(cp, nonce + AESGCM(chave).encrypt(nonce, dados, None))
    creds._token_cache.pop(cfg, None)


def concluir(con, canais, state, code, avisar=None, log=print):
    """Troca o código, confere a conta e grava. Devolve (ok, mensagem); nunca inclui o código na mensagem."""
    state, code = (state or '').strip(), (code or '').strip()
    if not state or not code:
        return False, 'faltou o código ou o identificador do pedido'
    r = con.execute('SELECT * FROM login_pedidos WHERE nonce=?', (state,)).fetchone()
    con.execute('DELETE FROM login_pedidos WHERE nonce=?', (state,))
    limite = (datetime.now() - timedelta(minutes=VALIDADE_MIN)).strftime('%Y-%m-%d %H:%M:%S')
    if not r or r['criado_em'] < limite:
        return False, f'pedido de login vencido ou desconhecido; clique em Autenticar de novo (vale {VALIDADE_MIN} min)'
    c = canais.get(r['canal'])
    if not c or not proprio(c):
        return False, 'canal não encontrado ou ainda sem login próprio'
    env = creds.load_env(c['config_dir'])
    try:
        tokens = _trocar_codigo(env, code)
        if not tokens.get('refresh_token'):
            return False, 'o Google não devolveu refresh_token; tente de novo'
        ids = _canais_da_conta(tokens['access_token'])
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f'falha falando com o Google: {type(e).__name__}'
    esperado = _esperado(c, env)
    if esperado not in ids:
        return False, f"a conta escolhida não é a do canal {c['nome']} (esperado {esperado}, veio {', '.join(ids) or 'nenhum canal'}); nada foi gravado"
    _salvar(c['config_dir'], tokens)
    _gravar(con, c['nome'], renovado_em=db.agora())
    res = testar(con, c, avisar, log)
    return res.startswith('ok'), f"{c['nome']}: login renovado e conferido ({res})"


def colar(con, canais, texto, avisar=None, log=print):
    """Recebe a URL de retorno colada pelo Nei (acesso pela rede, onde localhost não abre)."""
    texto = (texto or '').strip()
    if not texto or len(texto) > 4096:
        return False, 'cole o endereço inteiro da barra do navegador'
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(texto).query)
    if q.get('error'):
        return False, f"o Google respondeu: {q['error'][0][:80]}"
    return concluir(con, canais, (q.get('state') or [''])[0], (q.get('code') or [''])[0], avisar, log)


def pagina(ok, msg):
    cor = '#22c55e' if ok else '#ef4444'
    return (f'<!doctype html><meta charset="utf-8"><title>Login do YouTube</title><body style="background:#0c0c10;color:#e4e4e7;'
            f'font-family:sans-serif;display:grid;place-items:center;min-height:90vh"><div style="max-width:640px;text-align:center">'
            f'<h1 style="color:{cor}">{"Login renovado" if ok else "Login não renovado"}</h1><p>{html.escape(msg)}</p>'
            f'<p><a href="/" style="color:#FACC15">Voltar ao painel</a></p></div>').encode()
