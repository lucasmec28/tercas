# Catálogo solicitado e materiais — 31/10/2026

## Origem e fidelidade
- Arquivo recebido: `Dimensionamento_de_tercas_V03(2).xlsx`, Library `libfile_65551dd40fc88191a85055bf1bd4b28e`.
- SHA-256: `c5f4d0fa25df92e17676602154aea5aaab3329a57d40935194ee3a1c8ef2ca38`.
- Aba `03_Perfis`, linhas 5–213: 83 Ue +126 U. Sem Tuper.
- Todas as 27 colunas de cada linha preservadas em `raw_source_values`. Não recalculamos nem salvamos a planilha.
- Geometria Ue indicada na planilha: Calculista de Aço; U: NBR 6355:2012 Tabela A.2. Críticos indicados: Pierin, Silva & La Rovere (2013). Esta entrega importa o catálogo da planilha, não afirma extração nova de DimPerfil ou validação independente contra ele.
- Conversões explícitas: It cm4 ×10000 → J mm4; Cw cm6 ×1000000 → mm6; críticos kNm ×1000000 → Nmm.
- Ausências preservadas: 7 Ue sem Ml,x; todos 126 U sem Ml,x tabulado e sem Mdist,x. Não substituir ausência por zero, interpolação ou valor de outro perfil. Para U simples a rota normativa local já existente pode calcular o crítico; não tratar como ausência de resistência distorcional aplicável.
- Mly e críticos axiais são armazenados, mas NÃO introduzidos na rota atual de flexão forte. Não extrapolar para flexão fraca ou axial.
- Não foi encerrada a antiga flag de convenção geométrica sem comprovação adicional; isto evita transformar importação em validação.

## Materiais
Valores fy/fu mínimos nominais, MPa:
- ASTM A36: 250/400.
- ASTM A572 Gr.50: 345/450.
  Fonte: catálogo de chapas grossas Gerdau, tabela de propriedades mecânicas, https://gsn.gerdau.com/sites/gsn_gerdau/files/downloadable_files/Catalogo-Chapa-Grossa.pdf
- USI-CIVIL 300: 300/400.
- USI-CIVIL 350: 350/500.
  Fonte: Catálogo Geral Usiminas, tabela Aço Estrutural / USI CIVIL; cópia do documento do fabricante em https://pt.slideshare.net/slideshow/catalogo-geral-usiminas-01/87514983 (tabelas de chapas e bobinas). Não usar o catálogo mais recente apenas como prova da disponibilidade atual dessas marcas.
- Constantes físicas: E=200000 MPa; G=77000 MPa, NBR 14762:2010 §4.6; separadas das fontes de resistência.
- O usuário deve selecionar grau compatível com material efetivamente fornecido. Não significa certificado de fabricação ou garantia de disponibilidade/espessura comercial. Personalizado admite fy/fu positivos finitos com fu>=fy.

## Integração
1. `catalog_labels()` substitui lista fixa de 3 perfis. `catalog_entry(i)` valida índice.
2. Em `defaults(i)`: atualizar com `critical_defaults(i)` e aplicar material padrão via `apply_material(data,'ASTM A36')`.
3. `select(i)` preserva raio, J e Cw do catálogo em vez de sobrescrevê-los por None.
4. `material()` retorna propriedades e fontes. Mostrar fontes em seção recolhida e fy/fu editáveis só em Personalizado; conservar aço selecionado ao trocar perfil.
5. Não copiar os arquivos app.py/application.py desta pasta: são referências originais, sem alteração.

## Testes
`PYTHONPATH=<candidate> python -m unittest discover -s <candidate>/tests -v`: 8 testes, incluindo 209 subcasos de fidelidade/seleção. Isto testa transcrição e contrato de dados, NÃO valida dimensionamento normativo nem caracteriza publicação.
