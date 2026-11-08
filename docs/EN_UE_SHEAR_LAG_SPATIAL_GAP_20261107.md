# Shear lag sobre seção Ue local/distorcional: revisão espacial focada

## Resultado e alcance

Não foi identificada, nas passagens verificadas abaixo, uma regra que feche a representação espacial conjunta da seção Ue arredondada já reduzida local/distorcionalmente. Não foi ampliada elegibilidade. Não falta implementar o método de larguras efetivas inteiro: os quatro operadores puros dos 66 Ue completos já existem. A exigência de integralidade dos suplementos atuais é uma condição suficiente própria, não uma proibição normativa de usar seção reduzida.

Base preservada: `1a335043f4fdf4454b450cd508f6c4eb6b53d812`. Revisão em cópia independente; nenhuma alteração no kernel, consumidor, replay, UI ou árvores históricas.

## Fontes examinadas e o que efetivamente fornecem

- [EN 1993-1-5:2006](https://people.fsv.cvut.cz/machacek/PomuckyE/Plated%20structural%20elements%20%281993-1-5%29.pdf), páginas impressas 9–14: §3.2.2/Fig.3.3 fornece distribuição quártica de tensão de shear lag elástico; §3.3 permite opções no ELU e calcula área combinada; §4.3 trata propriedades efetivas. Conferida visualmente a Fig.3.3. Não se identificou nessas passagens uma prescrição de espessura uniforme βt para toda a montagem Ue já reduzida.
- [EN 1993-1-3:2006, corrigendum 2009](https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf), §§5.5, 6.1.4.1, 6.1.4.3 e 6.1.6: local/distorcional, seção efetiva por momento e remissão ao shear lag. O §6.1.6 conserva componentes efetivas separadas de flexão e propriedades brutas para empenamento/cisalhamento. Portanto, não é necessário inventar uma seção efetiva única combinada.
- [JRC/ECCS, EUR 22898 EN, 2007](https://eurocodes.jrc.ec.europa.eu/sites/default/files/2021-12/EUR22898EN.pdf), §§3.2 e 3.6, páginas impressas 30–32 e 39–40: explica funções de empenamento para shear lag e a alteração do fator de ortotropia com área reduzida por flambagem. Essa explicação não fecha a atribuição espacial da redução às faixas desconexas, lábio e cantos do Ue deste kernel.

## Passo matemático exato que ainda falta

O estado existente é uma medida de área no contorno: intervalos retidos com espessura t ou t_red. Para cada eixo e sinal, falta definir uma transformação espacial documentada desse estado, incluindo mesa, lábio e cantos, que produza a área combinada e os momentos de área necessários ao operador. Alternativamente, uma lei de tensão diretamente integrada poderia fechar o problema, desde que sua normalização, domínio físico e acoplamento ao estado local/distorcional estejam definidos.

Conservar apenas a área não determina ∫x dA, ∫y dA, ∫x² dA, ∫y² dA ou ∫xy dA. Consequentemente, não determina CG, tensor, campo unitário ou módulo resistente. Zerar um primeiro momento adicional também não fixa os segundos momentos. Isto é uma dedução algébrica, não uma exigência normativa nova.

A lei elástica documentada usa u=y/b0 a partir da raiz da placa. Para β>0,2, sua forma normalizada é q(u)=a+(1−a)(1−u)^4, a=1,25(β−0,2). Para β≤0,2, a distribuição termina em b1=5βb0. Ela tem integral β sobre a placa completa normalizada, mas essa identidade não se transfere automaticamente a uma medida de área com faixas removidas e espessuras diferentes.

O diagnóstico racional reproduzível em `qa/en_ue_shear_lag_spatial_review/` mostra, para β=4/5 e faixas [0,1/4] e [3/4,1]:

- área local = 1/2; área-alvo combinada = 2/5;
- integral da lei quártica diretamente nas faixas = 4231/10240, diferente de 2/5;
- renormalizar por 4096/4231 restaura apenas área; é uma escolha adicional, sem derivação espacial obtida nesta revisão.

Outro diagnóstico conserva exatamente área 4/5 em três distribuições. Faixa na raiz, faixa na ponta e espessura uniforme têm primeiros e segundos momentos distintos; a distribuição uniforme também tem segundo momento central diferente das duas faixas. Não são propostas físicas concorrentes, mas contraprovas à inferência de tensor a partir de área.

## O que já pode ser conectado quando essa regra estiver definida

1. O kernel já calcula faixas, As/Is/K, chi_d/t_red e iteração da alma; não precisa ser substituído.
2. `audit_effective_state` já reintegra um estado fornecido, devolve operador/tensor, faixas de alma requeridas e limites de tensão de As. Não concede qualificação ao estado.
3. A nova regra deverá determinar os intervalos/pesos físicos ou o campo integrável por eixo/sinal e fechar o reequilíbrio e a revisão local/distorcional. Não basta reutilizar chi_d e a seção anteriores após mudar seu campo sem reavaliar as hipóteses.
4. Os operadores separados podem continuar sendo somados conforme §6.1.6, mantendo B/omega/Cw brutos. O bloqueio descrito é espacial por componente, não uma exigência de tensor biaxial comum.
5. A implementação futura deverá ter revisão/snapshot próprio e preservar o despacho de replay histórico. Perfis genéricos ficam fora desta frente.

Não se alterou curling. Uma eventual ampliação de shear lag não resolve automaticamente sua média de mesa com B e outro eixo. Não se deu crédito a telha, vínculos ou projetos privados.

## Verificação executada

`python qa/en_ue_shear_lag_spatial_review/check_spatial_contract.py`

Cinco verificações diagnósticas exatas com Fraction, sem solver, rede, NumPy ou bateria de 66 perfis. Saída versionada em `exact_diagnostics.json`; nenhuma resistência ou cobertura física adicional é afirmada. Não foram executadas regressão completa, UI ou publicação porque não houve mudança de produção. A ausência de ponte nesta busca focada não prova que nenhuma literatura possível a forneça.
