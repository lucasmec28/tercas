# ELS reduzido: fronteira de implementação e próximo delta

Revisão sobre a base R17 `23de0dd535bf71f863c2ca9e2fba3ef8fa5032be`.
Nenhuma rigidez efetiva nova é atribuída ao campo combinado nesta revisão.

## O que a fonte pede e o que o programa faz

A NBR 14762:2010 §9.8.5 admite duas rotas para levar a redução de rigidez
por flambagem local ao cálculo de deslocamentos. Na opção (a), as larguras
MLE de §§9.2.2/9.2.3 usam a tensão de serviço. O §9.2.2.2 explicita
aproximações sucessivas e a máxima compressão calculada para a seção efetiva. Na opção (b), a lei MSE usa
Mn/Ml da flexão. A norma não exige que o perfil permaneça integral, nem
transforma um crivo suficiente inconclusivo em reprovação.

O programa já dispõe da lei MSE escalar `core/protocolo_ief.py`, inclusive
Ief variável no vão, q/P de mesmo sentido e máximo de flecha por raiz da
derivada. `deflection_scope.py` a oferece explicitamente como componente
forte local. Esta revisão não apresenta essa rotina como uma novidade.

O campo combinado, por sua vez, usa Mx+My+B concomitantes, E/G, contorno,
ponto/direção/corda próprios. Os crivos v1/v2/v3 apenas demonstram casos
em que a seção nominal pode permanecer integral no modelo. A ausência da
prova não demonstra, por si só, que uma parede realmente perde largura.
O campo bruto e sua razão diagnóstica não são uma flecha efetiva.

## Por que não há ponte automática ao MSE forte

1. Uma lei escalar Ix,ef(Mx/Ml) não fornece Iy,ef, Ixy,ef, o deslocamento do
   centroide, Cw,ef nem um campo setorial efetivo para Mx+My+B.
2. PP no CG e ações externas no topo geram torques diferentes, mesmo quando
   a força transversal total é pequena. Não se pode reconstruir essa fonte
   a partir do total, apagar PP ou mover sua linha para obter torção nula.
3. Escolher somente a projeção normal não elimina My/B da determinação das
   larguras efetivas. Também não permite somar máximos uniaxiais e torsionais.
4. O contorno arredondado preserva resíduos numéricos de Ixy/omega. Uma
   comparação por tolerância não demonstra um subdomínio exatamente puro.
5. O ramo MLE fraco existente `ue_catalog_nbr_weak_mle.py` é local resistente,
   tem uma fonte Ue125 pinada, separa os sinais alma/lábios e não é lei ELS.
   Importar sua largura, tensão fy ou certificado para outro perfil seria
   transferência indevida. No ELS, tensão e centroide devem ser compatíveis.

## Próximo delta qualificável

O menor avanço efetivo útil deve primeiro fornecer uma seção MLE sob a
solicitação concomitante da fonte, sem recalcular silenciosamente o histórico.
Um contrato de seção, separado de qualquer solução do membro, deve receber:

- Contorno arredondado completo e espessura, dimensões planas, E e tensão de
  serviço, todos vinculados à mesma seção própria, sem filtro por nome.
- Mx, My e B concomitantes; a convenção de sinal e a fibra/ponto de referência.
- Regra explícita para os trechos comprimidos/tracionados de cada parede,
  posições de be1/be2, enrijecedores e dobras, com seu domínio normativo.
- Evidência iterativa de equilíbrio e compatibilidade: centroide/tensor,
  campo de tensões e larguras, sem trocar tensão de serviço por fy.

Primeiro teste de aceitação: no limite integral reproduzir a fonte bruta;
se houver redução, fechar o equilíbrio do mesmo vetor de esforços e verificar
os sinais de alma/lábios, inclusive reversão da ação. Depois será necessário
qualificar a compatibilidade dessas propriedades com a flexão e a
torção/empenamento do modelo adotado, sua linha de carga e o deslocamento
concomitante no mesmo ponto. Não se atribui à norma uma exigência universal
de reduzir J/Cw/SC/omega: a escolha precisa de uma derivação compatível.
O §9.8.5 não prescreve Ief constante no Mmáx nem Ief variável; adotar qualquer
dessas aproximações exige explicitar seu domínio e sua justificativa.

### Reuso concreto e interface que falta

- `en_ue_catalog_operators._properties/_bands`: a integração geométrica de
  bandas é reutilizável; as leis EN, fy e a redução distorcional não são
  automaticamente uma lei NBR de serviço.
- Novo operador MLE NBR de cinco paredes: ramos Tabela 5/6, be1/be2 e
  §9.2.3, com tensões concomitantes de serviço e iteração do centroide/tensor.
- Com B, a base normal contém 1, y, −x e omega. A redução introduz integrais
  cruzadas flexão/empenamento antes nulas. Manter a base bruta exige tratar
  a matriz normal acoplada; renormalizar exige transformar coerentemente
  esforços, linha de carga e referências. Uma simples substituição de Ix
  não faz nenhuma dessas operações.
- `torsion_vlasov.vlasov.matrix/solve_member`: a formulação atual monta
  somente os dois graus de liberdade phi/phi' com GJ/ECw constantes e SC
  fixo. Não recebe o operador normal acoplado acima.
- Após demonstrar a lei espacial e um campo compatível, reutilizar ponto,
  direção, corda e envelope existentes, sem somar máximos independentes.

Não recortar a alma e reconectar os nós por `from_polyline`: isso inventaria
segmentos e um fluxo de cisalhamento de outro contorno. A largura inefetiva
para tensão longitudinal não representa um rasgo físico na parede.

Isso descreve uma lacuna da implementação, não obrigação de GMNIA, ensaio,
solver específico ou documento adicional imposto pela norma. Um ramo
analítico mais curto pode substituí-la quando sua equivalência for provada.

## Preservação e alcance

Leff continua somente resistente. Não se acrescentam telha, rigidez, tirante,
vínculo, ligação ou ação. O limite angular numérico não vira limite normativo.
Nenhuma lista vazia, hash ou cache pode promover um resultado. Os leitores
mantêm os snapshots v1/v2/v3 e não resolvem novamente o membro.

Fonte primária recuperada e SHA-256 conferido nesta rodada:
`c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.
Revisão independente inspecionou visualmente as páginas impressas
24, 26–31 e 51–52 (PDF30,32–37,57–58), incluindo §§9.2.2.2 e 9.8.5.
O PDF protegido não integra o repositório. A conclusão não depende de uma
transcrição pública ou de texto OCR com fórmulas corrompidas.

Não houve publicação, liberação estrutural ou conclusão de ELS combinado
reduzido. Uma fixture sintética e as regressões desta revisão devem documentar
a lacuna sem mascará-la como progresso de capacidade normativa.

## Alteração entregue e regressão

A apresentação autenticada agora identifica as paredes onde o crivo salvo
ficou inconclusivo e apresenta separadamente a guarda elástica. Se só a
guarda elástica não concluir, não se aponta redução de parede como solução.
A classificação é somente de apresentação: nenhum novo snapshot, decisão,
índice ou requalificação histórica foi criado. Tela e Word usam o mesmo
detalhe, após o leitor/autenticador existente.

A fixture de regressão incluída é inteiramente sintética: Ue100x50x17, t=1,2 mm,
vão físico 4000 mm, inclinação 5°, PP calculado uma vez no CG, ação externa
normal 0,42 N/mm e paralela 0,02 N/mm na linha superior da alma. O campo
salvo tem Mx/My/B não nulos. Seu limite superior elástico é 200,9788 MPa
para fy=250 MPa; alma e mesa superior ficam inconclusivas. Mesmo usando
limite permissivo de 1000 mm e razão bruta menor que 1, os índices permanecem
ausentes. O giro linear de 0,6523 rad é apenas diagnóstico da cinemática
linear, não rotação física qualificada nem critério normativo adicional.

O gerador explícito usa uma solução ELS de 32 elementos; os testes só leem
a fixture e reproduzem a aritmética, com o solver e a substituição MSE
bloqueados. A reversão de sinal é verificada separadamente na álgebra
σ=−My(x−cg)/Iy: My físico negativo comprime a alma; o sinal My_app da
rotina MLE fraca é oposto. Nenhum PP fisicamente invertido foi criado.

157 testes focais passaram (1,05 s): diagnóstico, fixture e panorama. Não
é execução da suíte integral nem AppTest desta alteração. Recibo e SHA da
fixture: `qa/r18_els_gap/RECEIPT.json`. A fixture verifica a lacuna da
implementação e preservação do campo, não valida um projeto real.
