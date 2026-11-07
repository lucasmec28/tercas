# Recibo EN shear lag R11

Domínio: Mx puro, seção nominal simétrica integral, material nominal parametrizado; seis casos exercitados explicitamente em fy300 e L4000. O certificado não afirma tensor efetivo completo ou distribuição física exata.

- `final_tests.xml/log`: execução final combinada, 54 testes aprovados e uma expectativa numérica excessivamente restritiva em um teste escalar de vão curtíssimo. Não houve falha das equações ou testes de integração.
- `final_rechecks.xml/log`: a expectativa do teste foi corrigida sem modificar produção; 19 testes escalares e um replay adicional contra engine v2 autêntico passaram, 20/20 em 8,76 s.
- `validation_receipt.json`: último resultado de cada ID de teste, com fontes dos resultados preservadas: 56 distintos, todos aprovados. Os arquivos de produção não mudaram entre essas duas execuções finais.
- `six_scalar_proofs.json.gz`: seis provas escalares completas, pisos anteriores/após consideração explícita de shear lag, parâmetros e tempos. Não é uma execução de membro; a execução dos seis membros sintéticos é coberta pelos testes de integração.

Execução monothread com dependências exatas restauradas; sem AppTest. As leituras JSON/Word e v2/R10 são verificadas sem solver de membro. Todos os dados são sintéticos. Não houve publicação ou aprovação global.
