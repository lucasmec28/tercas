# Candidata posterior à R11: shear lag com Mx + My + B

> Nota da integração R12: o texto abaixo documenta a entrega matemática
> candidata antes da integração. A R12 conecta os dois imports de cálculo/leitura
> e a apresentação de pisos efetivamente usados, sem nova declaração física.
> Os resultados novos e o estado de publicação são registrados separadamente
> em `qa/r12_integration/`. Números de execução histórica não substituem a
> validação da árvore integrada e recuperada. A schema mantém o nome candidato
> por compatibilidade do contrato, sem representar aprovação de membro.

Esta frente é isolada da R11 publicada e não foi publicada. Acrescenta dois módulos novos, um consumidor de cálculo novo com schema `EN_Ue_family_concurrent_section_components_v4_candidate` e seu replay. Nenhum arquivo do consumidor v3, da UI ou dos leitores históricos foi alterado.

A declaração EN que o aplicativo já exige é suficiente para uma futura integração dentro do mesmo domínio físico. Não foi criado checkbox, dado físico ou consentimento adicional. A API separada apenas impede que a pesquisa seja ativada na R11 antes da revisão e dos testes. No cálculo novo de uma próxima versão, o método pode ser escolhido automaticamente quando EN já estiver selecionada e todas as guardas forem demonstradas. Abrir resultados antigos não executa essa expansão.

## O avanço em relação ao componente puro

O piso My puro de `1b063a9` não qualificava um campo que também tivesse Mx e B. A Eq.4.4 de EN1993-1-5 exige considerar as tensões simultâneas. A nova construção cobre o campo inteiro por:

`S = sup|Mx| sup|uMx| + sup|My| sup|uMy| + sup|B| max|omega|/Cw`.

Aqui uMx e uMy são os respectivos operadores efetivos intervalares, cada um com sua própria redução de shear lag. B, omega e Cw continuam na fonte bruta original. Não é escolhido um tensor efetivo biaxial comum. Não há cancelamento favorável entre componentes.

O método só pode ser ativado se, além da autenticação e do curling, `S <= s*`, onde s* é o teto suficiente local/distorcional calculado abaixo de fy. Comparar apenas a tensão com fy, ou apenas My com seu piso, continua proibido.

## Operadores próprios dos dois eixos

A extensão inicial Mx exigia seção integral no estado puro normalizado a fy. Isso deixava de fora perfis cuja seção resistente última era reduzida, embora as cargas aplicadas fossem pequenas. A nova candidata não escala nem requalifica esse certificado antigo.

Para cada eixo:

1. Calcula β em todas as zonas físicas entre zeros de seu próprio momento, não em cortes arbitrários de malha.
2. Usa áreas grossas condicionais à prova posterior de integralidade sob o campo simultâneo completo.
3. Limita as perdas nas retas e admite a perda integral de todos os cantos. Não coloca uma área retida arbitrária nem aplica espessura βt aos arcos.
4. Integra os seis momentos grossos e limita os seis momentos das perdas. Não confunde tolerância numérica de espelho com Ixy=0.
5. Limita ambos os centroides, Ix, Iy e Ixy e demonstra um complemento de Schur positivo.

Em My, os grupos de shear lag são a alma e cada lábio; as retas têm x constante. Em Mx, cada conjunto mesa/lábio possui seu próprio teto de perda. As inércias resistentes e os intervalos dos três coeficientes são distintos por eixo. Reutilizam-se apenas as integrais **brutas recém-calculadas** do mesmo contorno, não propriedades efetivas anteriores.

Os denominadores são:

`DMy >= Iy_min − C²/Ix_min`

`DMx >= Ix_min − C²/Iy_min`, com `C >= |Ixy|` de cada envoltória própria.

Cada piso resistente inteiro é calculado diretamente como `floor(s* Dmin/Rmax)`, com Rmax incluindo deslocamento de centroide, acoplamento e faces físicas. Não é um fator multiplicado por resistência antiga.

## Referência uniforme que fecha local/D simultâneo

### Local

O módulo puro recalcula um teto por compressão uniforme adversa que domina qualquer compressão real do campo total. Usa k=4 para a alma, k=0,43 de outstand livre para as mesas e o piso k=0,5 de Eq.5.13 para os lábios. Não dá crédito ao apoio de um lábio realmente tracionado.

Para cada painel, Eq.4.4 é reavaliada com `sqrt(S gamma_M0/sigma_cr_min)`, exigindo o limite de seção integral. Esse S inclui Mx, My e B. Não é a tensão My isolada.

### Distorcional

Os dois lábios são provados integrais **no estado inicial uniforme em fyb**, antes de usar o lábio inteiro no limite inferior de Is. Isso evita justificar circularmente a rigidez de As pela hipótese posterior de tensão pequena.

A função `_uniform_reference_audit` constrói As geométricos no próprio contorno para:

- as larguras locais iniciais sob compressão uniforme em fyb;
- a referência de larguras locais integrais sob o teto simultâneo.

Não se remove a parcela que estiver realmente tracionada. Não se usa essa tração como crédito de força ou rigidez. O mesmo majorante positivo S é aplicado a todo As de referência. Ele limita a média comprimida e cada compressão relevante de forma conservadora.

Os limites cobrem toda faixa adjacente entre zero e a mesa inteira, não apenas os dois exemplos geométricos exibidos:

- As mínimo contém o lábio reto inteiro;
- As máximo é o lábio mais a mesa completa;
- Is mínimo é `t l_lip³/12`;
- b1 e b2 não excedem a largura física w;
- kr não excede As máximo dividido pela área do lábio reto mínimo.

Disso resultam K mínimo, sigma_cr,D mínimo e chi_d mínimo. O envelope de chi_d inclui os limites laterais das expressões arredondadas, inclusive o salto em lambda_d=1,38. A condição `S <= chi_min fyb/gamma_M0` fecha Eq.5.17 com As_red/As=1 para a referência completa.

A hipótese de área grossa usada em β é, portanto, confirmada no **campo simultâneo** que os próprios operadores intervalares produziram. Não se transfere a conclusão de um estado anterior de centroide/área.

## Cobertura de campo e curling

- Mx/My: equilíbrio biapoiado racional a partir das cargas e posições originais, com conferência exata da sequência binary64 das reações salvas. Bernstein limita todos os trechos e sinais.
- B: coeficientes explícitos, finitos, de grau no máximo3. Bernstein racional cobre cada elemento e o estado limite no apoio, quando houver.
- Seção: todas as extremidades de segmentos, linha média e duas faces físicas. O máximo de omega nos nós cobre o omega linear por segmento.
- Não há testemunha de excesso físico derivada de um controle intervalar.

Curling continua sendo a guarda das **componentes resistentes puras**, não uma alegação de deslocamento físico simultâneo N/M/B. O novo Mx recalcula sua guarda com a tensão demandada do operador novo, o intervalo novo de Cy, a excursão da linha neutra por Ixy/Iy e os cantos. Não herda o status do Mx anterior. My mantém a guarda própria de seu operador novo. Ambos devem qualificar.

## Contrato do consumidor e do replay

`isolated_en_ue_concurrent_candidate.calculate` começa pelo cálculo/replay original, que autentica:

- o provider normal determinístico completo;
- o contorno, a espessura, o CG, omega e Cw contra a geometria própria;
- a fonte densa original, inclusive K*u−f e os polinômios salvos, sem resolver um novo membro;
- cargas, vão, reações e o domínio de análise original.

O certificado de equilíbrio das reações flexionais também é gravado no suplemento novo. Hash declarado pelo chamador não basta.

Se a aplicação v3 já é qualificada, o resultado v3 é retornado **idêntico**. Se estava pendente, o consumidor novo só ativa quando o teto simultâneo, a referência uniforme e os dois curlings qualificam conjuntamente. Se qualquer guarda falhar, os índices normal/interação/M–V pendentes continuam pendentes. Um piso positivo sozinho nunca libera cálculo.

O leitor novo recompõe a aritmética sob a schema nova e compara todo o resultado. Para v3, delega ao leitor original. Não altera fontes, cargas, B/V/T, propriedades históricas ou resultados salvos. Não gera aprovação global, primeira ordem física, ELS ou estabilidade do membro.

## Fontes normativas

- [EN1993-1-5:2006](https://people.fsv.cvut.cz/machacek/PomuckyE/Plated%20structural%20elements%20%281993-1-5%29.pdf): §3.3, Tabela3.1, §4.3(1),(2),(4),(5), §4.4(4)/Eq.4.4 e Tabelas4.1/4.2.
- [EN1993-1-3:2006](https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf): §5.4, §5.5.3.2 e Eq.5.10b/5.12/5.13/5.15/5.17, §6.1.4.1 e §6.1.6(3),(5).

Os limites de área/momentos e o majorante triangular são deduções próprias documentadas, não exemplos prontos de Ue publicados na norma. Nenhum PDF normativo foi copiado ao repositório. Não se exige ensaio universal ou uma FSM nova para esta condição suficiente.

## QA e dados

Os dados são os66 exemplos da matriz sintética de família R11, fy300, L4100, uma DIRECT_ELU por perfil. **Não são dados do projeto real.** A proveniência é `synthetic_application_workflow_matrix` e a declaração `Synthetic R11 complete-family application audit`. O campo genérico `synthetic` da emissão padrão do aplicativo é preservado sem alteração; o recibo registra seu valor original separadamente da proveniência do teste.

Foram preservados os18 testes do componente puro. A suíte focada inclui também autenticação de reações, B e geometria resealada; replay sem solver; falha do teto subyield apesar de tensão abaixo de fy; falha de curling; ausência de cancelamento favorável; As sem crédito de tração; Bernstein exato e amostras independentes de perdas para o operador forte.

Os testes focados e os scripts de replay/survey proíbem `solve_member`: usam apenas cálculo escalar, aritmética intervalar e campos já salvos. O gerador dos quatro casos P executou o solver original do aplicativo para criar essas fontes sintéticas novas, em série e BLAS1; a candidata e sua releitura não executam outro solver. Não foi executado AppTest nem alterada a R11 publicada. Os números finais da execução, hashes e recibos estão em `qa/en_ue_concurrent_shear_lag_candidate/`.

## Hook mínimo de uma próxima versão

A integração não foi aplicada nesta árvore. Em `isolated_en_ue_family_application.py`, o gerador `attach_dense` pode importar `calculate_many` do consumidor candidato, e `_validate_preserved_uncached` pode importar seu `validate_saved_many`. A declaração já existente `isolated_en_ue_family_model` continua sendo o único opt-in físico. Não alterar o engine v3 nem migrar snapshots.

O batch de geração autentica a fonte pelo `original.calculate_many` uma vez e estende apenas cada base validada. O batch de leitura despacha pelo **schema salvo**: v2/v3 vão ao leitor original; v4 é recomposto pela candidata. O custo de autenticação por v4 ainda existe na leitura. Não foi introduzido cache novo.

O cache externo atual inclui `provider._source_key()`, que rehasha todos os `.py`/`.json` do pacote. A suíte verifica que mudar bytes do candidato invalida esse token e também seu `technical_source_sha256`. O conteúdo inteiro do resultado continua integrando a chave externa. A identidade técnica histórica do provider normal não foi alterada.

### Campos que a apresentação deve mostrar para v4

Com `p = check.concurrent_shear_lag_supplement`:

- Pisos **realmente usados** em M–V: união de `p.pure_Mx_construction.signed_capacity_floor` e `p.pure_My_construction.signed_capacity_floor`. Não apresentar os pisos de `normal_snapshot.components` como denominadores usados neste caso. Eles continuam fontes históricas do provider, não certificados requalificados.
- Operadores usados em EN6.1.6: `p.operator_intervals`, coeficientes c0/cx/cy próprios por eixo/sinal, transportados para o CG da fonte efetivamente usado no campo. Não apresentar um tensor comum.
- Guarda simultânea: `p.absolute_stress_contributions_upper_MPa` (Mx, My e B), `p.simultaneous_normal_stress_upper_MPa` e `p.integral_local_D_design_ceiling_MPa`. A soma absoluta limita todo o campo; não é uma tensão física localizada.
- Local/D: `p.simultaneous_uniform_reference.qualified`, a referência As uniforme e os certificados de `p.pure_My_construction.local_distortional_audit`.
- Curling novo: `p.curling_components.qualified` e seus `axes.Mx/My.panels`, com razão/tensão/linha neutra usadas. Não herdar o antigo curling por status.
- Elegibilidade: `p.eligible` somente após fonte autenticada e conjunção de todas as guardas. Falha: `p.blocking_reasons` e os indicadores individuais. `pending_method_domain` explicita `construction_qualified=False` e `source_authenticated=False` no módulo aritmético; o consumidor pode autenticar a fonte e ainda manter `eligible=False`.
- Índices: os mesmos `check.stress.criteria`, `check.shear` e `check.mv` já consumidos por UI/Word/panorama. Sucesso significa condição suficiente seccional, não aprovação global.

Há teste que reconstitui todos os controles M–V com esses pisos novos e compara exatamente ao resultado. Há também teste dos dois imports por shim em memória: o documento, a projeção da UI e o panorama recebem o mesmo snapshot v4 autenticado, sem alterar arquivos de produção. A apresentação descritiva específica de v4 deve ser acrescentada na integração R12; esse teste não afirma que o texto antigo já descreva a metodologia nova.


### Vínculo entre dois CGs determinísticos

O mesmo contorno pode produzir CGs binary64 ligeiramente distintos em dois builders autenticados. Nos índices25 e30, a diferença em CGx era de 3,552713678800501e-15 mm. Não se usa tolerância nem se modifica a geometria/demanda. Os operadores puros permanecem referidos a seu CG normal; os operadores finais são transportados para o CG da fonte:

`c0_fonte = c0_normal + cx*(CGfonte_x − CGnormal_x) + cy*(CGfonte_y − CGnormal_y)`.

A subtração e o transporte usam intervalos direcionados. cx/cy não mudam. O teto unitário é recalculado no CG da fonte com a mesma caixa entregue ao campo. Com N=0 provado, Mx/My são invariantes pela translação de origem. B/omega/Cw, fluxo de cisalhamento e torques permanecem integralmente na fonte original. Os dois CGs e o deslocamento são registrados em `operator_reference_transport`. Igualdade exata retorna os intervalos originais sem ampliá-los. Testes por vértices/Fraction cobrem os casos reais25/30 desta matriz **sintética** e uma translação grande; o consumidor continua rejeitando CG adulterado mesmo com hashes refeitos.
