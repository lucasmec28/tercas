# LRO — Terças (primeira emissão restrita)

Aplicativo Streamlit para verificações parciais de um vão U/Ue, segundo o método documentado na Rev07 e NBR 14762:2010. **Não considera telha como travamento e não emite aprovação global.**

## Executar

Python 3.12. `pip install -r requirements.txt`; `streamlit run app.py`.
No Streamlit Community Cloud: repositório `lucasmec28/tercas`, branch escolhida, arquivo `app.py`.

## Escopo e entradas

- Eixo forte; ações q+P já combinadas, uma posição por caso; ELU e ELS separados.
- Catálogo inicial: 3 perfis Tuper. Dados ausentes (material, raio, J, Cw, críticos) não são inventados. Origem de valores informados fica no relatório.
- FLT por trechos com Ly/Lz informados; a hipótese de domínio da expressão deve corresponder ao modelo físico. Tirantes não implicam automaticamente restrição de torção.
- Local/MSE, distorcional quando aplicável, cortante, interação M–V, ELS de flexão e introdução localizada no subconjunto implementado.
- Geometria fora do subconjunto ou dados ausentes geram estado parcial, não aprovação.
- Exemplo didático é explicitamente sintético; não é produto qualificado nem projeto.

## Não incluído

Projeto de ligações, torção primária, flexão biaxial/axial, balanços/continuidade, análise física automática de travamentos, geração automática de Mdist e de todas as combinações. Os limites são da implementação, não novas exigências da norma.

## Testes

`python -m unittest discover -s tests -v`

Status: primeira emissão restrita. 30 testes automatizados da aplicação passaram; houve revisão independente e comparações aritméticas. Implantação e navegador online ainda precisam de conferência. Testes não equivalem a validação experimental ou aprovação de projeto.
