"""Textos e capas pelo Codex, usando o yt-pubx em processo separado. Sem imagem reserva."""
import json
import os
import subprocess
import sys

from . import config


def _chamar(pedido, tempo=1200):
    script = os.path.join(config.ROOT, 'scripts', 'ia_ytpubx.py')
    r = subprocess.run([sys.executable, '-I', script], input=json.dumps(pedido), text=True,
                       capture_output=True, timeout=tempo)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[-300:] or 'IA falhou')
    return json.loads(r.stdout.strip().splitlines()[-1])


def escrever_textos(canal, tipo, contexto, arquivo='', titulo='', descricao=''):
    return _chamar({'acao': 'texto', 'canal': canal, 'tipo': tipo, 'contexto': contexto, 'video': arquivo,
                    'titulo': titulo, 'descricao': descricao})


def enriquecer_live(canal, pedido):
    """{'title','description'} pelo Codex; o pedido (prompt + transcrição) vai pelo stdin, nunca como argumento."""
    return _chamar({'acao': 'enriquecer', 'canal': canal, 'tipo': 'live', 'contexto': pedido})


THUMBVIRAL ='~/projetos/output/thumbviral/thumbviral.py'


def gerar_capa(canal, titulo, descricao, pasta):
    """Thumb viral 1280x720 pelo Codex image_gen (gerador oficial da linha thumb do kit de design INEMA):
    o Codex escolhe o gancho e o desenha dentro da arte, com estilo sorteado. Sem texto por cima e sem reserva."""
    script = os.path.expanduser(os.environ.get('X3_THUMBVIRAL') or THUMBVIRAL)
    if not os.path.isfile(script):
        raise RuntimeError(f'gerador de thumb ausente: {script}')
    saida = os.path.join(pasta, 'capa-x3')
    os.makedirs(saida, exist_ok=True)
    pedido = os.path.join(saida, 'pedido.json')
    with open(pedido, 'w', encoding='utf-8') as f:
        json.dump([{'id': 'capa', 'titulo': titulo, 'resumo': (descricao or '')[:400]}], f, ensure_ascii=False)
    # No systemd o /usr/bin/codex antigo vem antes do atual no PATH.
    env = {**os.environ, 'PATH': os.path.expanduser('~/.npm-global/bin') + os.pathsep + os.environ.get('PATH', '')}
    r = subprocess.run([sys.executable, script, saida, pedido], capture_output=True, text=True, timeout=1200, env=env)
    jpg = os.path.join(saida, 'capa.jpg')
    if not os.path.isfile(jpg):
        raise RuntimeError(f"Codex não gerou a capa: {(r.stdout + r.stderr).strip()[-300:] or 'sem saída'}")
    return jpg
