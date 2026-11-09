# R22: controle integrado de 8 de novembro de 2026

A candidata combina a largura forte NBR `bf0 = bf - t + lip` e a prova de leitura dos resultados EN dos sete perfis próprios. Não ativa a candidata de rede EN dos 66 perfis e não implementa a redução da Tabela 7. Vão físico, solicitações, fatores de peso próprio, política vigente de forças no CT e escopo de apoios permanecem preservados.

## Resultado final local

No código executável `b6ac803af1e9c3181cf9223f484c3839eecc0b4d`:

- 590 testes de backend passaram em 105,27 s.
- 10 testes de interface passaram em 97,21 s, incluindo central 1,20 mm com ELS, cobertura inclinada CT, históricos e apoios somente leitura.
- `compileall` e `git diff --check` passaram. As alterações seguintes são documentos e uma docstring explicativa.
- Quatro avisos de overflow são esperados no teste que exige recusa de aritmética não finita e ausência de inserção no cache. Não são falhas de um caso ordinário.

As versões exatas do ambiente, fontes alteradas e hashes dos recibos estão em `qa/r22_integrated_release/receipt.json`. A suíte completa do repositório e o site hospedado não foram testados nesta rodada. O ambiente de teste não é idêntico a todas as versões fixadas para hospedagem.

## Histórico e limites de desempenho

Uma rodada anterior teve duas falhas distintas: expectativa de interface ainda ligada ao modelo antigo de altura de carga, e timeout real da central 1,20 mm com ELS. A primeira foi reproduzida na R21 e reparada separando a leitura histórica do cálculo atual CT. A segunda exigiu otimização do cálculo e da leitura, mantendo 60 s por execução individual da interface. O resultado final passou; as execuções anteriores não são contadas como aprovadas.

O ensaio controlado de memória mediu 535.340 KiB de pico na candidata contra 329.340 KiB na base. Os caches têm limites globais explícitos e retêm cerca de 24,4 MiB no caso medido, sem payloads completos de usuário. O aumento residual é real; não se afirma equivalência de memória ou adequação comprovada a qualquer limite de hospedagem.

A aritmética intervalar em lote preservou os resultados bit a bit nos controles escalares, no certificado completo e no resultado EN comparado. O método do certificado e a geometria NBR tiveram revisão independente anterior. Não se reivindica uma nova revisão independente completa do último delta de desempenho.

## Interpretação

Este recibo demonstra apenas os controles de software listados, com dados sintéticos. Não aprova um projeto, não homologa a estrutura e não amplia silenciosamente o domínio normativo. A preservação de históricos não transforma números antigos em uma nova conclusão autenticada; cálculo explícito emite a versão corrente.

Na emissão deste recibo a publicação R22 ainda não foi iniciada. A validação hospedada será registrada separadamente, após a versão correspondente estar disponível.
