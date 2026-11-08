import copy
from streamlit.testing.v1 import AppTest
from tercas.point_web.ui import LABEL,BUTTON
from test_ui_support_web import widget,run


def test_explicit_point_details_saved_rerender_invalidation(monkeypatch):
    script='''
import streamlit as st
from test_point_web import fixture
from tercas.point_web.ui import render
if 'source' not in st.session_state:st.session_state.source=fixture()
render(st,st.session_state.source,context='qa')
'''
    app=run(AppTest.from_string(script));old=copy.deepcopy(app.session_state.source)
    assert 'point_web_qa_saved' not in app.session_state
    widget(app,'checkbox',LABEL).check();run(app)
    assert widget(app,'number_input','Comprimento real de contato c [mm]: DIRECT_ELU').value is None
    widget(app,'text_input','Origem do detalhe físico de P: DIRECT_ELU').set_value('Synthetic centered physical detail')
    widget(app,'text_input','Descrição da mesa carregada: DIRECT_ELU').set_value('Mesa superior declarada')
    widget(app,'selectbox','Extremos físicos coincidem com 0/L e P está centrada no contato: DIRECT_ELU').select(True)
    widget(app,'number_input','Comprimento real de contato c [mm]: DIRECT_ELU').set_value(40.)
    widget(app,'selectbox','Mesa conectada na região de P: DIRECT_ELU').select(False)
    widget(app,'selectbox','Outra força concentrada na mesa oposta: DIRECT_ELU').select(True)
    widget(app,'selectbox','Sinal de P normal que comprime a mesa declarada: DIRECT_ELU').select(1)
    run(app);widget(app,'button',BUTTON).click();run(app)
    saved=copy.deepcopy(app.session_state.point_web_qa_saved)
    assert saved['rows'][0]['local']['status']=='computed' and app.session_state.source==old
    from tercas.point_web import application as a
    def no(*args,**kwargs):raise AssertionError('No recalculation on rerender')
    monkeypatch.setattr(a,'calculate',no)
    run(app);assert app.session_state.point_web_qa_saved==saved
    widget(app,'number_input','Comprimento real de contato c [mm]: DIRECT_ELU').set_value(41.);run(app)
    assert 'point_web_qa_saved' not in app.session_state and app.session_state.source==old
