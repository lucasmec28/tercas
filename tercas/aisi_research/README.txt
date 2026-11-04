COMPARADOR AISI 2024 INCORPORADO — PESQUISA ISOLADA

Ponto de entrada do app: panel.render(st). API restrita: adapter.evaluate(t,L,f),
adapter.validate_snapshot e adapter.export_json. Não executar aisi_candidate.py
como script neste pacote: seu conteúdo mecânico foi preservado, com somente o
import relativo ajustado. A API impõe os 48 casos e confere o resultado inteiro
contra RESULTS.json antes de disponibilizar o snapshot.

A partir da raiz do aplicativo, com requirements.txt instalado:
  python -m pytest -q tests/test_aisi_research.py tests/test_ui_aisi_research.py
  streamlit run app.py

Reprodução dos 48 casos, sem escrever resultados:
  python -c "from itertools import product; from tercas.aisi_research.adapter import *; print(len([evaluate(*c) for c in product(THICKNESSES,LENGTHS,FACTORS)]))"

LEIA_ME.txt, provenance/ e os recibos de escala são documentação HISTÓRICA
intacta do estudo independente original, preservada para rastreabilidade.
Os comandos dessa documentação não descrevem a estrutura deste pacote do app.
As matrizes NPZ dos 12 modos FSM não foram incorporadas. Seus pins originais,
críticos, dados geométricos, kernels e recibos de auditoria estão preservados;
a auditoria integral de escala/autovalores requer o estudo original completo:
Tercas_Comparador_Longitudinal_AISI_20261104.zip. Não há promessa de executar
a auditoria de autovalores usando somente esta candidata do aplicativo.
O comparador de 48 casos e seus testes aqui são autossuficientes. Não há import
ou leitura da árvore externa do estudo. A geometria e os kernels necessários
ficam neste pacote e são verificados, sem cache, em cada renderização ativa.

O manifesto BUNDLE_MANIFEST.json é pinado no adapter e cobre os insumos
congelados e o kernel copiado. Os arquivos de integração (adapter/panel/testes)
são cobertos pelo manifesto externo da candidata, não pelo manifesto do estudo.
Hashes são controle de integridade acidental, não assinatura de autenticidade.

NÃO É DIMENSIONAMENTO NBR, RESULTADO DO PROJETO OU APROVAÇÃO DA PEÇA.
O piso é derivação conservadora condicionada de F2/F3/F4. Mantém Saint-Venant e
empenamento. Não é capacidade literal publicada nem limite físico universal.
PP×1 não é combinação AISI; 1% é controle matemático. Vínculos/cargas reais,
cisalhamento/interações, estabilidade, serviço, produto e ligações pendentes.
