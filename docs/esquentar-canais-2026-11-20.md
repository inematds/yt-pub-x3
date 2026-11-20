# Por que alguns canais entregam 0 a 10 views e como esquentar — 20/11/2026

## Resumo em 5 linhas

1. **Medido:** em 60 dias (até 16/11) a rede publicou 2.410 vídeos em 16 canais. 96% das views são do lives10 (clima). Nos outros 14 canais (sem contar lives10 e Aventuras), 41% dos vídeos têm menos de 10 views.
2. **São dois problemas diferentes.** lives22, lives23, lives24 e lives11 estão em zero de verdade (mediana 0 a 1 e vídeo antigo não ganha view nenhuma). Os outros (lives2, 3, 4, 6, 7, 8, 9, 12, 26) estão vivos, mas fracos (mediana 10 a 30).
3. **O que o dado aponta nos fracos:** volume alto, a mesma propaganda em 13 a 14 canais no mesmo minuto, peça dupla no mesmo canal e 9 canais falando de IA para o mesmo público. Horário e duração não mudam nada.
4. **Pesquisa:** o YouTube nega "sandbox" e castigo por frequência; cada vídeo é julgado sozinho. Mas a regra de spam vale para "redes coordenadas de canais", e canal encerrado derruba os outros do mesmo dono. O risco maior não é a view baixa, é o lives10 e o lives1 caírem junto.
5. **Plano:** parar de publicar nos canais zerados, tirar a propaganda repetida, cortar para 1 a 2 Shorts por dia por canal, juntar os canais de IA em poucos (um público cada) e esquentar 2 canais por 4 semanas com série fixa e título de busca, medindo views de 24 h e de 7 dias contra a base do próprio canal.

## As 5 ações de maior impacto

1. **Parar o YouTube nos canais zerados** (lives23 com a fila de 1.418 clipes, lives22, lives24) e fazer o passo zero no Studio, incluindo o lives11. Custo zero; tira da rede o que mais parece produção em massa.
2. **Tirar a propaganda repetida:** nada de campanha igual em vários canais nem no mesmo minuto, e nenhuma propaganda no lives10. Custo zero.
3. **Cortar o volume e a peça dupla:** 1 a 2 Shorts por dia e 2 vídeos longos por semana por canal; uma peça = um canal = um título.
4. **Juntar os canais de IA** em poucos, um público por canal. É decisão do Nei; a proposta está no plano.
5. **Esquentar 2 canais por 4 semanas** (lives4 e lives2) com série fixa, título de busca e pelo menos um vídeo por semana com gente de verdade, e trocar a régua do alerta do x3 para leituras de 24 h e 7 dias.

## De onde vêm os números

- **Fonte principal:** `~/projetos/verdade-das-redes/dados/youtube/2026-11-16.jsonl` (coleta de 16/11, janela de 60 dias, 16 canais, views, likes e comentários por vídeo), comparada com as coletas de 07/11 e 09/11.
- **Motor de cada vídeo:** `~/.local/share/yt-pubx/historico.jsonl` (1.490 envios de 07/10 a 19/11), casado pelo id do vídeo.
- **Origem dos Shorts antigos:** tabela `publicados` dos `yt-pub-livesN/data/lives.db` (imports e cortes de live).
- **x3:** `data/x3.db` aberto só para leitura (fila, entregas, alerta de shadowban) e os YAMLs de `canais/`.
- Nenhuma API foi chamada e nada foi alterado. Medianas excluem vídeos com menos de 3 dias no ar.
- **Limites:** não há impressões, retenção nem origem do tráfego (isso só existe no YouTube Studio). O lives25 (espanhol) não está na coleta. A fase do x3 (desde 18/11) ainda não dá para medir: o alerta tem só 23 leituras, todas com 60 a 75 minutos de vida, nenhuma de 24 h.

## Diagnóstico por canal (medido)

| Canal | Nome | Inscritos | Vídeos em 60 d (por dia) | Mediana de views | % com menos de 10 | Com zero | Antigos que ainda ganham view¹ | Título igual repetido no canal² | Horários no x3 hoje³ |
|---|---|---|---|---|---|---|---|---|---|
| lives10 | Eventos Extremos | 8.100 | 189 (3,1) | **4.942** | 1% | 1 | 92% | 12% | 12 + 3 |
| lives31 | Inema Club 31 | 27 | 44 (0,7) | 60 | 5% | 0 | 0% | 0% | 2 + 4 |
| lives1 | INEMA TDS | 14.500 | 401 (6,7) | 40 | 4% | 0 | 43% | 5% | 5 + 4 |
| lives2 | INEMA TIA | 881 | 150 (2,5) | 29 | 26% | 0 | 26% | 7% | 6 + 3 |
| lives7 | INEMA LOOPY | 161 | 171 (2,9) | 28 | 25% | 3 | 76% | 4% | 5 + 2 |
| lives9 | Inema Vip | 148 | 78 (1,3) | 19 | 26% | 0 | 9% | 8% | 2 + 4 |
| lives8 | Inema Vibe | 82 | 144 (2,4) | 15 | 35% | 15 | 18% | 3% | 3 + 2 |
| lives26 | Aventuras INEMA | 58 | 260 (7,0) | 14 | 39% | 3 | 36% | 0% | 6 + 6 |
| lives4 | INEMA Tec | 156 | 218 (3,6) | 13 | 41% | 5 | 28% | 10% | 4 + 3 |
| lives12 | Inema Pro | 19 | 63 (1,7) | 12 | 46% | 2 | 44% | 0% | 3 + 3 |
| lives3 | INEMA FTD | 214 | 266 (4,4) | 12 | 43% | 8 | 20% | 11% | 4 + 5 |
| lives6 | INEMA Robot | 93 | 111 (1,9) | 10 | 50% | 13 | 12% | 5% | 5 + 3 |
| lives11 | INEMA Futuros | 773 | 107 (1,8) | **1** | 92% | 30 | 17% | 7% | 3 + 4 |
| lives22 | Inema Club22 | 13 | 69 (1,1) | **0** | 100% | 47 | 2% | 0% | 2 + 0 |
| lives23 | Inema Club23 | 1 | 78 (1,3) | **0** | 100% | 66 | 0% | 3% | 2 + 2 |
| lives24 | Inema Club24 | 1 | 61 (1,0) | **0** | 100% | 39 | 3% | 20% | 2 + 4 |
| lives25 | Inema Espanhol | sem dado | sem dado | — | — | — | — | — | 8 + 8 |

¹ Dos vídeos que já tinham 7 dias ou mais em 09/11, quantos ganharam pelo menos 1 view entre 09/11 e 16/11. Mostra se existe busca ou recomendação depois da primeira semana.
² Vídeos com o mesmo título exato de outro vídeo do mesmo canal (em geral a versão 16:9 e a 9:16 da mesma peça, ou a peça reenviada).
³ Horários de Short + horários de vídeo (clipes) no YAML. Todos os 17 YAMLs estão com `ativo: true`.

### O que os dados mostram

1. **Quase toda a audiência está em um canal.** 3,94 milhões de views na janela; 3,79 milhões (96,2%) do lives10. Os 14 canais de IA e afins somaram 120 mil views em 1.961 vídeos; os 5% melhores vídeos concentram 57% disso. Só 55 passaram de 500 views. No total, os 16 canais já têm 17.326 vídeos no ar.
2. **Os canais zerados não são só "canal pequeno".** lives31 tem 27 inscritos e mediana 60. lives12 tem 19 inscritos e mediana 12. lives22, 23 e 24 publicaram 208 vídeos em 60 dias e somaram 48 views. Na semana de 09 a 16/11, 58 vídeos novos nesses três canais somaram 9 views.
3. **O que os zerados publicam não é reenvio.** lives22, 23, 24 e 31 nasceram entre julho e agosto de 2026 e publicam 100% pela mesma esteira: lotes de Shorts prontos ("import"), 2 por dia. Os títulos quase não se repetem em outros canais (lives22: 8 de 150; lives23: 1 de 117; lives24: 0 de 85). A mesma esteira dá mediana 60 no lives31 e zero nos outros três. O que muda é o assunto: lives31 fala com um público claro (pais: "seu filho e a IA"); lives22 fala de profissão e emprego, lives23 de "seu colega usa IA melhor" e curso, lives24 de empresa e, desde novembro, futebol, contábil e IA misturados.
4. **lives11 tem 773 inscritos e mediana 1.** Publica em qualquer hora (19 dos 107 vídeos entre 23 h e 5 h) e manda a mesma peça duas vezes com 1 hora de diferença (13 e 14/11).
5. **Vídeo antigo morre.** Fora o lives10 (92%) e o lives7 (76%), a maioria dos vídeos com mais de 7 dias não ganha mais nenhuma view. Ou seja: não há busca trazendo gente. Os títulos atuais não são o que as pessoas procuram.
6. **Inscrito não é audiência.** lives1 tem 14.500 inscritos e mediana 40 (0,3%). As lives dele fazem 209 de mediana; os Shorts, 21.
7. **Volume no dia e views andam em sentidos opostos** (correlação, não prova de causa: dia cheio também tem peça diferente):

| Canal | Dias com 1 a 2 vídeos | Dias com 5 a 7 | Dias com 8 ou mais |
|---|---|---|---|
| lives2 | mediana 84 | 13 | 29 |
| lives3 | 28 | 26 | 7 |
| lives6 | 24 | 1 | 5 |
| lives7 | 49 | 25 | 14 |
| lives8 | 31 | 8 | 13 |
| lives4 | 21 | 11 | 12 |

   O lives3 chegou a 23 vídeos num dia, o lives4 a 20 e o lives1 a 32. Em 15/11 a rede subiu 117 vídeos num dia só.
8. **A queda de lives3, lives4 e lives8 começa na semana de 19/10**, junto com duas coisas ao mesmo tempo: mais volume (lives3 de 29 para 43 vídeos na semana, lives4 de 35 para 49, lives8 de 21 para 38) e a entrada do r7ex. Não dá para separar as duas causas. O lives6 cai na semana de 26/10 (mediana 26 para 2).
9. **Motor: a diferença grande é de assunto, não de formato.** Medianas no YouTube: finviral 59 e advviral 41 (lives2, notícia do dia), reel7etapas 19, gitbombando 19, explicavideo 13, saudeviral 13, contaviral 8, r7exp 7, r7ex 4, promos "nível de IA" 4, futviral 0 (lives24). Esses números misturam canais. Dentro do mesmo canal, r7ex × explicavideo: lives1 16 × 34, lives3 5 × 13, lives6 1 × 7, lives8 2 × 4, lives11 1 × 2, lives4 12 × 13, lives7 25 × 11. O r7ex rende menos em 5 de 7 canais, mas nenhum dos dois passa de 34. E o r7ex acerta com celebridade (Musk no lives6: 1.150 e 1.184).
10. **Shorts dos sistemas antigos (imports e cortes de live) rendem mais que as peças novas enviadas pelo yt-pubx.** Só Shorts, desde 08/10: lives1 33 × 19, lives3 14 × 10, lives6 12 × 6, lives7 35 × 25, lives8 25 × 8, Aventuras 305 × 8. É o contrário no lives4 (8 × 19). No lives2 todos os Shorts do período são do Radar e a mediana é 136.
11. **Propaganda igual em vários canais.** Em 15/11, às 12:00, 13:00 e 16:00, 13 a 14 canais publicaram no mesmo minuto a mesma campanha: 41 vídeos, mediana 3 views. "Qual é o seu nível de IA? Tire o seu certificado grátis" saiu em 10 canais com o mesmo título. No x3, de 18 a 20/11, 49 dos 133 envios ao YouTube (37%) foram a "imersão diária", espalhada por 15 canais. No lives10 a propaganda fez 3 views em 74 minutos; o clima, no mesmo tempo, fez 65, 128 e 348. Isso caiu dentro do teste nº 1 do lives10 ("só séries fixas"), que vai até 22/11.
12. **Título repetido.** No mesmo canal: 20% no lives24, 12% no lives10, 11% no lives3, 10% no lives4 (15 pares com menos de 24 h no lives3, 11 no lives4). Entre canais, na janela: 94 vídeos (lives1 com lives4: 13 pares; lives3 com lives7: 10; lives2 com lives24: 5). No histórico inteiro dos sistemas antigos: 426 títulos em mais de um canal (17% dos títulos do lives2, 12% do lives3). O x3 só barra arquivo idêntico (sha256); cada canal recebe um arquivo diferente, então nada disso é barrado.
13. **Fila do x3.** O lives23 (1 inscrito, 100% zero) tem 1.418 clipes antigos na fila, vindos de 9 canais de assuntos diferentes. O lives26 tem 543.
14. **O que não explica:** horário (mediana 13 a 25 em todas as faixas) e duração do Short (16 a 21 em todas as faixas).
15. **O "Travado" do x3 não é prova de shadowban.** Seis canais travaram na primeira noite porque o limite é 20 views com 60 minutos. Nesse critério até o lives1 travaria. Serve como aviso, não como diagnóstico.

### O que é hipótese

- **lives22, 23, 24 e 11 podem estar sem distribuição** (limitados, ou nunca classificados pelo YouTube). A favor: a mesma esteira funciona no lives31. Contra: o lives31 tem um público claro e os outros não. O dado local não separa "limitado" de "sem público": precisa das impressões do Studio. Por isso este relatório não chama de shadowban.
- **Nove canais de IA dividem o mesmo público** e nenhum junta massa. Já estava como hipótese no estudo de 07/11; os números de 16/11 continuam batendo.
- **Volume alto com pouca reação faz o YouTube parar de testar o canal.** O dado mostra a correlação; a causa não está provada.
- **Avatar e voz sintética rendem menos que gente de verdade.** Bate com os itens 6 e 10 e com reportagens de 2026, mas não foi testado de forma isolada.

## Pesquisa (2025–2026)

### Fonte oficial do YouTube (páginas da Ajuda, lidas hoje)

- **"Conteúdo inautêntico" é regra de monetização, não de alcance.** Em 15/07/2025 o YouTube renomeou a regra de "conteúdo repetitivo". Ela barra da monetização o canal em que os vídeos "parecem feitos com um modelo" e são trocáveis entre si, inclusive "conteúdo de IA feito com modelos genéricos, dando impressão de produção em massa, sem a visão própria do criador". Usar IA é permitido. Vale para o canal inteiro. [Políticas de monetização](https://support.google.com/youtube/answer/1311392?hl=en)
- **A regra de spam vale para todo canal, monetizado ou não, e cita "redes coordenadas de canais".** Rotular IA "não é passe livre". Punição: aviso, strike ou encerramento. [Política de spam](https://support.google.com/youtube/answer/2801973?hl=en)
- **Canal encerrado derruba os outros.** Quem tem um canal encerrado fica proibido de "usar, possuir ou criar" qualquer outro; vale para todos os canais existentes. [Encerramento de canal](https://support.google.com/youtube/answer/2802168?hl=en)
- **Rótulo de IA.** Obrigatório quando o conteúdo é realista e faz uma pessoa real parecer dizer ou fazer o que não fez, altera imagem de lugar ou evento real, ou cria cena realista que não aconteceu. Um dos exemplos é "evento de clima chegando a uma cidade real que não aconteceu". Não precisa rotular: clonar a própria voz para narrar, e roteiro, título e capa feitos com IA. "Rotular, sozinho, não limita a audiência nem a monetização." O YouTube também pode rotular por conta própria. [Divulgação de IA](https://support.google.com/youtube/answer/14328491?hl=en)
- **E o avatar do Nei?** A página libera a voz clonada do próprio criador, mas não cita avatar em vídeo. O avatar realista mostra o Nei "fazendo" algo que ele não gravou; não é um dos exemplos, é zona cinzenta. Como rotular não tira alcance, a escolha segura é rotular os vídeos com avatar.
- **Pausa não castiga.** O YouTube estudou milhares de canais e "não achou relação entre o tamanho da pausa e a mudança nas views"; só leva um tempo para o público "esquentar de novo". Subir como não listado e abrir depois também não atrapalha. [FAQ de desempenho](https://support.google.com/youtube/answer/141805?hl=en)
- **Frequência:** a orientação oficial é agenda "consistente e sustentável", sem número mágico. [Dicas de agenda](https://support.google.com/youtube/answer/13616979?hl=en)

### Fala oficial, lida por reportagem (não li o original)

- **View conta do primeiro quadro.** Nos Shorts desde 31/03/2025 e em todos os formatos desde 24/08/2026 (aviso do TeamYouTube). Então 0 views quer dizer que o vídeo não começou a tocar para ninguém. [ppc.land](https://ppc.land/youtube-counts-views-from-the-first-frame-across-all-formats-on-august-24/)
- **Como o vídeo novo é testado (Todd Beaupré, Creator Insider, 01/09/2026).** Não é testado só nos inscritos: na primeira hora ele já chega a quem nunca viu o canal. A decisão não se fecha nos primeiros momentos; alguns vídeos juntam a maior parte da audiência um mês depois. Em canal novo, sem histórico, o sistema casa o assunto do vídeo com o gosto das pessoas e, se não aparece público interessado, as impressões param (resumo da reportagem, não frase literal). Inscrito clica em 10% ou menos dos vídeos. Sobre ter vários canais: "alinhe canais com públicos"; se as mesmas pessoas veriam os dois, é um canal só. [ppc.land](https://ppc.land/subscribers-skip-90-of-uploads-in-their-feed-youtube-director-says/)
- **Inscrito parado não derruba o canal; tráfego de fora ajuda a dar a partida.** O YouTube diz que avalia cada vídeo, não a "reputação" do canal, e que link externo "pode dar início" à recomendação. [Social Media Today](https://www.socialmediatoday.com/news/youtube-answers-common-questions-on-video-discovery-and-distribution/588415/)
- **Esclarecimento de julho/2025** (Rene Ritchie, do YouTube): a mudança mira spam e produção em massa, não o uso de IA nem vídeo de reação. [Search Engine Journal](https://www.searchenginejournal.com/youtube-clarifies-monetization-update-targeting-spam-not-reaction-channels/550123/)
- **Prioridade de 2026:** a carta do CEO Neal Mohan promete reduzir a propagação de conteúdo de IA de baixa qualidade. Só vi a manchete e o resumo da busca, não o texto. [Bloomberg](https://www.bloomberg.com/news/articles/2026-01-21/youtube-ceo-says-battling-ai-slop-a-top-priority-in-2026)

### Reportagem e estudo de terceiros (não é palavra do YouTube)

- **Derrubada em grupo.** Um artigo de pesquisadores do Google descreve um sistema que encerrou 50 mil grupos (130 mil canais) em seis meses; cerca de 1% das decisões foi revertida. Na leitura de Jim Louderback (não é lista do artigo), o que faz uma operação legítima parecer fábrica é: modelos compartilhados, agenda de envio sincronizada e infraestrutura comum. [Fstoppers](https://fstoppers.com/artificial-intelligence/how-google-machine-terminated-130000-ai-slop-youtube-channels-six-months-903645)
- **Rede de um dono só.** Em setembro/2026 o YouTube encerrou 20 canais de uma mesma operação citando "spam e práticas enganosas". [The Next Web](https://thenextweb.com/news/youtube-ghost-creators-paid-actors-ai-detection-loophole)
- **Canal sem rosto.** Reportagens dizem que os ajustes de 2026 favorecem vídeo com gente de verdade na tela e que a punição de monetização é por canal, olhando o padrão dos últimos envios. [The Next Web](https://thenextweb.com/news/youtube-ai-slop-crackdown-faceless-creators-collateral-damage?type=AI)
- **Frequência (vidIQ, 10,2 milhões de canais com mais de 1.000 inscritos):** quem publica mais cresce mais na mediana, mas o próprio estudo diz que não prova causa e que mais volume "pode sair pela culatra se baixar a qualidade". [vidIQ](https://vidiq.com/research/youtube-upload-frequency-study/)
- **Metricool 2026:** o feed de Shorts traz 61% das views; canal pequeno é quem mais ganha; cada Short é visto por uns 16 segundos; com 35 ou mais Shorts por mês o vídeo longo do canal volta ao nível de quem não posta Short; hashtag quase não ajuda. [Metricool](https://metricool.com/youtube-trends/)

### Opinião de criador, sem confirmação oficial

- "Sandbox", "canal frio" e "shadowban" de canal: nenhuma fonte oficial confirma. O que o YouTube descreve é mais simples: sem público interessado, as impressões param.
- "Apagar e subir de novo": circula em fóruns, não tem base oficial e cria mais conteúdo repetido. Não recomendo.
- "Postar demais é punido": o YouTube não diz isso. O que existe é o dado da própria INEMA (item 7) e a regra de spam para produção em massa.

### Como a pesquisa conversa com os dados

A rede tem hoje o desenho que as reportagens descrevem como alvo: 17 canais do mesmo dono, mesmos motores e modelos, a mesma campanha em 13 a 14 canais no mesmo minuto (e em 15 canais ao longo do dia) e a maioria com reação quase nula. Isso é **risco**, não fato consumado: nenhum aviso ou strike aparece nos arquivos locais. Mas o que está em jogo são o lives10 (96% das views) e o lives1 (14.500 inscritos e as lives).

## Plano de ação

### Passo zero (30 minutos, só o Nei, no YouTube Studio, sem API)

Para lives22, lives23, lives24 e lives11, e um canal "vivo" para comparar (lives31 ou lives4):
1. Conteúdo: há restrição ou aviso em algum vídeo?
2. Estatísticas → Alcance dos últimos 10 Shorts: impressões e "mostrado no feed".
3. Configurações → Canal → Status e recursos; e-mails de aviso da conta.
4. Abrir 2 vídeos em janela anônima e buscar o título exato.

Leitura: **impressões zero** = o canal não está sendo distribuído; não adianta esquentar, é parar e consolidar. **Impressões com quase ninguém assistindo** = problema de conteúdo ou de público; entra no protocolo abaixo.

### Por canal, em ordem de impacto e custo

| Canal | O que fazer | Por quê (dado) |
|---|---|---|
| **lives23** | Parar o YouTube agora. Não soltar a fila de 1.418 clipes. | 1 inscrito, 100% zero, fila com assuntos de 9 canais. |
| **lives22, lives24** | Parar o YouTube até o passo zero. Se as impressões forem zero, encerrar o uso. | Com o lives23: 208 vídeos, 48 views somadas. |
| **lives11** | Parar a publicação de madrugada e a peça dupla. Passo zero. Se seguir em 1 de mediana após 2 semanas com 1 vídeo por dia, levar o tema "futuro" para o lives1. | 773 inscritos, mediana 1, 92% abaixo de 10. |
| **lives10** | Não mexer na série. Tirar a propaganda de lá. Avaliar o rótulo de IA nas peças com imagem gerada realista de evento de clima. Manter 3 a 5 por dia. | 96% das views; propaganda fez 3 views; a regra de rótulo cita clima. |
| **lives2** | Só finanças e direito do dia, 2 por dia. Tirar saúde, r7ex e propaganda. Baixar de 6 para 2 horários. | Shorts do Radar com mediana 136 desde 08/10 e picos de 1.200 a 1.500; saúde 13, r7ex 5. |
| **lives3** | Cortar para 1 Short por dia e 2 vídeos por semana. Uma série só. Sem peça dupla. | Maior volume fora o lives1 (266), mediana 12, 15 pares de título igual em menos de 24 h. |
| **lives4** | Canal do teste de esquentar (abaixo): tutorial com título de busca. | Testes 2 e 3 do `verdade-das-redes/testes.md` estão propostos desde 07/11 e não começaram. |
| **lives26** | Shorts de corte: no máximo 3 por dia. Episódio longo: 2 por semana. | Short de corte 305 de mediana, episódio 8 a 10; dias com 1 a 4 Shorts rendem 385, com 5 ou mais rendem 8; inscritos de 31 para 58 em 9 dias. |
| **lives6, 7, 8, 9, 12** | 1 vídeo por dia, sem propaganda, até decidir a consolidação. | Mediana 10 a 28; o mesmo público de IA. |
| **lives1** | Lives e cortes de lives com título de busca. No máximo 2 peças de IA por dia. Se houver propaganda da imersão, só aqui, 1 por dia. | Lives 209 de mediana; Shorts de IA 21. |
| **lives31** | Manter o tema "IA para pais e filhos", 1 por dia. | Melhor canal pequeno: 27 inscritos, mediana 60. |
| **lives25** | Não mexer por enquanto (segue a regra da fila do espanhol, 8 por dia). Incluir o canal na coleta semanal e decidir com 2 semanas de dado. | Sem coleta. |

### O que parar (custo zero)

1. Publicar em canal zerado.
2. A mesma campanha em vários canais, e qualquer envio no mesmo minuto em vários canais.
3. O mesmo título em dois canais, e 16:9 mais 9:16 da mesma peça no mesmo canal com menos de 24 h e o mesmo título.
4. Propaganda no lives10.
5. Peça avulsa fora da série do canal (no YouTube; Instagram e TikTok seguem como estão).

### Consolidar (decisão do Nei)

A orientação do próprio YouTube é "um canal por público". Proposta: clima (lives10), aventuras (lives26), finanças e direito (lives2), IA para quem faz — tutoriais e lives (lives1, com o lives4 em teste), IA para leigo 40+ e pais (lives8 ou lives31). Os demais ficam em 1 por dia ou param.

### Protocolo de esquentar (4 semanas, 2 canais: lives4 e lives2)

- **Antes:** registrar em `verdade-das-redes/testes.md` com data de início e a base do canal (mediana dos 60 dias: lives4 = 13, lives2 = 29).
- **Ritmo:** 1 Short por dia, sempre no mesmo horário, e 2 vídeos longos por semana (6 a 12 minutos). Nada mais no canal: sem propaganda, sem repetido, sem peça de outro canal.
- **Tipo de vídeo:** uma série reconhecível. lives4: tutorial que resolve ("Como instalar X", "X ou Y: qual usar", "X não funciona? Como arrumar"), com o nome da ferramenta no título. lives2: "o que dizem os finfluencers" sobre o fato do dia, com número no título.
- **Gente de verdade:** pelo menos 1 dos 2 longos da semana com tela e voz reais do Nei (pode ser corte de live com título de busca).
- **Capa:** um estilo só por canal.
- **Empurrão legítimo:** mandar 1 vídeo por dia ao grupo do Telegram do tema e citar na live. É público real da INEMA, e o YouTube diz que tráfego externo ajuda a dar a partida.
- **Sem atalho:** nada de comprar views, robô, troca de inscrição ou apagar e subir de novo.

### Quando desistir ou juntar

- **Canal zerado:** impressões zero no Studio = parar já, sem teste.
- **Canal em teste:** ao fim de 4 semanas (cerca de 28 Shorts e 8 longos), se a mediana de 7 dias for menor que 2 vezes a base e nenhum vídeo passar de 500 views, parar o canal e levar o melhor conteúdo para o canal principal do mesmo público.
- **Canal em 1 por dia:** se em 4 semanas a mediana de 7 dias não subir, juntar.

## Mudanças sugeridas no x3 (só sugestões, nada foi alterado)

1. **Teto por canal e por tipo:** `max_shorts_dia` e `max_longos_semana`, valendo acima dos horários.
2. **Trava de repetido por título:** comparar o título normalizado com os últimos 30 dias do canal e dos outros canais. Hoje só o sha256 é conferido.
3. **Classe "promo":** origem `imersao-diaria` e parecidas com lista de canais permitidos e limite por dia; nunca no lives10. O yt-pubx 2.6.1 já recusava avulso no lives10; no x3 a propaganda passou em 19 e 20/11.
4. **Sem envio sincronizado:** não publicar em 3 ou mais canais no mesmo minuto; espalhar com 20 a 40 minutos de diferença.
5. **Par 16:9 e 9:16:** títulos diferentes e pelo menos 24 h entre um e outro no mesmo canal.
6. **Alerta de shadowban:** decidir pela leitura de 24 h (já existe no código, etapa `dia`) e criar a de 7 dias; limite relativo à base do canal (por exemplo, 5 seguidos abaixo de 30% da mediana de 24 h do próprio canal) no lugar de 20 fixo; a leitura de 60 minutos vira só informação.
7. **`rotulo_ia`:** hoje é `false` por padrão e só o lives25 tem `true`; o yt-pubx também não envia o rótulo. Definir por canal e por origem (avatar, clima com imagem gerada realista, refazvideo).
8. **Fila do lives23:** deixar parada; se houver consolidação, cada clipe volta ao canal de origem dentro do teto, ou sai.
9. **Menos horários:** lives2 de 6 para 2, lives3 e lives4 de 4 para 1 ou 2, lives26 de 6 para 3.
10. **Coleta e relatório semanal:** incluir o lives25, "antigos que ainda ganham view" e mediana por motor dentro de cada canal.

## Como medir se funcionou

| Métrica | Onde | Meta em 4 semanas |
|---|---|---|
| Mediana de views com 7 dias, por canal | coleta semanal do `verdade-das-redes` | 3 vezes a base do canal (lives4: de 13 para 40; lives2: de 29 para 90) |
| % de vídeos com menos de 10 views aos 7 dias | idem | metade da base (lives4: de 41% para 20%) |
| Antigos que ainda ganham view | comparação de duas coletas | 30% ou mais (sinal de busca) |
| Views de 24 h por vídeo | alerta do x3, etapa `dia` | acima da mediana de 24 h do próprio canal |
| Inscritos por semana | coleta semanal | subindo toda semana |
| Impressões e "assistiu × deslizou" dos Shorts | Studio, à mão, 1 vez por semana | comparar com a semana anterior do mesmo canal |
| Avisos, strikes e restrições | Studio e e-mail | zero |

Prazo: primeira leitura com 2 semanas (só para ver direção), decisão com 4. Não há promessa de milagre: IA em português é um assunto disputado, e sair de 13 para 40 a 100 de mediana no lives4 já seria resultado.

## Decisões do Nei (20/11/2026)

- **Rótulo de IA: não.** Vídeo com o rosto ou o avatar do Nei não leva rótulo, nem no lives10. O rótulo fica só para canais dark (sem rosto e sem avatar). Palavras dele: "como eu dou orientação do que falar, não vou considerar IA; seria a mesma coisa que fazer um vídeo diferente de ser ao vivo".
- **Propaganda da imersão: parada por enquanto.** Desliguei a geração (`imersao-diaria-pauta.timer`, agendador, montador, trabalhadores t2–t4) e pausei no x3 as 7 entregas que estavam na fila (3665, 3743, 3747, 3751, 3757, 3759, 3766). Para voltar: `systemctl --user link ~/projetos/imersao2026/diaria/systemd/*.service ~/projetos/imersao2026/diaria/systemd/*.timer` + `enable --now`, e `./yt-pub-x3 retomar <entrega>`.
