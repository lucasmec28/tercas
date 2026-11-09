# Apresentação da demanda torsional nula no CT

Base: R22 `ffd294aafc931333344b187ef142eaff904dbff7`.

A primeira linha genérica de aplicabilidade e a célula de interpretação da demanda Vlasov passam a apresentar somente **“Torção não solicitada no modelo linear calculado.”** quando a política CT já está salva no panorama e seu registro `torsion_warping` coincide exatamente com `isolated_ct_torsion.record(result)`, que autentica todo o inventário. A conclusão é informativa, não uma aprovação da primeira ordem, da estabilidade ou do elemento.

O leitor conserva as validações anteriores de giro, identidade e snapshot AISI. A mesma conclusão validada é reutilizada na tela e no Word, sem solver, construção de panorama, novo resultado salvo ou alteração do JSON. A tabela mantém os números originais. Histórico sem a política/conclusão salva, prova inválida, demanda torsional não nula, giro elevado e inconsistências conservam o comportamento anterior.

Não se acrescenta gate de FLT, biaxial ou qualquer outro critério resistente apenas para essa frase. As pendências e falhas desses critérios continuam nos próprios registros. Torque sobre o CG pode ser não nulo: a prova diz respeito ao CT. Nenhuma fórmula, índice, carga, fingerprint, resistência ou flag de aprovação foi alterada. O aviso próprio de interpretação G8.1/H4 do complemento AISI é preservado porque sua análise é separada.

## Fundamento e limite

A revisão de escopo fornecida ao implementador conferiu NBR 14762:2010 §§8.1–8.2, 9.8.2.2 e 9.9. A alteração trata apenas de apresentação do resultado torsional já demonstrado. Não é uma nova auditoria das hipóteses físicas nem uma dispensa normativa de FLT ou de segunda ordem aplicável a qualquer modelo.

## Verificação focal

- Reprodução com o leitor original da base: os dois controles específicos do novo texto falham como esperado.
- `test_ct_torsion_notice.py`, `test_torsion_applicability.py`, `test_isolated_ct_torsion.py` e `test_rotation_geometry_diagnostic.py`: 221 testes aprovados, em 15,64 s.
- Os testes novos usam uma única criação sintética explícita. Durante a leitura, bloqueiam solver, cálculo, attach e construção do panorama; comparam integralmente o resultado antes/depois.
- Casos cobertos: CT completo; FLT/biaxial/local/distorcional/MV pendentes e falhos preservados; histórico sem política; prova ausente/alterada/duplicada; fonte divergente; B/Tsv/Tw/phi não nulos; torque CT não nulo; torque CG não nulo permitido; inventário incompleto; grandes giros; AISI inconsistente; tela e Word.
- AppTest focal das rotas atual CT e histórica: 2 testes aprovados, em 21,93 s, verificando Word, JSON e repetição da tela sem solver.

Execução serial com BLAS limitado a uma thread e dependências locais já existentes. Nenhuma instalação, suíte integral, push, deploy ou publicação.
