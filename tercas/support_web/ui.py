"""Read-only display/export of historical support-web sidecars.

Local support checks are outside the app's scope. This panel cannot create or
edit an assessment, including when its source is an unmarked historical result.
"""
import json
from . import application as a
from .report import display_rows,word

# Historical labels retained only for compatibility and regression assertions.
LABEL='Verificar alma nas reações de apoio'
BUTTON='Calcular somente a resistência local dos apoios'
CACHE_KEY='support_web_assessment'


def render(st,result,context='isolated'):
    """Read saved evidence only. Never calculate, consolidate or modify result."""
    from ..support_scope import saved as saved_scope, TITLE
    try:scope=saved_scope(result)
    except (ValueError,TypeError,KeyError) as exc:
        st.warning(str(exc));return
    if scope is not None:
        with st.expander(TITLE,expanded=False):st.caption(scope['reason'])
        return
    base='support_web_'+context
    try:identity=a.source_fingerprint(result)
    except (ValueError,TypeError,OverflowError):
        st.warning('Resultado inválido para leitura dos apoios.');return
    saved=st.session_state.get(base+'_saved')
    envelope=st.session_state.get(base+'_completion_saved')
    # A previous source remains stored, but is never displayed for this source.
    if saved is not None and saved.get('source_fingerprint')!=identity:saved=None
    if envelope is not None and envelope.get('source_fingerprint')!=identity:envelope=None
    if saved is None and envelope is None:return
    prefix=base+'_'+identity[:16]
    from . import completion
    try:
        if envelope is not None:
            envelope=completion.read_saved(result,envelope)
            if saved is None:saved=envelope['assessment']
            elif envelope['assessment']!=saved:
                raise ValueError('Fechamento complementar desvinculado da avaliação salva.')
        saved=a.saved_assessment(result,saved)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        st.warning(str(exc));return
    with st.expander('Histórico: alma nas reações de apoio',expanded=False):
        from ..three_girt_scope import central, NOTICE
        if central(result):st.caption(NOTICE)
        st.caption('Avaliação histórica salva, somente leitura. Nenhuma resistência local é calculada ou requalificada nesta consulta.')
        st.caption('Resultados salvos: '+str(saved['summary'])+'. Exceção/local atendido não aprova a ligação ou a barra.')
        st.dataframe(display_rows(saved),hide_index=True)
        st.download_button('Baixar verificação local dos apoios (JSON)',json.dumps(saved,ensure_ascii=False,indent=2),file_name='alma_apoios_resultado.json',mime='application/json',key=prefix+'_json')
        st.download_button('Baixar memória local dos apoios (Word)',word(result,saved),file_name='MC_alma_apoios.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key=prefix+'_word')
        if envelope is not None:
            st.caption(completion.SCOPE)
            st.caption(completion.PERSISTENCE)
            st.caption(completion.HISTORICAL_READ)
            st.download_button('Baixar fechamento complementar (JSON)',json.dumps(envelope,ensure_ascii=False,indent=2),file_name='fechamento_complementar.json',mime='application/json',key=prefix+'_completion_json')
            st.download_button('Baixar fechamento complementar (Word)',completion.word_saved(result,envelope),file_name='fechamento_complementar.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',key=prefix+'_completion_word')
