"""Geração: os agendadores (timers do systemd do usuário) que FAZEM vídeo e para qual canal vai.

Só LÊ: o catálogo abaixo diz o que cada timer gera e para qual canal; os horários, o próximo
disparo, o último disparo e o resultado vêm ao vivo do systemd (`systemctl --user show`).
Trocar horário = mexer no .timer do projeto dono, nunca aqui. Filas de publicação (lives7,
espanhol, cidades, metricool-lives11) não são geração e ficam fora.
Canal novo para um gerador: atualizar o catálogo neste arquivo.
"""
import json
import os
import re
import subprocess
from datetime import datetime

HOME = os.path.expanduser('~')
RADAR = os.path.join(HOME, 'projetos', 'radar-viral', 'radar.json')
IMERSAO = os.path.join(HOME, 'projetos', 'imersao2026', 'diaria', 'config.py')
PLACAR = os.path.join(HOME, '.local', 'share', 'inema', 'rodadas.jsonl')  # wifi/scripts/rodada: início e fim de cada rodada

# timers: [(timer, rótulo)] · canais: [(canal, o que chega lá)] · tipo: agenda | pedido | pauta
CATALOGO = [
    {'id': 'clima24h', 'nome': 'Clima 24h', 'projeto': 'eventosextremospub', 'tipo': 'agenda',
     'timers': [('clima24h-diario', '')], 'canais': [('lives10', 'Short 9:16')], 'nota': 'também no bot v3'},
    {'id': 'previsao', 'nome': 'Previsão do Dia', 'projeto': 'eventosextremospub', 'tipo': 'agenda',
     'timers': [('previsao-dia', '')], 'canais': [('lives10', 'Short 9:16')], 'nota': ''},
    {'id': 'clima-dia', 'nome': 'Clima do DIA (meio-dia)', 'projeto': 'eventosextremospub', 'tipo': 'agenda',
     'timers': [('clima-dia', '')], 'canais': [('lives10', 'Short 9:16')], 'nota': ''},
    {'id': 'clima-alerta', 'nome': 'Alerta da semana', 'projeto': 'eventosextremospub', 'tipo': 'agenda',
     'timers': [('clima-alerta', '')], 'canais': [('lives10', 'Short 9:16')], 'nota': '+ Instagram/TikTok eventosextremos (metritds)'},
    {'id': 'clima-mundo', 'nome': 'Clima no Mundo', 'projeto': 'eventosextremospub', 'tipo': 'agenda',
     'timers': [('clima-mundo', '')], 'canais': [('lives10', 'Short 9:16')], 'nota': ''},
    {'id': 'clima-sul', 'nome': 'Impacto Sul', 'projeto': 'eventosextremospub', 'tipo': 'agenda',
     'timers': [('clima-sul', '')], 'canais': [('lives10', 'Short 9:16')], 'nota': '+ metritds'},
    {'id': 'clima-semana', 'nome': 'Clima da semana + 15 dias', 'projeto': 'eventosextremospub', 'tipo': 'agenda',
     'timers': [('clima-semana', '')], 'canais': [('lives10', 'Short 9:16')], 'nota': ''},
    *[{'id': p, 'nome': n, 'projeto': p, 'tipo': 'agenda', 'radar': p,
       'timers': [(f'{p}-diario', 'diário'), (f'{p}-semanal', 'semanal'), (f'{p}-domingo', 'domingo')],
       'canais': [(c, 'vídeo + Short (Radar Viral)')], 'nota': 'pronto vai à fila do x3 pelo radar-viral (a cada 5 min); redes: Radar (inema.club24)'}
      for p, n, c in (('finviral', 'Finanças viral', 'lives2'), ('futviral', 'Futebol viral', 'lives24'),
                      ('contaviral', 'Contabilidade viral', 'lives24'), ('saudeviral', 'Saúde viral', 'lives2'),
                      ('advviral', 'Direito viral', 'lives2'))],
    {'id': 'gb-dia', 'nome': 'GitHub bombando · Top 10 do dia', 'projeto': 'gitbombando', 'tipo': 'agenda',
     'timers': [('gitbombando-grade-dia', '')], 'canais': [('lives4', 'reel'), ('lives9', 'carrossel @inema.tech')], 'nota': 'no dia 1 também o do mês'},
    {'id': 'gb-top5', 'nome': 'GitHub bombando · Top 5 da semana', 'projeto': 'gitbombando', 'tipo': 'agenda',
     'timers': [('gitbombando-grade-top5', '')], 'canais': [('lives8', 'reel'), ('lives12', 'carrossel @inema.tds')], 'nota': ''},
    {'id': 'gb-area', 'nome': 'GitHub bombando · Top 5 da área', 'projeto': 'gitbombando', 'tipo': 'agenda',
     'timers': [('gitbombando-grade-area', '')], 'canais': [('lives3', 'reel'), ('lives9', 'carrossel @inema.tech')], 'nota': ''},
    {'id': 'gb-agentes', 'nome': 'GitHub bombando · Top 5 de agentes', 'projeto': 'gitbombando', 'tipo': 'agenda',
     'timers': [('gitbombando-grade-agentes', '')], 'canais': [('lives7', 'reel'), ('lives12', 'carrossel @inema.tds')], 'nota': ''},
    {'id': 'gb-semana', 'nome': 'GitHub bombando · Top 10 da semana', 'projeto': 'gitbombando', 'tipo': 'agenda',
     'timers': [('gitbombando-grade-semana', '')], 'canais': [('lives4', 'reel')], 'nota': 'sem carrossel'},
    {'id': 'imersao', 'nome': 'Imersão diária (1 vídeo por canal)', 'projeto': 'imersao2026', 'tipo': 'agenda', 'imersao': True,
     'timers': [('imersao-diaria-pauta', 'pauta')], 'canais': [], 'nota': 'pauta 00:30 → trabalhadores geram → publica 16:00 no canal; até 10/12'},
    {'id': 'izabela', 'nome': 'Vigia Izabela (reel refeito com avatar)', 'projeto': 'wifi/vigia-izabela', 'tipo': 'agenda',
     'timers': [('vigia-izabela', '')], 'canais': [('lives3', 'reel 9:16')], 'nota': '+ metritds FTD, INEMA.FTD e portal; só quando há reel novo'},
    {'id': 'saraev', 'nome': 'Vigia Saraev (explicavideo)', 'projeto': 'wifi/vigia-saraev', 'tipo': 'agenda',
     'timers': [('vigia-saraev', '')], 'canais': [('lives7', '16:9 + 9:16, até 2 por dia')], 'nota': 'só quando há vídeo novo'},
    {'id': 'r7ex', 'nome': 'r7ex (reel 7 etapas)', 'projeto': 'r7ex', 'tipo': 'pedido',
     'timers': [('r7ex-producao', '')], 'canais': [('lives7', 'reel (fila lives7)')], 'nota': 'gera quando há pedido (/r7ex no inemaccbot); confere a cada 5 min'},
    {'id': 'rtex', 'nome': 'rtex (reel de N peças)', 'projeto': 'rtex', 'tipo': 'pedido',
     'timers': [('rtex-producao', '')], 'canais': [('do pedido', 'reel')], 'nota': 'gera quando há pedido (/rtex); canal vem do pedido'},
    {'id': 'rtexjp', 'nome': 'rtexjp (ilustrado, sem HeyGen)', 'projeto': 'rtexjp', 'tipo': 'pedido',
     'timers': [('rtexjp-producao', '')], 'canais': [('do pedido', 'reel')], 'nota': 'gera quando há pedido (/rtexjp); canal vem do pedido'},
    {'id': 'oportunidades', 'nome': 'Radar de oportunidades (pautas)', 'projeto': 'wifi/radar-oportunidades', 'tipo': 'pauta',
     'timers': [('radar-oportunidades', '')], 'canais': [('o Nei escolhe', 'ficha no v3; "faz N" produz')], 'nota': 'não gera sozinho: só a pauta'},
]

DIAS = {'Mon': 'seg', 'Tue': 'ter', 'Wed': 'qua', 'Thu': 'qui', 'Fri': 'sex', 'Sat': 'sáb', 'Sun': 'dom'}


def _show(timers):
    """Propriedades de vários timers numa só chamada ao systemd."""
    nomes = [t + '.timer' for t in timers]
    try:
        out = subprocess.run(['systemctl', '--user', 'show', *nomes, '-p', 'Id', '-p', 'TimersCalendar',
                              '-p', 'TimersMonotonic', '-p', 'NextElapseUSecRealtime', '-p', 'LastTriggerUSec',
                              '-p', 'ActiveState', '-p', 'UnitFileState', '-p', 'Unit', '-p', 'LoadState'],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return {}
    props = {}
    for bloco in out.strip().split('\n\n'):
        d = {}
        for linha in bloco.splitlines():
            k, _, v = linha.partition('=')
            d.setdefault(k, []).append(v)
        if 'Id' in d:
            props[d['Id'][0].removesuffix('.timer')] = d
    servicos = sorted({d['Unit'][0] for d in props.values() if d.get('Unit') and d['Unit'][0]})
    res = {}
    if servicos:
        try:
            out = subprocess.run(['systemctl', '--user', 'show', *servicos, '-p', 'Id', '-p', 'Result', '-p', 'ActiveState',
                                  '-p', 'ExecMainExitTimestamp'], capture_output=True, text=True, timeout=10).stdout
            for bloco in out.strip().split('\n\n'):
                d = dict(l.partition('=')[::2] for l in bloco.splitlines())
                res[d.get('Id', '')] = d
        except Exception:
            pass
    for d in props.values():
        d['_servico'] = res.get((d.get('Unit') or [''])[0], {})
    return props


def _dias(expr):
    if not expr or expr == '*-*-*':
        return 'todo dia'
    m = re.fullmatch(r'(\w{3})(?:\.\.(\w{3}))?', expr)
    if not m:
        return expr
    a, b = DIAS.get(m.group(1), m.group(1)), DIAS.get(m.group(2) or '', m.group(2))
    return f'{a}–{b}' if b else a


def calendario(oncal):
    """'Mon..Fri *-*-* 09,15:00:00' → ('seg–sex', ['09:00', '15:00'])."""
    partes = oncal.split()
    hora = partes[-1] if partes else ''
    dia = partes[0] if len(partes) == 3 else ''
    h, _, resto = hora.partition(':')
    mi = resto.split(':')[0] if resto else '00'
    if h == '*' and '/' in mi:
        return _dias(dia), [f'a cada {mi.split("/")[1]} min']
    if h == '*':
        return _dias(dia), [f'toda hora :{mi}']
    horas = [f'{int(x):02d}:{int(m):02d}' for x in h.split(',') for m in mi.split(',') if x.isdigit() and m.isdigit()]
    return _dias(dia), horas or [hora]


def _quando(v):
    """'Fri 2026-11-20 08:00:00 -03' → '2026-11-20 08:00'."""
    m = re.search(r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})', v or '')
    return f'{m.group(1)} {m.group(2)}' if m else ''


def _agenda(d):
    linhas = []
    for c in d.get('TimersCalendar', []):
        m = re.search(r'OnCalendar=([^;]+);', c)
        if m:
            dias, horas = calendario(m.group(1).strip())
            linhas.append({'dias': dias, 'horas': horas})
    if not linhas:
        for c in d.get('TimersMonotonic', []):
            m = re.search(r'OnUnit(?:Active|Inactive)U?Sec=([^;]+);', c)
            if m:
                linhas.append({'dias': 'sempre', 'horas': [f'a cada {m.group(1).strip()}']})
    return linhas


def _radar():
    try:
        return {n['projeto']: n for n in json.load(open(RADAR, encoding='utf-8')).get('nichos', [])}
    except Exception:
        return {}


def _imersao():
    try:
        txt = open(IMERSAO, encoding='utf-8').read()
        bloco = txt[txt.index('CANAIS = {'):]
        bloco = bloco[:bloco.index('\n}')]
        hora = (re.search(r'^HORA = "([^"]+)"', txt, re.M) or [None, '16:00'])[1]
        return re.findall(r'^\s*"(lives\d+)"\s*:', bloco, re.M), hora
    except Exception:
        return [], '16:00'


def _placar(caminho=PLACAR):
    """Último 'fim' de cada unidade no placar da máquina (resultado, motivo, quando)."""
    ult = {}
    try:
        with open(caminho, encoding='utf-8', errors='replace') as f:
            linhas = f.readlines()[-5000:]
    except OSError:
        return ult
    for l in linhas:
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if d.get('fase') in ('fim', 'retificacao') and d.get('unidade'):  # retificação = conferência posterior (ex.: saiu depois no x3)
            ult[d['unidade']] = {'quando': (d.get('ts') or '')[:16].replace('T', ' '), 'resultado': d.get('resultado') or '',
                                 'motivo': (d.get('motivo') or '')[:400], 'url': d.get('url') or ''}
    return ult


def ler(canais_cfg=None, props=None, placar=None):
    todos = [t for g in CATALOGO for t, _ in g['timers']]
    props = _show(todos) if props is None else props
    radar, (im_canais, im_hora) = _radar(), _imersao()
    placar = _placar() if placar is None else placar
    falhas = []
    titulos = {n: (c.get('destino_nome') or '') for n, c in (canais_cfg or {}).items()}
    geradores, por_canal, grade = [], {}, []
    for g in CATALOGO:
        canais = list(g['canais'])
        if g.get('radar') and g['radar'] in radar:
            canais = [(radar[g['radar']].get('fila_x3') or radar[g['radar']].get('canal') or canais[0][0], canais[0][1])]
        if g.get('imersao'):
            canais = [(c, f'vídeo da imersão às {im_hora}') for c in im_canais]
        execucoes, ligados = [], 0
        for t, rotulo in g['timers']:
            d = props.get(t)
            if not d or (d.get('LoadState') or [''])[0] != 'loaded':
                execucoes.append({'timer': t, 'rotulo': rotulo, 'existe': False, 'agenda': [], 'ligado': False})
                continue
            sv = d['_servico']
            ligado = (d.get('ActiveState') or [''])[0] == 'active'
            ligados += ligado
            execucoes.append({'timer': t, 'rotulo': rotulo, 'existe': True, 'ligado': ligado,
                              'habilitado': (d.get('UnitFileState') or [''])[0], 'agenda': _agenda(d),
                              'proximo': _quando((d.get('NextElapseUSecRealtime') or [''])[0]),
                              'ultimo': _quando((d.get('LastTriggerUSec') or [''])[0]),
                              'resultado': sv.get('Result', ''), 'rodando': sv.get('ActiveState') in ('activating', 'active'),
                              'placar': placar.get(t)})
            e = execucoes[-1]
            pl = e['placar'] or {}
            if not e['rodando'] and (pl.get('resultado') == 'falhou' or (e['resultado'] and e['resultado'] != 'success')):
                e['falhou'] = True
                falhas.append({'gerador': g['nome'], 'id': g['id'], 'timer': t, 'rotulo': rotulo,
                               'quando': pl.get('quando') if pl.get('resultado') == 'falhou' else e['ultimo'],
                               'motivo': pl.get('motivo') if pl.get('resultado') == 'falhou' else f"systemd: {e['resultado']} (ver journalctl --user -u {t})",
                               'canais': [c for c, _ in canais]})
        item = {'id': g['id'], 'nome': g['nome'], 'projeto': g['projeto'], 'tipo': g['tipo'], 'nota': g['nota'],
                'canais': [{'canal': c, 'titulo': titulos.get(c, ''), 'o_que': o} for c, o in canais],
                'execucoes': execucoes, 'ligado': ligados > 0}
        geradores.append(item)
        for c, o in canais:
            if not re.fullmatch(r'lives\d+', c):
                continue
            pc = por_canal.setdefault(c, {'canal': c, 'titulo': titulos.get(c, ''), 'itens': []})
            for e in execucoes:
                for a in e['agenda']:
                    pc['itens'].append({'gerador': g['nome'], 'o_que': o, 'dias': a['dias'], 'horas': a['horas'], 'ligado': e['ligado']})
        if g['tipo'] == 'agenda':
            for e in execucoes:
                for a in e['agenda']:
                    for h in a['horas']:
                        if re.fullmatch(r'\d{2}:\d{2}', h):
                            grade.append({'hora': h, 'dias': a['dias'], 'gerador': g['nome'], 'rotulo': e['rotulo'],
                                          'canais': [c for c, _ in canais], 'ligado': e['ligado']})
    for pc in por_canal.values():
        pc['itens'].sort(key=lambda i: i['horas'][0] if i['horas'] else '')
    return {'agora': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'geradores': geradores,
            'falhas': sorted(falhas, key=lambda f: f['quando'] or '', reverse=True),
            'grade': sorted(grade, key=lambda x: (x['hora'], x['gerador'])),
            'por_canal': [por_canal[k] for k in sorted(por_canal, key=lambda c: int(c[5:]))]}
