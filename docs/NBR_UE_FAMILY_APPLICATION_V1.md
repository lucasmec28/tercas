# Aplicação NBR da família completa Ue

O limite de cálculo novo study_completion.complete_result anexa componentes NBR
para os66registros completos de Pierin quando o contorno nominal próprio foi
adotado. O pacote JSON é nbr_ue_family_application_v1. Abrir/importar resultado
antigo sem esse pacote não o acrescenta nem o reclassifica.

UI e Word apresentam cada ELU, fonte, método, eixo/sinal, resistência, momento,
índice parcial e pendência. Referência publicada (Wx de catálogo + Ml/Mdist
Pierin inalterados) e contorno próprio são alternativas separadas. Correspondência
nominal não prova contorno idêntico. Mly publicado sem sinal não fornece
resistência fraca. Local fraco negativo não equivale a negativo completo.

Classificação por parcela: -Fnormal*h e +Fparalela*x são contribuições à rigidez
rotacional. Não há compensação entre ações favoráveis e desfavoráveis. Sem esquema
ativo, posições externas são desconhecidas; PP permanece no CG próprio, uma vez.
Comprimentos resistentes afetam somente FLT clássico/Anexo E. Momento usa L físico,
extremos analíticos de cada trecho quadrático e testemunha concomitante Mx/My.
Índices parciais não são somados nem usados no panorama para aprovação global.

Altura histórica permanece separada e inalterada. Este pacote não reutiliza Me
salvo para emitir capacidade nova: o leitor legado autentica snapshot/domínio,
mas não prova independentemente o autovalor. Nova altura fica pendente, com L
físico e sem multiplicador Leff. Estender exige certificado numérico independente
ou reexecução explicitamente versionada do operador especializado.

O leitor novo reproduz fontes analíticas, contorno, inventário completo, ações e
extremos; compara integralmente o pacote. Não aceita capacidades/índices/omissões
adulterados após rehash. Não executa solver de flambagem nem altera dados salvos.
Fonte resistente é construída uma vez por resultado, não uma vez por caso/linha.
Word valida uma vez e percorre as linhas sem replays individuais.

Rede três travessas ativa/malformada, aplicação não purlin e schema não isolado
produzem apenas pendência, sem reconstruir solicitações N=0 nem produzir índices.
Ações axiais/componentes próprios da rede permanecem intocados. Não aprovação
global não substitui essa guarda mecânica.
