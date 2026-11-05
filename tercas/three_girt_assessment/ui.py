"""Explicit read-only inventory; kept outside the mechanical hash chain."""
import json
from .presentation import label,STATES
from .application import assess,saved_assessment
from ..three_girt_warping.application import fingerprint

KEY='three_girt_saved_global_inventory'
LABEL='Montar panorama global do resultado salvo'
STATUS={'aprovado':'Critérios deste grupo atendidos no escopo declarado',
    'reprovado':'Há critério não atendido neste grupo',
    'inconclusivo':'Grupo com verificação pendente'}


def render(st,result):
    try:digest=fingerprint(result)
    except (ValueError,TypeError) as exc:
        st.session_state.pop(KEY,None);st.warning('Panorama indisponível: resultado salvo não é JSON finito. '+str(exc));return None
    old=st.session_state.get(KEY)
    if old is not None and old.get('source_result_sha256')!=digest:
        st.session_state.pop(KEY,None);old=None
    st.caption('O panorama reúne somente resultados salvos. Não resolve o modelo e não altera a cadeia de hashes.')
    if st.button(LABEL,key=KEY+'_build'):
        old=assess(result);st.session_state[KEY]=old
    if old is None:return None
    try:old=saved_assessment(result,old)
    except (ValueError,TypeError,KeyError) as exc:
        st.session_state.pop(KEY,None);st.warning('Panorama retirado: '+str(exc));return None
    st.subheader('Panorama do modelo e critérios')
    if old['status']=='reprovado':st.error(old['display_summary'])
    else:st.warning(old['display_summary'])
    st.caption(old.get('interpretation','Integridade do resultado requer revisão.'))
    st.dataframe([dict(Grupo=g['title'],Situação=STATUS[g['status']],Escopo=g['scope'],
        Atendidos=g['counts']['meets'],Não_atendidos=g['counts']['fails'],Pendentes=g['counts']['pending'])
        for g in old['groups']],hide_index=True)
    with st.expander('Critérios não atendidos e pendências da rede',expanded=True):
        for r in old['checks']:
            if r['status'] not in ('fails','pending'):continue
            index='' if r['index'] is None else ' | índice '+format(r['index'],'.6g')
            st.write(label(r)+' | '+STATES[r['status']]+index+' | '+r['reason'])
    with st.expander('Dispensas fundamentadas e escopo excluído'):
        for r in old['checks']:
            if r['status']=='not_applicable':st.write(label(r)+': '+r['reason'])
        for text in old['excluded_scope']:st.write(text)
    st.download_button('Baixar panorama separado (JSON)',json.dumps(old,ensure_ascii=False,indent=2),
        file_name='tres_travessas_panorama_global.json',mime='application/json')
    return old
