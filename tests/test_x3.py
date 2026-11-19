"""Testes só com publicadores falsos e pastas temporárias: nada toca canal real."""
import base64
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'dashboard'))
import hub  # noqa: E402
import server  # noqa: E402
from lib import canais, cortes, db, entrada, importar, metricool, midia, migrar, painel, runner, vigia, youtube  # noqa: E402
from lib.falhas import AMBIGUO, AUTH, COTA, DEFINITIVO, TEMPORARIO, Falha  # noqa: E402

VERT = (1080, 1920, 55.0)
DEIT = (1920, 1080, 179.0)


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='x3-teste-')
        self.addCleanup(shutil.rmtree, self.t, True)
        amb = {'X3_DB': f'{self.t}/d/x3.db', 'X3_ENTRADA': f'{self.t}/entrada', 'X3_CANAIS': f'{self.t}/canais', 'X3_ACERVO': f'{self.t}/acervo',
               'X3_RECUSADOS': f'{self.t}/rec', 'X3_HISTORICO_YTPUBX': f'{self.t}/hist.jsonl', 'X3_LEGADO': f'{self.t}/legado', 'X3_PUBLICAR': '1'}
        p = mock.patch.dict(os.environ, amb)
        p.start()
        self.addCleanup(p.stop)
        self.dims = {}
        p = mock.patch.object(midia, 'probe', lambda f: self.dims.get(os.path.basename(f), VERT))
        p.start()
        self.addCleanup(p.stop)
        self.yt, self.rs = [], []
        self.falha_yt, self.falha_rs = None, None
        p = mock.patch.dict(runner.PUBLICADORES, {'youtube': self.pub_yt, 'rs': self.pub_rs})
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(runner, 'avisar', lambda *a, **k: None)
        p.start()
        self.addCleanup(p.stop)
        self.con = db.connect()
        self.hm = datetime.now().strftime('%H:%M')
        self.canal()
        self.n = 0

    def pub_yt(self, canal, item, log=print):
        if self.falha_yt:
            raise self.falha_yt
        self.yt.append(item['id'])
        return 'vid%d' % item['id'], 'https://youtu.be/%d' % item['id']

    def pub_rs(self, canal, item, log=print):
        if self.falha_rs:
            raise self.falha_rs
        self.rs.append(item['id'])
        return 'FTD', 'https://planner/%d' % item['id']

    def canal(self, nome='lives3', **extra):
        c = {'ativo': True, 'config_dir': f'{self.t}/cfg', 'lives_dir': f'{self.t}/lives', 'origem_id': 'UCx',
             'youtube': {'horarios': [self.hm]}, 'rs': {'provedor': 'metricool', 'ligado': True, 'marca': 'FTD', 'redes': ['tiktok', 'instagram']}}
        c.update(extra)
        canais.salvar(canais.normaliza(nome, c), sobrescrever=True)

    def c(self, nome='lives3'):
        return canais.carregar()[nome]

    def pasta(self, nome=None, tipo='video', arquivos=None, pronto=True, canal='lives3', **post):
        self.n += 1
        nome = nome or f'p{self.n}'
        d = f'{self.t}/entrada/{canal}/{nome}'
        os.makedirs(d)
        for a in arquivos or (['video.mp4'] if tipo == 'video' else ['foto.jpg'] if tipo == 'foto' else ['01.jpg', '02.jpg']):
            with open(f'{d}/{a}', 'w') as f:
                f.write(f'{nome}-{a}')
        p = {'tipo': tipo, **({'titulo': f'T{self.n}', 'descricao': 'D'} if tipo == 'video' else {'titulo': 'T', 'texto_rs': 'Texto'}), **post}
        with open(f'{d}/post.json', 'w') as f:
            json.dump(p, f)
        if pronto:
            open(f'{d}/pronto', 'w').close()
        return d

    def varrer(self):
        return entrada.varrer(self.con, self.c(), log=lambda m: None)

    def rodar(self, destino):
        return runner.executar(self.con, self.job('publicar', {'destino': destino}), canais.carregar(), False, lambda m: None)

    def job(self, tipo, p):
        j = db.add_job(self.con, 'lives3', tipo, db.agora(), json.dumps(p), f'{tipo}:{self.id()}:{os.urandom(4).hex()}')
        db.reivindicar_job(self.con, j)
        return self.con.execute('SELECT * FROM jobs WHERE id=?', (j,)).fetchone()

    def st(self, item=1, destino='youtube'):
        return self.con.execute('SELECT * FROM entregas WHERE item_id=? AND destino=?', (item, destino)).fetchone()


class Falhas(Base):
    def _pausa(self, tipo):
        self.pasta(); self.pasta(); self.varrer()
        self.falha_yt = Falha('caiu', tipo)
        self.assertEqual(self.rodar('youtube'), tipo)
        e = self.st()
        self.assertEqual((e['status'], e['tentativas']), ('aguardando', 0))
        self.assertTrue(db.estado_destino(self.con, 'lives3', 'youtube')['retomar_em'])
        self.rodar('rs')
        self.assertEqual(self.rs, [1])
        self.assertEqual(self.st(1, 'rs')['status'], 'feito')
        self.assertEqual(self.rodar('youtube'), runner.disponivel(self.con, self.c(), 'youtube')[1])
        self.assertEqual(self.st(2)['status'], 'aguardando')
        self.falha_yt = None
        db.limpar_pausa(self.con, 'lives3', 'youtube')
        self.rodar('youtube')
        self.assertEqual(self.yt, [1])

    def test_auth_caida_preserva_fila_e_rs_sai(self):
        self._pausa(AUTH)

    def test_cota_preserva_fila_e_rs_sai(self):
        self._pausa(COTA)

    def test_rs_falha_e_youtube_segue(self):
        self.pasta(); self.varrer()
        self.falha_rs = Falha('x', DEFINITIVO)
        self.rodar('rs'); self.rodar('youtube')
        self.assertEqual(self.st(1, 'rs')['status'], 'erro')
        self.assertEqual(self.st()['status'], 'feito')

    def test_temporaria_para_no_limite(self):
        self.pasta(); self.varrer()
        self.falha_yt = Falha('rede', TEMPORARIO)
        for _ in range(3):
            self.rodar('youtube')
        self.assertEqual((self.st()['status'], self.st()['tentativas']), ('erro', 3))

    def test_ambiguo_vai_para_conferir(self):
        self.pasta(); self.varrer()
        self.falha_yt = Falha('caiu no upload', AMBIGUO)
        self.rodar('youtube')
        self.assertEqual(self.st()['status'], 'conferir')
        self.assertEqual(self.rodar('youtube'), 'fila vazia')

    def test_queda_no_meio_nao_reenvia(self):
        self.pasta(); self.varrer()
        db.reivindicar(self.con, self.st()['id'])
        self.assertEqual(db.recuperar_interrompidos(self.con), 1)
        self.assertEqual(self.st()['status'], 'conferir')
        self.assertEqual(self.rodar('youtube'), 'fila vazia')
        self.assertEqual(self.yt, [])

    def test_classificacao_http(self):
        self.assertEqual(youtube.classifica_http(401, ''), AUTH)
        self.assertEqual(youtube.classifica_http(403, '"reason":"uploadLimitExceeded"'), COTA)
        self.assertEqual(youtube.classifica_http(403, '"reason":"quotaExceeded"'), COTA)
        self.assertEqual(youtube.classifica_http(503, ''), TEMPORARIO)
        self.assertEqual(youtube.classifica_http(400, ''), DEFINITIVO)


class Entrada(Base):
    def test_sem_pronto_ignorada(self):
        d = self.pasta(pronto=False)
        self.assertEqual(self.varrer(), 0)
        self.assertTrue(os.path.isdir(d))

    def test_repetido_recusado(self):
        self.pasta('a'); self.varrer()
        d = self.pasta('b')
        shutil.copy(f"{json.loads(db.item(self.con, 1)['arquivos'])[0]}", f'{d}/video.mp4')
        self.assertEqual(self.varrer(), 0)
        self.assertIn('repetido', self.con.execute('SELECT motivo FROM recusados').fetchone()[0])
        self.assertFalse(os.path.exists(d))

    def test_repetido_no_ytpubx(self):
        d = self.pasta()
        sha = midia.sha256([f'{d}/video.mp4'])
        with open(os.environ['X3_HISTORICO_YTPUBX'], 'w') as f:
            f.write(json.dumps({'canal': 'lives3', 'sha256': sha}) + '\n')
        self.assertEqual(self.varrer(), 0)

    def test_carrossel_nao_gasta_youtube(self):
        self.pasta(tipo='carrossel'); self.pasta(tipo='foto'); self.pasta(); self.varrer()
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM entregas WHERE destino='youtube'").fetchone()[0], 1)
        self.rodar('youtube')
        self.assertEqual(self.yt, [3])
        self.rodar('rs')
        self.assertEqual(self.rs, [1])

    def test_16_9_longo_ignorado_na_rs(self):
        self.dims['h.mp4'] = (1920, 1080, 180.0)
        self.pasta(arquivos=['h.mp4']); self.varrer()
        self.assertEqual(self.st(1, 'rs')['status'], 'ignorado')
        self.assertEqual(self.st()['status'], 'aguardando')
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'a_gerar')

    def test_16_9_com_menos_de_3_min_vai_para_rs(self):
        self.dims['h.mp4'] = (1920, 1080, 179.0)
        self.pasta(arquivos=['h.mp4']); self.varrer()
        self.assertEqual(self.st(1, 'rs')['status'], 'aguardando')

    def test_short_nao_leva_capa(self):
        self.pasta(); self.varrer()
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'nao_leva')

    def test_contexto_escreve_textos(self):
        d = self.pasta()
        json.dump({'tipo': 'video', 'contexto': 'sobre IA'}, open(f'{d}/post.json', 'w'))
        n = entrada.varrer(self.con, self.c(), lambda m: None, lambda *a: {'titulo': 'Novo', 'descricao': 'Desc', 'tags': ['ia']})
        self.assertEqual(n, 1)
        self.assertEqual(db.item(self.con, 1)['titulo'], 'Novo')

    def test_invalidos(self):
        self.pasta(tipo='outro', arquivos=['a.jpg']); self.pasta(tipo='carrossel', arquivos=['1.jpg'])
        self.pasta(quando='amanhã')
        self.assertEqual(self.varrer(), 0)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM recusados').fetchone()[0], 3)


class Hub(Base):
    def test_simulacao_nao_publica(self):
        self.pasta()
        with mock.patch.dict(os.environ, {'X3_PUBLICAR': ''}):
            hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual((self.yt, self.rs), ([], []))
        self.assertEqual(self.st()['status'], 'aguardando')

    def test_canal_inativo_nao_roda(self):
        self.canal(ativo=False); self.pasta()
        self.assertEqual(hub.ciclo(self.con), 0)
        self.assertTrue(os.path.isdir(f'{self.t}/entrada/lives3/p1'))

    def test_horario_publica_um_por_destino(self):
        self.pasta(); self.pasta(); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [1])
        self.assertEqual(self.rs, [1])

    def test_agora_nao_fura_a_fila(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(); self.pasta(quando='agora'); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [])
        self.assertEqual({r[0] for r in self.con.execute('SELECT quando FROM itens')}, {'fila'})

    def test_data_futura_espera(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(quando='2099-01-01 10:00'); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [])

    def test_destino_desligado(self):
        db.definir_ligado(self.con, 'lives3', 'youtube', False)
        self.pasta(); hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [])
        self.assertEqual(self.rs, [1])

    def test_acoes(self):
        self.pasta(); self.varrer()
        e = self.st()['id']
        self.assertTrue(db.acao(self.con, e, 'pausar'))
        self.assertEqual(self.rodar('youtube'), 'fila vazia')
        self.assertTrue(db.acao(self.con, e, 'retomar'))
        self.assertTrue(db.acao(self.con, e, 'pular'))
        self.assertTrue(db.acao(self.con, e, 'reenviar'))
        self.assertFalse(db.acao(self.con, e, 'confirmar'))


class Capa(Base):
    def _pub(self):
        self.dims['h.mp4'] = DEIT
        self.pasta(arquivos=['h.mp4']); self.varrer(); self.rodar('youtube')

    def test_codex_falha_publica_e_fica_pendente(self):
        self._pub()
        with mock.patch.object(runner, 'gerar_capa', side_effect=RuntimeError('sem codex')):
            self.assertEqual(runner.fazer_capa(self.con, self.c(), 1, False, lambda m: None), 'capa pendente')
        self.assertEqual(self.st()['status'], 'feito')
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'pendente')

    def test_capa_aplicada(self):
        self._pub()
        with mock.patch.object(runner, 'gerar_capa', return_value='c.jpg'), mock.patch.object(runner, 'definir_capa') as d:
            runner.fazer_capa(self.con, self.c(), 1, False, lambda m: None)
        d.assert_called_once()
        self.assertEqual(db.item(self.con, 1)['capa_status'], 'aplicada')


class Cortes(Base):
    def setUp(self):
        super().setUp()
        self.canal(cortes={'ligado': True, 'horarios': [self.hm], 'max_por_dia': 1})

    def _cortar(self, canal, vid, log=print):
        d = f"{canal['lives_dir']}/{vid}"
        os.makedirs(f'{d}/clips')
        m = []
        for i in (1, 2):
            f = f'{d}/clips/c{i}.mp4'
            open(f, 'w').write(f'{vid}{i}')
            m.append({'index': i, 'file': f, 'title': f'C{i}', 'description': 'D', 'tags': ['a'], 'duration': 300})
            self.dims[f'c{i}.mp4'] = (1920, 1080, 300)
        json.dump(m, open(f'{d}/clips_manifest.json', 'w'))

    def test_corte_gera_clipes_na_fila(self):
        self.con.execute("INSERT INTO lives(canal,video_id,data_live) VALUES('lives3','L1','2026-01-01')")
        self.assertIn('2 clipes', cortes.cortar_proxima(self.con, self.c(), self._cortar))
        self.assertEqual(self.con.execute("SELECT tipo,origem FROM itens").fetchone()[:2], ('clip', 'live:L1'))
        self.assertEqual(self.st(1, 'rs')['status'], 'ignorado')
        self.assertEqual(self.st()['status'], 'aguardando')

    def test_limite_por_dia(self):
        for v in ('L1', 'L2'):
            self.con.execute("INSERT INTO lives(canal,video_id,data_live) VALUES('lives3',?,'2026-01-01')", (v,))
        cortes.cortar_proxima(self.con, self.c(), self._cortar)
        self.assertEqual(cortes.cortar_proxima(self.con, self.c(), self._cortar), 'limite do dia')

    def test_historico_nao_recorta(self):
        os.makedirs(f'{self.t}/legado/yt-pub-lives3/data')
        v = sqlite3.connect(f'{self.t}/legado/yt-pub-lives3/data/lives.db')
        v.execute('CREATE TABLE lives(video_id,titulo,data_live,status_cortes,qtd_clips)')
        v.execute("INSERT INTO lives VALUES('L1','t','2026-01-01','concluido',3),('import_x','t','','concluido',1)")
        v.commit(); v.close()
        self.assertEqual(cortes.importar_historico(self.con, self.c()), 1)
        cortes.sincronizar(self.con, self.c(), lambda *a: [{'video_id': 'L1', 'titulo': 't', 'data_live': '2026-01-01'}])
        self.assertEqual(cortes.cortar_proxima(self.con, self.c(), self._cortar), 'nenhuma live pendente')

    def test_erro_no_corte(self):
        self.con.execute("INSERT INTO lives(canal,video_id,data_live) VALUES('lives3','L1','2026-01-01')")
        def ruim(*a):
            raise RuntimeError('falhou')
        cortes.cortar_proxima(self.con, self.c(), ruim)
        self.assertEqual(self.con.execute('SELECT status FROM lives').fetchone()[0], 'erro')


class Revisao(Base):
    """Defeitos achados na revisão independente de 18/11/2026."""

    def test_400_com_limite_pausa(self):
        self.assertEqual(youtube.classifica_http(400, '"reason":"uploadLimitExceeded"'), COTA)

    def test_5xx_depois_do_envio_e_ambiguo(self):
        erro = urllib.error.HTTPError('u', 503, 'x', {}, __import__('io').BytesIO(b'{}'))
        with mock.patch('urllib.request.urlopen', side_effect=erro):
            with self.assertRaises(Falha) as c:
                youtube._http(urllib.request.Request('http://x'), apos_envio=True)
        self.assertEqual(c.exception.tipo, AMBIGUO)

    def _legado(self, status):
        os.makedirs(f'{self.t}/legado/yt-pub-lives3/data', exist_ok=True)
        v = sqlite3.connect(f'{self.t}/legado/yt-pub-lives3/data/lives.db')
        v.execute('CREATE TABLE IF NOT EXISTS lives(video_id,titulo,data_live,status_cortes,qtd_clips)')
        v.execute('DELETE FROM lives')
        v.execute("INSERT INTO lives VALUES('L1','t','2026-01-01',?,0)", (status,))
        v.commit(); v.close()

    def test_live_cortada_pelo_antigo_nao_recorta(self):
        self._legado('pendente')
        cortes.importar_historico(self.con, self.c())
        self._legado('concluido')
        chamou = []
        self.assertEqual(cortes.cortar_proxima(self.con, self.c(), lambda *a: chamou.append(1)), 'nenhuma live pendente')
        self.assertEqual(chamou, [])
        self.assertEqual(self.con.execute('SELECT status FROM lives').fetchone()[0], 'cortada')

    def test_reimportar_atualiza_pendente(self):
        self._legado('pendente'); cortes.importar_historico(self.con, self.c())
        self._legado('concluido'); cortes.importar_historico(self.con, self.c())
        self.assertEqual(self.con.execute('SELECT status FROM lives').fetchone()[0], 'cortada')

    def test_repetido_sem_sha_pelo_arquivo_de_origem(self):
        d = self.pasta()
        o = f'{self.t}/origem.mp4'
        shutil.copy(f'{d}/video.mp4', o)
        with open(os.environ['X3_HISTORICO_YTPUBX'], 'w') as f:
            f.write(json.dumps({'canal': 'lives3', 'video_id': 'v', 'origem': o}) + '\n')
        self.assertEqual(self.varrer(), 0)

    def test_video_removido_nao_conta_como_repetido(self):
        d = self.pasta()
        sha = midia.sha256([f'{d}/video.mp4'])
        with open(os.environ['X3_HISTORICO_YTPUBX'], 'w') as f:
            f.write(json.dumps({'canal': 'lives3', 'video_id': 'v', 'sha256': sha}) + '\n' + json.dumps({'removido': 'v'}) + '\n')
        self.assertEqual(self.varrer(), 1)

    def test_hub_parado_nao_solta_horarios(self):
        for _ in range(3):
            self.pasta()
        self.varrer()
        for i in range(3):
            db.add_job(self.con, 'lives3', 'publicar', '2020-01-01 08:00:00', json.dumps({'destino': 'youtube'}), f'velho{i}')
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        hub.ciclo(self.con)
        self.assertEqual(self.yt, [])

    def test_data_vencida_volta_depois_da_pausa(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(quando='2000-01-01 00:00'); self.varrer()
        db.pausar_destino(self.con, 'lives3', 'youtube', 'x', '2099-01-01 00:00:00')
        e = self.st()
        j = self.job('publicar_entrega', {'entrega_id': e['id'], 'destino': 'youtube'})
        db.limpar_pausa(self.con, 'lives3', 'youtube')
        db.pausar_destino(self.con, 'lives3', 'youtube', 'x', '2099-01-01 00:00:00')
        runner.executar(self.con, j, canais.carregar(), False, lambda m: None)
        db.limpar_pausa(self.con, 'lives3', 'youtube')
        hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [1])

    def test_simulacao_nao_prende_item_vencido(self):
        self.canal(youtube={'horarios': []}, rs={'provedor': ''})
        self.pasta(quando='2000-01-01 00:00')
        with mock.patch.dict(os.environ, {'X3_PUBLICAR': ''}):
            hub.ciclo(self.con); hub.ciclo(self.con)
        hub.ciclo(self.con); hub.ciclo(self.con)
        self.assertEqual(self.yt, [1])

    def test_sem_capa_nao_gera_capa(self):
        self.dims['video.mp4'] = (1920, 1080, 3600)
        self.pasta(sem_capa=True)
        self.assertEqual(self.varrer(), 1)
        self.assertEqual(self.con.execute('SELECT capa_status FROM itens').fetchone()[0], 'nao_leva')

    def test_esperar_devolve_o_link(self):
        self.pasta()
        self.assertEqual(self.varrer(), 1)
        item = self.con.execute('SELECT id FROM itens').fetchone()[0]
        cmd = [sys.executable, os.path.join(RAIZ, 'yt-pub-x3'), 'esperar', str(item)]
        self.assertEqual(subprocess.run(cmd, capture_output=True, text=True).returncode, 4)
        self.con.execute("UPDATE entregas SET status='feito', url='https://youtu.be/x' WHERE item_id=? AND destino='youtube'", (item,))
        self.con.commit()
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'Publicado: https://youtu.be/x'))

    def test_rotulo_ia_no_envio(self):
        m = youtube.metadados('t', 'd', categoria='19', idioma='es', rotulo_ia=True)
        self.assertTrue(m['status']['containsSyntheticMedia'])
        self.assertEqual((m['snippet']['categoryId'], m['snippet']['defaultLanguage']), ('19', 'es'))

    def test_video_sempre_vai_para_as_duas_filas(self):
        self.pasta(destinos=['youtube'])
        self.assertEqual(self.varrer(), 1)
        destinos = {r[0] for r in self.con.execute('SELECT destino FROM entregas')}
        self.assertEqual(destinos, {'youtube', 'rs'})

    def test_post_malformado_nao_trava_nem_some(self):
        self.pasta(privacy=['x']); self.pasta()
        self.assertEqual(self.varrer(), 1)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM recusados').fetchone()[0], 1)
        self.assertEqual(len(os.listdir(f'{self.t}/acervo/lives3')), 1)

    def test_canal_desligado_nao_corta(self):
        self.canal(ativo=False, cortes={'ligado': True, 'horarios': [self.hm]})
        j = self.job('cortar', {})
        with mock.patch.object(runner, 'CORTAR', side_effect=AssertionError):
            self.assertEqual(runner.executar(self.con, j, canais.carregar(), False, lambda m: None), 'canal inativo')

    def test_simulacao_nao_gasta_ia(self):
        d = self.pasta()
        json.dump({'tipo': 'video', 'contexto': 'x'}, open(f'{d}/post.json', 'w'))
        chamou = []
        n = entrada.varrer(self.con, self.c(), lambda m: None, lambda *a: chamou.append(1), True)
        self.assertEqual((n, chamou, os.path.isdir(d)), (0, [], True))

    def test_codex_fora_mantem_pasta(self):
        d = self.pasta()
        json.dump({'tipo': 'video', 'contexto': 'x'}, open(f'{d}/post.json', 'w'))
        def ruim(*a):
            raise RuntimeError('sem limite')
        entrada.varrer(self.con, self.c(), lambda m: None, ruim)
        self.assertTrue(os.path.isdir(d))
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM recusados').fetchone()[0], 0)

    def test_link_simbolico_recusado(self):
        d = self.pasta(tipo='foto')
        s = f'{self.t}/segredo'
        open(s, 'w').write('x')
        os.remove(f'{d}/foto.jpg'); os.symlink(s, f'{d}/foto.jpg')
        self.assertEqual(self.varrer(), 0)
        self.assertIn('link', self.con.execute('SELECT motivo FROM recusados').fetchone()[0])


class ConectorMetricool(Base):
    def _script(self, codigo, saida=''):
        p = f'{self.t}/pub.sh'
        with open(p, 'w') as f:
            f.write(f'#!/bin/bash\necho "$MARCA|$REDES|$1|$2|$3" > {self.t}/args\necho "{saida}"\nexit {codigo}\n')
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
        return p

    def _item(self):
        self.pasta(); self.varrer()
        return db.item(self.con, 1)

    def test_ok_envia_marca_e_redes(self):
        with mock.patch.dict(os.environ, {'X3_METRICOOL_VIDEO': self._script(0, 'Metricool: https://app/x')}):
            ref, url = metricool.publicar(self.c(), self._item())
        self.assertEqual((ref, url), ('FTD', 'https://app/x'))
        self.assertTrue(open(f'{self.t}/args').read().startswith('FTD|tiktok,instagram|'))

    def test_trava_de_1h_desligada_nos_publicadores(self):
        it, saida = self._item(), f'{self.t}/livre'
        video, pub2 = f'{self.t}/v.sh', f'{self.t}/p2.py'
        with open(video, 'w') as f:
            f.write(f'#!/bin/bash\necho -n "$INTERVALO_LIVRE" > {saida}\n')
        with open(pub2, 'w') as f:
            f.write(f"import os\nopen('{saida}', 'w').write(os.environ.get('INTERVALO_LIVRE', ''))\n")
        with mock.patch.dict(os.environ, {'X3_METRICOOL_VIDEO': video}):
            metricool.publicar(self.c(), it)
        self.assertEqual(open(saida).read(), '1')
        os.remove(saida)
        with mock.patch.dict(os.environ, {'X3_METRICOOL_PUB2': pub2}):
            metricool.publicar_pub2(self.c(), it)
        self.assertEqual(open(saida).read(), '1')

    def test_saidas(self):
        it = self._item()
        for cod, tipo in ((2, 'formato'), (1, 'temporario')):
            with mock.patch.dict(os.environ, {'X3_METRICOOL_VIDEO': self._script(cod)}):
                with self.assertRaises(Falha) as c:
                    metricool.publicar(self.c(), it)
            self.assertEqual(c.exception.tipo, tipo)

    def test_legenda_estavel(self):
        it = self._item()
        p = metricool.legenda(it)
        a = open(p).read()
        self.assertEqual(metricool.legenda(it), p)
        self.assertEqual(open(p).read(), a)

    def test_legenda_sem_hashtag_de_shorts(self):
        it = dict(self._item())
        it['titulo'] = 'Boleto e Pix #Shorts'
        with open(metricool.legenda(it)) as f:
            self.assertEqual(f.readline().strip(), 'Boleto e Pix')

    def test_scripts_validos(self):
        self.assertEqual(os.system(f"bash -n {RAIZ}/scripts/metricool-imagens.sh"), 0)


class ContaPub2(Base):
    def test_lives11_publica_na_conta_pub2(self):
        p = f'{self.t}/pub2.py'
        with open(p, 'w') as f:
            f.write('import sys\nprint("Metricool: https://app.metricool.com/x", sys.argv[1])\n')
        self.canal(rs={'provedor': 'metricool-pub2', 'ligado': True, 'marca': 'inemafuturos', 'redes': ['tiktok', 'instagram']})
        self.pasta(); self.varrer()
        self.assertEqual(self.st(1, 'rs')['status'], 'aguardando')
        it = dict(db.item(self.con, 1))
        with mock.patch.dict(os.environ, {'X3_METRICOOL_PUB2': p}):
            marca, url = metricool.PUBLICADORES['metricool-pub2'](self.c(), it, lambda m: None)
        self.assertEqual((marca, url), ('inemafuturos', 'https://app.metricool.com/x'))


class SoImagens(Base):
    def test_canal_so_imagens_nao_manda_video_para_as_redes(self):
        self.canal(rs={'provedor': 'metricool', 'ligado': True, 'marca': 'FTD', 'redes': ['tiktok', 'instagram'], 'so_imagens': True})
        self.pasta(); self.pasta(tipo='carrossel'); self.varrer()
        self.assertEqual(self.st(1, 'rs')['status'], 'ignorado')
        self.assertEqual(self.st(1)['status'], 'aguardando')
        self.assertEqual(self.st(2, 'rs')['status'], 'aguardando')


class Painel(Base):
    def setUp(self):
        super().setUp()
        painel._cache.update(t=0, v={})
        self.s = server.criar(0)
        self.base = f'http://127.0.0.1:{self.s.server_address[1]}'
        threading.Thread(target=self.s.serve_forever, daemon=True).start()
        self.addCleanup(self.s.server_close)
        self.addCleanup(self.s.shutdown)

    def req(self, caminho, metodo='GET', cab=None):
        r = urllib.request.Request(self.base + caminho, method=metodo, headers=cab or {})
        try:
            with urllib.request.urlopen(r, timeout=5) as x:
                return x.status, x.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_escuta_so_local(self):
        self.assertEqual(self.s.server_address[0], '127.0.0.1')

    def test_estado_e_acao(self):
        self.pasta(); self.varrer()
        c, b = self.req('/api/estado')
        self.assertEqual(json.loads(b)['canais'][0]['nome'], 'lives3')
        e = self.st()['id']
        self.assertEqual(self.req(f'/api/entrega/{e}/pausar', 'POST')[0], 403)
        self.assertEqual(self.req(f'/api/entrega/{e}/pausar', 'POST', {'X-X3': '1'})[0], 200)
        self.assertEqual(self.st()['status'], 'pausado')
        self.assertEqual(len(json.loads(self.req('/api/canal/lives3')[1])['itens']), 1)

    def test_host_estranho_recusado(self):
        self.assertEqual(self.req('/api/estado', cab={'Host': 'site.mal'})[0], 403)

    def test_rs_herda_imports_ate_ter_lista_propria(self):
        herda = lambda: json.loads(self.req('/api/estado')[1])['canais'][0]['rs_herda']
        self.assertTrue(herda())
        canais.definir_horarios('lives3', 'rs', ['10:00'])
        self.assertFalse(herda())

    def test_grafico_soma_o_que_o_x3_entregou_hoje(self):
        self.pasta(); self.varrer(); self.rodar('youtube'); self.rodar('rs')
        c = json.loads(self.req('/api/estado')[1])
        s = c['canais'][0]['serie']
        self.assertEqual((len(c['dias_serie']), s['yt'][-1], s['rs'][-1], sum(s['yt'][:-1])), (30, 1, 1, 0))

    def test_estado_separa_clipes_de_imports(self):
        self.dims['h.mp4'] = (1920, 1080, 300)
        self.pasta(arquivos=['h.mp4']); self.pasta(); self.varrer()
        y = json.loads(self.req('/api/estado')[1])['canais'][0]['destinos']['youtube']
        self.assertEqual((y['n']['aguardando'], y['clipes']['aguardando']), (2, 1))

    def test_filtro_de_videos_olha_a_fila_inteira(self):
        for i in range(35):
            self.pasta(titulo=f'Comum {i}')
        self.pasta(titulo='Previsão do Clima')
        self.dims['video.mp4'] = VERT
        self.varrer()
        filas = lambda q: json.loads(self.req('/api/filas' + q)[1])['canais']
        self.assertEqual(len(filas('')[0]['itens']), 30)
        c = filas('?q=previsao%20CLIMA')[0]
        self.assertEqual((c['achados'], c['total'], c['itens'][0]['titulo']), (1, 36, 'Previsão do Clima'))
        self.assertEqual(filas('?q=nao-existe'), [])
        self.assertEqual(filas('?tipo=clipe'), [])
        self.assertEqual(filas('?canal=outro'), [])
        sem_filtro = {i['titulo']: i['quando'] for i in painel.filas(self.con, canais.carregar(), limite=99)[0]['itens']}
        self.assertEqual(c['itens'][0]['quando'], sem_filtro['Previsão do Clima'])
        canal = lambda q: json.loads(self.req('/api/canal/lives3' + q)[1])
        self.assertEqual((len(canal('')['itens']), canal('')['total']), (36, 36))
        self.assertEqual([i['titulo'] for i in canal('?q=clima&status=aguardando&tipo=import')['itens']], ['Previsão do Clima'])
        self.assertEqual(canal('?status=feito')['total'], 0)

    def horarios(self, valor, cab=None):
        r = urllib.request.Request(self.base + '/api/horarios/lives3/youtube', method='POST', data=json.dumps({'horarios': valor}).encode(),
                                   headers={'X-X3': '1', **(cab or {})})
        try:
            with urllib.request.urlopen(r, timeout=5) as x:
                return x.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_horarios_salvam_e_validam(self):
        self.assertEqual(self.horarios(['23:58', '08:15', '08:15']), 200)
        c = canais.carregar()['lives3']
        self.assertEqual(c['youtube']['horarios'], ['08:15', '23:58'])
        self.assertTrue(c['ativo'])
        self.assertEqual(self.horarios(['25:00']), 400)
        self.assertEqual(self.horarios('08:00'), 400)
        self.assertEqual(canais.carregar()['lives3']['youtube']['horarios'], ['08:15', '23:58'])

    def test_horario_desligado_sai_e_passado_nao_dispara(self):
        agora = datetime.now()
        if agora.hour == 0 or agora.hour == 23:
            self.skipTest('virada do dia')
        antes, depois = (agora - timedelta(minutes=5)).strftime('%H:%M'), (agora + timedelta(minutes=30)).strftime('%H:%M')
        self.assertEqual(self.horarios([depois]), 200)
        hub.agendar(self.con, canais.carregar())
        chave = f"yt:lives3:{agora:%Y-%m-%d} {depois}"
        self.assertTrue(self.con.execute('SELECT 1 FROM jobs WHERE chave=?', (chave,)).fetchone())
        self.assertEqual(self.horarios([antes]), 200)
        hub.agendar(self.con, canais.carregar())
        self.assertFalse(self.con.execute('SELECT 1 FROM jobs WHERE chave=?', (chave,)).fetchone())
        passado = self.con.execute('SELECT status FROM jobs WHERE chave=?', (f"yt:lives3:{agora:%Y-%m-%d} {antes}",)).fetchone()
        self.assertEqual(passado[0], 'ok')

    def test_horario_de_clipes_separa_da_fila_de_imports(self):
        for n, origem, l, a, d in ((1, 'short', 720, 1280, 30), (2, 'video', 1920, 1080, 600)):
            self.con.execute("INSERT INTO itens(canal,tipo,pasta,arquivos,titulo,descricao,sha256,origem,quando,criado_em,largura,altura,duracao) VALUES('lives3','clip','p','[]','t','d',?,?,'fila','x',?,?,?)", (f's{n}', origem, l, a, d))
            db.add_entrega(self.con, n, 'lives3', 'youtube')
        ids = lambda g: db.item(self.con, db.proxima(self.con, 'lives3', 'youtube', g)['item_id'])['origem']
        self.assertEqual(ids('clipes'), 'video')
        self.assertEqual(ids('outros'), 'short')
        canais.definir_horarios('lives3', 'clipes', ['23:59'])
        self.assertEqual(canais.carregar()['lives3']['clipes']['horarios'], ['23:59'])

    def test_filas_mostra_itens_e_agendados(self):
        self.pasta(); self.varrer()
        futuro = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        with open(f'{self.t}/hist.jsonl', 'w', encoding='utf-8') as f:
            f.write(json.dumps({'canal': 'lives3', 'video_id': 'v', 'titulo': 'Agendado', 'privacy': {'publishAt': futuro}}) + '\n')
        c = json.loads(self.req('/api/filas')[1])['canais'][0]
        self.assertEqual((c['nome'], c['total'], len(c['itens'])), ('lives3', 1, 1))
        self.assertEqual(c['externos'][0]['fonte'], 'Agendado no YouTube')

    def test_pagina(self):
        c, b = self.req('/')
        self.assertEqual(c, 200)
        self.assertIn(b'X3 Master', b)
        self.assertLess(b.index(b"linha('yt-pubx'"), b.index(b"linha('Lives'"))

    def test_migracao_conta_so_o_que_veio_depois(self):
        os.makedirs(f'{self.t}/legado/yt-pub-c/data')
        arq = f'{self.t}/legado/yt-pub-c/data/lives.db'
        c = sqlite3.connect(arq)
        c.execute('CREATE TABLE lives(video_id,titulo,qtd_clips,clips_pendentes,status_cortes,data_corte,data_sync)')
        c.execute('CREATE TABLE publicados(clip_video_id,live_video_id,data_publicacao)')
        c.executemany('INSERT INTO lives VALUES(?,?,?,?,?,?,?)', [
            ('L1', 'live', 9, 9, 'concluido', '', '2026-01-01'),
            ('L2', 'live', 3, 1, 'concluido', '2026-12-02 03:00', '2026-01-01'),
            ('import_velho', 'i', 5, 1, '', '', '2026-01-01'), ('import_novo', 'i', 2, 1, '', '', '2026-12-02')])
        c.executemany('INSERT INTO publicados VALUES(?,?,?)', [
            ('a', 'L1', '2026-01-02 10:00'), ('c', 'L2', '2026-12-02 11:00'), ('b', 'import_velho', '2026-01-02 10:00'), ('d', 'import_novo', '2026-12-02 10:00')])
        c.commit(); c.close()
        antes = os.path.getmtime(arq)
        h = {'d': {}}
        o = painel._legado('c', h, [], '2026-12-01 00:00')
        self.assertEqual((o['clips'][0], o['clips'][1], o['clips'][2]), (3, 1, 1))
        self.assertEqual((o['lives'][0], o['lives'][2]), (1, 1))
        self.assertEqual((o['imports'][0], o['imports'][1], o['imports'][2]), (2, 1, 1))
        self.assertEqual(os.path.getmtime(arq), antes)
        with open(f'{self.t}/hist.jsonl', 'w', encoding='utf-8') as f:
            for vid, d in (('v', '2026-01-02T10:00'), ('n', '2026-12-02T10:00')):
                f.write(json.dumps({'canal': 'c', 'video_id': vid, 'data': d, 'privacy': {'privacyStatus': 'public'}}) + '\n')
        self.assertEqual(painel._historico_ytpubx([], {'c': '2026-12-01 00:00'})['c']['n'], 1)

    def test_zerado_mantem_erros_e_pendentes_com_arquivo(self):
        ld = f'{self.t}/ld/L'
        os.makedirs(ld)
        arq = f'{ld}/a.mp4'
        with open(arq, 'w') as f:
            f.write('x')
        with open(f'{ld}/clips_manifest.json', 'w') as f:
            json.dump([{'index': 1, 'file': arq, 'title': 'T'}, {'index': 2, 'file': f'{ld}/sumiu.mp4', 'title': 'S'}], f)
        os.makedirs(f'{self.t}/legado/yt-pub-c/data')
        c = sqlite3.connect(f'{self.t}/legado/yt-pub-c/data/lives.db')
        c.execute('CREATE TABLE lives(video_id,titulo,clips_pendentes)'); c.execute("INSERT INTO lives VALUES('L','t',2)")
        c.execute('CREATE TABLE publicados(live_video_id,filename,clip_video_id,clip_titulo)'); c.commit(); c.close()
        z = {k: [0, 0, 0, 0, 0] for k in ('imports', 'clips', 'lives')}
        cheio = {'imports': [9, 9, 5, 2, 0], 'clips': [9, 9, 5, 4, 0], 'lives': [9, 0, 5, 3, 0]}
        o = painel._manter_erros_e_pendentes('c', {'lives_dir': f'{self.t}/ld'}, z, cheio)
        self.assertEqual(o['clips'][:4], [5, 1, 0, 4])
        self.assertEqual(o['imports'][:4], [2, 0, 0, 2])
        self.assertEqual(o['lives'][:4], [3, 0, 0, 3])

    def test_ytpubx_separa_agendado_e_ignora_removido(self):
        agora = datetime.now()
        fmt = lambda d: d.strftime('%Y-%m-%dT%H:%M:%S')
        passado, futuro = fmt(agora - timedelta(days=2)), fmt(agora + timedelta(days=1))
        linhas = [
            {'canal': 'c', 'video_id': 'a', 'data': passado, 'privacy': {'privacyStatus': 'public'}},
            {'canal': 'c', 'video_id': 'a', 'data': passado, 'privacy': {'privacyStatus': 'public'}},
            {'canal': 'c', 'video_id': 'b', 'data': passado, 'privacy': {'privacyStatus': 'private', 'publishAt': futuro}},
            {'canal': 'c', 'video_id': 'x', 'data': passado, 'privacy': {'privacyStatus': 'public'}},
            {'canal': 'c', 'removido': 'x', 'em': passado},
        ]
        arq = f'{self.t}/historico.jsonl'
        with open(arq, 'w', encoding='utf-8') as f:
            f.write(''.join(json.dumps(l) + '\n' for l in linhas))
        with mock.patch.dict(os.environ, {'X3_HISTORICO_YTPUBX': arq}):
            h = painel._historico_ytpubx([])['c']
        self.assertEqual((h['n'], h['pub'], h['ag']), (2, 1, 1))


class PainelRede(Base):
    SENHA = 'senha-de-teste-bem-longa'

    def subir(self, redes='127.0.0.0/8'):
        painel._cache.update(t=0, v={})
        s = server.criar_rede(0, self.SENHA, redes, '127.0.0.1')
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.server_close)
        self.addCleanup(s.shutdown)
        return f'http://127.0.0.1:{s.server_address[1]}'

    def auth(self, senha=None, usuario='x3'):
        v = base64.b64encode(f'{usuario}:{senha or self.SENHA}'.encode()).decode()
        return {'Authorization': f'Basic {v}'}

    def req(self, url, metodo='GET', cab=None):
        r = urllib.request.Request(url, method=metodo, headers=cab or {})
        try:
            with urllib.request.urlopen(r, timeout=5) as x:
                return x.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_exige_senha_certa(self):
        b = self.subir()
        self.assertEqual(self.req(b + '/api/estado'), 401)
        self.assertEqual(self.req(b + '/api/estado', cab=self.auth('errada')), 401)
        self.assertEqual(self.req(b + '/api/estado', cab=self.auth(usuario='outro')), 401)
        self.assertEqual(self.req(b + '/api/estado', cab={'Authorization': 'Basic %%%'}), 401)
        self.assertEqual(self.req(b + '/api/estado', cab=self.auth()), 200)

    def test_recusa_origem_fora_da_rede(self):
        self.assertEqual(self.req(self.subir('192.168.250.0/24') + '/api/estado', cab=self.auth()), 403)

    def test_host_estranho_recusado(self):
        self.assertEqual(self.req(self.subir() + '/api/estado', cab={**self.auth(), 'Host': 'site.mal'}), 403)

    def test_acao_ainda_exige_cabecalho(self):
        self.pasta(); self.varrer()
        e = self.st()['id']
        b = self.subir()
        self.assertEqual(self.req(f'{b}/api/entrega/{e}/pausar', 'POST', self.auth()), 403)
        self.assertEqual(self.req(f'{b}/api/entrega/{e}/pausar', 'POST', {**self.auth(), 'X-X3': '1'}), 200)

    def test_nao_sobe_sem_senha_forte_ou_rede_privada(self):
        for senha, redes in ((None, '192.168.1.0/24'), ('curta', '192.168.1.0/24'), (self.SENHA, ''),
                             (self.SENHA, '0.0.0.0/0'), (self.SENHA, '100.64.0.0/10'), (self.SENHA, '8.8.8.0/24')):
            with self.assertRaises(ValueError):
                server.criar_rede(0, senha, redes, '127.0.0.1')


class MigrarClipes(Base):
    def montar(self):
        base = f'{self.t}/legado/yt-pub-o'
        os.makedirs(f'{base}/data')
        c = sqlite3.connect(f'{base}/data/lives.db')
        c.execute('CREATE TABLE lives(video_id,titulo,clips_pendentes)')
        c.execute('CREATE TABLE publicados(live_video_id,filename,clip_video_id,clip_titulo)')
        c.executemany('INSERT INTO lives VALUES(?,?,?)', [('L', 'live', 9), ('import_a', 'x', 1), ('import_t', 'TikTok @a', 0), ('import_z', 'z', 0)])
        c.executemany('INSERT INTO publicados VALUES(?,?,?,?)', [
            ('L', 'L_1', 'ok1', 'A'), ('L', 'L_2', 'erro_upload', 'B'), ('L', 'L_3', 'erro_upload', 'C'), ('L', 'L_3', 'ok3', 'C'), ('L', 'L_4', 'publicando', 'D'),
            ('import_a', 'import_a_1', 'erro_upload', 'E'), ('import_a', '2.mp4', 'ok', 'F'), ('import_t', 'import_t_1', 'erro_upload', 'G'), ('L', 'L_7', 'ok7', 'Título já saiu')])
        c.commit(); c.close()
        self.ld = f'{self.t}/ld'
        for vid, idx in (('L', range(1, 8)), ('import_a', range(1, 4)), ('import_t', [1]), ('import_z', [1])):
            os.makedirs(f'{self.ld}/{vid}/clips')
            m = []
            for i in idx:
                arq = f'{self.ld}/{vid}/clips/{i}.mp4'
                if (vid, i) != ('L', 6):
                    with open(arq, 'w') as f:
                        f.write(f'{vid}{i}')
                titulo = 'Título já saiu' if (vid, i) == ('L', 7) else f'{vid} T{i}'
                m.append({'index': i, 'file': arq, 'filename': f'{i}.mp4', 'title': titulo, 'description': '', 'tags': ['a']})
            with open(f'{self.ld}/{vid}/clips_manifest.json', 'w') as f:
                json.dump(m, f)
        return f'{base}/data/lives.db'

    def ids(self, **k):
        return sorted(x['clip_id'] for x in migrar.selecionar('o', self.ld, **k)[0])

    def test_escolhe_so_o_pedido(self):
        self.montar()
        self.assertEqual(self.ids(clipes_pendentes=True), ['L_5'])
        self.assertEqual(self.ids(clipes_erro=True), ['L_2'])
        self.assertEqual(self.ids(imports_erro=True), ['import_a_1'])
        self.assertEqual(self.ids(imports_pendentes=True), ['import_a_3'])
        self.assertNotIn('import_z_1', self.ids(imports_pendentes=True))
        fora = migrar.selecionar('o', self.ld, clipes_pendentes=True, imports_erro=True)[1]
        self.assertEqual((fora['sem arquivo'], fora['import do TikTok'], fora['envio indefinido']), (1, 1, 1))

    def test_enfileira_sem_duplicar_nem_mexer_na_origem(self):
        arq = self.montar()
        antes = open(arq, 'rb').read()
        destino = canais.normaliza('d', {'ativo': True, 'youtube': {'horarios': ['08:00']}})
        lista = migrar.selecionar('o', self.ld, clipes_pendentes=True, clipes_erro=True, imports_erro=True)[0]
        self.assertEqual(migrar.enfileirar(self.con, destino, lista), (3, 0))
        self.assertEqual(migrar.enfileirar(self.con, destino, lista), (0, 3))
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM entregas WHERE canal='d' AND destino='youtube' AND status='aguardando'").fetchone()[0], 3)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM entregas WHERE destino='rs'").fetchone()[0], 0)
        self.assertEqual(open(arq, 'rb').read(), antes)


class Importar(Base):
    def test_cria_inativo_sem_sobrescrever(self):
        d = f'{self.t}/legado/yt-pub-lives1'
        os.makedirs(f'{d}/data')
        v = sqlite3.connect(f'{d}/data/lives.db')
        v.execute('CREATE TABLE config(chave,valor)')
        v.executemany('INSERT INTO config VALUES(?,?)', [('import_pub_horarios', '07:00,10:00'), ('pub_horarios', '01:00'), ('corte_horarios', '01:35'), ('corte_max_por_dia', '1')])
        v.commit(); v.close()
        self.assertEqual(importar.importar()[0], ['lives1'])
        c = self.c('lives1')
        self.assertFalse(c['ativo'])
        self.assertEqual(c['youtube']['horarios'], ['07:00', '10:00'])
        self.assertTrue(c['cortes']['ligado'])
        self.assertEqual(importar.importar()[1], ['lives1'])


class AlertaShadowban(Base):
    """Leitores falsos: nada lê YouTube nem Metricool de verdade."""

    def setUp(self):
        super().setUp()
        self.views, self.lidas, self.avisos = {}, [], []
        p = mock.patch.dict(vigia.LEITORES, {'youtube': self.ler_yt})
        p.start()
        self.addCleanup(p.stop)

    def ler_yt(self, canal, ids):
        self.lidas.append(list(ids))
        return {i: self.views[i] for i in ids if i in self.views}

    def publicar(self, horas_atras=2):
        self.pasta(); self.varrer()
        self.rodar('youtube')
        e = self.con.execute("SELECT * FROM entregas WHERE destino='youtube' AND status='feito' ORDER BY id DESC").fetchone()
        quando = (datetime.now() - timedelta(hours=horas_atras)).strftime('%Y-%m-%d %H:%M:%S')
        self.con.execute('UPDATE entregas SET concluido_em=? WHERE id=?', (quando, e['id']))
        return e['ref']

    def conferir(self):
        return vigia.conferir(self.con, self.c(), lambda m, log=None: self.avisos.append(m), lambda m: None)

    def ligar(self, horas_atras=10):
        vigia.ligar(self.con, 'lives3', 'youtube', True)
        self.con.execute('UPDATE vigia SET ligado_em=?', ((datetime.now() - timedelta(hours=horas_atras)).strftime('%Y-%m-%d %H:%M:%S'),))

    def test_desligado_nao_le_nem_agenda(self):
        self.views[self.publicar()] = 0
        self.assertEqual(self.conferir(), 'alerta desligado')
        hub.agendar(self.con, canais.carregar())
        self.assertFalse(self.con.execute("SELECT 1 FROM jobs WHERE tipo='vigiar'").fetchone())
        self.assertEqual(self.lidas, [])

    def test_ligado_agenda_uma_conferencia(self):
        self.ligar()
        hub.agendar(self.con, canais.carregar())
        hub.agendar(self.con, canais.carregar())
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM jobs WHERE tipo='vigiar'").fetchone()[0], 1)

    def test_ignora_post_de_antes_de_ligar_e_recente(self):
        velho = self.publicar(horas_atras=20)
        self.ligar(horas_atras=5)
        novo = self.publicar(horas_atras=0.2)  # ainda dentro da espera de 60 min
        self.views.update({velho: 0, novo: 0})
        self.conferir()
        self.assertEqual(self.lidas, [])

    def test_trava_com_dois_seguidos_e_so_pausa_se_pedido(self):
        self.ligar()
        a = self.publicar(3)
        self.views[a] = 5
        self.conferir()
        self.assertFalse(vigia.estado(self.con, 'lives3', 'youtube')['travado'])
        self.assertEqual(len(self.avisos), 1)
        b = self.publicar(2)
        self.views[b] = 3
        self.conferir()
        self.assertTrue(vigia.estado(self.con, 'lives3', 'youtube')['travado'])
        self.assertIn('TRAVADO', self.avisos[-1])
        self.assertTrue(runner.disponivel(self.con, self.c(), 'youtube')[0])  # pausa automática desligada
        vigia.salvar_cfg(self.con, 'lives3', {'auto_pausa': True})
        pode, motivo = runner.disponivel(self.con, self.c(), 'youtube')
        self.assertFalse(pode)
        self.assertIn('shadowban', motivo)
        self.assertTrue(runner.disponivel(self.con, self.c(), 'rs')[0])  # o outro destino segue
        vigia.destravar(self.con, 'lives3', 'youtube')
        self.assertTrue(runner.disponivel(self.con, self.c(), 'youtube')[0])
        self.conferir()  # os baixos de antes não travam de novo
        self.assertFalse(vigia.estado(self.con, 'lives3', 'youtube')['travado'])

    def test_ok_quebra_a_sequencia_e_nao_le_duas_vezes(self):
        self.ligar()
        a, b = self.publicar(3), self.publicar(2)
        self.views.update({a: 5, b: 500})
        self.conferir(); self.conferir()
        self.assertFalse(vigia.estado(self.con, 'lives3', 'youtube')['travado'])
        self.assertEqual(len(self.lidas), 1)
        an = vigia.analise(self.con, 'lives3')['destinos']['youtube']
        self.assertEqual((an['n'], an['baixos'], an['mediana']), (2, 1, 252.5))

    def test_video_sumido_nao_conta_como_baixo(self):
        self.ligar()
        self.publicar(3); self.publicar(2)
        self.conferir()
        self.assertFalse(vigia.estado(self.con, 'lives3', 'youtube')['travado'])
        self.assertEqual(self.avisos, [])

    def test_rs_le_a_foto_do_metricool(self):
        self.canal(rs={'provedor': 'metricool', 'ligado': True, 'marca': 'FTD', 'blog_id': 7908265, 'redes': ['tiktok', 'instagram']})
        self.pasta(titulo='Sua apresentação feita com IA tem efeitos #shorts'); self.varrer()
        runner.executar(self.con, self.job('publicar', {'destino': 'rs'}), canais.carregar(), False, lambda m: None)
        e = self.con.execute("SELECT * FROM entregas WHERE destino='rs' AND status='feito'").fetchone()
        pub = datetime.now() - timedelta(hours=30)
        self.con.execute('UPDATE entregas SET concluido_em=? WHERE id=?', (pub.strftime('%Y-%m-%d %H:%M:%S'), e['id']))
        vigia.ligar(self.con, 'lives3', 'rs', True)
        self.con.execute("UPDATE vigia SET ligado_em='2000-01-01 00:00:00'")
        fotos = f'{self.t}/fotos/2026-11-19'
        os.makedirs(fotos)
        q = (pub + timedelta(minutes=10)).strftime('%Y%m%d%H%M%S')
        with open(f'{fotos}/ftd-tiktok.json', 'w') as f:
            json.dump({'rows': [[q, 'Sua apresentação feita com IA tem efeitos #shorts\n\ntexto', '30', '4']]}, f)
        with open(f'{fotos}/ftd-ig-reels.json', 'w') as f:
            json.dump({'rows': [[q, 'Sua apresentacao feita com IA tem efeitos', '120']]}, f)
        with mock.patch.dict(os.environ, {'X3_VIGIA_FOTOS': f'{self.t}/fotos'}):
            self.conferir()
        r = {x['rede']: (x['views'], x['resultado']) for x in self.con.execute('SELECT * FROM vigia_leituras')}
        self.assertEqual(r, {'tiktok': (4, 'baixo'), 'instagram': (120, 'ok')})

    def test_placar_por_taxa_rs_ordena_por_compartilhamento(self):
        self.canal(rs={'provedor': 'metricool', 'ligado': True, 'marca': 'FTD', 'blog_id': 7908265, 'redes': ['tiktok']})
        vigia.ligar(self.con, 'lives3', 'rs', True)
        self.con.execute("UPDATE vigia SET ligado_em='2000-01-01 00:00:00'")
        fotos = f'{self.t}/fotos/2026-11-19'
        os.makedirs(fotos)
        rows = []
        for n, (views, likes, com, comp) in enumerate([(1000, 50, 2, 1), (200, 10, 1, 6)]):
            self.pasta(titulo=f'Post numero {n} sobre agentes de IA'); self.varrer()
            runner.executar(self.con, self.job('publicar', {'destino': 'rs'}), canais.carregar(), False, lambda m: None)
            e = self.con.execute("SELECT * FROM entregas WHERE destino='rs' AND status='feito' ORDER BY id DESC").fetchone()
            pub = datetime.now() - timedelta(hours=30 - n)
            self.con.execute('UPDATE entregas SET concluido_em=? WHERE id=?', (pub.strftime('%Y-%m-%d %H:%M:%S'), e['id']))
            rows.append([(pub + timedelta(minutes=5)).strftime('%Y%m%d%H%M%S'), f'Post numero {n} sobre agentes de IA', '15', str(views), str(likes), str(com), str(comp), '900'])
        with open(f'{fotos}/ftd-tiktok.json', 'w') as f:
            json.dump({'rows': rows}, f)
        with mock.patch.dict(os.environ, {'X3_VIGIA_FOTOS': f'{self.t}/fotos'}):
            self.conferir()
        p = vigia.analise(self.con, 'lives3')['destinos']['rs']['placar']
        self.assertEqual(p['ordem'], 'compart')
        self.assertEqual([x['views'] for x in p['top']], [200, 1000])  # 3% de compartilhamento vence 0,1%
        self.assertEqual(p['top'][0]['tx_compart'], 3.0)
        self.assertEqual(p['medianas']['likes']['mediana'], 5.0)

    def test_placar_youtube_usa_leitura_de_24h_com_curtidas(self):
        self.ligar(horas_atras=40)
        a = self.publicar(30)
        self.views[a] = {'views': 400, 'likes': 20, 'comentarios': 4}
        self.conferir()
        p = vigia.analise(self.con, 'lives3')['destinos']['youtube']['placar']
        self.assertEqual(p['n'], 1)
        self.assertEqual(p['ordem'], 'likes')  # YouTube não dá compartilhamento nesta API
        self.assertEqual((p['top'][0]['tx_likes'], p['top'][0]['tx_comentarios']), (5.0, 1.0))

    def test_tabela_antiga_ganha_as_colunas_novas(self):
        self.con.execute('DROP TABLE vigia_leituras')
        self.con.execute("CREATE TABLE vigia_leituras (id INTEGER PRIMARY KEY AUTOINCREMENT, entrega_id INTEGER NOT NULL, canal TEXT NOT NULL, destino TEXT NOT NULL, rede TEXT NOT NULL DEFAULT '', etapa TEXT NOT NULL, views INTEGER, idade_min INTEGER NOT NULL, lido_em TEXT NOT NULL, resultado TEXT NOT NULL DEFAULT '', UNIQUE(entrega_id, rede, etapa))")
        vigia.preparar(self.con)
        cols = {r['name'] for r in self.con.execute('PRAGMA table_info(vigia_leituras)')}
        self.assertTrue(set(vigia.EXTRAS) <= cols)

    def test_config_recusa_valor_fora_da_faixa(self):
        with self.assertRaises(ValueError):
            vigia.salvar_cfg(self.con, 'lives3', {'espera_yt': 1})
        with self.assertRaises(ValueError):
            vigia.salvar_cfg(self.con, 'lives3', {'apagar': 1})
        self.assertEqual(vigia.salvar_cfg(self.con, 'lives3', {'limite_yt': '8'})['limite_yt'], 8)

    def test_painel_mostra_estado(self):
        self.ligar()
        e = painel.estado(self.con, canais.carregar())['canais'][0]['vigia']
        self.assertTrue(e['youtube']['ligado'])
        self.assertFalse(e['rs']['ligado'])


if __name__ == '__main__':
    unittest.main()
