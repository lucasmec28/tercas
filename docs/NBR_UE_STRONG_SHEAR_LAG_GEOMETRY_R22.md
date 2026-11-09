# R22: largura de referência forte e dispensa NBR de shear lag

## Entrega

A investigação complementar fecha a **convenção geométrica nominal da largura forte** para as 66 Ue próprias, simétricas, com lábios internos de 90 graus. A nova guarda usa `bf0 = bf externo - t + lip nominal` e mantém o vão físico `L`. Ela recupera apenas a faixa `30(bf - t + lip) <= L < 30(bf + lip)`, antes conservadoramente pendente.

**Não foi implementada a redução da Tabela 7.** Se a dispensa não for demonstrada, as propriedades reduzidas continuam pendentes. Não se multiplicam capacidades por um fator, não se altera esforço e não se inventa distribuição espacial. O eixo fraco conserva exatamente a prova suficiente anterior. Nenhuma aprovação global decorre desta mudança.

Este documento substitui a conclusão geométrica preliminar de `NBR_UE_SHEAR_LAG_R22_REVIEW_20261108.md`. A contraprova daquele relatório continua válida para a distribuição entre mesa/lábio/cantos, que não foi resolvida. Não é necessário um tensor 2D universal para uma futura extensão forte escalar.

## Fonte primária e definição geométrica

Fonte normativa: ABNT NBR 14762:2010, SHA-256 `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`. Foram conferidas visualmente:

- PDF 14, impressa 8, 3.2.2: distingue largura plana `b`, largura nominal `bf` e referência `bf0`;
- PDF 38–39, impressas 32–33, 9.4/Tabela 7: largura livre da mesa mais largura nominal do enrijecedor; para viga simplesmente apoiada, comprimento de referência igual ao vão físico.

A convenção é corroborada geometricamente pelo [ANSI/SDI AISI S100-2024 e comentário](https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf), SHA-256 `6ec32742f056d08a0823557d9ce58b69d84312e64a6e656b8ba4b3b10cf4b4ca`. Conferência visual: B4.3, PDF 72–73/impressas 27–28; definições de C-I1.1-4, PDF 383/impressa 115. B4.3 soma projeção da mesa e lábio; C-I1.1-4, para C com lábios, identifica projeção desde a face interna da alma e altura total do lábio. O segundo item trata de outro problema e é usado **somente para corroborar a convenção dimensional comum**, não como regra de shear lag ou fórmula de resistência NBR. Não são usados seu cálculo de ligação, sua expressão de centro de torção ou suas curvas resistentes.

A consulta textual a Yu, *Cold-Formed Steel Design*, exemplos 4.13–4.14, reforçou a distinção entre projeção livre e trecho plano, mas não foi usada como certificado do Ue com lábio. O comentário B4.3 também foi lido, sem adotar sua proposta para DSM. O arquivo do manual AISI 1996 não pôde ser obtido da biblioteca consultada (HTTP 403); ele não fundamenta o código.

Nenhuma imagem/PDF dessas fontes é redistribuída.

## Derivação no contorno adotado

O contorno de `catalog_torsion_section.nominal_channel_nodes` usa dimensões externas e origem na interseção das linhas médias não arredondadas da alma e da mesa inferior:

1. Plano da face interna da alma: `x = t/2`.
2. Face externa da borda da mesa/lábio: `x = bf - t/2`.
3. Projeção livre entre essas faces: `(bf - t/2) - t/2 = bf - t`.
4. Soma da dimensão nominal externa do lábio: `bf0 = bf - t + lip`.

Com `r = ri + t/2`, a parte **plana** da mesa vai de `x=r` a `x=bf-t-r` e mede `bf-2(ri+t)`. Ela é necessária à rotina local, mas não substitui a projeção em 9.4. Alterar `ri` muda o trecho plano e não muda `bf0`, desde que os arcos e os lábios caibam no contorno. A guarda verifica essas condições de encaixe com as mesmas desigualdades do gerador nominal.

Exemplo sintético `h=200, bf=75, lip=20, t=2, ri=3 mm`: projeção 73 mm, `bf0=93 mm`, fronteira `L=2790 mm`. A antiga cota usava 95 mm/fronteira 2850 mm. A igualdade é dispensada porque o gatilho é estritamente menor. Frações exatas dos números binários controlam a comparação, não tolerâncias ou arredondamento visual.

Isso qualifica a geometria **nominal declarada**, não a medição/fabricação do produto. A largura fraca não recebe metade da alma nem qualquer nova classificação.

## Contrato e integração

Novo módulo `tercas.nbr_ue_shear_lag_strong`:

- `strong_reference_geometry(dimensions, inner_radius)` devolve faces, projeção, lábio nominal, largura exata, trecho plano distinto e fontes;
- `assess(...)` recebe as mesmas ações individuais/vão/modelo da guarda anterior e o raio autenticado;
- `validate_saved(...)` reconstrói todos os campos, sem aceitar isoladamente booleans ou hashes salvos;
- evidência `NBR_Ue_shear_lag_applicability_v2_strong_reference_geometry`;
- o eixo normal guarda também sua prova suficiente anterior, e o eixo paralelo permanece idêntico à v1;
- não usa dispensa por P no apoio, espaçamento de múltiplas P, cancelamentos de resultantes ou tolerância para forças pequenas;
- `below_exact_span_threshold` não é automaticamente uma prova de incidência em todos os inventários de múltiplas P. O caso curto continua pendente, nunca `fails`.

A aplicação da família autentica a origem entre as 66 linhas admitidas e utiliza a guarda em **cada combinação ELU**, incluindo travessa isolada. O raio e as dimensões vêm da mesma identidade nominal do pacote resistente. M-V valida pela versão da guarda, e os demais consumidores usam a qualificação do eixo correspondente. Capacidades puras, ações, sinais, PP e comprimentos resistentes não mudam.

Schemas novos de aplicação:

- `nbr_ue_family_application_v8_strong_shear_lag_geometry`;
- `nbr_ue_family_application_v8_all_actions_CT_strong_shear_lag_geometry`;
- `nbr_ue_wall_girt_application_v3_strong_shear_lag_geometry`;
- `nbr_ue_wall_girt_application_v3_all_actions_CT_strong_shear_lag_geometry`.

As versões antigas são reconhecidas explicitamente e reconstroem a guarda v1. Não basta renomear um schema antigo: a nova evidência tem outra largura, prova, raio e fontes e a reconstrução rejeita adulterações. Novos cálculos continuam adotando CT pela política existente e PP 1,25/1,0; não se altera aquela política física, somente os identificadores da emissão resistente. A interface/Word descrevem a nova referência apenas nos schemas novos.

## Histórico independente e verificação

Quatro snapshots sintéticos foram produzidos executando a base **inalterada** `332e478cd1b26323974475dfa1fcf14327ccd216`, antes da nova guarda:

- cobertura CT, antigo v7, e travessa CT, antigo v2: `L=1980 mm`, seção nominal do índice 26, P interior, comprimentos resistentes de 1000 mm; a guarda antiga permanece pendente;
- cobertura sem CT, antigo v6, e travessa sem CT, antigo v1: q puro no domínio escalar anterior.

Arquivos e SHA-256 estão em `qa/nbr_shear_lag_strong_geometry/historical_manifest.json`. A leitura fria compara o pacote completo com a reconstrução antiga; o teste verifica imutabilidade. Somente o recálculo explícito dos dois primeiros emite schema novo e dispensa forte: sua fronteira passa de 2010 a 1950 mm. As fontes resistentes, capacidades, ações e demandas são comparadas integralmente antes/depois.

Testes focais realizados com `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`:

- Guarda nova + consumidor CT + guarda v1: 234 testes aprovados em 5,17 s.
- Cache, 66 travessas escalares, política CT, consumidor e diagnóstico preliminar: 262 testes aprovados em 76,50 s.
- Rodada final, incluindo os dois históricos sem CT e o diagnóstico preliminar: 262 testes aprovados em 6,19 s, conforme `qa/nbr_shear_lag_strong_geometry/validation.json`.

As duas últimas rodadas não são somadas como testes distintos: 524 execuções têm 36 casos sobrepostos (10 do consumidor e 26 diagnósticos), cobrindo **488 casos distintos aprovados**. A coleta da união dos sete arquivos confirmou 488 casos. A rodada inicial de 234 também é sobreposta e não acrescenta cobertura distinta.

Revisão independente estática/visual aceita, sem bloqueios ou mudanças solicitadas, conforme confirmação da integração após releitura da geometria nominal, fonte NBR, apoio dimensional AISI, fronteiras, eixo fraco e schemas históricos. Isso não amplia o escopo para redução de seção pela Tabela 7.

Cobertura: todos os 66 registros na aritmética geométrica; sinais opostos; fronteira exata e números adjacentes; faixa recuperada; q puro e P individuais contrárias; invariância do eixo fraco; influência de raio apenas no encaixe/trecho plano; importação escalar sem NumPy; JSON; fontes/raio/largura/schema adulterados; M-V, panorama e históricos completos. Os testes focais de integração bloqueiam os solvers elásticos e de barra. A regressão existente da política CT preserva as ações e PP com seus fatores.

Não se rodou regressão completa, navegador ou matriz pesada de estabilidade nesta entrega. Não foram ampliados rede, ELS combinado, apoio local, ligação, U simples, perfil genérico ou seção efetiva reduzida por shear lag.
