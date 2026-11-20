"""Dados do painel: fila do x3 + leitura somente-leitura dos sistemas atuais."""
import collections
import glob
import json
import os
import re
import sqlite3
import time
import unicodedata
from datetime import datetime, timedelta

from . import VERSION, canais as canais_mod, config, db, login, migrar, runner, vigia

_cache = {'t': 0, 'v': {}}
GRUPOS = {'clipe': 'Clipe', 'import': 'Import'}
APELIDO = {'aventuras': 'lives26', 'espanhol': 'lives25'}   # nomes destes canais no histórico do yt-pubx
STATUS = ('aguardando', 'enviando', 'feito', 'erro', 'pausado', 'ignorado', 'conferir')


def _sem_acento(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto or '')) if not unicodedata.combining(c)).casefold()


def _acha(busca, *textos):
    """Todas as palavras da busca aparecem nos textos, sem ligar para acento ou maiúscula."""
    alvo = ' '.join(_sem_acento(t) for t in textos)
    return all(p in alvo for p in _sem_acento(busca).split())


def _historico_ytpubx(dias, cortes=None):
    """Por canal: n = pub + ag; ag = agendados; removidos não contam; `cortes` zera o que veio antes da migração."""
    h = collections.defaultdict(lambda: {'n': 0, 'ag': 0, 'pub': 0, 'h24': 0, 'd': collections.Counter(), 'env': collections.Counter()})
    agora = datetime.now().strftime('%Y-%m-%d %H:%M')
    d24 = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')
    try:
        f = open(config.historico_ytpubx(), encoding='utf-8')
    except OSError:
        return h
    registros, removidos = {}, set()
    with f:
        for i, l in enumerate(f):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get('removido'):
                removidos.add(r['removido'])
            else:
                registros[r.get('video_id') or f'sem-id-{i}'] = r
    for vid, r in registros.items():
        if vid in removidos:
            continue
        p = r.get('privacy') or {}
        q = str(p.get('publishAt') or r.get('data') or '')[:16].replace('T', ' ')
        if not r.get('canal') or not q or (p.get('privacyStatus') != 'public' and not p.get('publishAt')):
            continue
        if str(r.get('data') or '')[:16].replace('T', ' ') < (cortes or {}).get(r['canal'], ''):
            continue
        x = h[r['canal']]
        x['n'] += 1
        x['d'][q[:10]] += 1
        x['h24'] += d24 <= q <= agora
        x['ag'] += q > agora
        x['pub'] += q <= agora
        if q <= agora:
            h[APELIDO.get(r['canal'], r['canal'])]['env'][q[:10]] += 1
    return h


def _serie_antiga(nome, yp, dias):
    """YouTube por dia nos sistemas antigos, sem o corte da migração: é a história real do canal."""
    d = collections.Counter(yp['env'])
    p = os.path.join(config.legado_dir(), f'yt-pub-{nome}', 'data', 'lives.db')
    if os.path.exists(p):
        c = sqlite3.connect(f'file:{p}?mode=ro', uri=True, timeout=5)
        for v, q in c.execute('SELECT clip_video_id, data_publicacao FROM publicados'):
            if v not in ('erro_upload', 'publicando', ''):
                d[str(q)[:10]] += 1
        c.close()
    return [d[x] for x in dias]


def _recibos():
    out = collections.Counter()
    d = os.path.join(config.legado_dir(), 'metricool-inematds', 'estado')
    for p in glob.glob(os.path.join(d, '*.recibo.json')):
        try:
            m = re.search(r'blogId=(\d+)', open(p, encoding='utf-8').read())
            if m:
                out[int(m.group(1))] += 1
        except OSError:
            pass
    return out


def _legado(nome, yp, dias, corte=''):
    """Só lê o sistema antigo. Com `corte`, conta apenas o que surgiu depois da migração."""
    z = lambda: [0, 0, 0, 0, 0]
    o = {'imports': z(), 'clips': z(), 'lives': z(), 'ultimo_corte': ''}
    D = collections.Counter(yp['d'])
    p = os.path.join(config.legado_dir(), f'yt-pub-{nome}', 'data', 'lives.db')
    if os.path.exists(p):
        d24 = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M')
        c = sqlite3.connect(f'file:{p}?mode=ro', uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        L = {r['video_id']: r for r in c.execute('SELECT video_id,titulo,qtd_clips,clips_pendentes,status_cortes,data_corte,data_sync FROM lives')}
        tipo = lambda v: None if str(v).startswith('import_') and str(L[v]['titulo'] if v in L else '').startswith('TikTok @') else (
            'imports' if str(v).startswith('import_') else 'clips')
        for v, r in L.items():
            importado = str(v).startswith('import_')
            if str(r['data_sync' if importado else 'data_corte'] or '')[:16] < (corte[:10] if importado else corte):
                continue
            k = tipo(v)
            if k:
                o[k][0] += int(r['qtd_clips'] or 0)
                o[k][1] += int(r['clips_pendentes'] or 0)
            if not v.startswith('import_'):
                o['lives'][0] += 1
                s = r['status_cortes']
                o['lives'][1] += s == 'pendente'
                o['lives'][2] += s == 'concluido'
                o['lives'][3] += str(s).startswith('erro')
                dc = r['data_corte'] or ''
                o['lives'][4] += dc >= d24
                o['ultimo_corte'] = max(o['ultimo_corte'], dc)
        for r in c.execute('SELECT clip_video_id v, live_video_id l, data_publicacao d FROM publicados'):
            k, e = tipo(r['l']), r['v'] in ('erro_upload', 'publicando', '')
            if str(r['d'])[:16] < corte:
                continue
            if not e:
                D[str(r['d'])[:10]] += 1
            if k:
                o[k][3 if e else 2] += 1
                o[k][4] += (not e) and str(r['d']) >= d24
        c.close()
    o['historico'] = [D[d] for d in dias]
    o['entrada7'] = sum(yp['d'][d] for d in dias[-7:])  # o que chegou pelo yt-pubx e teria de caber na fila
    return o


def _manter_erros_e_pendentes(nome, canal, zerado, completo):
    """Canal zerado que mantém os erros antigos e só o que ainda tem arquivo para publicar."""
    pend = collections.Counter(x['grupo'] for x in migrar.selecionar(nome, canal['lives_dir'], clipes_pendentes=True, imports_pendentes=True)[0])
    for chave, grupo in (('imports', 'imports'), ('clips', 'clipes')):
        z = zerado[chave]
        z[1], z[3] = pend[grupo], completo[chave][3]
        z[0] = z[1] + z[2] + z[3]
    z = zerado['lives']
    z[1], z[3] = completo['lives'][1], completo['lives'][3]
    z[0] = z[1] + z[2] + z[3]
    return zerado


def legado(canais):
    if time.time() - _cache['t'] > 60:
        ontem = datetime.now().date() - timedelta(days=1)
        dias = [(ontem - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
        cortes_m = {n: c['migrado_em'] for n, c in canais.items() if c['migrado_em']}
        h = _historico_ytpubx(dias, cortes_m)
        h_completo = _historico_ytpubx(dias)
        hoje = ontem + timedelta(days=1)
        dias_serie = [(hoje - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
        v = {'dias': dias, 'dias_serie': dias_serie, 'recibos': _recibos(), 'canais': {}}
        for n, c in canais.items():
            try:
                o = _legado(n, h[n], dias, cortes_m.get(n, ''))
                ag = h[n]['ag']
                if c['manter_erros_e_pendentes'] and c['migrado_em']:
                    o = _manter_erros_e_pendentes(n, c, o, _legado(n, h_completo[n], dias))
                    ag = h_completo[n]['ag']
                v['canais'][n] = {**o, 'yt': [h[n]['pub'] + ag, ag, h[n]['pub'], '–', h[n]['h24']],
                                  'serie_antiga': _serie_antiga(n, h_completo[n], dias_serie)}
            except sqlite3.Error:
                v['canais'][n] = {}
        _cache.update(t=time.time(), v=v)
    return _cache['v']


def _contagem(con, nome, destino):
    r = {x['status']: x['n'] for x in con.execute('SELECT status, COUNT(*) n FROM entregas WHERE canal=? AND destino=? GROUP BY status', (nome, destino))}
    d24 = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    r['h24'] = con.execute("SELECT COUNT(*) FROM entregas WHERE canal=? AND destino=? AND status='feito' AND concluido_em>=?", (nome, destino, d24)).fetchone()[0]
    return r


def _contagem_clipes(con, nome):
    """Parte da contagem do YouTube que é de clipes (vídeos); o resto são imports (Shorts)."""
    d24 = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    r = {'h24': 0}
    for x in con.execute(f"""SELECT e.status, COUNT(*) n, SUM(e.status='feito' AND e.concluido_em>=?) h FROM entregas e JOIN itens i ON i.id=e.item_id
                             WHERE e.canal=? AND e.destino='youtube' AND {db.E_CLIPE} GROUP BY e.status""", (d24, nome)):
        r[x['status']] = x['n']
        r['h24'] += x['h'] or 0
    return r


def estado(con, canais):
    lg = legado(canais)
    out = []
    dias_serie = lg['dias_serie']
    x3 = collections.Counter()
    for r in con.execute("""SELECT canal, destino, substr(concluido_em,1,10) d, COUNT(*) n FROM entregas
                            WHERE status='feito' AND concluido_em>=? GROUP BY 1,2,3""", (dias_serie[0],)):
        x3[r['canal'], r['destino'], r['d']] = r['n']
    for n, c in canais.items():
        v = lg['canais'].get(n, {})
        antiga = v.get('serie_antiga') or [0] * len(dias_serie)
        serie = {'yt': [a + x3[n, 'youtube', d] for a, d in zip(antiga, dias_serie)], 'rs': [x3[n, 'rs', d] for d in dias_serie]}
        destinos = {}
        for d in ('youtube', 'rs'):
            e = db.estado_destino(con, n, d)
            destinos[d] = {'ligado': runner.ligado(con, c, d), 'pausa': e['pausa_motivo'], 'retomar_em': e['retomar_em'], 'n': _contagem(con, n, d)}
        destinos['youtube']['clipes'] = _contagem_clipes(con, n)
        s = len(c['youtube']['horarios']) * 7
        sem = v.get('entrada7', 0)
        out.append({'nome': n, 'titulo': c['destino_nome'] or 'Sem nome salvo', 'url': c['url'], 'ativo': c['ativo'], 'migrado_em': c['migrado_em'],
                    'youtube': c['youtube'], 'clipes': c['clipes'], 'rs': c['rs'], 'rs_herda': c['rs_herda'], 'cortes': c['cortes'], 'destinos': destinos, 'legado': v, 'serie': serie,
                    'vagas': s, 'semana': sem, 'recibos': lg['recibos'].get(c['rs']['blog_id'], 0), 'vigia': vigia.resumo(con, n),
                    'login': {**login.estado(con, n), 'proprio': login.proprio(c)}})
    return {'versao': VERSION, 'publicando': config.publicar_de_verdade(), 'agora': db.agora(), 'dias': lg['dias'], 'dias_serie': dias_serie, 'canais': out,
            'recusados': [dict(r) for r in con.execute('SELECT * FROM recusados ORDER BY id DESC LIMIT 30')]}


def salvar_horarios(con, nome, secao, horarios):
    """Grava os horários. O que já passou hoje não dispara: vale a partir da próxima vez."""
    salvos = canais_mod.definir_horarios(nome, secao, horarios)
    c = canais_mod.carregar()[nome]
    agora = datetime.now()
    grupos = [('yt', 'publicar', {'destino': 'youtube'}, c['youtube']['horarios']),
              ('clip', 'publicar', {'destino': 'youtube', 'grupo': 'clipes'}, c['clipes']['horarios']), ('rs', 'publicar', {'destino': 'rs'}, c['rs']['horarios']),
              ('corte', 'cortar', {}, c['cortes']['horarios'])]
    for prefixo, tipo, payload, lista in grupos:
        for hm in lista:
            quando = datetime.strptime(f'{agora:%Y-%m-%d} {hm}', '%Y-%m-%d %H:%M')
            if quando < agora:
                job = db.add_job(con, nome, tipo, quando.strftime('%Y-%m-%d %H:%M:%S'), json.dumps(payload), f'{prefixo}:{nome}:{agora:%Y-%m-%d} {hm}')
                if job:
                    db.fim_job(con, job, True, 'horário ligado depois da hora')
    return salvos


def _proximos(horarios, n):
    agora, out, dia = datetime.now(), [], 0
    while horarios and len(out) < n:
        base = (agora + timedelta(days=dia)).strftime('%Y-%m-%d')
        out += [f'{base} {h}' for h in horarios if f'{base} {h}' > agora.strftime('%Y-%m-%d %H:%M')]
        dia += 1
    return out[:n]


def _dias(n, horarios):
    return -(-n // len(horarios)) if n and horarios else 0


def _formato(largura, altura, duracao):
    return 'Short' if largura and altura and largura < altura and (duracao or 0) <= 180 else 'Vídeo'


def _externos():
    """Filas fora do x3, só leitura: agendados no YouTube, episódios do Aventuras e Radar Viral."""
    out, raiz = collections.defaultdict(list), config.legado_dir()
    agora = datetime.now().strftime('%Y-%m-%dT%H:%M')
    regs, removidos = [], set()
    try:
        with open(config.historico_ytpubx(), encoding='utf-8') as f:
            for l in f:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                removidos.add(r['removido']) if r.get('removido') else regs.append(r)
    except OSError:
        pass
    for r in regs:
        q = str((r.get('privacy') or {}).get('publishAt') or '')[:16]
        if q > agora and r.get('video_id') not in removidos:
            out[APELIDO.get(r.get('canal'), r.get('canal'))].append({'fonte': 'Agendado no YouTube', 'titulo': r.get('titulo') or '', 'quando': q.replace('T', ' ')})
    try:
        with open(os.path.join(raiz, 'aventurasinemavideo', 'fila.json'), encoding='utf-8') as f:
            episodios = json.load(f)
    except (OSError, ValueError):
        episodios = []
    for ep in episodios:
        titulo = ep.get('ep', '')
        try:
            with open(ep.get('plano') or '', encoding='utf-8') as f:
                yt = json.load(f).get('youtube') or {}
            titulo = yt.get('titulo') or yt.get('title') or titulo
        except (OSError, ValueError):
            pass
        out['lives26'].append({'fonte': 'Episódio do Aventuras', 'titulo': titulo, 'quando': ''})
    try:
        with open(os.path.join(raiz, 'radar-viral', 'radar.json'), encoding='utf-8') as f:
            nichos = json.load(f).get('nichos', [])
    except (OSError, ValueError):
        nichos = []
    for n in nichos:
        for p in glob.glob(os.path.join(raiz, n.get('projeto', ''), 'edicoes', '*', 'PUBLICAR_PENDENTE.*')):
            if re.search(r'\.(feito|segurado|esquecido|erro|tentativas|sem-metricool)$', p):
                continue
            try:
                with open(os.path.join(os.path.dirname(p), 'legenda.txt'), encoding='utf-8') as f:
                    titulo = f.readline().strip()
            except OSError:
                titulo = os.path.basename(p).split('.', 1)[1]
            out[n.get('canal', '')].append({'fonte': f"Radar · {n.get('nome', '')}", 'titulo': titulo, 'quando': ''})
    return out


def filas(con, canais, limite=30, busca='', tipo='', canal=''):
    """Filas por canal. O filtro olha a fila inteira; `limite` só corta o que volta para a tela."""
    externos, out = _externos(), []
    filtrando = bool(busca.strip() or tipo or canal)
    for nome, c in canais.items():
        if canal and nome != canal:
            continue
        ligado = c['ativo'] and runner.ligado(con, c, 'youtube')
        base = "FROM entregas e JOIN itens i ON i.id=e.item_id WHERE e.canal=? AND e.destino='youtube' AND e.status='aguardando'"
        linhas = con.execute(f"""SELECT i.titulo, i.origem, i.quando, i.largura, i.altura, i.duracao, {db.E_CLIPE} clipe {base}
            ORDER BY e.id""", (nome,)).fetchall()
        total, n_clipes = len(linhas), sum(r['clipe'] for r in linhas)
        h_yt, h_clip = c['youtube']['horarios'], c['clipes']['horarios']
        # O horário depende da posição na fila inteira, por isso é calculado antes de filtrar.
        if h_clip:
            dias = max(_dias(total - n_clipes, h_yt), _dias(n_clipes, h_clip))
            prox = {1: iter(_proximos(h_clip, n_clipes) if ligado else []), 0: iter(_proximos(h_yt, total - n_clipes) if ligado else [])}
        else:
            dias = _dias(total, h_yt)
            todos = iter(_proximos(h_yt, total) if ligado else [])
            prox = {1: todos, 0: todos}
        itens = [{'titulo': r['titulo'], 'origem': r['origem'].split(':')[1] if r['origem'].startswith('migrado:') else r['origem'],
                  'formato': _formato(r['largura'], r['altura'], r['duracao']), 'grupo': 'Clipe' if r['clipe'] else 'Import',
                  'quando': r['quando'] if r['quando'] not in ('fila', 'agora') else (next(prox[r['clipe']], '') if r['quando'] == 'fila' else 'agora')} for r in linhas]
        achados = [] if tipo == 'fora' else [i for i in itens if (tipo not in GRUPOS or i['grupo'] == GRUPOS[tipo]) and _acha(busca, i['titulo'], i['origem'])]
        fora = [] if tipo in GRUPOS else [x for x in externos.get(nome, []) if _acha(busca, x['titulo'], x['fonte'])]
        fora.sort(key=lambda x: x['quando'] or '9')
        if achados or fora or (total and not filtrando):
            out.append({'nome': nome, 'titulo': c['destino_nome'] or 'Sem nome salvo', 'ativo': c['ativo'], 'ligado': ligado,
                        'por_dia': len(h_yt) + len(h_clip), 'dias': dias, 'clipes': n_clipes, 'total': total, 'achados': len(achados),
                        'itens': achados[:limite], 'externos': fora})
    return out


def itens_canal(con, nome, busca='', tipo='', status='', limite=100):
    """Publicações do canal, mais novas primeiro. O filtro olha todas; `limite` só corta a resposta."""
    sql, args = 'SELECT i.* FROM itens i WHERE i.canal=?', [nome]
    if tipo in GRUPOS:
        sql += f" AND {'' if tipo == 'clipe' else 'NOT '}{db.E_CLIPE}"
    if status in STATUS:
        sql += ' AND EXISTS (SELECT 1 FROM entregas e WHERE e.item_id=i.id AND e.status=?)'
        args.append(status)
    achados = [i for i in con.execute(sql + ' ORDER BY i.id DESC', args).fetchall() if _acha(busca, i['titulo'], i['origem'])]
    itens = []
    for i in achados[:limite]:
        e = [dict(x) for x in con.execute('SELECT id,destino,status,motivo,tentativas,url,atualizado_em FROM entregas WHERE item_id=? ORDER BY destino DESC', (i['id'],))]
        itens.append({'id': i['id'], 'tipo': i['tipo'], 'titulo': i['titulo'], 'origem': i['origem'], 'quando': i['quando'], 'largura': i['largura'],
                      'altura': i['altura'], 'duracao': round(i['duracao']), 'capa': i['capa_status'], 'capa_motivo': i['capa_motivo'], 'entregas': e})
    lives = [dict(r) for r in con.execute('SELECT video_id,titulo,data_live,status,qtd_clips,erro FROM lives WHERE canal=? ORDER BY data_live DESC LIMIT 30', (nome,))]
    return {'itens': itens, 'total': len(achados), 'lives': lives}
