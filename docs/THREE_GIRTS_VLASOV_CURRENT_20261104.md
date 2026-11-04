# Complemento prático das três travessas

Implementado em nova cópia, sem alterar a candidata anterior ou os núcleos NBR/6DOF.

## O que está disponível

- `candidate/`: aplicação copiável. Dois pontos de integração mínimos, nos editores próprios Ue de 1,20 mm e família de seis espessuras.
- `overlay/tercas/three_girt_warping/`: pacote autônomo de demanda 7DOF, painel e memória Word. Depende dos módulos comuns já presentes na aplicação.
- No editor de travessa própria, selecionar **Complemento de três travessas com empenamento e G8.1**. As ações atuais alimentam o cálculo, não o fixture histórico.
- Hipóteses editáveis: posições, linha externa, ponto material ou braços atuais, empenamento livre/impedido e PP das barras. Empenamento livre é o default explícito. Braços fora do contorno usam resultante Qpsi=0 declarada, nunca omega fictício no CG.
- Só o botão calcula. Exibição, seleção de combinação e exportação usam o snapshot salvo. Alteração de ações, geometria ou hipóteses retira o resultado anterior. Proposta de geometria ainda não aplicada também retira o resultado.
- Word, JSON dos resultados e JSON completo de entradas/hipóteses disponíveis no painel.

## API

`current_configuration(data, three_girt)` propõe configuração explícita a partir da fonte própria atual. `calculate(data, config)` calcula N/My/Mz/B/T por membro, combinação, x e lado. `attach_g81(result)` consome a capacidade G8.1 já implementada em `aisi_torsion_component`, sem alterar N. O snapshot da geometria própria fornece somente geometria, material e ações; não transfere a qualificação resistente da travessa isolada.

`recover_exported_state(model, beam, x_mm)` avalia N/M/V/B/T nos trechos salvos sem nova solução da rede. `normal_action_polynomials` tem coeficientes crescentes na coordenada t=(x-x_start)/length, N constante, My/Mz quadráticos. `torsion_state_parameters` guarda solução exata torcional por trecho. Essa API permite a interação N/M em andamento localizar seu máximo concomitante sem adotar máximos de componentes distintos.

## Mapa e contratos

R01 x aponta da alma para os lábios, R01 y é o outro eixo transversal. Para a travessa boca para baixo: Y=−x_R01 e Z=−y_R01, com rotação própria que preserva omega. Istrong=Ix_strong_R01; Iweak=Iy_weak_R01. Tensões: sigma=N/A−My_frame*y_R01/Istrong+Mz_frame*x_R01/Iweak+B_frame*omega/Cw. Portanto Mx_R01=−My_frame, My_R01=−Mz_frame e B_R01=B_frame. O sinal de resistência fraca NBR deve respeitar seu contrato próprio, não apenas o nome My físico.

As barras são axiais bilaterais e de primeira ordem. N central e compressão nas barras não são apagados. G8.1 só é componente ao bimomento; H4 reduzido não é aplicado. A matriz de combinações atual é preservada, sem recombinação LRFD AISI. O índice Bsd/Ba é comparação complementar condicionada, não declaração de compatibilidade normativa global de ações/resistências. Não verifica tirantes, ligações, ancoragens, ELS ou estabilidade global.

Cargas concentradas ativas no modo direto são recusadas, não descartadas. Geometrias fora dos sete contornos próprios íntegros não recebem omega ou Cw inventados. O elemento exato reutilizado mantém seu domínio numérico 0≤kL≤10.

## Testes proporcionais

- Caso atual de QA: Ue próprio 1,50 mm, L=4000 mm, 19 combinações, 84 DOFs, pontos materiais e ações declaradas. Não é projeto físico.
- Replay de um fixture original congelado, rotulado histórico; não é usado como entrada atual.
- Mutação de CP recalcula também as forças de interface; não congela forças dos tirantes.
- Corpo livre, trabalho de ponto, energia, balanço de bimomento, vínculos, origem setorial e recuperação constitutiva/equilíbrio.
- Teste AppTest real: ativa painel, calcula, muda combinação e exporta sem resolver novamente; alteração da linha externa invalida o resultado.
- Regressões do núcleo 6DOF e da aplicação própria isolada preservadas.

Logs, entradas, resultados e memória de QA estão em `results/`. A memória Word foi renderizada e inspecionada em três páginas; as imagens/PDF são somente QA.

## Reprodução

Usar `PYTHONPATH=/tmp/tercas_publish_deps OPENBLAS_NUM_THREADS=1 python -m pytest tests` no pacote para testes, ou executar os testes novos dentro de `candidate` com o mesmo ambiente. O ambiente já contém dependências da publicação. Não instalar globalmente.

`python run_current.py results/CURRENT_QA_INPUT.json resultado.json --base candidate --g81`

Nenhum novo espectro de flambagem, casca, 2D ou análise não linear foi introduzido. As propriedades de contorno e o solver exato previamente ensaiados foram reaproveitados.
