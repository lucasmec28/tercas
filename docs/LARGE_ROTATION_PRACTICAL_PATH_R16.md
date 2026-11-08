# Grandes giros: caminho prático a partir de R16

Revisão técnica de 07/11/2026. Base inspecionada: 631b0de017b12b9c6b95a8f2be9809766aad19c3. Documento de pesquisa e plano de qualificação, não nova prescrição normativa nem aprovação da estrutura. Nenhum caso privado foi usado como fixture ou exemplo.

## Resultado

Preservar os métodos simplificados normativos existentes dentro dos seus domínios. Não há fundamento nesta pesquisa para converter um ângulo fixo em nova reprovação, exigir GMNIA de toda terça, interpretar Leff como apoio físico ou acrescentar rigidez da telha. Quando a hipótese de pequenas rotações precisar ser investigada, existe caminho intermediário menor que um modelo de cascas elastoplástico: análise geometricamente não linear, inicialmente elástica, de viga 3D com empenamento da seção aberta e cargas excêntricas corretamente transportadas. Essa opção ainda precisa ser integrada e verificada para este aplicativo; a disponibilidade comercial do elemento não qualifica automaticamente um caso.

## O que o código já resolve

- `tercas/torsion_vlasov/vlasov.py`: energia linear GJ/ECw, translações/resultantes concomitantes e torção sobre o centro de cisalhamento. `resolve_actions` calcula cada torque a partir da posição inicial e do vetor da força. A API declara fora de escopo forças seguidoras e segunda ordem.
- `tercas/isolated_service_mechanics.py:displacement_field`: flexão tensorial Euler–Bernoulli no centro de cisalhamento, mais phi vezes o produto vetorial do braço do ponto. Projeção e subtração da corda usam o mesmo ponto; não somam máximos de posições diferentes.
- `tercas/direct_torsion.py:actions`: preserva separadamente PP no CG, ações externas no topo e força concentrada. Importante para investigar torques que se cancelam na posição inicial e deixam de se cancelar ao girar.
- `tercas/torsion_applicability.py`: aviso de primeira ordem e preservação dos resultados; não é qualificação de resposta física para grandes rotações.
- A rede `three_girt_warping` também é de primeira ordem. Refinar sua malha ou verificar resíduos não acrescenta não linearidade geométrica.

## Três questões diferentes

Considere uma seção rígida no próprio plano, rotação prescrita phi em torno do eixo longitudinal e braço transversal r=(rx,ry) do centro de cisalhamento ao ponto. R(phi) é a rotação plana usual, e Jr=(-ry,rx).

1. **Posição do ponto:** a parcela rotacional exata para essa rotação prescrita é (R-I)r; a linear é phi Jr. Sua diferença é [(cos(phi)-1)rx-(sin(phi)-phi)ry, (sin(phi)-phi)rx+(cos(phi)-1)ry]. Translações concomitantes e corda do mesmo ponto precisam ser incluídas ao calcular deslocamento de serviço. Não se deve empregar phi máximo de uma estação com translação máxima de outra.
2. **Força morta:** significa direção mantida no referencial espacial, não sinônimo de carga permanente. Para F fixo e ponto material girando, torque transversal instantâneo sobre SC é (Rr)×F. Ele geralmente varia com phi. Trabalho potencial -F·u_P é coerente com essa força conservativa, sob as hipóteses declaradas.
3. **Força seguidora:** se, especificamente, F(phi)=R(phi)F0 e o braço gira pela mesma R, (Rr)×(RF0)=r×F0. Isso não prova conservação de energia nem equivalência global do problema; a força também muda de direção e sua tangente de carga precisa entrar no equilíbrio. Pressão, vento e transmissão pela cobertura não podem ser classificados automaticamente como seguidores da rotação da terça isolada.

Essas fórmulas são identidades de cinemática e transporte de força, não um solver. Substituir phi pelo campo linear e aplicar sen/cos produz uma avaliação sobre uma configuração postulada, não a configuração de equilíbrio não linear. Atualizar só o torque e iterar o bloco linear ECw/GJ também não demonstra um modelo geral adequado: faltam consistência da energia interna, acoplamento flexão-torção, transporte de eixos e possivelmente efeitos de encurtamento e de empenamento.

## Implementação segura imediata

Um utilitário diagnóstico puro pode receber phi concomitante, braço r, projeção e força e devolver:

- parcela linear e parcela de rotação finita **prescrita** do ponto;
- diferença vetorial/projetada e norma dessa diferença;
- torque no braço inicial, torque no braço girado para força morta e variação absoluta;
- alternativa explicitamente hipotética de força seguidora;
- unidades, referencial, origem do phi e escopo expresso: não é deslocamento ou torque corrigido em equilíbrio.

Não gerar `meets`, `fails`, fator resistente, porcentagem com denominador nulo, novo limite angular nem aprovação. Preservar hashes, resultados, cargas e flags normativas. Para forças distribuídas usar N/mm e torque por comprimento em N; para concentradas N e Nmm. Não confundir unidade de um tipo com o outro.

É possível dar um limite geométrico conservador sem amostragem: para |phi|<=p, a norma do defeito é <= |r| p²/2, por resto integral da expansão de R. Trata-se de limite absoluto do defeito para rotação prescrita, não de limite do erro da solução estrutural. A diferença projetada de deslocamento relativo à corda inclui os defeitos nos dois extremos; ignorá-los só é permitido se forem efetivamente nulos. O bound não é critério de validade e pode ser pouco informativo para p grande.

Não recomendo anexar automaticamente esse resultado ao ELS como se corrigisse sua flecha. Primeiro um diagnóstico separado e testes sintéticos; depois integração de apresentação com rastreabilidade do ponto e das cargas, se houver utilidade clara.

## Menor modelo existente a qualificar

Opções implementadas por fornecedores:

- Abaqus/Standard B31OS/B32OS: vigas de seção aberta com grau de liberdade de empenamento. A documentação de análise estática permite NLGEOM e distingue análise geométrica não linear de não linearidade material. A seção geral aceita propriedades pertinentes e localização do centro de cisalhamento; a correspondência exata das convenções de empenamento deve ser auditada antes de exportar.
- Ansys BEAM188 (ou BEAM189): viga 3D com opção explícita de sétimo grau de liberdade WARP. BEAM188 documenta grandes rotações e saídas de bimomento/bicurvatura quando ativado. Não usar o default de seis graus de liberdade como substituto silencioso da rota ECw.

Esses são candidatos existentes, não solvers disponíveis/qualificados aqui. `abaqus` e `ansys` não foram encontrados no PATH desta revisão. Não houve instalação, execução comercial, validação de licença ou tentativa de contornar acesso.

Para o aplicativo, a próxima entrega mínima útil é especificação de intercâmbio e benchmark independente de uma dessas opções, antes de escrever um novo elemento. Entrada: seção/CG/SC/eixos/E/G/ECw, comprimento físico, condições de translação/rotação/empenamento, origem axial de cada ação, braço e lei de direção, convenção de força por comprimento de referência/deformado. Saída: trajetória de carga e estado convergido, deslocamentos/rotações concomitantes, esforços incluindo B, reações, resíduos, energia e identificação da discretização. Não transportar comprimentos resistentes para vínculos. Preservar o apoio idealizado declarado; não inventar certificação física universal.

A cinemática de seção rígida no plano exclui flambagem local/distorcional e deformações da ligação. Material elástico exclui plastificação. Equilíbrio calculado não equivale a estabilidade da trajetória nem a resistência normativa. Se surgir ponto-limite ou bifurcação, a continuação e interpretação merecem tratamento próprio; uma análise de caminho instável não é o próximo passo obrigatório para todos os casos.

## Testes propostos

Diagnóstico leve, sem solver:

1. phi=0, r=0 e F=0; sem divisões singulares.
2. rotações de quarto/meia volta, de ambos os sinais, contra coordenadas analíticas independentes.
3. erro absoluto O(phi²) e aproximação delta_u≈-phi² r/2 para phi pequeno, com avaliação numericamente estável de cos(phi)-1.
4. covariância sob rotação do sistema transversal e escala de unidades.
5. força morta excêntrica: torque derivado de -F·Rr e consistência de sua derivada; força seguidora ideal: invariância de torque sobre SC.
6. torque inicialmente nulo que se torna não nulo; cancelamentos entre ações não apagar parcelas.
7. extremos com rotações não nulas: subtrair a corda do mesmo ponto.
8. rejeitar NaN, infinito, booleanos numéricos, dimensões incompatíveis e projeções inválidas; nenhuma mutação de inputs.
9. consumidor do diagnóstico não alterar resultados, resistências, flags, hashes, Leff ou apoios.

Qualificação futura do modelo não linear:

1. limite de carga tendendo a zero reproduzindo solução Vlasov e flexão tensorial, inclusive empenamento livre/restrito e seção com CG≠SC;
2. modo de corpo rígido: energia/deformação internas nulas; objetividade de resultados após rotação global;
3. flexão, torção uniforme e não uniforme, forças q/P excêntricas e combinação biaxial; comparar com soluções fechadas somente onde aplicáveis;
4. distinguir força morta/seguidora no mesmo braço e verificar trabalho/reações/tangente externa;
5. cargas aplicadas em pontos materiais de excentricidade conhecida, sem rigidez fictícia introduzida pelo método de aplicação;
6. convergência de malha, incremento e tolerância, mais comparação independente do caminho de equilíbrio; não só do último número;
7. conferir tensões recuperadas com B, convenções de eixos/SC, parcelas de PP e ausência de dupla contagem;
8. falha de convergência/ramo instável/domínio excedido retorna lacuna explícita, nunca aprovação por ausência de resultado.

## Fontes primárias consultadas

As fontes abaixo documentam capacidades e hipóteses de modelos. Não são novas regras NBR/AISI.

1. Dassault Systèmes, *Choosing a Beam Element*, Abaqus 2026: https://docs.software.vt.edu/abaqusv2026/English/SIMACAEELMRefMap/simaelm-c-beamelem.htm . Conteúdo encontrado no índice de busca; abertura direta indisponível nesta sessão. Sustenta identificação B31OS/B32OS e grau de liberdade de empenamento.
2. Dassault Systèmes, *Static Stress Analysis*, Abaqus 2026: https://docs.software.vt.edu/abaqusv2026/English/SIMACAEANLRefMap/simaanl-c-static.htm . Página aberta. NLGEOM, material separado e caminhos instáveis.
3. Dassault Systèmes, *About Loads*, Abaqus 2026: https://docs.software.vt.edu/abaqusv2026/English/SIMACAEPRCRefMap/simaprc-c-loading.htm . Página aberta. Força com direção fixa versus seguidora e contribuição de rigidez de carga possivelmente não simétrica.
4. Dassault Systèmes, *BEAM GENERAL SECTION*, Abaqus 2026: https://docs.software.vt.edu/abaqusv2026/English/SIMACAEKEYRefMap/simakey-r-beamgeneralsection.htm . Página aberta; confirmar mapeamento completo antes de implementação de deck.
5. Ansys, *BEAM188*, 2026 R1: https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_BEAM188.html . Página aberta. Grandes rotações, sétimo grau de liberdade opcional e saídas B/bicurvatura.
6. OpenSees, *Corotational Transformation*: https://opensees.github.io/OpenSeesDocumentation/user/manual/model/geomTransf/Corotational.html . Resultado oficial de busca descreve transformação geométrica exata; isso isoladamente NÃO demonstra elemento com empenamento apropriado à seção aberta.

Literatura localizada, mas texto integral não acessível nesta sessão; não utilizada para alegar formulação implementada/validada: *Geometric and material nonlinear analysis of thin-walled members with arbitrary open cross-section* (2021), https://www.sciencedirect.com/science/article/pii/S0263823120306613 ; *Large torsion analysis of thin-walled open sections beams by the Asymptotic Numerical Method* (2015), https://www.sciencedirect.com/science/article/pii/S0141029614006038 . Os resumos localizados motivam cautela com empenamento, encurtamento e acoplamento. Abertura retornou HTTP 403; nenhum contorno de acesso tentado.

## Estado da revisão

Inspeção de código e pesquisa concluídas. Documento local, sem publicação. Nenhum solver, benchmark numérico ou suíte pesada executado. O documento não encerra a qualificação física de grandes giros e não transforma essa lacuna em requisito normativo universal.

## Implementação local posterior à revisão do plano

`tercas/rotation_geometry_diagnostic.py` implementa o diagnóstico puro e `saved_maximum_twist_load_lines(result)`. O leitor reutiliza a validação do leitor torsional existente (incluindo hash do snapshot torsional quando existe evidência AISI), confere identidade/estação da testemunha, braço/força/torque inicial e usa somente o phi concomitante no máximo de giro salvo. As cargas uniformes podem ser avaliadas nessa estação. Uma força concentrada em outra estação retorna motivo de indisponibilidade, sem usar esse phi indevidamente. O máximo de giro não é apresentado como máximo da diferença geométrica ou da sensibilidade do torque. Momentos diretamente aplicados são identificados, mas excluídos da parcela de braço vezes força.

A lei de direção de força NÃO está declarada fisicamente no contrato salvo: por isso toda comparação de torque é rotulada como cenário hipotético de direção fixa nos eixos de seção salvos. O leitor não seleciona seguidora/morta como fato e não produz uma solução estrutural. Nenhuma UI, migração, alteração de hash, novo critério ou status foi acrescentado. O utilitário não computa flecha relativa à corda: devolve somente a parcela rotacional local; integração futura precisará das três estações concomitantes do mesmo ponto. O corte interno na série de Taylor de seno é apenas tratamento numérico de cancelamento, não classificação de giro nem limite de engenharia.

Este leitor verifica consistência nos mesmos limites do contrato histórico: sem hash torsional independente no histórico, identidade/fingerprint e coerência interna não são autenticação contra adulteração coordenada. Ele não melhora implicitamente a proveniência do dado salvo.

O diagnóstico também devolve a diferença por unidade de raio, sqrt((cos(phi)-1)²+(sin(phi)-phi)²). Ela independe da orientação do braço. A derivada do seu quadrado para phi>=0 é 2 phi (1-cos(phi))>=0; portanto o máximo absoluto de phi salvo fornece o máximo desta diferença normalizada no campo salvo, sem escolher ponto do projeto. Esse máximo normalizado é distinto da amostra de torques e não é percentual de erro físico, flecha relativa à corda ou nova condição de aprovação.

Verificação local final: 74 testes passaram (arquivo novo mais leitor de aplicabilidade existente), sem solver, com BLAS/OMP/MKL em uma thread e OpenBLAS Haswell. `compileall` e `git diff --check` passaram. Não executada suíte completa nem navegador.

## Conexão de apresentação adicional

A apresentação compartilhada `torsion_applicability` agora inclui somente a distância geométrica normalizada pelo raio, calculada pelo helper puro `normalized_rotation_difference` a partir do máximo de phi já validado. A linha aparece tanto na UI existente quanto na memória Word. Ela esclarece rotação prescrita, não erro físico nem limite de aceitação, sem correção de deslocamento/torque/equilíbrio e sem cálculo de flecha relativa à corda. Nenhum cenário de forças é apresentado; a API de leitura das forças continua somente instrumento de pesquisa. O helper não chama leitores, evitando recursão. O histórico sem evidência ou com registro inconsistente não ganha diagnóstico quantitativo.

Verificação desta integração: 80 testes leitores/geometria passaram, com solvers e acesso ao leitor de forças proibidos nos testes de apresentação. UI simulada e parágrafos Word concordam, inclusive em zero, giro pequeno, sinal negativo e rotações maiores. `compileall` e `git diff --check` passaram. AppTest/navegador ficam para a integração geral; nenhuma suíte pesada foi executada.
