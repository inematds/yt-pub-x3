"""Publicador do YouTube, sem estado: recebe arquivo, textos e pasta de login do canal."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import creds
from .falhas import AMBIGUO, AUTH, COTA, DEFINITIVO, TEMPORARIO, Falha

UPLOAD = 'https://www.googleapis.com/upload/youtube/v3'
API = 'https://www.googleapis.com/youtube/v3'
RAZOES_COTA = ('quotaExceeded', 'uploadLimitExceeded', 'dailyLimitExceeded', 'rateLimitExceeded', 'userRateLimitExceeded')


def classifica_http(codigo, corpo):
    # O YouTube já devolveu uploadLimitExceeded com HTTP 400: o motivo vale mais que o código.
    if any(r in corpo for r in RAZOES_COTA):
        return COTA
    if codigo in (401, 403):
        return AUTH
    if codigo in (408, 429, 500, 502, 503, 504):
        return COTA if codigo == 429 else TEMPORARIO
    return DEFINITIVO


def _http(req, timeout=60, rede=TEMPORARIO, apos_envio=False):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors='replace')
        tipo = classifica_http(e.code, corpo)
        if apos_envio and tipo == TEMPORARIO:
            tipo = AMBIGUO  # os bytes já foram: 5xx não prova que o vídeo não entrou
        raise Falha(f'HTTP {e.code}: {corpo[:300]}', tipo) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise Falha(f'rede: {e}', rede) from None


def metadados(titulo, descricao, tags='', privacy='public', categoria='27', idioma='pt', rotulo_ia=False):
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    status = {'privacyStatus': privacy, 'selfDeclaredMadeForKids': False}
    if rotulo_ia:
        status['containsSyntheticMedia'] = True
    return {'snippet': {'title': titulo[:100], 'description': descricao[:5000], 'tags': tags[:30], 'categoryId': str(categoria),
                        'defaultLanguage': idioma, 'defaultAudioLanguage': idioma},
            'status': status}


def _token(config_dir):
    faltam = [k for k, ok in creds.check(config_dir).items() if not ok]
    if faltam:
        raise Falha(f'login incompleto em {config_dir}: {faltam}', AUTH)
    try:
        return creds.access_token(config_dir)
    except Exception as e:
        raise Falha(f'login: {e}', AUTH) from None


def publicar(arquivo, titulo, descricao, config_dir, tags='', privacy='public', log=print, categoria='27', idioma='pt', rotulo_ia=False):
    if not os.path.isfile(arquivo) or not os.path.getsize(arquivo):
        raise Falha(f'arquivo ausente ou vazio: {arquivo}', DEFINITIVO)
    if not titulo.strip():
        raise Falha('título vazio', DEFINITIVO)
    token = _token(config_dir)
    tamanho = os.path.getsize(arquivo)
    chave = creds.api_key(config_dir)
    url = f'{UPLOAD}/videos?uploadType=resumable&part=snippet,status' + (f'&key={chave}' if chave else '')
    req = urllib.request.Request(url, data=json.dumps(metadados(titulo, descricao, tags, privacy, categoria, idioma, rotulo_ia)).encode(), method='POST',
                                 headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=UTF-8',
                                          'X-Upload-Content-Length': str(tamanho), 'X-Upload-Content-Type': 'video/*'})
    cab, _ = _http(req)
    sessao = cab.get('Location') or cab.get('location')
    if not sessao:
        raise Falha('YouTube não abriu o envio', TEMPORARIO)
    log(f'enviando {tamanho / 1048576:.1f} MB')
    with open(arquivo, 'rb') as f:
        put = urllib.request.Request(sessao, data=f, method='PUT', headers={
            'Authorization': f'Bearer {token}', 'Content-Type': 'video/*', 'Content-Length': str(tamanho)})
        # Queda aqui não prova que o vídeo não entrou: vai para "conferir", nunca reenvio automático.
        _, corpo = _http(put, timeout=3600, rede=AMBIGUO, apos_envio=True)
    vid = json.loads(corpo).get('id')
    if not vid:
        raise Falha(f'resposta sem id: {corpo[:200]!r}', AMBIGUO)
    return vid, f'https://www.youtube.com/watch?v={vid}'


def visualizacoes(ids, config_dir):
    """Números públicos de até 50 vídeos numa chamada (1 unidade de cota). Vídeo que sumiu não volta no dicionário.

    Compartilhamentos não vêm nesta API (só na YouTube Analytics, não autorizada)."""
    ids = [i for i in ids if i][:50]
    if not ids:
        return {}
    req = urllib.request.Request(f"{API}/videos?part=statistics&id={','.join(ids)}",
                                 headers={'Authorization': f'Bearer {_token(config_dir)}'})
    _, corpo = _http(req)
    n = lambda s, k: int(s[k]) if s.get(k) not in (None, '') else None
    return {v['id']: {'views': n(s, 'viewCount') or 0, 'likes': n(s, 'likeCount'), 'comentarios': n(s, 'commentCount')}
            for v in json.loads(corpo).get('items', []) for s in [v.get('statistics', {})]}


def definir_capa(video_id, capa, config_dir):
    token = _token(config_dir)
    with open(capa, 'rb') as f:
        dados = f.read()
    tipo = 'image/png' if capa.lower().endswith('.png') else 'image/jpeg'
    _http(urllib.request.Request(f'{UPLOAD}/thumbnails/set?videoId={video_id}', data=dados, method='POST',
                                 headers={'Authorization': f'Bearer {token}', 'Content-Type': tipo}), timeout=120)


def snippets(ids, config_dir):
    """{video_id: snippet} dos vídeos do canal logado (videos.list, 50 por chamada)."""
    token = _token(config_dir)
    out = {}
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({'part': 'snippet', 'id': ','.join(ids[i:i + 50])})
        _, corpo = _http(urllib.request.Request(f'{API}/videos?{q}', headers={'Authorization': f'Bearer {token}'}))
        out.update({v['id']: v['snippet'] for v in json.loads(corpo).get('items', [])})
    return out


def atualizar_textos(video_id, titulo, descricao, config_dir):
    """Troca título e/ou descrição mantendo categoria, tags e idioma que o vídeo já tem (título vazio = mantém)."""
    s = snippets([video_id], config_dir).get(video_id)
    if not s:
        raise Falha(f'vídeo {video_id} não encontrado no canal logado', DEFINITIVO)
    novo = {k: s[k] for k in ('title', 'description', 'categoryId', 'tags', 'defaultLanguage', 'defaultAudioLanguage') if k in s}
    if titulo:
        novo['title'] = titulo[:100]
    novo['description'] = descricao[:5000]
    token = _token(config_dir)
    _http(urllib.request.Request(f'{API}/videos?part=snippet', data=json.dumps({'id': video_id, 'snippet': novo}).encode(),
                                 method='PUT', headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}))


def listar_lives(origem_id, config_dir, maximo=20):
    chave = creds.api_key(config_dir)
    if not chave:
        raise Falha('API_KEY ausente', AUTH)
    q = urllib.parse.urlencode({'part': 'snippet', 'channelId': origem_id, 'eventType': 'completed', 'type': 'video',
                                'order': 'date', 'maxResults': maximo, 'key': chave})
    _, corpo = _http(urllib.request.Request(f'{API}/search?{q}'))
    return [{'video_id': i['id']['videoId'], 'titulo': i['snippet']['title'], 'data_live': i['snippet']['publishedAt'][:10]}
            for i in json.loads(corpo).get('items', [])]
