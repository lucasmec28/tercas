# R23: apresentação dos resultados CT

Identificação: `apresentacao-CT-textos-20261109-r23`.

Base local: R22 `ffd294aafc931333344b187ef142eaff904dbff7`. O integrador informou como fonte remota publicada `6e1a68171866778076af33ae35ba1dfca091b822`; este preparo não consultou nem alterou o remoto. As duas correções já integradas entram a partir de `dfd038cce5fb622fcd36a5613604b9867ed940fa`.

## Escopo

- No texto de inclinação, PP automático com política CT usa a convenção já registrada pelo próprio PP. Cálculos sem essa política conservam literalmente a convenção anterior.
- Tela e Word mostram “Torção não solicitada no modelo linear calculado.” somente quando há conclusão CT salva e autenticada, demanda nula e demais verificações de consistência satisfeitas. Sem essa prova, permanece o aviso anterior. Os números, critérios resistentes e flags globais não mudam.
- O marcador de sessão passa a `active_ui_caches_CT_presentation_20261109_r23`. Na primeira abertura, somente os três caches ativos já previstos são descartados. Entradas, rascunhos e históricos salvos permanecem intactos; não há cálculo automático nem migração de resultados antigos.

Nenhuma frente nova de Nc, rede, empenhamento, material, Aef ou Ndist é importada. As fontes resistentes, os arquivos normativos vinculados e seus hashes permanecem os da R22. R23 de apresentação não implica liberação de Nc nem aprovação estrutural.

## Verificação e limites

O recibo `qa/r23_ct_presentation/receipt.json` registra o commit de código verificado, os comandos, resultados, hashes e preservação da base. Os quatro arquivos focais de apresentação são executados em série, com BLAS limitado a uma thread, além dos controles de identificador e cache afetados. Os casos são sintéticos. AppTest é local, sem navegador ou serviço hospedado.

Nova execução focal: **61 testes aprovados em 54,10 s**, sem falhas, erros ou testes ignorados. Inclui os quatro arquivos de apresentação e os testes afetados de identificação/cache.

O QA anterior de 51 testes da composição e os resultados dos autores têm cobertura sobreposta; não são somados à nova execução. Não foi executada a suíte integral. Este pacote é candidato local para revisão do integrador: não é publicação, homologação nem confirmação de comportamento do serviço remoto.
