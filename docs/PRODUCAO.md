# Produção do yt-pub-x3 — situação em 18/11/2026

**Publicação real ligada em 18/11/2026, 03:45, por ordem do Nei** (`X3_PUBLICAR=1` em `~/.config/systemd/user/yt-pub-x3.service.d/publicar.conf`; apagar o arquivo volta à simulação). Primeiros envios ainda não conferidos. Serviços: `yt-pub-x3.service`, `yt-pub-x3-avisos.service` (avisos no Telegram, desde 27/11/2026) e `yt-pub-x3-painel-rede.service`, systemd do usuário. Painel único na porta 8090 desde 27/11/2026 (o painel antigo `yt-master-dashboard` foi desligado sem apagar nada; `yt-pub-x3-painel` na 8230 também): http://127.0.0.1:8090 no servidor, sem senha, e http://192.168.2.99:8090 e http://192.168.1.172:8090 na rede, com usuário `x3` e senha em `~/.config/yt-pub-x3/painel-rede.env`, só para origens 192.168.0.0/16. Canais ativos: lives2, lives3, lives4, lives23 e lives26. Filas depois da limpeza de 18/11: lives23 1426, lives26 552; lives3 e lives4 vazias.

## lives2

- O sistema antigo `yt-pub-lives2` não foi alterado. O painel zera Lives, Clips, Imports e yt-pubx a partir de `migrado_em`, sem apagar nada na origem.
- Os 9 clipes pendentes da live `3RZRD_UmaWA` não têm arquivo: o download dessa live parou em `source.mp4.part`. `lives/` é um link para `/mnt/hd8t/yt-pub-lives`: use `find -L` ao procurar arquivos.
- Finanças, saúde e direito do Radar Viral entram na fila do x3 (`fila_x3` em `radar-viral/radar.json`). Desde 18/11/2026 o Radar não agenda mais o Metricool.

## Fila do lives23

- 1426 itens aguardando, apontando para os arquivos originais. Vieram de clipes e imports sem publicação confirmada nos sistemas antigos.
- O Nei pausou no painel antigo a publicação de clipes e imports de todos os `yt-pub-livesN` (18/11/2026, 03:07). Sem `X3_PUBLICAR=1`, essas filas não saem por nenhum dos dois caminhos.
- lives5 e lives32 saíram do x3; os sistemas antigos continuam como estavam.
- lives6, lives7, lives8, lives10, lives11 e lives12 ficam fora do x3 e zerados no painel a partir do corte.
- lives26 é o canal Aventuras INEMA e fica só com conteúdo do Aventuras: 552 Shorts pendentes na fila do x3. Os episódios longos seguem pelo `aventuras-fila`, direto no canal.

## Horários e origem das publicações

- Os horários de imports, clipes, redes e cortes são definidos no painel do x3, por canal. Short sai nos horários de imports; vídeo sai nos horários de clipes. Os horários de clipes vieram de `pub_horarios` dos sistemas antigos.
- Entregam na fila do x3: Radar (todos os nichos), imersão diária (no dia do vídeo), reels do inemaccbot, fila do r7ex/rtex, fila das cidades, clima (lives10), gitbombando (lives4), explicavideo e vigias, Aventuras (episódios na fila de clipes do lives26, cortes em imports) e espanhol (lives25). Tudo entra na fila e sai no horário do canal (Nei, 19/11/2026): `--quando agora` foi desligado e vira `fila`. Quem precisa do link usa `--esperar` e recebe o link quando o horário chegar.

- gitbombando (grade de 18/11/2026): reels em lives4, lives8, lives3 e lives7; carrosséis em lives9 e lives12. O lives9 usa a marca FTD com `rs.so_imagens: true`: nas redes só saem foto e carrossel, e os vídeos do canal ficam só no YouTube.

## Regra de entrada (Nei, 18/11/2026)

Todo vídeo que entra no x3 vira duas entregas: imports (YouTube) e redes. O produtor não escolhe; `destinos` e `--so-youtube` são ignorados. Canal sem provedor marca redes como ignorado, formato que não serve também, e canal com redes desligadas deixa a entrega aguardando. Os itens migrados não foram duplicados.

## Pendentes ainda fora do x3

Com arquivo e sem destino definido: lives1 8 clipes, lives9 11 imports e lives22 13 imports. A publicação antiga deles está pausada.

## Pronto

- 51 testes passam com publicadores falsos.
- 19 canais importados com `ativo: false`; 334 lives do lives1 importadas.
- Login do YouTube válido em 17 canais. lives5 (`invalid_grant`) e lives32 (`disabled_client`) precisam de nova autorização.
- Desde 20/11/2026 (v0.6.0) o x3 usa cópia própria do login em `~/.config/yt-pub-x3/youtube/<canal>/`; os 17 renovaram o token a partir dela. Teste de 6 em 6 h e botão Autenticar no painel do canal. Autenticar de novo no x3 não muda o login das pastas antigas (yt-pubx e agendadores antigos seguem com o deles).
- Publicador do Metricool, `gh`, `ffprobe`, `yt-dlp` e `codex` disponíveis.

## Bloqueios

1. O `yt-pubx` ainda publica direto e não deposita na fila do x3.
2. Nenhum envio real foi feito. Carrossel e cortes também nunca rodaram de verdade.
3. No lives12, o agendador antigo e o gancho `pos_publicar` do yt-pubx seguem ativos: na virada, desligar imports antigos e gancho para não duplicar.

## Plano proposto ao Nei (aguarda aprovação)

1. ~~Instalar hub e painel em simulação (`systemd/`, sem `X3_PUBLICAR=1`).~~ Feito em 18/11/2026.
2. Ligar só o lives12 e publicar 1 Short inédito real, no YouTube e na marca inema.tds.
3. Conferir YouTube, Metricool e painel.
4. Fazer o `yt-pubx` depositar na fila do lives12 e desligar ali o caminho antigo.
5. Acompanhar um dia; depois lives7, lives31, lives3 e lives4.
6. Migrar os cortes do lives1 por último, após um corte real testado.

## Decisões do Nei em aberto

- Aprovar os passos 2 a 4 e indicar o Short inédito do teste, ou autorizar a escolha de um pronto.
- Horários de lives3, lives4, lives8, lives11 e lives24, que recebem mais vídeos do que têm vagas.
- Reenvio dos 27 vídeos que ficaram fora do Metricool.
- Troca da senha padrão do Master Dashboard atual.
- Explicavideo do guia.
