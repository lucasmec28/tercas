# NBR M-V forte/alma da familia completa Ue, R11

## Base normativa e alcance

A conferência visual da NBR14762:2010, páginas impressas 50-51 (páginas 56-57 do
PDF fornecido), confirma:

- Sem enrijecedores transversais de alma, §9.8.4 exige
  `(MSd/MRd)^2 + (VSd/VRd)^2 <= 1` na mesma seção.
- O denominador MRd é exclusivamente de §9.8.2.1. O mínimo entre local, FLT e
  distorcional pertence a outras verificações e não substitui esse denominador.
- VRd é de §9.8.3, com h igual à altura plana da alma. No contorno nominal próprio
  adotado, `h_flat = h_external - 2*(ri+t)`; `kv=5`, sem crédito de enrijecedores,
  e coeficiente de ponderação 11/10.
- Cada alma de seção com múltiplas almas deve resistir à sua parcela. Este módulo
  trata somente a alma única da Ue. Não transfere VRd para cortante fraco nas mesas.

`tercas/nbr_family_mv.py` é um módulo puro e versionado. Não altera aplicativo,
membro, panorama, interface ou dados históricos. Não prepara geometrias, não
inicia solver, não calcula autovalores e não acessa fontes EN. Não qualifica
forças locais, torção/bimomento, eixo fraco, estabilidade, ELS ou segurança global.

## Fontes e denominadores

`build(record, sources, span_mm)` recebe um registro ELU e o pacote de fontes
**já autenticados integralmente pelo consumidor**. O hash registrado pelo módulo
é vínculo de conteúdo, não uma autoridade que autentica dados arbitrários.

A componente local deve ser única na rota `own_rounded_contour`, ter índice
utilizável e capacidade igual à fonte `strong.local.MRd_Nmm`. Uma fonte local MLE
não precisa fornecer Ml: os quatro perfis fora da Tabela 12 são cobertos quando
seu MRd local próprio está disponível. Resistência nominal Pierin, mínimo FLT/D,
pisos de energia e resistências EN não são usados como denominador local.

A geometria plana e o material de VRd vêm do mesmo `source_binding` de MRd.
O quadrado de VRd é conservado exatamente em Fraction, usando coeficientes
normativos decimais exatos:

- Escoamento: `(0.6*fy*h*t/1.10)^2`.
- Intermediário: `(0.65*t^2/1.10)^2*5*fy*E`.
- Elástico: `(0.905*E*5*t^3/(h*1.10))^2`.

As comparações de esbeltez também são feitas ao quadrado e em aritmética exata.
`VRd_lower_N` e `VRd_upper_N` são apenas limites de exibição da raiz. Nenhum deles
entra no denominador do critério. **Não se trata de piso resistente especial**:
é a fórmula normativa para a geometria/material idealizados e autenticados.
Isso não elimina a necessidade de comprovar o produto e as hipóteses físicas.
O MRd fornecido permanece o escalar binário calculado pelo provedor existente;
a prova de envelope é relativa a esse escalar, sem alegar precisão física extra.

## Esforços e prova contínua

Para um caso com q, P e posição a assinados, o módulo conserva exatamente:

- `RA = q*L/2 + P*(L-a)/L`;
- antes de P: `M=RA*x-q*x^2/2`, `V=RA-q*x`;
- depois de P: `M=RA*x-q*x^2/2-P*(x-a)`, `V=RA-q*x-P`.

M e V são concomitantes. Os dois lados de P interior e os limites físicos dos
apoios são mantidos. Quando P está exatamente sobre um apoio, somente o lado
físico da barra é coberto: essa força não cria cortante interno fictício.
A posição de P é fixa em cada combinação; não se afirma envelope de P móvel.

Em cada trecho, o índice é um polinômio de grau no máximo4. Coeficientes de
Bernstein racionais encerram todos os seus valores no intervalo. Subdivisão
exata de de Casteljau mantém uma partição completa, sem lacunas, do trecho.
Todas as folhas terminais são registradas com intervalo, cinco coeficientes e
limite superior. O maior desses limites é um teto demonstrado de todo o vão.

A testemunha concomitante fornece somente um limite inferior do máximo.
`witness_is_exact_maximum=False` impede tratar sua coordenada como solução
analítica exata. São registrados separadamente `maximum_lower_exact`,
`maximum_upper_exact`, `index_squared_lower` e `index_squared_upper`.
As conversões para float são dirigidas para fora. A tolerância aritmética
relativa 1e-10 limita o intervalo reportado, não altera o limite resistente 1.

- `meets`: teto exato <= 1.
- `fails`: testemunha inferior exata > 1.
- `boundary_inconclusive`: limite inferior <= 1 < teto.

O limite operacional de 2048 subdivisões não invalida a cobertura: se atingido,
os limites continuam demonstrados e `requested_gap_reached=False`. Isso nunca
promove uma testemunha a máximo, nem transforma um teto excedido em falha.

`web_shear(...)` e o campo superior `web_shear` calculam separadamente o máximo
exato de |V| nos extremos dos trechos lineares. Essa componente não depende da
disponibilidade de MRd nem da dispensa de shear lag flexional. Não inclui
cisalhamento torsional, cortante fraco ou forças locais.

## Gate de NBR9.4

Dependência de integração: `nbr_ue_shear_lag.py`, commit original bb80924.
O registro deve conter `shear_lag_applicability`, calculado com vão físico,
dimensões externas próprias e inventário completo das ações individuais.
`build` revalida integralmente esse resultado e usa somente `axes.normal` para
M-V forte. Gate ausente/falho mantém `criterion_status=None` e estado pendente;
uma aritmética diagnosticamente acima de 1 não vira reprovação qualificada.

Se M forte é identicamente nulo, provado pelo equilíbrio completo, não se exige
resistência flexional nem esse gate. Essa dispensa particular não presume
inexistência de torção, forças locais, eixo fraco ou outros efeitos. O cortante
fraco continua explicitamente não avaliado, mesmo que seu carregamento exista.

## Proposta mínima de hook (não aplicada neste commit)

1. No consumidor autenticado, após criar `record['shear_lag_applicability']`,
   adicionar `record['strong_web_MV'] = nbr_family_mv.build(record, sources, L)`.
2. No panorama atual, substituir somente o registro `:MV` legado desse caso por
   essa componente autenticada. Qualificar apenas quando o `criterion_status`
   superior for `meets` ou `fails`, preservadas as guardas de domínio físico.
   Usar `arithmetic.index_squared_upper` como teto do índice e conservar os dois
   limites e o veredicto exato no trace. `boundary_inconclusive` é pendente.
3. Substituir `:shear` forte pelo campo superior `web_shear`, independentemente
   do gate9.4 e da disponibilidade local, preservadas as mesmas guardas de domínio.
   Usar `index_upper` e conservar `index_squared_exact`/veredicto no trace.
   Não criar nova aprovação ou linha de cortante fraco a partir desse resultado.
4. Para leitura/replay, revalidar o pacote e chamar
   `validate_saved(saved, record, sources, L)`. A função recompõe só aritmética
   racional e capacidade escalar da alma, nunca solver ou geometria.
5. Versionar a nova composição do consumidor ou congelar o replay anterior.
   Resultados históricos sem a nova componente não são migrados nem reparados.

O panorama não pode usar diretamente `arithmetic.criterion_status` se o gate
superior estiver pendente. Toda apresentação deve identificar forte/alma,
limites do máximo, mesma combinação e mesmo x, sem aprovação global.

## Verificação local

Execução limitada a testes escalares, com OPENBLAS_NUM_THREADS=1,
OMP_NUM_THREADS=1 e MKL_NUM_THREADS=1; nenhum solver ou interface iniciados.

`tests/test_nbr_family_mv.py` cobre todos os 66 perfis completos a fy=300, inclusive
MRd MLE sem Ml, três ramos e fronteiras de VRd, quatro combinações de sinais,
reversão, P nos dois apoios/interior, salto de V, carga nula, demanda fraca
separada, gate9.4 por eixo, teto inconclusivo, raiz subnormal, replay JSON,
imutabilidade e adulterações. O teste independente da prova verifica cinco
identidades racionais distintas em cada folha de grau 4 e a união integral da
partição; isso prova a identidade polinomial, não é amostragem de um máximo.

A família testada não é aprovação de produto ou projeto. O encerramento de
M-V forte/alma não resolve as demais pendências normativas/físicas do aplicativo.

Recibo: 306 testes aprovados em 7,68 s no conjunto M-V + shear-lag + biaxial +
member + panorama. Revisão estática independente confirmou a fórmula normativa,
cobertura Bernstein, limites e domínio; o revisor não executou solver/testes.
