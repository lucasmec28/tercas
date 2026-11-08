# Fechamento complementar da alma nos apoios

O novo `support_web_completion_v1` consolida a evidência local já calculada, sem alterar o resultado-base ou sua avaliação global. Mantém um envelope separado com o hash integral do resultado-base, o sidecar de apoio e uma projeção dos 19 requisitos. Somente o requisito de alma nos apoios recebe evidências locais adicionais. Demais registros e flags globais permanecem preservados.

A consolidação exige inventário original de terça isolada existente e válido. Não migra estudos antigos, não aceita inventários vazios, só ELS, duplicados ou incompletos, e não promove outras fontes 7GL ou amplia um escopo central. O leitor v1 de apoio e seus downloads permanecem intactos, sem reclassificação retroativa.

Antes de consumir os resultados, o contrato novo reconcilia forças, posições, eixos, combinações e inventário de apoios com `sources.extract`, e reconcilia seção, material, geometria, FRd, índice e decisão com a fórmula escalar existente. A fonte direta inclui PP por seu contrato, equilíbrio de q/P e posições reais. Não há solver de membro. As revisões exatas de `support_web/mechanics.py` e `core/anexo_d.py` são fixadas por SHA256; revisão desconhecida é recusada, não atualizada silenciosamente.

Esse replay escalar pertence somente ao novo contrato e pode ocorrer na sua leitura/exportação. Os leitores históricos continuam sem novo cálculo. Autoridade é técnica/do software, não assinatura do arquivo nem prova física do detalhe: as declarações de contato e ligação continuam hipóteses informadas. Uma edição consistente de todos os dados declarados é outra hipótese, não prova de autenticidade física.

A exceção §9.5.1 dispensa somente enrijecedor transversal na alma declarada ligada a viga/pilar. Não dimensiona ligação. Reação normal zero dispensa somente o mecanismo normal. P no limite matemático de apoio não cria detalhe de contato. Ancoragem em sucção, esforços paralelos, momento, torção e ligação completa permanecem separados, sem inventar uma interação M+F de outra norma.

Na interface, o usuário calcula o critério local e escolhe explicitamente consolidar sua evidência. O painel mantém os JSON/Word locais antigos e acrescenta downloads de fechamento complementar JSON/Word, com resultado-base identificado, estados locais e inventário preservado. A consolidação pode registrar falhas ou pendências; não significa atendimento local automático nem conclusão global.

Testes cobrem conservação do original, JSON/Word, fluxo de interface, configuração alterada, PP+q/P, força normal zero, inventários vazios/só ELS, versão desconhecida e adulterações com rehash deliberado de capacidade, ações, posição, material, detalhe, exclusão, duplicação, contagens e aprovação. Não constituem validação física de um projeto.

O JSON complementar não incorpora o resultado-base. É necessário conservar também o JSON original do estudo para validar ou reabrir a evidência. Não é um arquivo de entrada substituto.

Verificação focal final: 498 testes passaram em 22,60 s, incluindo interface, consumidores e adulteração de metadados. Recibo e JUnit em `qa/support_web_completion/`. Não é a suíte integral.
