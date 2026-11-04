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

## Família própria Ue100 — seis espessuras, 03/11/2026

O novo carregador **Carregar família própria Ue100** oferece 1,50 / 2,00 / 2,25 /
2,65 / 3,00 / 3,35 mm. São referências próprias R01 de 209 nós, ri=t, com
propriedades e críticos individuais. A rota anterior de 1,20 mm permanece
separada e os projetos antigos não são migrados automaticamente.

Dentro da referência ativa, a prévia conjunta de seção e vão permite trocar
espessura e L entre 3000 e 6000 mm, preservando ações e a posição absoluta de P.
Aplicar reconstrói o vetor completo da nova identidade, incluindo PP, críticos,
Ne/Me e fontes. Nenhum piso ou crítico é escalado de outra espessura. Uma proposta
não aplicada retira resultados e bloqueia cálculo até aplicar ou descartar.

As seis incluem D forte próprio, sem dispensa da Tabela 14. D da alma permanece
não identificado; o valor consumido é o piso elástico discreto individual, com
prova conservadora escalar delimitada. Locais e D dos lábios são próprios por
sentido. A matriz existente de combinações e as duas posições de P permanecem.

O pacote de fontes em `tercas/data/ue_family` é autossuficiente e verificado por
hashes. O marcador não basta: valores protegidos, fontes, material, vínculos e
sentidos são comparados integralmente. Arquivos incompatíveis abrem inspeção,
sem reparo silencioso. Os JSON antigos do estudo externo não ativam a nova rota.
Word e JSON usam a evidência guardada no resultado, sem requalificar histórico.

Componentes resistentes e interação concomitante N=0 são calculadas dentro do
domínio. ELS biaxial, torção/empenamento físicos, forças locais, ligações e
aprovação global continuam pendentes. A telha não contribui estruturalmente.
Não há nova linha de cortante/flecha paralela, migração para travessas 3D,
interpolação de espessura ou generalização para seção livre.

Veja `docs/UE_FAMILY_INTEGRATION_20261103.txt` para escopo e QA.


## Componente flexional biaxial própria — opção explícita de 04/11/2026

Nas sete espessuras próprias Ue100×50×17, ri=t, entre 3 e 6 m, a opção
**Flecha flexional biaxial por crivo de seção integral** verifica uma condição
suficiente MLE nas cinco paredes e em todo o vão. Quando demonstrada, calcula
nova resposta simultânea com Ix/Iy/Ixy do mesmo contorno, incluindo q/P assinados,
reversão e posição interior de P. Somente a componente normal é comparada com
o limite declarado. A condição suficiente é uma interpretação de engenharia
documentada; não é fórmula normativa geral de seção reduzida biaxial.

Crivo inconclusivo permanece sem índice, sem recuperar o resultado escalar.
A viga é uma componente flexional biapoiada, não inclui a resposta torsional,
ligações ou instabilidade física. ELS completo e aprovação global continuam
pendentes. O primeiro contrato de integração cobriu a terça. A extensão explícita
à travessa isolada está descrita abaixo; o conjunto 3D tem contrato físico próprio.
As rotas anteriores sem essa escolha e a opção uniaxial explícita são preservadas.

O prazo foi cancelado: nenhum estudo novo ativa automaticamente o fallback
uniaxial ou esta nova rota. Importações e escolhas existentes não são migradas.
Não são restauradas linhas de flecha/cortante paralelo. Históricos só exibem
sua evidência salva, sem executar cálculo novo; registros inconsistentes perdem
o índice na apresentação e solicitam recálculo explícito.

Esta integração permanece em cópia, sem publicação. Ver
`docs/BIAXIAL_GROSS_COMPONENT_20261104.txt` e os recibos de QA separados.


## Travessa isolada com fonte própria — extensão explícita de 04/11/2026

Nas mesmas sete fontes Ue e vãos de 3 a 6 m, a seleção **Aplicação da referência
própria** permite propor e aplicar uma **Travessa lateral isolada — boca para
baixo**. Um contrato versionado preserva propriedades, ações, critérios e fontes.
Mudar apenas o rótulo no JSON não ativa essa transformação. Nenhum apoio ou crédito
de tirantes, molas, telha ou conjunto de três travessas é inferido.

No modo por área, PP e permanente do fechamento entram verticalmente, pela área
de influência; vento atua horizontalmente. SC, inclinação e P automática de
cobertura ficam inativos, com dados antigos preservados. No modo direto, os
componentes já combinados e as posições de P são mantidos sem nova rotação ou PP.
O limite horizontal é `wall_els.normal_reference_mm / normal_denominator`, com
referência vazia igual ao vão. Ele não usa o limite armazenado da cobertura,
não encurta o vão de cálculo e não representa prescrição normativa automática.

A escolha biaxial permanece opt-in. Quando o crivo demonstra a seção integral,
somente a componente horizontal da resposta flexional tensorial é comparada com
o critério. Crivos inconclusivos continuam sem índice. Não há nova linha vertical,
resistência torsional, aprovação ELS física/global ou extensão ao conjunto 3D.
A escolha de torção da terça, se armazenada, é preservada e fica inativa e pendente
na travessa isolada. Históricos inconsistentes são recusados sem recálculo.

Veja `docs/OWN_UE_ISOLATED_GIRT_20261104.txt`. A candidata foi preparada e testada
em cópia; publicação e confirmação do runtime online são etapas separadas.
