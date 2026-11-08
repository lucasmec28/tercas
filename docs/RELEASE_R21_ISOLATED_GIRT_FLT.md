# R21: aplicação das forças, travessa isolada e escopo de apoios

A emissão R21 integra a travessa isolada à família documental completa de
66 Ue, adota o modelo de aplicação solicitado para os cálculos novos e retira
a verificação local de apoio do escopo do aplicativo. Ela não ativa os 66
perfis na rede de três travessas e não representa homologação de um projeto.

## Aplicação das forças e preservação

Os novos cálculos apoiados pela interface registram a política versionada
`all_actions_at_shear_center_v1_20261108`. Todas as forças transversais
aplicadas, incluindo peso próprio do perfil e parcelas de peso das barras,
atuam no centro de torção. Não há seletor dessa política. Cargas, fatores
1,25/1,0 de peso próprio, estações de P, vão físico, comprimentos resistentes,
geometria, rigidez e apoios permanecem os mesmos.

Na rede, os braços e acoplamentos das conexões continuam físicos. A mudança
dos braços das forças externas não apaga torques internos transmitidos pelas
conexões excêntricas. No modelo isolado de garfos, a solicitação torsional
nula decorre das forças e das equações; não é um resultado sobrescrito.

Renderização, importação, restauração e exportação não migram resultados
históricos. A preparação ocorre na ação explícita de cálculo ou adoção de
um novo contorno, invalidando o resultado anterior. Os dados antigos mantêm
seus campos e a política com que foram calculados, inclusive linhas no topo
ou manuais; esses campos ficam inativos no novo modelo.

## Resistências e serviço

- NBR da família usa schemas novos para cobertura e travessa isolada. Me
  segue as expressões existentes para forças no CT, Cb=1 no eixo forte e
  comprimentos resistentes independentes. As rotas históricas de altura,
  ENV e pisos energéticos continuam disponíveis para replay, sem transferir
  suas hipóteses para as solicitações novas.
- A travessa isolada passa a consumir Vlasov, G8.1, componentes EN e NBR
  com sua identidade própria. Nenhum H4 ou crítico de outra seção é herdado.
- Flecha é somente a componente local solicitada: vertical local da terça
  e horizontal da travessa. Os 66 perfis dispõem de rota de serviço, 62 MSE
  e quatro MLE; continuam válidos os domínios seccionais e de tensão da lei.
- Os pisos FLT v2/v3 permanecem qualificados somente em seus contratos
  históricos. Não são somados e não modificam o vão físico.

## Apoios e lacunas de escopo

A verificação local de introdução da reação nos apoios fica fora do escopo
do aplicativo por decisão do usuário. O resultado registra essa decisão,
sem índice, aprovação do apoio ou dispensa normativa. Reações, vínculos e
geometria mecânica não mudam. Introdução de força concentrada no interior do
vão e cisalhamento da barra não foram removidos dessa forma.

A rede de três travessas conserva o escopo resistente anterior e a mecânica
das três barras; somente a central é alvo das verificações. Os candidatos
de operadores axiais e EN para ampliar a rede inteira à família não integram
esta emissão. Limitações de shear lag fora da dispensa, seções efetivas e
outras condições específicas continuam explícitas nos respectivos resultados;
nenhuma ausência de cálculo se transforma em aprovação.

## Verificação e rastreabilidade

A época de cache separa o cálculo ativo novo sem reescrever o histórico. O
recibo final distingue baterias autorais, integração, testes repetidos e
controles de falha histórica. Testes são sintéticos e não incluem dados de
projeto, documentos pessoais ou arquivos primários das normas. Testes de
software não demonstram as condições físicas executadas nem homologação.
