# NBR/FLT da travessa isolada por ações locais autenticadas

## Menor extensão implementada

A identidade `ue_catalog_wall_girt_reference_v1`, o contrato de linhas locais
`wall_girt_isolated_vlasov_choice_v1` e a API `height_actions` do adapter de
travessas alimentam os métodos resistentes existentes. Nenhum marcador de
cobertura é criado, copiado ou ativado. `girt_flt_adapter.qualify` reconstitui
as combinações ELU e exige igualdade integral das ações e linhas, mesma fonte
própria, material e escolha explícita do modelo isolado.

PP continua uma vez no CG; altura forte é y_linha−SCy, braço paralelo é
x_linha−SCx. Cada ação conserva sua posição e sinal. Ausência de declaração
permanece None, nunca altura zero nem fachada presumida. Vão físico e
solicitações não mudam quando Ly/Lz mudam.

## Domínio

- NBR local/distorcional e componentes por sinal: métodos existentes da mesma
  família e material, sem copiar resistência Pierin para o contorno próprio.
- FLT clássico: CT/estabilizante por eixo, sem benefício de altura favorável.
- FLT forte desestabilizante: ENV apenas uniforme ou P central e fatores
  tabulados; alternativas q+P/posições/fatores fora dessa fórmula usam o piso
  energético v3, quando suas hipóteses e ponte resistente são aplicáveis.
- Ritz de altura da travessa NÃO foi qualificado neste delta. Não se reconstrói
  `roof.geometry` para fazê-lo passar. Se houver condição suficiente pelo piso,
  ela permanece identificada como tal; excedê-la é inconclusivo.
- A condição de energia com Lz é uma hipótese resistente declarada. A escolha
  explícita de garfos do modelo isolado não comprova que outro Leff equivale a
  fixidez executada. Nenhum apoio intermediário ou mola é criado/inferido.
- Torção primária, estabilidade biaxial física, rede de três travessas e
  aprovação global não são resolvidas pelas componentes escalares.

Fontes e provas dos métodos mantidas em `flt_height_effective.SOURCES`,
`FLT_HEIGHT_ENERGY_FLOOR_R11.md`, `FLT_ENERGY_MOMENT_PRODUCT_V2_20261107.md`
e `FLT_DIRECT_CURVATURE_V3_20261108.md`: NBR14762 §9.8.2.2, ENV1993 AnnexF
informativo e energia de Sahraei2017 Eq2. A extensão presente é somente o
vínculo autenticado das ações, não uma nova fórmula de resistência.

## Histórico e apresentação

Consumidor separado `nbr_ue_wall_girt_application_v1`, com
`application_source_binding` próprio. Panorama aceita esse schema, autentica
antes de consumir e não conserva pendências obsoletas por filtro de versão.
O leitor de resultados antigos de travessa ainda fora do domínio v6 mantém
exatamente a pendência salva. Roof v3–v6 preserva seleção/replay anteriores.
UI e Word exibem nota específica da aplicação e distinguem piso condicional.

Testes sintéticos diretos/área verificam ações por linha, PP, CT, ENV, q+P no
piso, desconhecidas, marcador antigo, modelo desabilitado, adulteração,
panorama e ida/volta JSON/Word. `roof.geometry` e solver Ritz são bloqueados
nos testes; replay é escalar, sem recálculo mecânico de Vlasov.

## QA e entrega

- Primeiro conjunto focal:8 testes novos passaram em23,88s, com JSON/Word.
- Regressão final:139 passaram,76 casos numéricos/mecânicos deliberadamente
  excluídos, em56,25s. Inclui a nota final de Word, integração NBR/FLT de
  travessa, panorama, altura NBR de terça, pisos v2/v3 e replay histórico.
- Teste AppTest existente ganhou assertivas de schema NBR girt e nota de
  aplicação; ainda NÃO executado após este delta, reservado ao integrado.
- Nenhum solver mecânico/eigensolver/UI/rede/publicação foi executado neste
  delta. Os8 testes focais impedem explicitamente roof.geometry e Ritz.
- Dependências: adapter de travessas até eaac1ca e piso FLT v3 até9b13811.
  A integração recebe os commits próprios deste delta separadamente das
  cópias locais desses commits dependentes.
