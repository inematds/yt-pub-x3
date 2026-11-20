"""Enriquecimento das lives: live com título genérico ganha título, descrição e capa; live sem descrição ganha só a descrição.

Usa a transcrição que o corte já deixou em <lives_dir>/<video_id>/condensed.txt. Sem transcrição, a live espera o corte.
Nunca refaz: o que deu certo fica na tabela `enriquecidas`; o título que já não é genérico no YouTube também conta como feito.
"""
import os

from . import config, db, ia, youtube

GENERICOS = ('', 'INEMA')
LIMITE_TRANSCRICAO = 60000  # caracteres: a live de 3 h passa de 140 mil e estourava o comando no sistema antigo


def generico(titulo):
    return (titulo or '').strip().upper() in GENERICOS


def prompt_do_canal(canal):
    """Prompt do canal: `enriquecer.prompt` no YAML ou o prompt_enrich.txt do agendador antigo (só leitura)."""
    p = canal['enriquecer']['prompt'] or os.path.join(config.legado_dir(), f"yt-pub-{canal['nome']}", 'config', 'prompt_enrich.txt')
    p = os.path.expanduser(p)
    if not os.path.isfile(p):
        return ''
    with open(p, encoding='utf-8') as f:
        return f.read().strip()


def transcricao(canal, video_id):
    p = os.path.join(canal['lives_dir'], video_id, 'condensed.txt')
    if not canal['lives_dir'] or not os.path.isfile(p):
        return ''
    with open(p, encoding='utf-8', errors='ignore') as f:
        return f.read()[:LIMITE_TRANSCRICAO].strip()


def ja_feitas(con, nome):
    return {r[0] for r in con.execute("SELECT video_id FROM enriquecidas WHERE canal=? AND status='feito'", (nome,))}


def candidatos(con, canal, listar=None, ler=None):
    """[(live, modo)] com modo 'tudo' (título genérico) ou 'descricao' (título próprio, descrição vazia)."""
    listar = listar or youtube.listar_lives
    ler = ler or youtube.snippets
    lives = listar(canal['origem_id'], canal['config_dir'], 50)
    feitas = ja_feitas(con, canal['nome'])
    lives = [l for l in lives if l['video_id'] not in feitas]
    snip = ler([l['video_id'] for l in lives], canal['config_dir']) if lives else {}
    out = []
    for l in lives:
        s = snip.get(l['video_id'])
        if not s:
            continue  # não é do canal ou sumiu
        if generico(s.get('title')):
            out.append((l, 'tudo'))
        elif not (s.get('description') or '').strip():
            out.append((l, 'descricao'))
    return out


def _registrar(con, nome, vid, modo, status, titulo='', erro=''):
    con.execute("""INSERT INTO enriquecidas(canal,video_id,modo,status,titulo,erro,em) VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(canal,video_id) DO UPDATE SET modo=excluded.modo, status=excluded.status, titulo=excluded.titulo,
                   erro=excluded.erro, em=excluded.em""", (nome, vid, modo, status, titulo[:200], erro[:300], db.agora()))


def _uma(con, canal, live, modo, prompt, escrever, capa, atualizar, definir_capa, log):
    vid = live['video_id']
    texto = transcricao(canal, vid)
    if not texto:
        return 'sem transcrição'
    pedido = (f"{prompt}\n\n---\n\nVideo ID: {vid}\nData da live: {live.get('data_live', '')}\n\n"
              f"=== TRANSCRICAO DA LIVE ===\n{texto}\n\n---\n\n"
              'Responda SOMENTE um JSON com "title" e "description".')
    d = escrever(canal['nome'], pedido)
    titulo, descricao = (d.get('title') or '').strip(), (d.get('description') or '').strip()
    if modo == 'descricao':
        titulo = ''  # mantém o título e a capa que já estão no YouTube
    elif not titulo:
        raise RuntimeError('IA não devolveu título')
    if not descricao:
        raise RuntimeError('IA não devolveu descrição')
    atualizar(vid, titulo, descricao, canal['config_dir'])
    if modo == 'tudo':
        try:
            pasta = os.path.join(config.acervo_dir(), canal['nome'], f'live-{vid}')
            definir_capa(vid, capa(canal['nome'], titulo, descricao, pasta), canal['config_dir'])
        except Exception as e:  # texto já subiu: a capa falhar não desfaz o resto
            log(f'enriquecer {vid}: capa falhou: {e}')
            return f'texto ok, capa falhou: {str(e)[:120]}'
    return 'ok'


def executar(con, canal, simular, log=print, listar=None, ler=None, escrever=None, capa=None, atualizar=None, definir_capa=None):
    """Enriquece até `max_por_vez` lives. Em simulação só lista o que faria."""
    cands = candidatos(con, canal, listar, ler)
    cands = [(l, m) for l, m in cands if transcricao(canal, l['video_id'])]
    limite = int(canal['enriquecer']['max_por_vez'])
    if simular:
        return 'simulado: ' + (', '.join(f"{l['video_id']} ({m})" for l, m in cands[:limite]) or 'nada a enriquecer')
    prompt = prompt_do_canal(canal)
    if not prompt:
        return 'sem prompt de enriquecimento'
    feitos = []
    for live, modo in cands[:limite]:
        vid = live['video_id']
        try:
            r = _uma(con, canal, live, modo, prompt, escrever or ia.enriquecer_live, capa or ia.gerar_capa,
                     atualizar or youtube.atualizar_textos, definir_capa or youtube.definir_capa, log)
            _registrar(con, canal['nome'], vid, modo, 'feito', live.get('titulo', ''), '' if r == 'ok' else r)
        except Exception as e:
            r = f'erro: {str(e)[:150]}'
            _registrar(con, canal['nome'], vid, modo, 'erro', live.get('titulo', ''), str(e))
        feitos.append(f'{vid} {r}')
    return '; '.join(feitos) or 'nada a enriquecer'
