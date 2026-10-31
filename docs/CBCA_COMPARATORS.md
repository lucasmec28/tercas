# Comparadores CBCA 2014 — etapas comuns (31/10/2026)

Fonte: Silva, Pierin e Silva, *Estruturas compostas por perfis formados a frio*, CBCA 2014. Ex.07–09, pp.62–71; S8 pp.164–170. PDF autoral acessível em https://www.jodi.com.br/wp-content/uploads/2021/01/Manual-CBCA-Estrutura-composta-por-perfis-formados-a-frio.pdf . Registro editorial oficial em https://www.cbca-acobrasil.org.br/site/biblioteca/ .

Este manual usa **MLE**, não MSE. Os 11 testes não validam dimensionamento integral: conferem funções existentes nas etapas comuns; resistências MLE fornecidas são apenas entradas de comparadores de interação. Nenhuma equação de produção foi modificada.

## Matriz
- Ex.07: Me elástico forte e redução FLT; Ue100×50×17×1,2, L4000mm, fy250MPa, Cb1. A idealização do comparador tem cargas no CT e vínculos de garfo; não constitui evidência de que qualquer ligação física realize esses vínculos.
- Ex.08: Me pelo Anexo E para o sentido alma comprimida, sem extensão ao outro sentido. Teste adicional exige `not_evaluated` quando faltam críticos MSE; não transforma módulos efetivos MLE em dados MSE.
- Ex.09: momento de P central, cortante resistente e interação M–V; P1500N **já de cálculo**. Não valida combinações da carga característica P1000N do app. Capacidade M0Rd195,45kNcm é entrada MLE fixa.
- S8: Cb para metade do vão sob carga uniforme; Anexo E; cortante; parcela biaxial da interação. Axial de1,2kN é acrescentado somente na conferência aritmética documental, fora da API N=0. Não declarar caso S8 integralmente implementado.

## Divergências preservadas
1. S8 Me: dados impressos da p168 resultam227,509543kNcm; p169 apresenta224,57kNcm. O teste verifica a expressão e exige que a divergência >1% permaneça sinalizada; teste aprovado NÃO significa concordância com o número impresso.
2. S8 altura plana: ri3,975mm e t2,65mm implicam111,75mm, mas cortante usa114,4mm. A reprodução de39,69kN usa o h impresso; não endossa consistência geométrica. O teste mantém a incompatibilidade explícita.
3. Valores de saída arredondados comparados por tolerância documentada de impressão, sem alteração de fórmulas para coincidir.

## Execução
`python -m unittest discover -s tests -p test_cbca_reference_stages.py -v`
Resultado em31/10/2026: **11 testes aprovados** em0,002s. Pytest ausente nesse interpretador; usado unittest, sem instalar dependência. Não publicado.
