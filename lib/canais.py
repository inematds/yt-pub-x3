"""Canais = canais/<nome>.yaml. Nenhum segredo aqui: o login fica no config_dir do canal."""
import glob
import os
import re

import yaml

from . import config

BASE = {
    'destino_id': '', 'destino_nome': '', 'url': '', 'origem_id': '', 'config_dir': '', 'lives_dir': '',
    'ativo': False, 'max_tentativas': 3, 'migrado_em': '', 'manter_erros_e_pendentes': False,
}
YOUTUBE = {'ligado': True, 'horarios': [], 'privacy': 'public', 'categoria': '27', 'idioma': 'pt', 'rotulo_ia': False}
RS = {'provedor': '', 'ligado': False, 'marca': '', 'blog_id': '', 'redes': [], 'instagram': '', 'tiktok': '',
      'horarios': None, 'nota': '', 'so_imagens': False}
CLIPES = {'horarios': []}
CORTES = {'ligado': False, 'horarios': [], 'max_por_dia': 1, 'ai_modo': 'claude-api'}
ENRIQUECER = {'ligado': False, 'horarios': [], 'max_por_vez': 3, 'prompt': ''}
# Cota do YouTube vira à meia-noite do Pacífico (04:00/05:00 de Brasília): sobe às 03:30 com a cota que sobrou do dia.
CAPAS_CLIPES = {'ligado': False, 'gerar': '02:30', 'subir': '03:30', 'ultimos': 10}


def _lista(v):
    if isinstance(v, str):
        v = v.split(',')
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def normaliza(nome, bruto):
    bruto = bruto or {}
    c = {**BASE, **{k: v for k, v in bruto.items() if k in BASE and v is not None}, 'nome': nome}
    c['youtube'] = {**YOUTUBE, **(bruto.get('youtube') or {})}
    c['rs'] = {**RS, **(bruto.get('rs') or {})}
    c['cortes'] = {**CORTES, **(bruto.get('cortes') or {})}
    c['clipes'] = {**CLIPES, **(bruto.get('clipes') or {})}
    c['clipes']['horarios'] = _lista(c['clipes']['horarios'])
    c['youtube']['horarios'] = _lista(c['youtube']['horarios'])
    c['cortes']['horarios'] = _lista(c['cortes']['horarios'])
    c['enriquecer'] = {**ENRIQUECER, **(bruto.get('enriquecer') or {})}
    c['enriquecer']['horarios'] = _lista(c['enriquecer']['horarios'])
    c['capas_clipes'] = {**CAPAS_CLIPES, **(bruto.get('capas_clipes') or {})}
    c['rs']['redes'] = _lista(c['rs']['redes'])
    c['rs_herda'] = c['rs']['horarios'] is None  # sem lista própria, o RS acompanha os horários de imports
    c['rs']['horarios'] = c['youtube']['horarios'] if c['rs_herda'] else _lista(c['rs']['horarios'])
    c['migrado_em'] = str(c['migrado_em'] or '')[:16]
    c['config_dir'] = os.path.expanduser(str(c['config_dir'] or ''))
    c['lives_dir'] = os.path.expanduser(str(c['lives_dir'] or ''))
    return c


def validar_horarios(valor):
    if not isinstance(valor, list) or len(valor) > 48:
        raise ValueError('lista de horários inválida')
    if not all(isinstance(h, str) and re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', h) for h in valor):
        raise ValueError('use horários no formato HH:MM')
    return sorted(set(valor))


def definir_horarios(nome, secao, horarios, dir_=None):
    """Troca só os horários de uma seção, sem reescrever o resto do arquivo do canal."""
    if secao not in ('youtube', 'clipes', 'rs', 'cortes'):
        raise ValueError('seção inválida')
    horarios = validar_horarios(horarios)
    p = os.path.join(dir_ or config.canais_dir(), nome + '.yaml')
    with open(p, encoding='utf-8') as f:
        dados = yaml.safe_load(f) or {}
    dados.setdefault(secao, {})['horarios'] = horarios
    tmp = f'{p}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        yaml.safe_dump(dados, f, allow_unicode=True, sort_keys=False)
    os.replace(tmp, p)
    return horarios


def definir_config_dir(nome, valor, dir_=None):
    definir_campo(nome, 'config_dir', valor, dir_)


def definir_campo(nome, campo, valor, dir_=None):
    """Troca só a linha de um campo de topo do arquivo do canal (guarda .bak do anterior)."""
    if campo not in BASE or not re.fullmatch(r'[\w./~-]+', valor):
        raise ValueError('campo ou valor inválido')
    p = os.path.join(dir_ or config.canais_dir(), nome + '.yaml')
    with open(p, encoding='utf-8') as f:
        texto = f.read()
    with open(p + '.bak', 'w', encoding='utf-8') as f:
        f.write(texto)
    linha = f'{campo}: {valor}'
    novo, n = re.subn(rf'^{campo}:.*$', lambda _: linha, texto, count=1, flags=re.M)
    if not n:
        novo = texto.rstrip('\n') + '\n' + linha + '\n'
    if str((yaml.safe_load(novo) or {}).get(campo)) != valor:
        raise ValueError(f'não consegui gravar {campo} em {p}')
    tmp = f'{p}.{os.getpid()}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(novo)
    os.replace(tmp, p)


def carregar(dir_=None):
    out = {}
    ordem = lambda x: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', os.path.basename(x))]
    for p in sorted(glob.glob(os.path.join(dir_ or config.canais_dir(), '*.yaml')), key=ordem):
        nome = os.path.splitext(os.path.basename(p))[0]
        if nome.startswith('_'):
            continue
        with open(p, encoding='utf-8') as f:
            out[nome] = normaliza(nome, yaml.safe_load(f))
    return out


def salvar(c, dir_=None, sobrescrever=False):
    dir_ = dir_ or config.canais_dir()
    os.makedirs(dir_, exist_ok=True)
    p = os.path.join(dir_, c['nome'] + '.yaml')
    if os.path.exists(p) and not sobrescrever:
        return None
    dados = {k: v for k, v in c.items() if k not in ('nome', 'rs_herda')}
    if dados['rs']['horarios'] == dados['youtube']['horarios']:
        dados['rs'] = {k: v for k, v in dados['rs'].items() if k != 'horarios'}  # herda do YouTube
    with open(p, 'w', encoding='utf-8') as f:
        yaml.safe_dump(dados, f, allow_unicode=True, sort_keys=False)
    return p
