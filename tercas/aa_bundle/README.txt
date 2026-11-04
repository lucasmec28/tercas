PACOTE PORTÁTIL AA, PESQUISA FECHADA, SEM APROVAÇÃO FÍSICA

Três entradas independentes, sem seletor automático e sem fusão matemática:
 family_assess / family_assess_json / family_compare_component
 local_partition_assess(request, refinement_budget=64)
 local_partition_assess_json(raw, refinement_budget=64)
 local_partition_compare_component(request, component, criterion_mm, refinement_budget=64)
 positive_ratio_assess / positive_ratio_assess_json / positive_ratio_compare_component
As assinaturas family/positive_ratio compare_component são
(request, component, limit_mm). As três interfaces locais existentes são
encaminhadas sem alterar seu comportamento ou orçamento.

Uso: adicionar APENAS a raiz deste bundle ao caminho de importação da sua
aplicação; importar Bundle de aa_portable; criar Bundle(SHA256 confiável de
BUNDLE_MANIFEST.json), obtido do recibo externo da entrega. Não confiar em um
hash fornecido pelo mesmo download sem conferir sua origem. O loader verifica
seu próprio arquivo e todos os arquivos da clausura antes de cada chamada.
Alteração/falta de arquivo produz IntegrityError explícito, não teto parcial.
Verifique também o SHA do loader antes da primeira importação. Isso é
integridade de distribuição, não sandbox contra modificação concorrente hostil.

Não renomear/mover as subárvores outputs internas. Seus caminhos são parte dos
manifestos históricos; a pasta candidate contém SOMENTE sete JSON de geometria,
não aplicativo. Todos os originais copiados permanecem byte-idênticos.
Os recibos históricos mantêm inclusive descrições antigas de revisão pendente;
os três handoffs e relatórios posteriores registram seus encerramentos.

Requisitos: Python 3.12 (validado nesta entrega); mpmath 1.3.0 instalado no
ambiente Python. Nenhuma outra biblioteca externa, aplicativo, rede ou serviço
é requerido. Bibliotecas não são vendorizadas; nenhuma licença de terceiros
é implicitamente concedida por este pacote. Os arquivos de pesquisa e suas
fontes não receberam nova licença de redistribuição. Distribuição externa
continua sujeita à autorização de seus titulares. Não contém texto integral
licenciado da norma. Execução verificada com PYTHONPATH ausente, cwd arbitrário,
python -I, PYTHONDONTWRITEBYTECODE=1 (e sys.dont_write_bytecode=True no modo -I),
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1.

Contrato: fonte SHA explicitamente entre sete geometrias; E=200000 MPa,
nu=.3, fy=250 MPa; N=B=0; viga simplesmente apoiada; q e P assinados em
coordenadas de MOMENTO do contrato, não eixos físicos inferidos do app.
P nãozero exige 0<a<L. Não há support_limit, snapping, hull importado,
interpolação geométrica ou IDs de caso como dados físicos.
Família/local: schema_version aa_web_family_qp_component_v1.
Positivo: schema_version aa_web_positive_ratio_qp_component_v1.
Campos: schema_version, geometry_sha256, material {E_MPa,nu,fy_MPa}, L_mm,
q_N_mm [q0,q1], P_N [P0,P1], a_mm, N_N, bimoment_Nmm2,
supports='simply_supported_bending', stress_scope='bending_component_only'.

Resultados são TETOS DE COMPONENTES, não flechas reais. Teto acima de critério
é inconclusivo, não falha física. Domínio inconclusivo não entrega teto
utilizável. Os dois componentes permanecem explícitos. Partição retorna base
literalmente quando suficiente ou recusada; somente inconclusão do domínio é
refinada, com TODAS as folhas e um Green global. Razão positiva não é portada
para partição. Nenhum histórico, índice ou aprovação global é atualizado.

Limites: suportes seccionais com 70 dígitos e padding, não aritmética intervalar
formal. Green racional é condicionado a esses suportes. Nenhuma prova de
unicidade, seleção estável, torção, distorção, estabilidade global ou ELS físico.
Mesas/lábios reduzidos continuam fora do método. A lei/fonte normativa para
essa extensão não foi qualificada; não inventar lei para fechar a lacuna.
EC3 permanece pesquisa comparativa separada e NÃO integra este bundle.
