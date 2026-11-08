# Referência FLT já qualificada no recálculo fresco

## Alteração concreta

O consumidor `nbr_ue_family_application_v5_current_reference` seleciona a
referência q+P Vlasov/Ritz v2 já existente também no recálculo de entradas sem
`flt_combined_height_method`. Não exige adesão adicional e não acrescenta o
marcador às entradas. A API histórica permanece inalterada; a nova seleção
ocorre por `qualify_family_fresh`, com certificado
`flt_height_current_reference_v2`.

A referência ENV dos casos puros continua preferida. O Ritz só é chamado no
seu domínio anterior: contorno próprio simétrico da família completa de 66 Ue,
um vão físico com garfos extremos/empenamento livre, Ly=Lz=L, alturas individuais
conhecidas e projeção paralela elegível quando existente. Geometria e posições
são autenticadas no mesmo contorno. Material vem da mesma seção resistente.
O algoritmo, bases e critério de refinamento não mudaram.

Não há reescala do autovalor, redução do vão físico ou nó intermediário.
Comprimentos resistentes diferentes de L continuam fora desse Ritz. Nesses
casos, o piso condicional v2 anterior continua disponível; exceder seu índice
não prova reprovação. Não convergência continua explícita e não cria referência
numérica utilizável. Erros inesperados não são absorvidos pelo novo seletor.

O Me numérico continua uma referência aproximada, sem certificado de limite
inferior ou crítico exato. O consumo NBR é o já existente, com o mesmo material,
contorno, ações e seleção de componentes. A alteração não resolve pré-deformação
por torção, autovalor biaxial ou aprovação global. Telha não fornece rigidez.

## Comprimentos e referência ENV

O esclarecimento de saída fresca registra que Ly/L e Lz/L são adotados como
fatores equivalentes kz/kw na expressão aproximada. O valor 0,5 corresponde à
hipótese resistente ideal na direção relevante; não comprova nem identifica
automaticamente a fixidez real. A tabela F.1.2 inclui k=0,5 no mesmo diagrama
biapoiado: a rotação lateral e o empenamento não se confundem com o vínculo no
plano forte. Não se mudaram coeficientes nem se introduziu um novo gate físico.

Fontes que já sustentavam os métodos:

- ENV 1993-1-1:1992, Anexo F, F.1.2(2)–(5), F.2/F.4 e Tabela F.1.2.
  URL preservada: https://www.shining-solutions.com/wp-content/uploads/2024/10/DD-ENV-1993-1-1-1992-Steel-Design.pdf
- Reprodução didática Castiglioni/Politecnico, PDF páginas 47 e 50,
  conferidas visualmente nesta revisão:
  https://www.c430.it/pas/doc/edilizia/acciao-statilimite-ntc.pdf
  SHA256: 0e0715f5f026468b0590db9c52cbcf60ee1374446da1e3d3d3d2ba5afceddd3b.
- SCIA distingue fator de comprimento, fator de fixidez e fator de empenamento:
  https://help.scia.net/19.1/en/pvt/steelcodechecktb/en/lateral_torsional_buckling.htm
- Energia e potenciais individuais, Sahraei/Pezeshky/Mohareb (2017), Eq.2:
  https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf
- Simetria de canais e expressão documental, Vermeylen et al. (2023), Eq.1:
  https://orbi.uliege.be/bitstream/2268/306606/1/VermeylenMaxime-Eurosteel%202023.pdf

Nenhum PDF integral é incorporado ao delta. Esta revisão não afirma mudança
na edição normativa adotada nem nova qualificação experimental dos métodos.

## Preservação

O replay do certificado v5 chama novamente o operador Ritz para autenticar os
valores, assim como já faziam as referências opt-in anteriores. Portanto o
rerender v5 não é descrito como livre de solver nem como cache numérico novo.
Somente os oráculos v3/v4 sem marcador abaixo são validados com solver proibido.

O leitor v1/v2 permanece nos módulos anteriores. O leitor v3 usa piso de
energia v1 e seleção histórica; v4 usa piso v2 e seleção histórica. Um resultado
antigo sem marcador continua pendente na referência q+P quando apenas lido;
só um novo cálculo usa o seletor v5. Marcadores explícitos v1/v2 mantêm sua
versão. Os oito snapshots v3/v4 sintéticos para índices 0,26,53,79 foram gerados
na base congelada antes da alteração, para comparação independente do replay.

Panorama, Word e UI reconhecem o novo schema. O epoch da sessão invalida
somente caches ativos; não altera JSON de entrada, resultados exportados ou
históricos. A tabela de componentes conserva separadamente referência numérica,
piso suficiente e pendências. Não há publicação remota nem dados de projeto.

## QA

Base: 23de0dd535bf71f863c2ca9e2fba3ef8fa5032be. Testes novos cobrem seleção fresca
66/66 com projeção paralela elegível, invariância de entrada/ações, material e
consumo resistente, guardas de comprimentos, geometria/posição paralela,
marcador inválido, versão explícita v1, falha de convergência e erro inesperado,
replay adulterado, leitura v3/v4 e AppTest de importação, cálculo, JSON/Word e
rerender. Resultados finais são registrados no recibo ao concluir a focal.

Primeira focal: 119 testes passaram em 51,06 s, exit 0. Incluiu os arquivos
`test_flt_fresh_reference`, `test_nbr_family_height_integration`,
`test_nbr_family_floor_consumer`, `test_nbr_family_panorama`,
`test_nbr_family_word_dispatch` e `test_ui_flt_fresh_reference`.
Os oito oráculos v3/v4 efetivamente produzidos na base passaram no replay,
sem solver e sem mutação. SHA256 do JSON sintético externo ao pacote:
6d295e307695acbc32c999c67a9b40438c5e256f1e84e189414cfecda18f9c00.
A revisão estática independente confirmou o fluxo fresco, os guardas e o
replay, sem apontar bloqueio; não se apresenta essa revisão como teste numérico.


Focal final de compatibilidade: 471 testes passaram em 154,96 s, exit 0,
singlethread. Arquivos: `test_nbr_ue_family_application`,
`test_flt_combined_height`, `test_flt_height_effective`,
`test_flt_energy_moment_product`, `test_ui_cache_epoch`, o controle novo de
material variável e `test_ui_flt_fresh_reference`. A contagem não é somada à
primeira focal como se todos fossem testes diferentes.

O AppTest final usou timeout de 60 s em cada etapa: importação 1,79 s,
cálculo com Word/JSON 3,27 s e rerender com Word/JSON 2,14 s. Não houve timeout
nem troca silenciosa de snapshot. O rerender inclui a autenticação numérica
existente do Ritz; esses tempos não são promessa para toda entrada.

Compileall e `git diff --check` passaram. Os avisos de teste foram ambientais
Streamlit/Fontconfig e de API de largura depreciada, sem falha funcional.
Esta é uma focal do delta, não execução da suíte total nem aprovação de projeto.

Exemplo independente sintético de utilidade: índice26, L=Ly=Lz=4100 mm,
q externo ELU=0,3 N/mm, P=300 N em1537 mm, inclinação5,71°. O antigo piso
fornecia índice1,22908, inconclusivo; a referência existente agora selecionada
fornece índice0,857949 na componente FLT, com Msd=0,978072 kNm e
MRd de referência=1,140013 kNm. Não se trata de prova de limite inferior nem
aprovação global. Os dados são apenas uma fixture artificial.

Recibo compacto: `qa/FLT_CURRENT_REFERENCE_R18_20261108.json`. Os hashes de
JUnit bruto e sanitizado são separados; o bruto e os logs permanecem fora do
repositório. Nenhum nome de máquina foi copiado ao recibo.
