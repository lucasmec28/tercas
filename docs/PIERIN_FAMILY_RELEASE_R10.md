# Família Ue Pierin e comprimentos resistentes — R10

## Escopo

A entrada de novos estudos oferece as 66 linhas Ue com dimensões, propriedades publicadas e os cinco valores críticos documentais completos. As outras 17 linhas continuam auditáveis e legíveis em estudos anteriores. Seções genéricas e U simples não são ampliadas neste lote. Completude documental não significa dimensionamento completo.

Os métodos novos recebem índice, geometria, material e comprimentos como parâmetros. Não escolhem equações por um nome de perfil. O contorno próprio arredondado e a referência nominal publicada são fontes distintas: os críticos Pierin não são transferidos para o contorno próprio por igualdade de nome.

## Componentes implementadas

- EN: operadores normais puros por sinal, inclusive redução de alma no ramo qualificado, cortante nos dois eixos e interação seccional 6.27. Um operador normal indisponível não elimina o cortante independente calculável. As tensões combinam o campo original de torção/empenamento e os operadores compatíveis.
- Material EN: fyb=fya nominal declarado, E resistente 210000 MPa, nu 0,3 e gamma_M0=1 nesta versão. A rigidez E/G da análise não é alterada. O valor de fy não comprova conformidade de fabricação, produto ou ductilidade.
- NBR: componentes local e distorcional da referência nominal publicada, separadas das componentes calculadas no contorno próprio; FLT clássica e Anexo E dentro de seus domínios de seção, sinal e posição da carga.
- Testemunhas normais: um limite superior acima de 1 não é tratado automaticamente como falha. A busca reavalia pontos geométricos reais do mesmo campo com aritmética intervalar; somente um limite inferior estritamente maior que fy prova excesso naquele ponto. Controles interiores de Bernstein não são pontos físicos.
- Os resultados novos aparecem em JSON, tela e Word. Leituras validam a fonte, o inventário e a aritmética, sem novo solver de membro e sem aprovar globalmente o elemento.

## Comprimentos

L físico permanece nas solicitações, flechas e análise Vlasov. Lx, Ly e Lz resistentes são usados apenas nas fórmulas que os admitem. Declarações existentes de um único trecho físico integral podem ser consumidas sem criar apoios intermediários. A leitura de certificados antigos mantém sua própria política, sem substituição silenciosa de comprimentos.

A FLT com altura desestabilizante do solver anterior continua referida ao vão físico. Não se converte esse resultado multiplicando Me ou substituindo L por um comprimento resistente. A expressão clássica parametrizada exige coeficientes compatíveis com o diagrama, as alturas das parcelas e os fatores efetivos; esse domínio não está concluído para toda combinação q+P com alturas diferentes.

## Validação e limites

A matriz de aplicação sintética em `qa/recovery_current/EN_UE_FAMILY_APP_COVERAGE_20261106.json` percorre os 66 perfis no cenário declarado pelo gerador. A cobertura de um cenário não prova cobertura de todos os sinais, materiais, cargas ou condições de contorno.

Ramos locais/distorcionais EN ainda não implementados permanecem identificados como limitação do método disponível, não como proibição normativa da seção. Inaplicabilidade demonstrada e ausência de método são situações diferentes. As componentes não são somadas entre normas ou fontes para formar uma aprovação artificial.

A grande rotação de um modelo linear é um aviso de alcance da análise, não uma previsão qualificada da rotação física. Estabilidade global, serviço combinado, introdução de reações, ligações e conclusão completa permanecem fora da aprovação deste lote.

Os recibos da reconstrução identificam os ensaios realmente repetidos e separam resultados históricos. Os arquivos de teste e cobertura usam casos sintéticos; não contêm dados de projetos privados.

## Referências para o limite de FLT com altura

- Vermeylen et al., Eurosteel 2023, Eq. (1): https://orbi.uliege.be/bitstream/2268/306606/1/VermeylenMaxime-Eurosteel%202023.pdf
- NCCI SN003a-EN-EU, tabelas e curvas de C1/C2: https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/SN003a-EN-EU.pdf
- Sahraei et al., CSCE 2017, operador com cargas distribuídas/concentradas e suas alturas: https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf

Essas referências não autorizam transportar automaticamente os coeficientes de um caso com fatores unitários para fatores efetivos independentes e outras distribuições de carga. A limitação é dos coeficientes/domínio qualificados na implementação, não uma exigência universal de modelar apoios físicos intermediários.
