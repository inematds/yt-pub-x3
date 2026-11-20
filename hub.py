#!/usr/bin/env python3
"""Hub único. A cada ciclo agenda os horários dos canais ativos e entrega os jobs às faixas de trabalho."""
import fcntl
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import VERSION, canais as canais_mod, config, db, login, runner, vigia  # noqa: E402

INTERVALO = int(os.environ.get('X3_INTERVALO', '30'))
TAMANHOS = {'youtube': 2, 'rs': 3, 'cortes': 1, 'geral': 2}


def log(m):
    print(f'[{datetime.now():%Y-%m-%d %H:%M:%S}] {m}', flush=True)


def _slots(con, nome, tipo, horarios, payload, prefixo):
    agora = datetime.now()
    for hm in horarios:
        try:
            quando = datetime.strptime(f'{agora:%Y-%m-%d} {hm}', '%Y-%m-%d %H:%M')
        except ValueError:
            log(f'[{nome}] horário inválido: {hm}')
            continue
        # Hub que subiu atrasado não despeja de uma vez o que passou há mais de 1 h.
        if (agora - quando).total_seconds() <= 3600:
            db.add_job(con, nome, tipo, quando.strftime('%Y-%m-%d %H:%M:%S'), json.dumps(payload), f'{prefixo}:{nome}:{agora:%Y-%m-%d} {hm}')


def _limpar_slots(con, nome, prefixo, horarios):
    """Horário desligado no painel não pode continuar agendado."""
    marcas = ','.join('?' * len(horarios))
    con.execute(f"""DELETE FROM jobs WHERE canal=? AND status='pendente' AND tipo IN ('publicar','cortar')
        AND chave LIKE ? AND substr(chave,-5) NOT IN ({marcas})""", (nome, f'{prefixo}:{nome}:%', *horarios))


def agendar(con, canais, simular=False):
    agora = datetime.now()
    for nome, c in canais.items():
        if not c['ativo']:
            continue
        db.add_job(con, nome, 'entrada', db.agora(), chave=f'entrada:{nome}:{agora:%Y-%m-%d %H:%M}')
        _limpar_slots(con, nome, 'yt', c['youtube']['horarios'])
        _limpar_slots(con, nome, 'clip', c['clipes']['horarios'])
        _limpar_slots(con, nome, 'rs', c['rs']['horarios'] if c['rs']['provedor'] else [])
        _limpar_slots(con, nome, 'corte', c['cortes']['horarios'] if c['cortes']['ligado'] else [])
        _slots(con, nome, 'publicar', c['youtube']['horarios'], {'destino': 'youtube'}, 'yt')
        _slots(con, nome, 'publicar', c['clipes']['horarios'], {'destino': 'youtube', 'grupo': 'clipes'}, 'clip')
        if c['rs']['provedor']:
            _slots(con, nome, 'publicar', c['rs']['horarios'], {'destino': 'rs'}, 'rs')
        if c['cortes']['ligado'] and c['cortes']['horarios']:
            db.add_job(con, nome, 'sync_lives', db.agora(), chave=f'sync:{nome}:{agora:%Y-%m-%d}')
            _slots(con, nome, 'cortar', c['cortes']['horarios'], {}, 'corte')
        bloco = agora.hour // login.INTERVALO_H
        db.add_job(con, nome, 'login', db.agora(), chave=f'login:{nome}:{agora:%Y-%m-%d}:{bloco}')
        if any(vigia.estado(con, nome, d)['ligado'] for d in ('youtube', 'rs')):
            q = agora.minute // vigia.INTERVALO_MIN * vigia.INTERVALO_MIN
            db.add_job(con, nome, 'vigiar', db.agora(), chave=f'vigiar:{nome}:{agora:%Y-%m-%d %H}:{q:02d}')
        for e in ([] if simular else db.vencidas(con, nome)):
            if not runner.disponivel(con, c, e['destino'])[0]:
                continue  # destino pausado: a entrega espera, sem gastar job
            db.add_job(con, nome, 'publicar_entrega', db.agora(), json.dumps({'entrega_id': e['id'], 'destino': e['destino']}),
                       f"ent:{e['id']}:{e['tentativas']}:{e['atualizado_em']}")
    con.execute("DELETE FROM jobs WHERE tipo IN ('entrada','vigiar','login') AND status='ok' AND fim_em < datetime('now','localtime','-1 day')")


def _rodar(job_id, canais, simular):
    con = db.connect()
    try:
        job = con.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        runner.executar(con, job, canais, simular, log)
    finally:
        con.close()


def ciclo(con, faixas=None):
    """Sem faixas roda tudo em sequência (testes e --once). Devolve quantos jobs iniciou."""
    canais = canais_mod.carregar()
    simular = not config.publicar_de_verdade()
    agendar(con, canais, simular)
    perdidos = db.expirar_atrasados(con)
    if perdidos:
        log(f'{perdidos} horário(s) perdido(s) não serão recuperados de uma vez')
    n = 0
    for job in db.jobs_vencidos(con):
        if not db.reivindicar_job(con, job['id']):
            continue
        n += 1
        if faixas:
            faixas[runner.faixa(job)].submit(_rodar, job['id'], canais, simular)
        else:
            runner.executar(con, job, canais, simular, log)
    return n


def main():
    os.makedirs(os.path.dirname(config.db_path()), exist_ok=True)
    fd = os.open(config.db_path() + '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit('outro hub já está rodando')
    con = db.connect()
    n = db.recuperar_interrompidos(con)
    log(f"hub v{VERSION} {'PUBLICANDO' if config.publicar_de_verdade() else 'em simulação'}; {n} envio(s) para conferir")
    if '--once' in sys.argv:
        ciclo(con)
        return
    faixas = {k: ThreadPoolExecutor(v, thread_name_prefix=k) for k, v in TAMANHOS.items()}
    parar = threading.Event()
    while not parar.is_set():
        try:
            ciclo(con, faixas)
        except Exception as e:
            log(f'erro no ciclo: {type(e).__name__}: {e}')
        parar.wait(INTERVALO)


if __name__ == '__main__':
    main()
