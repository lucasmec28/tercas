"""Explicit preview/application of span and stability-length changes."""
import copy
from .homogeneous_lengths import FIELD, SPAN_ORIGIN, LIMIT, apply_lengths, configuration, global_criticals
from .presentation import fmt, display_frame


def render(st, data, revision, load):
    if FIELD not in data:
        st.caption('Modo fixo de 3 m preservado. A extensão abaixo precisa de ativação separada e mantém seção/material/críticos locais congelados.')
        if st.button('Habilitar edição de vão e comprimentos', key=f'length_enable_{revision}'):
            load(apply_lengths(data,L_mm=data['L_mm']));st.rerun()
        return False
    st.subheader('Vão inteiro e comprimentos de estabilidade')
    st.caption(LIMIT)
    st.caption('Os campos abaixo são uma proposta. Entradas atuais só mudam ao clicar em Aplicar; resultados são retirados enquanto houver proposta pendente. P direto não será reposicionado; o limite ELS escolhido para teste acompanha L.')
    current=configuration(data['L_mm'],data[FIELD])
    draft_key=f'length_draft_values_{revision}'
    if draft_key not in st.session_state:
        st.session_state[draft_key]={**current['lengths'],'origin':current['origin'] if current['mode']=='declared' else ''}
    draft=copy.deepcopy(st.session_state[draft_key])
    def proposal_number(label, initial, key):
        # value=None keeps a genuinely empty draft empty, rather than letting
        # the widget silently restore its numeric default when cleared.
        if key not in st.session_state:st.session_state[key]=initial
        return st.number_input(label,value=None,key=key,format='%.6f')
    proposed_L=proposal_number('Vão proposto L [mm]',float(data['L_mm']),f'length_span_{revision}')
    labels={'span':'Sem travamento intermediário: comprimentos iguais ao vão',
            'declared':'Distâncias efetivas declaradas (K = 1)'}
    mode=st.selectbox('Modelo dos comprimentos',list(labels),index=list(labels).index(current['mode']),format_func=labels.get,key=f'length_mode_{revision}')
    origin=current['origin'] if mode=='span' and current['mode']=='span' else SPAN_ORIGIN
    args={}
    if mode=='declared':
        for key,label in [('Lx','Lx efetivo — flexão em x [mm]'),('Ly','Ly efetivo comum — flexão em y [mm]'),('Lz','Lz efetivo — torção [mm]')]:
            draft[key]=proposal_number(label,None if draft[key] is None else float(draft[key]),f'length_{key}_{revision}')
            args[key+'_mm']=draft[key]
        draft['origin']=st.text_input('Origem e justificativa dos comprimentos',value=draft['origin'],key=f'length_origin_{revision}')
        origin=draft['origin']
        st.warning('Não se comprova um arranjo físico de contraventamentos a partir dessas distâncias. Não há rigidez de tirante, apoio intermediário ou contenção da telha gerados automaticamente.')
    else:
        st.caption('Na proposta, Lx = Ly = Lz = L, com K = 1 e empenamento livre. O vão continua biapoiado inteiro.')
    st.session_state[draft_key]=draft
    preview=None
    try:
        preview=apply_lengths(data,L_mm=proposed_L,mode=mode,origin=origin,**args)
        values=global_criticals(preview);lengths=configuration(preview['L_mm'],preview[FIELD])['lengths']
        st.markdown('**Prévia da alteração, ainda não aplicada**')
        st.caption('Trecho único proposto: [0, '+fmt(preview['L_mm'])+'] mm. '+
                   '; '.join(k+'='+fmt(v)+' mm' for k,v in lengths.items())+'. Ly é comum aos dois sentidos fortes.')
        st.dataframe(display_frame([{'Derivado':key,'Valor':value,'Unidade':'N·mm' if key.startswith('Me_') else 'N·mm²' if key.startswith('torsion_') else 'N'}
                                    for key,value in values.items()]),hide_index=True)
        st.caption('ELS direto: L/'+fmt(data['ELS_down_denominator'])+' = '+fmt(preview['ELS_limit_mm'])+' mm. '
                   'Área: limites L/'+fmt(data['ELS_down_denominator'])+' = '+fmt(preview['L_mm']/data['ELS_down_denominator'])+' mm e '
                   'L/'+fmt(data['ELS_up_denominator'])+' = '+fmt(preview['L_mm']/data['ELS_up_denominator'])+' mm. '
                   'Razões escolhidas para teste, não prescrição universal; não qualificam ELS completo ou Ief combinado.')
        st.caption('P direto conserva x ELU='+str(data['x_uls'])+' mm e x ELS='+str(data['x_sls'])+' mm. '
                   'No modo área, P continua nas posições prescritas centro L/2 e limite junto ao apoio; não há varredura intermediária.')
        outside=[key for key in ('x_uls','x_sls') if data[key] is not None and not 0<=data[key]<=preview['L_mm']]
        if outside:st.warning('Posição direta fora do novo vão: '+', '.join(outside)+'. Será preservada; corrija explicitamente antes de calcular no modo direto.')
        if mode=='declared' and any(v<preview['L_mm'] for v in lengths.values()):
            st.warning('Há comprimento de estabilidade menor que o vão. A origem declarada não comprova os vínculos nem sua rigidez/compatibilidade; esforços e flechas não recebem esses apoios.')
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        st.error('Proposta não aplicável: '+str(exc))
    pending=preview is None or preview!=data
    if pending:
        st.session_state.pop('result',None)
        st.info('Há proposta de comprimentos não aplicada. Resultados anteriores retirados; aplique a proposta ou descarte-a antes de calcular. O JSON de entradas continua sendo o conjunto já aplicado.')
        if st.button('Descartar proposta de comprimentos',key=f'length_discard_{revision}'):
            load(data);st.rerun()
    if st.button('Aplicar vão e comprimentos',key=f'length_apply_{revision}',disabled=preview is None):
        load(preview);st.rerun()
    st.caption('Para voltar à referência fixa original de 3 m, use o carregador explícito de referências; essa ação abre o caso sintético completo selecionado.')

    return pending
