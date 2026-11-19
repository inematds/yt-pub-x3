"""Conector do Metricool: usa os publicadores da conta (fila por marca e recibo).

A trava de 1 h entre posts fica desligada aqui: quem controla o intervalo são os horários do x3 (Nei, 18/11/2026).
"""
import json
import os
import re
import subprocess
import sys

from . import config
from .falhas import DEFINITIVO, FORMATO, TEMPORARIO, Falha



def repo_midia():
    """Repo público que hospeda a mídia: o Metricool precisa de URL pública."""
    return os.environ.get('X3_METRICOOL_REPO') or 'inematds/yt-pubx'


TEMPO = 5400  # espera da vez na marca + agente
SEM_TRAVA = {'INTERVALO_LIVRE': '1'}


def publicador_video():
    return os.environ.get('X3_METRICOOL_VIDEO') or os.path.join(config.PROJETOS, 'metricool-inematds', 'publicar.sh')


def publicador_imagens():
    return os.environ.get('X3_METRICOOL_IMAGENS') or os.path.join(config.ROOT, 'scripts', 'metricool-imagens.sh')


def publicador_pub2():
    return os.environ.get('X3_METRICOOL_PUB2') or os.path.join(config.ROOT, 'scripts', 'metricool-pub2.py')


def formato(item, rs):
    """Motivo pelo qual o item não serve para as redes, ou ''."""
    if item['tipo'] in ('foto', 'carrossel'):
        return ''
    if item['largura'] >= item['altura']:  # Nei, 18/11/2026: 16:9 com menos de 3 min também vai às redes
        if 0 < item['duracao'] < 180:
            return ''
        return 'Vídeo 16:9 só vai às redes com menos de 3 min'
    limite = 180 if 'instagram' in rs['redes'] else 600
    if item['duracao'] > limite:
        return f'Passa de {limite} s'
    return ''


def legenda(item):
    """Sempre o mesmo arquivo: o recibo do publicador depende deste texto."""
    os.makedirs(item['pasta'], exist_ok=True)
    p = os.path.join(item['pasta'], 'legenda-rs.txt')
    if not os.path.exists(p):
        with open(p, 'w', encoding='utf-8') as f:
            titulo = re.sub(r'\s*#shorts\b', '', item['titulo'], flags=re.I).strip()
            f.write(f"{titulo}\n\n{item['texto_rs'] or item['descricao']}\n")
    return p


def publicar(canal, item, log=print):
    rs = canal['rs']
    motivo = formato(item, rs)
    if motivo:
        raise Falha(motivo, FORMATO)
    arquivos = json.loads(item['arquivos'])
    env = {**os.environ, **SEM_TRAVA, 'MARCA': rs['marca'], 'REDES': ','.join(rs['redes'])}
    if item['tipo'] in ('foto', 'carrossel'):
        cmd = ['bash', publicador_imagens(), legenda(item), repo_midia(), *arquivos]
    else:
        cmd = ['bash', publicador_video(), arquivos[0], legenda(item), repo_midia()]
    return _rodar(cmd, env, rs)


def publicar_pub2(canal, item, log=print):
    """Conta metricool-pub2 (@inemafuturos): só vídeo vertical."""
    rs = canal['rs']
    motivo = 'Esta conta recebe só vídeo' if item['tipo'] in ('foto', 'carrossel') else formato(item, rs)
    if motivo:
        raise Falha(motivo, FORMATO)
    return _rodar([sys.executable, publicador_pub2(), json.loads(item['arquivos'])[0], legenda(item)], {**os.environ, **SEM_TRAVA}, rs)


def _rodar(cmd, env, rs):
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=TEMPO)
    except subprocess.TimeoutExpired:
        raise Falha('Metricool demorou demais', TEMPORARIO) from None
    saida = (r.stdout or '') + (r.stderr or '')
    if r.returncode == 0:
        m = re.search(r'Metricool: (https://\S+)', saida)
        url = m.group(1) if m else f"https://app.metricool.com/planner/calendar?blogId={rs['blog_id']}"
        return rs['marca'], url
    fim = saida.strip()[-300:]
    if r.returncode == 2:
        raise Falha(fim or 'Formato recusado', FORMATO)
    raise Falha(fim or f'publicador saiu com {r.returncode}', TEMPORARIO)


PUBLICADORES = {'metricool': publicar, 'metricool-pub2': publicar_pub2}


def sem_conector(canal, item, log=print):
    raise Falha(f"RS sem conector ativo: {canal['rs'].get('provedor') or 'nenhum'}", DEFINITIVO)
