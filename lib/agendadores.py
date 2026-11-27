"""Aviso de agendador parado (yt-schedulerN dos canais lives), migrado do monitor do painel antigo em 27/11/2026.

Lê o systemd do usuário. Parado = ActiveState fora de active (ou reiniciando em laço), em duas leituras seguidas,
para não avisar de um reinício rápido. Avisa ao parar, repete a cada REPETIR_H enquanto continuar parado e
avisa quando volta. Instância com "monitorar": false na lista fica de fora.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta

from . import config

INTERVALO_S = 300
CONFIRMAR = 2
REPETIR_H = 6
ESTADO = os.path.join(os.path.dirname(config.db_path()), 'agendadores.json')


def ler_systemd(servicos):
    """{servico: (ActiveState, SubState)}; serviço que o systemd não conhece vem como ('', '')."""
    if not servicos:
        return {}
    out = subprocess.run(['systemctl', '--user', 'show', *servicos, '-p', 'Id', '-p', 'ActiveState', '-p', 'SubState'],
                         capture_output=True, text=True, timeout=30).stdout
    res, cur = {}, {}
    for linha in out.splitlines() + ['']:
        if not linha.strip():
            if cur.get('Id'):
                res[cur['Id'].removesuffix('.service')] = (cur.get('ActiveState', ''), cur.get('SubState', ''))
            cur = {}
            continue
        k, _, v = linha.partition('=')
        cur[k] = v
    return {s: res.get(s, ('', '')) for s in servicos}


def parado(ativo, sub):
    return ativo != 'active' and not (ativo == 'activating' and sub != 'auto-restart')


def _carregar(caminho):
    try:
        with open(caminho) as f:
            return json.load(f)
    except Exception:
        return {}


def _salvar(caminho, st):
    tmp = caminho + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, caminho)


def verificar(instancias, avisar, ler=ler_systemd, agora=None, caminho=ESTADO, log=print):
    """Uma rodada. Devolve a lista de mensagens avisadas."""
    agora = agora or datetime.now()
    alvo = {i['scheduler_svc']: i['name'].removeprefix('yt-pub-') for i in instancias
            if i.get('scheduler_svc') and i.get('monitorar', True)}
    lido = ler(list(alvo))
    st = _carregar(caminho)
    msgs = []
    for svc, canal in alvo.items():
        ativo, sub = lido.get(svc, ('', ''))
        e = st.setdefault(svc, {'quedas': 0, 'avisado_em': ''})
        if parado(ativo, sub):
            e['quedas'] += 1
            ultimo = e['avisado_em']
            if e['quedas'] >= CONFIRMAR and (not ultimo or agora - datetime.fromisoformat(ultimo) >= timedelta(hours=REPETIR_H)):
                msgs.append(f'{canal}: agendador {svc} PARADO ({ativo or "desconhecido"}/{sub or "-"}). '
                            f'Ver: systemctl --user status {svc}')
                e['avisado_em'] = agora.isoformat(timespec='seconds')
        else:
            if e['avisado_em']:
                msgs.append(f'{canal}: agendador {svc} voltou a rodar.')
            e['quedas'], e['avisado_em'] = 0, ''
    _salvar(caminho, st)
    for m in msgs:
        avisar(m, log)
    return msgs
