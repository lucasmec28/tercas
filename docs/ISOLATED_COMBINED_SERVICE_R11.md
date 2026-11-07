# ELS combinado da terça isolada: consumidor de campo denso

Complemento separável à preparação normativa R11. Fontes: ABNT NBR 14762:2010 §8.1, §9.8.5(a), §§9.2.2/9.2.3 e Anexo A, Tabela A.1 notas a/e/f/g. PDF primário conferido, SHA-256 `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`; o PDF não integra o repositório.

## Funcionalidade consumida

A opção visível **ELS combinado: deslocamento no ponto de serviço** permite selecionar ponto (CG, ponto da linha de carga no topo ou coordenadas), direção (vertical global, normal local ou vetor explícito), referência à corda dos extremos físicos e critério. As hipóteses e os resultados constam de tela, JSON e Word. Não é necessário digitar uma nova certificação ou origem textual para usar o modelo já declarado. Uma seção nominal própria já selecionada é reutilizada e mostrada como hipótese editável.

Dois critérios estão disponíveis:

- Tabela A.1: casos raros candidatos de mesmo sentido, limite L/180, e **caso suplementar separado de sucção característica isolada**, limite L/120, sem PP/CP. Ausência da fonte característica não é inferida como zero. Esse caso suplementar não altera combinações nem índices anteriores.
- Limite declarado para cada combinação ELS existente. Não infere decomposição de ações a partir de um total direto legado.

L é o vão físico integral. Leff permanece restrito às verificações resistentes. O ponto/critério não é inferido silenciosamente. Empoçamento e parcela/sequência construtiva continuam escolhas/avaliações do projeto conforme Anexo A; L/180 não é imposto a toda situação.

## Ramo suficiente da rigidez bruta

O crivo usa as tensões normais concomitantes Mx+My+B e a guarda elástica de V+Tsv+Tw do **mesmo caso, contorno, E/G e campo Vlasov**. Nas cinco paredes, compara a maior compressão limitada por Bernstein exterior com a condição uniforme suficiente de largura integral da MLE: alma AA, k=4; mesas e lábios AL, k=0,43, sem crédito do enrijecedor. Usa o limite inferior arredondado para fora de `(0,673 × 0,95)² k E (t/b)²`. Contorno, dimensões, cinco paredes e arcos são vinculados à referência própria, não ao nome nem aos sete pins antigos. As faces extremas e os arcos também passam pela guarda elástica de von Mises. Não há afirmação de estabilidade do membro a partir desse crivo.

Condição suficiente inconclusiva **não** é falha de serviço nem proibição do perfil. Nesse caso o campo bruto diagnóstico permanece, mas o índice de comparação é ausente. A implementação não soluciona, nesse ramo, uma seção efetiva iterada sob flexão biaxial e empenamento.

## Deslocamento simultâneo e envelope

A flexão tensorial Euler–Bernoulli é construída com as ações e o vão físico do mesmo caso. As parcelas uniformes são somadas como frações exatas dos números de entrada. A translação é referida ao centro de cisalhamento; acrescenta-se `phi × (P − SC)`, projetado na direção declarada, antes de procurar extremos. Subtrai-se a corda do **mesmo ponto**, incluindo os valores numéricos salvos nos extremos.

Cada trecho tem polinômio concomitante, não soma de máximos independentes. A subdivisão racional de Casteljau fornece limites inferior e superior do máximo absoluto. A testemunha é uma posição e valor no próprio campo. O limite superior ≤1 é suficiente para atender ao critério **nesse modelo linear**; limite inferior >1 demonstra excesso no mesmo modelo. Fronteira inconclusiva continua inconclusiva. Esses limites certificam o campo polinomial salvo, não seu erro de discretização nem uma rotação física finita.

## Integridade e retrospectividade

Cada resultado novo opt-in guarda a fonte densa relevante, a fonte compacta e seus vínculos. Na primeira leitura, o auditor aritmético compartilhado recompõe os polinômios e K·u−f a partir do vetor nodal salvo, **sem resolver K·u=f**. As reações de flexão são recompostas das cargas. O resumo deve coincidir integralmente com a fonte salva. O crivo e o envelope são reexecutados deterministicamente e devem coincidir com o resultado salvo. Cache limitado inclui todos os inputs, fontes e outputs: uma adulteração coerente com hash refeito não reutiliza validação anterior.

A leitura não recalcula membro, não cria resultados ausentes e não migra estudos antigos. A exportação Word e os rerenders usam a mesma evidência. O caso complementar de sucção é resolvido somente no novo cálculo opt-in, nunca ao abrir histórico.

## Limites de alcance

Nenhum limiar angular normativo foi criado. O alerta numérico de giro preexistente não é convertido em falha normativa automática. Os índices são condicionais à cinemática linear, e grandes valores de phi não são apresentados como rotação física qualificada. `combined_ELS_approved`, `physical_first_order_applicability_qualified` e `whole_member_approved` permanecem falsos. O consumidor não soma rigidez/travamento da telha, não dimensiona ligações completas e não impõe ensaio ou GMNIA universal.

A rota completa fica pendente quando: escolha de ponto/direção/critério ausente, campo denso próprio indisponível, condição suficiente de rigidez inconclusiva ou dados de avaliação aplicável ausentes. Falta de implementação é distinguida de inaplicabilidade. O inventário fixo continua independente dos outputs; listas vazias ou truncadas nunca concluem aprovação global.
