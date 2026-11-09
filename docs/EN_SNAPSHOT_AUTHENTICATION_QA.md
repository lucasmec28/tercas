# QA do reparo do leitor EN

Base local: 332e478, com árvore idêntica à R21 publicada em 6e00d887. Implementação inicial verificada: 8fa3fbc. O fechamento adicional de desempenho e autoridade está registrado abaixo.

## Verificações concluídas

- 193 testes focais: certificados intervalares, testemunhas, transporte de centroide, escopo central/integral, compatibilidade histórica e EN6.27. Inclui contornos 1,20 / 1,50 / 3,35 mm, B não nulo, aliases e leitura fria/quente. Esta rodada antecedeu apenas a memoização da aritmética pura.
- 49 testes finais no código congelado: prova matemática, ataques coordenados com hashes refeitos, cache seguro, UI EN (cálculo, reabertura e invalidação), panorama e migração de caches. 70,48 s, sem timeout.
- 10 testes finais de classificação e inventário do panorama. 3,12 s.
- Importação/visualização preservam a entrada histórica. Após cálculo novo explícito, a entrada esperada difere somente pelos marcadores vigentes de cargas no centro de torção e exclusão local dos apoios.
- Os testes proíbem network.solve, shear_interaction.envelope e field_envelope.stress_extrema na leitura.
- Ataques incluem zeros coordenados em folhas/pais/testemunhas/política do centroide, testemunha falsa, troca de certificado de espessura, checks/grupo/resumo/banner de panorama alterados, cobertura incompleta e cache quente com argumentos modificados.
- O cache aritmético aceita somente entradas reais finitas, usa todos os coeficientes reconstruídos, escalas, parâmetros, caixa e revisão, e guarda apenas resultados finitos não negativos. O retorno é um escalar imutável. Não há confiança em hash declarado ou identidade do objeto.

## Medidas de replay final

Ensaios sintéticos CT, fy = 250 MPa, sem alteração dos fingerprints após leitura:

- 1,20 mm, q normal/paralela = +0,1 / −0,1 N/mm: frio 1,470 s; quente 0,277 s. Normal, cisalhamento e interação atendem com prova autenticada.
- 3,35 mm, q normal/paralela = +3 / −3 N/mm: frio 0,796 s; quente 0,202 s. Os três critérios apresentam excesso autenticado.

## Histórico das execuções

A primeira rodada UI ampla foi interrompida para diagnóstico, não concluída. O diagnóstico isolado terminou com uma falha de expectativa antiga do teste: após cálculo novo, o teste ainda esperava ausência dos dois marcadores já adotados na R21. Nesse primeiro episódio não houve timeout. O teste foi corrigido preservando o assert de entrada original antes do cálculo e comparando depois com a preparação explícita vigente. A rodada final de 49 testes passou com código e expectativas congelados. A captura de stack aos 30 segundos foi diagnóstica, não um timeout da aplicação.

Não foi executada a suíte completa do repositório. Não há ativação da família ampliada nem publicação neste reparo.


## Fechamento adicional: domínio 1,20 mm com ELS

Este é um segundo episódio, distinto da expectativa antiga do teste: o AppTest `test_reduced_axial_coexists_with_service_and_saved_exports[1.2]` apresentou timeout real de 60 segundos no clique de cálculo. A publicação permaneceu suspensa durante o reparo.

Controle R21 local 332e478: o mesmo cenário passou em 39,86 s; repetição para memória passou em 36,74 s com pico RSS de 329.340 KiB. O cálculo EN levou 13,70 s e as leituras antigas cerca de 0,33 s.

No v6 anterior à otimização final, o cálculo EN levou 56,90 s e a primeira validação 43,63 s. Havia mais de 150 mil resultados aritméticos distintos, excedendo o cache inicial. Uma vetorização parcial melhorou o custo, mas ainda ocorreu timeout; portanto esses ensaios não foram tratados como aprovação.

O fechamento em 42212a4 mantém os mesmos 75 controles intervalares por face, com a mesma ordem de operações e arredondamentos, executados em lotes de faces com campo/caixa idênticos. O oráculo escalar permanece somente nos testes. Foram verificadas 128 paridades bit a bit, um certificado completo com faces e folhas diferentes e a igualdade do resultado EN completo.

O cache aritmético tem teto de 196.608 entradas; o cache semântico tem teto de quatro. Ambos retêm somente resultados imutáveis de sucesso, sob SHA-256 calculado com enquadramento dos bytes reais completos e revisão. Não retêm os payloads de usuário. Falhas, valores negativos ou não finitos não são inseridos. Evicção muda custo, não decisão.

A validação semântica fria usa uma cópia própria que preserva aliases internos: serializa essa cópia para a chave, valida a mesma cópia e verifica seus bytes novamente antes de registrar sucesso. A entrada atual, inclusive substituição integral do componente, é conferida antes do retorno. A normalização de escalares ocorre somente na saída de cálculo novo, preservando bytes JSON/digests e sem alterar o argumento original ou históricos.

A autoridade dos operadores dos sete perfis é conferida no registro local qualificado, independentemente da presença da componente opcional EN6.27. A leitura quente também repassa os gates dos arquivos-fonte manifestados e o perfil pinado. Testes cobrem coeficiente não nulo adulterado, hashes refeitos e EN6.27 removida ou pendente.

Resultados finais locais em 42212a4:

- 61 testes focais passaram em 7,64 s. Os avisos numéricos pertencem ao ensaio proposital de overflow.
- O AppTest completo de 1,20 mm com ELS passou, exit 0, em 65,72 s totais. Cada execução individual manteve o timeout original de 60 s.
- Cálculo EN: 18,99 s. Primeira validação: 8,17 s. Leituras quentes: 1,12–1,21 s.
- Pico RSS: 535.340 KiB, contra 329.340 KiB na base. Houve redução frente aos ensaios intermediários de 709.644 / 605.856 / 592.692 KiB, mas permanece aumento de 206.000 KiB. Não se afirma equivalência de memória à R21 nem adequação automática a um limite de hospedagem.
- Retenção medida do cache aritmético: 25.569.552 bytes, 150.656 entradas. Retenção semântica: 477 bytes, uma entrada. Esses limites são globais do processo, não multiplicados por sessão.

O controle final integrado NBR + EN é realizado separadamente. Estes resultados locais não constituem publicação ou aprovação global de engenharia.
