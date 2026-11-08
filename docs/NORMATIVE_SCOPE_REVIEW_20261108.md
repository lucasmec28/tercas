# Parecer técnico de leitura: itens 1, 3, 4 e 6

**Revisão corrigida do mapa EN:** o primeiro texto deste parecer confundia o caminho alternativo fy250 com a rota familiar prioritária. O bloco da família abaixo foi substituído após seguir o dispatcher e o consumidor efetivamente importado.

Base examinada: R18, commit `e12bfe9`. Revisão somente de leitura em 08/11/2026. Nenhuma edição de produção, solver, teste ou UI executado. Este parecer descreve implementações e domínios; não examina um resultado de projeto específico, portanto não afirma quais entradas de um projeto estão ausentes.

## Síntese para responder ao usuário

**1. Torção.** Manter as verificações previstas nos métodos adotados. O ramo AISI G8.1 de primeiro escoamento já implementado não exige Bp/Bcr. A opção com reserva inelástica é alternativa, não uma pendência automática. Uma limitação do modelo linear em um caso de grande giro deve ser descrita como limite de aplicabilidade da análise, não como nova equação resistente, limite angular normativo inventado ou exigência universal de ensaio/GMNIA. Não se impõe uma análise externa adicional como verificação universal da norma.

**3. Cortante e interações.** Não falta implementar novamente o cortante forte e M–V NBR. A pergunta correta é se o caso/rota atual tem todas as componentes efetivamente não nulas e seus domínios cobertos. NBR forte/alma, EN dois cortantes/N–M–V e EN tensões de torção são componentes distintas. Não se somam índices de normas diferentes nem se inventa uma interação adicional N+M+V+B+T sem expressão aplicável. Quando o método suficiente produz teto maior que1, o resultado é inconclusivo, não prova de falha nem demonstração de fórmula faltante.

**4. FLT.** A NBR é clara e sua fórmula resistente está disponível. A entrada que exige cuidado é Me elástico. A fórmula fechada NBR cobre carga no CT e permite carga estabilizante a favor da segurança; carga desestabilizante remete expressamente à bibliografia especializada. A rota direta do app já aceita q+P, Cb e Ly/Lz independentes dentro daquele domínio. A rota com altura possui ENV, Ritz e piso energético com diferentes domínios. Logo, “q+P pendente” sem indicar rota é enganoso.

**6. Apoio.** Faltam, quando não declarados, os dados do caminho da reação e do contato local que selecionam a equação/linha da tabela. Não é pedido de dimensionamento de parafusos, soldas ou telha. Há painel de apoio já implementado e componente separada de P. Resultado de apoio não deve ser confundido com ligação completa.

## 3. Mapa real de cortante/interação

### Vão isolado NBR legado, inclusive U simples nas condições admitidas pela origem

- `tercas/global_verification.py:277–292`: lê VRd do ramo de cortante e M–V com x concomitante.
- `tercas/core/travamentos_nbr.py:23–36`: estabilidade resistente separada; não usar seu mínimo FLT como denominador M–V.
- Fonte primária conferida visualmente: NBR14762:2010 pp.50–51/PDF56–57. §9.8.3 usa h da parte plana da alma; kv=5 sem enrijecedores transversais. §9.8.4 usa (MSd/MRd)^2+(VSd/VRd)^2≤1 e define MRd por9.8.2.1, VRd por9.8.3.
- Esse caminho não transforma a capacidade da alma em capacidade transversal das mesas. Não foi encontrada justificativa para anunciar EN em todo U simples apenas porque há Vlasov ou NBR escalar.

### Família própria dos 66 Ue completos

- `tercas/nbr_family_mv.py:204–228,325 em diante`: M forte/V da alma concomitantes, resistência local própria e gate de9.4 para M–V; cortante puro independente do gate flexional. Não recebe capacidade nominal Pierin/EN no denominador próprio.
- `tercas/nbr_family_panorama.py:73–87`: integração real existente, substitui as linhas forte/alma de cortante e M–V. O documento histórico `docs/NBR_FAMILY_MV_R11.md` termina com proposta de hook, mas o código R18 já contém o consumidor. Não tratar essa proposta histórica como ausência atual.
- O ramo NBR não fecha cortante fraco não nulo. Caso fraco nulo não precisa de parcela fictícia.
- **Rota prioritária atual, corrigida nesta revisão:** `isolated_en_application.py:116–122` despacha primeiro `isolated_en_ue_family_application` quando `isolated_en_ue_family_model` existe. O limite fy=250 pertence à rota alternativa/legada `isolated_en_ue_catalog_application`, não à cobertura geral R18. Há também legado Ue125300 separado. Não usar o mapa desses legados para limitar a família atual.
- `isolated_en_ue_family_application.py:19–27,76–92,159–171`: família completa nominal Ue, fyb=fya declarado, modelo intacto, terça isolada N=0, origem declarada. `en_ue_family_provider.py:48–70` recalcula seção pelo material recebido, sem escalar capacidades antigas. `en_ue_family_kernel.py:24–30` exige fy/gamma positivos finitos; `:401–402` limita atualmente a normalização normal a gammaM0=1. Não há limitação geral a fy250.
- **Dois cortantes já calculados:** `en_ue_family_kernel.py:269–312` aplica EN13 §6.1.5/Tabela6.1, alma no forte e duas mesas tratadas como almas rotacionadas no fraco. Pisos próprios por material/parede; sem crédito ao lábio, cantos ou enrijecedores de apoio. Guardas geométricas/raio/espessura estão em `applicability_checks`. `isolated_en_ue_family.py:134–176` conserva cortantes mesmo quando ramos flexionais requeridos faltam.
- **M–V EN existente:** mesmo `isolated_en_ue_family.py:134–176`, N=0 provado, ambos os momentos assinados e cortantes concomitantes, Eq6.27 com Mf=0; parcela adicional zero até V/Vb≤0,5 e penalidade (2V/Vb−1)^2 acima. Usa somente pisos EN da própria seção/material. B/Tsv/Tw ficam nas desigualdades de EN6.1.6, não se exige torque nulo nem se converte T em V. `mv.status=pending` significa ramo solicitado ausente ou aplicabilidade flexional ainda não qualificada; `inconclusive_upper_bound` é diferente.
- **Reduções local/distorcional já existentes:** `en_ue_family_kernel.py:408–456` tenta seção integral, My negativo com alma reduzida e extensões de `en_ue_family_reductions.py`. Este usa EN13 §5.5.3.2 passos1–2, largura efetiva e t_red=chi_d·t, com rechecagem5.17; o refinamento favorável opcional passo3 não é usado. My negativo ainda dispõe de majorantes Table4.2 e Eq4.4 EN15. Não anunciar “só seção integral” ou exigir implementar novamente local/D.
- **Shear lag/curling atuais:** `en_ue_family_applicability.py:57–102`, e NÃO a rotina antiga fixa em250, usa fy/gamma declarado e centroides efetivos. Dispensa shear lag somente b0<Le/50 em zonas físicas entre zeros de M, com q uniforme/até uma posição P por eixo; curling por EN13 §5.4. Falha dessa dispensa não encerra o caminho: `isolated_en_ue_family.py:179–190` tenta envoltória Mx de `en_ue_family_shear_lag`, com My concomitante independentemente aplicável.
- **A extensão concomitante Mx/My está ligada ao aplicativo:** `isolated_en_ue_family_application.py:171,201` importa/chama `isolated_en_ue_concurrent_candidate.calculate_many`. O docstring antigo “No UI or production caller imports it” e textos internos “not production integration” estão desatualizados frente a essa chamada; não são evidência de caminho desligado. `isolated_en_ue_concurrent_candidate.py:44–100,123–133` conserva base já qualificada; para base pendente tenta a extensão de ambos os eixos com verificação local/D simultânea e curling de cada componente pura. Recalcula6.1.6 e6.27 com os pisos/operadores próprios resultantes. Não migra histórico automaticamente.
- **Pendências reais da extensão, condicionais ao caso:** `en_ue_concurrent_shear_lag_candidate.py:283–354`: construção My própria indisponível; ramo assinado exigido inelegível; geometria/contorno/campo original incompatível; falta de omega/Cw/B explícitos; teto do campo normal simultâneo Mx+My+B acima do teto suficiente local/D; referência uniforme local/D não qualificada; curling puro de eixo ativo não qualificado. Códigos: `SIMULTANEOUS_LOCAL_D_CEILING_NOT_PROVED`, `UNIFORM_LOCAL_D_REFERENCE_NOT_QUALIFIED`, `PURE_COMPONENT_CURLING_NOT_QUALIFIED`, `CONCURRENT_SHEAR_LAG_REFERENCE_NOT_QUALIFIED`; o consumidor acrescenta `SOURCE_SIGNED_OPERATOR_NOT_QUALIFIED`. São motivos concretos de inconclusão do método implementado, não rejeição normativa universal de uma seção.
- Fontes dos métodos de extensão: `en_ue_my_shear_lag_candidate.py:28–31` e `en_ue_family_shear_lag.py:23–26`: EN1993-1-5 §3.3 Nota2/Eqs3.3–3.4/Tabela3.1 e §4.3; `en_ue_concurrent_shear_lag_candidate.py:261` EN15 §4.4(4)/Eq4.4 e EN13 §5.5.3.2/passos1–2/Eqs5.10b,5.12,5.13,5.15,5.17; curling EN13 §5.4/6.1.4.1. A construção suficiente simultânea é uma forma de justificar a extensão, não nova expressão obrigatória de interação imposta pelo aplicativo.
- A extensão do contorno próprio não se transfere para registros Pierin incompletos sem geometria autenticada. Ausência de contorno é falta de entrada/rota, não proibição normativa da família.

### Referências Ue próprias anteriores e rede/travessas

- `tercas/isolated_en_application.py:17–22`: EN6.1.6 independente, tensões normais e cisalhamento V/Tsv/Tw no mesmo campo; não substitui resistência a flambagem por cortante6.1.5 ou interação6.1.10.
- `tercas/three_girt_shear.py`: alma forte NBR e componente EN de alma já presentes; documentação histórica `SIMPLIFIED_SHEAR_STABILITY_20261106.txt` descreve o estágio apenas alma, não toda cobertura atual.
- `tercas/three_girt_en_mv.py:16–34` e `tercas/en_simplified_interaction.py:14–23,73–109`: N–Mx–My e dois cortantes EN, redução zero até V/Vb≤0,5; acima disso penalidade (2V/Vb−1)^2 com Mf=0 conservador. N mantém transporte do centroide. B/Tsv/Tw continuam em6.1.6, sem conversão T→V.
- `tercas/three_girt_assessment/application.py:370–399`: quando o snapshot EN6.27 cobre todos os trechos selecionados, substitui as pendências antigas “cortante fraco” e “N–M–V” por resultados das duas direções. Não afirmar que essas parcelas faltam sempre na rede. Se incompleto, identifica erro/trecho ausente.
- “Sem aprovação global” não é uma verificação normativa adicional: é separação de escopo. Exibir o critério disponível e a parcela realmente ausente, se houver.

### O que é adicional/opcional, não obrigatório por falta genérica

- Rodar EN em paralelo não transforma EN em requisito universal extra da NBR. Uma vez adotada a rota EN para uma componente, seus domínios e interações aplicáveis precisam ser respeitados.
- Recalcular algo mais preciso quando um teto suficiente excede1 é uma possibilidade para resolver inconclusão, não reprovação automática.
- Não impor uma equação universal combinando NBR9.8.4, NBR9.9, AISI H4 e EN6.1.6. Manter fonte e grandeza de cada critério.

## 4. Me, Cb, altura e comprimentos

### Texto primário conferido

NBR p.48/PDF54: Me é momento de FLT “em regime elástico”; expressões deduzidas para carga no centro de torção; aplicação também a carga estabilizante é permitida a favor da segurança. Para posição desestabilizante, manda consultar bibliografia especializada. Para seção duplamente simétrica ou monossimétrica em torno do eixo de simetria: Me=Cb·r0·sqrt(Ney·Nez). Ney/Nez são de9.7.2.1 considerando KyLy=Ly e KzLz=Lz. Valores menores podem ser usados com justificativa bibliográfica. Cb pode ser1 a favor da segurança ou calculado pelos momentos de quartos.

Essa página não impõe universalmente Ly=Lz=L físico. Não confundir a guarda numérica do Ritz com uma restrição universal da norma. A passagem destaca também que vínculo de empenamento e condições de balanço/continuidade podem exigir bibliografia; coordenadas de travamento não comprovam, sozinhas, sua rigidez.

### Rotas já disponíveis

1. **Direta NBR, CT/estabilizante:** `core/travamentos_nbr.py:23–36`. Me=Cb·π/Ly·sqrt(EIy·(GJ+π²ECw/Lz²)). Aceita Ly,Lz positivos independentes, origem declarada, Cb=1 ou quartos. O próprio `segment_moments:7–19` trata q+P. `:41–69` admite comprimento lateral da mesa superior/inferior conforme compressão e não cria travamento no ponto de inflexão. Guarda: eixo forte de simetria, CT/estabilizante sem torção primária na referência. Exemplo sintético: q+P nesse domínio, Ly=L/2 e Lz=L declarados/justificados já têm rota de cálculo. Não inventar altura zero para habilitar o caminho.
2. **Com altura por fórmula ENV:** `flt_height_effective.py:30–55,88–122,130–214`. q uniforme resultante OU P no meio do vão; kz=Ly/L exatamente0,5 ou1 e kw=Lz/L entre0,5 e1. Alturas das parcelas agregadas apenas para funções de carga idênticas. Exemplo: q uniforme, Ly=L/2,Lz=L, coeficientes C1=0,972/C2=0,304. Exemplo: P central, Ly=L,Lz=L/2, C1=1,365/C2=0,553. São cálculos condicionais à equivalência dos fatores; Ly/L não identifica um engaste real. Não usar as linhas ENV de q ou P para q+P misto por soma harmônica.
3. **Ritz q+P fresco R18:** `flt_height_effective.py:285–342,348 em diante`. Prioriza ENV quando elegível; caso contrário Ritz existente com Ly=Lz=L físico, garfos/empenamento livre, simetria, alturas e ações autenticadas, eventual projeção paralela elegível. Não convergência mantém motivo explícito. Me é referência aproximada, não limite inferior certificado.
4. **Piso energético q+P/Leff:** `flt_height_energy_floor.py:152–212,254–304`; consumidor `flt_height_nbr_floor.py`. Comprimentos entram como hipóteses de limites energéticos, com phi nulo nos extremos. Não reconstrói vínculos. Pode provar atendimento com o piso resistente; índice>1 é inconclusivo. A rota existe para domínios em que o Ritz não aceita Leff reduzido, mas não torna qualquer Leff fisicamente demonstrado.

Fontes documentais do ramo com altura: `docs/FLT_REFERENCE_REVIEW_R18.md` e `FLT_FRESH_REFERENCE_20261108.md`: ENV1993-1-1:1992 Anexo F; reprodução Castiglioni pp47/50; NCCI SN003a para contraste; Sahraei/Pezeshky/Mohareb2017 energia. Nesta revisão, NBR foi conferida novamente na fonte primária; essas demais fontes foram avaliadas pelo registro auditado do projeto, sem nova consulta integral independente.

## 6. Dados físicos de apoio e introdução localizada

### Fonte correta

NBR p.78/PDF84 e p.79/PDF85 conferidas visualmente: D.1 define domínio de compressão localizada da alma por força aplicada ou reação; **D.2 é a equação FRd**, e **Tabela D.2** fornece coeficientes para U/Ue. Não confundir seção D.2 com uma exigência de enrijecedor. Fórmula usa t,fy,theta,ri,c,h e coeficientes da situação. §9.5.1/exceção de alma ligada é usada pelo app; seu texto é registrado nos docs, não foi novamente renderizado nesta leitura.

### O painel de apoio realmente pede

`support_web/ui.py:10–11,40–59`, contrato `support_web/mechanics.py:1–23,109–180`:

- Caminho da reação: alma ligada a outra viga/pilar, ou contato pela mesa. Não inferido de garfo ideal.
- Origem/descrição do detalhe.
- No contato: comprimento longitudinal **c_mm** (não “N” no schema deste app), distância livre ao extremo físico **end_distance_mm**.
- Mesa conectada **connected**: restrição local à rotação da mesa na região, não travamento global, ligação de alma ou projeto de fixador.
- Outra força concentrada na mesa oposta: **no_opposite_force**; se existe, **opposite_clear_distance_mm**.
- Sinal de força normal que comprime a mesa declarada **normal_compressive_sign** e descrição **loaded_flange_orientation**. A descrição é campo de UI, mas o núcleo permite omiti-la; o sinal é obrigatório no contato.
- O domínio é theta=90°, sem crédito a enrijecedor transversal. H,t,ri,fy vêm da seção, não são novas entradas de apoio.

`core/anexo_d.py:5–18,21–53`: classificação automática da condição de uma/duas mesas e extremidade/interior. Distância livre entre forças opostas≥1,5h corresponde a uma mesa, abaixo a duas; distância ao extremo≤1,5h corresponde à extremidade. Caso específico conectado/duas mesas/interior requer >2,5h. Equivalentemente, os quatro casos físicos podem ser descritos EOF/IOF/ETF/ITF, mas essas siglas não são campos de entrada no código.

Limites: c≥20mm, h/t≤200, c/t≤210, c/h≤2, theta90°, ri/t por linha. U simples com mesa conectada não tem linha no subconjunto da Tabela D.2, logo não se inventa capacidade. Contato de reação não compressiva não é reclassificado automaticamente em outra mesa ou ancoragem.

`support_web/mechanics.py:99–124`: normal nula não aplica apenas o critério normal; alma declarada ligada a outra viga/pilar registra exceção de enrijecedor9.5.1, não resistência/aprovação da ligação. Não pedir diâmetro de parafuso, solda, telha ou desenho completo para essa declaração local.

### Carga P e reações são entradas distintas

`point_web/ui.py:20–42` e `docs/POINT_WEB_LOCAL_R17.md`: Ue isolado usa o mesmo motor Anexo D. P pede contato c, origem/mesa/sinal/conexão/força oposta e declaração de extremos físicos em0/L com P centrada no contato; só então deriva distância ao extremo. Essas duas últimas são limitações do adaptador, não exigências universais da NBR. P no limite matemático do apoio não representa contato finito; reações permanecem separadas. Ações paralelas e momento são registrados sem inventar interação M+F no Anexo D.

Não existe identificador literal `local_load_site` no código R18 examinado (busca textual completa no repositório). Usar os nomes reais `support_web`, `point_web`, `point_contact` e detalhes acima; não prometer um schema inexistente.

## Alteração mínima recomendada de apresentação, sem mudar mecânica

O inventário `completion_requirements.py:17–63,95–106` é deliberadamente amplo e pode conservar `closure_not_qualified` apesar de componentes calculadas; a saída deve evitar traduzi-lo como “falta fazer tudo”.

- Cortante: “Forte/alma NBR: calculado”; “Fraco: nulo / coberto pela componente EN / não coberto nesta rota”, conforme evidência atual.
- M–V: “NBR9.8.4 calculado”; para EN, mostrar ramos faltantes/gate concreto ou “teto inconclusivo”.
- FLT: mostrar fórmula resistente disponível, origem de Me (NBR direta, ENV, Ritz ou piso) e a exata hipótese que impede aquela rota. Não usar “norma ambígua”.
- Apoio: “Aguardando caminho da reação/dados de contato”, listando apenas campos ausentes. Separar “fora do escopo: dimensionamento completo de ligações”.
- Torção: “G8.1 primeiro escoamento” e “H4 no domínio implementado”; reserva inelástica opcional; limite do modelo descrito separadamente.

## 1. Rastreabilidade da torção

`aisi_torsion_component.py:22–29,38–50`: Bn=By=Fy·Cw/max|omega|; Ba=0,90By. `:221–226`: H4 possui domínio de implementação Ue100 próprios e L3–6m, não limite normativo universal. `aisi_torsion_ui.py:37` já informa expressamente que Bp/Bcr não são exigidos nessa opção.

AISI S100-2024, G8.1 pp. 67–68 e H4 pp. 73–74; fonte https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf. Não se acrescenta limite angular normativo nem uma verificação resistente extra por esse comentário de aplicabilidade.

## Fonte primária NBR usada nesta leitura

PDF fornecido, SHA256 declarado `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`. Foram renderizadas e lidas as páginas54,56,57,84,85 do PDF. A extração de texto preexistente estava vazia; nenhum enunciado normativo foi inferido desse arquivo vazio. A norma integral não foi copiada para este parecer.
