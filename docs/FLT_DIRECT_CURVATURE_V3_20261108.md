# FLT: domínio remanescente e piso de curvatura direta

## Mapa após o dispatch completo, não apenas a fórmula ENV

Para a família documental completa de 66 contornos próprios, mesma geometria
resistente/material, flexão forte e ações autenticadas de terça isolada:

1. CT ou altura estabilizante: referência NBR clássica com Ly/Lz independentes
   e Cb=1, sem benefício estabilizante. Não necessita ENV ou Ritz.
2. Altura desestabilizante, resultante uniforme OU P central: referência
   documental aproximada ENV1993-1-1:1992, Annex F, tabela F.1.2, se
   Ly/L=.5 ou 1 e .5≤Lz/L≤1; sem interpolação. Fatores .5 são hipóteses
   resistentes equivalentes, não prova de fixidez física por Leff.
3. Outras distribuições com pontos (q+P, ponto fora do centro, múltiplos pontos):
   cálculo fresco usa o Ritz Vlasov existente se Ly=Lz=L físico, contorno
   simétrico, projeção paralela admissível e convergência numérica qualificada.
4. Casos desestabilizantes ainda sem capacidade pela referência anterior
   tentam piso energético e a ponte resistente NBR: cargas q/P e posições
   gerais, Ly/Lz positivos independentes. Há uma condição suficiente, não Me
   exato. Piso excedido é inconclusivo, nunca reprovação.

Assim permanecem sem Me de referência aplicável: misturas/posições não
qualificadas na ENV com Ly ou Lz diferentes de L; fatores fora da tabela
para carga uniforme/central; referência numérica sem convergência/escopo;
altura desconhecida, seção fora de simetria ou fonte incompleta; casos sem
momento resultante que ainda têm potencial de giro. O piso resolve apenas
subconjunto suficiente, quando suas hipóteses e ponte NBR são aplicáveis.
Torção primária, estabilidade biaxial, cisalhamento/shear lag, contornos
incompletos e aprovação global são questões separadas. Eixo fraco não ganha
uma fórmula de altura por esta extensão. Travessas continuam exigindo o
adapter próprio de suas ações; não herdam a geometria de cobertura.

## Método simples reaproveitado e sua origem

Fonte publicada da energia: Sahraei, Pezeshky e Mohareb (2017), Eq.2:
https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf

A desigualdade aqui implementada é derivação explícita, NÃO fórmula normativa
atribuída aos autores ou extensão inventada dos coeficientes ENV. Não foi
qualificada uma fórmula publicada genérica q+P com fixidez determinada apenas
por Ly/Lz. Reaproveita a energia já documentada e a ponte NBR já demonstrada.

No intervalo físico [0,L], u∈H² e phi∈H²∩H1_0. Admite-se energia lateral
Klat≥EIy||u''||² (eventuais energias de vínculo não negativas), além das
hipóteses anteriores Klat≥Ny||u'||² e Kwarp≥ECw(π/Lz)²||phi'||².
As últimas são hipóteses resistentes declaradas, não consequência física
comprovada de comprimentos efetivos digitados. Lz permanece nessa condição
mesmo se não houver realização física verificada. Quando todos os comprimentos
coincidem com L, as desigualdades clássicas decorrem do espaço garfo livre.
Não é necessário adicionar um novo input ou impor um vínculo ao usuário.

O termo original é limitado sem integrar por partes:

|∫M u'' phi| ≤ Mmax ||u''|| ||phi|| ≤ Mmax (L/π)||u''|| ||phi'||.

Poincaré usa SOMENTE L físico. Com Udir=(Ly/π)||u''|| e W=||phi'||:

Ny Udir² = EIy||u''||², Bdir=Mmax L/Ly,
Bdir²/Ny=Mmax² L²/(π² EIy).

O Ly cancela na alternativa direta; ela não inventa benefício por reduzir Ly.
Usa-se o melhor entre esta desigualdade e a do produto de momento v2. As
coordenadas Udir e ||u'|| são diferentes: não se somam as energias nem se
alega que Bdir limita (M phi)'. São duas provas independentes de positividade
do mesmo operador, com raiz na forma Ny(T−lambda D)−lambda²B²=0. Por isso
selecionar o menor B produz o maior piso válido. T e D são os anteriores;
as alturas individuais e o diagrama físico completo são preservados.

Sem potencial de altura, a alternativa direta recupera o piso
Me=(π/L) sqrt(EIy [GJ+ECw(π/Lz)²]), equivalente à referência de momento
constante no vão físico, sem benefício de Cb. É particularmente útil para
Ly≈L e Lz≠L, onde não se aplica o Ritz existente. Para Ly muito curto o piso
v2 pode ser melhor e é mantido. Não é piso certificado da barra física quando
as hipóteses de energia declaradas não foram demonstradas fisicamente.

## Aritmética, histórico e limites

Bdir é fração exata Mmax L/Ly, convertido para cima. Ny e T continuam
convertidos para baixo, D para cima, lambda/Me para baixo; a raiz é envolvida
por raiz inteira racional e o determinante é rechecado exatamente. Não há
eigensolver novo, nova malha, rescale de autovalor ou alteração de solicitações.

Piso elástico v3 / ponte NBR v3 / consumidor v6 são novos. Defaults isolados
v1 e chamada explícita v2 mantêm o resultado histórico. Replay v3/v4/v5 do
consumidor continua selecionando exatamente suas rotas anteriores. Nenhum
resultado salvo é promovido ou migra automaticamente ao ser lido.

O teste de fechamento usa q+P sintéticos, Ly=L=3600, Lz=2400, fora de ENV e
Ritz; escolhe uma solicitação entre os pisos resistentes v2 e v3. O caso
antes inconclusivo passa a suficiente SOB O OPERADOR DECLARADO. Isso não é
homologação, aprovação global ou prova de que o vínculo executado satisfaz
a hipótese Lz. Outro caso acima do novo piso segue inconclusivo.

### Testemunha numérica de fechamento (somente sintética)

Índice0, L=Ly=3600 mm, Lz=2400 mm; qPP=.016043952471129466 N/mm,
hPP=0; q=.024065928706694197 N/mm, hq=55mm; P=13.510696817793235N
em s=1800mm, hP=42mm. Msd=.07713763464408825 kN·m em ambos.
V2: Me piso=.07445904776845117 kN·m, MRd piso=.06769004342586469,
índice=1.1395713570278727, inconclusivo.
V3: Me piso=.09524374844854303 kN·m, MRd piso=.08658522586231184,
índice=.8908867982483849, suficiente sob operador declarado.
Com Ly=1800mm na carga-base do teste, o majorante v2 permanece selecionado:
novo piso exatamente igual ao anterior. Nenhum crédito lateral fictício.

## QA executada no clone isolado

- Regressão escalar dos pisos v1/v2/v3, ponte NBR, família66 e replay:
  388 testes passaram em70,08s.
- Delta final:24 ensaios de energia original com espaços free-warping e
  clamped explicitamente construídos passaram em0,51s;9 testes de panorama,
  incluindo schema corrente v6, passaram em0,23s.
- A expectativa do AppTest de importação/cálculo/exportação/reabertura foi
  atualizada para v3; NÃO foi executado neste clone, reservado para integração.
- Nenhum eigensolver, UI, acesso à rede, publicação ou arquivo real de projeto
  foi usado nesta extensão. Revisão matemática independente estática sem
  bloqueio remanescente. `git diff --check` limpo.
