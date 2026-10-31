# LRO — Terças (emissão restrita — 0.4.4-estudo)

Aplicativo Streamlit para verificações parciais de um vão U/Ue, segundo o método documentado na Rev07 e NBR 14762:2010. **Não considera telha como travamento e não emite aprovação global.**

## Executar

Python 3.12. `pip install -r requirements.txt`; `streamlit run app.py`.
No Streamlit Community Cloud: repositório `lucasmec28/tercas`, branch escolhida, arquivo `app.py`.

## Escopo e entradas

- Eixos X horizontal/forte e Y vertical/fraco; duas entradas: q+P já combinados (ELU/ELS separados) ou cargas por área, distância entre terças e PP automático.
- Modo área: matriz fixa de 48 combinações fornecida por Lucas, mais combinações próprias de P nas famílias aplicáveis (4 ELU e 1 ELS rara), cada uma em duas posições, filtrável em quatro famílias; cada caso recalculado, sem somar índices ou flechas de diferentes inércias efetivas.
- Aços predefinidos e personalizado; comprimentos efetivos Lx, Ly superior/inferior e Lz agrupados. Troca de perfil preserva dados de projeto, não críticos manuais de outra seção.
- Catálogo: 209 perfis U/Ue da planilha V03 fornecida por Lucas, com rastreabilidade Pierin/DimPerfil. Dados ausentes (material, raio, J, Cw, críticos) não são inventados. Origem de valores informados fica no relatório.
- FLT por trechos com Ly/Lz informados; a hipótese de domínio da expressão deve corresponder ao modelo físico. Tirantes não implicam automaticamente restrição de torção.
- Local/MSE, distorcional quando aplicável, cortante, interação M–V, ELS de flexão.
- Eixo fraco: rota Anexo E e interação biaxial §9.9 conforme dados por sentido; hipóteses provisórias e ramos parciais permanecem explícitos.
- Comparação explícita do catálogo por massa, utilização e pendências; progresso/cancelamento entre perfis. Não é porcentagem de aprovação.
- Desenho com combinação selecionável e P visível nos casos aplicáveis; P automática em duas posições prescritas: centro e limite junto ao apoio, sem varredura intermediária. FLT e interação cobrem essas posições, não certificam máximo contínuo.
- Geometria fora do subconjunto ou dados ausentes geram estado parcial, não aprovação.
- Exemplo didático é explicitamente sintético; não é produto qualificado nem projeto.

## Não incluído

Projeto de ligações, torção primária, interação axial, balanços/continuidade, análise física automática de travamentos, geração automática de Mdist e geração normativa genérica de combinações. Flecha paralela à cobertura foi retirada da lista e fica fora do escopo desta emissão. Os limites são da implementação, não novas exigências da norma.

## Testes

`python -m pytest -q` (inclui regressões de interface e testes aritméticos).

Status: emissão restrita 0.4.4. Suíte ampliada de testes automatizados incluída; houve revisão independente e comparações aritméticas. Implantação e navegador online ainda precisam de conferência. Testes não equivalem a validação experimental ou aprovação de projeto.

