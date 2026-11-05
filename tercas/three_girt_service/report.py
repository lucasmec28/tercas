"""Word consumes saved service results without any new solver or source read."""
from .application import saved_component,ERROR
from .ui import LEVELS
from ..three_girt_report import _table


def append(d,demand):
    c=saved_component(demand)
    if c is None:
        if demand.get(ERROR):d.add_paragraph('Componente horizontal não calculada: '+demand[ERROR])
        return
    d.add_page_break();d.add_heading('Componente horizontal de serviço no modelo Vlasov',1)
    d.add_paragraph('Deslocamento horizontal Z no centroide, relativo à corda dos extremos com translações e torção impedidas. Inclui a parcela de rotação da seção: uZ_CG = w_SC − sc_y·phi. Não se somam máximos de flexão e torção em posições diferentes.')
    d.add_paragraph('Modelo declarado: '+c['configuration']['model_origin']+'. Seção nominal intacta. A referência é a mesma rede bilateral de primeira ordem; reações, rigidezes, barras e continuidade foram preservadas.')
    crit=c['criterion'];d.add_paragraph(f"Limite horizontal declarado: {crit['reference_mm']:.3f}/{crit['denominator']:.3f} = {crit['horizontal_limit_mm']:.6f} mm. Origem: {crit['origin'].rstrip('. ')}. Não é critério vertical nem nova prescrição de comprimento entre tirantes.")
    values=[]
    for case in c['cases']:
        for name,m in case['members'].items():
            w=m['witness'];result=('Dentro' if m['horizontal_limit_satisfied_in_declared_model'] else 'Acima') if case['network_local_normal_gross_sufficient'] else 'Inconclusivo'
            values.append([case['combination']['id'],LEVELS[name],f"{abs(w['horizontal_CG_mm']):.5f}",f"{w['x_mm']:.3f}",result])
    _table(d,['Combinação','Travessa','|uZ| mm','x mm','Modelo bruto'],values,[1.4,1.0,1.0,1.0,1.3])
    d.add_heading('Prova suficiente de integralidade local normal',2)
    d.add_paragraph('NBR 14762:2010 §9.8.5 remete ao MLE; usa-se o ramo integral de §§9.2.2.1–9.2.2.2/Tabelas 5–6 e comparação mecânica suficiente com compressão uniforme. k=4 na alma AA; k=0,43 nas mesas e lábios, sem crédito dos enrijecedores. sigma0 = (0,673·0,95)² k E (t/b)². O campo concomitante N/Mx/My/B de serviço, e não fy ou máximos separados, fornece a compressão máxima de cada parede. E é o da demanda NBR, 200000 MPa, sem importar a prova EN.')
    d.add_paragraph('Cada trecho de todas as três travessas é verificado antes da comparação: se a integralidade de qualquer parede da rede não for demonstrada, toda a combinação fica inconclusiva. Não se altera apenas a flecha conservando reações incompatíveis. As dobras permanecem no modelo MLE e entram no guardião elástico normal max|sigma|≤fy. Exceder um comparador suficiente não prova falha resistente.')
    d.add_paragraph('Extremos contínuos de deslocamento vêm das raízes das derivadas da função quártica mais hiperbólica. Não há grade de estações substituindo a envoltória. A rotação e a translação são avaliadas na mesma posição.')
    d.add_heading('Limites que permanecem separados',2)
    d.add_paragraph('O resultado pode demonstrar atendimento do limite horizontal no modelo linear bruto declarado. Não demonstra rigidez efetiva torsional sob distorção/cisalhamento, estabilidade, interação sigma–tau, grandes rotações ou ELS físico completo. A condição local normal não é uma fórmula normativa geral para os efeitos de B; a dominância adotada é a interpretação mecânica explícita do comparador. Nenhum limite universal de giro foi imposto e nenhuma aprovação global foi liberada.')
    d.add_paragraph('SHA256 do registro de serviço: '+c['content_sha256'])
