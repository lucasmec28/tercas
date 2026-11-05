"""Explicit isolated choice and saved-only results, separate from Vlasov ELS."""
from .application import configuration,saved_component,ERROR,SCOPE
LABEL='Alternativa de flecha uniaxial isolada com Ix efetivo'
DECLARE='Adotar três vigas isoladas para esta comparação de flecha'
LEVELS={'upper':'Superior','middle':'Central','lower':'Inferior'}
COMPARISONS={'within_isolated_uniaxial_limit':'Dentro no modelo uniaxial',
    'above_isolated_uniaxial_limit':'Acima no modelo uniaxial',
    'gross_elastic_model_exceeded':'Sem conclusão: tensão bruta excede fy',
    'numerical_result_unavailable':'Sem conclusão numérica'}


def controls(st,data,demand_fingerprint,prefix):
    if not st.checkbox(LABEL,value=False,key=prefix+'_uniaxial_enabled'):return None
    c=configuration(dict(input_fingerprint=demand_fingerprint))
    st.caption(SCOPE)
    c['independent_members_declared']=st.checkbox(DECLARE,value=False,key=prefix+'_uniaxial_declared')
    c['model_origin']=st.text_input('Origem ou hipótese da alternativa uniaxial',value='',key=prefix+'_uniaxial_origin')
    return c


def rows(c):
    return [dict(Combinação=case['combination']['id'],Travessa=LEVELS[name],
        Flecha_uniaxial_mm=None if r['deflection_mm'] is None else abs(r['deflection_mm']),
        x_mm=r['x_mm'],Ief_mínimo_sobre_Ig=r['Ief_min_over_Ig'],
        Limite_mm=c['criterion']['limit_mm'],Índice_uniaxial=r['isolated_component_index'],
        Comparação=COMPARISONS[r['comparison']])
        for case in c['cases'] for name,r in case['members'].items()]


def render_saved(st,demand):
    if demand.get(ERROR):st.warning('Alternativa uniaxial não calculada: '+demand[ERROR])
    c=saved_component(demand)
    if c is None:return
    st.subheader('Alternativa uniaxial com Ix efetivo variável')
    st.caption(SCOPE);st.dataframe(rows(c),hide_index=True)
    st.warning('Índice restrito à componente uniaxial isolada. Não substitui o resultado Vlasov nem encerra a flecha física da rede, a estabilidade ou a segurança biaxial.')
    st.caption('Cada travessa usa sua carga horizontal já distribuída, sem aplicar metade duas vezes e sem escalar flechas. Não se soma rotação torsional bruta à flecha efetiva. Critério: '+c['criterion']['origin'])
    failed=[dict(Combinação=case['combination']['id'],Travessa=LEVELS[name],qZ_N_por_mm=r['q_Z_N_mm'],Tensão_bruta_MPa=r['sigma_gross_max_MPa'],fy_MPa=c['properties']['fy_MPa']) for case in c['cases'] for name,r in case['members'].items() if not r['gross_elastic_guard']]
    if failed:st.dataframe(failed,hide_index=True)
    st.caption('Tensão bruta acima de fy retira a conclusão deste modelo elástico, mas não altera a fórmula MSE nem constitui um novo limite normativo de resistência. Tensão bruta abaixo de fy não prova a tensão da seção efetiva.')
