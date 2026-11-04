"""Explicit opt-in and read-only saved normal-component display."""
from .application import reference_configuration,saved_component
LABEL='Incluir componente normal N+M+B pela EN'
MODEL_LABEL='Declarar modelo de seção nominal intacta, sem furos ou recortes'
LEVELS={'upper':'Superior','middle':'Central','lower':'Inferior'}


def controls(st,data,demand_fingerprint,prefix):
    if not st.checkbox(LABEL,value=False,key=prefix+'_en_normal_enabled'):return None
    config=reference_configuration(dict(input_fingerprint=demand_fingerprint))
    st.caption('Complemento seccional EN1993-1-3:2006, separado da NBR. Soma N, duas flexões e B na mesma fibra e posição. Apenas componentes com seção integral demonstrada no ELU; trechos fora do domínio ficam pendentes. Não verifica estabilidade, cisalhamento/interação sigma–tau ou ELS.')
    with st.expander('Domínio do complemento normal EN'):
        st.caption('Seção própria Ue100×50×17, ri=t; fyb=fya=250 MPa, E de resistência=210000 MPa, nu=0,3 e gammaM0=1,00. Mantém E e combinações da demanda atual; não representa projeto integral EN. Espessura de cálculo/material reais precisam corresponder ao modelo declarado.')
        config['intact_section_model_declared']=st.checkbox(MODEL_LABEL,value=False,key=prefix+'_en_normal_intact')
        config['section_model_origin']=st.text_input('Origem ou hipótese da seção nominal EN',value='',key=prefix+'_en_normal_origin')
        st.caption('Declaração do modelo da barra, sem inventário nem dimensionamento de ligações. Não substitui ruptura líquida. Flexão fraca com lábios tracionados e mesa mista permanece fora do recorte; não vira aprovação por troca de sinal.')
    return config


def rows(component):
    records=[]
    for level,item in component['per_member'].items():
        witness=item['complete_envelope'] or item['partial_maximum']
        records.append(dict(Travessa=LEVELS[level],Cobertura=f"{item['complete_segments']}/{item['ELU_segments']} trechos ELU",
            Índice_normal=None if witness is None else witness['normal_index'],
            Envelope='Completo no recorte' if item['complete'] else 'PARCIAL, não é envelope completo',
            Combinação=None if witness is None else witness['combination_id'],
            Resultado={'within_1_in_declared_section_model':'Dentro do limite normal no modelo',
                       'above_1_in_declared_section_model':'Acima do limite normal no modelo',
                       'above_1_at_checked_state_full_envelope_incomplete':'Excesso normal em estado verificado; envelope parcial'}.get(item['normal_criterion'],'Não concluído'),
            Ramos_pendentes=', '.join(item['blocking_components']) or 'Nenhum ramo seccional faltante'))
    return records


def render_saved(st,demand):
    if demand.get('EN_normal_N_M_B_error'):st.warning('Componente normal EN não calculada: '+demand['EN_normal_N_M_B_error'])
    c=saved_component(demand)
    if c is None:return
    st.subheader('Componente normal N+M+B pelo critério EN')
    st.warning('Resultado condicionado ao modelo de seção declarado. Não encerra EN §6.1.6: cisalhamento e interação sigma–tau continuam pendentes, assim como estabilidade da barra e aplicabilidade da análise de primeira ordem.')
    st.dataframe(rows(c),hide_index=True)
    st.caption('Índice = maior |sigmaN + sigmaMx + sigmaMy + sigmaB| / 250 MPa, nas duas faces de cada segmento facetado. Campos concomitantes e extremos analíticos no vão. Empenamento constante através da espessura: não é solução de sólido curvo exato.')
    st.caption('Pendência de ramo não significa reprovação. Um máximo parcial não é envelope completo. NBR e AISI permanecem verificações separadas; seus denominadores não entram neste índice.')
    with st.expander('Prova seccional e memória normal EN'):
        st.json(dict(configuration=c['configuration'],material=c['component_sections']['material'],
            component_sections=c['component_sections']['components'],per_member=c['per_member']))
