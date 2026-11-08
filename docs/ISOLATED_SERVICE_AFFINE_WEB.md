# ELS combinado: majorante afim suficiente da alma

Esta extensão reutiliza `biaxial_gross.gross_mle.web_index`, sem alterar seu
arquivo pinado. Acrescenta apenas uma prova suficiente para a alma AA ao crivo
das cinco paredes já existente. Não calcula seção efetiva reduzida, não resolve
novamente o membro e não altera ações, vínculos, geometria ou rigidez física.

## Fonte e domínio

ABNT NBR 14762:2010, §§9.2.2.1–9.2.2.2, Tabela 5 casos a/b e §9.8.5(a).
Fonte primária conferida visualmente nas páginas impressas 26–28 e 51;
SHA-256 `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.
O PDF não integra o repositório.

As tensões de serviço vêm do campo concomitante Mx+My+B salvo, com ambas as
faces exteriores e todo o vão físico. Define-se compressão como C=−sigma.
As bordas recebem S0,S1 não negativos, superiores a C em cada borda em todas
as peças longitudinais e em ambas as faces. A linha L(u)=(1−u)S0+uS1 é um
comparador superior, não uma seção física onde os dois máximos necessariamente
ocorrem juntos. Não há crédito por tensão de tração nem extrapolação para ψ<0.

Na rota adicional, a cadeia da alma deve ser contígua; todos os seus nós têm
abscissa exatamente igual e ordenadas estritamente crescentes. Não se usa uma
tolerância geométrica favorável. O reconhecimento geral das cinco paredes
permanece inalterado, mas uma geometria que não satisfaz esse domínio mais
estreito simplesmente não recebe a prova afim adicional. A rota uniforme k=4
permanece independente. O domínio é definido pelos dados, nunca pelo nome do
perfil, espessura específica ou lista de identificadores.

## Dominação completa e correção exterior

O código não presume que omega discreto seja perfeitamente afim entre as duas
extremidades da alma. Para cada segmento, usa todos os coeficientes Bernstein
de C no vão e na coordenada da parede, nas duas faces. A linha L é representada
no mesmo grau na parede, inclusive o coeficiente intermediário quando o grau
foi elevado para 2, e é constante na coordenada longitudinal.

1. Calcula u=(y−y0)/(yN−y0) com intervalos exteriores, sem arredondar u para
   dentro de [0,1]. Os valores exatos estão nesse intervalo pela ordem dos nós.
2. Calcula o limite superior de todos os coeficientes de C−L.
3. Adiciona a ambas as bordas delta=max(0,resíduo superior), mais uma margem
   aritmética explicitamente desfavorável de 1e−12 vezes a escala das tensões
   (no mínimo 1 MPa). Todas as somas são arredondadas para cima.
4. Repete a verificação intervalar completa e exige resíduo superior final ≤0.
   A margem nunca substitui essa exigência e não é tolerância de aceitação.

Uma combinação convexa de coeficientes não positivos é não positiva. Portanto
C≤L em todo segmento e todo intervalo do vão, não apenas em estações amostradas.
A prova inclui diferenças de omega e arredondamento em todos os nós/segmentos,
além das duas faces e da interpolação em espessura. Ela é uma dominação mecânica
de compressão, não uma nova fórmula normativa para um campo não afim.

O snapshot registra bordas iniciais/corrigidas, resíduos antes/depois, correção,
margem, inventário de segmentos, quantidade de nós/coeficientes e faces. Se a
dominação não for certificada ou houver falha numérica, a rota adicional fica
inconclusiva. Valores não representáveis como JSON finito são recusados.

## Critério escalar e monotonicidade

Usam-se os casos a/b da Tabela 5: a=max(S0,S1), b=min(S0,S1), ψ=b/a∈[0,1],
k=4+2(1−ψ)+2(1−ψ)³. Para ψ=1, obtém-se o caso uniforme a, k=4; para ψ<1,
o caso b. A verificação é λ=(largura/t)/0,95 sqrt(a/(E k))≤0,673.

Aumentar qualquer borda não reduz λ. Com F(a,b)=a/k(b/a),
dF/db=−k′/k²≥0 e dF/da=(k+ψk′)/k²>0. Escrevendo d=1−ψ∈[0,1],
k′=−2−6d² e k+ψk′=2+4d−6d²+8d³=2+2d+2d(1−3d+4d²)>0.
A função simétrica por troca das bordas é contínua em a=b e conserva essa
monotonicidade. A elevação das bordas e a correção residual não criam ganho
artificial de suficiência. O limite em a=b=0 é zero.

O comparador utiliza a maior entre a largura nominal h−2ri−2t, derivada em
Decimal de 70 dígitos dos dados binários exatos, e o limite superior da largura
geométrica yN−y0. Não usa largura pré-arredondada favorável. A decisão chama o
`web_index` existente dentro desse contexto e aplica a guarda interna 1e−20.
O campo de largura superior sai arredondado para fora; ψ, k e λ gravados em
float são diagnósticos. O aceite é decidido antes de sua conversão.

## Preservação, histórico e alcance

- v1: comparação uniforme original, sem crédito do enrijecedor.
- v2: a mesma comparação com a rota suficiente das mesas §9.2.3.
- v3: mesmas mesas/lábios/dobras/guarda elástica e a prova afim da alma.

O despacho é explícito pelo schema salvo. Abrir v1/v2 não os promove a v3.
O replay recompõe a aritmética do campo salvo sem solver e verifica todo o
registro; um hash refeito não legitima alterações de resíduos, bordas, ψ,
largura, inventário ou suficiência. UI e Word distinguem as três versões.

O campo de deslocamento, giro, ponto/direção, corda e critério não mudam.
Mantêm-se as mesas e seus lábios adjacentes, todos os cantos no controle
elástico, cisalhamento V+Tsv+Tw e von Mises≤fy. Resultado inconclusivo não é
falha física nem exigência normativa de seção integral. Suficiência permite
apenas a comparação no campo linear declarado, sem aprovação ELS completa,
estabilidade global, validade física de primeira ordem ou seção reduzida.

## Verificação

Os testes usam campos sintéticos, inclusive Mx, My e B não nulos, extremos
não concomitantes, tensões trativas, segunda face desfavorável, coeficientes
internos não afins, fronteira do critério, dados mal ordenados, overflow e
JSON não finito. Os 66 contornos completos são parametrizados diretamente por
`pierin_ue_registry.new_study_indices()`, sem seleção por nome.

Uma revisão independente verificou 87 decisões λ² por aritmética racional e
12.528 coeficientes contra a linha afim com Fraction exato. O replay frio dos
snapshots sintéticos v1/v2 e v3 foi realizado sem solver, com o runtime
numérico original dos snapshots. Resultado e limites da focal constam em
`ISOLATED_SERVICE_AFFINE_WEB_QA.json`. Nenhum dado de projeto privado integra
testes, documentação ou recibos públicos deste delta.
