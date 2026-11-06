# Recuperação dos operadores EN Ue após perda do filesystem

## Recuperação byte-exata comprovada

As fontes foram recuperadas do texto integral preservado na conversa da tarefa.
Os hashes foram comparados com valores completos anteriores, não com hashes
calculados pela primeira vez depois da recuperação:

- `tercas/en_ue_catalog_operators.py`:
  `86f8c5d6fb78b344f89d1f4e8adce789cf2a9790d3461d965a1fad83e3e62222`.
- `tercas/en_ue_qualified_library.py`, versão original de dc4aabc:
  `5561f2854f7cb60fcf98f38106e2fef2be31a7499143abc1e1dfaaa133a828dd`.
- O mesmo módulo na versão final do integrador, com a cópia defensiva de
  `normal_integration_conditions` no provider:
  `b53375fc4110e3ec9092cef329639e353ca9b689caae04d8868e14541b0c8cfb`.
- Inventário estático, bytes completos do arquivo:
  `455f8aa52886d620ec54255c332d39ccbac55212870bc046dd3ff4fbe1429353`.
- Pin canônico interno do mesmo inventário:
  `51e7bac78b21e58f2adb2cc5bd25b1a65469fe0334e921e31bc351522c0e1f53`.

A recuperação do inventário rederivou os 83 candidatos e a transformação de
qualificação, sem solver de rede. Só instalou o arquivo depois de reproduzir
SIMULTANEAMENTE o pin canônico e o SHA256 de todos os bytes do arquivo perdido.
Não houve alteração do pin, tolerância, novo cadastro ou admissão por pisos iguais.
Isso recupera os mesmos hashes completos, identidades e ramos das 83 referências.

O SHA256 histórico do relatório de comparação de kernels,
`ce375847a8921f9c9c8355473770d7290f2b365035d5be8263376441a25f8abf`,
foi recuperado da saída original de revisão independente e mantido como proveniência
histórica. O arquivo completo desse relatório ainda não foi recuperado nesta etapa.
O novo cálculo de recuperação NÃO é apresentado como a execução histórica.

## Conteúdo restaurado sem hash anterior disponível

Os três geradores QA e os dois arquivos de testes também foram recuperados do texto
integral disponível. Seus hashes atuais podem ser registrados, mas não há um hash
anterior completo disponível para declarar identidade byte a byte desses arquivos.
Os scripts foram compilados e a focal restaurada executada com sucesso.

Os textos originais de `catalog_torsion_section.py` e de `_construct/from_polyline`
foram repassados à tarefa responsável pela geometria. Apenas esses dois módulos
de dependência foram consumidos aqui; ações, compositor e interação assinada não
foram reconstruídos nem alterados por esta tarefa.

## QA nova desta recuperação

- Inventário: 83 perfis, 498 ramos possíveis, os MESMOS 400 elegíveis e 98 pendentes.
- 35 testes focais passaram em 6,55 segundos.
- Nenhum solver de rede, autovalor, alteração de consumidores ou publicação.
- A comparação nativo/Haswell e as 54 regressões legadas anteriores continuam
  evidências históricas; não foram novamente executadas nesta janela de recuperação.
- O novo recibo e logs estão em `qa/en_ue_recovery/`.

O módulo mantém seleção por sinal, dispensa apenas de zero exato, ausência de
fallback bruto, leitura salva sem reconstrução, inventário externo pinado e
validação contra a fonte original. A biblioteca é NORMAL somente: não fornece
cortante, não qualifica o app/barra/estabilidade/produto físico e não remove as
condições de integração de My+, curling, shear lag, EN6.1.6 ou EN6.27.
