# Método da primeira emissão restrita

Base: lógica do app de terças Rev07, consolidada em 31/10/2026, e protocolos de cálculo revisados. A norma resistente é exclusivamente ABNT NBR 14762:2010. AISI e Anexo F não são rotas ativas. A telha não trava a terça.

## O que esta interface conecta

Um perfil de catálogo U/Ue, um vão isostático, q uniforme e uma força P em posição informada. Ações ELU/ELS já combinadas são entradas independentes. As ações não são copiadas entre ELU e ELS nem recebem fatores ocultos; peso próprio precisa estar incluído na combinação informada.

- Flexão local MSE, crítico Ml informado com origem para a seção correspondente.
- Distorcional: dispensa §9.3 para U aplicável; Tabela 14 para Ue no domínio; caso não dispensado recebe Mdist informado. Não gera Mdist automaticamente.
- FLT por trecho: Ly e Lz efetivos independentes informados e domínio explícito. Cb=1 ou momentos dos quartos do próprio trecho. Não deduz capacidade de um travamento físico da sua posição.
- Cortante da alma, sem enrijecedores transversais de cortante.
- Interação M–V com momento e cortante concomitantes da mesma combinação e posição da carga.
- Introdução localizada: subconjunto interno de compressão com contato informado; apoios por alma ligada no ramo §9.5.1. Ligação não dimensionada.
- ELS: componente de flexão Euler–Bernoulli, Ief(M) local, q/P de mesmo sentido. O pequeno excesso de Ig na expressão arredondada é limitado a Ig explicitamente. Aviso de integração numérica retira a conclusão ELS.
- Triagem de shear lag §9.4 visível. Quando insuficiente, não presume dispensa nem aplica redução não implementada.

## Catálogo e dados

Três entradas Tuper com campos publicados conferidos visualmente. Não é catálogo completo: material/resistências, raio, J e Cw não foram extraídos dessa fonte; são entradas complementares com origem. A diferença de convenção de Wx frente à planilha permanece informada. Não se certifica o material fornecido pelo fabricante.

Os dados sintéticos do botão didático são identificados no app, JSON e Word. O caso reprova FLT. Não usar como projeto.

## Estados e rastreabilidade

Cada verificação pode retornar calculada, não atende, não aplicável ou não avaliada. Não há aprovação global automática. Ausência de propriedade ou geometria fora do domínio afeta o ramo correspondente. Alteração de entradas elimina resultado/exportação anterior. JSON contém snapshot, versão e SHA256 das entradas. A origem de cada edição fica na memória.

## Limitações de implementação

Esta primeira emissão não calcula torção primária, flexão biaxial, axial, balanços, continuidade, deformação do sistema de cobertura, capacidade dos travamentos/apoios, contato próximo ao apoio ou todas as combinações automaticamente. São limites do programa, não proibições adicionais da NBR. Me só se aplica ao domínio declarado. Resultados de resistência individuais não dispensam aspectos não cobertos.

## Verificação

Testes unitários, regressão AppTest e comparações aritméticas independentes estão documentados no relatório da candidata. Isso não equivale a ensaio físico, validação universal ou conferência de projeto. Nenhum teste externo de outro método foi imposto como exigência normativa.
