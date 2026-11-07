# Piso distorcional forte da aproximação existente

## Entrega e alcance

`tercas.nbr_ue_strong_distortional_floor` fornece um certificado puro e versionado,
`nbr_ue_strong_distortional_approximation_floor_v1`, para as 66 linhas Ue completas
do registro documental. A API é:

```python
from tercas import nbr_ue_strong_distortional_floor as distortion_floor

certificate = distortion_floor.assess(
    index,
    material=dict(E_MPa=200000., G_MPa=77000., fy_MPa=300., nu=.3, gamma=1.1),
    # Opcional: momento forte puro assinado, sem combinação automática de eixos.
    Msd_Nmm=1_000_000.,
)
distortion_floor.validate_saved(certificate, index=index,
    material=certificate['source_binding']['material'], Msd_Nmm=1_000_000.)
```

Retorna `Fcrd_lower_bound_MPa`, `Mdist_lower_bound_Nmm`,
`MRd_lower_bound_Nmm`, provas racionais, fontes e vínculo integral ao contorno e
material. O material padrão é o mesmo da família existente. E, G e nu são
independentes e explícitos; G não é recalculado de E/nu. fy não muda o piso
elástico. Não há leitura de críticos Pierin como entradas resistentes.

O resultado é um **piso da formulação aproximada já adotada**, não piso de um
autovalor físico/FSM ou de cada contorno arredondado. Aplica-se à referência de
flexão forte pura e simétrica, ambos os sinais, seção nominal sem furos, pequenos
giros e estabilidade elástica linear. Não resolve eixo fraco, estado combinado,
pré-torção, apoios reais, adequação física ou aprovação global.

O módulo não aceita L, Lm, Ly, Lz, comprimentos efetivos, molas ou apoios. A prova
vale para toda meia-onda positiva da expressão e dispensa sua escolha. Isso
remove a necessidade matemática da guarda `L físico >= Lcr` **para este piso de
referência**, sem afirmar uma solução de membro finito ou usar L como Lm. No texto
AISI, Lm é a distância entre restrições distorcionais discretas. Esse dado não é
deduzido do vão nem de comprimentos de FLT.

## Fonte e correspondência

- ABNT NBR 14762:2010, §9.3: rota da aproximação já documentada; §9.8.2.3:
  exclusivamente a curva resistente NBR.
- AISI S100-16 (2020), Supplement 3 (2022), Apêndice 2, §2.3.3.2(a), Eqs.
  1/2/4/5/6/7, e kfe da Eq. 2.3.3.1-3. PDF pp.231–232, impressas 2-12–2-13.
  [PDF oficial](https://buildusingsteel-media.s3.amazonaws.com/wp-content/uploads/2023/06/23212327/AISI-S100-16-2020-wS3-22.pdf).
  SHA-256: `706a4bfaf030768d6382324a8d1916acdb749a0e739ef20fa0d7638ba8a9f03a`.
- As mesmas expressões gerais de AISI S100-2024, já adotadas em
  `nbr_ue_family_base.elastic_distortion`; referências e SHA-256 constam do
  certificado. `docs/UE125_NBR_DISTORTIONAL_20261106.md` preserva a adoção,
  correlação e testemunho histórico. Ele não é reescrito por esta extensão.

Usam-se beta=1, xi_web=2 e k_phi=0. A fórmula preliminar do comentário, a curva
resistente AISI, fatores empíricos novos e créditos de telha/momento-gradiente
não são usados. A correlação de família publicada em Glauz2018 não é convertida
em garantia pontual ou piso físico.

A subestrutura mesa-lábio mantém a Tabela 2.3.3-1: b=bf−t e d_lip=D−t/2, linhas
médias sem raio, não larguras planas entre tangências. H, Af, Jf, Ixf, Iyf, Ixyf,
xo, xh e yo são os da formulação existente, incluindo a parcela em t³ de Ixf.
Sfc=Ix/(h externo/2) usa exclusivamente Ix do próprio contorno arredondado
preparado. Raio, identidade nominal e hash dos nós ficam vinculados ao resultado.

## Prova do piso para todo q positivo

Defina q=pi/Ld, s=(qh)² e:

```
H = Cwf + Ixf (xo−xh)² (1−Ixyf²/(Ixf Iyf)), com Cwf=0
K = E t³ / [4(1−nu²)h]
a = E H + K h⁴/720
b = G Jf + 2 K h²/15
c = K
C = Ixf + Iyf + Af [xh²+yo²−2yo(xo−xh)Ixyf/Iyf]
d = t h³/240
R(s) = (s²+8s+300)/(s²+28s+420)
F(q) = (a q²+b+c/q²)/(C+d R(s))
```

Todos os coeficientes são calculados e sua positividade é exigida. Para s>0, os
dois polinômios de R são positivos e sua diferença é 20s+120>0, portanto 0<R<1.
Logo 0<C+dR<C+d. A desigualdade aritmético-geométrica dá
`a q²+c/q² >= 2 sqrt(a c)` para todo q>0. Assim:

```
F(q) >= [b+2 sqrt(a c)]/(C+d) = F_floor
Mdist(q) = Sfc F(q) >= Sfc F_floor
```

Esta é uma prova analítica, não mínimo por amostragem. O Lcr da expressão
existente minimiza apenas `a q²+c/q²`, não a razão completa com R variável.
Esta extensão não renomeia aquele Lcr como mínimo exato, nem altera sua fórmula
ou resultados históricos.

## Direção aritmética e curva resistente

Todos os escalares de entrada são interpretados como valores binários exatos.
Subtrações de dimensões, propriedades mesa-lábio, H, C, coeficientes e Sfc são
operados em frações racionais, sem cancelamento arredondado intermediário.
A raiz de ac recebe um intervalo por raiz inteira, com pelo menos 128 bits
significativos. F é convertido para binary64 para baixo; o Mdist usa **esse F
exportado** e Sfc exato e é convertido para baixo. A curva resistente usa **esse
Mdist exportado**, não o valor não arredondado oculto. Os extremos de Sfc e lambda
também são reportados com direção explícita.

Para Mdist>=Mdist_floor, lambda=sqrt(Sfc fy/Mdist) não aumenta. A curva capada já
adotada é rho=1 até lambda=.673 e, acima, min(1,(lambda−.22)/lambda²). Sua derivada
no ramo reduzido é (−lambda+.44)/lambda³<0. O cap em 1 elimina o pequeno excesso
produzido pelos coeficientes decimais arredondados junto a .673, sem crédito
resistente extra. Lambda é cercado para cima; rho e `MRd=rho Sfc fy/gamma` são
avaliados para baixo. Logo o MRd é um piso de toda a curva para Mdist acima do
piso elástico.

As frações exatas e os passos ficam no certificado. Não se afirma uma inclusão
intervalar dos erros de discretização do contorno, propriedades físicas, modelo
teórico ou correlação. A prova começa nos escalares da aproximação declarada.

## Condição suficiente e integração proposta

Se Msd for fornecido, a API usa abs(Msd)/MRd_floor, com divisão para cima, e
compara as frações exatas. Igualdade é suficiente. Resultado acima de 1 é sempre
`inconclusive_floor_exceeded`, com `failure_proven=False`. Não existe tolerância
que transforme o próximo float acima do piso em atendimento.

**Nenhum provedor, application, member, panorama ou histórico compartilhado foi
alterado nesta entrega.** Hook proposto, somente em versão nova/fresh calculation:

1. Preservar a dispensa documental válida por Tabela 14 e a referência
   convencional já existente. Não migrar evidências salvas nem reescrever seus
   denominadores.
2. Se a referência própria forte distorcional estiver ausente exclusivamente
   por `L físico < Lcr`, chamar `assess(index, material=material_exato)` e guardar
   o certificado separado, identificado como `approximate_reference_floor`.
   Conferir igualdade de identidade nominal, nós, material e convenção Sfc.
3. Consumir o piso como **condição suficiente de componente**, com replay
   completo. Não apresentar Mdist_floor como autovalor e não marcar capacidade
   ordinária/exata. Não tomar Lm de L/Ly/Lz ou criar vínculo.
4. Para demanda forte pura <=piso, a componente distorcional pode ter atendimento
   suficiente **sob a aproximação adotada**. Acima, manter componente inconclusiva;
   não alimentar automaticamente um `exceeds`/`failed` legado. Uma falha de outra
   componente com capacidade ordinária comprovada continua sendo daquela
   componente, nunca consequência de exceder este piso.
5. No mínimo entre capacidades, propagar o tipo de evidência de cada parcela.
   Empates com capacidades ordinárias não devem apagar sua proveniência. A
   integração precisa de testes próprios para essa composição antes de mudar
   contagens, relatórios ou resultados de membro. `whole_member_approved`,
   `actual_load_capacity_qualified`, `biaxial_qualified` e
   `physical_resistance_bound` continuam falsos aqui.

## Testes e testemunho

`tests/test_nbr_ue_strong_distortional_floor.py` cobre as 66 linhas em
fy=250/300/345/350 MPa; referência Decimal independente a 90 dígitos; reprodução
independente das rigidezes Eqs.5–7 em múltiplos q e materiais; testemunhos
racionais em 25 q por geometria; curva resistente junto ao limiar; demanda
positiva/negativa/zero, igualdade e floats adjacentes; rejeição de entradas
inválidas, alterações rehashed e substituição número/booleano; e preservação do
provedor histórico para vão curto. Amostras não substituem a prova analítica.

Ue125×50×17×2 (índice26), E=200000, G=77000, fy=300 MPa, nu=.3, gamma=1.1:

- Fcrd_floor=718.4641551446908 MPa.
- Mdist_floor=13579405.793814167 Nmm.
- MRd_floor=5154709.919603469 Nmm; rho=1 neste testemunho.
- O valor convencional Fcrd em Lcr é 740.7103215331766 MPa, portanto maior.

Testes escalares, BLAS limitado a um thread; nenhuma varredura FEM/FSM,
publicação ou promoção global.

Execução local de 07/11/2026 sobre a base `09bf50f`:

- Nova suíte: 373 passaram em 12,44 s.
- Regressões `test_nbr_ue_family.py` e `test_ue_catalog_nbr_distortional.py`:
  238 passaram em 11,53 s.
- `git diff --check` e compilação dos dois arquivos Python: sem erros.
- A suíte integral do aplicativo não foi executada neste módulo isolado.
