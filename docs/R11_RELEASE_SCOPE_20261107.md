# R11: família Ue, resistências e serviço combinado

## Alcance

Novos estudos usam os 66 perfis Ue com inventário documental Pierin completo. Os 17 perfis restantes não são silenciosamente preenchidos: 7 não têm Ml e 10 não têm Ndist no conjunto documental. U simples e seção genérica ficam para implementação futura. A disponibilidade documental não torna todos os estados de carregamento automaticamente qualificados.

A geometria própria arredondada, os operadores e seus materiais são vinculados por identidade. Dados nominais Pierin, contornos próprios, métodos NBR, EN e AISI permanecem distintos. Não há transferência de crítico, capacidade ou índice por nome nominal de perfil.

Comprimentos efetivos são usados nas verificações resistentes dentro do domínio do método. O vão físico integral continua nas solicitações e deslocamentos; não se cria apoio intermediário, contribuição da telha ou restrição de empenamento pela simples declaração de Leff.

## Métodos integrados

- NBR: flexão local e distorcional por eixo/sinal, FLT com comprimentos resistentes e altura quando aplicável, interação biaxial concomitante e interação forte M–V com capacidade local própria. M–V e cortante da alma são componentes separados da torção, cortante fraco e forças locais.
- Referências suficientes de FLT/altura e distorção: os pisos conservadores são identificados como tal. Demanda acima de um piso não é convertida em falha; fica inconclusiva quando não existe outro resultado resistente que a resolva.
- NBR §9.4: aplicabilidade é testada nas parcelas concentradas individuais, antes de cancelamentos. Falhar a condição suficiente não significa proibição normativa nem resistência zero.
- EN: operadores normais com reduções locais/distorcionais e verificação separada de shear lag/curling. Tensões com torção/empenamento e interação seccional usam a mesma demanda, sem alterar o escopo da estabilidade NBR. Onde a aplicabilidade não é qualificada, os índices normativos são retirados e o diagnóstico é identificado.
- Serviço: campo concomitante de flexão e torção, ponto/direção e corda declarados, envelope contínuo e comparação com critério selecionado. O crivo MLE é suficiente, não uma reprovação quando inconclusivo. A sucção característica da nota f pode ser calculada como caso suplementar sem PP/CP e sem alterar a matriz fornecida.

## Evidência de integração

O corte computacional aa1eef2887b1177b270c5990e5434c5bf3162134 passou 1.702 testes backend e 3 testes reais de interface. Os recibos estão em qa/r11_integration. Contagens de baterias focadas sobrepostas não devem ser somadas.

A matriz real de aplicação executou os 66 perfis, um ELU e um ELS por perfil: fy=300 MPa, fu=450 MPa, L=4100 mm, inclinação=5,71°, Ly=Lz=2050 mm, cargas externas no topo e PP no CG, P=0. Neste cenário:

- 66/66 interações biaxiais NBR calculadas e atendidas;
- 66/66 interações fortes NBR M–V calculadas e atendidas;
- 66/66 componentes de cortante EN disponíveis;
- 36/66 componentes de tensões e M–V EN disponíveis;
- 66/66 comparações de serviço calculadas e atendidas para o limite declarado de 20 mm.

Esses resultados não são uma matriz de todas as cargas, sinais, materiais ou critérios normativos de flecha. O limite de 20 mm foi um critério sintético declarado; não prova L/180, L/120 ou sucção suplementar para toda a família. A matriz não usa dados de projeto privado.

## Pendências concretas

As 30 pendências EN desse cenário incluem shear lag de My; 24 também incluem Mx e 11 curling de My. As componentes de cortante permanecem disponíveis quando sua própria aplicabilidade é satisfeita. Não se afirma torção completa para todos os estados só porque existe G8.1 ou um campo Vlasov.

Na flexão fraca negativa NBR, o método local para mesa parcialmente enrijecida sob gradiente ainda não está qualificado para todos os perfis/materiais. Capacidades negativas completas: 55/66 em fy250, 51/66 em fy300, 45/66 em fy345 e 44/66 em fy350. A matriz de aplicação acima exercitou Mx+/My+, não resolve essa lacuna pelo sucesso dos casos positivos.

Serviço completo da cobertura pode requerer outras parcelas/etapas e avaliação de empoçamento. O cálculo do ponto não modela a superfície deformada e drenagem da cobertura. A nota g do Anexo A e a combinação frequente pertinente são registradas separadamente, sem exigir um certificado físico universal nem usar um limite angular arbitrário. Os alertas de giro linear permanecem visíveis.

A introdução de forças e as reações dependem do detalhe aplicável; o modelo de garfo não dimensiona a ligação. Ligações, ancoragens e conclusão integral do sistema não são aprovadas por estes componentes. O panorama distingue cobertura de cálculo, atendimento numérico e pendência de dados/método. A aprovação global permanece falsa.

## Preservação

Leitores de resultados históricos não recalculam nem migram silenciosamente seus números. O backend EN publicado em R10 é preservado separadamente para replay dos contratos anteriores. Registros novos conferem identidades, fontes, inventários e aritmética; hashes refeitos não substituem validação semântica.

O corte final de apresentação a5e698c passou mais 203 testes focados e 3 testes reais de interface. Houve replay autenticado dos 66 campos sintéticos preservados, com solvers de membro bloqueados e aritmética de validação permitida. Todos os pacotes calculados e todos os critérios não ELS permaneceram idênticos. Somente as novas cópias de apresentação foram reconstruídas; os arquivos originais não foram migrados. Recibo: qa/r11_integration/FINAL_RECEIPT.json.

Uma primeira execução do roteiro de replay bloqueou por engano também a função de aritmética/envelope, que não é um solver de membro. O roteiro foi corrigido, sem mudança de produção; a execução interrompida e a execução final bem-sucedida estão preservadas separadamente.
