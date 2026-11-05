"""Opt-in service comparison and saved-only presentation."""
from .application import configuration,saved_component,ERROR
LABEL='Incluir deslocamento horizontal Vlasov e crivo local de serviço'
INTACT='Declarar seção nominal intacta no modelo de serviço'
LEVELS={'upper':'Superior','middle':'Central','lower':'Inferior'}


def controls(st,data,demand_fingerprint,prefix):
    if not st.checkbox(LABEL,value=False,key=prefix+'_service_enabled'):return None
    c=configuration(dict(input_fingerprint=demand_fingerprint))
    st.caption('Compara o deslocamento horizontal no centroide, incluindo a rotação torsional do modelo. A seção bruta exige crivo local normal nas três travessas simultaneamente. Não é ELS físico completo nem verificação de estabilidade.')
    c['nominal_intact_section_declared']=st.checkbox(INTACT,value=False,key=prefix+'_service_intact')
    c['model_origin']=st.text_input('Origem ou hipótese do modelo de serviço',value='',key=prefix+'_service_origin')
    return c


def rows(c):
    rows=[]
    for case in c['cases']:
        for name,member in case['members'].items():
            w=member['witness']
            rows.append(dict(Combinação=case['combination']['id'],Travessa=LEVELS[name],
                Deslocamento_horizontal_mm=abs(w['horizontal_CG_mm']),x_mm=w['x_mm'],
                Limite_mm=c['criterion']['horizontal_limit_mm'],
                Crivo_local_da_rede='Suficiente' if case['network_local_normal_gross_sufficient'] else 'Inconclusivo',
                Comparação={'within_declared_limit_in_gross_linear_model':'Dentro do limite no modelo bruto',
                    'above_declared_limit_in_gross_linear_model':'Acima do limite no modelo bruto',
                    'local_normal_gross_proof_inconclusive':'Sem conclusão: crivo local inconclusivo'}[member['comparison']]))
    return rows


def render_saved(st,demand):
    if demand.get(ERROR):st.warning('Componente horizontal não calculada: '+demand[ERROR])
    c=saved_component(demand)
    if c is None:return
    st.subheader('Deslocamento horizontal no modelo Vlasov')
    st.dataframe(rows(c),hide_index=True)
    st.caption(f"{c['sufficient_combinations']}/{c['ELS_combinations']} combinações de serviço demonstram integralidade LOCAL NORMAL nas três travessas. Ações e reações do modelo são preservadas; não se reduz I mantendo reações antigas.")
    st.warning('Comparação condicionada ao modelo linear bruto declarado. O crivo não qualifica rigidez torsional efetiva, distorção, cisalhamento ou estabilidade. ELS físico completo e aprovação global permanecem pendentes.')
    st.caption('Critério horizontal: '+c['criterion']['origin']+' Não se aplica ao deslocamento vertical nem cria apoio nos tirantes. Sem limiar normativo inventado para giro.')
