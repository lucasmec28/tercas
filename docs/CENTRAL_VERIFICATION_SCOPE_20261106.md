# Verificação dirigida à travessa central

## Contrato

O botão de cálculo Vlasov solicita `three_girt_middle_verification_v1`. A demanda resultante registra `verification_scope`, vinculado ao fingerprint das entradas. O solver recebe exatamente as mesmas entradas, resolve as três travessas e mantém as mesmas ações externas 0,5/1/0,5, PP integral, ligações, rigidez, deslocamentos, forças e reações.

A API `calculate(data, config)` sem a opção continua disponível para reproduzir o contrato histórico. O app passa explicitamente `verification_scope=SCHEMA`. Abrir um resultado antigo, mudar a combinação exibida ou montar seu panorama não o converte. É preciso solicitar um novo cálculo para obter o novo registro. Os schemas/configurações e leitores de componentes não foram redefinidos: o hash da demanda consumida inclui o novo registro quando presente, impedindo reutilizar componentes calculados para outro escopo.

## Seleção dos critérios

Apenas `middle` alimenta índices e critérios EN, referência NBR N+M, G8.1, ELS horizontal, alternativa uniaxial e cortante da alma apresentados. O panorama novo usa `three_girt_middle_inventory_v2`; o leitor continua aceitando o inventário histórico v1 sem o reconstruir. A integridade das fontes, combinações, cobertura e equilíbrio ainda é conferida para a rede completa antes da seleção.

Os snapshots completos dos componentes são preservados como evidência técnica; a apresentação usa cópias filtradas depois da validação. A tabela mecânica detalhada continua mostrando as três barras, identificada como contexto, sem concluir resistência das extremas. Nenhuma projeção de apresentação volta para o solver ou para um leitor de hash.

A extração de reações para resistência local dos apoios valida toda a rede antes de selecionar os dois apoios centrais. As estações intermediárias de todas as barras e a prova de equilíbrio permanecem na memória de origem. Reações externas de outras travessas não criam pendências locais da central.

## ELS e entorno elástico

No escopo central, o crivo local normal e a comparação do limite horizontal usam os trechos da central. Um crivo inconclusivo na superior/inferior não vira falha resistente nem pendência local da central. O crivo conjunto original permanece salvo e é mostrado separadamente como informação sobre a hipótese de rigidez bruta do entorno.

Isso **não** demonstra rigidez efetiva real do entorno, ELS físico completo ou estabilidade. O resultado central continua condicionado ao modelo linear bruto declarado; alterar rigidez real exigiria outro modelo/cálculo, nunca corrigir apenas a flecha mantendo reações incompatíveis. A lacuna de estabilidade, primeira ordem, tirantes e ligações continua explícita. Nenhum apoio ideal é criado e nenhuma aprovação global é emitida.

## Verificação

`tests/test_three_girt_middle_scope.py` cobre igualdade exata das 19 combinações mecânicas, seleção central, preservação das três barras, validação da rede inteira, leitura histórica sem solver, proibição de reutilizar hashes de outro escopo, guardas ELS separadas, exportação Word sem cálculo e seleção dos apoios centrais após equilíbrio completo.
