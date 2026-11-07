> Nota de evolução R11: este documento registra a preparação normativa inicial. O cálculo combinado e o envelope contínuo foram depois implementados em `ISOLATED_COMBINED_SERVICE_R11.md`; a projeção dos resultados e seus limites está em `ISOLATED_SERVICE_PANORAMA_R11.md`. As referências a integração futura abaixo descrevem aquele primeiro corte, não ausência atual do cálculo.

# Serviço e fechamento da terça isolada — R11

## Resultado e escopo

Esta revisão corrige uma dispensa excessiva, prepara critérios reais de serviço e torna explícito o inventário de fechamento. Não conclui o dimensionamento integral nem altera a matriz de combinações fornecida, a resposta de membro, os ramos resistentes ou o histórico. Não há cálculo pesado novo.

1. Cargas paralelas nulas dispensam a parcela de flexão fraca, mas **não** demonstram torque ou deslocamento torsional nulos. `combined_ELS_scope` agora permanece pendente nesse caso. O contraexemplo escalar usa `q=(0,-0,1) N/mm`, linha no topo `x=0` e CT em `x=-18 mm`: torque no CT = −1,8 N apesar da carga paralela nula.
2. Um novo cálculo salva um inventário independente de 19 tópicos. Sua lista não é obtida dos resultados que por acaso existem. Ausência, limitação de implementação, dispensa documentada do domínio N=0 e itens externos ao dimensionamento do perfil são estados diferentes. O inventário não alimenta uma soma de índices nem um novo atalho de aprovação.
3. A preparação de serviço identifica os critérios da Tabela A.1 e a lacuna específica da sucção característica isolada, sem calcular deslocamento novo ou adulterar uma combinação do usuário.
4. Uma função escalar de cinemática permite transformar deslocamentos e rotação **concomitantes** para um ponto e uma direção de serviço, relativamente à corda dos extremos do mesmo ponto. Ela não qualifica, por si só, a rigidez, o máximo contínuo, a validade da primeira ordem ou ELS.

`whole_member_approved`, `combined_ELS_approved` e `normative_design_complete` permanecem falsos. Cumprir verificações listadas de normas/fontes diferentes não cria uma aprovação NBR conjunta.

## Fonte primária conferida

Cópia da ABNT NBR14762:2010 fornecida pelo usuário, SHA256 `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`. O PDF não é incluído no repositório.

Leitura visual nesta revisão:

- §8.1–8.2: p.24 impressa / PDF30. Exige modelo representativo e deformações de todos os esforços relevantes, com procedimento de análise remetido à NBR8800. §8.2 permite método de comprimentos efetivos para barras isoladas. Isso não determina que Leff substitua o vão físico do solver nem exige GMNIA universal.
- §9.8.5: pp.51–52 / PDF57–58. Redução de rigidez associada à flambagem local por Ief, via MLE com tensão normal de compressão das combinações de serviço ou MSE no domínio descrito. A lei escalar MSE não fornece, por si, tensor de rigidez geral de flexão biaxial com bimomento.
- Anexo A: pp.69–71 / PDF75–77. A.2.2 trata de possíveis deformações plásticas e da rigidez rotacional das ligações conforme avaliação do projeto. A.2.4 e A.3.3 distinguem combinações, parcelas do deslocamento, função e sequência construtiva. A.3.2 limita a dedução de contraflecha ao deslocamento das ações permanentes.
- Tabela A.1, terça de cobertura: L/180 com nota e; L/120 com nota f. Nota a define L como vão teórico entre apoios (ou duas vezes o balanço, não aplicável ao modelo biapoiado atual). Nota g requer evitar empoçamento, com atenção especial à pequena declividade.

## Critérios de serviço preparados

### Mesmo sentido da permanente

L/180 corresponde à nota e: combinações raras de serviço com variáveis de mesmo sentido que a permanente. O planejador lista combinações raras candidatas da matriz salva com PP=CP=1 e sem sucção. Isso **não** certifica todos os fatores de combinação ou escolhe a parcela de deslocamento de A.3.3 automaticamente.

### Sentido oposto à permanente

L/120 corresponde à nota f: somente ações variáveis de sentido oposto, sucção com valor característico. Uma combinação rara/frequente cujo resultado líquido seja ascendente, mas inclua PP/CP, não substitui esse caso. A matriz fixa atual exige PP/CP em todas as suas combinações.

A preparação lê o vetor característico `case_vectors_N_mm.V_Cima` já salvo, incluindo os dois eixos, e cria apenas um registro de ações para cálculo posterior. Não soma PP, não inclui CP, não reaplica inclinação e não calcula resistência ou flecha. Carga de sucção explicitamente zero é diferente de vetor ausente. Não se decompõem cargas diretas combinadas sem os dados correspondentes.

O limite deve ser aplicado ao ponto, direção e parcela realmente adotados. Não se promove a flecha local normal de cobertura inclinada a vertical global, nem a resultante dos dois eixos a critério por direção. Critérios mais rigorosos podem ser necessários para uso, acabamentos e drenagem. Não se inventa limite angular de serviço.

## Método simples para deslocamentos relevantes

No mesmo campo linear, em eixos transversais x,y com phi positivo pela regra da mão direita ao longo da barra, seja O a linha de referência dos deslocamentos e P um ponto de serviço com offset indeformado `(rx,ry)`:

- `ux_P = ux_O − ry phi`;
- `uy_P = uy_O + rx phi`;
- a corda de P é a interpolação dos deslocamentos de P nos dois extremos declarados;
- a componente relevante é a projeção unitária do deslocamento relativo àquela corda.

Se o deslocamento é referido ao CT, o offset é CT→P. Se é referido ao CG, o offset é CG→P. Não se usam os dois simultaneamente. O helper exige identidade comum de combinação, barra, seção, análise, rigidez, sistema de coordenadas e linha de referência. Os estados extremos têm as mesmas identidades; não se subtraem deslocamentos de pontos diferentes.

Não se somam máximos de ux, uy ou phi obtidos em posições distintas. O helper verifica somente a estação fornecida e não prova um envelope de vão. Sua razão diagnóstica não é índice ELS e nunca muda para falha normativa por phi grande ou razão maior que 1. Usar seno/cosseno sobre phi linear não corrigiria a validade física da análise.

Para integração futura do serviço combinado, a sequência mínima é:

1. Definir as ações/famílias, ponto, direção, parcelas e corda corretos, incluindo o caso da nota f e drenagem.
2. Obter um único campo de deslocamentos/torção compatível com as mesmas propriedades e hipóteses de serviço. MLE ou prova suficiente de integralidade pode simplificar o ramo aplicável. Não basta juntar flecha de Ief uniaxial e rotação bruta de outro campo.
3. Qualificar o domínio da análise, conforme §8.1. O aviso computacional de giro não é um limite normativo. Sua ausência também não demonstra validade da primeira ordem.
4. Recuperar e combinar no mesmo ponto antes de procurar o extremo contínuo. Qualificar numericamente o envelope e comparar somente com o critério aplicável.

Não se impõe um suposto certificado universal de GJef/Cwef nem ensaio obrigatório para toda seção. A rota material/rigidez adotada deve ser tecnicamente compatível e documentada; os limites atuais são da implementação validada.

## Inventário e dados mínimos

O JSON registra separadamente: ações; seção/material; aplicabilidade da análise; flambagem local; distorcional; FLT; cortantes; M–V; biaxial; torção/empenamento; escopo axial; introdução de P; alma nas reações; vínculos; rigidez de serviço; deslocamentos combinados; limites/parcelas; empoçamento; ligações completas.

### Apoios e transferência de reações

A hipótese de garfo com empenamento livre define a análise, mas não define o detalhe de transferência local. P externa nula não exclui as reações. O módulo local existente permite:

- Alma ligada a viga ou pilar, com origem da declaração: registra a exceção de enrijecedor de §9.5.1, sem pedir comprimento de solda ou certificado inexistente.
- Contato por mesa: exige c real, distância livre ao extremo físico, mesa conectada ou não, ausência/presença da força oposta e sua distância quando existir, sentido compressivo e orientação do detalhe. Deve respeitar o domínio geométrico/material tabulado.
- Inversão da reação não muda automaticamente a mesa comprimida nem aprova ancoragem para sucção.

A resistência local de alma não é a resistência completa da ligação. Para dimensionar ligação completa são indispensáveis o arranjo escolhido, geometria e materiais de chapas/elementos, fixadores ou soldas, distâncias e ações de transferência relevantes. Não se presume nenhum desses detalhes. A ligação completa permanece fora do dimensionamento do perfil nesta entrega, mas sua necessidade não é tratada como inaplicabilidade normativa.

### Ausência versus inaplicabilidade

- Sem dado/método/resultado qualificado: pendência ou componente não consolidada, não resistência zero e não dispensa.
- Ação explicitamente nula: dispensa apenas o mecanismo demonstrado por essa nulidade.
- N=0: domínio declarado do vão isolado, não capacidade axial fictícia requerida.
- Limite matemático P→apoio: não constitui detalhe físico de contato.
- Telha sem crédito de rigidez/travamento: não exige verificar um travamento que não foi creditado.
- Falta de roteiro para outro ramo EN/NBR: limitação implementacional, não proibição normativa do perfil.

## Preservação e validação

`completion_requirements.attach` é chamado ao final de `complete_result`, apenas após novo cálculo. O leitor não cria snapshot ausente, não consulta fontes vivas e não resolve membro. Ele confere hash, inventário fixo, vínculos, regras e aritmética da preparação salvos. Flags de aprovação, exclusões indevidas, supressão/duplicação de requisitos ou adulteração do caso de sucção são recusadas mesmo se o hash for refeito.

UI e Word consomem o mesmo snapshot. Nenhum resultado histórico é recalculado ao abrir/exportar. Os números anteriores e os componentes separados permanecem disponíveis. Os testes desta entrega são escalares/sintéticos e de contrato, sem nova matriz de membro nem validação física integral das 66 seções.
