from ..three_girt_scope import members as verification_members, central, NOTICE
from ..direct_self_weight import active as direct_PP_active
"""Saved-result UI. Solver runs only on its explicit calculation button."""
import copy,json
from .application import calculate,current_configuration,material_point,attach_g81,fingerprint
from ..three_girt_application import defaults as legacy_defaults
from ..three_girt_frame import topology
from ..torsion_study import section_for

LABEL='Complemento de três travessas com empenamento e G8.1'
RESULT_KEY='three_girt_warping_result'
LABELS={'upper':'Superior','middle':'Central','lower':'Inferior'}


def discard_stale(state,data,config):
    old=state.get(RESULT_KEY)
    if old is not None and old.get('input_fingerprint')!=fingerprint(dict(data=data,config=config)):
        state.pop(RESULT_KEY,None);return True
    return False


def result_rows(result):
    return [dict(Combinação=row['combination']['id'],Travessa=LABELS[a['member']],
        B_Nmm2=a['B_Nmm2'],x_mm=a['x_mm'],G81=a['ratio'],
        Componente='Bsd/Ba <= 1' if a['component_condition'] else 'Bsd/Ba > 1',
        N_max_abs_N=a['max_abs_N_N'],Interação_N_M_B='Não encerrada')
        for row in result['cases'] for a in row.get('G81_component',{}).get('records',[]) if a['member'] in verification_members(result)]


def render_saved(st,result):
    if central(result):st.caption(NOTICE)
    st.subheader('Três travessas com empenamento')
    st.warning('Verificações por componente e método. G8.1 não representa aprovação global; estabilidade e ELS completo da rede não estão encerrados. Tirantes e ligações não são dimensionados.')
    if result['status']!='conditional_elastic_vlasov_demand':
        for item in result.get('missing',[]):st.warning(item)
        return
    st.caption('Ações da matriz atual preservadas, sem recombinação LRFD AISI. Comparação complementar condicionada, não aprovação normativa global.')
    st.caption('Entradas e hipóteses salvas. Exibir, mudar combinação ou exportar não recalcula o modelo.')
    st.dataframe(result_rows(result),hide_index=True)
    from ..three_girt_axial.ui import render_saved as render_nbr
    if result.get('NBR_axial_bending_error'):st.warning('Referência NBR não calculada: '+result['NBR_axial_bending_error'])
    render_nbr(st,result)
    from ..three_girt_en_normal.ui import render_saved as render_en_normal
    render_en_normal(st,result)
    from ..three_girt_service.ui import render_saved as render_service
    render_service(st,result)
    from ..three_girt_uniaxial.ui import render_saved as render_uniaxial
    render_uniaxial(st,result)
    from ..three_girt_assessment.ui import render as render_assessment
    assessment=render_assessment(st,result)
    i=st.selectbox('Combinação Vlasov 3D detalhada',range(len(result['cases'])),format_func=lambda i:result['cases'][i]['combination']['id'],key='three_warping_view_case')
    if central(result):st.caption('Contexto mecânico completo abaixo: superior/inferior não recebem conclusão resistente.')
    case=result['cases'][i];m=case['model'];rows=[]
    for name,env in m['girt_envelopes'].items():
        a=env['B_equilibrium_Nmm2']['max_abs']
        rows.append(dict(Travessa=LABELS[name],x_mm=a['x_mm'],Lado=a['side'],N_N=a['N_N'],My_Nmm=a['My_strong_Nmm'],Mz_Nmm=a['Mz_weak_Nmm'],B_Nmm2=a['B_equilibrium_Nmm2'],T_SC_Nmm=a['T_equilibrium_SC_Nmm']))
    st.caption('Esforços concomitantes na seção de maior |B|, não máximos combinados de componentes distintas.')
    st.dataframe(rows,hide_index=True)
    with st.expander('Hipóteses físicas e controle do modelo 7DOF'):
        st.json(dict(configuration=result['configuration'],stress_axis_mapping=result['stress_axis_mapping'],diagnostics=m['diagnostics']))
    from .report import word
    st.download_button('Baixar memória Vlasov 3D G8.1 e NBR (Word)',word(result,i,assessment=assessment),file_name='MC_tres_travessas_vlasov_G81_NBR.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    from ..support_web.ui import render as render_support_web
    render_support_web(st,result,context='vlasov')
    st.download_button('Baixar resultado Vlasov 3D (JSON)',json.dumps(result,ensure_ascii=False,indent=2),file_name='tres_travessas_vlasov_resultado.json',mime='application/json')


def render_panel(st,data,revision,disabled=False):
    if data.get('member_application')!='wall_girt':
        st.session_state.pop(RESULT_KEY,None);return
    if disabled:st.session_state.pop(RESULT_KEY,None)
    prefix='three_warping_'+str(revision)
    if not st.checkbox(LABEL,value=False,key=prefix+'_enabled'):
        st.session_state.pop(RESULT_KEY,None);return
    from ..current_calculation_inputs import prepare, begin_calculation
    with st.expander('Modelo das três travessas com empenamento',expanded=True):
        st.caption('Modelo adicional de primeira ordem: três travessas contínuas iguais, distância entre eixos igual à distância atual entre travessas. Barras azuis e verdes bilaterais, sem resistência; sem rigidez da telha. Não altera a verificação isolada armazenada.')
        c=copy.deepcopy(st.session_state.get(prefix+'_legacy',data.get('three_girt_model',legacy_defaults())))
        c.update(enabled=True,geometry_declared=True,axial_bars_declared=True,connections_declared=True)
        c['origin']=st.text_input('Origem ou hipótese do modelo Vlasov 3D',value=c.get('origin') or 'Hipótese explícita do complemento: três travessas iguais e barras bilaterais; não levantamento físico.',key=prefix+'_origin')
        c['tie_count']=st.number_input('Linhas interiores de tirantes Vlasov',min_value=0,max_value=20,value=c['tie_count'],step=1,key=prefix+'_count')
        positions=st.text_input('Posições X em mm separadas por vírgula (vazio = uniformes)',value='' if c['position_mode']=='uniform' else ','.join(str(v) for v in c['positions_mm']),key=prefix+'_positions')
        c['position_mode']='custom' if positions.strip() else 'uniform'
        st.caption('PP integral de cada perfil; ações externas superior/central/inferior recebem 0,5/1/0,5. PP das barras é adicional e ponderado uma vez.')
        c['brace_self_weight']=st.checkbox('Incluir peso próprio dos tirantes e cantoneiras Vlasov',value=c['brace_self_weight'],key=prefix+'_weight')
        if data.get('load_mode')=='direct':
            for state in ('uls','sls'):
                if not direct_PP_active(data):
                 c['direct_pp_'+state+'_N_mm']=st.number_input('PP da travessa já contido em q '+state.upper()+' [N/mm]',value=c['direct_pp_'+state+'_N_mm'],key=prefix+'_pp_'+state)
                if c['brace_self_weight']:c['direct_brace_factor_'+state]=st.number_input('Fator PP das barras '+state.upper(),value=c['direct_brace_factor_'+state],key=prefix+'_factor_'+state)
        mode=st.selectbox('Ligação setorial das barras Vlasov',('Braços atuais com ponto material ou resultante Qpsi zero','Ponto material comum no contorno atual'),key=prefix+'_point_mode')
        warping=st.selectbox('Empenamento nos seis extremos Vlasov',('free_assumed','restrained_assumed'),format_func=lambda v:'Livre, hipótese explícita sem restrição adicional' if v=='free_assumed' else 'Impedido, hipótese explícita adicional',key=prefix+'_warping')
        origin=st.text_input('Origem da condição de empenamento Vlasov',value='Hipótese explícita selecionada acima, sem comprovação física da ligação.',key=prefix+'_warp_origin')
        try:
            c['positions_mm']=[float(x.strip()) for x in positions.split(',')] if positions.strip() else []
            if mode.startswith('Ponto material'):
                sec=section_for(data);seg=st.number_input('Segmento do contorno atual (0 a 207)',min_value=0,max_value=207,value=0,step=1,key=prefix+'_segment')
                par=st.number_input('Parâmetro no segmento atual',min_value=0.,max_value=1.,value=0.,key=prefix+'_parameter')
                point=material_point(sec,seg,par,c['origin']);c['connection_mode']='individual';c['connection_offsets']={name:[point['arm_mm'],point['arm_mm']] for name,*_ in topology(c['tie_count'])}
            elif c['connection_mode']=='individual' and set(c['connection_offsets'])!={name for name,*_ in topology(c['tie_count'])}:
                raise ValueError('A nova quantidade requer redocumentar os braços individuais ou selecionar ponto material comum.')
            cfg=current_configuration(prepare(data),c);cfg['warping_end_condition']=warping;cfg['warping_condition_origin']=origin
            st.session_state[prefix+'_legacy']=copy.deepcopy(c)
            from ..three_girt_axial.ui import controls as nbr_controls
            nbr_config=nbr_controls(st,data,fingerprint(dict(data=data,config=cfg)),prefix)
            from ..three_girt_en_normal.ui import controls as en_normal_controls
            en_normal_config=en_normal_controls(st,data,fingerprint(dict(data=data,config=cfg)),prefix)
            from ..three_girt_service.ui import controls as service_controls
            service_config=service_controls(st,data,fingerprint(dict(data=data,config=cfg)),prefix)
            from ..three_girt_uniaxial.ui import controls as uniaxial_controls
            uniaxial_config=uniaxial_controls(st,data,fingerprint(dict(data=data,config=cfg)),prefix)
            old=st.session_state.get(RESULT_KEY)
            if old is not None and old.get('isolated_uniaxial_service_requested_configuration')!=uniaxial_config:
                st.session_state.pop(RESULT_KEY,None)
                st.info('A alternativa uniaxial mudou. Calcule novamente.')
            if old is not None and old.get('horizontal_service_requested_configuration')!=service_config:
                st.session_state.pop(RESULT_KEY,None)
                st.info('Dados da componente horizontal mudaram. Calcule novamente.')
            if old is not None and old.get('EN_normal_N_M_B_requested_configuration')!=en_normal_config:
                st.session_state.pop(RESULT_KEY,None)
                st.info('Dados da componente normal EN mudaram. Calcule novamente para atualizar a memória.')
            if old is not None and old.get('NBR_axial_bending_requested_configuration')!=nbr_config:
                st.session_state.pop(RESULT_KEY,None)
                st.info('Dados da referência NBR mudaram. Calcule novamente para atualizar a memória.')
            if discard_stale(st.session_state,data,cfg):st.info('Ações, geometria ou hipóteses mudaram. Resultado 3D anterior retirado; calcule novamente.')
            st.caption('Boca para baixo: Y=−x_R01, Z=−y_R01; omega preservado. Braços fora da parede são resultantes com transmissão Qpsi=0 declarada, não omega fictício no CG.')
            with st.expander('Configuração setorial registrada antes do cálculo'):st.json(cfg)
            st.download_button('Baixar entradas e hipóteses Vlasov 3D (JSON)',json.dumps(dict(input_data=data,configuration=cfg),ensure_ascii=False,indent=2),file_name='tres_travessas_vlasov_entradas.json',mime='application/json')
            st.caption(NOTICE+' O novo cálculo registra este escopo; resultados históricos não são convertidos.')
            if st.button('Calcular três travessas Vlasov e G8.1',disabled=disabled,key=prefix+'_calculate'):
                data=begin_calculation(st.session_state,data)
                demand_fingerprint=fingerprint(dict(data=data,config=cfg))
                for requested in (nbr_config,en_normal_config,service_config,uniaxial_config):
                    if requested is not None:requested['demand_input_fingerprint']=demand_fingerprint
                st.session_state.pop(RESULT_KEY,None)
                from ..three_girt_scope import SCHEMA as SCOPE_SCHEMA
                result=calculate(data,cfg,verification_scope=SCOPE_SCHEMA)
                if result['status']=='conditional_elastic_vlasov_demand':
                    result=attach_g81(result)
                    result['NBR_axial_bending_requested_configuration']=copy.deepcopy(nbr_config)
                    if uniaxial_config is not None:
                        result['isolated_uniaxial_service_requested_configuration']=copy.deepcopy(uniaxial_config)
                        from ..three_girt_uniaxial.application import attach as attach_uniaxial
                        try:result=attach_uniaxial(result,uniaxial_config)
                        except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
                            result['isolated_uniaxial_service_error']=str(exc)
                    if service_config is not None:
                        result['horizontal_service_requested_configuration']=copy.deepcopy(service_config)
                        from ..three_girt_service.application import attach as attach_service
                        try:result=attach_service(result,service_config)
                        except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
                            result['horizontal_service_error']=str(exc)
                    if en_normal_config is not None:
                        result['EN_normal_N_M_B_requested_configuration']=copy.deepcopy(en_normal_config)
                        from ..three_girt_en_normal.application import attach as attach_en_normal
                        try:result=attach_en_normal(result,en_normal_config)
                        except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
                            result['EN_normal_N_M_B_error']=str(exc)
                    if nbr_config is not None:
                        from ..three_girt_axial.application import attach as attach_nbr
                        try:result=attach_nbr(result,nbr_config)
                        except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
                            result['NBR_axial_bending_error']=str(exc)
                st.session_state[RESULT_KEY]=result
        except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
            st.session_state.pop(RESULT_KEY,None);st.error('Complemento 3D não calculado: '+str(exc))
        if RESULT_KEY in st.session_state:render_saved(st,st.session_state[RESULT_KEY])
