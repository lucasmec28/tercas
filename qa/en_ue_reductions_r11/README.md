# Recibo sintético EN Ue R11

Base: `39d1673b0f879112367d36abc2b10f0525072f87` (R10).

- `section_tests.xml/log`: 46 testes seccionais/provider aprovados, 79,18 s. Inclui as 264 seções, integração independente, fontes, adulteração, histórico e categoria numérica forçada.
- `isolated_tests.xml/log`: 18 testes de aplicação isolada e um reteste pontual da reauditoria aprovados, 12,43 s. Inclui JSON/Word, leitura sem solver, solicitações e E/G inalterados, cache adulterado e cortante independente de ramos R10 ainda bloqueados. Esse reteste já pertence aos 46 acima, portanto são 64 testes distintos.
- `material_coverage.json.gz`: antes/depois das 66 seções × quatro materiais × quatro sinais, cortante, métodos e tempos de construção fria.
- `r10_frozen_sources.json`: SHA256 dos 13 arquivos R10 congelados e igualdade byte a byte com a base.

Execução: `OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`; dependências exatas restauradas pelo integrador. Testes seccionais não executam solver de membro. O subconjunto isolado executou os casos sintéticos autorizados; as leituras/reports são testadas com solver desabilitado. AppTest e suíte geral não foram executados neste lote.

Nenhum projeto privado, publicação ou aprovação global foi incluído. Todos os resultados são limitados ao método e domínio declarados.
