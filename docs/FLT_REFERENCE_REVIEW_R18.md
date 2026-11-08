# Revisão da referência FLT e da seleção no recálculo R18

Data: 08/11/2026. Revisão estática e documental.

Base R17: `23de0dd535bf71f863c2ca9e2fba3ef8fa5032be`.
Delta examinado: `ec43e6f547a6e6c54afff1816645462d49c104f8`.

## Conclusão

Não foi identificado bloqueio na seleção dos coeficientes ENV para o domínio
implementado, entendida como referência aproximada condicionada aos fatores
resistentes declarados. O delta de seleção no recálculo preserva as guardas do
Ritz existente e separa a emissão nova do replay histórico. Esta revisão não
certifica vínculos de campo nem a resistência global da barra.

## Comprimentos declarados e realização física

A Tabela F.1.2 contém, para o mesmo diagrama forte biapoiado, coeficientes
correspondentes a k=1 e k=0,5. O fator k diz respeito à rotação lateral em
planta, não ao engastamento no plano forte. Assim, usar a linha k=0,5 não
obriga a trocar o diagrama físico por um diagrama de viga engastada. kw trata
o empenamento e aparece separadamente na expressão.

O código adota Ly/L e Lz/L como os fatores equivalentes kz/kw dessa referência.
Essa adoção é uma hipótese resistente: Ly=L/2 não demonstra, por si só,
fixidez física ou equivalência de qualquer arranjo real com a hipótese da
tabela. A origem declarada e `physical_restraints_verified=False` preservam
essa distinção. Não é necessário criar molas, novos apoios ou outro solver
para apresentar o cálculo condicional. Uma condição física explicitamente
incompatível exige revisão do caso, não uma proibição geral de Leff reduzido.

Os coeficientes implementados coincidem com as linhas documentadas de carga
uniforme e P central. A nova nota esclarece a equivalência assumida sem
alterar coeficientes, resultados ENV ou o vão físico das solicitações.

O consumidor transforma Me em resistência própria NBR e pode utilizá-la na
interação. Portanto, a hipótese acompanha uma componente resistente, não
apenas um número ilustrativo. Os indicadores de aproximação e de ausência de
aprovação global permanecem presentes no consumidor e na apresentação.

## Seleção nova e replay conferidos

- `qualify_family_fresh` seleciona o fallback Ritz v2 quando o marcador está
  ausente; uma versão v1/v2 explicitamente declarada continua sendo respeitada.
  O marcador não é inserido nas entradas.
- O ramo ENV permanece prioritário quando elegível. O fallback numérico ainda
  exige Ly=Lz=L físico, cobertura habilitada, simetria e ações admissíveis.
  Projeções paralelas passam pelas verificações de geometria e elegibilidade
  já existentes. Falta de convergência não vira referência qualificada.
- A família nova usa schema v5 e a referência fresca usa schema próprio.
  `preserved` encaminha v3/v4 à seleção histórica; v3 conserva também sua
  política antiga de piso. v1/v2 continuam nos respectivos módulos históricos.
- `validate_saved` distingue os schemas da referência antiga e nova. A nota
  de equivalência ENV entra no snapshot novo, sem reescrever o antigo.
- O panorama reconhece v5. A UI chama a emissão nova na fronteira de cálculo;
  leitura e relatório usam a validação do resultado salvo. A atualização do
  identificador de cache não altera o conteúdo de um histórico persistido.

## Alternativas e limites

Para uniforme ou P central, a própria fórmula ENV é a alternativa documental
direta sem solver novo. Uma referência adicional com kz=kw=1 pode retirar o
benefício dos fatores reduzidos, mas não deve substituir silenciosamente os
comprimentos pedidos. Não há suporte nas fontes revistas para usar os
coeficientes NCCI de k=1 com Ly reduzido, nem para estender automaticamente
estas linhas a q+P por soma harmônica. O piso energético existente tem seu
próprio contrato condicional e não certifica essa composição ENV.

## Fontes e rastreabilidade

1. Castiglioni, *Le Costruzioni di Acciaio e gli stati limite secondo le nuove
   NTC*. PDF p.47: expressão e significado de k/kw. PDF p.50: reprodução da
   Tabela F.1.2. Ambas as páginas foram conferidas visualmente.
   https://www.c430.it/pas/doc/edilizia/acciao-statilimite-ntc.pdf
   SHA256 do PDF: `0e0715f5f026468b0590db9c52cbcf60ee1374446da1e3d3d3d2ba5afceddd3b`.
2. ENV 1993-1-1:1992, Anexo F informativo, F.1.2(2)–(5), equações F.2/F.4 e
   Tabela F.1.2. O texto das cláusulas foi conferido em reprodução pública;
   o endereço original citado no código não forneceu PDF válido nesta revisão.
   Não se afirma conferência de um novo exemplar primário integral.
   https://www.scribd.com/document/622269092/Eurocode-3-Part-1-1-DDENV-1993-1-1-1992-strony-231-239-1
3. Vermeylen et al., Eurosteel 2023, PDF p.2, §2.1, Eq.1: fatores efetivos,
   condições de apoio/carga e aplicação a canais. A referência não resolve
   automaticamente torção primária ou toda excentricidade do caso real.
   https://orbi.uliege.be/bitstream/2268/306606/1/VermeylenMaxime-Eurosteel%202023.pdf
4. NCCI SN003a-EN-EU, PDF pp.3–7, §§2–3: fatores e restrições de seus
   coeficientes. Utilizado para contraste, sem substituir a tabela ENV.
   https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/SN003a-EN-EU.pdf

Código revisto: `flt_height_effective.py`, `nbr_ue_family_application.py`,
`nbr_family_member.py`, `nbr_family_panorama.py`, `nbr_ue_family_ui.py`,
`study_completion.py`, fronteira de cálculo em `app.py` e testes novos do delta.
SHA256 de `tercas/flt_height_effective.py` no delta:
`7a34910159a90e26959e9cf601f0ab7031466e7d9a7e56d1657b253257fd42fd`.

Nenhum teste, AppTest ou solver foi executado nesta revisão independente.
Os testes adicionados foram lidos; seu resultado deve ser informado no recibo
de execução correspondente. Nenhuma fórmula ou código de produção foi editado
por esta revisão. Não foram incluídos projetos privados nem normas integrais.
