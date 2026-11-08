"""Explicit point-contact sidecar UI; original downloads stay immutable."""
import json
from . import application as a,sources

LABEL='Verificar parcela normal da introdução de P (Ue)'
BUTTON='Calcular somente a parcela normal local de P'


def render(st,result,context='isolated'):
    base='point_web_'+context
    identity=a.fingerprint(result)
    old=st.session_state.get(base+'_saved')
    if old is not None and old.get('source_fingerprint')!=identity:st.session_state.pop(base+'_saved',None)
    with st.expander('Introdução de P: parcela normal local NBR Anexo D',expanded=False):
        st.caption(a.SCOPE)
        st.caption('O JSON complementar deve acompanhar o resultado original. Esta verificação não é incorporada automaticamente à memória Word ou ao JSON principal.')
        if not st.checkbox(LABEL,value=False,key=base+'_'+identity[:16]+'_enabled'):return
        try:
            src=sources.extract(result);cfg=a.reference_configuration(result,src)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            st.session_state.pop(base+'_saved',None);st.warning(str(exc));return
        st.caption('Ue, contato por mesa explicitamente declarado. Extremos físicos em 0/L e carga centrada no contato são limites deste adaptador, não exigências normativas universais. Não presume contato com telha nem contenção global.')
        prefix=base+'_'+identity[:16]
        for p in src['points']:
            sid=p['point_id'];d=cfg['details'][sid];key=prefix+'_'+sid
            st.markdown('**'+sid+'**')
            st.caption('x='+str(p['x_mm'])+' mm; P normal='+str(p['normal_N'])+' N; P paralela='+str(p['parallel_N'])+' N; M forte concomitante='+str(p['moment_strong_Nmm'])+' Nmm.')
            if p['normal_N']==0:
                st.caption('Sem P normal: outras parcelas e reações não são dispensadas.');continue
            if p['mathematical_point_limit']:
                st.warning('Limite matemático junto ao apoio: nenhum contato finito inferido. Reações de apoio permanecem independentes.');continue
            st.caption('Escolher e preencher este detalhe declara contato por mesa com compressão da alma a 90°. Modelo sem crédito a enrijecedor transversal. Mesa conectada significa restrição local da rotação, não travamento global.')
            d['origin']=st.text_input('Origem do detalhe físico de P: '+sid,key=key+'_origin',max_chars=2000)
            d['physical_ends_match_span']=st.selectbox('Extremos físicos coincidem com 0/L e P está centrada no contato: '+sid,(None,True,False),format_func=lambda v:'Não informado' if v is None else 'Sim' if v else 'Não',key=key+'_ends')
            d['c_mm']=st.number_input('Comprimento real de contato c [mm]: '+sid,value=None,key=key+'_c',format='%.6f')
            d['connected']=st.selectbox('Mesa conectada na região de P: '+sid,(None,False,True),format_func=lambda v:'Não informado' if v is None else 'Sim' if v else 'Não',key=key+'_connected')
            d['no_opposite_force']=st.selectbox('Outra força concentrada na mesa oposta: '+sid,(None,True,False),format_func=lambda v:'Não informado' if v is None else 'Não existe' if v else 'Existe',key=key+'_opposite')
            if d['no_opposite_force'] is False:
                st.caption('A força oposta declarada serve somente à classificação local da Figura D.1; não cria nem altera cargas na análise.')
                d['opposite_clear_distance_mm']=st.number_input('Distância livre à força oposta, Figura D.1 [mm]: '+sid,value=None,key=key+'_distance',format='%.6f')
            d['normal_compressive_sign']=st.selectbox('Sinal de P normal que comprime a mesa declarada: '+sid,(None,1,-1),format_func=lambda v:'Não informado' if v is None else 'Positivo (+)' if v==1 else 'Negativo (−)',key=key+'_sign')
            d['loaded_flange_orientation']=st.text_input('Descrição da mesa carregada: '+sid,key=key+'_orientation',max_chars=2000)
        saved=st.session_state.get(base+'_saved')
        if saved is not None and saved.get('configuration')!=cfg:st.session_state.pop(base+'_saved',None)
        if st.button(BUTTON,key=prefix+'_calculate'):
            try:st.session_state[base+'_saved']=a.calculate(result,cfg)
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                st.session_state.pop(base+'_saved',None);st.warning(str(exc))
        saved=st.session_state.get(base+'_saved')
        if saved is None:return
        try:saved=a.saved_assessment(result,saved)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            st.session_state.pop(base+'_saved',None);st.warning(str(exc));return
        st.caption('Somente F normal/FRd. P paralela não é verificada; pendências globais e guardas antigas permanecem. '+str(saved['summary']))
        st.dataframe([dict(Combinação=r['source_record']['combination_id'],Estado=r['local']['status'],
            Critério=r['local'].get('criterion_status'),FRd_N=r['local'].get('FRd_N'),
            Índice=r['local'].get('index'),Observação=r['local']['reason']) for r in saved['rows']],hide_index=True)
        st.download_button('Baixar parcela local de P (JSON)',json.dumps(saved,ensure_ascii=False,indent=2),
            file_name='introducao_P_parcela_normal.json',mime='application/json',key=prefix+'_json')
