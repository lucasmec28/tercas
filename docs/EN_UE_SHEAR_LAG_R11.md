# Shear lag EN: envoltória suficiente para Mx puro

## Domínio que foi acrescentado

A extensão considera EN 1993-1-5:2006 §3.3, Nota 2, Eq.3.3/3.4 e Tabela 3.1, no componente puro Mx de seção Ue nominal horizontalmente simétrica, com N=0 e componentes Mx positivo/negativo integralmente efetivas. My pode ser concomitante somente no domínio independente descrito abaixo. As equações recebem geometria, material e zonas físicas de momento como parâmetros, sem exceções pelo nome ou índice do perfil.

A dispensa original b0 < Le/50 continua estrita e registrada. Le é a distância física entre zeros exatos do diagrama de momento. Não é comprimento resistente de estabilidade, elemento de malha ou subdivisão automática na força P. Inversão de todas as ações não escolhe arbitrariamente outra curva de shear lag.

Casos com shear lag fraco relevante, seções locais/distorcionais Mx reduzidas e casos fora das provas abaixo continuam pendentes nesta extensão. Os seis perfis 51, 52, 58, 59, 60 e 67 foram qualificados somente nos casos sintéticos declarados. My não nulo por inclinação não recebe dispensa automática.

### My concomitante com aplicação independente

EN 1993-1-3 §6.1.4.1(4),(7) e §6.1.6(3),(5) permitem as respectivas seções efetivas puras para as tensões dos dois momentos. O suplemento continua fornecendo somente intervalos e pisos Mx. O operador My original permanece intacto, com os dois sinais elegíveis, e `assess(demand,n)` deve demonstrar sua dispensa de shear lag e seu curling no mesmo caso. Booleanos recebidos do chamador não substituem essa recomputação.

O registro `independent_My_companion` guarda a aplicabilidade My reavaliada, seus hashes e os hashes dos operadores My não modificados. Os campos concomitantes continuam somados nos mesmos pontos pelo consumidor contínuo existente; B/torção/cortantes não mudam. Não se soma índice em lugar de tensão e não se declara tensor efetivo comum. Nenhum método novo de shear lag My, área local ou distorcional foi criado.

A revisão `symmetric_integral_area_loss_bound_independent_My_20261107_v2` muda o hash técnico da candidata v3 R11 ainda não publicada. Os recibos QA anteriores permanecem históricos; somente novos resultados são acrescentados. V1/V2 e as fontes históricas permanecem intocados.

## Área e inércia sem localização inventada

A Eq.3.3 fornece Aeff=Ac,eff·beta_ult, mas não autoriza espalhar beta como espessura uniforme sobre qualquer seção Ue nem inventar a posição de todas as faixas efetivas combinadas. A implementação não faz isso e não declara um novo tensor efetivo exato.

Para cada metade da seção, usa-se um superconjunto físico da área que pode ser retirada: mesa, lábio e todos os arcos. Somente a alma reta em x=0 é excluída. A maior área superior das duas metades é usada duas vezes. Isso inclui de forma conservadora cantos que outra idealização poderia atribuir parcialmente à alma.

A razão kappa é limitada por sqrt(A_flange_upper·b0_upper/t)/Le_lower. Na Tabela 3.1, toma-se um beta inferior que cobre as curvas de vão, apoio e extremidade. O mínimo lateral em kappa=0,7 também entra no limite, pois as fórmulas arredondadas da tabela têm pequena descontinuidade nessa fronteira. Comprimentos racionais, constantes decimais e operações são convertidos com arredondamento dirigido.

Com perdas espelhadas, o centroide vertical permanece em (h−t)/2 e Ixy permanece nulo. A posição horizontal do centroide não precisa ser inventada para Mx puro. Para qualquer localização espelhada da área perdida:

Ix_eff ≥ Ix_bruto − 2·(1−beta_lower)·A_flange_upper·ymax² = Ix_lower.

ymax=h/2 limita ambas as faces físicas. A inércia bruta é reintegrada no contorno original por aritmética intervalar. Se o limite inferior não for positivo, não se emite resistência.

O piso resistente é floor(fyb/gammaM0·Ix_lower/ymax). Não é beta multiplicado por um momento resistente anterior.

## Local, distorcional e tensões concomitantes

A integralidade local/distorcional não é aceita apenas pelo rótulo do certificado. O método refaz as verificações locais no majorante fy·|y−y0|/ymax. A área As física, sua rigidez e chi_d são recalculadas. Uma integração intervalar da tensão média de As precisa demonstrar sigma_As_upper ≤ chi_d·fy. Assim, os cinco dos seis casos com chi_d<1 não são confundidos com chi_d=1: a área integral decorre da Eq.5.17 comprovada sob esse majorante.

A distribuição de tensão física de shear lag não é inventada. O consumidor usa uma envoltória intervalar assinada de Mx, com coeficiente entre zero e 1/Ix_lower, preservando o sinal e o plano médio de simetria. O extremo zero evita cancelamento favorável de uma distribuição desconhecida com o campo B. B, V, Tsv e Tw continuam sendo os originais. Não há conversão de torção em cortante nem alteração de E/G da análise.

Um teto dessa envoltória acima de 1 continua inconclusivo. O ramo não emite testemunha de excesso físico, pois não foi declarada uma distribuição física exata. O piso próprio entra na interação M–V, sem alterar o certificado normal de catálogo.

## Correção da apresentação normativa

Nos checks v3, se faltar aplicabilidade de shear lag ou curling, os critérios normal e interação EN6.1.6 são pendentes. Seus valores anteriores ficam separados como diagnóstico, sem índice normativo nem testemunha normativa de falha. O cisalhamento concomitante tau e a resistência independente a cortante continuam disponíveis. Um suplemento de shear lag não apaga uma pendência de curling.

Checks v2 são reproduzidos pela rota anterior, sem a extensão e sem alterar seus números, rótulos ou elegibilidades. A apresentação acrescenta apenas um aviso de alcance histórico. O teste utiliza uma cópia byte a byte do engine v2 original, inclusive com a fonte normal R10 congelada. O hash de conteúdo externo refeito não autoriza adulterar beta, inércia, piso, intervalo do operador ou identidade técnica.

## Fonte primária e validação

Fonte dos bytes examinados: [EN 1993-1-5:2006, espelho CVUT](https://people.fsv.cvut.cz/machacek/PomuckyE/Plated%20structural%20elements%20%281993-1-5%29.pdf), páginas impressas 10–13, 448378 bytes, 53 páginas. SHA256: `1f1c2639f1d03520ccf2ef3d438f6c8cf0a02875ab0fece2ff4410882e0fa7a6`. O PDF não foi incorporado ao repositório.

O recibo `qa/en_ue_shear_lag_r11/validation_receipt.json` identifica 56 testes distintos aprovados e seus XML originais/retakes. A matriz `six_scalar_proofs.json.gz` contém os seis suplementos completos e tempos escalares. Os testes de aplicação incluem os seis casos reais sintéticos, inversão, salto P, zonas entre zeros, JSON/Word, replay sem solver, preservação de B/torção/E/G, caso inclinado ainda pendente, adulteração e histórico v2/R10.

Não houve AppTest nem publicação neste lote. Nenhuma verificação seccional fornece aprovação global, estabilidade de barra, adequação física, ligações ou serviço combinado.

## Curling por tensão solicitada: avaliação, sem mudança neste lote

EN 1993-1-3 §5.4(2) utiliza tensão média da mesa sobre a área bruta; para tensão da seção efetiva, indica a conversão pela razão entre áreas efetiva e bruta. Há base normativa para substituir um majorante fy por tensão solicitada qualificada. Isso não permite usar um teto apenas diagnóstico quando o próprio campo ainda carece de shear lag. Uma próxima extensão deve vincular os momentos e operadores autenticados, evitar cancelamentos favoráveis e manter pendente o eixo cujo shear lag ainda não foi tratado. O método de curling não foi modificado neste lote.
