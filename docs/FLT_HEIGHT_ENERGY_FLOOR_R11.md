# Piso de FLT por energia: q+P, alturas individuais e Ly/Lz

## Resultado e alcance

O módulo isolado `flt_height_energy_floor.py` fornece um **piso analítico
condicional do operador resistente declarado**. Ele não ajusta Me depois de
um solver e não reutiliza C1/C2 de uma distribuição incompatível. O domínio
de carga contém ações uniformes e concentradas arbitrárias no vão, com os
sinais e as alturas de cada ação preservados.

Não é um novo coeficiente normativo. É uma desigualdade derivada da energia
linear clássica de Vlasov escrita por Sahraei, Pezeshky e Mohareb (2017), Eq.2:
https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf

Não altera a conclusão física do modelo nem comprova o detalhamento dos
vínculos. Em particular, quando Ly ou Lz são menores que L físico, o resultado
**não é identificado como piso do solver histórico de garfo livre**, cujo
espaço de perturbações não usa esses comprimentos. As desigualdades resistentes
abaixo são hipóteses explícitas dos comprimentos declarados.

## Hipóteses necessárias

1. Seção prismática elástica rígida no próprio plano, simétrica no eixo forte,
   com o termo Wagner forte nulo. A API de família verifica o contorno, CG/CT e
   integral cúbica exatamente como a referência documental do lote anterior.
2. Perturbação de torção nula nas duas extremidades físicas:
   `phi(0)=phi(Lphysical)=0`. Nenhum apoio intermediário é criado.
3. Com `Ny=pi² E Iy/Ly²`, a energia lateral admitida satisfaz
   `K_lateral >= Ny integral(u'^2)`.
4. A energia de empenamento admitida satisfaz
   `K_warping >= pi² E Cw/Lz² integral(phi'^2)`.
   Eventuais energias positivas de restrição de extremidade estão incluídas
   nesses limites admitidos; o programa não infere nem desenha molas.
5. Não há crédito para torção primária pré-deformada, acoplamento biaxial,
   mudança de geometria ou modos locais/distorcionais no operador.

A declaração de Ly/Lz é consumida como hipótese resistente. Não demonstra
por si a realização física das desigualdades 3–4. Com Ly=Lz=L e as condições
clássicas de extremidade, elas seguem das desigualdades de Poincaré/Euler.
Com comprimentos menores, sua validade depende da hipótese resistente
adotada. O certificado conserva a origem declarada e marca a realização
física como não verificada. Não são exigidas novas entradas ou apoios.

## Derivação

Use a convenção da aplicação: q/P positivos para baixo; h positivo acima do
CT. Para um fator comum de cargas lambda, a energia quadrática é

`2Pi = K_lateral + GJ integral(phi'^2) + K_warping`
`       + lambda [2 integral(M u'' phi) - sum(qh) integral(phi²) - sum(Ph phi(a)²)]`.

Sejam `U=||u'||_2`, `W=||phi'||_2`, `Mmax=max|M(s)|` e
`Vmax=ess sup|M'(s)|`, no vão físico completo. O momento é contínuo mesmo
nos pontos de carga. Integrar o termo acoplado por partes não cria termos
internos de salto; o termo de extremidade é zero porque phi=0.

`|integral(M u'' phi)| = |integral[u'(V phi + M phi')]|`
`                         <= U [Vmax ||phi||_2 + Mmax W]`
`                         <= U W [Mmax + (Lphysical/pi) Vmax]`.

A última etapa usa `||phi||_2 <= (Lphysical/pi)||phi'||_2`, sem trocar o
vão físico por um comprimento resistente.

Para cada ponto `a`, a desigualdade de avaliação no espaço H1_0 é

`phi(a)^2 <= a(Lphysical-a)/Lphysical * integral(phi'^2)`.

Ela resulta de escrever phi(a) como a integral de phi' contra a função
`1_(s<a)-a/Lphysical` e aplicar Cauchy-Schwarz. Seu coeficiente é zero em
ambos os apoios. Alturas de cargas coincidentes são somadas primeiro;
termos estabilizantes negativos podem ser descartados para formar um limite
superior desestabilizante, sem deslocar fisicamente nenhuma ação.

Defina:

- `T = GJ + pi² E Cw/Lz²`;
- `B = Mmax + (Lphysical/pi) Vmax`;
- `D = max(sum(q_i h_i),0)(Lphysical/pi)²`
  `+ sum_a max(sum_(i em a)(P_i h_i),0) a(Lphysical-a)/Lphysical`.

Então `2Pi >= Ny U² + (T-lambda D)W² - 2 lambda B U W`.
A matriz de duas variáveis à direita permanece semidefinida positiva até a
raiz positiva de `Ny(T-lambda D)-lambda² B²=0`:

`lambda_floor = 2T / [D + sqrt(D² + 4 B² T/Ny)]`.

Por isso `Me_floor=lambda_floor Mmax` é um piso do momento de referência no
operador condicionado às hipóteses. Não requer matriz de flambagem ou fator
empírico de diagrama. Em geral é mais conservador que resolver o autovalor.

Se B=0 e D>0, o piso do fator é T/D, mas Mmax=0 não é convertido em Me=0.
Se B=D=0, não é criada capacidade infinita nem um índice de aprovação.
A implementação usa frações exatas dos valores numéricos fornecidos para
agregar forças/alturas, momentos, raízes de cortante e posições. O limite de
pi é racional e explícito. Ny/T são convertidos para baixo; B/D para cima.
A raiz quadrada é envolvida por raiz inteira de um racional escalado, com
mais de 128 bits significativos; lambda e Me são convertidos para baixo.
O determinante da matriz final é rechecado como fração exata não negativa.
Não há epsilon heurístico. Essa certificação aritmética se refere aos inputs
numéricos do operador, não à incerteza física da seção/vínculos.

## Máximos, torques e material

Mmax é encontrado nas extremidades e raízes de cortante de cada trecho
quadrático. Vmax usa ambos os lados das cargas concentradas em todos os
trechos lineares. Cargas aplicadas exatamente nos apoios não geram momento
interior nem potencial de altura porque phi é nulo nesses pontos.

O certificado mantém os torques normal e total, incluindo a ação paralela.
A comprovação do piso se refere à projeção forte escalar; não implica que as
outras ações foram verificadas. E/G são os valores coerentes do contorno
adotado e não são trocados silenciosamente por material de outra norma.

## Consumo resistente ainda separado

A API usa o campo `Me_lower_bound_Nmm`, deliberadamente diferente de Me_Nmm.
Não há hook de capacidade neste módulo. Um piso de Me só pode virar piso
resistente depois de demonstrar a monotonicidade do consumidor ou formar uma
envoltória resistente própria. O projeto já trata essa questão no MSE em
`direct_roof_envelope.nbr_resistance_floor`. Isso não prova automaticamente
monotonicidade do novo MLE da família nem autoriza transferir a mesma garantia.

Índice acima de 1 contra um piso não prova falha da capacidade real. A
extensão não declara aprovação global, resistência completa, nem fechamento
normativo de todo o membro.

## Verificações independentes

Os testes incluem os 66 contornos com q+P fora do meio do vão e Ly/Lz
independentes; raiz decimal independente; avaliação da energia original em
campos trigonométricos admissíveis, para as quatro combinações livre/fixo das
condições laterais/de empenamento; extremos unilaterais de cortante; cargas
nos apoios; cancelamento de resultantes; altura estabilizante; escala de
cargas; e adulteração com rehash. Nenhum solver de autovalor de membro ou
AppTest é executado por essa suíte.

A revisão independente detectou e motivou a eliminação de um problema de
cancelamento: para L=1,1 e q=[1e16, -1e16+2], somar os momentos por parcela
em float produz 0,25 em vez de aproximadamente 0,3025. O novo ramo usa o
máximo racional da resultante, sem alterar o solver histórico. Produtos de
força por altura também são feitos antes de qualquer arredondamento.

Resultado final repetido: 191 testes passaram em 34,32 s, dos quais 81 são da
extensão por energia. A matriz `FAMILY66_ENERGY_FLOOR_RESULTS.json` contém
66/66 casos q+P com Ly=2050, Lz=2733 e Lphysical=4100 mm. São somente
inputs sintéticos; nenhum solver de autovalor de membro foi executado.

No Ue125×50×17×2 sintético dessa matriz, Msd=1,2519830546 kN·m e o piso
condicional de Me é 1,4276882769 kN·m, lambda=1,1403415339. Esses números
não são piso de MRd sem a prova específica do consumidor resistente.
