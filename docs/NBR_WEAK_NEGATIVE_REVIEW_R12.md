# Flexão fraca negativa NBR: revisão delimitada R12

Revisão de 07/11/2026 sobre a base R11 `70523d5`. Nenhuma fórmula,
capacidade, condição de elegibilidade ou arquivo de produção foi alterado.

## Resultado

Não foi encontrada, nas disposições diretamente aplicáveis da NBR 14762:2010
fornecida, uma redução MLE para a combinação ainda pendente: mesa sob gradiente
com inversão de sinal e enrijecedor de borda apenas parcialmente suficiente.
Não se qualifica esse caso aplicando diretamente as faixas efetivas do caso
uniforme. Isso é uma lacuna do método atualmente implementado, não uma
proibição normativa da geometria nem uma obrigação de usar FSM.

## Conferência da fonte

NBR 14762:2010, PDF fornecido, SHA-256
`c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.
As páginas abaixo foram conferidas visualmente; o PDF não tem texto extraível.

- §§9.2.1–9.2.2.1 e Tabelas 5–6, pp.26–29 / PDF32–35: o gradiente é tratado
  nos casos AA/AL indicados. A Tabela 5 não fornece a combinação com o fator
  de apoio parcial `Is/Ia` da mesa enrijecida.
- §9.2.3.1 e Figura 2, pp.30–31 / PDF36–37: `Is/Ia`, `ds` e a repartição
  `bef,1` / `bef,2` pertencem expressamente ao elemento uniformemente
  comprimido. §9.2.3.2 reaplica esse procedimento para deslocamentos, sem
  acrescentar uma lei de gradiente para o apoio parcial.
- §9.8.2.1(a–b), p.45 / PDF51: a alternativa MSE usa
  `lambda_p = sqrt(W*fy/Ml)` e `MRd = Wef*fy/gamma`; `Ml` pode ser obtido
  por análise de estabilidade elástica. A norma não exige uma técnica FSM
  específica nem identidade byte a byte de um arquivo de contorno.
- Tabelas 12–13, pp.46–47 / PDF52–53: os coeficientes diretos da seção
  completa são expressamente para flexão no eixo de maior inércia; não são
  uma fórmula de `Ml` para este sinal do eixo fraco.
- §9.8.2.2, pp.47–48 / PDF53–54: a redução local para FLT também depende
  de MLE aplicável ou de `Ml` aplicável no MSE. Dispor de `Me` não elimina
  a pendência local.

## Fórmula ou dado que falta

Uma das duas rotas abaixo resolveria o bloqueio, após sua qualificação:

1. Uma lei aplicável de largura e distribuição efetiva para a mesa sob o
   gradiente real, incluindo a interação com o enrijecedor parcial e a
   redução do lábio. É necessário determinar `bef,1`, `bef,2` e `ds` nesse
   campo e calcular a seção efetiva coerente. Inserir `Is/Ia` na Tabela 5,
   ou inserir o `k` de gradiente nas fórmulas de §9.2.3, seria uma combinação
   nova sem fundamento demonstrado nesta revisão.
2. Um `Ml,y` elástico aplicável à flexão com lábios comprimidos e alma
   tracionada, com geometria, material, eixo, sinal e normalização rastreáveis,
   e `W` coerente para §9.8.2.1(b). Pode ser uma referência externa aplicável
   ou um cálculo qualificado, sem impor um novo FSM próprio. O `Ml,y`
   Pierin atualmente catalogado não demonstra esse sinal nem um envelope
   bilateral e, por isso, não foi consumido aqui.

Não foram reutilizadas as rotas rejeitadas de subescoamento vezes módulo
bruto, retirada de lábios para suposta seção U conservadora ou transferência
de resistências EN para NBR.

## Cobertura reconfirmada

Executada novamente a função `nbr_ue_family.coverage` para as 66 linhas Ue
completas, com `L=6000 mm`, carga no centro de torção, material padrão e
`fy=250/300/345/350 MPa`. Foram 264 combinações escalares, sem solver de
membro, rede ou interface; BLAS Haswell e uma thread.

| fy (MPa) | Local negativo | Referência negativa completa | Pendentes locais |
| --- | --- | --- | --- |
| 250 | 55/66 | 55/66 | 11 |
| 300 | 51/66 | 51/66 | 15 |
| 345 | 45/66 | 45/66 | 21 |
| 350 | 44/66 | 44/66 | 22 |

Em todos os quatro materiais, local forte, local fraco positivo e distorção
fraca negativa permanecem disponíveis em 66/66. A referência distorcional
mantém sua qualificação aproximada já documentada. Esta revisão não amplia
o escopo resistente, não representa novo ensaio e não aprova o membro.
