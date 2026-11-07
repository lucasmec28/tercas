# Registro documental Ue Pierin

Recuperação do delta final f66fee após substituição do executor. Código/API/UI e testes foram reconstruídos a partir do texto dos comandos no histórico da tarefa, sobre a base recuperada fcd2671. O original não está disponível para comparação byte a byte. Não atribuir recibos anteriores automaticamente aos bytes reconstruídos.

## Contrato mantido

O registro deriva dos arquivos existentes; não duplica as83 linhas nem calcula seção/resistência. A tabela de auditoria contém todas as linhas, inclusive incompletas. Importações e leitores históricos não são alterados. O hook separado acrescenta comando explícito em app.py, ao final da página e ao final do modo de inspeção, depois dos controles históricos.

**83 Ue; 66 com dados tabulados completos; 17 incompletos.** Sete sem Ml (índices4,5,38,39,46,61,76); dez sem Ndist (68–75,77,78). Índices zero-based do catálogo, não linhas da planilha.

Campos mínimos da política: h,bf,lip,t; massa,A,Ix,Wx,Iy,J,Cw,ri; Nl,Ndist,Ml,Mdist,Mly; linha nominal Pierin exata e fontes. Os cinco críticos definem tabela completa; uma linha incompleta pode ter rota parcial disponível, mas não entra na seleção de novos estudos sob essa política. Não se inventam números nem se descarta a linha da auditoria.

G/nu/sentido desconhecidos da fonte, convenção geométrica não resolvida e falta de comprovação física não são ausência dos valores tabulados e não excluem linhas. Permanecem separados. Críticos Pierin de canto reto não são MRd e não são transferidos para contorno próprio arredondado. Dados tabulados completos não significam dimensionamento completo.

## API

- table(include_routes=True):83 registros, dados brutos, fontes, completude e rotas.
- inventory(): contagem e campos faltantes; sem autoridades por padrão.
- new_study_indices():66 índices completos.
- select_new_study(index): gate documental explícito; retorna descritor, não entrada/certificado/aprovação. NÃO cria ue_catalog_reference.

Provedores EN250/300 originais autenticam referências, vinculadas a geometria, material, contorno e sentidos. Nenhum gerador/solver é chamado. A tabela não substitui validação do consumidor nem disponibiliza denominador resistente. NBR próprio segue not_assessed_for_current_study, com referência aos provedores específicos. Falhas/ausência de autoridade são explícitas; rotas não solicitadas são not_requested.

## Interface e histórico

Novo estudo Ue usa66 opções, confirmação explícita, revalidação do gate e defaults+for_new_study+load existentes. Não herda ações/hipóteses/certificados. Avisa início em cobertura, modo direto, inclinação zero em graus, unidades padrão e PP novo. Importador e seletor histórico permanecem intactos; medidas genéricas antigas continuam legíveis, sem geração nova.

Apenas no clique de transição, preserva entradas, resultados/caches e rascunho durável de aço em histórico temporário de sessão. Não copia/restitui chaves de botões, uploads ou widgets. Restauração cria nova revision e reidrata o editor pelas entradas salvas, sem aplicar PP novo ao legado. O estudo substituído também fica preservado. Controles transitórios ainda não aplicados não são restaurados. Exportar antes de encerrar sessão; isto não é armazenamento persistente nem sistema novo de projetos.

Controles novos ao final preservam a ordem posicional dos antigos. Referências próprias ativas mantêm editor restrito: encerrar explicitamente o modo leva à inspeção, onde o comando novo fica disponível.

## Amostras

Índice26/Ue125x50x17x2: dados tabulados completos; fontes de propriedades/críticos separadas; Pierin com cantos retos, E200000, G/nu/sentido não explicitados; referências EN específicas sem aprovação global. Índice4/Ue50x25x10x2,65: Ml ausente, auditável e legível em históricos, excluído apenas de novos estudos.

## Testes e estado da recuperação

Antes da perda do executor:14 testes passaram em39,35s no hook5d945cb, recibo no f66fee:8 documentais e6 UI/transição, sem solver. Este é SOMENTE um fato histórico, não valida os bytes reconstruídos.

Recuperados tests/test_pierin_ue_registry.py e tests/test_ui_pierin_new_study.py: cobertura83/66/17, campos ausentes/conflitos, cópias, autoridades e material/sinal, proibição de geração, ordem do seletor histórico, criação explícita, preservação/restauração, importação incompleta e PP legado. **Ainda não executados após reconstrução**, aguardando dependências comuns e coordenação de CPU. Nenhum projeto privado lido. Nenhuma publicação.
