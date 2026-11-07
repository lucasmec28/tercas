# Seções efetivas EN da família Ue Pierin: extensão R11

## Escopo e separação de fontes

O método é parametrizado por geometria, material e sinal. Não escolhe equações por nome de perfil. As 66 linhas completas do inventário nominal continuam sendo a entrada documental. A integração é feita no contorno próprio arredondado de 32 cordas por canto. Nenhum crítico Pierin, módulo publicado ou resistência NBR é transferido para esse contorno.

E resistente = 210000 MPa, nu = 0,3, fyb = fya nominal declarado e gammaM0 = 1. A análise original conserva E/G, solicitações, torção e empenamento. Todos os sinalizadores de aprovação global continuam falsos. Conformidade do produto, estabilidade de barra, segunda ordem, ligações, introdução local de forças e serviço combinado não são certificados por esta extensão.

## Operadores novos

Os operadores R10 que já eram elegíveis são mantidos exatamente. Apenas os ramos antes bloqueados usam a extensão.

### Mx positivo/negativo e My positivo

1. As mesas usam o psi da seção bruta permitido por EN 1993-1-3 §5.5.2(3). As larguras e a posição de suas faixas seguem EN 1993-1-5 Tabela 4.1, mantendo a região tracionada. Lábios comprimidos seguem EN13 Eq.5.13, com a largura efetiva retida desde a raiz.
2. Cada As físico contém o lábio efetivo e somente a faixa de mesa adjacente. Área, centroide e Is são integrados nas próprias facetas arredondadas. K, tensão crítica e chi_d seguem EN13 Eq.5.10b, 5.15 e 5.12. A montagem oposta só pode fornecer kr=0 se permanecer toda tracionada no campo final.
3. Adota-se t_red = chi_d*t apenas nos intervalos disjuntos de As. O refinamento opcional do passo 3 e o aumento favorável de área da Eq.5.17 são omitidos. Isso não elimina a redução distorcional. O campo final comprova As comprimido e chi_d <= min(1,chi_d*fyb/sigma_As), com sigma_As no centroide físico do enrijecedor. A razão efetivamente aplicada e a razão máxima permitida são guardadas separadamente.
4. A alma começa com mesas efetivas e alma bruta. Seu psi é refinado com a seção efetiva até residual inferior a 1e-13, com pelo menos duas atualizações. O relatório não chama essa convergência de prova intervalar de unicidade.
5. A inversão completa Ix/Iy/Ixy fornece c0/cx/cy sobre o centroide bruto. N=0 e o momento transversal nulo são conferidos por quadratura independente. Não se substitui a tensão por M/W absoluto. O esforço puro é normalizado nas duas faces de todo o contorno original, não somente nas faixas retidas. O piso resistente continua usando aritmética externa dirigida.

### My negativo

A alma mantém a solução Eq.4.4/Nota 1 com contrato de contração já existente. Quando o majorante de mesa psi=0 era insuficiente, buscam-se majorantes assinados da última orientação da Tabela 4.2: bordo apoiado comprimido, bordo livre tracionado, psi em [-1,0]. A amplitude é obtida pelas inequações de dominância em todos os vértices de linha e das duas faces, incluindo os valores negativos. O arredondamento da amplitude para cima não é aceito se violar qualquer limite de dominância na região tracionada.

O passo de busca de psi=0,05 apenas seleciona um majorante comprovado. Não constitui uma proibição normativa quando nenhum é encontrado. A mesa só permanece integral quando lambda_red <=0,748 e rho=1, com o lábio todo não comprimido. Não se atribui rigidez ou estabilização de lábio à mesa. Todos os 66 casos dos quatro materiais encontrados satisfizeram esse teste; não foi necessário recortar mesas do ramo My negativo.

## Fontes verificadas

- EN 1993-1-3:2006, incorporando corrigendum 2009, §§5.5.2(3), 5.5.3.1–5.5.3.2 e 6.1.4.1: https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf (páginas PDF 26 e 28–32).
- EN 1993-1-5:2006, incorporando corrigendum 2009, §§4.3–4.4 e Tabelas 4.1–4.2: https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.5.2006.pdf (páginas PDF 14–18).

O alcance continua sendo o modelo simplificado de enrijecedor-coluna. Não é uma análise de autovalores de modos acoplados com translação das junções.

## Histórico, vínculo técnico e testes

O método R10 e suas dependências relevantes foram preservados sem alteração em um pacote somente de leitura histórica. O verificador despacha pela revisão, reconstitui o resultado pelo método original e exige igualdade completa, incluindo o binding técnico original. Um histórico R10 com ramo bloqueado continua bloqueado; não é promovido por abrir na versão nova. Adulterações com hash externo refeito continuam rejeitadas.

A fonte do novo operador faz parte da identidade técnica do provider. Cache transitório não é autoridade. JSON, UI e Word continuam consumindo os operadores/snapshots autenticados sem resolver novamente o membro. A cobertura seccional completa não implica que todos os cenários de aplicação superem suas próprias guardas, shear lag ou outras verificações.

A matriz sintética `qa/en_ue_reductions_r11/material_coverage.json.gz` registra o antes/depois por linha, sinal e material, os métodos usados e o tempo por construção. Os testes incluem integração independente de As/Is, fórmulas K/chi_d, equilíbrio dos operadores, domínio das faces, partição sem sobreposição, dominância assinada dos majorantes, regressão dos operadores R10 já elegíveis e replay legado adulterado. Não há projetos privados nem publicação neste lote.

## Cobertura e execução sintética deste lote

| fy (MPa) | Mx+/Mx− antes | My+ antes | My− antes | Depois, cada sinal | Cortante antes/depois |
|---:|---:|---:|---:|---:|---:|
| 250 | 49/49 | 61 | 48 | 66/66 | 66/66 |
| 300 | 44/44 | 54 | 40 | 66/66 | 66/66 |
| 345 | 38/38 | 50 | 36 | 66/66 | 66/66 |
| 350 | 35/35 | 49 | 36 | 66/66 | 66/66 |

A construção fria dos quatro operadores e cortante custa, neste executor, em média 0,20–0,32 s por seção/material; máximo observado de 1,08 s. Isso não inclui solver de membro. As 264 seções possuem 1056 operadores de momento disponíveis, sem lacuna local/distorcional no domínio sintético declarado.

Foi removido no método novo o limite inferior artificial 0,2 para a razão nocional bp,c/bp. A Eq.5.13 aceita 0 < bp,c/bp <= 0,6; a razão externa c/b da Eq.5.2 permanece uma verificação separada. O método R10 histórico conserva suas regras originais.

A função `audit_effective_state` recalcula um estado de faixas/espessuras fornecido, rejeita partições inválidas/sobrepostas e devolve tensor, centroide, campo, faixas de alma requeridas e limites Eq.5.17. Ela não concede qualificação: uma extensão suplementar deve justificar seus fatores e fechar sua própria iteração. Não há implementação de shear lag implícita nessa função.
