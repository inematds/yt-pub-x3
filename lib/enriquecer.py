"""Enriquecimento das lives: live com título genérico ganha título, descrição e capa; live sem descrição ganha só a descrição.

Usa a transcrição que o corte já deixou em <lives_dir>/<video_id>/condensed.txt. Sem transcrição, a live espera o corte.
Nunca refaz: o que deu certo fica na tabela `enriquecidas`; o título que já não é genérico no YouTube também conta como feito.
Capa que não subiu (429, Codex fora) fica `capa_pendente` e é reenviada nas rodadas seguintes, sem refazer o texto
(26/11/2026: a a-Ka7urkoPg tomou 429 em 21/11, foi marcada feita e ficou sem capa).
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
    return {r[0] for r in con.execute("SELECT video_id FROM enriquecidas WHERE canal=? AND status IN ('feito','capa_pendente')", (nome,))}


def capa_pronta(canal, vid):
    """Capa já gerada numa rodada anterior (não gasta o Codex de novo)."""
    jpg = os.path.join(config.acervo_dir(), canal['nome'], f'live-{vid}', 'capa-x3', 'capa.jpg')
    return jpg if os.path.isfile(jpg) else ''


def _limite_capas(e):
    return '429' in str(e) or 'too many thumbnails' in str(e).lower()


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
            _subir_capa(canal, vid, titulo, descricao, capa, definir_capa)
        except Exception as e:  # texto já subiu: a capa falhar não desfaz o resto, e ela é reenviada depois
            log(f'enriquecer {vid}: capa falhou: {e}')
            return f'texto ok, capa falhou: {str(e)[:120]}'
    return 'ok'


def _subir_capa(canal, vid, titulo, descricao, capa, definir_capa):
    jpg = capa_pronta(canal, vid) or capa(canal['nome'], titulo, descricao,
                                          os.path.join(config.acervo_dir(), canal['nome'], f'live-{vid}'))
    definir_capa(vid, jpg, canal['config_dir'])


def reenviar_capas(con, canal, ler, capa, definir_capa, log):
    """Lives com texto feito e capa pendente: usa a capa já gerada (ou gera) e sobe. Para no primeiro 429."""
    pend = [r[0] for r in con.execute("SELECT video_id FROM enriquecidas WHERE canal=? AND status='capa_pendente' ORDER BY em",
                                      (canal['nome'],))]
    if not pend:
        return []
    snip = ler(pend, canal['config_dir'])
    out = []
    for vid in pend:
        s = snip.get(vid)
        if not s:
            _registrar(con, canal['nome'], vid, 'tudo', 'erro', '', 'vídeo não encontrado no canal')
            out.append(f'{vid} capa: vídeo sumiu')
            continue
        try:
            _subir_capa(canal, vid, s.get('title', ''), s.get('description', ''), capa, definir_capa)
            _registrar(con, canal['nome'], vid, 'tudo', 'feito', s.get('title', ''), '')
            out.append(f'{vid} capa reenviada')
        except Exception as e:
            log(f'enriquecer {vid}: capa ainda falhou: {e}')
            con.execute("UPDATE enriquecidas SET erro=?, em=? WHERE canal=? AND video_id=?",
                        (f'capa falhou: {str(e)[:200]}', db.agora(), canal['nome'], vid))
            out.append(f'{vid} capa ainda pendente: {str(e)[:80]}')
            if _limite_capas(e):
                break  # o canal está no limite de troca de capas: tenta na próxima rodada
    return out


def executar(con, canal, simular, log=print, listar=None, ler=None, escrever=None, capa=None, atualizar=None, definir_capa=None):
    """Enriquece até `max_por_vez` lives. Em simulação só lista o que faria."""
    ler = ler or youtube.snippets
    todos = candidatos(con, canal, listar, ler)
    cands = [(l, m) for l, m in todos if transcricao(canal, l['video_id'])]
    esperando = [l['video_id'] for l, m in todos if (l, m) not in cands]
    aviso = f"{len(esperando)} live(s) esperando transcrição: {', '.join(esperando)}" if esperando else ''
    limite = int(canal['enriquecer']['max_por_vez'])
    if simular:
        r = ', '.join(f"{l['video_id']} ({m})" for l, m in cands[:limite]) or 'nada a enriquecer'
        return 'simulado: ' + '; '.join(x for x in (r, aviso) if x)
    feitos = reenviar_capas(con, canal, ler, capa or ia.gerar_capa, definir_capa or youtube.definir_capa, log)
    prompt = prompt_do_canal(canal)
    if not prompt:
        return '; '.join(feitos + ['sem prompt de enriquecimento'])
    for live, modo in cands[:limite]:
        vid = live['video_id']
        try:
            r = _uma(con, canal, live, modo, prompt, escrever or ia.enriquecer_live, capa or ia.gerar_capa,
                     atualizar or youtube.atualizar_textos, definir_capa or youtube.definir_capa, log)
            st = 'capa_pendente' if r.startswith('texto ok, capa falhou') else 'feito'
            _registrar(con, canal['nome'], vid, modo, st, live.get('titulo', ''), '' if r == 'ok' else r)
        except Exception as e:
            r = f'erro: {str(e)[:150]}'
            _registrar(con, canal['nome'], vid, modo, 'erro', live.get('titulo', ''), str(e))
        feitos.append(f'{vid} {r}')
    return '; '.join(feitos + ([aviso] if aviso else [])) or 'nada a enriquecer'
