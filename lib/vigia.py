"""Alerta de shadowban: confere as views de cada post depois de publicado e marca o destino como travado.

Começa desligado em todo canal. Ligado, só confere o que foi publicado depois de ligar.
- YouTube: lê as views pela YouTube Data API (videos.list, 1 unidade por até 50 vídeos) após `espera_yt` minutos.
- RS: não lê nada novo; usa a foto diária do Metricool que o verdade-das-redes já grava, após `espera_rs` horas.
Travado só bloqueia a publicação quando a pausa automática do canal está ligada. Destravar é sempre manual.
"""
import glob
import json
import os
import re
import statistics
import unicodedata
from datetime import datetime, timedelta

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS vigia (
  canal TEXT NOT NULL, destino TEXT NOT NULL, ligado INTEGER NOT NULL DEFAULT 0, ligado_em TEXT NOT NULL DEFAULT '',
  travado INTEGER NOT NULL DEFAULT 0, motivo TEXT NOT NULL DEFAULT '', desde TEXT NOT NULL DEFAULT '', PRIMARY KEY(canal, destino));
CREATE TABLE IF NOT EXISTS vigia_cfg (canal TEXT PRIMARY KEY, dados TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS vigia_leituras (
  id INTEGER PRIMARY KEY AUTOINCREMENT, entrega_id INTEGER NOT NULL, canal TEXT NOT NULL, destino TEXT NOT NULL,
  rede TEXT NOT NULL DEFAULT '', etapa TEXT NOT NULL, views INTEGER, idade_min INTEGER NOT NULL, lido_em TEXT NOT NULL,
  resultado TEXT NOT NULL DEFAULT '', UNIQUE(entrega_id, rede, etapa));
CREATE INDEX IF NOT EXISTS idx_vigia_leituras ON vigia_leituras(canal, destino, etapa);
"""

PADRAO = {'limite_yt': 20, 'espera_yt': 120, 'limite_rs': 20, 'espera_rs': 24, 'seguidos': 2, 'auto_pausa': False, 'so_shorts': True}
FAIXAS = {'limite_yt': (0, 100000), 'espera_yt': (15, 1440), 'limite_rs': (0, 100000), 'espera_rs': (12, 72), 'seguidos': (1, 10)}
DESISTE_H = 96          # post que não deu para ler em 4 dias sai da conferência
INTERVALO_MIN = 15      # o hub agenda uma conferência por canal a cada 15 min
# Fotos do verdade-das-redes: blogId do Metricool → prefixo do arquivo (coleta/metricool.sh, VR_MARCAS).
MARCAS_FOTO = {7797870: 'inema-tds', 7800440: 'eventosextremos', 7908265: 'ftd'}
# conjunto: (rede, {campo: índice da coluna}) — mesma ordem de coleta/junta.py do verdade-das-redes
COLUNAS = {'tiktok': ('tiktok', {'views': 3, 'likes': 4, 'comentarios': 5, 'compart': 6, 'alcance': 7}),
           'ig-reels': ('instagram', {'views': 2, 'alcance': 3, 'likes': 5, 'comentarios': 6, 'compart': 7, 'salvos': 8})}
EXTRAS = ('likes', 'comentarios', 'compart', 'salvos', 'alcance')
TAXAS = (('compart', 'Compartilhamento'), ('likes', 'Curtida'), ('comentarios', 'Comentário'), ('salvos', 'Salvo'))


def preparar(con):
    con.executescript(SCHEMA)
    tem = {r['name'] for r in con.execute('PRAGMA table_info(vigia_leituras)')}
    for k in EXTRAS:
        if k not in tem:
            con.execute(f'ALTER TABLE vigia_leituras ADD COLUMN {k} INTEGER')


def _stats(x):
    """Leitor pode devolver só as views (int) ou um dicionário com os outros números."""
    if x is None:
        return None
    return dict(x) if isinstance(x, dict) else {'views': int(x)}


def agora():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _dt(s):
    return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')


# ---------- configuração e estado ----------

def cfg(con, canal):
    r = con.execute('SELECT dados FROM vigia_cfg WHERE canal=?', (canal,)).fetchone()
    return {**PADRAO, **(json.loads(r['dados']) if r else {})}


def salvar_cfg(con, canal, novo):
    atual = cfg(con, canal)
    for k, v in (novo or {}).items():
        if k not in PADRAO:
            raise ValueError(f'campo desconhecido: {k}')
        if k in ('auto_pausa', 'so_shorts'):
            atual[k] = bool(v)
            continue
        n = int(v)
        lo, hi = FAIXAS[k]
        if not lo <= n <= hi:
            raise ValueError(f'{k} precisa ficar entre {lo} e {hi}')
        atual[k] = n
    con.execute('INSERT INTO vigia_cfg(canal,dados) VALUES(?,?) ON CONFLICT(canal) DO UPDATE SET dados=excluded.dados',
                (canal, json.dumps(atual)))
    return atual


def estado(con, canal, destino):
    r = con.execute('SELECT * FROM vigia WHERE canal=? AND destino=?', (canal, destino)).fetchone()
    return dict(r) if r else {'canal': canal, 'destino': destino, 'ligado': 0, 'ligado_em': '', 'travado': 0, 'motivo': '', 'desde': ''}


def _garante(con, canal, destino):
    con.execute('INSERT OR IGNORE INTO vigia(canal,destino) VALUES(?,?)', (canal, destino))


def ligar(con, canal, destino, ligado):
    """Ligar de novo reinicia a contagem: só o que for publicado daqui em diante é conferido."""
    _garante(con, canal, destino)
    if ligado:
        con.execute('UPDATE vigia SET ligado=1, ligado_em=? WHERE canal=? AND destino=? AND ligado=0', (agora(), canal, destino))
    else:
        con.execute('UPDATE vigia SET ligado=0 WHERE canal=? AND destino=?', (canal, destino))


def destravar(con, canal, destino):
    """Libera o destino. A sequência recomeça: o que já estava baixo não trava de novo."""
    _garante(con, canal, destino)
    con.execute("UPDATE vigia SET travado=0, motivo='', desde=?, ligado_em=CASE WHEN ligado=1 THEN ? ELSE ligado_em END WHERE canal=? AND destino=?",
                ('', agora(), canal, destino))


def bloqueia(con, canal, destino):
    """Motivo para não publicar, ou ''. Só bloqueia com a pausa automática ligada."""
    e = estado(con, canal, destino)
    if e['travado'] and cfg(con, canal)['auto_pausa']:
        return f"travado pelo alerta de shadowban desde {e['desde'][:16]}: {e['motivo']}"
    return ''


# ---------- leitores (trocados nos testes) ----------

def ler_youtube(canal, ids):
    from . import youtube
    return youtube.visualizacoes(ids, canal['config_dir'])


def _norm(s):
    s = re.sub(r'#\w+', ' ', str(s or ''))
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).casefold()
    return ' '.join(re.findall(r'\w+', s))


def foto_dir():
    return os.path.expanduser(os.environ.get('X3_VIGIA_FOTOS') or os.path.join(config.PROJETOS, 'verdade-das-redes', 'dados', 'metricool'))


def ler_rs(canal, itens):
    """{entrega_id: {rede: views}} a partir da foto mais nova do Metricool. Post não achado fica de fora."""
    prefixo = MARCAS_FOTO.get(int(canal['rs'].get('blog_id') or 0))
    dias = sorted(glob.glob(os.path.join(foto_dir(), '20??-??-??')))
    if not prefixo or not dias:
        return {}
    linhas = []
    for conj, (rede, cols) in COLUNAS.items():
        try:
            with open(os.path.join(dias[-1], f'{prefixo}-{conj}.json'), encoding='utf-8') as f:
                rows = json.load(f).get('rows') or []
        except (OSError, ValueError):
            continue
        for r in rows:
            try:
                quando = datetime.strptime(str(r[0])[:14], '%Y%m%d%H%M%S')
                num = {}
                for k, i in cols.items():
                    try:
                        num[k] = int(float(r[i])) if r[i] not in (None, '') else None
                    except (IndexError, ValueError, TypeError):
                        num[k] = None
                if num['views'] is None:
                    continue
                linhas.append((rede, quando, _norm(r[1]), num))
            except (ValueError, IndexError, TypeError):
                continue
    out = {}
    for it in itens:
        alvo = _norm(it['titulo'])[:50]
        if len(alvo) < 12:
            continue
        pub = _dt(it['concluido_em'])
        for rede, quando, texto, num in linhas:
            if texto.startswith(alvo) and timedelta(hours=-2) <= quando - pub <= timedelta(hours=36):
                out.setdefault(it['entrega_id'], {})[rede] = num
    return out


LEITORES = {'youtube': None, 'rs': None}   # None = leitores reais acima


# ---------- conferência ----------

def _candidatos(con, canal, destino, espera_min, etapa, so_shorts=False):
    e = estado(con, canal, destino)
    if not e['ligado'] or not e['ligado_em']:
        return []
    limite = (datetime.now() - timedelta(minutes=espera_min)).strftime('%Y-%m-%d %H:%M:%S')
    velho = (datetime.now() - timedelta(hours=DESISTE_H)).strftime('%Y-%m-%d %H:%M:%S')
    sql = f"""SELECT e.id entrega_id, e.ref, e.concluido_em, i.titulo FROM entregas e JOIN itens i ON i.id=e.item_id
        WHERE e.canal=? AND e.destino=? AND e.status='feito' AND e.ref!='' AND e.concluido_em>=? AND e.concluido_em<=? AND e.concluido_em>=?
        {"AND i.privacy='public'" if destino == 'youtube' else "AND i.tipo='video'"}
        {"AND i.largura>0 AND i.largura<i.altura AND i.duracao<=180" if so_shorts else ''}
        AND NOT EXISTS (SELECT 1 FROM vigia_leituras l WHERE l.entrega_id=e.id AND l.etapa=?) ORDER BY e.concluido_em"""
    return [dict(r) for r in con.execute(sql, (canal, destino, e['ligado_em'], limite, velho, etapa))]


def _gravar(con, c, destino, rede, etapa, st, resultado):
    st = st or {}
    idade = int((datetime.now() - _dt(c['concluido_em'])).total_seconds() // 60)
    con.execute(f"""INSERT OR IGNORE INTO vigia_leituras(entrega_id,canal,destino,rede,etapa,views,idade_min,lido_em,resultado,{','.join(EXTRAS)})
                    VALUES(?,?,?,?,?,?,?,?,?{',?' * len(EXTRAS)})""",
                (c['entrega_id'], c['canal'], destino, rede, etapa, st.get('views'), idade, agora(), resultado, *(st.get(k) for k in EXTRAS)))


def _sequencia(con, canal, destino, n):
    """As n verificações mais recentes do destino, da mais nova para a mais velha."""
    return [r['resultado'] for r in con.execute(
        """SELECT l.entrega_id, MIN(l.resultado) resultado FROM vigia_leituras l JOIN entregas e ON e.id=l.entrega_id
           WHERE l.canal=? AND l.destino=? AND l.etapa='verifica' AND l.resultado IN ('baixo','ok') AND e.concluido_em>?
           GROUP BY l.entrega_id ORDER BY e.concluido_em DESC LIMIT ?""", (canal, destino, estado(con, canal, destino)['ligado_em'], n))]


def conferir(con, canal, avisar=print, log=print):
    """Uma rodada do alerta para um canal. Devolve um resumo curto para o job."""
    nome, c, feitos = canal['nome'], cfg(con, canal['nome']), []
    for destino in ('youtube', 'rs'):
        if not estado(con, nome, destino)['ligado'] or (destino == 'rs' and not canal['rs'].get('provedor')):
            continue
        if destino == 'youtube':
            cand = _candidatos(con, nome, 'youtube', c['espera_yt'], 'verifica', c['so_shorts'])  # Nei 20/11: por ora só Shorts travam; a leitura de 24 h segue em tudo
            dia = _candidatos(con, nome, 'youtube', 24 * 60, 'dia')
            todos = {x['ref']: x for x in cand + dia}
            leitor = LEITORES['youtube'] or ler_youtube
            st = {}
            refs = list(todos)
            for i in range(0, len(refs), 50):
                st.update({k: _stats(v) for k, v in leitor(canal, refs[i:i + 50]).items()})
            for x in cand:
                x['canal'] = nome
                v = (st.get(x['ref']) or {}).get('views')
                _gravar(con, x, 'youtube', 'youtube', 'verifica', st.get(x['ref']), 'sumiu' if v is None else 'baixo' if v < c['limite_yt'] else 'ok')
            for x in dia:
                x['canal'] = nome
                _gravar(con, x, 'youtube', 'youtube', 'dia', st.get(x['ref']), '')
            lidos = [(x, {'youtube': (st.get(x['ref']) or {}).get('views')}) for x in cand]
            limite = c['limite_yt']
        else:
            cand = _candidatos(con, nome, 'rs', c['espera_rs'] * 60, 'verifica')
            achados = (LEITORES['rs'] or ler_rs)(canal, cand) if cand else {}
            lidos = []
            for x in cand:
                x['canal'] = nome
                redes = achados.get(x['entrega_id'])
                if not redes:
                    if (datetime.now() - _dt(x['concluido_em'])).total_seconds() > (c['espera_rs'] + 48) * 3600:
                        _gravar(con, x, 'rs', '', 'verifica', None, 'sem_dado')
                    continue
                redes = {r: _stats(v) for r, v in redes.items()}
                for rede, v in redes.items():
                    _gravar(con, x, 'rs', rede, 'verifica', v, 'baixo' if v['views'] < c['limite_rs'] else 'ok')
                lidos.append((x, {r: v['views'] for r, v in redes.items()}))
            limite = c['limite_rs']
        for x, redes in lidos:
            baixos = {r: v for r, v in redes.items() if v is not None and v < limite}
            if baixos:
                avisar(f"{nome}: post com poucas views ({', '.join(f'{r} {v}' for r, v in baixos.items())}, limite {limite}): {x['titulo'][:60]}", log)
        seq = _sequencia(con, nome, destino, c['seguidos'])
        e = estado(con, nome, destino)
        if not e['travado'] and len(seq) == c['seguidos'] and all(s == 'baixo' for s in seq):
            ultimos = [x['entrega_id'] for x, _ in lidos][-c['seguidos']:] or [0]
            redes = sorted({r['rede'] for r in con.execute(
                f"SELECT DISTINCT rede FROM vigia_leituras WHERE resultado='baixo' AND etapa='verifica' AND entrega_id IN ({','.join('?' * len(ultimos))})", ultimos)})
            motivo = f"{c['seguidos']} post(s) seguidos abaixo de {limite} views" + (f" no {' e '.join(redes)}" if destino == 'rs' and redes else '')
            con.execute('UPDATE vigia SET travado=1, motivo=?, desde=? WHERE canal=? AND destino=?', (motivo, agora(), nome, destino))
            extra = 'Publicação PAUSADA até você destravar.' if c['auto_pausa'] else 'A publicação continua (pausa automática desligada).'
            avisar(f"{nome}: {destino} TRAVADO pelo alerta de shadowban: {motivo}. {extra} Destravar no painel do canal.", log)
        feitos.append(f'{destino} {len(lidos)} lido(s)')
    return ', '.join(feitos) or 'alerta desligado'


# ---------- painel ----------

def resumo(con, canal):
    """Linha do painel: estado por destino."""
    return {d: {**estado(con, canal, d), 'bloqueia': bool(bloqueia(con, canal, d))} for d in ('youtube', 'rs')}


def analise(con, canal, limite=40):
    c = cfg(con, canal)
    out = {'cfg': c, 'padrao': PADRAO, 'faixas': FAIXAS, 'destinos': {}}
    for d in ('youtube', 'rs'):
        rows = [dict(r) for r in con.execute(
            f"""SELECT l.entrega_id, l.rede, l.etapa, l.views, l.idade_min, l.lido_em, l.resultado, {','.join('l.' + k for k in EXTRAS)},
                      i.titulo, e.concluido_em, e.url
               FROM vigia_leituras l JOIN entregas e ON e.id=l.entrega_id JOIN itens i ON i.id=e.item_id
               WHERE l.canal=? AND l.destino=? ORDER BY e.concluido_em DESC, l.etapa DESC LIMIT ?""", (canal, d, limite * 3))]
        lim = c['limite_yt' if d == 'youtube' else 'limite_rs']
        vs = [r['views'] for r in rows if r['etapa'] == 'verifica' and r['views'] is not None]
        out['destinos'][d] = {
            'leituras': rows, 'limite': lim, 'n': len(vs), 'mediana': statistics.median(vs) if vs else None,
            'baixos': sum(v < lim for v in vs), 'estado': estado(con, canal, d),
            'mediana_dia': statistics.median(x) if (x := [r['views'] for r in rows if r['etapa'] == 'dia' and r['views'] is not None]) else None,
            'placar': placar(rows, d)}
    return out


def _taxa(r, k):
    return round(100 * r[k] / r['views'], 2) if r.get(k) is not None and r.get('views') else None


def placar(rows, destino):
    """Placar por taxa (% das views), não por views. YouTube usa a leitura de 24 h; RS a conferência (já é de 24 h+).

    Uma linha por post e rede; post sem leitura de 24 h no YouTube ainda não entra."""
    etapa = 'dia' if destino == 'youtube' else 'verifica'
    pecas = [{**r, **{f'tx_{k}': _taxa(r, k) for k, _ in TAXAS}} for r in rows if r['etapa'] == etapa and r['views']]
    med = {}
    for k, nome in TAXAS:
        v = [p[f'tx_{k}'] for p in pecas if p[f'tx_{k}'] is not None]
        med[k] = {'nome': nome, 'mediana': round(statistics.median(v), 2) if v else None, 'n': len(v)}
    chave = 'tx_compart' if any(p['tx_compart'] is not None for p in pecas) else 'tx_likes'
    top = sorted(pecas, key=lambda p: (p[chave] or 0, p['views']), reverse=True)[:5]
    campos = ('entrega_id', 'rede', 'titulo', 'url', 'concluido_em', 'views', *EXTRAS, *(f'tx_{k}' for k, _ in TAXAS))
    return {'n': len(pecas), 'medianas': med, 'ordem': chave[3:], 'top': [{k: p.get(k) for k in campos} for p in top],
            'meta_compart': 1.0}
