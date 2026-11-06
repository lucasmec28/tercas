# Interação NBR da terça inclinada por resistências separadas

Base desta alteração: commit 89785b61c2b01a7d5ec350b00c10fc5e9bc8e90d.
São os sete modelos próprios Ue100×50×17, ri=t, nos vãos já qualificados.
Não amplia o catálogo nem muda o modelo de apoios: um vão, garfos extremos,
empenamento livre e nenhum travamento intermediário ou contribuição da telha.

## Fundamento e distinção

A NBR 14762:2010 §9.9, p53, emprega resistências por eixo determinadas em
§9.8.2. Portanto, exigir um autovalor biaxial para toda interação dessa seção
seria uma limitação adicional da implementação, não requisito dessa expressão.
O caso N=0 usa os momentos concomitantes e a soma |Mx|/MxRd + |My|/MyRd.

A ressalva de posição das ações de §9.8.2.2, p48, permanece: a formulação no
centro de torção pode representar conservadoramente uma posição estabilizante.
Anexo E, p82, fornece a resistência crítica fraca; Cm=1 corresponde ao caso
biapoiado com máximo de momento interior. Não se reaplica Cb ao Me forte.

Texto normativo primário conferido em reprodução da edição 2010:
https://studylib.net/doc/28226231/430662924-nbr-14762-2010-pdf
Passagens: p48 (linhas3154–3177), p53 (3429–3450), p82 (5000–5033).
O espelho tem caracteres extraídos corrompidos; as equações, títulos, números
de páginas e remissões foram comparados com a implementação e os registros
prévios de revisão. Não se usou resumo de fabricante como fonte da equação.

## Classificação de posição: interpretação mecânica explícita

Na convenção física já usada pelo Vlasov, F=[Fparalelo,−Fnormal] e x aponta
para os lábios. A contribuição da força paralela à segunda variação do potencial
rotacional é +Fparalelo·(xaplicação−xCT)·phi². Produto não negativo é neutro ou
estabilizante. Este critério é uma classificação mecânica da posição mencionada
na norma, não uma nova equação normativa de resistência.

A classificação é feita para CADA ação antes de somar forças, com PP no seu CG
e demais cargas na linha superior escolhida. Não se classifica somente pela
inclinação ou pela força líquida. Um par de ações opostas que cancele continua
bloqueado se qualquer parcela tiver posição fraca desestabilizante. Coordenada
não qualificada também mantém a pendência. A entrada direta legada com PP
não separado não é ampliada por esta alteração.

No caso sintético de auditoria de 4 m, t=2 mm, +5°, o PP paralelo aponta para
os lábios e o CG está à direita do CT: esta parcela é estabilizante no eixo
fraco. Em −5°, o sentido muda e esta rota não a libera.

## Implementação

- O operador forte existente e seus testes/limites numéricos não mudam. Ele
  calcula o Me da projeção forte, preservando a altura de cada ação normal.
- Esse Me gera o MRd NBR forte no mesmo caso. O menor local–FLT–D entra no
  denominador forte da interação §9.9. Não se recupera MRd do comparador CT.
- A resistência fraca própria do mesmo perfil, material, vão e sentido é
  consumida pelo Anexo E, sem benefício da posição estabilizante.
- O envelope é concomitante e mantém a posição de P. Não soma máximos
  independentes dos dois eixos. Limite P no apoio mantém sua interpretação.
  Um certificado contém os quatro polinômios assinados em cada trecho de P,
  seus extremos e vértices interiores. O leitor confere cobertura e aritmética,
  incluindo que nenhuma estação candidata excede a testemunha governante.
  Uma testemunha artificial nula no apoio não pode passar como máximo.
- O snapshot identifica resistências por eixo, nunca um autovalor biaxial.
  Não se afirma que o Me forte seja limite inferior do autovalor combinado.
- Torque total do novo registro inclui −ex·Fnormal−h·Fparalelo. O torque da
  projeção normal fica salvo separadamente. A análise Vlasov não é alterada.
- UI/Word/panorama substituem somente as pendências resolvidas. M–V, AISI,
  EN, vínculos, introdução local, ELS, torção e aprovação global não mudam.
- Leitura de históricos não recalcula nem promove resultados antigos.
  Novos vínculos de origem e inventário são verificados antes da apresentação.

Quando um piso distorcional fraco governa, índice acima de 1 permanece
inconclusivo como prova de falha física; não se transforma piso de resistência
em teto da resistência real.

## Verificação

Após liberação de CPU, executados com BLAS/OMP/MKL=1:
- 44 testes focais novos passaram em 29,23 s: sete espessuras, sinais, parcelas
  canceladas, eixo ausente, torque externo paralelo, certificados do máximo,
  mutações coerentes com rehash, históricos, área e interface Streamlit real.
- 282 testes dirigidos passaram em 415,43 s: Me/FLT topo, NBR, PP direto,
  envoltória legada, interfaces e rota AISI existente.
- Reprodução do caso sintético exato publicado: em 0°, FLT=0,26394360852979176;
  em +5°, FLT=0,2637128303218076 e §9.9=0,2703624348153767. Em −5°, esta rota
  conserva FLT/interação pendentes pela posição fraca desestabilizante.
- Nos casos 0/+5°, NBR_branches (incluindo M–V), PP, Vlasov, AISI, EN, ELS e
  input_snapshot permaneceram exatamente iguais aos registros publicados.
- O Word de +5° contém o novo índice concomitante, sem repetir a pendência
  legada de resistência forte. Aprovação global permanece falsa nos três casos.

O primeiro teste focal teve três falhas somente por exigir igualdade binária
entre a altura do contorno e 50 mm. O contorno tinha diferenças de arredondamento
inferiores a 1e−13 mm; corrigiu-se a comparação geométrica do teste, não o motor.

Recibo reduzido com entradas sintéticas e hashes em
`NBR_ROOF_BIAXIAL_SCALAR_QA_20261106.json`. Testes são QA de software e do método
implementado, não validação experimental, aprovação de apoios ou projeto.

## Complemento de integridade geométrica

A classificação da posição paralela não depende apenas do hash do snapshot.
Para as sete referências próprias, o leitor liga o ID e o hash de nós às
coordenadas CG/CT congeladas do mesmo contorno e confere posição da linha,
altura, dimensões e excentricidades. Os valores escalares estão pinados ao
SHA-256 de cada fonte de `torsion_study.PINS`. A tolerância de comparação é a
já usada na consistência geométrica da fonte (relativa 2e−12, absoluta 1e−10 mm),
não uma tolerância de atendimento estrutural. Leitura não reabre fontes nem
reconstrói a seção.

Contornos coerentes diferentes dessas sete referências recebem pendência
controlada somente nesta rota por eixos, sem abortar outras componentes. Isso
é limite de integração e do contrato salvo, não proibição normativa das outras
seções. A expansão de catálogo exige teste integrado próprio após o merge.

A regressão leve com 24 testes passou em 1,19 s. Inclui troca coerente do CT
que faria −5° parecer estabilizante, ações/classificação/hash refeitos, além
de alterações do CG, altura, posição, dimensões e identidade. O leitor rejeita
as falsificações. Um contorno diferente permanece pendente sem exceção global,
e o leitor é testado com acesso às fontes e solver desativados. Históricos sem
a nova classificação não são migrados, recalculados nem promovidos.

Após o complemento, os 44 testes focais completos passaram novamente em
29,88 s, incluindo as sete referências e a interface Streamlit real.
