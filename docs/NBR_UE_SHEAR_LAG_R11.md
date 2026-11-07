# NBR 14762 §9.4: qualificação explícita da família Ue

## Entrega e limite

`tercas.nbr_ue_shear_lag` fornece uma função pura de aplicabilidade, sem gerar seção, resolver estabilidade, modificar esforços ou reduzir propriedades. Seu consumo se destina somente às 66 linhas Ue documentalmente completas já admitidas pela aplicação da família. Não habilita perfis genéricos, rede, viga contínua ou balanço.

A leitura visual da ABNT NBR 14762:2010, páginas impressas 32–33, confirmou o item 9.4, a Tabela 7 e as definições imediatamente posteriores. Nenhum PDF ou imagem da fonte acompanha esta entrega.

O item incide sobre vigas de referência `L < 30 bf0`, com força concentrada ou várias forças concentradas suficientemente espaçadas. Nessa situação, as larguras das mesas tracionada e comprimida afetam as propriedades geométricas; a largura comprimida também fica limitada pela redução local de 9.2.2/9.2.3. Não é correto multiplicar um MRd existente pelo fator da Tabela 7, reduzir somente a mesa comprimida, nem alterar Msd para representar shear lag.

Esta entrega **não implementa a redução da Tabela 7**. Quando a dispensa não é demonstrada, registra uma pendência de qualificação, não uma reprovação resistente, proibição normativa ou prova de que a redução é obrigatória.

## Comprimento e dimensões

- Para a viga isolada simplesmente apoiada, `L` é o vão físico. `Lx`, `Ly`, `Lz`, intervalos da malha e divisões em P não o substituem.
- A norma define outros comprimentos para vigas contínuas e balanços. A função rejeita esses modelos, em vez de reaproveitar o vão físico indevidamente.
- Em Ue, a referência da mesa enrijecida inclui a largura livre da mesa **mais a largura nominal do enrijecedor de borda**. Usar somente `bf` omite o lábio.
- O contrato de dimensões externas é o do contorno `catalog_torsion_section`: `h`, `bf`, `lip`, `t`, seção Ue simétrica e lábios de 90 graus. A aplicação autentica a identidade nominal e o contorno antes da chamada; a função não transforma dimensões de outra convenção.

As provas são suficientes e deliberadamente conservadoras:

1. Eixo forte (`normal`, Mx): `bf0 <= bf + lip`. `bf` externo limita a largura livre e `lip` é a largura nominal externa do lábio.
2. Eixo fraco (`parallel`, My): a alma original é a placa entre as duas mesas originais; usa-se toda a altura externa `h`, sem crédito de metade. Os lábios originais são elementos em balanço, de largura no máximo `lip`. O majorante `max(h, bf + lip)` contém essas larguras e mantém a cota da mesa original. Não se soma arbitrariamente `bf` à alma como um novo enrijecedor.

Essas cotas **não são definições exatas de bf0**. A classificação rotacionada e a possibilidade de usar metade da largura entre elementos de alma podem permitir dispensa mais ampla depois de prova específica. A função não usa esse benefício. Um caso abaixo da cota suficiente pode ainda ser dispensado após qualificação mais precisa.

## Inventário de ações e resultado

`assess(*, physical_span_mm, external_dimensions_mm, actions, member_model)` exige `member_model='isolated_simply_supported'`. `actions` usa os mesmos campos produzidos por `direct_roof_separated.actions` e `roof_top_load._actions`, com `include_parallel=True`:

- Distribuída: `kind='uniform'`, `q_down_N_mm`, `q_parallel_N_mm`.
- Concentrada: `kind='point'`, `P_down_N`, `P_parallel_N`, `s_mm`.

O exame é individual antes de cancelamentos. Uma parcela distribuída contrária não apaga uma P. Duas P contrárias tampouco são descartadas. Forças minúsculas não são zeradas por tolerância. Reações não são inventadas como novas cargas aplicadas. Não se usa uma dispensa por espaçamento de várias P ou por P exatamente no apoio; tais casos podem ficar conservadoramente pendentes.

Cada eixo recebe:

- `not_triggered_no_concentrated_action`: nenhuma parcela P não nula nesse eixo, inclusive q puro em vão curto.
- `not_required_sufficient_span`: P presente, mas `L >= 30 * bf0_upper` demonstra dispensa. A igualdade é admitida porque o gatilho normativo é estritamente menor.
- `pending_shear_lag_qualification`: dispensa não demonstrada por esta função. Resolver a geometria de referência e, quando aplicável, as propriedades com redução conjunta antes do uso como resistência da barra.

`qualified` global é a conjunção dos dois eixos. `bf0_exact_determined=False` e `normative_reduction_required_demonstrated=False` evitam confundir a cota suficiente com incidência demonstrada da redução. Frações exatas dos números binários de entrada controlam a fronteira; números de apresentação são arredondados para cima.

## Proposta de hook, a cargo da integração

Depois de `_inventory`, `_outside_domain` e da autenticação de `own['source_binding']`, em cada combinação ELU:

```python
from .nbr_ue_shear_lag import assess as assess_shear_lag

shear_lag = assess_shear_lag(
    physical_span_mm=data['L_mm'],
    external_dimensions_mm=own['source_binding']['nominal_identity']['dimensions_mm'],
    actions=acts,
    member_model='isolated_simply_supported',
)
record['shear_lag_applicability'] = shear_lag
```

O consumidor deve:

1. Executar a guarda em **todas** as combinações ELU, não apenas na governante, e preservá-la no replay autenticado.
2. Manter as capacidades puras de referência e todos os esforços originais. Exigir a guarda nos eixos com flexão realmente ativa, conforme a prova exata do consumidor. P em apoio pode produzir momento identicamente nulo e não exigir denominador flexional; isso não resolve torção, rotação ou efeitos locais da carga.
3. Se qualquer eixo com flexão ativa estiver pendente, não promover capacidades sem redução a uma conclusão resistente da barra. Uma opção conservadora é suspender todos os índices de flexão de carga real, sem remover os valores de referência. Propagar à seleção resistente, interação e panorama, sem permitir que demanda nula de **um sinal** oculte flexão ativa do sinal oposto, nem que uma isenção distorcional ou outra referência recupere aprovação. A guarda por eixo explica a causa; a pendência aplicável bloqueia a conclusão conjunta.
4. Não deixar um índice nominal publicado parecer resolução do shear lag do contorno próprio. Preservar a separação entre comparação nominal e resistência própria.
5. Mostrar a razão e a diferença entre “dispensa não demonstrada” e “falha resistente”. Nenhum `fails` é gerado por esta função.
6. Não requalificar silenciosamente evidência histórica. Usar revisão/schema do consumidor e reconstrução determinística para resultados novos; os leitores legados mantêm seu contrato.

`validate_saved(evidence, **inputs)` refaz somente aritmética escalar. Não autentica por si só a origem de `actions` ou das dimensões; essa obrigação permanece no consumidor de referência.

## Validação local

- 114 testes escalares aprovados em 0,86 s, incluindo as 66 linhas completas do registro.
- Cobertura: q puro, P normal/paralela, sinais, zeros, P minúscula, limites exatos e adjacentes, inclusão do lábio, majorante da alma no eixo fraco, P contrárias, P nos apoios, dados inválidos, modelos excluídos, imutabilidade, JSON e adulteração de replay.
- Importação isolada do módulo não carrega NumPy. Nenhum teste desta entrega executa solver, UI ou rede.
- Testes de integração/UI/Word e revisão do consumo dos índices ficam a cargo da integração. Não foram executados nem declarados aprovados nesta entrega.

Comando de verificação usado neste ambiente:

```sh
PYTHONPATH=.:tests:/workspace/scratch/200bd23c4a9b/tercas_test_dependencies_r11:/workspace/scratch/200bd23c4a9b/connections_audit/test_dependencies \
OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -q tests/test_nbr_ue_shear_lag.py
```
