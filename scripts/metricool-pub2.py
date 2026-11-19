#!/usr/bin/env python3
"""Agenda um vídeo vertical na conta metricool-pub2 (@inemafuturos), para a fila de redes do lives11.

uso: metricool-pub2.py <video.mp4> <legenda.txt>
Saída: 0 agendado (imprime "Metricool: <url>") · 1 tentar de novo · 2 entrada inválida.
Reaproveita hospedagem e agendamento de ~/projetos/metricool-pub2/lives11/fila.py.
O x3 chama com INTERVALO_LIVRE=1: a trava de 1 h não atrasa o post, os horários do x3 mandam.
"""
import fcntl
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ARQ = Path.home() / 'projetos/metricool-pub2/lives11/fila.py'
TRAVAS = Path.home() / '.local/share/metricool-intervalo'


def carregar():
    spec = importlib.util.spec_from_file_location('fila_pub2', ARQ)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main(a):
    if len(a) != 2 or not Path(a[0]).is_file() or not Path(a[1]).is_file():
        print('falta vídeo ou legenda'); return 2
    f = carregar()
    video, legenda = a[0], Path(a[1])
    w, h, dur = f.probe(video)
    if w >= h or dur > 180:
        print(f'formato fora das redes ({w}x{h}, {dur:.0f} s)'); return 2
    f.EST.mkdir(parents=True, exist_ok=True)
    TRAVAS.mkdir(parents=True, exist_ok=True)
    with (TRAVAS / 'metricool-pub2.publicacao.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        d = hashlib.sha256(Path(video).read_bytes() + legenda.read_bytes()).hexdigest()[:24]
        recibo = f.EST / f'x3-{d}.recibo.json'
        if recibo.exists():
            print(f'Metricool: {(json.loads(recibo.read_text()).get("planner") or [""])[0]}'); return 0
        txt = f.EST / f'x3-{d}-texto.txt'
        txt.write_text(legenda.read_text(encoding='utf-8'), encoding='utf-8')
        subprocess.run(['python3', str(f.SEM_LINKS), str(txt)], check=True)
        alvo = datetime.now(f.BR) + timedelta(minutes=10)
        r = subprocess.run(['python3', str(f.TRAVA), '--conector', 'metricool-pub2', '--alvo', str(int(alvo.timestamp()))], capture_output=True, text=True)
        if r.returncode:
            print('trava de 1 h: não consegui ler a agenda da marca'); return 1
        alvo = datetime.fromtimestamp(int(r.stdout.split()[-1]), f.BR)
        media = f.hospeda(video, f'x3-lives11-{d}.mp4')
        j = f.agenda(media, txt, ['tiktok', 'instagram'], alvo.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:00'), alvo.strftime('%d/%m %H:%M'))
        if not j.get('ok'):
            print(f'Metricool não agendou: {j.get("erro") or "sem resposta"}'); return 1
        subprocess.run(['python3', str(f.TRAVA), '--registrar', '--conector', 'metricool-pub2', '--alvo', str(int(alvo.timestamp()))])
        recibo.write_text(json.dumps(j, ensure_ascii=False))
        print(f'Metricool: {(j.get("planner") or [""])[0]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
