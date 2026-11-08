"""Optional source-bound local reaction checks, separate from the member model."""
import copy,json
from . import application as a
from . import sources
from .report import display_rows,word

LABEL='Verificar alma nas reações de apoio'
BUTTON='Calcular somente a resistência local dos apoios'
CACHE_KEY='support_web_assessment'
ROUTES=(None,'web_connection','flange_contact')
ROUTE_LABELS={None:'Não informado','web_connection':'Alma ligada a outra viga ou pilar','flange_contact':'Contato por uma mesa'}


def render(st,result,context='isolated'):
    """Never modifies result. Member solver is not called by this panel."""
    base='support_web_'+context
    try:identity=a.source_fingerprint(result)
    except (ValueError,TypeError,OverflowError):
        st.session_state.pop(base+'_saved',None);st.warning('Resultado inválido para leitura dos apoios.');return
    old=st.session_state.get(base+'_saved')
    if old is not None and old.get('source_fingerprint')!=identity:
        st.session_state.pop(base+'_saved',None)
    with st.expander('Alma nas reações de apoio: NBR §9.5.1 / Anexo D',expanded=False):
        from ..three_girt_scope import central, NOTICE
        if central(result):st.caption(NOTICE)
        st.caption('As reações de apoio exigem avaliação própria mesmo quando não existe carga P externa. Este componente não dimensiona soldas nem ligações.')
        if not st.checkbox(LABEL,value=False,key=base+'_'+identity[:16]+'_enabled'):
            return
        try:
            extracted=sources.extract(result)
            cfg=a.reference_configuration(result,extracted)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            st.session_state.pop(base+'_saved',None);st.warning('Demanda de apoio indisponível: '+str(exc));return
        st.caption('Somente dados e forças já salvos. Nenhum garfo ideal é tratado automaticamente como contato de mesa ou ligação de alma. A reação externa total do nó pode incluir outras barras; usa-se a ação introduzida na própria travessa.')
        st.caption('A ligação da alma a outra viga/pilar permite registrar apenas a exceção de enrijecedor §9.5.1. Tirante ou ligação entre travessas não recebe automaticamente essa exceção.')
        records={row['support_id']:row for row in extracted['supports']}
        prefix=base+'_'+identity[:16]
        for sid,record in records.items():
            d=cfg['details'][sid];key=prefix+'_'+sid
            st.markdown('**'+str(record.get('label',sid))+'**')
            trace=record.get('trace',{})
            convention=record.get('source_axis_convention',trace.get('source_axis_convention'))
            if convention:st.caption(str(convention))
            d['route']=st.selectbox('Caminho da reação: '+sid,ROUTES,index=ROUTES.index(d['route']),format_func=lambda v:ROUTE_LABELS[v],key=key+'_route')
            d['origin']=st.text_input('Origem do detalhe: '+sid,value=d['origin'],key=key+'_origin',max_chars=2000)
            if d['route']=='flange_contact':
                st.caption('Domínio: alma a 90° da superfície de apoio/carregamento; se essa condição não corresponder ao detalhe real, não use esta rota. Nenhum enrijecedor é dimensionado aqui.')
                st.caption('Informe o contato real e as distâncias livres segundo Figura D.1. Distância ao apoio analítico não substitui distância ao extremo físico da peça. Nenhum valor é preenchido automaticamente.')
                for field,label in [('c_mm','Comprimento longitudinal de contato c [mm]'),('end_distance_mm','Distância livre ao extremo físico [mm]')]:
                    d[field]=st.number_input(label+': '+sid,value=None,key=key+'_'+field,format='%.6f')
                d['connected']=st.selectbox('Mesa conectada na região do apoio: '+sid,(None,False,True),format_func=lambda v:'Não informado' if v is None else 'Sim' if v else 'Não',key=key+'_connected')
                d['no_opposite_force']=st.selectbox('Outra força concentrada na mesa oposta: '+sid,(None,True,False),format_func=lambda v:'Não informado' if v is None else 'Não existe' if v else 'Existe, informar distância',key=key+'_opposite')
                if d['no_opposite_force'] is False:
                    d['opposite_clear_distance_mm']=st.number_input('Distância livre à força na mesa oposta [mm]: '+sid,value=None,key=key+'_opposite_distance',format='%.6f')
                else:d['opposite_clear_distance_mm']=None
                d['normal_compressive_sign']=st.selectbox('Qual sinal da força normal sobre a barra comprime a mesa deste detalhe: '+sid,(None,1,-1),format_func=lambda v:'Não informado' if v is None else 'Positivo (+)' if v==1 else 'Negativo (−)',key=key+'_sign')
                d['loaded_flange_orientation']=st.text_input('Descrição da mesa e do sentido de compressão: '+sid,value='',key=key+'_orientation',max_chars=500)
        current=st.session_state.get(base+'_saved')
        if current is not None and current.get('configuration')!=cfg:
            st.session_state.pop(base+'_saved',None)
        if st.button(BUTTON,key=prefix+'_calculate'):
            try:st.session_state[base+'_saved']=a.calculate(result,cfg)
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                st.session_state.pop(base+'_saved',None);st.warning('Verificação local não concluída: '+str(exc))
        saved=st.session_state.get(base+'_saved')
        if saved is None:return
        try:saved=a.saved_assessment(result,saved)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            st.session_state.pop(base+'_saved',None);st.warning(str(exc));return
        st.caption('Resultados salvos: '+str(saved['summary'])+'. Exceção/local atendido não aprova a ligação ou a barra.')
        st.dataframe(display_rows(saved),hide_index=True)
        st.download_button('Baixar verificação local dos apoios (JSON)',json.dumps(saved,ensure_ascii=False,indent=2),file_name='alma_apoios_resultado.json',mime='application/json',key=prefix+'_json')
        st.download_button('Baixar memória local dos apoios (Word)',word(result,saved),file_name='MC_alma_apoios.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key=prefix+'_word')
        # Explicit new sidecar only; existing v1 downloads/readers are unchanged.
        from ..completion_requirements import FIELD as COMPLETION_FIELD
        if COMPLETION_FIELD in result:
            from . import completion
            extra_key=base+'_completion_saved'
            envelope=st.session_state.get(extra_key)
            if envelope is not None and (envelope.get('source_fingerprint')!=identity or envelope.get('assessment')!=saved):
                st.session_state.pop(extra_key,None);envelope=None
            if st.button('Consolidar evidência local no fechamento',key=prefix+'_completion'):
                try:
                    envelope=completion.build(result,saved)
                    st.session_state[extra_key]=envelope
                except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                    st.session_state.pop(extra_key,None);envelope=None
                    st.warning('Fechamento complementar não consolidado: '+str(exc))
            if envelope is not None:
                try:
                    current=completion.saved(result,envelope)
                    document=completion.word(result,current)
                except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                    st.session_state.pop(extra_key,None);st.warning(str(exc));return
                st.caption(completion.SCOPE)
                st.caption(completion.PERSISTENCE)
                st.caption('Reações e resistência reconciliadas por verificação escalar. Detalhes físicos continuam hipóteses declaradas. O resultado original e as demais pendências permanecem preservados.')
                st.download_button('Baixar fechamento complementar (JSON)',json.dumps(current,ensure_ascii=False,indent=2),file_name='fechamento_complementar.json',mime='application/json',key=prefix+'_completion_json')
                st.download_button('Baixar fechamento complementar (Word)',document,file_name='fechamento_complementar.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key=prefix+'_completion_word')
