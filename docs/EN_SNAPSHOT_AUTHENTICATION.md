# Verificação de snapshots EN

Os cálculos novos dos sete perfis Ue100×50×17 usam o schema v6. O cálculo mecânico, as ações no centro de torção, as reações, as seções resistentes e os critérios normativos permanecem os mesmos. A mudança autentica a prova numérica armazenada, não amplia o domínio de projeto.

Cada ramo elegível armazena uma cobertura binária completa das faces e do intervalo longitudinal. Na leitura, os campos são reconstruídos da seção própria fixada e dos esforços salvos validados. Uma expansão Taylor–Bernstein de grau 24, com cauda e arredondamento para fora, verifica o teto de cada caixa. As testemunhas finalistas são recuperadas somente nas posições salvas, incluindo sinais, seção efetiva, N·e, B, parcelas de cisalhamento, erros e índices. A leitura não resolve a rede, não busca extremos e não executa um novo envelope.

O certificado envolve campos binary64 reconstruídos e suas margens numéricas. Não certifica a geometria física, a aplicabilidade normativa completa, a estabilidade global ou a construção exata das propriedades seccionais. Pequenos aumentos conservadores dos tetos são possíveis nos cálculos novos. Os limites inferiores físicos não são alterados por essa certificação.

Snapshots v1–v5 continuam legíveis. Seus números, testemunhas, ações e hashes não são reescritos. Sem a nova prova, um atendimento ou excesso salvo é apresentado como observação histórica, não como decisão atual autenticada. Para obter a verificação atual é necessário solicitar explicitamente um novo cálculo. Abrir, exportar ou montar um panorama não faz esse recálculo.

UI, Word, resumo e panorama usam a mesma política. Um panorama em cache que contradiga a fonte EN, o grupo completo ou seus próprios agregados é retirado e exige montagem explícita. Entradas e históricos não são apagados pela atualização dos caches ativos.

A prova e as testemunhas são verificadas independentemente de seus hashes. Trocar espessura/seção, eliminar caixas, reduzir tetos, inventar testemunhas ou alterar agregados, mesmo recalculando os hashes, não autentica uma decisão v6. Renomear o schema para histórico também não recupera crédito de atendimento.

Não há ativação da família ampliada de 66 perfis, nova opção de carregamento ou aprovação global neste reparo.


Os operadores seccionais do v6 também são vinculados ao registro local dos sete perfis, independentemente da EN6.27 opcional. O hash fornecido pelo arquivo não é uma autoridade. Fontes manifestadas e perfil próprio são rechecados mesmo em leitura quente. Caches limitados guardam apenas sucesso imutável sob digest calculado dos dados reais completos; não guardam payloads de usuário, falhas ou números não finitos.
