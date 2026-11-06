# Aplicabilidade da torção linear na apresentação

## Decisão

Esta alteração só lê resultados salvos. Não muda Vlasov, ações, materiais,
comprimentos, vínculos, combinações, resistências, índices, estados ou hashes.
Não introduz análise não linear, limite normativo de giro, novo requisito de
resistência, dispensa ou aprovação. Não transporta comprimentos efetivos de
estabilidade para apoios do modelo torsional.

A análise existente declara primeira ordem e cinemática de pequenos giros.
Um número obtido dessa linearização não é previsão validada do giro físico
quando a própria triagem está ativa. O aviso existente de 0,05 rad continua
estritamente não normativo. A ausência do aviso também não valida a primeira
ordem. O status histórico de cada verificação permanece como foi salvo.

## Fonte técnica

Alsheikh, A. M. S.; Rees, D. W. A. (2021), *General Stiffness Matrix for a
Thin-Walled, Open-Section Beam Structure*, World Journal of Mechanics 11,
205–236, DOI [10.4236/wjm.2021.1111015](https://doi.org/10.4236/wjm.2021.1111015).
Na derivação cinemática do §3.2, pp. 211–212, os autores partem da rotação
finita e usam cos(phi) aproximadamente 1 e sen(phi) aproximadamente phi
para obter as equações lineares (1)–(4). Isso documenta a hipótese de pequenos
giros; não fornece um limite universal em radianos.
[PDF do editor](https://www.scirp.org/pdf/wjm_2021112915273879.pdf), consultado
em 06/11/2026. A fonte fundamenta a interpretação da cinemática, não novas
resistências NBR/AISI ou validação física de uma ligação.

## Comportamento e rastreabilidade

- `torsion_applicability.saved_notice` confere o fingerprint das entradas,
  identidade e contagem dos registros, domínio, finitude, tipo booleano do
  aviso e sua coerência com o limiar salvo. Quando existe complemento AISI,
  usa seu leitor de preservação, incluindo hash próprio e vínculo com o
  objeto torsional salvo. Não refaz o campo ou a solução.
- O panorama aparece no início da apresentação de resultados. O alerta de
  aplicabilidade precede o banner histórico, sem alterar seu texto/estado.
  A seção específica de torção e a memória Word repetem a ressalva antes
  dos números torsionais. Tabelas continuam mostrando os números originais.
- G8.1 acima de 1 é contado e mostrado como comparação condicional AISI
  preservada. Não é convertido em reprovação global NBR ou ruptura física.
  H4 dentro do limite é apenas condição algébrica nas hipóteses declaradas;
  H4 acima do limite com denominadores de piso permanece inconclusivo.
- Dados contraditórios mostram aviso explícito de registro inconsistente;
  o novo banner não emite um resumo quantitativo aparentemente válido.
  Não repara registros nem esconde/reescreve a evidência original.
- Histórico sem evidência torsional não ganha análise ou conclusão. Os
  cálculos novos usam os mesmos campos já produzidos, sem nova migração ou
  mudança de formato. A exibição é uma projeção, não um novo snapshot.

## Controles

`tests/test_torsion_applicability.py` usa somente objetos sintéticos de leitor:
avisos presentes/ausentes, fronteira exata do limiar existente, valores
negativos, identidades/contagens inválidas, booleanos falsos, dados não finitos,
fingerprint e hashes adulterados, legenda condicional e ordem das mensagens.
Solvers e o construtor do panorama ficam proibidos por monkeypatch. A sequência
de apresentação e os parágrafos Word são conferidos sem recalcular.

Nenhum arquivo privado de projeto é fixture, documento ou parte deste patch.
Estes controles de apresentação não qualificam a mecânica para grandes giros
nem substituem análise de engenharia da estrutura real.

Recibo local em 06/11/2026: 120 testes passaram em 4,50 s, com dois controles
de relatório que geram cálculos novos deliberadamente não selecionados.
Comando: `python -m pytest -q tests/test_torsion_applicability.py
tests/test_global_verification.py tests/test_report_audit.py -k
'not full_word_technical and not invalid_aa_ui'`. BLAS/OMP com uma thread,
OpenBLAS Haswell. `compileall` dos cinco módulos alterados e `git diff --check`
passaram. Não foi executada suíte completa nem navegador/AppTest nesta frente.
