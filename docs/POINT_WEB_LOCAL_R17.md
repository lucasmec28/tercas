# Introdução normal local de P, componente separada R17

## Fonte e alcance

Conferência visual da ABNT NBR14762:2010 fornecida pelo usuário, SHA256
c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407:
PDF39 (§9.5.1), PDF84 (D.1/D.2), PDF85 (Tabela D.2 e notas), PDF87 (Figura D.1).
A cópia normativa e imagens de revisão ficam fora do repositório.

D.1 cobre força aplicada e reação de apoio que causem compressão na alma.
O motor já existente `support_web.mechanics` / `core.anexo_d` cobre as oito
linhas Ue de uma/duas mesas, conectada/não conectada, força interna/extremidade.
Não foi criada fórmula de resistência nem importada interação de outra norma.
§9.5.1/Anexo D não apresentam equação M+F; isso não dispensa flexão, cortante,
M–V, torção, estabilidade, força fora do plano ou ligação.

A nova rota é exclusivamente Ue, terça isolada e componente normal de P.
O caminho U simples legado não é ampliado ou modificado.
P paralela e M forte na seção da carga permanecem registrados concomitantemente;
M da seção ideal não representa máximo no comprimento finito do contato.
A força paralela não é verificada por Fnormal/FRd. As guardas legadas de
`point_contact` e `point_introduction_scope` permanecem intactas.

## Detalhes físicos, nenhum padrão de contato

O painel opt-in pede origem, mesa carregada, sinal normal que a comprime,
comprimento real c, restrição local de rotação da mesa e declaração de
força concentrada na mesa oposta (com distância livre quando presente).
Exige declarar contato centrado em x e extremos físicos em 0/L. Essas são
restrições do adaptador, não exigências normativas universais. A distância
livre ao extremo é calculada somente depois dessa declaração explícita.
O contato deve estar contido em 0/L. Não se cria apoio nem reposiciona P.
A rota é contato por mesa com alma a 90°, sem crédito a enrijecedor transversal.
Nenhuma ligação à telha ou contenção global é inferida.

Limites da Tabela D.2 preservados: c≥20mm, h/t≤200, c/t≤210, c/h≤2;
h=H−2(ri+t), raios por linha, distância de 1,5h e nota de 2,5h.
A mesa é identificada fisicamente, não selecionada pelo sinal calculado.
Fora de domínio ou sem declaração resulta pendente, nunca falha resistente.

## Inventário, conservação e leitura

`sources.extract` usa a validação isolada de demandas de `support_web` e
registra todas as combinações ELU, inclusive sem P normal. ELS é contado e
excluído. Registra posição e estados concomitantes de P e mantém reações
separadas como evidência de demanda, sem verificá-las ou dispensá-las.
Nenhum solver de barra é chamado. Não são envelopes de máximos independentes.

P_APOIO representa limite a→0+, nunca contato finito centrado em x=0.
Com P normal não nula essa linha permanece pendente nesta rota. A reação
completa do apoio permanece separada mesmo no limite. P normal zero dispensa
somente essa parcela, sem dispensar P paralela nem reações por q.

A configuração está vinculada ao fingerprint integral da origem e tem detalhe
por combinação ELU. Cálculo é botão explícito. Alterações da fonte/detalhe
invalidam o resultado do painel. Resultado mecânico, Word/JSON originais e
panorama global não são modificados. O novo JSON é sidecar separado, não se
mescla silenciosamente aos arquivos anteriores. Não há fechamento global.

O leitor salvo confere hash, inventário, fonte/ações, geometria e coerência
aritmética com replay escalar local F/FRd e domínio, sem chamar extração ou solver de barra. A leitura nunca substitui o registro por um novo cálculo; divergência é rejeitada. Hash não é assinatura nem
comprovação de realidade física, nem proteção contra reescrita deliberada
completa. Flags de aprovação global, ligação, introdução completa, reação
verificada, condições físicas comprovadas e componente paralela são false.

## Verificação

Testes sintéticos cobrem demanda mista, leitura sem solver com replay escalar, ausência de
informação, compressão invertida, contato extremo e duas mesas, transbordo,
limite matemático, P normal zero, inventário completo por famílias de
combinação, mutações de fonte e resultados, escopo Ue/terça e painel opt-in.
Reutilização da fórmula é protegida também pelos testes já existentes das
12 linhas da Tabela D.2 com oráculo Decimal independente.
Nenhum dado privado ou projeto real usado. Não publicado.
