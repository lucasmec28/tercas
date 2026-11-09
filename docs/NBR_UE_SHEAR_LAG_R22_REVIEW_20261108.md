# NBR 14762, 9.4/Tabela 7: revisão da ampliação pós-R21

**Registro preliminar preservado.** A investigação complementar posterior fechou a referência geométrica forte e conectou uma guarda versionada, conforme [relatório de entrega R22](NBR_UE_STRONG_SHEAR_LAG_GEOMETRY_R22.md). A pendência de distribuição/redução da seção descrita abaixo continua aberta. Os diagnósticos deste primeiro estágio não são certificados da geometria adotada depois.

## Resultado

**Não foi qualificada uma redução nova da seção Ue.** A revisão deixou intacto o gate suficiente de R21, seus consumidores e o histórico. A parte inequívoca da Tabela 7 foi transcrita em um diagnóstico racional isolado, sem ligação com cálculo, interface ou aprovação. Não se apresenta esta entrega como ampliação resistente ou nova cobertura dos 66 Ue.

A implementação só seria apropriada depois de fechar a ligação entre a largura normativa e o contorno arredondado, e entre a redução da largura e as propriedades efetivas. A inspeção abaixo não encontrou essa ligação completa nas passagens consultadas. Isso é uma pendência desta implementação, **não uma proibição da NBR, nem prova de que o método não possa ser fundamentado por outra referência**.

Base local imutável: `332e478cd1b26323974475dfa1fcf14327ccd216` (R21). O ramo de revisão é independente; nenhum arquivo de produção ou fonte normativa foi alterado. Nenhum PDF/imagem normativa está incluído no commit ou bundle.

## Fonte e reaproveitamento

- Fonte primária: ABNT NBR 14762:2010, PDF de SHA-256 `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.
- Conferência visual: páginas PDF 38–39, correspondentes às páginas impressas 32–33; 9.4, Tabela 7 e definições imediatamente posteriores. Páginas PDF 30–31/impressas 24–25 também foram conferidas para o contexto de métodos e elementos.
- Reaproveitada a revisão anterior registrada em `docs/NBR_UE_SHEAR_LAG_R11.md`. O autor anterior confirmou que não havia demonstrado `bf0 = bf - t + lip`, `bf0 = bf - 2(ri + t) + lip` ou regra espacial de redução. A aprovação anterior do gate conservador não é aprovação dessas fórmulas.
- Código inspecionado: `catalog_torsion_section.nominal_channel_nodes`, `nbr_ue_shear_lag.assess`, `nbr_ue_family_expansion.strong_effective_modulus`, produtores `nbr_ue_family*` e consumidores `nbr_ue_family_application`, `nbr_family_member`, `nbr_family_mv`.

Não se fez nova busca bibliográfica ampla, nem se importou método ou coeficiente da EN/AISI.

## O que está definido na fonte

1. O gatilho usa `L < 30 bf0` e força concentrada, ou várias forças concentradas com espaçamento superior a `2 bf0`. Para viga simplesmente apoiada, `L` é o vão físico; comprimentos resistentes e intervalos entre eventos não o substituem.
2. As larguras das mesas tracionada **e** comprimida entram reduzidas na determinação das propriedades geométricas. A comprimida também fica limitada pela redução local de 9.2.2/9.2.3.
3. Para a mesa de I/U/Z enrijecida na borda, a referência soma a largura livre da mesa à largura **nominal** do enrijecedor. O texto caracteriza a largura livre pela distância da face da alma à borda livre.
4. A Tabela 7 contém os dez pares exatos `L/bf0` e fator entre 6 e 30. Esses pares estão no diagnóstico. Não se atribui a um fator da tabela a função de multiplicador direto de `MRd`, nem de esforços, nem de campo longitudinal `beta(s)`.
5. Não se encontrou nas passagens lidas um desenho de mapeamento para a mesa Ue arredondada usada pelo programa, nem distribuição explícita de remoções entre mesa, lábio e cantos. A revisão também não adota interpolação/extrapolação entre/fora dos nós. Isso não afirma uma proibição normativa de interpolar; apenas evita apresentar uma política não fundamentada como texto da tabela.

## Elo geométrico: o que falta exatamente

O programa conhece as dimensões externas `h, bf, lip, t`, o raio interno `ri` e a linha média. Portanto, **não faltam coordenadas do contorno**. Faltou qualificar qual distância corresponde à largura livre de 9.4 quando há o lábio e os cantos:

- Com `r = ri + t/2`, a face interna plana da alma está em `x = t/2` e a face externa plana do lábio em `x = bf - t/2`. Sua separação é `bf - t`.
- As tangências da parte plana da mesa estão em `x = r` e `x = bf - t - r`. O comprimento plano é `bf - 2(ri + t)`.
- Essas são distâncias geométricas exatas diferentes. O fato de conhecê-las não identifica por si só a “borda livre” normativa da mesa enrijecida com uma dessas faces/tangências. A frase normativa não autoriza trocar automaticamente largura livre por largura plana usada no MLE.
- A largura nominal do lábio é a dimensão externa declarada, não seu comprimento plano. Misturar uma dessas larguras de mesa com um lábio plano produziria ainda outra convenção.

O diagnóstico sintético `200 x 75 x 20 x 2`, `ri = 3 mm`, `L = 2700 mm`, mostra a consequência, **sem escolher uma proposta**:

- majorante externo já usado: `bf + lip = 95 mm`, fronteira suficiente 2850 mm;
- proposta não qualificada baseada nas faces: `bf - t + lip = 93 mm`, fronteira 2790 mm;
- proposta não qualificada baseada na parte plana: `bf - 2(ri + t) + lip = 85 mm`, fronteira 2550 mm.

A última proposta dispensaria o efeito nesse vão e a anterior não demonstraria dispensa. Logo, essa escolha não pode ficar oculta em um arredondamento ou no nome da variável. Nenhum desses exemplos determina `bf0` exato para produção. O eixo fraco também não recebe automaticamente metade da alma: a classificação das placas após a rotação precisa de justificativa própria.

## Elo das propriedades: restrição mais estreita que um solver universal

**Flexão forte escalar não exige, por si só, um tensor efetivo 2D completo.** Na integração convencional de `A`, `Sy` e `Ix`, deslocar uma mesma largura removida ao longo de `x` em uma mesa horizontal com `y` constante não altera esses integrais. Esta revisão não usa a necessidade de um operador universal como bloqueio artificial a uma futura extensão forte restrita.

O problema que resta é identificar quais partes a largura reduzida representa. O lábio e os cantos têm ordenadas diferentes da mesa plana. Se forem incluídos na área “mesa mais lábio”, conhecer somente a área final, mesmo preservando o centroide vertical, não determina `Ix`.

A contraprova exata usa apenas uma polilinha sintética de cantos vivos: alma de 200 mm, mesas de 75 mm, lábios de 20 mm e espessura 2 mm. Não é o contorno real, não é validação de um Ue do catálogo e não propõe seções físicas alternativas. Aplicando apenas como dado algébrico o nó `L/bf0 = 20`, fator `0,91`, à área das duas montagens mesa+lábio, obtêm-se três distribuições ilustrativas com a mesma área 745,8 mm² e centroide vertical zero:

- mesma área removida das mesas horizontais: `Ix = 4 642 000 mm4`;
- mesma área removida das pontas verticais dos lábios: `Ix = 4 740 893,8315 mm4`;
- peso uniforme em toda a montagem, **somente como contraprova**: `Ix = 4 655 440 mm4`.

As diferenças são racionais exatas. Nenhuma distribuição é adotada. Elas mostram especificamente por que uma área-alvo, ou um `beta` uniforme escolhido para consegui-la, não fecha o cálculo forte quando a participação do lábio/cantos não está estabelecida. Se uma referência definir que só a parte horizontal deve ser reduzida e como tratar seus cantos, o problema escalar poderá ser menor e deverá ser retomado nesse escopo.

## Composição com local, FLT e distorcional

A rotina forte existente mantém cantos e remove trechos planos da mesa comprimida e do lábio, com prova de alma integral reavaliada no centroide efetivo. Ela não recebe uma largura de shear lag, não reduz a mesa tracionada e não constitui, sem nova prova, aplicação de 9.4.

Uma ponte futura deve:

1. Definir as larguras/partes reais reduzidas nas duas mesas, nos dois sinais. Documentar cantos, lábio e centroide resultante.
2. Respeitar o limite local da comprimida e revalidar as hipóteses de tensão, lábio e alma da rotina MLE. Não multiplicar cegamente duas reduções: uma largura real de 100, largura local de 70 e limite de shear lag de 80 não transformam, só pelo texto lido, a largura em `70 x 0,8 = 56`; os limites isolados apenas permitem comparar com 70. Isso não é prova de que basta aplicar `min` ao contorno inteiro sem reequilíbrio.
3. Identificar o papel das propriedades efetivas em cada mecanismo NBR realmente usado. Não manter automaticamente um módulo/estado local, referência de FLT ou redução distorcional cuja hipótese tenha mudado. Também não exigir sem fundamento que todo problema elástico bruto seja refeito.
4. Entregar nova evidência versionada por combinação/eixo/sinal, vinculada às mesmas dimensões, ações e material. Somente ela poderá substituir a pendência de 9.4 no consumidor; capacidades nominal e própria continuam separadas.

As forças no CT, fatores de PP 1,25/1,0 e comprimentos resistentes independentes de `L` não resolvem essas ligações de largura/propriedades. Foram mantidos intactos. Efeitos locais de apoio/carga, ligações, ELS combinado, U simples e perfis genéricos continuam fora desta revisão.

## Entrega e verificação

Arquivos novos, todos fora do cálculo de produção:

- este relatório;
- `qa/nbr_shear_lag_r22_review/check_contract.py`, diagnóstico de biblioteca padrão com `Fraction`;
- `qa/nbr_shear_lag_r22_review/exact_diagnostics.json`, recibo determinístico;
- `tests/test_nbr_shear_lag_r22_review.py`, 26 testes do diagnóstico e de sua separação da produção.

Executado com uma thread:

```
python qa/nbr_shear_lag_r22_review/check_contract.py
PYTHONPATH=.:tests:/workspace/scratch/200bd23c4a9b/tercas_test_dependencies_r11:/workspace/scratch/200bd23c4a9b/connections_audit/test_dependencies \
OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -m pytest -q tests/test_nbr_shear_lag_r22_review.py tests/test_nbr_ue_shear_lag.py
```

Resultado: **140 testes aprovados em 0,78 s** (26 novos diagnósticos + 114 do gate existente). O diagnóstico não importa NumPy, catálogo, provedor resistente ou solver. Seus dados são todos sintéticos. O replay do recibo é comparado exatamente, e razões não tabuladas não são aceitas silenciosamente como fatores da Tabela 7.

Não foram executados solver, bateria pesada de perfis, regressão completa, UI/Word ou publicação, porque não houve mudança de produção. Esses testes não são validação estrutural nem aprovação de projeto. O gate R21 mantém apenas a dispensa suficiente e, fora dela, uma pendência, nunca reprovação automática.

**Próximo passo concreto:** obter uma derivação/desenho/exemplo verificável que identifique `bf0` e as partes reduzidas do Ue arredondado, começando pela flexão forte escalar. Então adaptar o integrador existente e as suas provas locais, com revisão/snapshot próprio, antes de conectar aos índices. A Tabela 7 isolada não fechou essa passagem nesta revisão.
