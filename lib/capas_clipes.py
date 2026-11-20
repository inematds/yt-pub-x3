"""Capas dos últimos clipes: troca, todo dia, a capa dos clipes que saíram sem capa do Codex.

Gera de madrugada (só Codex, sem cota) e sobe pouco antes da virada da cota do YouTube (meia-noite do Pacífico =
04:00/05:00 de Brasília), gastando a cota que sobrou do dia. Clipe com capa já trocada não é refeito.
Fontes: itens do x3 com capa pendente e clipes do agendador antigo cuja capa caiu no fundo liso (log do systemd).
"""
import os
import re
import sqlite3
import subprocess

from . import config, db, ia, youtube

RECUSA_CAPA = 'permissions to upload and set custom'


def _log_antigo(nome):
    """{video_id: 'liso'|'ia'} pelo log do agendador antigo do canal (yt-scheduler<N>)."""
    n = nome.replace('lives', '')
    try:
        txt = subprocess.run(['journalctl', '--user', '-u', f'yt-scheduler{n}', '--since', '-30 days', '--no-pager', '-o', 'cat'],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return {}
    out, cur = {}, None
    for l in txt.splitlines():
        m = re.search(r'Generating (?:API|local|fallback) thumbnail for (\S+)', l)
        if m:
            cur = m.group(1)
            continue
        if cur and ('Usando fallback local' in l or 'Thumbnail (fallback)' in l):
            out[cur] = 'liso'
        elif cur and 'Thumbnail salva' in l:
            out.setdefault(cur, 'ia')
        if cur and ('Thumbnail uploaded for' in l or 'upload failed' in l):
            cur = None
    return out


def _clipes_antigos(nome, limite=None):
    """Clipes de live do agendador antigo, do mais novo para o mais velho."""
    p = os.path.join(config.legado_dir(), f'yt-pub-{nome}', 'data', 'lives.db')
    if not os.path.exists(p):
        return []
    v = sqlite3.connect(f'file:{p}?mode=ro', uri=True, timeout=10)
    try:
        return [r[0] for r in v.execute("""SELECT clip_video_id FROM publicados WHERE clip_video_id NOT LIKE 'erro%' AND clip_video_id NOT LIKE 'moved_%'
                    AND clip_video_id NOT IN ('', 'publicando') AND live_video_id NOT LIKE 'import_%' AND privacy='public'
                    ORDER BY id DESC LIMIT ?""", (limite or -1,))]
    finally:
        v.close()


def candidatos(con, canal, log_antigo=None):
    """[(video_id, item_id ou None)] até `por_dia`: primeiro os últimos clipes sem capa do Codex,
    depois (com `retroativo`) os clipes antigos do mais novo para o mais velho, até todos terem capa do Codex."""
    cc = canal['capas_clipes']
    nome, ultimos, por_dia = canal['nome'], int(cc['ultimos']), int(cc['por_dia'])
    feitos = {r[0] for r in con.execute("SELECT video_id FROM capas_clipes WHERE canal=? AND status IN ('gerada','aplicada','erro')", (nome,))}
    out = []
    for r in con.execute("""SELECT e.ref, i.id FROM entregas e JOIN itens i ON i.id=e.item_id WHERE i.canal=? AND e.destino='youtube'
                            AND e.status='feito' AND e.ref!='' AND i.tipo IN ('clip','video') AND i.capa_status='pendente'
                            ORDER BY e.concluido_em DESC LIMIT ?""", (nome, ultimos)):
        if r[0] not in feitos:
            out.append((r[0], r[1]))
    antigos = _clipes_antigos(nome)
    if antigos:
        marca = (log_antigo or _log_antigo)(nome)
        recentes = antigos[:ultimos]
        out += [(v, None) for v in recentes if marca.get(v) == 'liso' and v not in feitos]
        if cc['retroativo']:  # o resto do dia anda para trás no histórico, até todos terem a thumb viral do Codex
            ja = {v for v, _ in out}
            out += [(v, None) for v in antigos if v not in feitos and v not in ja]
    return out[:por_dia]


def _gravar(con, nome, vid, item_id, status, capa='', msg=''):
    con.execute("""INSERT INTO capas_clipes(canal,video_id,item_id,status,capa,msg,em) VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(canal,video_id) DO UPDATE SET status=excluded.status, capa=excluded.capa, msg=excluded.msg, em=excluded.em""",
                (nome, vid, item_id, status, capa, msg[:300], db.agora()))


def gerar(con, canal, simular, log=print, log_antigo=None, ler=None, capa=None):
    """Gera no Codex as capas que faltam. Não gasta cota de envio (só lê os títulos)."""
    nome = canal['nome']
    if db.capa_permissao(con, nome) == 'nao':
        return 'canal sem permissão de capa'
    # Capa gerada que ainda não subiu ocupa vaga do dia: o YouTube limita as trocas de capa por canal (HTTP 429).
    na_fila = con.execute("SELECT COUNT(*) FROM capas_clipes WHERE canal=? AND status='gerada'", (nome,)).fetchone()[0]
    cands = candidatos(con, canal, log_antigo)[:max(0, int(canal['capas_clipes']['por_dia']) - na_fila)]
    if simular or not cands:
        return 'simulado: ' + ', '.join(v for v, _ in cands) if simular else 'nada a trocar'
    snip = (ler or youtube.snippets)([v for v, _ in cands], canal['config_dir'])
    feitos = 0
    for vid, item_id in cands:
        s = snip.get(vid)
        if not s:
            _gravar(con, nome, vid, item_id, 'erro', msg='vídeo não encontrado no canal')
            continue
        pasta = os.path.join(config.acervo_dir(), nome, f'capa-{vid}')
        try:
            jpg = (capa or ia.gerar_capa)(nome, s.get('title', ''), s.get('description', ''), pasta)
            _gravar(con, nome, vid, item_id, 'gerada', jpg)
            feitos += 1
        except Exception as e:
            _gravar(con, nome, vid, item_id, 'erro', msg=str(e))
            log(f'{nome}: capa de {vid} falhou: {e}')
    return f'{feitos} de {len(cands)} capa(s) gerada(s)'


def subir(con, canal, simular, log=print, definir=None):
    """Sobe as capas geradas. Cota acabou: para e tenta de novo amanhã."""
    nome = canal['nome']
    prontas = con.execute("SELECT * FROM capas_clipes WHERE canal=? AND status='gerada'", (nome,)).fetchall()
    if simular:
        return f'simulado: {len(prontas)} capa(s) para subir'
    n = 0
    for r in prontas:
        try:
            (definir or youtube.definir_capa)(r['video_id'], r['capa'], canal['config_dir'])
        except Exception as e:
            if RECUSA_CAPA in str(e):
                db.definir_capa_permissao(con, nome, 'nao', str(e))
                return f'{n} trocada(s); canal sem permissão de capa'
            if 'too many thumbnails' in str(e):
                return f'{n} trocada(s); limite de troca de capas do YouTube, o resto vai amanhã'
            if 'quota' in str(e).lower() or 'HTTP 429' in str(e):
                return f'{n} trocada(s); cota acabou, o resto vai amanhã'
            _gravar(con, nome, r['video_id'], r['item_id'], 'gerada', r['capa'], str(e))
            continue
        _gravar(con, nome, r['video_id'], r['item_id'], 'aplicada', r['capa'])
        if r['item_id']:
            con.execute("UPDATE itens SET capa=?, capa_status='aplicada', capa_motivo='' WHERE id=?", (r['capa'], r['item_id']))
        n += 1
    return f'{n} capa(s) trocada(s)'
