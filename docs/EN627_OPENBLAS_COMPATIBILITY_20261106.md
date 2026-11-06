# EN6.27: compatibilidade auditada de certificados OpenBLAS

## Diagnóstico reproduzido

Base examinada: `2be5620c6ecb2afa28f0c1806018950156a8463a` (mesma árvore funcional de `f0eff704`). O arquivo de construção `tercas/three_girt_en_normal/en1993_normal_components.py` permaneceu inalterado; SHA-256 de seus bytes: `2f407a8d96ff24ed5541efe7a1507cacde9a21d3729db83a8f627e54b6efc745`.

No mesmo computador, interpretador Python 3.12.14, NumPy 2.3.5, biblioteca OpenBLAS 0.3.30 e arquivos de entrada, trocar somente `OPENBLAS_CORETYPE` de SkylakeX (seleção nativa) para Haswell reproduziu exatamente o hash observado no Streamlit para t1,20. `OPENBLAS_NUM_THREADS=1` e `OMP_NUM_THREADS=1` em ambos os processos. Isso comprova que a seleção do kernel BLAS é suficiente para explicar esta divergência. Não foi necessário alterar versão Python, serializador, tipos, material, perfil ou geometria. A identificação do processador efetivo do serviço hospedado não foi obtida; a correspondência exata do certificado foi reproduzida localmente.

Das sete espessuras, cinco geraram certificados completos byte-idênticos. Somente estas duas diferiram:

- t1,20: SkylakeX `160fc2f2d8cb3d490ddccb996d023ba04459d25f54d287eb0a1bb495f539638b`; Haswell `5b6bfa95bc26d22b35ebec2e96fd9cb26aaf2a46672bffa3df5fe0ba22029ea8`.
- t3,00: SkylakeX `06ab706c093469f2b915532c91f3101f6d0a4a83134a2fcb1888682c295e1e9c`; Haswell `5d6993c2c82dd7cb5b03e18cb90cc87e5c4f22acdb1fed27f8eef03df555d06a`.

Os certificados completos adicionais estão em `tests/data/en_normal_haswell_t1.20.json` e `tests/data/en_normal_haswell_t3.00.json`. São saídas capturadas do construtor original, não certificados editados ou fabricados a partir do hash observado.

## Diferenças e conferência dos pisos

Nenhum campo textual, booleano, conjunto de chaves, comprimento de lista, elegibilidade ou escopo mudou. Houve 67 folhas numéricas diferentes em t1,20 e 100 em t3,00. Os índices de intervalos retidos e as decisões normativas permaneceram iguais; algumas ordenadas e auditorias numéricas variaram.

- t1,20: diferença absoluta máxima entre todas as folhas numéricas `1.3969838619232178e-9`, no resultante Mx da auditoria do ramo positivo: `2151532.071541066` contra `2151532.0715410644` Nmm. Diferença relativa nesse campo: `6.492972521309468e-16`.
- t3,00: diferença absoluta máxima `1.1641532182693481e-10`, em Is do enrijecedor: `2066.595136585762` contra `2066.5951365856454` mm⁴. Diferença relativa nesse campo: `5.6331944155866686e-14`.
- Coeficientes resistentes de t1,20: três folhas mudaram, diferença absoluta máxima `1.3552527156068805e-20`, relativa máxima `1.515749546012475e-14`.
- Coeficientes resistentes de t3,00: duas folhas mudaram, diferença absoluta máxima `8.470329472543003e-22`, relativa `1.835395948404502e-16`.

Esses números descrevem a comparação e NÃO são tolerâncias de admissão. Resíduos próximos de zero podem ter grande diferença relativa; por exemplo, a maior relativa de todas as folhas t1,20 é aproximadamente 0,545 em uma auditoria de inversão da ordem de 1e-21. A decisão de compatibilidade não foi baseada em um percentual global.

Os seis pisos foram rederivados com o procedimento intervalar já existente, sobre todas as linhas físicas e ambas as faces afastadas, e também conferidos independentemente por avaliação direta dos operadores nos mesmos vértices físicos. Valores inteiros idênticos:

- t1,20: N+ 67831 N, N− 51458 N, Mx± 2151532 Nmm, My+ 787876 Nmm, My− 748463 Nmm.
- t3,00: N± 160697 N, Mx± 4957708 Nmm, My± 1680316 Nmm.

As capacidades de cortante, material, geometria, bases e todos os denominadores permanecem exatamente os anteriores. A menor parte fracionária dos denominadores diretos destes dois perfis é aproximadamente 0,071541 Nmm; nenhuma variante fica junto da mudança de piso inteiro. O cálculo intervalar continua exigindo igualdade exata dos seis pisos durante cada cálculo novo.

## Reparo mínimo e limites de segurança

`REFERENCES` não foi modificado. Um seletor retorna uma cópia da referência original com o hash completo REAL do certificado, apenas se esse hash for o original ou uma das duas saídas exatas auditadas acima. Os hashes adicionais são ligados à respectiva espessura.

O cálculo continua verificando integridade do certificado, vínculo de geometria, elegibilidade e os seis pisos rederivados. A leitura salva continua comparando a referência inteira, a origem exata do certificado, os hashes de solicitações, as ações concomitantes e os indicadores de escopo. Ela apenas seleciona uma referência já qualificada; não reconstrói certificados, seções, capacidades ou o modelo estrutural.

Isso é compatibilidade auditada de duas saídas do despacho Haswell, NÃO portabilidade universal de hashes numéricos. Qualquer outro hash, biblioteca, kernel ou futura mudança que produza nova saída permanece pendente até auditoria própria. Não há arredondamento de certificados, tolerância para hashes, cadastro automático, aceitação só porque os pisos coincidem, nem substituição do hash real pelo hash antigo.

Um certificado adulterado e recalculado pode manter todos os pisos inteiros, por exemplo após uma mudança de 1 ULP em um coeficiente axial. Por isso somente verificar o auto-hash e os pisos seria insuficiente. O teste dessa adulteração comprova a rejeição pelo pin completo exato. Trocar entre dois hashes conhecidos sem trocar a fonte correspondente também é rejeitado.

Forçar globalmente um kernel, mudar a aritmética do construtor, apagar o pin ou arredondar o certificado inteiro seriam mudanças mais amplas. Nenhuma delas foi aplicada. As hipóteses físicas, métodos normativos, flags de não aprovação global, legados e escopo central permanecem inalterados.

## Reproduzir e testar

A montagem dos certificados é leve e não executa solver de barra/rede. Em uma máquina que suporte as instruções Haswell, execute o mesmo programa em dois processos, um nativo e outro com `OPENBLAS_CORETYPE=Haswell`, usando os pins de `requirements.txt`:

```python
import json
from pathlib import Path
import numpy as np
from tercas.three_girt_en_normal.en1993_normal_components import build_component_sections
from tercas.en_simplified_interaction import capacities
np.show_runtime()
for path in sorted(Path('tercas/data/torsion_profiles').glob('ue*.json')):
    profile = json.loads(path.read_text())
    certificate = build_component_sections(profile)
    print(profile['thickness_mm'], certificate['content_sha256'],
          capacities(profile, certificate)['signed_capacity_floor'])
```

Não force SkylakeX em hardware que não suporte esse kernel. Na máquina auditada, a seleção nativa já era SkylakeX.

Testes focados, ambos os processos com BLAS/OMP em uma thread:

```sh
python -m pytest -q tests/test_en_capacity_runtime_variants.py tests/test_en_simplified_interaction.py tests/test_three_girt_en_normal_sections.py tests/test_three_girt_en_remaining120_certificate.py
```

Os testes novos incluem as duas fixtures completas, os seis pisos independentes, adulteração com auto-hash refeito, um coeficiente 1 ULP diferente que preserva o piso, material, elegibilidade, auditoria, geometria, hash desconhecido, troca de espessura, cópias que não modificam REFERENCES, leitura isolada e de três travessas sem builders, e substituição indevida entre dois hashes conhecidos.

Resultados focados: 69 testes passaram com SkylakeX e 69 com Haswell. Outros 6 testes unitários existentes de três travessas passaram sob Haswell. Os 7 casos isolados existentes de cálculo EN6.27, um por espessura, passaram sob Haswell; em todos os casos a solicitação original ficou inalterada e não houve aprovação global.

O teste histórico dos 39 ramos não introduzidos em v5 precisou reconhecer também seu agregado exato Haswell (`9e797d62b37d09aaf7572a828f83a5447d12b7a534ba3d98ab707aff9ba108d1`), selecionado pelo hash completo t3,00. O agregado original (`32f6a817f880e882cbb0f1956f198a1be938b438adc656ba495ec2355729a3e1`) foi preservado. Não se substituiu a asserção por comparação aproximada.

Também foram lidos o controle local original e os dois JSON hospedados após reboot, com construtor de certificado, capacidades, cálculo EN6.27 e solver isolado substituídos por funções que lançam erro se chamados. Os três foram aceitos sem alteração do conteúdo. Os dois snapshots históricos que contêm a pendência continuam pendentes: este reparo não os recalcula nem preenche retroativamente.

Não foi executada a suíte completa, solver integrado de rede ou smoke online desta alteração isolada. Publicação e validação da candidata integrada pertencem à etapa de integração.
