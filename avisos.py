#!/usr/bin/env python3
"""Avisos no Telegram das publicações (bot dedicado) e de agendador yt-schedulerN parado (bot v3), migrados do painel antigo em 27/11/2026.

Processo único (o token do bot só aceita um leitor de getUpdates): trava em data/avisos.lock.
Lista de canais lidos: X3_INSTANCIAS (JSON fora do git, mesmo formato do painel antigo).
Token: TELEGRAM_NOTIFY_BOT_TOKEN no ambiente (o serviço carrega o .env onde ele já está; nunca é impresso).
"""
import fcntl
import json
import os
import sys
import threading
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from lib import agendadores, notifier, runner  # noqa: E402

INSTANCIAS = os.environ.get('X3_INSTANCIAS') or os.path.expanduser('~/.config/yt-pub-x3/instancias.json')


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def carregar_instancias(caminho=INSTANCIAS):
    with open(caminho) as f:
        return json.load(f)


def vigiar_agendadores(inst):
    log(f'agendadores: vigiando {sum(1 for i in inst if i.get("monitorar", True))} a cada {agendadores.INTERVALO_S // 60} min')
    while True:
        try:
            agendadores.verificar(inst, runner.avisar, log=log)
        except Exception as e:
            log(f'agendadores: erro na rodada: {type(e).__name__}: {e}')
        time.sleep(agendadores.INTERVALO_S)


def main():
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    trava = open(os.path.join(ROOT, 'data', 'avisos.lock'), 'w')
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('avisos já está rodando')
    inst = carregar_instancias()
    log(f'avisos: {len(inst)} canais, estado em {notifier.STATE_FILE}')
    threading.Thread(target=vigiar_agendadores, args=(inst,), daemon=True).start()
    notifier.start(inst, log)
    if not notifier.enabled():
        log('sem TELEGRAM_NOTIFY_BOT_TOKEN: avisos de publicação desligados; vigia de agendadores segue')
    while True:
        time.sleep(3600)


if __name__ == '__main__':
    main()
