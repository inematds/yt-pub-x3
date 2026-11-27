"""Distribuição de links (Telegram, bot @inemaytbot): quem recebe o quê.

Quem envia é o notifier do x3 (lib/notifier.py, serviço yt-pub-x3-avisos; migrado do master em 27/11/2026).
Ele lê, na tabela `config` do lives.db de cada canal, `telegram_notify_enabled` e
`telegram_notify_chat_id`, e a partir de 20/11/2026 também o que o x3 publica.
Este módulo só LÊ esses dados para o painel. Ele nunca envia nada.
Os nomes vêm do getChat do mesmo bot e ficam guardados em data/distribuicao-nomes.json.
"""
import json
import os
import sqlite3
import urllib.request
from datetime import datetime, timedelta

MASTER = os.path.expanduser('~/projetos/yt-pub-livesx-master')
ESTADO = os.environ.get('X3_NOTIFIER_ESTADO') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'notify_state.json')
ENV = os.path.join(MASTER, 'config', '.env')
NOMES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'distribuicao-nomes.json')


def _config_canal(canal):
    raiz = os.path.dirname(canal.get('lives_dir') or '')
    db = os.path.join(raiz, 'data', 'lives.db')
    if not raiz or not os.path.isfile(db):
        return False, []
    try:
        con = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=5)
        try:
            cfg = dict(con.execute("SELECT chave, valor FROM config WHERE chave LIKE 'telegram_notify%'").fetchall())
        finally:
            con.close()
    except Exception:
        return False, []
    chats = [c.strip() for c in (cfg.get('telegram_notify_chat_id') or '').replace(';', ',').split(',') if c.strip()]
    return (cfg.get('telegram_notify_enabled') or '').lower() == 'true', chats


def _token():
    try:
        for linha in open(ENV, encoding='utf-8'):
            if linha.startswith('TELEGRAM_NOTIFY_BOT_TOKEN='):
                return linha.split('=', 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return ''


def _nomes(chats):
    try:
        nomes = json.load(open(NOMES, encoding='utf-8'))
    except Exception:
        nomes = {}
    faltam = [c for c in chats if c not in nomes]
    tok = _token() if faltam else ''
    mudou = False
    for c in faltam:
        if not tok:
            break
        try:
            r = json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/getChat?chat_id={c}', timeout=8))['result']
            nome = ' '.join(x for x in (r.get('first_name'), r.get('last_name'), r.get('title')) if x).strip()
            nomes[c] = {'nome': nome or c, 'usuario': r.get('username') or ''}
            mudou = True
        except Exception:
            continue
    if mudou:
        try:
            os.makedirs(os.path.dirname(NOMES), exist_ok=True)
            json.dump(nomes, open(NOMES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        except OSError:
            pass
    return nomes


def ler(canais):
    try:
        st = json.load(open(ESTADO, encoding='utf-8'))
    except Exception:
        st = {}
    enviados = st.get('sent', [])
    d7 = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M')
    d1 = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')
    lista_canais, pessoas = [], {}
    for nome, c in sorted(canais.items(), key=lambda kv: int(''.join(ch for ch in kv[0] if ch.isdigit()) or 0)):
        ligado, chats = _config_canal(c)
        meus = [s for s in enviados if str(s.get('ref', '')).split(':')[0] in (nome, f'yt-pub-{nome}')]
        ultimo = max((s.get('at', '') for s in meus), default='')
        lista_canais.append({'nome': nome, 'titulo': c.get('destino_nome') or '', 'ligado': ligado, 'chats': chats,
                             'envios_7d': sum(1 for s in meus if s.get('at', '') >= d7), 'ultimo': ultimo})
        for ch in chats:
            p = pessoas.setdefault(ch, {'chat': ch, 'canais': [], 'desligados': []})
            (p['canais'] if ligado else p['desligados']).append(nome)
    nomes = _nomes(list(pessoas))
    for ch, p in pessoas.items():
        dele = [s for s in enviados if str(s.get('chat')) == ch]
        p.update(nome=nomes.get(ch, {}).get('nome', ch), usuario=nomes.get(ch, {}).get('usuario', ''),
                 envios_24h=sum(1 for s in dele if s.get('at', '') >= d1),
                 envios_7d=sum(1 for s in dele if s.get('at', '') >= d7),
                 ultimo=max((s.get('at', '') for s in dele), default=''))
    return {'bot': '@inemaytbot', 'cadastro_aberto': bool(st.get('enroll_open')),
            'pessoas': sorted(pessoas.values(), key=lambda p: (-len(p['canais']), p['nome'].lower())),
            'canais': lista_canais}
