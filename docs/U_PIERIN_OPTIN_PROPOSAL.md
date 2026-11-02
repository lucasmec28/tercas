# Proposta em cópia: hipótese U/alma com seleção explícita

**Estado: opção exploratória com publicação autorizada por Lucas em 02/11/2026, mantendo a seleção desligada por padrão.** Base remota recuperada `9a730eb8cd053cec463d89d6de277f3b8cd8b7d3`, incorporando a rota forte publicada. Proposta inicial revisada sobre `8f323d8`, depois rebase em cópia com preservação da rota forte. Não atribuir esta hipótese a uma declaração de Pierin.

## Justificativa e decisão delimitada

O estudo separado comparou 124 geometrias U exatas em ambos os sentidos: alma comprimida ficou mais próxima da tabela em todos os casos no modelo próprio. As fontes primárias examinadas não explicitam o lado comprimido da Tabela 1. Portanto, há suporte numérico para uma hipótese escolhida conscientemente, não confirmação documental ou validação física geral.

A proposta permite calcular consequências **condicionais/exploratórias** dessa hipótese usando o valor oficial tabelado, sem mudar fórmulas de resistência. Não importa os críticos numéricos do benchmark. Ela é compatível com estudar métodos pendentes de revisão somente se a pendência não for ocultada e a ativação depender de escolha explícita. Lucas autorizou a publicação desta opção experimental para as quatro geometrias abaixo. Isso não confirma o sentido na fonte nem aprova o dimensionamento; a ativação continua a exigir seleção explícita em cada estudo.

## Cobertura inicial

Somente as quatro geometrias com refinamento n6/n9 e formas modais revisadas neste estudo:

| Seção U [mm] | Ml,y oficial [kN·m] |
|---|---:|
| 50 × 25 × 1,20 | 0,70 |
| 100 × 75 × 2,65 | 12,44 |
| 200 × 50 × 2,00 | 1,39 |
| 300 × 100 × 2,65 | 4,65 |

Isso é uma **lista de cobertura da evidência**, não limite normativo de espessura, esbeltez ou erro. As demais U mantêm referência sem atribuição de sentido. O caso espesso U200×50×8 permanece diagnóstico; não há extensão automática às 124 referências nem aos dois perfis sem linha exata.

## Fluxo e salvaguardas

1. Estado inicial e arquivos sem seleção: nenhuma atribuição automática U, como na versão publicada.
2. Checkbox nomeia explicitamente hipótese inferida, exploração e confirmação pendente.
3. O registro `weak_axis.positive.u_pierin_assumption` vincula versão da hipótese, identidade do catálogo, referência, hash do PDF, lado `web` e reconhecimento booleano explícito. Esse registro não é assinatura digital nem certificação de responsabilidade técnica.
4. Valor/origem ficam vinculados, sem edição ou escala nessa opção. Alterações em E/G, geometria, propriedades de seção, identidade, versão, valor ou origem bloqueiam a rota. Material fy/fu não altera o crítico elástico; guardas existentes continuam operantes.
5. Metadado ou marcador textual da hipótese aciona o controle mesmo se o booleano genérico provisório for removido/falso. Texto livre, valor preenchido ou um checkbox global não criam reconhecimento por si sós.
6. Somente My positivo/alma. My negativo continua sem crítico desta opção, e demanda negativa mantém a interação pendente. Nada é copiado bilateralmente ou convertido via valor absoluto.
7. Usa a rota existente de propriedades/linha média do catálogo. Não mistura esta opção com propriedades fracas manuais, não importa Mdist,y nem transfere dispensa da Tabela 14 forte. Expõe também a condição da rota existente de U simples sem painel na mesa tracionada, que deve ser conferida no caso estudado.
8. Ao desligar, retorna ao rascunho manual anterior da mesma sessão, quando houver; sem rascunho, apaga os campos gerados. Desligar não transforma silenciosamente a hipótese em dado manual confirmado.
9. Trocar seção ou executar comparação de catálogo limpa a opção, inclusive ao comparar a própria seção original. Lote de ações da mesma seção pode conservar a escolha, com condicionamento em todos os casos e resumo.
10. JSON desta opção requer uma versão que reconheça o novo campo; versões anteriores devem rejeitá-lo, não se deve remover metadados para forçar cálculo. JSON exporta/restaura seleção e vínculo; a interface avisa quando ativa. Dados adulterados não são autocorrigidos para aparentar confirmação: falham na validação ou deixam a rota pendente. Alterar seleção invalida resultados/exportações anteriores.

## Apresentação do resultado

UI, Word, JSON direto/lote e resumo conservam **“Exploratório — hipótese de sentido inferida, pendente de confirmação”**. A linha biaxial não usa “Atende” para essa hipótese, nem para índice menor que 1. Um índice maior que 1 permanece visível como excedência exploratória. Resultados fortes independentes não são ocultados; não há aprovação global.

O resultado registra `source_sign=None`, `source_sign_declared=False`, `source_confirmation_pending=True` e `design_approved=False`. A matriz numérica é uma consequência da hipótese; não torna a face comprimida um fato declarado pelo artigo.

## Limites que a opção não resolve

- G/ν e transformação geométrica do INSTAB2013 continuam sem confirmação. G=77000 MPa é detector da configuração original do app, não valor atribuído a Pierin.
- O benchmark usou E=200000 MPa, ν=0,3, G=76923,076923 MPa, linha média reta e apoios S–S. Concordância numérica não equipara essa idealização às propriedades reais arredondadas do catálogo.
- Proximidade não é tolerância normativa nem prova de conservadorismo resistente. Não há classificação modal geral ou validação de outras seções, imperfeições e pós-crítico.
- O caminho documental segue aberto: arquivos INSTAB do estudo ou esclarecimento dos autores sobre tensão/face comprimida, geometria, material e normalização. Nenhum contato externo foi feito.

## Evidência

- Benchmark reproduzível e revisão de fontes: Library `libfile_ca60144081c08191b498e2c7adb1135a`, versão 0.
- Fonte numérica oficial adotada: `tercas/data/pierin_2013_weak_reference.json`, preservada sem alteração.
- Núcleo, catálogo bruto, guardas fortes e FSM experimental permanecem byte a byte iguais à base. Esta proposta não promove o solver experimental a rotina de dimensionamento.

Testes e revisão final da implementação estão no pacote externo da candidata, incluindo opt-in/out, adulteração, mudança de perfil, scan, lote, Word/JSON, preservação das guardas e paridade do comportamento padrão.
