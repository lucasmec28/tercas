# LRO — Terças (emissão restrita — 0.4.4-estudo)

Aplicativo Streamlit para verificações parciais de um vão U/Ue, segundo o método documentado na Rev07 e NBR 14762:2010. **Não considera telha como travamento e não emite aprovação global.**

## Executar

Python 3.12. `pip install -r requirements.txt`; `streamlit run app.py`.
No Streamlit Community Cloud: repositório `lucasmec28/tercas`, branch escolhida, arquivo `app.py`.

## Escopo e entradas

- Eixos X horizontal/forte e Y vertical/fraco; duas entradas: q+P já combinados (ELU/ELS separados) ou cargas por área, distância entre terças e PP automático.
- Modo área: matriz fixa de 48 combinações fornecida por Lucas, mais combinações próprias de P nas famílias aplicáveis (4 ELU e 1 ELS rara), cada uma em duas posições, filtrável em quatro famílias; cada caso recalculado, sem somar índices ou flechas de diferentes inércias efetivas.
- Aços predefinidos e personalizado; comprimentos efetivos Lx, Ly superior/inferior e Lz agrupados. Troca de perfil preserva dados de projeto, não críticos manuais de outra seção.
- Catálogo: 209 perfis U/Ue da planilha V03 fornecida por Lucas, com rastreabilidade Pierin/DimPerfil. Dados ausentes (material, raio, J, Cw, críticos) não são inventados. Origem de valores informados fica no relatório.
- FLT por trechos com Ly/Lz informados; a hipótese de domínio da expressão deve corresponder ao modelo físico. Tirantes não implicam automaticamente restrição de torção.
- Local/MSE, distorcional quando aplicável, cortante, interação M–V, ELS de flexão.
- Eixo fraco: rota Anexo E e interação biaxial §9.9 conforme dados por sentido; hipóteses provisórias e ramos parciais permanecem explícitos.
- Comparação explícita do catálogo por massa, utilização e pendências; progresso/cancelamento entre perfis. Não é porcentagem de aprovação.
- Desenho com combinação selecionável e P visível nos casos aplicáveis; P automática em duas posições prescritas: centro e limite junto ao apoio, sem varredura intermediária. FLT e interação cobrem essas posições, não certificam máximo contínuo.
- Geometria fora do subconjunto ou dados ausentes geram estado parcial, não aprovação.
- Exemplo didático é explicitamente sintético; não é produto qualificado nem projeto.

## Não incluído

Projeto de ligações, torção primária, interação axial, balanços/continuidade, análise física automática de travamentos, geração automática de Mdist e geração normativa genérica de combinações. Flecha paralela à cobertura foi retirada da lista e fica fora do escopo desta emissão. Os limites são da implementação, não novas exigências da norma.

## Testes

`python -m pytest -q` (inclui regressões de interface e testes aritméticos).

Status: emissão restrita 0.4.4. Suíte ampliada de testes automatizados incluída; houve revisão independente e comparações aritméticas. Implantação e navegador online ainda precisam de conferência. Testes não equivalem a validação experimental ou aprovação de projeto.


## Terça / Travessa — 03/11/2026, escopo restrito

A seleção **Travessa lateral** orienta U/Ue com boca para baixo: peso/permanentes no eixo fraco vertical e vento no forte horizontal. Mantém a Terça legada. Inclinação e SC de cobertura são preservadas, mas inativas na travessa; o subconjunto por área usa 19 combinações sem SC/P de cobertura antes dos filtros. Não é dispensa universal de ações nem gerador normativo genérico.

O estudo opcional de tirantes usa posições e rigidezes finitas declaradas, molas verticais em tração e ancoragem fixa assumida. Não fornece rigidez por padrão, não divide o vão, não altera FLT ou resistência. A flecha vertical com **Iy bruto** é apenas diagnóstico, sem índice de aprovação ELS; momento negativo e levantamento podem ocorrer e são reportados. L do modelo, Lref do critério e comprimentos de FLT são separados. As escolhas editáveis L/120 e L/180 são referências históricas declaradas, não atualização normativa automática.

Veja `docs/RELEASE_TRAVESSA_20261103.txt` para hipóteses, fontes, exemplos, QA e limites. O identificador 0.4.4 do núcleo foi preservado para permitir comparação exata das saídas legadas; esta candidata é identificada pelo manifesto de 03/11/2026. Nenhuma resistência fraca nova foi liberada e nenhum dado R04 foi transposto ao projeto.

## Cópia com diagnóstico de três travessas em 3D

Opt-in na Travessa lateral: três travessas contínuas e barras axiais bilaterais de
primeira ordem. Solicitações simultâneas, reações, N, torção Saint-Venant e flechas
brutas; **sem resistência, sem conclusão ELS e sem aprovação global**. Não reutiliza
a rota N=0, não presume empenamento impedido ou ancoragem comprovada. Mantém todos
os projetos antigos no caminho anterior; detalhes em
`docs/THREE_GIRTS_DIAGNOSTIC_20261103.txt`. Cópia em qualificação, sem deploy inferido.

## Hipótese fixa da telha no modelo — 03/11/2026

Nesta idealização, não há contato da telha/painel com o perfil nem ligação de
qualquer mesa a painel. A telha entra somente nas ações declaradas, sem travamento,
apoio, contenção ou rigidez. Isso não comprova a condição física externa, não
estabelece caminho das forças e não implica torção nula. Legados são aceitos sem
novos campos obrigatórios; a hipótese e sua origem são registradas nos resultados
e na memória. Exportação de entradas acrescenta apenas um token de domínio em
cópia. Declaração física explícita incompatível é preservada e marcada fora do
domínio. Detalhes em `docs/NO_PANEL_MODEL_DOMAIN_20261103.txt`. Não publicado.

## Referências próprias homogêneas — cópia controlada de 03/11/2026

Carregador explícito de U100/U125/U150 nominais arredondados, com propriedades
próprias e FSM própria, para os casos sintéticos 0/±5 graus. Importações manuais
legadas continuam em inspeção até opt-in explícito. Um marcador só reabre o editor
restrito quando o vetor físico, origens e domínios integrais conferem novamente.
No modo fixo, seção/material/críticos/vínculos e L=3000 mm permanecem congelados;
somente ações sintéticas e identificação podem ser editadas. Não há comparação genérica do
catálogo neste modo, extrapolação de Nex/Nez, crédito da telha ou aprovação global.
A flecha forte usa Ief uniaxial, sem qualificação de Ief combinado/ELS biaxial.
Veja docs/HOMOGENEOUS_REFERENCE_UI_20261103.txt. Integração local sobre c26a5bf, com rastreabilidade M–V corrigida preservada.
Esta nova candidata não foi publicada; não altera as verificações resistentes.

## Extensão explícita de vão e comprimentos — cópia de 03/11/2026

As mesmas referências próprias podem ativar separadamente um único vão inteiro
editável, com Lx=Ly=Lz=L ou distâncias efetivas declaradas (K=1, Ly comum). Ne e
Mcr são recalculados das propriedades próprias congeladas; nenhum vínculo ou
rigidez de tirante é inferido. Comprimentos distintos são aplicação algébrica,
não comprovação de um arranjo físico de contraventamento.

Prévia/Aplicar preservam P absoluto e mostram os critérios ELS atualizados.
Rascunhos pendentes retiram resultados anteriores. JSON alterado não é reparado
silenciosamente; Word histórico usa a evidência gravada. O modo fixo de 3 m e o
fluxo legado são preservados. Veja docs/HOMOGENEOUS_LENGTHS_20261103.txt e o ajuste
isolado de quadratura em docs/IEF_TRANSITION_QUADRATURE_20261103.txt.
Esta candidata permanece local, sem publicação ou aprovação global.

## Referência própria Ue100 — opt-in restrito de 03/11/2026

O carregador **Carregar referência própria Ue100** abre um estudo sintético próprio
R01, Ue100×50×17×1,20, ri=1,20 mm, com 209 nós. Pierin seleciona somente a
correspondência nominal; nenhum crítico nem sentido histórico de Pierin é usado.
As fontes e decisões necessárias ao consumo estão incorporadas, com SHA-256,
em pacote autossuficiente. Não há importação da árvore externa de pesquisa.

Vão contínuo de 3000 a 6000 mm, inclusive, com Lx=Ly=Lz=L e K=Cb=Cm=1. A edição
de vão exige prévia e aplicação explícitas, recalcula Ne/Me/FLT e preserva a
posição absoluta de P direto. Não há comprimentos independentes, segmentação,
crédito de painel, migração automática de catálogo nem comparação de seções.
Ações, inclinação e identificação podem ser editadas. Fontes, propriedades,
material, sentidos e demais condições físicas são conferidos integralmente.
Alterações incompatíveis abrem inspeção não destrutiva, sem reparo silencioso.

Alma comprimida: o valor 850000 Nmm na entrada D legada é um **piso elástico
conservador**, não Mdist identificado nem dispensa distorcional. Lábios comprimidos:
Mdist próprio identificado de 1668845,1785399402 Nmm. A dispensa da Tabela 14 é
somente do eixo forte. Fonte e distinção constam da interface, JSON e Word.

ELS forte uniaxial mantém o critério parcial apenas quando as componentes locais
reais q e P paralelas do estado são ambas zero, preservadas as demais guardas.
Solicitação biaxial mantém valores escalares diagnósticos e fica pendente por
rigidez efetiva combinada, sem índice de atendimento. Não se transfere por ID a
evidência MLE de 34 estados específicos de 4 m. Não há linhas novas de flecha ou
cortante paralelo. A hipótese fixa continua telha sem contato/contribuição,
somente carga. Sem aprovação global, física, de ELS completo, torção ou 3D.

Detalhes: `docs/UE_REFERENCE_INTEGRATION_20261103.txt`. Integração local, sem
publicação. Caminhos anteriores U, Travessa e diagnóstico 3D preservados.
