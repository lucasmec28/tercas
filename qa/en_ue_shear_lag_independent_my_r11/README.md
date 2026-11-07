# Qualificação independente de My concomitante ao suplemento Mx

Candidata R11 v3 não publicada. A revisão/hash técnico mudou intencionalmente sob a decisão do integrador; esta alteração não é migração automática de snapshots antigos. Fontes históricas v1/v2 e recibos anteriores não foram editados.

- Execução final: 24 testes escalares aprovados em 6,34 s, com XML e log nesta pasta.
- Os dois sinais de My são cobertos: L=6000 mm, qMx=0,03 N/mm, Pmx=−135 N em 3000 mm resultam em zonas Mx de 1500/3000/1500 mm; My uniforme tem Le=6000 mm e sua própria dispensa.
- O teste compara a prova Mx com o caso puro: pisos, intervalos, inércia e auditoria local/distorcional idênticos. Operadores My não mudam.
- Flags recebidos falsamente verdes não substituem `assess` da fonte. Curling My e ambos os operadores My elegíveis continuam necessários.
- Nenhum solver de membro, UI, AppTest ou suíte completa executado nesta alteração. O aceite estático do revisor é restrito ao domínio acima.
- `initial_environment_attempt.log` registra apenas a tentativa inicial sem pytest no primeiro caminho; nenhum teste chegou a executar nessa tentativa.

Comando final: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:tests:/workspace/scratch/200bd23c4a9b/tercas_test_dependencies_r11:/workspace/scratch/200bd23c4a9b/connections_audit/test_dependencies OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q tests/test_en_ue_family_shear_lag.py --junitxml=qa/en_ue_shear_lag_independent_my_r11/scalar_tests.xml`.

O suplemento não resolve shear lag My, não fornece tensor comum e não aprova barra/projeto globalmente. A futura extensão My ainda depende das provas geométricas, locais/distorcionais e de distribuição de tensões descritas na pesquisa.
