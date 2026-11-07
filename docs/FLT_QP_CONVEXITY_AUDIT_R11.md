# Auditoria de q + P central por convexidade, 07/11/2026

Base examinada: 70523d58fba2aa3593872de455bed01337a3ac15.
Resultado: a identidade de convexidade é válida, mas as referências individuais
existentes NÃO fornecem suas hipóteses. Não foi criada capacidade combinada,
novo C1/C2, módulo resistente, consumidor, apoio, mola ou alteração de solver.
O ramo documental q+P continua fora do método; o piso energético existente
continua sendo uma condição suficiente condicional, possivelmente inconclusiva.

## Teorema efetivamente demonstrável

Seja V um único espaço de perturbações admissíveis e K uma forma elástica
simétrica positiva definida nesse espaço. Sejam Gi formas simétricas para
padrões de carga completos, já com sinais, momentos e alturas reais incluídos.
Não se exige Gi positiva nem semidefinida. Para cada i, é necessário possuir
um número positivo ai tal que K-ai Gi seja semidefinida positiva em TODO V.

Para ti >= 0 e s = soma(ti/ai) <= 1:

K - soma(ti Gi) = (1-s)K + soma[(ti/ai)(K-ai Gi)].

Cada parcela do lado direito é semidefinida positiva. Se s<1, K positiva
definida dá positividade estrita. Em s=1 a conclusão é apenas não negatividade:
a fronteira pode ser a própria flambagem, não uma margem positiva de estabilidade.
A demonstração é direta e independe do sinal dos autovalores de Gi.

Se Gi já inclui a amplitude integral da ação de referência e todas as ações
são multiplicadas por lambda, o piso combinado é
lambda_D = 1 / soma(1/ai). Se a normalização é por carga unitária, as amplitudes
não negativas entram no numerador de cada parcela. Uma amplitude negativa deve
ser incorporada no Gi e qualificada de novo; não é peso negativo na convexidade.
Me_i / max|Mi| converte um momento crítico individual em multiplicador somente
quando o momento de referência individual é não nulo e representa aquele Gi.
Não se somam simplesmente recíprocos de momentos críticos com diferentes
normalizações. Se o momento resultante combinado é nulo mas resta potencial
de altura, não se fabrica Me=0 nem aprovação.

## O elo ausente, precisamente

É preciso provar, para cada referência de uniforme e P central, que

K(L físico, V, vínculos, E, G, contorno) - ai Gi(Mi(s), alturas) >= 0 em V,

com o MESMO K e V nos dois problemas. A referência ENV atual retorna uma
aproximação escalar: elastic_formula_is_approximate=True e
 guaranteed_elastic_lower_bound=False. Ter C1/C2 próprios, mesmo material,
mesma seção, mesmos valores declarados de Ly/Lz e diagramas corretamente
normalizados não fornece a desigualdade acima. Ela não nasce da igualdade
formal dos argumentos de uma fórmula.

Ly/Lz na expressão são fatores resistentes declarados, não especificação
completa de um espaço variacional e suas energias de vínculo. Os limites
Euler do piso energético são hipóteses explícitas de outro contrato; não
provam que os críticos ENV sejam pisos desse operador. Em particular, os
críticos do solver de garfo livre no vão integral não podem ser reescalados
para substituir a prova com Ly ou Lz reduzidos. Nem mesmo Ly=Lz=L elimina
por si só a ausência de certificação unilateral dos valores aproximados.

Dois caminhos legitimariam uma futura extensão: (a) referência especializada
que autorize expressamente a combinação q+P, alturas e fatores efetivos no
domínio usado, mantida como aproximação documental; ou (b) pisos individuais
certificados do mesmo operador, com erro/unilateralidade demonstrados e
vínculos explicitamente compatíveis. A identidade acima não cria o caminho
(a) nem certifica os dados necessários ao caminho (b).

## Fontes efetivamente conferidas

1. NBR 14762:2010, §9.8.2.2, p.48 impressa / p.54 PDF. Exemplar fornecido,
SHA256 c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407.
Página renderizada e lida nesta auditoria. A fórmula ali tem domínio CT ou
uso conservador em posição estabilizante; altura desestabilizante remete a
bibliografia especializada. Fatores de comprimento inferiores aos comprimentos
correspondentes também requerem justificativa bibliográfica. Esse texto não
prescreve soma harmônica de críticos aproximados nem certifica um operador.
2. Sahraei, Pezeshky e Mohareb (2017), Eq.2–3, p.3 PDF: energia de Vlasov
com potenciais de altura separados e problema K-lambda KG. Tabela1, p.4 PDF,
caso 12: C_EUR=1,365 versus C_FEA médio=1,362, razão publicada 1,002.
A comparação é evidência de que a tabela não oferece um limite inferior
unilateral; NÃO se apresenta o FEA médio como valor exato certificado nem
se transporta sua diferença para canais Pierin. A fonte não fecha q+P/Leff.
https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf
3. Vermeylen et al. (2023), §2.1/Eq.1: a referência considera condições de
carga, diagrama e restrições; não fornece certificado de convexidade para
q+P com os fatores independentes da aplicação.
https://orbi.uliege.be/bitstream/2268/306606/1/VermeylenMaxime-Eurosteel%202023.pdf
4. ENV 1993-1-1:1992, Anexo F: os coeficientes e sua reprodução por
Castiglioni já estão registrados em FLT_HEIGHT_EFFECTIVE_R11.md. O arquivo
local chamado env1993_1992.pdf é HTML, não exemplar primário; não foi tratado
como prova documental adicional. Não se extrapolou a reprodução para q+P.
https://www.c430.it/pas/doc/edilizia/acciao-statilimite-ntc.pdf

## Contraprova exata ao uso de aproximações

K=diag(1,1), G1=G2=diag(1,-1). Os Gi são indefinidos e os críticos positivos
exatos individuais são 1. Suponha aproximações ai=101/100, apenas 1% maiores.
Tomando t1=t2=101/200, soma(ti/ai)=1, mas
K-t1G1-t2G2=diag(-1/100,201/100), que NÃO é semidefinida positiva.
Não é um modelo de terça nem uma alegação de erro de 1% da ENV: demonstra
que aproximações sem erro unilateral provado não bastam para aplicar o teorema.
A identidade continua verdadeira, mas suas parcelas deixam de ser positivas.

O script qa/flt_qp_convexity/check_exact.py verifica por frações racionais a
identidade, indefinição de Gi, positividade interior, fronteira semidefinida
e a contraprova. Não executa solver, autovalores, UI ou projeto real.

## Decisão de implementação

Não adicionar soma harmônica ao flt_height_effective.py nem ao
nbr_family_member.py. Não alimentar flt_height_nbr_floor.py com a referência
aproximada combinada sob o rótulo de piso. Continuam preservados o vão físico
das solicitações, os comprimentos resistentes declarados, PP no CG, alturas
externas individuais, cancelamentos e as verificações de material/geometria.
Nenhuma falha de condição suficiente é transformada em reprovação física.
Esta investigação fecha a avaliação da proposta, não fecha a pendência FLT
de toda combinação q+P e não autoriza anunciar o aplicativo 100% concluído.

## Distinção normativa e busca complementar delimitada

A ausência de piso matemático NÃO invalida a aproximação documental uniforme
já adotada nem constitui proibição normativa de q+P. A NBR não exige que toda
referência especializada forneça certificado unilateral. A diferença numérica
de 0,2% da Tabela1 de Sahraei não é critério de rejeição dessa aproximação.
Ela apenas impede usar aquela comparação como prova de que seus valores são
pisos. Para uma nova aproximação combinada, o elo documental faltante é uma
fonte que prescreva/valide explicitamente a composição das referências
individuais, nas alturas, condições de vínculo e fatores efetivos adotados.

Duas consultas complementares buscaram FLT + Dunkerley + cargas uniforme e
pontual combinadas. Os resultados próximos foram:

- *Exact lateral–torsional buckling solutions for cantilevered beams subjected
  to intermediate and end transverse point loads* (2009): o resumo indexado
  trata domínio convexo e reta de Dunkerley, porém para tiras em balanço e
  cargas pontuais, não q+P central de canal biapoiado com Ly/Lz declarados.
  https://www.sciencedirect.com/science/article/abs/pii/S0263823109001761
- *Lateral–Torsional Buckling of Cantilever Steel Beams under 2 Types of Complex
  Loads* (2023): o resultado indexado inclui q+P e alturas individuais, mas o
  domínio é balanço, não a família/vínculos do ramo proposto.
  https://www.mdpi.com/2076-3417/13/10/5830
- *General formulation of equivalent moment factor for elastic lateral
  torsional buckling of slender rectangular sections and I-sections*:
  resumo indexado indica combinação de cargas com aplicação no CT e apoios
  de garfo, com possível impedimento de empenamento. Não documenta a
  combinação pedida com altura desestabilizante e fatores independentes.
  https://www.sciencedirect.com/science/article/abs/pii/S0141029619326331
  https://repository.tudelft.nl/file/File_063a66b5-2b44-4747-8054-5024822c26f9

As tentativas de abertura integral desses três candidatos retornaram,
respectivamente, 403, 429 e timeout. Os resumos indexados servem somente para
triagem de escopo, não como prova de conteúdo integral. Nenhuma fonte
aplicável para a regra combinada foi confirmada nesta busca delimitada;
não se afirma inexistência universal na literatura. A investigação para
neste elo específico, sem novo solver, sem alterar a aproximação existente
e sem exigir garantia matemática extra como condição normativa geral.
