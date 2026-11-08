# Verificação focal do fechamento complementar

Base: 1a335043f4fdf4454b450cd508f6c4eb6b53d812.
498 testes passaram em 22,60 s; nenhuma falha/erro/skip. Execução monothread.
Inclui testes de panorama, inventário, EN/NBR/ELS, apoios escalares, conservação dos leitores antigos e interface do complemento. Não é a suíte integral nem qualificação física de projeto.

Comando: python -m pytest -q tests/test_global_verification.py tests/test_isolated_en_panorama.py tests/test_completion_requirements.py tests/test_nbr_family_panorama.py tests/test_isolated_service_panorama.py tests/test_support_web_completion.py tests/test_support_web_application.py tests/test_support_web_sources.py tests/test_support_web_mechanics.py tests/test_ui_support_web_completion.py tests/test_ui_support_web.py

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1; PYTHONPATH incluiu a árvore, tests e as dependências de teste fornecidas no executor.
