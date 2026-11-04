# Revisão independente do consumidor implementado

Aprovação restrita: comportamento do comparador ideal e do diagnóstico discreto consistente com a demonstração anterior. Nenhuma liberação de capacidade física, H4 real, interação biaxial ou dispensa F4 da alma.

Executados onze grupos independentes, cobrindo 72 combinações de seis perfis, seis vãos (incluindo 3501.25 e 5999.99 mm) e dois sentidos; 36 diagnósticos discretos; entradas fora de domínio; inversão Vlasov/FSM; zero; NaN/Inf/bool; primeiro escoamento e beta; sinais Cs; magnitude de j; ramo racionalizado; escalamento material; bloqueios por suporte/carga/N/furos. Resultado: todos passaram.

A inspeção AST e do código confirma somente imports de biblioteca-padrão no consumidor e ausência de leitura de arquivos de resistência NBR. A prova suplementar de material remontou matrizes E=200000 e E=203000 e verificou todos os autovetores armazenados de seis casos (web_local, lips_local, lips_distortional nas espessuras 1.50 e 3.35 mm), sem alterar fontes. Todas as verificações passaram. G global 78000 e G de placa implícito em E/(2(1+nu)) são decisões explícitas distintas, sem transferência de resistência.

O delta de F4 foi revisado e aprovado apenas no escopo do componente puro próprio. O gate exige manifesto independente exato 5d48a42b3a9b9bc7717a53574b5409ab22c81902154b9075ad3f787aa08ef248, arquivos correspondentes, resultado PASS, perfil/nós/dimensões elegíveis e margem positiva de tração de ambos os lábios com seus cantos. A interpretação documental foi fornecida pela revisão independente do pai; esta revisão verificou sua incorporação e os gates do consumidor.

Para alma comprimida pura, Ma_reference_floor_Nmm=0.90*min(P,L). Mcrd identificado e Mnd permanecem null, não infinito. Classificação explícita F4_NOT_APPLICABLE_PURE_WEAK_WEB. F2/global e F3 permanecem calculados; o comprimento ainda modifica Mcre. Não se transfere a hipótese de travamento integral do exemplo RP21-01, não se afirma ausência de modos físicos no contínuo e não se declara cláusula universal de exclusão.

A definição de componente exige N=Mx=B=V=T=0, suporta apenas os vínculos/carga ideal declarados e rejeita campos combinados. Isso não é uma aprovação do estado real nem uma dispensa D para flexão biaxial/torção. H4_for_actual_member_eligible e whole_member_approved permanecem false. O diagnóstico discreto continua separado, exige opt-in literal True, conserva Mcrd identificado null e não oferece capacidade H4; seu bound racional continua arredondado para baixo.

Novos controles independentes: seis perfis × cinco ações × cinco valores não elegíveis em ambas as entradas, lado lábios, flag puro false/não booleano, alteração de perfil/nós/centroide e manifesto adulterado. Todos rejeitados. Os 36 casos web testados retornaram exatamente 0.90*min(P,L), sem Mnd/Mcrd artificial.
Os dois pontos de robustez identificados foram corrigidos pelo autor e novamente testados:
- full_DSM agora impõe beta no intervalo [0.4,2), lambda local verdadeiro e lambda distortional <=5. Testes independentes de rejeição passaram.
- reference_capacity agora chama verify_sources antes de operar. Um teste independente com bloqueio simulado de verify_sources confirmou que a API pública falha fechada e não retorna capacidade. A verificação real das fontes e dos hashes de cada modo também passou.

Nenhum bug impeditivo permanece nos caminhos restritos revisados.
Reprodução:
python outputs/tercas_aisi_weak_capacity_20261104/independent_review/test_consumer_independent.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python outputs/tercas_aisi_weak_capacity_20261104/independent_review/check_material_independent.py

A primeira tentativa do teste de ausência de NBR usava busca textual ampla e acusou erroneamente a substring de “unbraced”; foi corrigida para inspecionar imports e caminhos literais via AST. Nenhuma mudança no consumidor foi necessária.

Hashes da versão inspecionada:
- weak_capacity.py: 2136c382bfaec30f4ad665583d0f8585d9f8d805302a68d6ba7d6d06ba481d9d
- check_material_scaling.py: 0140831d5b96848d6496af7f122a9be3103041853a705a7e70c82927059df6ce
- MATERIAL_SCALING.json: 7147b3ab568f598028ee7f3c8ecfc2d9f90ae2d40ab484f512f8df06999a4613

Maior resíduo relativo dos autovetores verificados: 2.04376e-07.
