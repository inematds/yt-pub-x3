"""Leva clipes e imports de um yt-pub-livesN para a fila de outro canal do x3.

O sistema antigo só é lido. Os arquivos ficam onde estão e a fila aponta para eles.
"""
import collections
import json
import os
import re
import sqlite3
import unicodedata

from . import config, db, entrada, midia

RUINS = ('erro_upload', 'publicando', '')


def _norm(texto):
    t = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\W+', ' ', t).strip()


def _registros(con):
    """Registros por live e títulos já publicados no canal. O antigo grava ora clip_id, ora nome do arquivo."""
    por_live, titulos_ok = collections.defaultdict(list), set()
    for live, fn, vid, titulo in con.execute('SELECT live_video_id, filename, clip_video_id, clip_titulo FROM publicados'):
        por_live[live].append((fn or '', vid or '', _norm(titulo)))
        if (vid or '') not in RUINS and _norm(titulo):
            titulos_ok.add(_norm(titulo))
    return por_live, titulos_ok


def situacao(clipe, vid, por_live, titulos_ok):
    """'publicado', 'erro', 'indefinido' (envio que pode ter saído) ou 'pendente'."""
    arquivo = os.path.basename(clipe.get('file') or '')
    ids = {f'{vid}_{clipe.get("index", 0)}', clipe.get('filename') or '', arquivo} - {''}
    titulo = _norm(clipe.get('title'))
    achados = {v for fn, v, t in por_live.get(vid, []) if fn in ids or (titulo and t == titulo)}
    if achados - set(RUINS) or titulo in titulos_ok:
        return 'publicado'
    if achados - {'erro_upload'}:
        return 'indefinido'
    return 'erro' if achados else 'pendente'


def selecionar(nome, lives_dir, clipes_pendentes=False, clipes_erro=False, imports_erro=False, imports_pendentes=False, orfaos_desde=''):
    """Devolve (lista de clipes escolhidos, contagem do que ficou de fora).

    orfaos_desde: live cortada pelo antigo a partir desta data e sem nenhum clipe publicado conta como pendente mesmo
    com clips_pendentes=0 (o antigo parou de publicar em 17/11/2026 e deixou os cortes novos sem pendência)."""
    arq = os.path.join(config.legado_dir(), f'yt-pub-{nome}', 'data', 'lives.db')
    con = sqlite3.connect(f'file:{arq}?mode=ro', uri=True, timeout=5)
    try:
        por_live, titulos_ok = _registros(con)
        cols = {r[1] for r in con.execute('PRAGMA table_info(lives)')}
        extra = ', '.join(c if c in cols else d for c, d in (('data_corte', "''"), ('clips_publicados', '0')))
        lives = con.execute(f'SELECT video_id, titulo, clips_pendentes, {extra} FROM lives ORDER BY rowid').fetchall()
    finally:
        con.close()
    escolhidos, fora = [], collections.Counter()
    for vid, titulo, pendentes, data_corte, publicados in lives:
        orfa = bool(orfaos_desde) and str(data_corte) >= orfaos_desde and not int(publicados or 0)
        importado = str(vid).startswith('import_')
        tiktok = importado and str(titulo or '').startswith('TikTok @')
        try:
            with open(os.path.join(lives_dir, vid, 'clips_manifest.json'), encoding='utf-8') as f:
                manifesto = json.load(f)
        except (OSError, ValueError):
            continue
        for c in manifesto if isinstance(manifesto, list) else []:
            cid = f'{vid}_{c.get("index", 0)}'
            st = situacao(c, vid, por_live, titulos_ok)
            if st == 'indefinido':
                fora['envio indefinido'] += 1
            if st == 'pendente' and not int(pendentes or 0) and not orfa:
                fora['sem pendência no sistema antigo'] += 1
                continue
            pend, erro = (imports_pendentes, imports_erro) if importado else (clipes_pendentes, clipes_erro)
            if not ((pend and st == 'pendente') or (erro and st == 'erro')):
                continue
            arquivo = c.get('file') or ''
            if not os.path.isfile(arquivo):
                arquivo = os.path.join(lives_dir, vid, 'clips', c.get('filename') or os.path.basename(arquivo))
            if tiktok:
                fora['import do TikTok'] += 1
            elif c.get('paused'):
                fora['pausado'] += 1
            elif not os.path.isfile(arquivo) or not os.path.getsize(arquivo):
                fora['sem arquivo'] += 1
            elif not str(c.get('title') or '').strip():
                fora['sem título'] += 1
            else:
                escolhidos.append({**c, 'file': arquivo, 'clip_id': cid, 'origem_canal': nome, 'situacao': st,
                                   'grupo': 'imports' if importado else 'clipes'})
    return escolhidos, fora


def enfileirar(con, destino, clipes):
    """Cria os itens no canal de destino. Repetir não duplica. Devolve (novos, repetidos)."""
    novos = repetidos = 0
    for c in clipes:
        arq = c['file']
        sha = midia.sha256([arq])
        if db.ja_existe(con, destino['nome'], sha) or entrada.ja_no_ytpubx(destino['nome'], sha, arq):
            repetidos += 1
            continue
        l, a, d = midia.probe(arq)
        titulo = str(c['title']).strip()
        tags = c.get('tags') or []
        pasta = os.path.join(config.acervo_dir(), destino['nome'], f"migrado-{c['clip_id']}")
        item_id = db.add_item(con, canal=destino['nome'], tipo='clip', pasta=pasta, arquivos=json.dumps([arq]), titulo=titulo,
                              descricao=str(c.get('description') or titulo).strip(), texto_rs='',
                              tags=','.join(map(str, tags)) if isinstance(tags, list) else str(tags),
                              privacy=destino['youtube']['privacy'], capa_status=entrada.capa_inicial('clip', '', l, a, d),
                              sha256=sha, origem=f"migrado:{c['origem_canal']}:{c['clip_id']}", largura=l, altura=a,
                              duracao=d or float(c.get('duration') or 0))
        entrada.criar_entregas(con, item_id, destino, ['youtube'])
        novos += 1
    return novos, repetidos
