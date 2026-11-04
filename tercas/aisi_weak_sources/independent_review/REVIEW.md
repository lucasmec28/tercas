# Revisão independente: comparador fraco restrito AISI S100-2024

Data: 2026-11-04. Escopo: revisão somente leitura das fontes e registro, sem alterar app, cálculo principal ou candidatos. Aprovação apenas da desigualdade algébrica e convenções abaixo, não liberação estrutural.

## Resultado

O piso proposto é algebricamente conservador em relação às equações F2.2/F3.2/F4, sob os mesmos dados elásticos válidos, seção sem furos, Fy uniforme e Mp >= My. A prova vale para qualquer beta_s > 0, inclusive os dois valores diferentes de 1 desta família. Não é a aplicação literal completa do DSM AISI: substitui a reserva plástica por um limite inferior demonstrável. Deve ser identificado como comparador restrito.

Lábios: os modos convencionais identificados permitem o comparador dentro das qualificações do registro. Alma: a conclusão inicial de indisponibilidade foi superada, exclusivamente para o componente puro revisado, pela revisão independente de aplicabilidade F4 (manifesto 5d48a42b3a9b9bc7717a53574b5409ab22c81902154b9075ad3f787aa08ef248). O piso da alma passa a 0.90*min(P,L), com classificação F4_NOT_APPLICABLE_PURE_WEAK_WEB, sem Mcrd identificado e sem o tratar como infinito. A ausência de D identificado não é, isoladamente, motivo suficiente para impedir uma conclusão de não aplicabilidade devidamente justificada. Ver CONSUMER_REVIEW.md para o estado atual. O piso condicional discreto permanece separado e sujeito às ressalvas abaixo.

## Equações e demonstração

Defina Y=My>0, e=Mcre>0, ell=Mcrl>0, dcr=Mcrd>0, b=beta_s>=0.4. Defina F(m,e)=m(1-m/(4e)) para e>m/2 e F(m,e)=e caso contrário. P=F(Y,e).

1. Para e fixo, F é não decrescente em m: derivada 1-m/(2e)>0 no ramo m<2e e zero no ramo restante; os ramos coincidem em m=2e. Portanto P<=F(Mp,e). Além disso P<=Y. Logo P<=B=min(F(Mp,e),Y), o Mne com barra da F3.2.
2. Faça q(x)=x/(1+a*x), a=0.55*b/ell>0. Sua derivada é 1/(1+a*x)^2>0. Logo L=q(P)<=q(B). Como ks=Mp/Y>=1 e 1+0.10*alpha_s*B/ell>=1 para alpha_s>=0, L não excede a expressão não limitada da F3.2.
3. L<=P<=Y e My3=(8Mp+Y)/9>=Y. Assim L também não excede o teto My3, preservando a comparação com a equação limitada.
4. D=Y/(1+0.60*b*Y/dcr)<=Mp*(1+0.07*alpha_s*Y/dcr)/(1+0.60*b*Y/dcr), para alpha_s>=0. Também D<=Y<=My3, preservando o teto F4.
5. O piso conjunto é 0.90*min(P,L,D). F1 exige o mínimo dos limites aplicáveis. O fator 0.90 é o fator de resistência indicado para LRFD e LSD nestas seções; não equivale a uma transferência ou conversão de capacidade NBR.

Domínio: exigir sqrt(Y/ell)<=5 é suficiente, embora mais restritivo que o limite normativo local sqrt(B/ell)<=5. Exigir sqrt(Y/dcr)<=5 corresponde ao limite F4. Não extrapolar as fórmulas além desses domínios por continuidade matemática. Valores nulos, negativos ou não finitos dos insumos devem bloquear o cálculo.

## Sinais e geometria

A renderização do PDF, p. impressa 2-8 (imagem /tmp/weak_AISI_213.png), confirma barras absolutas que o pdftotext perdeu: Mcre=Cb*Pex*(Cs*abs(j)+sqrt(j*j+r0*r0*Pt/Pex)). Não usar Cs*j sem o módulo na implementação genérica.

A definição AISI é j=integral(x^3+x*y^2)dA/(2Iy)-xo, com xo=SCx-CGx e coordenadas centroidais. O registro usa x0=CGx-SCx e j=integral/(2Iy)+x0; portanto é consistente. Não substituir o x0 positivo do registro diretamente no lugar do xo AISI com sinal negativo.

O centro de cisalhamento está do lado da alma: alma comprimida => Cs=+1; lábios comprimidos => Cs=-1. Pex usa Ix forte, pois a flexão examinada é em torno do eixo y fraco. Usar Pey aqui é erro. Para o ramo Cs=-1, a forma racionalizada Cb*r0²*Pt/(sqrt(j²+r0²*Pt/Pex)+abs(j)) evita cancelamento subtrativo.

beta_s=max(0.4,2*yc/d), com d=50 mm (profundidade perpendicular ao eixo de flexão fraco), não 100 mm. yc é a distância ao extremo COMPRIMIDO e muda com o sentido. Ver tabela numérica em CHECKS.json.

My=Fy*Wy_first_yield deve usar a fibra que primeiro escoa, seja tracionada ou comprimida. Nesta família o extremo dos lábios é o mais distante, portanto My é o mesmo nos dois sentidos; para alma comprimida não se deve usar Wy_web para My. Em contrapartida, a conversão de tensão crítica de compressão em momento usa Wc do sentido correspondente (Appendix 2.1).

alpha_s local e distortional têm critérios diferentes: F3.2 usa cantos no extremo comprimido; F4 exige que tais cantos não se desloquem no modo distortional. Não inferir alpha_s,D=1 apenas porque alpha_s,L=1. Suprimir os termos positivos no piso evita reclamar essa reserva e não exige reclassificar os modos nem afirmar que o alpha físico é zero.

## Limite inferior da alma

Se B0>0 é certificado como limite inferior de TODOS os autovalores convencionais admissíveis do MESMO modelo discreto e mesmo domínio, então todo autovalor distortional desse conjunto, caso exista, também é >=B0. A função D(z)=Y*z/(z+0.60*b*Y) é crescente em z, derivada 0.60*b*Y²/(z+0.60*b*Y)²>0. Logo D(B0)<=D(dcr_discreto). Se sqrt(Y/B0)<=5, o domínio F4 de qualquer dcr_discreto>=B0 também está coberto.

Isso não identifica Mcrd, não demonstra ausência de D, não prova o contínuo físico e não autoriza tratar B0 como o vale distortional convencional contínuo usado nos lábios. Manter o certificado, hashes, perfil/material/malha e domínio de vãos 3000–6000 mm; cobertura de todos os harmônicos e cauda infinita precisa ser a do certificado, não de mera amostragem. O registro afirma essas propriedades mas esta revisão não refez o certificado.

Na revisão inicial, antes de qualificar a aplicabilidade F4, o campo principal da alma permanecia indisponível. Essa conclusão de bloqueio está superada para o componente puro revisado, conforme o Resultado atualizado acima. O campo separado continua claramente denominado piso condicional do modelo discreto. Não permitir que esse segundo campo libere aprovação normativa, seleção automática ou extensão a outros vãos/perfis/modelos. Não atribuir erro de discretização igual a zero.

## Limitações globais importantes

Appendix 2.3 permite as soluções analíticas nas condições de contorno/geometria dadas. A nota de p. 2-3 pressupõe cargas transversais aplicadas no centro de cisalhamento; outras posições podem aumentar OU reduzir Mcre. Cobertura/carga excêntrica não é automaticamente conservadora por ignorar a excentricidade. Cb=1 é permitido conservadoramente para gradiente de momentos nas hipóteses da fórmula, mas não conserta carga fora do centro de cisalhamento, empenamento/torsão com vínculos incompatíveis ou interação biaxial. Não tratar esta revisão uniaxial como qualificação da interação biaxial, torção ou esforço normal.

O registro usa E=200000 MPa, nu=0.3 e G=76923.08 MPa. A seção 2.3.1 enumera E=203000 MPa e G=78000 MPa. Preservar o material próprio declarado pode produzir comparador coerente, mas não rotular silenciosamente esses valores como os constantes literais AISI. Não misturar material do registro com novo Mcre sem registrar a decisão e consistência dos três momentos críticos.

## Fontes e verificação

Fonte primária: ANSI/SDI AISI S100-2024, F1, F2.1–F2.2, F3.2, F4; Appendix 2.1, 2.3, 2.3.1 e 2.3.1.2.2. PDF oficial: https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf. Cópia local /tmp/torsion_sources/aisi_s100_2024.pdf e texto correspondente; sinais na Eq. 2.3.1.2.2-1 conferidos visualmente.

Fonte dos perfis: outputs/tercas_ue100_family_critical_20261103/FAMILY_ELASTIC_REGISTRY.json. Não houve reintegração da seção, identificação modal nova, recálculo dos certificados ou transferência de resistência NBR.
