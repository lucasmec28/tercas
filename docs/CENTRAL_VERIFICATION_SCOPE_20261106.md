# Verificação dirigida à travessa central

## Contrato

O botão de cálculo Vlasov solicita `three_girt_middle_verification_v1`. A demanda resultante registra `verification_scope`, vinculado ao fingerprint das entradas. O solver recebe exatamente as mesmas entradas, resolve as três travessas e mantém as mesmas ações externas 0,5/1/0,5, PP integral, ligações, rigidez, deslocamentos, forças e reações.

A API `calculate(data, config)` sem a opção continua disponível para reproduzir o contrato histórico. O app passa explicitamente `verification_scope=SCHEMA`. Abrir um resultado antigo, mudar a combinação exibida ou montar seu panorama não o converte. É preciso solicitar um novo cálculo para obter o novo registro. O hash da demanda consumida inclui o registro quando presente, impedindo reutilizar componentes calculados para outro escopo. O novo recorte de cálculo EN tem schema próprio, descrito abaixo; os demais componentes conservam os contratos anteriores.

## Seleção dos critérios

Apenas `middle` alimenta índices e critérios EN, referência NBR N+M, G8.1, ELS horizontal, alternativa uniaxial e cortante da alma apresentados. O panorama novo usa `three_girt_middle_inventory_v2`; o leitor continua aceitando o inventário histórico v1 sem o reconstruir. A integridade das fontes, combinações, cobertura e equilíbrio ainda é conferida para a rede completa antes da seleção.

Os snapshots históricos completos dos componentes são preservados como evidência técnica; a apresentação usa cópias filtradas depois da validação. Nos novos cálculos EN, só a resistência da central é calculada e gravada. Os demais componentes continuam completos. A tabela mecânica detalhada continua mostrando as três barras, identificada como contexto, sem concluir resistência das extremas. Nenhuma projeção de apresentação volta para o solver ou para um leitor de hash.

A extração de reações para resistência local dos apoios valida toda a rede antes de selecionar os dois apoios centrais. As estações intermediárias de todas as barras e a prova de equilíbrio permanecem na memória de origem. Reações externas de outras travessas não criam pendências locais da central.

## ELS e entorno elástico

No escopo central, o crivo local normal e a comparação do limite horizontal usam os trechos da central. Um crivo inconclusivo na superior/inferior não vira falha resistente nem pendência local da central. O crivo conjunto original permanece salvo e é mostrado separadamente como informação sobre a hipótese de rigidez bruta do entorno.

Isso **não** demonstra rigidez efetiva real do entorno, ELS físico completo ou estabilidade. O resultado central continua condicionado ao modelo linear bruto declarado; alterar rigidez real exigiria outro modelo/cálculo, nunca corrigir apenas a flecha mantendo reações incompatíveis. A lacuna de estabilidade, primeira ordem, tirantes e ligações continua explícita. Nenhum apoio ideal é criado e nenhuma aprovação global é emitida.

## Verificação

`tests/test_three_girt_middle_scope.py` cobre igualdade exata das 19 combinações mecânicas, seleção central, preservação das três barras, validação da rede inteira, leitura histórica sem solver, proibição de reutilizar hashes de outro escopo, guardas ELS separadas, exportação Word sem cálculo e seleção dos apoios centrais após equilíbrio completo.

## Cálculo EN restrito, sem redução da rede

Nos novos cálculos com `three_girt_middle_verification_v1`, a componente EN grava `three_girt_EN_middle_normal_shear_signed_union_v5` e uma cópia exata do marcador da demanda. Depois de validar a fonte física das três travessas, seleciona os trechos `middle` antes do transporte de ações, partição de sinais e envelopes de tensão normal, cisalhamento e interação. As fórmulas, certificados de seção, sinais, cargas, rigidezes, Ne e condições de estabilidade não mudam. A validação barata dos campos torsionais ELU continua abrangendo as três travessas. A seleção não volta ao solver.

A fonte e seu hash continuam abrangendo todas as combinações ELU/ELS e a rede inteira. O leitor v5 exige o marcador central válido na demanda e na componente, cobertura exata e ordenada dos trechos centrais, somente `middle` em `per_member` e a integridade física da rede completa. Hashes refeitos não dispensam essas verificações semânticas. As flags de aprovação continuam falsas.

Os schemas EN v1–v4 continuam com a cobertura original das três travessas, inclusive quando já pertencem a uma demanda com marcador central. Não recebem marcador novo, não são recalculados e não são promovidos durante leitura/exportação. Trocar apenas o schema ou marcador, retirar trechos ou substituir o conjunto de membros é rejeitado mesmo com hashes refeitos. Sem marcador na demanda nunca se presume o novo recorte central. SHA-256 é integridade de conteúdo, não uma assinatura que autentique a origem de um arquivo inteiramente reconstruído.

`tests/test_three_girt_en_middle_calculation.py` compara exatamente a central antes/depois em 1,20/1,50/3,35 mm, mede chamadas reais dos envelopes, verifica ausência de trabalho resistente nas extremas, conserva a fonte física inteira e exercita leitura/Word sem cálculo, contratos históricos e adulterações com hashes refeitos. Isso não cria aprovação global, prova da rigidez efetiva do entorno ou dispensa de estabilidade.

### Evidência focal de 06/11/2026

Execução sequencial, `OPENBLAS_NUM_THREADS=1` e `OMP_NUM_THREADS=1`, sem aumentar nenhum timeout:

- 102 testes novos de contrato passaram (28,85 s); os 98 testes focais de consumidores e leitores antigos também passaram (211,83 s). A central permaneceu exatamente igual em memória, incluindo os limites, testemunhas, sinais, transporte e certificados; as fontes mecânicas também ficaram iguais, salvo o marcador explícito já existente.
- No caso direto de 1,20/1,50/3,35 mm, as chamadas reais de envelope caíram de 24/21/9 para 3 em cada caso, todas da central. As nove validações baratas de campos torsionais foram preservadas: três por travessa.
- Os três testes UI que excediam 60 s passaram no limite original. EN no integrado de 1,20 mm: 33,76 s e 219 envelopes. Serviço+EN de 1,20 mm: 20,56 s e 219 envelopes. Serviço+EN de 1,50 mm: 20,90 s e 180 envelopes. Em todos, zero envelopes nas extremas e 36 trechos centrais salvos.
- O clique de cálculo completo no integrado de 1,20 mm levou 54,47 s, deixando apenas 5,53 s de margem para o prazo de 60 s. Reexibição: 6,74 s; exportação: 2,73 s. Os quatro leitores e os dois sidecars passaram sem modificar ou resolver novamente a rede.

Esses tempos são medições do ambiente de QA, não garantia universal de latência. Testes AppTest pesados devem ser executados serialmente, sem carga concorrente, mantendo os limites originais. Esta evidência focal não substitui a suíte final de integração nem qualificação física/global.
