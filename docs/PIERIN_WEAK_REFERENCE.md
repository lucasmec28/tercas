# Pierin: referência oficial adotada para Ml,y

Lucas autorizou em 02/11/2026 usar valores tabelados em Pierin como referência oficial do app e como comparadores do núcleo. Esta adoção identifica a **fonte do valor**; não cria um sentido de compressão ausente da fonte nem valida automaticamente outras seções.

## Dados incorporados

`tercas/data/pierin_2013_weak_reference.json` contém 207 linhas: 124 U da Tabela 1 (p29–30/PDF9–10) e 83 Ue da Tabela 2 (p31–32/PDF11–12), de Pierin, Silva e La Rovere (2013), *Forças Normais e Momentos Fletores Críticos de Perfis Formados a Frio*. Todas têm geometria nominal exata no catálogo. Os 83 valores Ue coincidem com os valores anteriormente importados. Os 124 U são dados oficiais adicionais. U100×75×3,00 e U250×100×6,35 continuam sem linha exata; não há interpolação ou troca de6,35 por6,30.

Cada linha guarda dimensão, família, valor Nmm, tabela, página, trecho numérico e identidade SHA256 do PDF. O catálogo original da planilha permanece byte-idêntico: seus valores brutos não são reescritos como se a planilha contivesse os dados novos. `weak_pierin` fornece a camada complementar, exibida na UI e registrada nos resultados JSON, Word, lote e comparação de catálogo.

## Valor oficial não equivale a sentido qualificado

A tabela identifica y, mas não explicita o lado comprimido. Consequentemente:
- Ue conserva somente a hipótese de atribuição previamente autorizada ao sentido positivo/alma comprimida. **O valor é oficial; a hipótese é de sentido.**
- Os novos valores U não preenchem automaticamente nem positivo nem negativo.
- Nenhum valor é copiado bilateralmente. Mdist,y não vem de Mdist,x nem de ausência de célula.
- A frase sobre ausência de distorção em torno de y no Ue não é promovida a dispensa bilateral. A não aplicabilidade já existente para U simples permanece específica dessa família.

Essa camada ainda não fecha sozinha as resistências faltantes. Uma origem manual preenchida também não constitui validação física automática.

## Compatibilidade e guardas

Pierin declara E=200 GPa, apoio simples e cantos retos. Nu e G numéricos não foram identificados; a transformação precisa do modelo INSTAB para linha média não é demonstrada pelo artigo. `source_G_MPa` e `source_nu` permanecem null.

A hipótese fraca herdada não é usada quando E, G operacional ou dimensões nominais diferem da configuração documentada. G=77000 MPa é detector de alteração do app, não valor atribuído a Pierin. Também se rejeitam cópia da hipótese para outra família/sentido, outra linha automática e alteração numérica de Ml ainda rotulada como o valor tabulado. A recuperação manual explícita com origem própria existente permanece disponível; não certifica os críticos.

Nenhuma fórmula resistente foi alterada. As guardas fortes E/G e o núcleo normativo/FSM permaneceram sem edição. A comparação Tabela12 versus Mlx de Pierin está em avaliação separada; Nl/Mlx não foram migrados nesta cópia.

## Comparador numérico disponível, sem ajuste de parâmetros

O estudo offline `Tercas_Flexao_Fraca_Pierin_FSM_R01_20261102.zip` preserva seis geometrias, dois sentidos e três malhas; montagem conferida com a implementação pyCUFSM recuperada e eigensolver independente. Seu modelo explícito é E200000 MPa, nu0,3, G76923,0769 MPa, linha média idealizada de cantos retos e S–S. Não é idêntico às propriedades arredondadas do catálogo nem prova o modelo exato de Pierin.

| Seção | Ml,y Pierin kNm, sentido não explícito | Modelo alma kNm | Modelo bordas/lábios kNm |
|---|---:|---:|---:|
| U100×50×2 | 3,26 | 3,347203 | 1,065584 |
| U200×50×2 | 1,39 | 1,491185 | 1,119012 |
| U100×75×2,65 | 12,44 | 12,784707 | 2,388295 |
| U125×75×8 | 252,94 | 259,669174 | 66,468840 |
| Ue100×50×17×1,2 | 0,90 | 0,885955 | 2,669815 |
| Ue200×75×20×2 | 2,91 | 2,853558 | 15,778328 |

Esses números apoiam investigar a associação ao lado da alma, mas não impõem tolerância normativa nem qualificam todo catálogo. U200×50×2 diverge cerca de+7,28%; o caso U125×75×8 é somente diagnóstico de uma idealização relativamente espessa. Nos Ue/lábios, os candidatos distorcionais são1,666331 e5,430306 kNm; são experimentais e não entraram no catálogo. Ausência de vale no sentido alma não demonstra dispensa.

**Estado desta cópia:** referência incorporada e guardas testáveis, sem publicação, sem aprovação global, sem importar o novo diagnóstico FSM ou seu lookup experimental.
