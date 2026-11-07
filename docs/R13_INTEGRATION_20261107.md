# R13: integração de flexão fraca e FLT q+P

Esta emissão integra os métodos e as guardas existentes, sem homologar o aplicativo ou aprovar um projeto.

## Cobertura efetivamente verificada

- Flexão fraca: componentes de referência em ambos os sentidos nos 66 Ue com documentação completa, na matriz fy = 250/300/345/350 MPa e L = 6000 mm. O MLE existente continua preferido. O RP23-01 é usado apenas no ramo negativo admitido e nas falhas de domínio reconhecidas; 11/15/21/22 casos precisaram dele, respectivamente.
- O RP23 tem domínio explícito. É aproximação elástica publicada, não piso garantido nem resultado de FSM próprio. Os raios ri/t = 1 não herdam a precisão estatística das amostras de calibração. A curva resistente continua a NBR; a referência distorcional permanece separada.
- FLT q+P: referência Vlasov/Ritz com alturas individuais, usando o operador existente, nos 66 contornos autenticados. Os casos de matriz com projeção paralela estabilizante foram cobertos; ações desestabilizantes não foram liberadas.
- Essa rota q+P exige Ly = Lz = vão físico e os vínculos extremos do operador. Os ramos documentais puros e suas regras de comprimento permanecem. Comprimento efetivo não foi transformado em apoio físico nem fixidez ideal.
- Novos estudos recebem o marcador v2; estudos importados precisam de adoção explícita. Histórico, JSON, Word, restauração e cache foram testados. A antiga rota v1 preserva sua classificação.

## Verificação da composição

A árvore integrada passou em 754 testes de backend (270,02 s) e 26 testes de interface (184,42 s), sem falha, erro ou teste ignorado. São baterias focadas nos consumidores alterados, não a suíte inteira. O recibo JSON e os relatórios JUnit identificam a árvore de código e as evidências.

Os arquivos de QA são exemplos construídos por testes, sem dados de projeto. A distribuição pública inclui geradores executáveis, recibos resumidos e logs; os arquivos integrais de estudo e Word gerados por eles não integram a distribuição. O campo de entrada synthetic=false nesses exemplos significa perfil de catálogo, não origem em projeto real. Não foram incluídos PDFs integrais de normas ou pesquisas.

## Limites ainda presentes

- Carga mista com comprimentos efetivos diferentes do vão físico continua dependente de método aplicável; não se extrapola o operador novo.
- A envoltória EN e as propriedades efetivas têm domínios próprios. Curling combinado e representação espacial de shear lag fora das rotas qualificadas não foram encerrados. A candidata de pesquisa de curling uniaxial não integra esta emissão.
- Resistências/criticidades são verificações separadas das hipóteses da análise, ligações e introdução local de esforços. Não há aprovação global por completar somente componentes.
- Esta matriz não certifica todos os carregamentos, materiais, comprimentos ou detalhes possíveis; os limites e pendências são preservados no aplicativo.

Os métodos e referências detalhados constam em docs/FLT_COMBINED_HEIGHT_RECOVERY_20261107.txt e qa/weak_rp23/DECISAO.txt. A revisão estática independente está em qa/r13_integration/weak_static_review.json.
