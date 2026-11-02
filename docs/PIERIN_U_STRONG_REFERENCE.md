# Mlx / Nl U — referência Pierin adotada e condicionada

## Escopo e base

Candidata sobre 8f323d834cb463f81d5b2dc037494d45a78896e5. A autorização do proprietário para usar Pierin como referência oficial do app não converte o artigo em norma, certificação de produto ou aprovação estrutural. Esta alteração é separada do diagnóstico experimental FSM e não altera o núcleo resistente.

Fonte: Pierin, Silva e La Rovere (2013), *Forças Normais e Momentos Fletores Críticos de Perfis Formados a Frio*, Revista da Estrutura de Aço, volume2/número1, pp21–40. Tabela1 nas páginas impressas29–30 / PDF9–10; hipóteses na p28/PDF8. [Página do artigo disponibilizado pelo autor](https://www.researchgate.net/publication/265207005_Forcas_Normais_e_Momentos_Fletores_Criticos_de_Perfis_Formados_a_Frio).

PDF SHA256: `2ff5f67f201e00ddb31fdb7370a8077bc9e27fb9ac553cb0c5036ab9ad9d2d73`.

## Dados e distinções

- 124 linhas U do catálogo coincidem **exatamente** em família, h, bf, lip=0 e t com a Tabela1. Mlx e Nl são extraídos por coluna com conversões exatas kN·m→N·mm e kN→N. Cada registro preserva linha textual, página, unidades e ID geométrico; não depende só do índice de catálogo.
- U100×75×3,00 e U250×100×6,35 não têm linha exata. Não usar3,35 no lugar de3,00, nem6,30 no lugar de6,35. Sua rota Tabela12 permanece quando válida.
- Nenhum Mlx/Nl Ue é modificado. Sete Mlx Ue ausentes na fonte continuam ausentes, com sua rota Tabela12 existente quando válida. Mly e todos os valores brutos da planilha permanecem intocados.
- Mlx é crítico local elástico em torno do eixo x de simetria U; não é resistência MRd e não é transposto ao eixo fraco. A simetria geométrica em relação a x evita a ambiguidade dos dois lados comprimidos de Mly; não autoriza qualquer carregamento fora do domínio forte declarado no app.
- Nl é **somente referência documental**. Não implementa resistência axial nem altera a interação restrita aN=0. Ausência de Mdist não é zero ou resistência infinita; a regra existente de aplicabilidade de distorção permanece intacta.

## Hipóteses da fonte e limites geométricos

A fonte declara apoio simples, E=200GPa e cantos retos. G/ν e a conversão exata das dimensões nominais para a discretização INSTAB não são explicitados. Não foram inventados. A observação no artigo sobre cantos retos ligeiramente conservadores não é extrapolada como critério geral.

A adoção utiliza correspondência nominal e propriedades originais de catálogo. Não comprova equivalência completa entre seção física, propriedades com raio e idealização INSTAB. Resultado mantém `section_property_convention_pending=true` e `source_geometry_convention_unresolved=true`; `whole_member_approved` permanecefalse. Não há validação de outras seções, interpolação, extrapolação, tolerância geométrica inventada ou calibração do FSM.

Guardas de integridade verificam h,bf,lip,t,A,Ix,Wx,Iy,J,Cw,ri contra o catálogo. Editar qualquer uma bloqueia o Mlx herdado; não demonstra que o valor esteja fisicamente errado, apenas exige nova origem/análise compatível em vez de misturar modelos silenciosamente. fy/fu não são parâmetros do crítico elástico e podem variar; as resistências posteriores continuam calculadas pelo núcleo existente. Massa é independente da identidade do crítico, embora altere peso próprio no modo área.

## Precedência e migração

1. **Novo default ou seleção explícita/comparação do catálogo**: se há linha U exata, Mlx Pierin tem precedência sobre o fallback Tabela12. Não se escolhe o maior de dois resultados. Origem especifica ID/página; catálogo bruto não é sobrescrito.
2. **Projeto salvo/importado com Tabela12**: entrada e origem existentes permanecem. Sem substituição silenciosa ao calcular. Recálculo explicitamente rastreado já existente conserva sua validação porE/parâmetros. Importar JSON não adota automaticamente a fonte nova.
3. **Nova tabela com E alterado**: bloquear, não escalar. **G alterado**: bloquear porque G/ν da fonte não foram explicitados. G77000MPa é apenas detector operacional de alteração do app, nunca atribuído aPierin.
4. Nenhum fallback automático em consequência do bloqueio. Restaurar configuração original restaura o valor original; não constitui nova análise física.
5. **Manual independente**: valor diferente e origem independente seguem a rota manual já existente, sem certificação. Editar só texto, só valor de uma origem automática ou copiar origem de outra seção não requalifica. Um valor numericamente igual ao tabelado é conservadoramente tratado como herdado, mesmo com texto livre alterado.

## Efeito nos resultados e testes

O aumento observado dos124críticos Mlx contra o fallback atual é6,5252%–35,5756%. Isso **não** mede erro físico, aumento aplicável de resistência ou margem de segurança. MRd depende também deW,fy,χFLT,domínio e outros limites. ELS também usa o crítico local no modelo existente e pode mudar. Comparação numérica é regressão e sensibilidade, não homologação física.

Evidências do pacote externo da candidata incluem inventário, comparação por perfil, projetoslegados, guardas E/G/geometria/linha/valor, origemmanual, UI, JSON, lote/scan e Word. Testes de fonte e de resistência são separados: nenhum ajuste de constante foi feito para forçar concordância com Pierin. A publicação exige nova conferência deHEAD, revisão e autorização aplicável; este documento não é recibo de publicação.

Exemplo numérico sintético documentado no pacote: U100×50×1,20, L=3000mm, fy=250MPa, G=77000MPa, qELU=0,83N/mm. A demanda local é0,93375kN·m. Tabela12 fornece Ml=0,713446210kN·m, MRdlocal=0,918528779kN·m e índice1,01657; Pierin fornece Ml=0,760kN·m, MRdlocal=0,943294217kN·m e índice0,989882. O critério local muda de não atende para atende; isso não aprova o elemento (FLT continua governante/não atendida nesse exemplo). Para qELS=0,8N/mm, a flecha passa14,68325→14,35190mm. As mudanças são efeitos do modelo existente, não prova de maior segurança física.
