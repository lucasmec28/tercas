# Nova rota EN seccional da família Ue

A escolha `isolated_en_ue_family_model` ativa explicitamente nova versão de cálculo. Não converte resultados antigos ao abrir. A ativação substitui escolhas EN concorrentes sem alterar cargas, E/G de análise, comprimentos ou propriedades numéricas.

A tabela documental admite apenas os 66 Ue completos. Elegibilidade documental não significa cobertura de todos os operadores. Cada combinação exige somente os ramos Mx/My necessários, identificados por controles racionais de equilíbrio. Eixo exatamente nulo não exige resistência fictícia. Um ramo necessário ausente gera pendência nominal nas tensões/M–V; o cortante EN6.1.5 continua calculado independentemente. Não há sigma/tau fabricados. Contagens distinguem cortante, tensões, M–V e casos parciais. EN My tem sinal oposto ao My NBR da interface, conforme demanda Vlasov existente.

Resistência: E=210000 MPa, ν=0,3, fyb=fya declarado, sem encruamento; γM0=1 é escolha explícita desta versão, independente de γ NBR. Outros γ ficam pendentes com motivo. Nome/fu/origem declarados acompanham a fonte, sem afirmar conformidade de produto/ductilidade automaticamente.

A rota calcula EN6.1.6 concomitante e EN6.1.5/6.1.10 com N=0 e Mf=0. Não herda capacidade axial250. Shear lag/curling e testemunhas físicas usam dimensões e limite resistente atuais. Giro alto, adequação física da primeira ordem, estabilidade global e ELS combinado não são aprovados.

Fontes normais e geometria integral (omega, primitivas, J/Cw) são autenticadas uma vez por lote fechado. Leituras verificam dados/fontes atuais, vínculos completos da demanda, resumo, cargas, rigidez e aritmética. Selfhash não é autoridade; não existe flag serializável de confiança. Cache usa conteúdo completo, nunca identidade de objeto. Em processo frio, geometria nominal pode ser preparada uma vez para autenticação; não há novo solver de membro nem reconstrução por combinação.

Módulos e fontes antigas pinadas permanecem intactos. Hooks limitados aos dispatches `isolated_en_application`/`isolated_en_ui` e à lista de opções preservadas entre reruns em `app.py`. UI/Word usam projeção após validação; JSON preserva prova completa.

Este checkout foi reconstruído após substituição do executor. Resultados de testes anteriores à reconstrução não constituem validação desta versão. A matriz deve ser gerada novamente pelo script `qa/en_ue_family_app_matrix.py`.
