"""Controls and saved arithmetic only. No calculation during display/export."""
from ..three_girt_scope import view, central, NOTICE, axial_demand
import copy
from .application import reference_configuration, saved_component
LABEL='Incluir referência NBR de compressão e flexão'
LEVELS={'upper':'Superior','middle':'Central','lower':'Inferior'}


def controls(st,data,demand_fingerprint,prefix):
    if not st.checkbox(LABEL,value=True,key=prefix+'_nbr_enabled'):return None
    config=reference_configuration(dict(input_data=data,input_fingerprint=demand_fingerprint))
    st.caption('Referência NBR separada: comprimentos efetivos iguais ao vão físico, K=Cb=Cm=1 e sem crédito de tirantes. Calcula N/NRd + |Mforte|/MRd + |Mfraco|/MRd por seção. Não encerra N+M+B, estabilidade física ou ELS.')
    with st.expander('Dados de tração e limites da referência NBR'):
        st.caption('Fy e Fu vêm da seção atual. An0, An e Ct exigem dados explícitos da ligação; deixar pendente não impede calcular os trechos comprimidos ou N=0.')
        config['reference_origin']=st.text_input('Origem da referência de estabilidade NBR',value=config['reference_origin'],key=prefix+'_nbr_origin')
        if st.checkbox('Fornecer seções líquidas e Ct de tração',value=False,key=prefix+'_nbr_tension'):
            from .tension_detail_ui import controls as detail_controls
            if not detail_controls(st,config,prefix):
                st.caption('Informar áreas líquidas e Ct aplicável. Esta entrada não verifica a resistência de parafusos, soldas, tirantes ou ligações.')
                t=config['tension']
                t['An0_mm2']=st.number_input('An0 fora da ligação [mm²]',min_value=0.001,value=None,key=prefix+'_nbr_an0')
                t['An_mm2']=st.number_input('An na ligação [mm²]',min_value=0.001,value=None,key=prefix+'_nbr_an')
                t['Ct']=st.number_input('Ct de tração aplicável',min_value=0.001,max_value=1.0,value=None,key=prefix+'_nbr_ct')
                t['outside_area_origin']=st.text_input('Origem de An0 e caminhos fora da ligação',value='',key=prefix+'_nbr_an0_origin')
                t['connection_origin']=st.text_input('Origem de An e ramo aplicável de Ct',value='',key=prefix+'_nbr_an_origin')
                t['origin']='Dados de tração declarados separadamente nesta configuração; sem aprovação da ligação.'
    return config


def rows(component):
    out=[]
    for level,entry in component['per_member'].items():
        full=entry['complete_reference_envelope'];partial=entry['partial_reference_maximum'];w=full or partial
        out.append(dict(Travessa=LEVELS[level],Cobertura=f"{entry['arithmetic_complete_segments']}/{entry['ELU_segments']} trechos ELU",
            Índice_referência=None if w is None else w['state']['numeric_index'],
            Envelope='Completo da referência' if full else 'PARCIAL, não é envelope completo',
            Combinação=None if w is None else w['combination_id'],
            Pendências=', '.join(entry['missing_capacity_keys']) or 'Nenhum denominador faltante',
            Limites='; '.join(entry['member_issues']) or 'Sem limite axial demandado excedido',
            Aprovação_global='Não'))
    return out


def render_saved(st,demand):
    component=saved_component(demand)
    if component is None:return
    from ..three_girt_shear import render_saved as render_web_shear
    render_web_shear(st,component,demand=demand)
    from ..three_girt_local_stability import render_saved as render_local_B1
    render_local_B1(st,component,demand=demand)
    if component.get('central_local_B1_error'):
        st.info('Amplificação local B1 da central inconclusiva: '+component['central_local_B1_error'])
    component=view(component,demand)
    st.subheader('Compressão e flexão das travessas pela NBR')
    st.warning('Índices da referência de vão inteiro, não aprovação do conjunto. A central conserva N das diagonais; G8.1 e H4 não encerram N+M+B.')
    st.dataframe(rows(component),hide_index=True)
    comp=component['capacities']['compression'];slender=comp['elastic']['compression_slenderness'];t=component['capacities']['tension']
    n=comp['capacity']['Nc_Rd_N']
    st.caption('Nc,Rd de referência: '+('pendente' if n is None else f'{n/1000:.4f} kN')+f". KL/r máximo = {max(slender['symmetry_axis'],slender['orthogonal_axis']):.4f}; limite de compressão §9.7.4 = 200. A área efetiva compressiva é conferida em chi·fy.")
    if not slender['satisfied'] and (not central(demand) or axial_demand(demand,-1)):st.warning('A referência de vão inteiro excede KL/r=200 na compressão. Um nó de tirante não foi usado como apoio fictício de flambagem.')
    from .tension_detail_ui import render_saved as render_tension_detail
    render_tension_detail(st,t)
    if t['Nt_Rd_N'] is None and (not central(demand) or axial_demand(demand,1)):st.info('Tração pendente: An0 fora da ligação, An nos caminhos da ligação e Ct aplicável com origem. Fy e Fu já estão disponíveis; Ag não substituiu áreas líquidas.')
    st.caption(f"Contexto da rede completa, maior |giro| nas estações exportadas: {component['maximum_observed_abs_twist_at_exported_stations_rad']:.6f} rad. A aplicabilidade física da análise linear/pequenas rotações não está qualificada.")
    st.caption('A soma é maximizada dentro de cada trecho e combinação. O ramo fraco positivo comprime a alma; o negativo comprime os lábios. B/T/V são recuperados no mesmo ponto, sem soma de máximos distintos.')
    with st.expander('Memória numérica da referência NBR'):
        st.json(dict(configuration=component['configuration'],compression=comp,tension=t,sign_mapping=component['sign_mapping']))
