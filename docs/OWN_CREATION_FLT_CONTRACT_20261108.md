# Criação sem transplante de contrato FLT

A política de criação injetava `flt_combined_height_method` em todas as fontes.
As sete referências próprias Ue (Ue100 1,20 mm e seis outras espessuras) possuem
consumidores congelados diferentes do consumidor de contorno próprio do catálogo.
O marcador era rejeitado corretamente como campo protegido divergente, deixando
os botões de cálculo desabilitados logo depois do carregamento.

A correção limita a criação à rota existente: essas sete fontes recebem PP e
flecha local, mas nenhum marcador FLT de outro consumidor. Referências U
homogêneas conservam seu contrato escalar próprio, com PP, sem os marcadores
FLT e flecha local que seu contrato não admite. O catálogo conserva sua
ativação FLT atual e flecha local. Não se alteram EDITABLE, fontes, certificados,
solvers, propriedades, comprimentos nem consumidores resistentes.

Nenhum marcador incompatível existente é apagado ou convertido. As mesmas
validações continuam rejeitando sua presença. Importação, sessão existente e
histórico não passam pela criação e continuam inalterados. A seleção R18 da
referência fresca sem marcador, os guardas Ly/Lz, as versões explícitas e a
leitura histórica não mudaram.

QA focado: consultar recibo final na mensagem de integração. Testes novos
cobrem cálculo direto das sete próprias, três U homogêneas, criação das 66
seções elegíveis, adulteração v1/v2/desconhecida/null, preservação das entradas
e histórico, os sete botões de carregamento e cálculo Ue100 pela UI. É validação
do delta, não aprovação de projeto nem execução da suíte total.

## Recibo do delta

- Backend e política de criação: 133 passed em 14,57 s.
- UI de loaders/importação/catálogo e referência fresca R18: 107 passed em
  101,38 s. Os sete loaders e rerender permaneceram calculáveis. Semântica
  Ly/Lz, versão explícita e replay histórico v3/v4 preservados.
- Clique efetivo de cálculo após carregar Ue100, modo direto e rerender:
  1 passed em 8,83 s.
- `compileall` dos arquivos alterados/novos e `git diff --check`: passaram.

Execução com OpenBLAS Haswell e BLAS/OMP/MKL em uma thread. Sem mudança de
release/cache, publicação remota ou inclusão de dados de projeto.
