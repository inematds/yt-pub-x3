#!/usr/bin/env python3
"""Avisos no Telegram das publicações (bot dedicado), migrado do painel antigo em 27/11/2026.

Processo único (o token do bot só aceita um leitor de getUpdates): trava em data/avisos.lock.
Lista de canais lidos: X3_INSTANCIAS (JSON fora do git, mesmo formato do painel antigo).
Token: TELEGRAM_NOTIFY_BOT_TOKEN no ambiente (o serviço carrega o .env onde ele já está; nunca é impresso).
"""
import fcntl
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from lib import notifier  # noqa: E402

INSTANCIAS = os.environ.get('X3_INSTANCIAS') or os.path.expanduser('~/.config/yt-pub-x3/instancias.json')


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def carregar_instancias(caminho=INSTANCIAS):
    with open(caminho) as f:
        return json.load(f)


def main():
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    trava = open(os.path.join(ROOT, 'data', 'avisos.lock'), 'w')
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('avisos já está rodando')
    inst = carregar_instancias()
    log(f'avisos: {len(inst)} canais, estado em {notifier.STATE_FILE}')
    notifier.start(inst, log)
    if not notifier.enabled():
        sys.exit('sem TELEGRAM_NOTIFY_BOT_TOKEN')
    while True:
        time.sleep(3600)


if __name__ == '__main__':
    main()
