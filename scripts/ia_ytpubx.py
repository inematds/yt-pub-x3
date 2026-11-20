#!/usr/bin/env python3
"""Ponte para as funções de texto do yt-pubx. Só lê o yt-pubx; recebe JSON no stdin."""
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
from types import SimpleNamespace

ARQ = os.path.expanduser('~/projetos/yt-pubx/yt-pubx')
sys.path.insert(0, os.path.dirname(ARQ))
sys.dont_write_bytecode = True
carregador = importlib.machinery.SourceFileLoader('ytpubx_x3', ARQ)
spec = importlib.util.spec_from_loader('ytpubx_x3', carregador)
yp = importlib.util.module_from_spec(spec)
carregador.exec_module(yp)

p = json.load(sys.stdin)
cfg = yp.load_config()
nome, c = yp.canal(cfg, {'lives25': 'espanhol', 'lives26': 'aventuras'}.get(p['canal'], p['canal']))
modelo = cfg.get('codex_modelo', '')
pasta = p.get('pasta') or os.getcwd()

# A capa saiu daqui (v0.7.0): é a thumb viral do Codex em lib/ia.py, com o texto desenhado na arte.
if p['tipo'] in ('foto', 'carrossel'):
    txt = yp.codex('Escreva o post de rede social em português do Brasil. Responda SOMENTE JSON com "titulo" (até 90 '
                   'caracteres) e "texto_rs" (até 900 caracteres, sem links, termina com 3 a 5 hashtags).\n\nContexto:\n'
                   + p['contexto'], pasta, modelo)
    print(json.dumps(json.loads(re.search(r'\{.*\}', txt, re.S).group(0)), ensure_ascii=False))
else:
    a = SimpleNamespace(contexto=p['contexto'], contexto_arquivo=None, legenda=None, title=p.get('titulo') or None,
                        description=p.get('descricao') or None, idioma='pt')
    d = yp.gerar_metadados(a, c, p['video'], yp.duracao(p['video']), pasta, modelo)
    print(json.dumps({'titulo': d['titulo'], 'descricao': d['descricao'], 'tags': d.get('tags', [])}, ensure_ascii=False))
