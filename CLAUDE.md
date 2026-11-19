# yt-pub-x3

Publicador único: fila por canal → YouTube + redes sociais, com status por destino, e cortes de lives. Decisões em `docs/ESPECIFICACAO.md`; uso em `README.md`.

- Conta GitHub: `inematds`.
- Publicar de verdade só com `X3_PUBLICAR=1` e canal `ativo: true`. Ligar canal novo é decisão do Nei.
- Não alterar yt-pubx, `~/.config/yt-pubx/config.json` nem os agendadores `yt-pub-livesN` sem pedido.
- Falha de login/cota nunca consome vídeo; envio interrompido vai para `conferir`.
- Blotato e Upload-Post só com autorização expressa do Nei.
- Testes: `python3 -m unittest tests/test_x3.py`, só com publicadores falsos.

## Self-learning

Quando for corrigido ou notar um erro seu, antes de continuar acrescente a lição em uma linha no topo de `## Lessons`.

## Lessons

- Painel: cortes de lives estão desligados nos canais; não montar caixa "Clips" com eles. Usar a publicação de clipes (`clipes.horarios`); leitura ainda a confirmar com o Nei. (18/11/2026)
- Pendência nos `yt-pub-livesN`: `publicados.filename` pode ser clip_id ou nome do arquivo. Conferir os dois, o título e `clips_pendentes` antes de enfileirar. (18/11/2026)
- `lives/` dos `yt-pub-livesN` é link para `/mnt/hd8t`: procurar arquivos com `find -L`, senão a contagem sai zero. (18/11/2026)
- Histórico importado não pode contar no limite diário de cortes: importar sem data de atualização. (18/11/2026)
