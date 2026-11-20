# FALHAS — yt-pub-x3

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 19/11/2026 | Short do Gemini 4 (item 3629) saiu às 03:14 e o explicativo (3633) estava marcado para 04:15 no lives4/inema.tds, fora dos horários: a sessão de produção usou `--quando agora`/hora fixa, como o PRODUCAO.md manda para explicavideo | Item 3633 para `fila`; v0.3.0: `agora` vira `fila` na entrada (Nei: tudo entra na fila) | prompt |
| 18/11/2026 | Migração tratou como pendentes itens já publicados, porque o antigo grava `filename` em dois formatos; 414 saíram da fila antes de qualquer envio | Casar clip_id, arquivo e título, e exigir `clips_pendentes` | prompt |
| 18/11/2026 | Painel contava agendados como publicados e vídeos removidos na linha yt-pubx | Separar `pub` de `ag` e ignorar registros com `removido`, com teste | prompt |
| 2026-11-20 | Distribuição de links dos vídeos publicados (Telegram, 5 destinatários) parou em 18/11: o notifier do master só lia lives.db e o histórico do yt-pubx, não o x3.db | fonte x3 no notifier do master (a partir de 20/11 03:45) | infra |
| 2026-11-18 | lives importadas contavam como cortadas hoje e bloqueavam o corte do dia | importar com data vazia | prompt |
| 2026-11-18 | horário rodava antes da varredura da entrada no mesmo ciclo e perdia o vídeo novo | varredura primeiro na ordem dos jobs | prompt |
| 2026-11-18 | revisão achou limite do YouTube em HTTP 400 consumindo fila, reenvio em 5xx, recorte de live já feita e rajada após queda | classificar pelo motivo, 5xx pós-envio vai para conferir, consultar o sistema antigo, expirar horários vencidos | prompt |
