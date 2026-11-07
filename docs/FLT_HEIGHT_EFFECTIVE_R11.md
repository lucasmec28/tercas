# FLT forte: altura de carga e comprimentos resistentes independentes

## Nova referência documental

`tercas/flt_height_effective.py` calcula o momento crítico elástico da expressão
do Anexo F da ENV 1993-1-1:1992, F.2/F.4, com `zj=0`, para distribuições
explicitamente admitidas pela Tabela F.1.2. A forma para canais simétricos no
eixo forte também é discutida em Vermeylen et al. (2023), Eq. 1. A expressão
histórica é utilizada como bibliografia especializada de Me, não como edição
atual da norma resistente EN nem como prova de limite inferior matemático.

O contorno próprio é verificado por reflexão em relação ao eixo forte, posição
de CG/CT e integral cúbica de Wagner. O cálculo não depende do nome de perfil.
Os 66 Ue completos têm o mesmo tratamento paramétrico. Propriedades e
críticos nominais de Pierin não são transplantados ao contorno arredondado.

## Expressão e comprimentos

Com `A = (Ly/Lz)^2 Cw/Iy + Ly^2 GJ/(pi^2 E Iy)` e `z = C2 zg`:

`Me = C1 pi^2 E Iy / Ly^2 [sqrt(A + z^2) - z]`.

A subtração é racionalizada para alturas desestabilizantes. São usados
`kz=Ly/Lphysical` e `kw=Lz/Lphysical`; Lx não pertence a esta expressão forte.
O vão físico continua integral nos momentos, posições de carga e demais
solicitações. Nenhum nó, apoio intermediário ou mola de extremidade é criado.
Os comprimentos são hipóteses resistentes declaradas, não uma reconstrução
ou verificação de vínculos físicos.

Ramos implementados, para o diagrama físico biapoiado:

- Resultante uniforme: C1/C2 = 1,132/0,459 para kz=1;
  C1/C2 = 0,972/0,304 para kz=0,5.
- Resultante concentrada no meio do vão: C1/C2 = 1,365/0,553 para kz=1;
  C1/C2 = 1,070/0,432 para kz=0,5.
- kw pode ser independente de kz, entre 0,5 e 1, dentro do domínio
  F.1.2(2)-(5). Não se interpolam C1/C2 nem se extrapola o domínio.

Os coeficientes variam com kz e distribuição; não são reaproveitados de
NCCI SN003 ou do benchmark anterior de duas cargas em L/4 e 3L/4.

## Alturas e sinais

A energia de ações uniformes contém `sum(q_i h_i) int(phi^2)`. Como todas
possuem a mesma distribuição, a redução exata dessas parcelas é
`qnet=sum(q_i)` e `zg=sum(q_i h_i)/abs(qnet)` no formato de Me positivo.
A mesma identidade vale para cargas concentradas coincidentes em L/2.

O denominador em valor absoluto preserva o efeito estabilizante da sucção e
não classifica a altura pelo sinal isolado de qnet. PP permanece no CG;
nenhuma parcela é movida ao topo. São preservados os torques normais e o
torque total `-ex Fnormal - h Fparallel` por ação. Torque de posição horizontal
desconhecida permanece desconhecido, não zero.

Resultante nula com potencial de altura não nulo fica pendente: pode existir
instabilidade de giro sem momento de referência. Mistura q+P e P fora do meio
do vão não recebem estes coeficientes. A soma harmônica de críticos tabulados
não foi adotada, pois eles não são limites inferiores certificados do mesmo
operador. Isso é limite do ramo implementado, não proibição normativa do caso.

## Consumo, histórico e apresentação

A API `qualify_family(data, actions)` retorna somente Me e sua rastreabilidade;
`elastic_reference_eligible` identifica disponibilidade dessa referência.
O consumidor NBR deve chamar o próprio núcleo de resistência na tensão
reduzida, com a seção efetiva correspondente, sem importar Ml nominal nem
misturar fontes. Índices são comparações com a referência documental, não
aprovação de estabilidade física sob torção/bimomento ou flexão biaxial.

O solver histórico `ltb_load_height.py` e os snapshots anteriores não são
modificados. A nova referência tem schema próprio. O consumidor que a
incorpora deve versionar seu schema e preservar o replay da versão anterior.
`validate_saved` reconstrói coeficientes, alturas, material, contorno,
comprimentos, máximo físico e aritmética escalar; um hash recalculado não
valida adulterações.

## Fontes verificadas

1. ENV 1993-1-1:1992, Anexo F, F.1.2(2)-(5), F.2/F.4 e Tabela F.1.2.
   A URL do exemplar completo foi localizada em busca, porém no download
   atual devolveu página de estacionamento, não PDF. Não é usada como
   prova de bytes baixados:
   https://www.shining-solutions.com/wp-content/uploads/2024/10/DD-ENV-1993-1-1-1992-Steel-Design.pdf
2. Carlo A. Castiglioni, Politecnico di Milano, *Le Costruzioni di Acciaio e gli
   stati limite secondo le nuove NTC*, páginas PDF 47 e 50. Reprodução da
   fórmula e da tabela, conferidas visualmente no PDF público baixado:
   https://www.c430.it/pas/doc/edilizia/acciao-statilimite-ntc.pdf
3. Vermeylen et al., Eurosteel 2023, Eq. 1 e discussão de canais:
   https://orbi.uliege.be/bitstream/2268/306606/1/VermeylenMaxime-Eurosteel%202023.pdf
4. Sahraei et al., CSCE 2017, Eq. 2, potenciais separados de altura:
   https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf
5. NCCI SN003a-EN-EU, §3, apenas para contraste: seus coeficientes não
   autorizam o transporte automático a fatores não unitários:
   https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/SN003a-EN-EU.pdf

## QA

`tests/test_flt_height_effective.py`: referência decimal independente da
implementação, 66 contornos, material/altura/sinais, quatro combinações de
Ly/Lz, demanda física invariável, PP separado, torque normal/paralelo, nulos,
exclusões de distribuição, adulteração com rehash e ausência de solver.

`qa/flt_height_effective/generate.py` gera 264 referências sintéticas em 66
seções, quatro pares Ly/Lz. O caso ilustrativo Ue125×50×17×2 usa fy=300 MPa,
Lphysical=4100 mm, Ly=Lz=2050 mm, inclinação 5,71°, PP calculado da própria
massa no CG e ação externa uniforme no topo. Não contém projeto privado.

Resultado repetido nesta revisão: 110 testes passaram (novo módulo e regressões
de comprimentos), 264/264 referências calculadas no gerador. Não houve AppTest
nem solver matricial neste lote. A matriz não é certificado de todas as cargas
ou vínculos possíveis. O recibo identifica os hashes da fonte pública lida e
os testes efetivamente executados.

No caso ilustrativo da matriz, Msd=1,1443388197 kN·m é idêntico nos quatro pares.
Me é 3,7356231904 kN·m para Ly=Lz=2050 mm; 1,9203320212 para 2050/4100 mm;
2,3227597445 para 4100/2050 mm; 1,2397985028 para 4100/4100 mm. Esses números
não alteram o solver físico anterior, não incluem torção e não são aprovação.
