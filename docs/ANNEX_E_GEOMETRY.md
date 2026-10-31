# Conversão automática de linha média — candidato0.4.1

Base: cópia do0.4.0 publicado; sem publicação deste candidato.

## Fontes realmente conferidas
- NBR14762:2010 FiguraE.1, p84/PDF90: imagem `outputs/tercas_cbca_examples/nbr_annex_fig.png` inspecionada visualmente.
- CBCA2014, Ex08 p69/PDF70: `ex08_geom.png` renderizada do PDF e inspecionada. O exemplo escreve am=bw−t, bm=bf−t, cm=D−t/2.
- U simples: am=h−t, bm=bf−t/2, cm=0, conforme linha média da FiguraE.1.
- U enrijecido: am=h−t, bm=bf−t, cm=D−t/2. Corrige a aproximação anterior cm=D−t usada apenas em estudos sintéticos, sem assumi-la como convenção oficial.

## Implementação
- `weak_catalog.nominal_mean_line` calcula as três dimensões da seção nominal selecionada, registra origem e dimensões de entrada. Nenhum raio é inferido; ri original permanece intacto inclusive quando ausente.
- UI convencional mostra dimensões/origem no expansor, não pede preenchimento manual. Entradas antigas explicitamente completas são preservadas; outro modelo de linha média não pode ganhar propriedades de catálogo automaticamente.
- Modo explícito só automatiza com dimensões iguais à conversão nominal comprovada, dentro de tolerância numérica1e-6. Fora disso, somente esta rota fica parcial. Não é tolerância normativa de resistência; evita misturar seções distintas.
- Comparações xm/x0/Iy de linha média idealizada versus catálogo com cantos tornam-se informativas. Diferença3% não bloqueia a rota e não é exigência da norma.
- Guarda de coerência de r0 e propriedades alteradas continua ativa. Único Wy original com diferença>3% (U75x40x3,35, linha112) é menor que reconstrução Iy/distância extrema: conserva o menor valor com aviso, somente quando todo conjunto de propriedades publicado permanece original e r0 coerente. Não corrige nem inventa valor da fonte.
- Continua hipótese provisória de Ml,y no lado alma; não resolve por si críticos do lado oposto ou Mdist,y. Sem cópia bilateral e sem aprovação global.

## Evidências
- CBCA Ex08: am98,8mm,bm48,8mm,cm16,4mm; xm17,3738mm, x042,9078mm, j60,6466mm, compatíveis com impressos17,37/42,9/60,6mm (arredondamento).
- 209/209 registros originais geram propriedades auxiliares AnexoE; não são209 dimensionamentos completos.94 registros apresentam avisos da idealização geométrica.
-64 testes focados +324 subtestes passaram; suíte integral e revisão final nos logs/REVIEW.md.

Regressão integral final: **219 testes +692 subtestes passaram**,120,85s de suíte, `pytest_full.log`,31/10/2026 19:20UTC. Inclui UI sem entradas geométricas convencionais, preservação do selo provisório, casos CBCA e todos os ramos anteriores. Revisão independente final em REVIEW.md sem bloqueio adicional. Não publicado.
