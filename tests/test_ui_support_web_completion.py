import copy
from streamlit.testing.v1 import AppTest
from test_ui_support_web import widget,run
from tercas.support_web.ui import LABEL,BUTTON
from tercas.support_web import completion


def test_explicit_complement_keeps_original_and_old_exports():
    script='''
import streamlit as st
from tercas.application import example,calculate
from tercas.completion_requirements import attach
from tercas.support_web.ui import render
if 'source' not in st.session_state:
    d=example();d.update(P_uls=0.,q_uls=1.,left_web=False,right_web=False,support_origin='')
    st.session_state.source=attach(calculate(d))
render(st,st.session_state.source,context='completion_qa')
'''
    app=run(AppTest.from_string(script));before=copy.deepcopy(app.session_state.source)
    widget(app,'checkbox',LABEL).check();run(app)
    for side in ('left','right'):
        widget(app,'selectbox','Caminho da reação: '+side).select('web_connection')
        widget(app,'text_input','Origem do detalhe: '+side).set_value('Declared synthetic detail')
    run(app);widget(app,'button',BUTTON).click();run(app)
    assert 'support_web_completion_qa_completion_saved' not in app.session_state
    widget(app,'button','Consolidar evidência local no fechamento').click();run(app)
    envelope=app.session_state.support_web_completion_qa_completion_saved
    assert completion.saved(before,envelope)==envelope
    assert app.session_state.source==before and not envelope['whole_member_approved']
    assert any(completion.SCOPE==v.value for v in app.caption)
    assert any(completion.PERSISTENCE==v.value for v in app.caption)
    labels=[e.proto.label for e in app.get('download_button')]
    assert 'Baixar verificação local dos apoios (JSON)' in labels
    assert 'Baixar fechamento complementar (JSON)' in labels
    assert 'Baixar fechamento complementar (Word)' in labels
    widget(app,'text_input','Origem do detalhe: left').set_value('Changed declaration');run(app)
    assert 'support_web_completion_qa_saved' not in app.session_state
    assert not any(e.proto.label=='Baixar fechamento complementar (JSON)' for e in app.get('download_button'))
    assert app.session_state.source==before
