# Critério ELS linear no panorama: módulo separável R11

Base inicial: `0cc446e`; revisão de cobertura sobre o candidato não publicado `aa1eef2`. Esta entrega não altera `global_verification.py` nem `study_completion.py`, não publica e não executa membro/AppTest. A implementação é `tercas/isolated_service_panorama.py`.

## Contrato e alcance

`apply(result, records)` autentica `isolated_service_component.saved(result)` e retorna uma cópia dos registros acrescida das comparações e o binding. A ausência de componente retorna os registros intactos e binding nulo. Fonte presente inválida não é ocultada.

Cada item do inventário recebe identidade própria `ELS:<id>:combined_point_linear`, inclusive o caso de sucção característica isolada da nota f, cuja combinação preparada é preservada exatamente. O panorama não substitui a sucção pelo caso original mais próximo e não acrescenta PP/CP. Não altera os valores/evidências da flecha anterior nem verificações concretas de modelo. Uma exceção estrita no inventário aposenta somente a tentativa automática MSE indisponível, sem critério próprio, conforme o recorte abaixo. O marcador genérico `combined_ELS_scope` é substituído por cobertura vinculada do cálculo declarado, não por aprovação física. Campo, crivo MLE e configuração completos produzem uma condição de cobertura `meets`, sem índice, independentemente de a comparação numérica atender, exceder ou atravessar 1. Lacunas concretas permanecem `pending` com motivo específico. Não cria gate MODEL fixo nem requisito universal novo de campo, certificado, ensaio, GMNIA ou giro.

O vínculo inclui o pacote autenticado completo, fontes densa/compacta, entrada, configuração com ponto/direção/corda/critério, combinação, domínio do modelo e identidade da fonte normativa. Não basta trocar rótulo ou refazer hash de números arbitrários. A verificação de origem continua pertencendo ao leitor completo do consumidor.

- `index_upper <= 1`: atende condicionalmente; índice ativo é o limite superior.
- `index_lower > 1`: excede condicionalmente; índice ativo é o limite inferior. A conclusão refere-se somente ao critério linear no ponto/corda/limite declarados, não à ruína ou à validade física do modelo.
- Intervalo que atravessa 1, inclusive `lower == 1 < upper`: pendente, com superior apenas diagnóstico.
- Crivo suficiente MLE inconclusivo: pendente, sem índice de aceitação e sem falha fictícia.
- Caso ainda não calculado: permanece explícito e pendente.
- Sucção característica explicitamente nula: somente esse caso é não aplicável.
- Escolha sem inventário: um registro de seleção incompleta evita aprovação por lista vazia.
- Domínio ausente/conflitante: nenhuma comparação é qualificada no panorama.

`validate_saved(result)` reconstrói somente a projeção aritmética a partir da componente autenticada, sem solver de membro. Exige critérios e cobertura completos e iguais à evidência autenticada, sem converter cobertura em atendimento numérico, e mantém flags globais falsas. Detecta fonte/binding alterado, critérios removidos/duplicados ou novos sem binding, anotações órfãs e resumos derivados que não correspondam aos critérios. Counts, status e os demais campos de aggregate são revalidados aritmeticamente; flags sobrescritas pelo builder não são confundidas com esses campos. O guard integrado de `display_summary(summary)` também é preservado. Histórico anterior sem binding e sem novos registros permanece intacto, mesmo se já continha a componente ELS antes da integração do panorama. Não migra nem recalcula histórico.

## Separação normativa entre cálculo, cobertura e aplicabilidade

- NBR 14762:2010 §8.1 (impressa 24/PDF30) exige modelo representativo e deformações dos esforços relevantes; remete à análise da NBR 8800. Não cria certificado físico universal como verificação adicional.
- NBR 14762 §9.8.5(a) (impressa 51/PDF57) fornece a rota de rigidez efetiva MLE sob tensões de serviço. Crivo suficiente inconclusivo é lacuna concreta de rigidez, não falha resistente ou proibição do perfil.
- NBR 8800:2008 §§4.9.8.1–2 (impressa 29/PDF39), conferidos na revisão normativa: primeira ordem elástica admitida em ELS para pequena/média deslocabilidade, sem exigir imperfeições iniciais nessa resposta. Relevância dos efeitos geométricos continua em §4.9.2.2. Não se classifica deslocabilidade pela flag angular do kernel.
- NBR 14762 Anexo A A.2.4/A.3.1–3 (impressas 69–70/PDF75–76) distingue combinações e parcelas. Deslocamento total da combinação, sem dedução de contraflecha, é contrato legítimo: A.3.2 permite dedução, não a obriga. Texto de origem vazio não cria pendência normativa. O contrato não afirma cobrir automaticamente todas as etapas/parcelas pertinentes de A.3.3.
- No modo `nbr_A1_pair`, frequentes e ascendentes com PP/CP ficam fora **somente** do par e/f selecionado. Sua cobertura recebe `not_applicable` para essa seleção, com `general_ELS_exemption=False`, fonte exata e razão explícita. Não são dispensadas do ELS geral. Ausência das fontes das notas e/f continua como pendência própria do inventário selecionado.
- A nota g da Tabela A.1 (impressa 71/PDF77) exige evitar empoçamento. Ela não é resultado do índice L/180/L/120 nem do limite declarado no ponto. A.2.4 determina combinação frequente quando deslocamentos causam empoçamento. A avaliação precisa de superfície deformada e drenagem/caminho de escoamento relevantes, ou fundamento que demonstre ausência do risco. O módulo registra essa fronteira em `SYSTEM_SCOPE`, sem reprovar, dispensar ou criar pending por caso. O requisito do sistema permanece no inventário separado, independentemente do critério escolhido.

O valor de phi e o aviso angular são preservados explicitamente em cada comparação e na cobertura correspondente. Nem o aviso de 0,05 rad nem a flag fixa `physical_first_order_applicability_qualified=False` são gates de cobertura. Isso não qualifica fisicamente giros grandes: a cobertura significa somente que a conta no modelo e nas hipóteses declaradas foi feita; evidências concretas de inadequação do modelo precisam da avaliação correspondente, sem limiar normativo inventado ou GMNIA universal.

Fonte NBR14762 primária: SHA-256 `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`, PDF recuperado fora do repositório. Nenhum PDF foi copiado para o código.

## Rota escalar automática sem critério próprio

No modo direto, o inventário pode substituir `:deflection` pendente por **rota default substituída** somente quando:

- objetivo novo tem campo, configuração e crivo MLE completos;
- `deflection_model` não existe nas entradas, portanto nenhum opt-in uniaxial/biaxial/AA foi escolhido;
- entradas raiz **e input_snapshot efetivo do caso** mostram limite ausente (`None`) e origem vazia;
- o resultado antigo é `not_evaluated`, somente com `Ml with origin`, sem índice, flecha ou conclusão numérica;
- o marcador a substituir continua pendente, sem índice.

O registro é `not_applicable` **somente à obrigação de executar essa rota automática**, sem índice: objetivo de ponto explicitamente escolhido a substituiu e sua rigidez tem prova MLE completa. Isso não declara equivalência física entre os campos e não usa cancelamento torsional para concluir uma componente flexional. Não diz que MSE/Ml antigos foram calculados. Limites antigos positivos, origens efetivas, resultados antigos calculados/falhos, métodos opt-in e todos os casos de batch são preservados. Ausência apenas no root nunca autoriza substituição: batch/referências podem injetar limite no spec efetivo. O input_snapshot e o resultado antigo estão vinculados no replay.

Fonte NBR8800:2008 conferida pela revisão: https://engcivil20142.wordpress.com/wp-content/uploads/2018/03/nbr8800_2008_1.pdf ; SHA-256 `bd34211d1498d787b79164a64b48c00815b5934a5993caccc2a48d7d9c2bbe89`, 1.793.517 bytes. §§4.9.8.1–2: impressa 29/PDF39; §4.9.2.2: impressa 24/PDF34. Arquivo não copiado ao repositório.

## Hooks já integrados e preservados

1. Em `global_verification.build_global_verification`, após a aplicação do panorama NBR atual e **antes** de `aggregate`, importar `apply` e `BINDING` deste módulo e executar `records, service_binding = apply_service(result, records)`.
2. Depois de `aggregate` e das flags de alcance já existentes, inserir `summary[SERVICE_BINDING] = service_binding` somente quando não nulo. Fazer isso antes do hash global eventualmente registrado em `roof_top_nbr_binding`. Não mudar as flags falsas nem a lista independente já utilizada pelo agregador.
3. Em `study_completion.show_global` e `_report_global`, no mesmo bloco de validação após EN/NBR, chamar `isolated_service_panorama.validate_saved(result)`. O leitor retorna sem alteração para histórico sem integração ELS.
4. Executar no integrador os testes da composição e os dois AppTests já existentes do consumidor. Nesta entrega, nenhum teste UI ou solve novo foi executado.

A inserção antes do hash global evita invalidar a fonte congelada de `roof_top_nbr`; inserir o binding depois de selar esse hash não é permitido. A fonte EN não é alterada.

## Verificação desta entrega

Os testes de projeção usam o consumidor autenticado simulado para isolar classificação/vínculo, sem fingir ser validação física. Um teste adicional utiliza componente pending real, construída sem solver, para verificar a chamada à autenticação e rejeição da alteração. Os testes reais do campo/crivo/replay já pertencem à entrega anterior integrada.

Regressões: fronteiras em 1; lower versus upper na falha; MLE insuficiente; fonte específica nota f; zeros explícitos; seleção vazia; conflito do modelo; corrupção/remoção/duplicação; point/direction/criterion; flags físicas; histórico; ausência de mutação; marcador ausente/duplicado; cobertura adulterada; cálculo completo sem gate físico genérico; warnings angulares preservados; exclusão limitada ao par e/f; fronteira do empoçamento.


Esta revisão altera apenas o candidato v1 não publicado. Panoramas candidatos anteriores precisam de reprojeção explícita a partir da componente salva autenticada; o leitor não migra a cobertura automaticamente. Histórico publicado sem esse binding permanece inalterado.
