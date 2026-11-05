import copy
from streamlit.testing.v1 import AppTest
from tercas.support_web import application as a,mechanics as m
from tercas.support_web.ui import LABEL,BUTTON


def widget(app,kind,label):
    return next(v for v in getattr(app,kind) if v.label==label)

def run(app):
    app.run(timeout=20)
    assert not app.exception
    return app

def fixture():
    script='''
import streamlit as st
from tercas.application import example,calculate
from tercas.support_web.ui import render
if 'source' not in st.session_state:
    d=example();d.update(P_uls=0.,q_uls=1.,left_web=False,right_web=False,support_origin='')
    st.session_state.source=calculate(d)
render(st,st.session_state.source,context='qa')
'''
    return run(AppTest.from_string(script))

def test_closed_panel_no_assessment_then_web_exception_and_invalidation(monkeypatch):
    app=fixture();src=copy.deepcopy(app.session_state.source)
    assert 'support_web_qa_saved' not in app.session_state
    widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'selectbox','Caminho da reação: left').select('web_connection')
    widget(app,'text_input','Origem do detalhe: left').set_value('Ligação da alma QA')
    widget(app,'selectbox','Caminho da reação: right').select('web_connection')
    widget(app,'text_input','Origem do detalhe: right').set_value('Ligação da alma QA')
    run(app);widget(app,'button',BUTTON).click();run(app)
    saved=copy.deepcopy(app.session_state.support_web_qa_saved)
    assert saved['summary']['exempt']==2 and saved['whole_member_approved'] is False
    assert app.session_state.source==src
    def forbidden(*args,**kwargs):raise AssertionError('No bearing calculation on rerender/export')
    monkeypatch.setattr(m,'evaluate_reaction',forbidden)
    run(app);assert app.session_state.support_web_qa_saved==saved
    widget(app,'text_input','Origem do detalhe: left').set_value('Outra origem');run(app)
    assert 'support_web_qa_saved' not in app.session_state
    assert app.session_state.source==src

def test_contact_has_no_default_dimensions_and_computes_without_P():
    app=fixture();widget(app,'checkbox',LABEL).check();run(app)
    widget(app,'selectbox','Caminho da reação: left').select('flange_contact');run(app)
    assert widget(app,'number_input','Comprimento longitudinal de contato c [mm]: left').value is None
    assert widget(app,'number_input','Distância livre ao extremo físico [mm]: left').value is None
    widget(app,'text_input','Origem do detalhe: left').set_value('Contato QA, sem projeto físico')
    widget(app,'number_input','Comprimento longitudinal de contato c [mm]: left').set_value(40.)
    widget(app,'number_input','Distância livre ao extremo físico [mm]: left').set_value(0.)
    widget(app,'selectbox','Mesa conectada na região do apoio: left').select(False)
    widget(app,'selectbox','Outra força concentrada na mesa oposta: left').select(True)
    widget(app,'selectbox','Qual sinal da força normal sobre a barra comprime a mesa deste detalhe: left').select(-1)
    run(app);widget(app,'button',BUTTON).click();run(app)
    saved=app.session_state.support_web_qa_saved
    assert saved['summary']['pending']==1 and saved['summary']['meets']+saved['summary']['fails']==1
    row=next(v for v in saved['rows'] if v['source_record']['support_id']=='left')
    assert row['local']['status']=='computed' and row['local']['force_N']==app.session_state.source['input_data']['L_mm']/2
    assert app.session_state.source['input_data']['P_uls']==0.
    widget(app,'number_input','Comprimento longitudinal de contato c [mm]: left').set_value(41.);run(app)
    assert 'support_web_qa_saved' not in app.session_state

def test_real_app_hook_preserves_original_result(monkeypatch):
    from test_ui_own_girt_application import imported,run as run_main
    from tercas.application import example
    data=example()
    data.update(P_uls=0.,q_uls=1.,left_web=False,right_web=False,support_origin='')
    app=imported(monkeypatch,data)
    widget(app,'button','Calcular verificações disponíveis').click();run_main(app)
    original=copy.deepcopy(app.session_state.result)
    widget(app,'checkbox',LABEL).check();run_main(app)
    widget(app,'button',BUTTON).click();run_main(app)
    assert app.session_state.support_web_isolated_saved['summary']['pending']==2
    assert app.session_state.result==original
