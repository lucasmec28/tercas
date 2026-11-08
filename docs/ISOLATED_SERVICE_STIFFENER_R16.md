# ELS combinado: extensão da comparação suficiente das mesas

Nota de integração: o histórico v2 descrito aqui permanece preservado. A
extensão seguinte da alma afim, com schema mecânico v3, está documentada em
`ISOLATED_SERVICE_AFFINE_WEB.md`; ela mantém integralmente a prova das mesas.

## O que foi conectado

A rota de deslocamento combinado já existia: translação e rotação concomitantes,
ponto/direção declarados, corda dos extremos físicos, envelope contínuo e critérios
explícitos. Esta revisão amplia somente o crivo suficiente de rigidez bruta,
reutilizando a comparação escalar de mesa enrijecida de §9.2.3 já implementada no
aplicativo. Não acrescenta solver, ações, combinação, rigidez da telha ou apoio.

O crivo anterior tratava as mesas como AL com k=0,43, sem crédito do enrijecedor.
A insuficiência dessa prova conservadora não é exigência normativa de seção
integral, reprovação do perfil ou demonstração de que a rigidez seja reduzida.
A nova rota pode demonstrar integralidade em casos antes inconclusivos. Quando
não consegue, não calcula propriedades efetivas reduzidas nem fabrica índice.

## Fonte e prova

ABNT NBR 14762:2010, §§9.2.2/9.2.3 e §9.8.5(a), fonte primária conferida por
revisão independente, SHA-256
`c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.
O PDF não integra o repositório. A comparação original está documentada em
`BIAXIAL_GROSS_COMPONENT_20261104.txt` e implementada no arquivo pinado
`biaxial_gross/gross_mle.py`, preservado byte a byte.

Para cada mesa, usa-se a maior compressão exterior limitada por Bernstein entre
ela e o lábio adjacente. É uma majorante uniforme do mesmo campo Mx+My+B em todo
o vão, não a tensão de um eixo puro ou a soma de máximos de outros modelos.
Antes de usar a inércia do lábio, sua integralidade é demonstrada inclusive sob
essa majorante comum, com AL k=0,43. Mantêm-se as cinco paredes e a guarda elástica
V+Tsv+Tw/von Mises, incluindo faces exteriores e dobras.

O helper escalar aplica as mesmas expressões anteriores:

- λp0 = (b/t)/0,623 × sqrt(σ/E), ramo baixo λp0≤0,673;
- Is = t × d_plana³/12, sem crédito das curvas;
- limite superior monotônico de Ia dado pelo menor de
  399t⁴[0,487 max(0,λp0−0,673)]³ e t⁴(56λp0+5);
- exige Is≥Ia_superior, com guarda numérica, antes de usar o k de enrijecedor
  integral, respeitando D/b≤0,8, e verifica λlocal≤0,673.

O cubo deslocado domina o cubo literal porque
0,487(λp0−0,673)=(0,487λp0−0,328)+0,000249 no ramo ativo.
As duas funções limitantes são monotônicas nesse ramo. A prova é suficiente e
local-normal, não um novo critério modal/distorcional ou de estabilidade global.

Dimensões planas são derivadas diretamente das dimensões originais em Decimal
com 70 dígitos, antes de arredondar para binary64. A conversão de σ é exata a
partir do limite superior exterior. Predicados têm guarda interna de 1e−20;
valores float gravados são diagnósticos, não o mecanismo de decisão.

## Histórico, interface e limites

Novos cálculos opt-in usam `isolated_service_stiffened_combined_field_v2`.
O leitor mantém `isolated_service_gross_combined_field_v1` e reexecuta a aritmética
exata daquela versão, sem promover históricos e sem resolver o membro.
A autenticação recompõe o campo salvo e a prova, recusando alterações mesmo com
hash refeito. O comparador biaxial histórico e seu pin não mudaram.

A UI distingue método disponível mas não escolhido de implementação ausente.
Ao escolher o par da Tabela A.1 sem ELS rara selecionada, informa essa lacuna;
não transforma frequentes em raras. O limite da flecha flexional preexistente
não é transferido automaticamente a outro ponto/direção. JSON e Word informam
qual comparação de rigidez foi empregada e quando segue inconclusiva.

Ponto, direção, parcela e critério continuam declarações explícitas do projeto.
A aplicabilidade física de primeira ordem, grandes giros, etapas construtivas e
empoçamento não são qualificados por este avanço. `combined_ELS_approved`,
`physical_first_order_applicability_qualified` e `whole_member_approved`
permanecem falsos. Leff não substitui o vão físico. Não houve publicação.

## Validação

Testes sintéticos cobrem igualdade escalar com o comparador existente, campo
Mx+My+B não nulo, ganho de suficiência sem alterar deslocamento/giro, lábio muito
comprimido, guarda elástica, dimensões antes de arredondamento, versão desconhecida,
replay histórico sem promover v1 e adulterações coerentes com hash refeito.
312 testes da focal principal passaram; após os controles adicionais e a
edição final de apresentação, 91 testes de helper/família/UI passaram. São 382
testes distintos cobertos, não a suíte integral do repositório. Os 66 contornos
completos foram exercitados sem solver de membro: 66 dentro de D/b≤0,8,
D/b entre 0,279642 e 0,639098; 66 provas de baixa compressão e 66 recusas de crédito
sob compressão extrema. Isso não é porcentagem de aprovação de projetos.

Um snapshot sintético foi realmente produzido na base R15 congelada e lido na
candidata com solver e refinamento v2 bloqueados. O resultado original ficou
intacto e gross_screen/calculate v1 coincidiram byte a byte. Resultados da
execução focal e revisão independente constam de
`ISOLATED_SERVICE_STIFFENER_QA_R16.json`.
Nenhum dado de projeto privado foi incluído nesses testes ou nesta documentação.
