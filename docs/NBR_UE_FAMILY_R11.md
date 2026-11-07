# Família Ue NBR: ampliação paramétrica R11

## Resultado e limite da emissão

O lote trabalha nas mesmas 66 linhas Ue documentalmente completas. Nenhum nome novo ou lista de exceções por perfil seleciona as fórmulas. A geometria arredondada própria continua separada da referência nominal publicada. Não se transfere Ml, Mly ou Mdist Pierin para o contorno próprio.

Matriz sintética em L físico = 6000 mm, carga no centro de torção, E = 200000 MPa, G = 77000 MPa, nu = 0,3 e gamma = 1,1:

| fy (MPa) | Forte local | Forte FLT referência | Fraco positivo local/completo | Fraco negativo local/completo | D fraco negativo |
| --- | --- | --- | --- | --- | --- |
| 250 | 66 | 66 | 66 | 55 | 66 |
| 300 | 66 | 66 | 66 | 51 | 66 |
| 345 | 66 | 66 | 66 | 45 | 66 |
| 350 | 66 | 66 | 66 | 44 | 66 |

“Completo” nesta matriz significa disponibilidade das componentes de referência da flexão pura daquele eixo/sinal. Inclui a referência distorcional explicitamente aproximada. Não aprova ações reais, efeito de altura, flexão biaxial, torção/bimomento, serviço, ligações ou o membro físico. A distorção forte mantém 64 aproximações e duas dispensas da Tabela 14. A distorção positiva fraca é não aplicável apenas quando as provas de tração dos lábios e dobras estão presentes. D negativo disponível em 66 casos não supre a ausência de local/FLT nos casos restantes.

## Fontes verificadas

- ABNT NBR 14762:2010, §§ 9.2.2, 9.2.3, 9.3, 9.8.2.1, 9.8.2.2 e 9.8.2.3. O PDF fornecido pelo usuário foi preservado fora do repositório, SHA-256 `c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407`.

Precisão da referência: a autorização para obter Ml local por análise de
estabilidade elástica está em §9.8.2.1(b). §9.3 trata especificamente do crítico
distorcional. Uma referência genérica a §9.3 em recibos históricos não transfere
essa autorização à flambagem local. Contratos históricos não são recalculados.
- [CBCA, Steel Framing: Engenharia, 2016](https://www.skylightestruturas.com.br/downloads/101497_manual_lsf_engenharia_2016.pdf), páginas impressas 61–65 e 112–119. Tabelas 4.2/4.3 e exemplo 6.3.1.1 conferidos visualmente. SHA-256 `3fc032153cd5afdfa2710d402499a3ebde5353d0a167fdc220e18bdb0fa457b6`.
- [ANSI/SDI/AISI S100-2024 e Commentary](https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf), Apêndice 2, § 2.3.3.2(b), equações 8–11 e Commentary C-2.3.3.2. Somente a aproximação elástica é adotada por NBR 9.3. A curva resistente e gamma continuam exclusivamente NBR.
- [AISI S100-16 (R2020), Supplement 3, 2022](https://buildusingsteel-media.s3.amazonaws.com/wp-content/uploads/2023/06/23212327/AISI-S100-16-2020-wS3-22.pdf), PDF página 233: mesmas equações 8–11, conferidas visualmente como verificação independente dos símbolos lidos na edição 2024. SHA-256 `706a4bfaf030768d6382324a8d1916acdb749a0e739ef20fa0d7638ba8a9f03a`. A errata de novembro de 2023 trata de F3.2, não dessas equações.

Os arquivos de fonte protegidos não são incorporados ao repositório.

## Local forte fora da Tabela 12(b)

O MLE convencional do exemplo CBCA é aplicado somente se suas condições são demonstradas: mesa uniformemente comprimida com enrijecedor de borda simples, larguras efetivas e redução ds por Is/Ia, dobras preservadas e alma provadamente integral pela Tabela 5 no campo da seção já reduzida. A tensão uniforme adotada na mesa/lábio é uma envoltória conservadora do campo forte convencional.

As propriedades escalares Aef, CGy e Ixef são obtidas por remoção apenas dos trechos planos inefetivos do mesmo contorno. Wfirst inclui as duas fibras externas. Isso segue a convenção normativa escalar forte do exemplo; não é um operador tensorial exato de tensões 2D. O eixo/tensor de rigidez bruto do solver não muda. Os índices 79–82, fora da relação D/h da Tabela 12(b), são cobertos sem extrapolar seu polinômio e sem fabricar Ml. Se a alma precisar de redução, este ramo delimitado não a inventa.

A FLT pode usar o mesmo MLE em sigma = chi*fy, recalculando Wc,ef. O helper `strong_capacity_at_me(index, material=..., Me_Nmm=...)` não qualifica o Me recebido nem transforma um piso elástico em piso de resistência. Para um Me que seja apenas limite inferior, são necessárias correções/provas de envoltória da curva resistente. O helper declara `resistance_lower_bound_qualified=False`.

## Local fraco positivo: alma comprimida

A redução uniforme AA da alma mantém a raiz escalar com enquadramento, contração e monotonicidade do módulo de primeira plastificação. Mesas e lábios não recebem larguras reduzidas inventadas. A prova de integralidade das mesas usa uma destas condições suficientes:

1. Enrijecedor plenamente suficiente e mesa não esbelta sob a envoltória uniforme da compressão realmente alcançada no campo final.
2. Mesa relaxada para uma placa AL, retirando o apoio do lábio tracionado. A borda apoiada junto à alma está comprimida; a borda livre está tracionada. A Tabela 6(c) dá k = 1,7 − 5 psi + 17,1 psi². Quando o psi real é inferior a −1, a função linear com psi = −1 e a mesma compressão máxima domina o campo real em todo o intervalo plano [0,1]. Se lambda <= 0,673, toda a parte comprimida permanece efetiva.

A segunda prova não cria uma seção reduzida AL, não pressupõe estabilidade de junções móveis e não se estende além da parte plana. O campo em ambas as faces da mesa coincide para flexão fraca pura. A prova armazena as tensões dos extremos, a dominação afim, o sinal de todos os lábios/dobras de ligação e a posição final do CG.

Na FLT, a prova das mesas é repetida na seção efetiva correspondente. Se a compressão no início do escoamento local já for menor que chi*fy, o próprio limite local é adotado como limite combinado conservador; não se anuncia um denominador FLT isolado maior com propriedades calculadas para tensão inferior.

## Local fraco negativo: lábios comprimidos

O ramo adicional reduz somente os dois lábios sob compressão uniforme, conforme Tabela 6(a). A remoção é simétrica em torno do eixo horizontal, mantendo Ixy = 0. A, CGx e Iy são recalculados do contorno próprio. Exigem-se alma tracionada, lábios/dobras comprimidos, normalização pela fibra externa comprimida, enrijecedor plenamente suficiente sob a envoltória final da mesa e integralidade das mesas comprovada pela Tabela 5.

Se Is < Ia ou a mesa precisar de largura reduzida sob gradiente, o resultado permanece pendente. A expressão direta de 9.2.3 é para elemento uniformemente comprimido. Aplicar suas faixas reduzidas a uma mesa sob gradiente requer referência ou prova adicional da distribuição e da segurança da seção efetiva; verificar somente tensões pontuais ou obter menor área/I não resolve essa questão. Uma alternativa normativa é obter o crítico local do próprio contorno por análise elástica identificada por sinal e utilizar a rota NBR apropriada, com qualificação independente. Isso é ausência de método qualificado nesta implementação, não proibição normativa do perfil.

## Distorção fraca negativa

O novo crítico é calculado para flexão em torno do eixo paralelo à alma, com alma tracionada e lábios comprimidos. Os termos do gradiente psi_f e xi_f provêm do campo bruto próprio. As propriedades da subestrutura mesa-lábio seguem a idealização de linhas médias sem raio da Tabela 2.3.3-1; o Iy global e o CG vêm do contorno arredondado. Essa diferença de idealização é explícita. Não se declara correlação FSM do mesmo contorno nem piso garantido.

A equação 10 inclui o termo adicional q² Iyf xi_f. A profundidade efetiva é he = 3,5 sqrt(Iyf/Af + xhf²). Mdist = Sfc Fcrd usa a fibra extrema **comprimida**. A curva NBR utiliza W da primeira fibra que escoa, que não é substituído cegamente por Sfc. As estatísticas da amostra de flexão forte de Glauz não são atribuídas à flexão fraca.

Ld = Lcrd sem benefício de contenção, momento não uniforme ou telha. Para esta fórmula fraca, escrevendo K = E t³ / [6 (1 − nu²) he], a = E H + K he⁴/120, b = G Jf + K he²/6, c = K e C = base psi_f + Iyf xi_f, obtém-se F(q) = (a q² + b + c/q²)/C. Os coeficientes a, c e C são positivos no domínio verificado. A identidade C [F(q) − Fmin] = (sqrt(a) q − sqrt(c)/q)² demonstra o mínimo global Fmin = (b + 2 sqrt(a c))/C, em q⁴ = c/a. A equação 8 fornece exatamente esse Lcrd = pi/q.

Portanto o valor irrestrito também serve como referência conservadora **dentro dessa aproximação** quando L físico < Lcrd; não se anuncia um crítico exato do vão finito nem piso físico universal. A curva D NBR com rho limitado a 1 preserva a ordem desse crítico no domínio. Essa prova não foi transposta à fórmula distorcional forte, cujo denominador é diferente. Lx/Ly/Lz resistentes não substituem L físico nem Ld.

## Persistência e apresentação

- `nbr_ue_family_v1.py` preserva literalmente a aritmética do provider R10.
- `nbr_ue_family_application_v1.py` preserva o consumidor R10 e importa exclusivamente aquele provider.
- `nbr_ue_family_base.py` mantém a base atual separada do replay e limita rho a 1 também nos ramos anteriormente elegíveis, incluindo referência nominal; a aproximação decimal do limiar 0,673 não pode ampliar largura ou módulo acima do bruto.
- Novos cálculos usam schemas v2. A leitura de v1 é encaminhada ao replay congelado, sem migrar ou promover suas capacidades.
- UI, Word e JSON conservam os componentes por fonte/eixo/sinal. A condição de aproximação também é apresentada explicitamente.
- A referência nominal publicada continua independente, com Mly sem sinal não convertido em resistência fraca.

## Verificações reproduzíveis

- `qa/nbr_family_r11/run_scalar_coverage.py`: 264 linhas de material/perfil, ambos os sinais, sem solver de membro.
- `tests/test_nbr_ue_family_expansion.py`: equações distorcionais reescritas independentemente em Decimal, exemplo externo CBCA, integrais das partes removidas, provas afins, limiares, identidade de fontes e replay v1.
- Os logs no mesmo diretório QA registram apenas os testes efetivamente executados. Não constituem validação experimental nem substituem revisão de projeto.
