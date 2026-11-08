# ELS local forte por MLE nas quatro Ue fora da Tabela 12(b)

## Base e fontes

Base de desenvolvimento: 97734054fc603c16021717cd32e12c629a8fa1d6. Implementação nova e isolada em `tercas/nbr_service_strong_mle.py`; nenhum consumidor, histórico ou cálculo de ELU alterado.

NBR 14762:2010, PDF SHA256 c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407. Conferência visual das páginas PDF33–35 e57–58, em especial §9.2.2.2, Tabelas5/6 e §9.8.5. PDF não incluído na entrega.

§9.8.5(a) fornece a alternativa MLE diretamente, sem exigir um momento crítico Ml. §9.2.2.2 pede aproximações sucessivas e a compressão máxima calculada na seção efetiva na combinação de serviço. Portanto uma resistência, Ief ou módulo resistente não deve ser convertido em crítico para usar a alternativa MSE.

## Método e reaproveitamento

O helper existente `nbr_ue_family_expansion.strong_effective_modulus` integra o contorno arredondado, preserva cantos e reduz mesa/lábio segundo sua convenção escalar NBR/CBCA, comprovando a alma integral pela partição da Tabela5. O novo módulo resolve a compatibilidade σ=|M|/Wc(σ) com iteração escalar bracketada, guarda residual e verifica a fibra tracionada. A chamada ao helper ocorre na tensão de serviço resolvida, não em fy para obter uma resistência. A busca começa na tensão bruta e cresce somente até encontrar compatibilidade, até fy ou até a borda do domínio implementado. Uma alma reduzida em fy não impede uma solução com alma integral na tensão real de serviço. Nenhuma etapa produz Ml ou resistência de projeto.

A flecha é a integral de M(x)m_virtual(x)/(E Ixef(M(x))). São usados os esforços isostáticos no vão físico e as cargas já combinadas recebidas do chamador. Não se usa Ief mínimo constante, não se acrescenta peso próprio nem se altera o carregamento. Carga uniforme e uma carga pontual podem ter sinais opostos. Zeros do momento particionam intervalos de inclinação monotônica: os zeros da inclinação nesses intervalos dão todos os candidatos a máximo absoluto da flecha, juntamente com apoios. O módulo devolve sinal e máximo absoluto.

## Escopo e limites

- Somente índices completos79–82, Ue300×100×25, espessuras3,35/3,75/4,25/4,75mm. A simetria horizontal permite a reflexão do lado comprimido sem alterar Ief/Wc/Wt.
- Componente de flexão forte local convencional. Não é seção tensorial, não atualiza torção, não inclui rotação de seção no deslocamento de ponto e não aprova o membro. Não reabre ELS combinado.
- Alma deve permanecer integral conforme a prova existente, em todas as avaliações necessárias. Necessidade de reduzir alma gera `OutsideMethod`, sem aprovação bruta por fallback.
- Compressão e tração não podem exceder fy. Geometria, material e ações devem ser válidos. Modelo isostático simplesmente apoiado, ações transversais fixas, pequenas deformações.
- Não é uma avaliação normativa de ELU, FLT, distorção, cortante ou resistência global.
- Brent fornece raiz compatível e residual controlado. Os ensaios de curva monotônica abaixo são verificação numérica, não prova matemática contínua de unicidade para qualquer material arbitrário. Não se declara tal prova.
- O estimador de erro de quadratura é verificado; não é um certificado de aritmética intervalar. Falha numérica deve permanecer pendente no consumidor.
- `section_at_max_moment` usa o lado comprimido de referência. Quando o momento real for negativo a geometria deve ser entendida refletida, e não como novo centroide físico permanente.

## Ensaios sintéticos focados

13 testes passaram em3,59s, sem UI/rede e sem dados do usuário: curvaσ/Wc em11 tensões de1 a350MPa para cada índice; espelhamento de sinais; alma integral; rigidez não crescente; flecha de carga uniforme e pontual central contra soluções fechadas de seção integral para as4 linhas; integral independente no caso reduzido; ponto excêntrico e cargas opostas contra expressão fechada independente; domínio inválido e carga nula.

A350MPa, E=200000MPa, Ixef/Ig: índice79=0,9533568709;80=0,9693877476;81=0,9758300958;82=0,9849765698. São resultados seccionais nessa tensão, não cargas de serviço atribuídas ao usuário. A faixa ensaiada é numérica e não uma nova restrição imposta pela norma.

## Contrato sugerido ao consumidor

Após o binding confiável de seção própria e escopo local já adotado pelo app, se Ml_SLS estiver ausente por estar fora da Tabela12(b), chamar a nova rotina com índice/material da identidade validada e os campos SLS (q/P/x), L físico e limite existentes. Registrar método `NBR9.8.5(a)_pointwise_MLE`, fonte, tensão efetiva/residual e seção de máximo momento. Não preencher Ml_SLS. Não afirmar a fórmula MSE no texto da evidência da lei MLE. Capturar falhas de domínio/numéricas como ELS pendente, preservando cálculos de ELU e histórico. O consumidor foi implementado em commit separado em `own_service_mle`: identidade e domínio são validados, e o spec recebe `MLE_SLS` congelado. O resultado registra separadamente tentativa e cálculo concluído; reportes leem somente a evidência salva.

Revisão independente:20.000 pontos de σWc, incluindo materiais extremos, não mostraram inversões onde a lei era aplicável. Quatro comparações com Simpson4001 e bisseção independente tiveram erro relativo máximo8,14e-9. Essas verificações não constituem prova contínua de unicidade. O teste de ações opostas q=10N/mm,P=−37500N,L=6000mm,a=3000mm verifica três estacionários, com máximo absoluto fora do centro.

## Integração e verificação do consumidor

`own_service_mle` somente é selecionado após a validação de contorno próprio, modo local e indisponibilidade real da Tabela12(b). O snapshot `MLE_SLS` é separado de `Ml_SLS`, que continua sem valor nas quatro linhas. No cálculo novo, a identidade nominal, nós, perfil e propriedades canônicas do índice são conferidos novamente: trocar79 por80 e recalcular todos os hashes não permite calcular outra espessura sobre o snapshot antigo. O material é extraído explicitamente dos campos E/G/fy já vinculados; nu e gamma seguem o contrato da rotina seccional, sem usar resistência ou fator de ELU no resultado de flecha.

O bloco ELS grava tanto a evidência da tentativa quanto, quando concluído, a seção, a compatibilidade e o resultado integrado. Falhas permanecem sem índice. A lei MLE é descrita corretamente nos metadados e Word; uma falha não é apresentada como cálculo MSE. Os snapshots antigos permanecem descritivos, sem nova qualificação na leitura.

Verificação final de42 testes sem UI: todos passaram em28,74s. Inclui13 testes de núcleo MLE,11 testes de consumidor MLE e18 testes de Ml_SLS. Os cálculos reais de aplicação abrangem as4 linhas em entrada direta e por área, JSON e Word congelados, retorno de pendência por tensão excedida, preservação bit a bit de ELU/FLT/seção e adulteração coerente de índice. Fonte de limite, vão, ações e adição única de peso próprio são preservados pelo contrato original do adaptador.

UI:1 AppTest passou em8,58s, importando a linha79, executando o botão de cálculo e verificando índice MLE, linha de flecha local e invariantes físicos/ações/material/limite. O importador já normaliza metadados auxiliares (`weak_catalog`/origens) no fluxo existente; o teste não confunde essa normalização com alteração física. Não foi feita homologação nem publicação.
