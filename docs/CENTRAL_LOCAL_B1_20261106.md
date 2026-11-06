# Amplificação flexional local B1 da central

## Entrega

Complemento separado da referência NBR das três travessas, somente para novas análises de escopo central. A revisão parte de 23dd0355e129c66d80b269fe18cd416c9fb0e9ad. Preserva a solução linear, os esforços físicos, os índices originais e os projetos antigos.

Por combinação ELU, calcula a compressão máxima da central, o Euler flexional de cada plano no vão integral e B1 = 1/(1 − Nc,max/Ne), com Cm=1. O B1 tem efeito: uma referência adicional de interação N/M usa os momentos amplificados. Não é somente um fator informativo.

A referência de barra usa dois ramos separados, quando presentes na mesma combinação: compressão uniforme equivalente Nc,max e tração uniforme equivalente Nt,max. Ambos retêm a posição e os sinais dos dois momentos, com o máximo da soma encontrado pelas raízes dos polinômios. A adoção dos máximos axiais espaciais é deliberadamente conservadora; essa referência não representa um estado físico concomitante resolvido da rede. Não mistura combinações. A resistência à tração ausente continua ausente; não é substituída automaticamente pela resistência da área bruta.

A saída aparece na interface, JSON e relatório Word. Continua sem aprovação global da rede ou interação com T/B.

## Base de referência

- NBR 8800:2008 D.2.2, páginas impressas 118–119: expressão B1=max[1;Cm/(1−NSd1/Ne)] e Cm=1 para forças transversais entre extremidades. https://engcivil20142.wordpress.com/wp-content/uploads/2018/03/nbr8800_2008_1.pdf
- NBR 8800:2024 C.2.2, páginas impressas 134–135; consultada em reprodução secundária: https://studylib.net/doc/28489089/nbr-8800--2024-
- NBR 14762:2010 8.1–8.2 e 9.9: análise estrutural e interação de barra. O axial é considerado constante na verificação de barra; não se afirma que a NBR prescreve expressamente esta extensão com Nc,max.
- AS 4100:2020 8.2, p.103: máximo axial na verificação da capacidade da barra e alternativa de primeira ordem amplificada. Seção 4.4.2.2, p.41: amplificação local cm/(1−N*/Nomb). Apoia a aproximação de força representativa máxima, não a aplicação integral da norma australiana ao Ue. https://sarah.com.au/wp-content/uploads/2024/09/4100_AS_2020_Steel_Structure.pdf
- Hancock, *Design of Cold-Formed Steel Structures*, 4ª edição, capítulo 8, 8.2, pp.166–167, eqs.(8.2) e (8.4)–(8.7): amplificação nos termos de momento da interação de perfis formados a frio, por Cm·M/(1−N*/Ne), com inércias brutas e comprimentos efetivos. Referência histórica baseada na AS/NZS4600:2005. https://www.steel.org.au/resources/elibrary/resources/cold-formed-members-in-combined-axial-compressive/?view=download

A versão inicial bloqueava aplicação quando N variava. Essa guarda foi removida: N variável, sozinho, não é proibição normativa encontrada. Também não é necessário exigir um majorante matemático ponto a ponto para usar uma fórmula aproximada de dimensionamento. O método e sua força axial equivalente são declarados, sem afirmar que os momentos aproximados são o equilíbrio de segunda ordem da rede.

Não se importa a dispensa N/Nc≤0,15 do livro, nem o limite de amplificação da AS4100. B1≤1,10 não é dispensa normativa automática. Não se aplica B1 novamente a uma solução que já contenha Pδ; o adaptador aceita exclusivamente a solução de primeira ordem declarada.

## Vínculos e limites mínimos

O software lê os vínculos salvos. K=1 resulta da referência isolada com translações extremas impedidas e rotações flexionais livres, no vão físico integral; não vem da posição dos tirantes. Não há crédito da telha ou dos tirantes como contenções intermediárias. O modelo usa seção prismática verificada. Força axial de todos os intervalos, inclusive os dois lados dos nós, entra no envelope.

Entradas inválidas, inventário incompleto, vínculos incompatíveis ou Nc,max≥Ne impedem o fator correspondente. Não se esconde denominador nulo ou negativo com max(1,...). A referência Kt=1, quando registrada, é separada e exige twist impedido e empenamento livre; não entra no B1 flexional.

Nenhuma resistência ou esbeltez de tirante, nem resistência de travessa extrema, é exigida por este complemento. A mecânica desses elementos permanece na solução da rede. Não foi criada exigência de certificado de campo ou dimensionamento das ligações para calcular a referência.

## O que ainda não se conclui

B1 modifica somente a flexão local. Não amplifica N físico, T, B, V ou reações. FLT e flexo-torção podem continuar nas resistências normativas de barra; não é obrigatório resolver esses modos de novo em um autovalor global, nem exigir GMNIA por existir torção.

A questão separada é a influência da geometria deformada sobre a transmissão de esforços das travessas extremas e dos tirantes para a central. Um segundo ciclo de cargas equivalentes pode estimar sua relevância usando a matriz elástica existente. A referência B1 central, por si só, não fornece esse número e não dispensa essa avaliação quando devida. Não se infere instabilidade pelo simples fato de algum tirante estar comprimido.

## Exemplo reproduzível

Entrada sintética Ue100x50x17, t=3,35 mm, L=4.000 mm, não projeto de Lucas. Nos 12 casos ELU, N varia ao longo da central. Em ELUN_00021: −300,384 N nos intervalos extremos e +600,767 N no intervalo intermediário. O menor Euler flexional é 28.918,904 N e B1 máx=1,010496 no plano fraco. Essa variação de N já não bloqueia o complemento local. O resultado pequeno não aprova a redistribuição global.

Há ainda um limite normativo já existente, independente de B1: nessa referência sem contenção intermediária, r fraco=18,169 mm e KL/r=220,153, acima de 200 da NBR14762:2010 9.7.4. O máximo vão para essa verificação com K=1 seria 3.633,844 mm. Isso não exige verificar os tirantes, mas impede declarar aprovada a referência NBR integral da central no exemplo de 4m. Reduzir o comprimento de flambagem exigiria justificar a contenção efetiva, não apenas contar os pontos de ligação. O limite de 200 não é importado para AS/EN e não bloqueia o cálculo do B1. Texto consultado da própria norma em reprodução pública, §9.7.4, página44: https://www.passeidireto.com/arquivo/200800732/nbr-14762-dimensionamento-de-estrutura-de-aco-constituidas-por-perfis-formados-a

## QA e publicação

Os testes específicos cobrem aritmética por plano, Nc≥Ne, dados inválidos, N variável, vínculos, vão integral, ramos axiais, não alteração dos índices originais e rejeição de snapshots alterados. Os resultados de execução e suas limitações ficam no recibo da entrega. Esta implementação não publica nem modifica o app online por si própria.

O registro QA completo está comprimido em gzip, sem perda de campos ou bytes do JSON original. Os hashes e tamanhos estão em `qa/CENTRAL_LOCAL_B1_PACKAGING_20261106.json`. `gzip -dc qa/CENTRAL_LOCAL_B1_20261106.json.gz` permite ler todo o JSON.
