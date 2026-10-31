# Candidato 0.4.0 — eixo fraco e flexão biaxial

> Estado atual: interface compacta com propriedades da planilha automatizadas; as descrições iniciais de entradas manuais duplicadas abaixo são histórico da primeira cópia, substituídas pela seção «Automação compacta posterior». Nenhuma publicação por este agente.

Base: cópia integral de outputs/tercas_bound/candidate, versão publicada 0.3.1. Não publicado.

## Implementado
- Motor revisado de `outputs/tercas_inclinacao/engine/inclination.py` reutilizado, preservando W primeira fibra versus Wc comprimida.
- Anexo E com Nex, Nez, r0, j, Cs, Cm rastreados por sinal de My; Na integração simplificada, Cm = 1 em todas as combinações; valores inferiores são rejeitados (motor genérico preserva domínio mais amplo, sem liberá-lo na UI).
- Capacidades local, FLT e distorcional por eixo/sentido, com Mly e Mdist externos qualificados. Sem importação bilateral de Pierin e sem Tabela 14 forte no eixo fraco.
- §9.9 N=0: envelope analítico para uma posição FIXA de P, cargas q/P simultâneas nos dois eixos. Partição nos zeros de Mx/My, na posição P e nos extremos; cálculo dos pontos estacionários de cada trecho quadrático. Não soma máximos separados.
- Capacidade forte conservadora: mínimo de todos os ramos aplicáveis e trechos FLT cobertos. Se algum exigível faltar, interação permanece parcial.
- Interface avançada por sentido; tabela de capacidades/dados ausentes. Perfil diferente limpa entradas fracas. Word e JSON guardam inputs, origem, capacidades e seção concomitante governante.
- P móvel por área: candidato central não aprova envelope biaxial; reprovação conhecida é preservada. Modos direto e por área, decomposição e limite superior de flecha P existentes preservados.

## Limitações explícitas
- Não gera automaticamente propriedades setoriais nem críticos fracos de catálogo. Os resultados são condicionados aos dados informados; não valida sua origem física apenas porque o texto está preenchido.
- ELS paralelo e cortante paralelo não foram implementados aqui; nenhuma reutilização indiscriminada de VRd da alma.
- Não inclui N axial na interação, torção primária ou efeito de altura da carga; domínio já declarado permanece necessário.
- Envelope biaxial P móvel ainda parcial; não validado por simplificação para P central.
- Nenhuma aprovação global da terça; propriedade geométrica do catálogo continua com ressalva original.

## Testes
- 15 novos testes de integração, domínio, sinais, origem, P móvel e Word; 100 cenários aleatórios contra 10.001 pontos de referência.
- Revisão independente adicional: 1.000 cenários aleatórios contra 10.001 pontos, sem subestimar a referência discreta (não validação física).
- Suíte completa e veredito independente: consultar REVIEW.md e test logs.

Resultado final, 31/10/2026 18:10 UTC: **168 testes + 468 subtestes passaram**, pytest completo em 113,40 s (tempo da suíte, não do cálculo). `pytest.log`. Smoke extra com inputs fracos preenchidos passou (`smoke_ui.py`, `weak_ui_smoke.log`). Revisão independente em `REVIEW.md` sem bloqueio no escopo fixo. Continua NÃO PUBLICADO.

Correção após auditoria de publicação: texto de escopo MC atualizado; Cm=1 fixo na rota simplificada; redução manual rejeitada em direto/lote, com testes por combinação.

Resultado pós-auditoria, 18:16 UTC: **172 testes + 468 subtestes passaram** (`pytest_final.log`), incluindo escopo de MC e Cm=1 em direto/lote. Substitui a contagem anterior para o estado final desta cópia.

## Automação compacta posterior (18:23 UTC)
- Recupera Wy, xg, x0, r0 da própria planilha; usa A/Ix/Iy/J/Cw/E/G já existentes. Nex/Nez automáticos, Cs por convenção local e Cm=1 fixo. Lx segue vão por padrão e preserva personalização; Lz é o máximo efetivo dos trechos existentes.
- UI remove entradas manuais repetidas W/Wc/r0/Nex/Nez/j/Cs/Cm. Conserva somente Lx, am/bm/cm e origem avançadas (conversão catálogo/linha média não confirmada), e críticos/origem por sentido.
- `annex_e_properties.py` revisado integrado. Dimensões médias não são presumidas; U exige cm=0, Ue cm>0. Triagem de compatibilidade de 3% é guarda operacional de dados, não nova verificação normativa nem comprovação de geometria. Valores ausentes/incompatíveis tornam a rota parcial; demais cálculos continuam.
- Hipótese provisória autorizada: Ml,y tabulado preenche somente o sentido com alma comprimida. Fundamentação: comparação pyCUFSM do Ue200x75x20x2 com desvio ~1,94%; isto não qualifica todo catálogo. Não atribui Ml,y ao sentido oposto nem reaproveita Mdist,x. Conferência posterior com exemplos CBCA permanece declarada.
- 31 testes específicos passaram; smoke compacta preenche apenas geometria/crítico/origem e calcula capacidades automaticamente. Revisão independente confirmou seguimento de Lx ao vão, preservação de valor customizado, guards de família e dados ausentes.

Regressão final da interface compacta: **184 testes + 468 subtestes passaram**, `pytest_compact_final.log`, 119,10 s de suíte (não desempenho do cálculo). Este é o estado final testado em 31/10/2026 18:26 UTC.

## Selo de hipótese provisória (18:37 UTC)
A linha resumida de flexão biaxial agora acrescenta «hipótese provisória, a conferir» quando usa a interpretação provisória, inclusive para índice menor que 1, resultados móveis e resumo do lote. A MC repete o selo na própria tabela, não somente na memória detalhada. Marcador estruturado preservado no JSON, com reconhecimento do texto legado. Testes direcionados UI/MC + exemplos CBCA presentes: 46 testes e100 subtestes passaram (`pytest_hypothesis_target.log`); comparação CBCA segue limitada a etapas comuns, não equivalência MLE=MSE.

Estado final pós-selo e comparadores CBCA: **199 testes + 468 subtestes passaram**, `pytest_release_candidate.log`, 125,97 s de suíte, 31/10/2026 18:39 UTC. Não publicado por este agente.
