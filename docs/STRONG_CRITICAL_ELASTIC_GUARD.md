# Guarda proposta — críticos tabulados do eixo forte

Cópia de avaliação local do HEAD 4e8420893e08e3f3bb223e94732e70b6c808ed97. Sem publicação.

A Rev07 registra E=200 GPa, apoios simples e cantos retos para Pierin 2013, mas não explicita ν. Não se atribui ν=0,3 nem G=77000 MPa à fonte. O segundo número é somente a configuração original do aplicativo (material NBR), não uma validação do modelo da tabela.

- E diferente de 200000 MPa bloqueia o uso dos críticos tabulados automaticamente herdados.
- G diferente de 77000 MPa sinaliza mudança da configuração original; a compatibilidade não é demonstrável sem G/ν da fonte. A guarda deixa esses críticos pendentes, em vez de inventar G ou ν, recalcular ou escalar.
- O caso original permanece disponível com as ressalvas já existentes: a ausência de ν na fonte não invalida por si a tabela no domínio original.
- Valores de entrada são preservados para auditoria; `input_snapshot.Ml/Mdist.value` fica nulo quando bloqueado. Ramos dependentes não recebem índices. Avisos entram na interface, Word e comparação de catálogo pelos caminhos existentes.
- A guarda reconhece importações antigas pelos valores numéricos tabulados ou pelo texto original do catálogo. Origem automática de outra seção/linha não vira entrada manual, mesmo quando o destino não tem Ml tabulado. Avisos de críticos são separados de cobertura geométrica: Mdist dispensado pela Tabela 14 não bloqueia a capacidade forte/biaxial apenas por ter um aviso de procedência. Editar só a origem, ou só o valor enquanto mantém a origem automática, não remove a guarda.
- A rota existente de valores independentes, diferentes dos tabulados e com origem independente, permanece manual e não é certificada. Nova análise que coincida numericamente com a tabela continua conservadoramente bloqueada: esta proposta não inclui um fluxo de requalificação explícita.
- Também bloqueia Ml automático legado da Tabela 12 no fluxo direto quando E muda: não há snapshot inequívoco dos parâmetros do valor herdado. O fluxo de comparação que já recalcula com E atual é reconhecido somente se sua origem e o valor coincidirem com a fórmula existente. A evidência registra E, dimensões, W e ν=0,3 como parâmetro já adotado pelo código, nunca como ν de Pierin. Não altera a fórmula nem o eixo fraco; mantém entradas originais e não aplica escala automática. G sozinho não muda esta expressão da Tabela 12, que usa E/ν explicitamente; a guarda operacional de G vale para os tabelados.

Verificação: `python -m pytest -q tests/test_strong_critical_guard.py`, seguida da suíte completa.
