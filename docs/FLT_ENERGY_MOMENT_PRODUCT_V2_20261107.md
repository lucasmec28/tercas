# FLT q+P com comprimentos resistentes: piso condicional v2

## Parecer técnico

Não foi qualificada uma fórmula documental combinada genérica que transforme
Ly/Lz em vínculos físicos. O novo ramo melhora a condição suficiente já
existente, sem ampliar suas hipóteses de energia e sem executar solver.
Não é crítico exato, coeficiente normativo novo ou aprovação global. Falhar
esta condição continua inconclusivo, nunca prova reprovação.

A energia de partida é Sahraei, Pezeshky e Mohareb (2017), Eq.2:
https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf
As parcelas de altura de q e P permanecem separadas. A desigualdade abaixo é
uma derivação desta implementação, não uma fórmula atribuída aos autores.

A documentação SCIA consultada distingue fator de comprimento LTB de fatores
de fixidez e empenamento. A rota Lopez zera C2/C3; não foi adotada para ignorar
as alturas reais. Os outros coeficientes exigem domínio carga/vínculo próprio:
https://help.scia.net/19.1/en/pvt/steelcodechecktb/en/lateral_torsional_buckling.htm
Isso não prova inexistência de outro método publicado, apenas não autoriza
uma composição genérica no domínio pedido.

## Mesmas hipóteses, majorante mais forte

Preservam-se integralmente as hipóteses do piso v1 documentadas em
FLT_HEIGHT_ENERGY_FLOOR_R11.md: phi nula nos extremos físicos, energia lateral
>= Ny ||u'||² e energia de empenamento >= ECw(pi/Lz)² ||phi'||².
Ny=pi²EIy/Ly². Comprimentos menores são hipóteses resistentes declaradas,
não uma reconstrução de fixidez ou apoios. A realização física não é verificada.

Se M é o momento contínuo das cargas uniformes e pontuais no vão físico L,
V=M' e M''=-q-soma(Pa delta_a), a integração por partes dá:

|| (M phi)' ||² = integral(M² phi'²) + integral(q M phi²)
                 + soma(Pa M(a) phi(a)²).

A identidade vale por trechos, incluindo os saltos de V=-Pa. Os termos de
extremidade se anulam porque phi=0. Os termos V² cancelam exatamente.
Com Cauchy, Poincaré e o mesmo limite de avaliação H1_0 usado no piso v1:

|integral(M u'' phi)| <= ||u'|| ||(M phi)'|| <= B2 ||u'|| ||phi'||,

B2² = Mmax² + max(0,max_x(q M(x))) (L/pi)²
      + soma(max(Pa M(a),0) a(L-a)/L).

O código usa B=min(B1,B2), onde B1 é o majorante anterior. Forças coincidentes
são agregadas antes de tomar partes positivas. Sinais mistos são permitidos;
parcelas negativas são descartadas somente para majorar o operador. Pontos
nos apoios não contribuem. q constante permite obter max(qM) nos mesmos
cortes e raízes de cortante, inclusive q negativo ou nulo.

D, as alturas individuais, Ny e T permanecem exatamente os anteriores.
A raiz suficiente é a mesma: Ny(T-lambda D)-lambda² B²=0. Todas as grandezas
do diagrama e as posições continuam no vão físico, sem deslocar PP ao topo.
Nenhum autovalor é reescalado e nenhum vínculo é inferido.

## Aritmética e preservação

Forças, produtos e extremos são frações exatas dos inputs numéricos. Pi é
limitado inferiormente; B2 usa raiz quadrada superior por aritmética inteira;
a conversão de B é dirigida para cima. Ny/T, lambda e Me são dirigidos para
baixo, como no piso v1. O determinante é rechecado por frações exatas.
O certificado registra todos os termos de B2, permitindo replay integral.

Nova seleção interna: method=moment_product_energy_bound_v2.
Novo schema elástico: flt_height_declared_energy_floor_v2.
Novo schema da ponte NBR: flt_height_declared_energy_nbr_floor_v2.
Consumidor novo: nbr_ue_family_application_v4_energy_product.
Toda avaliação fresca chama o piso v2, inclusive recálculo de entrada importada
sem marcador. O replay do consumidor v3 chama explicitamente o piso v1 e
mantém o schema original. Os consumidores históricos v1/v2 não são alterados.
Não há novo token de entrada, checkbox, adesão, migração ou publicação remota.
As APIs isoladas conservam default v1 para compatibilidade; o consumidor
fresco solicita v2 explicitamente. Leitores isolados escolhem pelo schema salvo.
A ponte resistente NBR e suas provas não mudam: recebem o novo piso qualificado,
com schema próprio. Ramos puros ENV e o Ritz de vão integral não mudam.

## Exemplo sintético independente

L=3600, Ly=1800, Lz=2400 mm; E=205000, G=79000 MPa;
Iy=190000 mm4, J=720 mm4, Cw=6,2e8 mm6. qPP=0,38 N/mm no CG,
qexterno=0,57 N/mm a h=55 mm; P=320 N no centro, h=42 mm.
São números de teste, não dados de projeto nem seleção de perfil.

A demanda permanece 1,827 kNm. B cai de 3.969.862,15 para 2.478.553,23 Nmm;
o piso Me sobe de 2,2863145 para 3,3718928 kNm (+47,48%).
Isso não é MRd, nem prova que todos os casos pendentes passam.

## Verificação

A suíte nova testa integração independente da identidade para sinais mistos,
energia original em campos admissíveis para quatro pares de comprimentos,
q=0/P=0, cancelamentos de forças com altura remanescente, pontos nos extremos
e seus limites unilaterais, escalonamento, família66, replay v1/v2 e adulteração
com hash recalculado. Essa suíte unitária não executa autovalores de membro ou AppTest.

O AppTest adicional importa entrada sintética sem marcador, calcula com
Ly=1800 e Lz=2400 diferentes de L=3600 mm, verifica o novo schema, exporta
JSON/Word e rerenderiza sem alterar o snapshot. Nenhum solver novo foi acrescentado.

## Recibo compacto

Base congelada: 2c5aa12253f08caa50fe0c1c0de67098d169b622.
Revisão matemática independente: identidade, sinal dos saltos, dimensões,
extremos qM e min de majorantes confirmados; quatro identidades polinomiais
foram verificadas por integração simbólica exata, sem solver.

Focal consumidor/panorama/M–V/Word/AppTest: 141 testes passaram em 65,35 s.
Comando: python -m pytest -q tests/test_flt_energy_moment_product.py
 tests/test_nbr_family_height_integration.py tests/test_nbr_family_floor_consumer.py
 tests/test_nbr_family_mv_consumer.py tests/test_nbr_family_panorama.py
 tests/test_nbr_family_word_dispatch.py tests/test_ui_flt_energy_product.py
BLAS/OMP/MKL com uma thread. Dois controles extras posteriores são cobertos
pela focal final elástico/ponte descrita abaixo; contagens não são somadas
como se fossem testes distintos.

Replay independente: quatro snapshots q+P v3 foram realmente produzidos na
base congelada, índices sintéticos 0,19,53,79, e então lidos pelo código novo.
4/4 foram aceitos numericamente idênticos, com chamada de solver proibida.
SHA256 do oráculo sintético JSON mantido fora do pacote: 868603688255979ce8f67a8e5b118e16946499207179a5509e921b3ebbccc45b.
O inventário extenso fica fora do delta. Outra comparação independente de
piso v1, ponte v1 e consumidor v3 em quatro índices foi byte a byte idêntica
entre a base e a revisão: SHA256 6d85123a8896e2ef69cacaea79d6f65ef29e8523fa898c310fda9a2448ef7565.
Nenhum dado de projeto real ou identidade empresarial consta no delta.

Focal final após os guardas adicionais: 296 testes passaram em 111,36 s.
Comando: python -m pytest -q tests/test_flt_energy_moment_product.py
 tests/test_flt_height_energy_floor.py tests/test_flt_height_nbr_floor.py
Inclui 66/66 contornos, comparação dos pisos resistentes, energia original,
identidades, replay, seleção explícita e rejeição de evidência v1 quando v2
foi expressamente solicitado. Compileall e git diff --check passaram.
A contagem não certifica condições físicas não modeladas, críticas exatas,
qualquer combinação arbitrária ou a resolução de todos os casos inconclusivos.
