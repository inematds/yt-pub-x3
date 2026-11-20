# yt-pub-x3

[![yt-pub-x3](guia/assets/banner.jpg)](https://inematds.github.io/yt-pub-x3/guia/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## O que é

O yt-pub-x3 é uma fila única de publicação para quem tem vários canais. Sua automação entrega um vídeo, uma foto ou um carrossel, e ele publica no YouTube e agenda nas redes pelo Metricool, nos horários de cada canal. Também corta lives em clipes para o YouTube. Um painel mostra, vídeo por vídeo, o que saiu, o que espera e o que precisa de você. Se um destino falhar, o outro continua. Roda num computador sempre ligado e pede alguém técnico ou uma IA de programação.

## 📖 Guia de uso

Guia completo: **https://inematds.github.io/yt-pub-x3/guia/**

## Peça para a sua IA analisar

```text
Leia o projeto yt-pub-x3 em https://github.com/inematds/yt-pub-x3 (o README explica tudo, inclusive a instalação).
Depois olhe como eu publico hoje e me responda em português simples:
1. Quais canais e redes eu tenho, e onde uma falha hoje derruba mais de um destino?
2. O que o yt-pub-x3 resolveria para mim, e o que ele não resolve?
3. O que preciso ter pronto (contas, logins, Metricool) e qual canal seria o melhor teste?
Não instale, não mude e não publique nada. Mostre o plano, comece em simulação e espere eu dizer sim.
```

**Estado:** v0.1.0, em teste. Passa nos testes com publicadores falsos, mas ainda não publicou em canal real. Os canais nascem desligados e, sem `X3_PUBLICAR=1`, tudo é simulação.

**Para quem é:** quem já opera canais com automações e tem alguém técnico ou uma IA de código. Foi feito para a operação INEMA e precisa de adaptação em outra máquina. Se você agenda posts à mão no Metricool, provavelmente não precisa dele.

---

## Instalação técnica

Precisa de Linux, Python 3 com `PyYAML` e `cryptography`, `ffmpeg`/`ffprobe`, e `gh` para hospedar mídia do Metricool.

```bash
git clone https://github.com/inematds/yt-pub-x3 && cd yt-pub-x3
pip install -r requirements.txt
python3 -m unittest tests/test_x3.py
cp canais/_exemplo.yaml canais/meucanal.yaml   # ajuste os dados do canal
python3 hub.py --once                          # simulação
python3 dashboard/server.py 8230               # http://127.0.0.1:8230
```

`config_dir` guarda o login do YouTube: `.env` com `CLIENT_ID`, `CLIENT_SECRET` e `API_KEY`, `credentials.enc` e `.encryption_key`. Para criar: `GWS_CONFIG_DIR=<config_dir> scripts/yt-auth`. `importar-canais` só serve para quem já tem instâncias `yt-pub-livesN`. Depois de importar, `./yt-pub-x3 login copiar` dá a cada canal uma cópia própria em `~/.config/yt-pub-x3/youtube/<canal>/` (pastas 700, arquivos 600, fora do git) e aponta o `config_dir` para lá; a origem não é alterada.

**Conector do Metricool.** O publicador é um programa externo, indicado por `X3_METRICOOL_VIDEO` (padrão: `~/projetos/metricool-inematds/publicar.sh`). Ele recebe `<video> <legenda.txt> <repo-público>` e as variáveis `MARCA` e `REDES`. Saídas: `0` agendado (imprima `Metricool: <url>`), `2` formato recusado, outra = tentar de novo. Precisa ser idempotente. A mídia fica pública no repo de `X3_METRICOOL_REPO`, para o Metricool poder baixar: use um repo seu e leve isso em conta em conteúdo inédito. Foto e carrossel usam `scripts/metricool-imagens.sh`, que espera a mesma estrutura em `X3_METRICOOL_DIR`.

**Cortes.** `scripts/yt-clip` usa `yt-dlp`, `ffmpeg`, o motor de `scripts/ia.yaml` e `prompt_cortes.txt` no `config_dir`. Usa `fila-vaga` só se ele existir.

**Textos por IA** usam o `yt-pubx` local (`scripts/ia_ytpubx.py`). **Capa** é a thumb viral do Codex image_gen (`thumbviral.py`, caminho em `X3_THUMBVIRAL`): 1280x720, o Codex escolhe o gancho e o desenha dentro da arte, com estilo sorteado; não há texto por cima nem imagem reserva. Só vídeo deitado leva capa (Short não), e só em canal onde o YouTube permite capa personalizada: o primeiro 403 marca o canal como "sem permissão" e o x3 para de gerar ali (o painel tem "Tentar de novo"). Sem IA, informe os textos no `post.json` e coloque `capa.jpg` na pasta. Os avisos usam `avisa-v3.sh` na máquina INEMA; em outra, ficam no log e no painel.

**Serviços** de exemplo em `systemd/`. Eles não ligam a publicação real. Para levar clipes de instâncias antigas a outro canal: `./yt-pub-x3 migrar-clipes lives3 --para lives23 --clipes-pendentes --clipes-erro --imports-erro` mostra a prévia, e `--aplicar` põe na fila.

## O processo, do início ao fim

| # | Passo | Comando | Quem faz |
|---|---|---|---|
| 1 | Gerar os canais a partir dos sistemas atuais, todos desligados | `./yt-pub-x3 importar-canais` | ⚙️ script |
| 2 | Trazer o histórico de lives de quem corta | `./yt-pub-x3 importar-lives lives1` | ⚙️ script |
| 3 | Escolher o canal do piloto e pôr `ativo: true` no YAML | editar `canais/livesN.yaml` | 🧠 sessão com o Nei |
| 4 | Subir hub e painel | `python3 hub.py` · `python3 dashboard/server.py 8230` | ⚙️ serviço |
| 5 | Entregar conteúdo | pasta em `entrada/<canal>/` ou `./yt-pub-x3 enviar <pasta> --canal livesN` | ⚙️ produtor |
| 6 | Validar: formato, repetição e textos | automático; `contexto` usa o Codex | ⚙️ hub · 🤖 Codex |
| 7 | Cortar lives em clipes, nos canais com cortes ligados | automático | ⚙️ hub · 🤖 IA de `scripts/ia.yaml` |
| 8 | Publicar 1 item por horário, separado por destino | automático | ⚙️ hub |
| 9 | Aplicar capa pelo Codex quando permitido | automático | ⚙️ hub · 🤖 Codex |
| 10 | Acompanhar, pausar, pular ou reenviar | `http://127.0.0.1:8230` | 🧠 Nei |
| 11 | Alerta de shadowban: ativar por canal e destino, ver as leituras e destravar | painel do canal → linha **Alerta de shadowban** e aba de mesmo nome | 🧠 Nei · ⚙️ hub |
| 12 | Login próprio do YouTube: copiar uma vez, teste de 6 em 6 h, autenticar de novo quando vencer | `./yt-pub-x3 login copiar` · painel do canal → linha **Login do YouTube** (Testar / Autenticar) | ⚙️ script · ⚙️ hub · 🧠 Nei |

## O que colocar na pasta

```
entrada/lives4/2026-11-18-enxame/
  video.mp4      ou foto.jpg, ou 01.jpg, 02.jpg...
  post.json
  capa.jpg       opcional, vídeo normal
  legenda.srt    opcional, vídeo
  pronto         arquivo vazio, criado por último
```

```json
{
  "tipo": "video",
  "titulo": "Título no YouTube",
  "descricao": "Descrição no YouTube",
  "texto_rs": "Texto das redes",
  "tags": ["ia"],
  "quando": "fila"
}
```

`tipo`: `video`, `foto` ou `carrossel`. `quando`: `fila` (padrão) ou `AAAA-MM-DD HH:MM`; `agora` foi desligado e vira `fila` (sai no próximo horário do canal). Sem os textos, informe `contexto` e o Codex escreve. Foto e carrossel vão só às redes e não gastam horário do YouTube.

## O que acontece quando algo falha

| Situação | Resultado |
|---|---|
| Login do YouTube caiu | YouTube do canal pausa por 1 h; o vídeo fica na fila; redes seguem. O teste de 6 h marca **Vencido** e avisa no v3 |
| Limite ou cota do YouTube | Igual, com pausa de 6 h |
| Rede temporária | Até 3 tentativas, depois erro |
| Queda durante o upload | Vai para **Conferir**; nunca reenvia sozinho |
| Vídeo 16:9 com 3 min ou mais, ou vertical longo demais | Redes ficam como **Ignorado** |
| Arquivo repetido ou pasta inválida | **Recusado**, com o motivo, em `data/recusados/` |
| Codex não fez a capa | Vídeo sai sem capa e o painel marca pendente |
| YouTube recusa capa personalizada no canal (403) | Canal marcado "sem permissão"; o x3 não gasta mais Codex com capa ali |
| Post com poucas views (alerta de shadowban ativo) | Aviso no v3. Com N posts baixos seguidos o destino fica **Travado**; só para de publicar se a pausa automática estiver ligada; destravar é manual no painel |

### Alerta de shadowban

Desativado em todo canal. Ativo, confere só o que foi publicado depois de ativar:
- **YouTube:** lê as views pela YouTube Data API (`videos.list`, 1 unidade por até 50 vídeos) depois de `espera_yt` minutos (padrão 60) e de novo com 24 h, para a análise.
- **RS:** não faz leitura nova; usa a foto diária do Metricool gravada pelo `verdade-das-redes` depois de `espera_rs` horas (padrão 24). Hoje cobre as marcas inema.tds, eventosextremos e FTD.
- Abaixo do limite (padrão 20 views) = aviso. `seguidos` posts baixos (padrão 2) = **Travado**. A pausa automática começa desligada.
- A aba mostra mediana, quantos posts dariam alerta com o limite atual e cada leitura, para calibrar o limite de cada canal.

### Placar por taxa

Na mesma aba, cada destino ganha um placar em % das views, não em views: compartilhamentos, curtidas, comentários e salvos por post, a mediana do canal e os 5 melhores. Meta do compartilhamento: 1%.
- **RS:** os números vêm da mesma foto do Metricool (curtidas, comentários, compartilhamentos, salvos, alcance); a ordem é por compartilhamento.
- **YouTube:** usa a leitura de 24 h (curtidas e comentários). Compartilhamentos não vêm na YouTube Data API, só na Analytics, que não está autorizada; a ordem é por curtidas.
- Só entra o que o alerta leu: o placar existe nos canais com o alerta ativo.

### Login do YouTube

- **Teste:** de 6 em 6 h o hub renova o token de cada canal ativo (sem cota). Só uma recusa do Google (`invalid_grant`, `disabled_client`, `invalid_client`) marca **Vencido**; erro de rede mantém o estado. O aviso no v3 sai só quando muda (venceu ou voltou). `./yt-pub-x3 login testar [canal]` faz o mesmo no terminal.
- **Autenticar:** o botão abre o Google com a conta do canal sugerida. O retorno registrado nos clientes OAuth é `http://localhost:8090/api/auth/callback`; o x3 não escuta nessa porta, então a página de retorno dá erro ou fica vazia: copie o endereço inteiro da barra e cole na caixa do painel (vale 15 min, uma vez). O x3 troca o código, confere se a conta é a do canal (`destino_id`, 1 unidade de cota) e só então grava o novo `credentials.enc` (o anterior fica em `.bak`). Conta errada não grava nada. Se a pausa do YouTube era de login, ela sai.

## Testes

```bash
python3 -m unittest tests/test_x3.py
```

## Segurança

O painel escuta em `127.0.0.1`, não tem senha padrão nem rota que execute comandos, e ações exigem um cabeçalho próprio. O acesso pela rede local é opcional: `dashboard/server.py 8231 --rede` (serviço `yt-pub-x3-painel-rede`) exige usuário `x3`, `X3_PAINEL_SENHA` com 16 caracteres ou mais e `X3_PAINEL_REDES` só com redes privadas. A conexão é HTTP, sem criptografia: use apenas em rede de confiança. Logins, `canais/*.yaml`, `data/` e `entrada/` ficam fora do git.

Conectores: Metricool para vídeo e imagem. Blotato e Upload-Post ainda não têm conector ativo.
