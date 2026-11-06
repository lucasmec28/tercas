"""The manual legacy panel must not conceal the separated direct top-load route."""
import copy
from streamlit.testing.v1 import AppTest
from tercas.ue_family_reference import load_reference
from tercas.new_study_policy import for_new_study
from tercas.direct_self_weight import FIELD, MODE
from tercas.torsion_study import FIELD as TORSION_FIELD

SCRIPT='''
import copy
import streamlit as st
from tercas.roof_top_load_ui import render_choice as roof
from tercas.torsion_study_ui import render_choice as torsion
data=copy.deepcopy(st.session_state.data)
roof(st,data,'roof')
torsion(st,data,'torsion')
st.session_state.data=data
'''


def app_for(automatic):
    data=load_reference(2.,4000.,0.)
    if automatic:data=for_new_study(data)
    data['load_mode']='direct'
    app=AppTest.from_string(SCRIPT)
    app.session_state.data=copy.deepcopy(data)
    app.run(timeout=30)
    assert not app.exception
    return app,data


def test_separated_direct_manual_panel_points_to_existing_top_route():
    app,before=app_for(True)
    next(w for w in app.checkbox if w.label=='Analisar torção Vlasov (diagnóstico elástico)').check().run(timeout=30)
    assert not app.exception
    assert any('Para calcular torção no modo direto com PP automático' in w.value for w in app.info)
    assert any('não é necessário para a rota direta automática' in w.value for w in app.caption)
    assert not any('Diagnóstico de torção pendente no modo direto' in w.value for w in app.warning)
    assert app.session_state.data[FIELD]==MODE
    assert {k:v for k,v in app.session_state.data.items() if k!=TORSION_FIELD}==before
    snapshot=copy.deepcopy(app.session_state.data)
    app.run(timeout=30)
    assert not app.exception and app.session_state.data==snapshot


def test_legacy_manual_warning_and_input_meaning_are_preserved():
    app,before=app_for(False)
    next(w for w in app.checkbox if w.label=='Analisar torção Vlasov (diagnóstico elástico)').check().run(timeout=30)
    assert not app.exception and FIELD not in app.session_state.data
    assert any('Diagnóstico de torção pendente no modo direto' in w.value for w in app.warning)
    assert not any('Para calcular torção no modo direto com PP automático' in w.value for w in app.info)
    assert {k:v for k,v in app.session_state.data.items() if k!=TORSION_FIELD}==before


def test_selecting_top_scheme_uses_existing_automatic_route_without_manual_toggle():
    app,before=app_for(True)
    next(w for w in app.selectbox if w.label=='Esquema da carga da cobertura').select('web_midplane').run(timeout=30)
    assert not app.exception
    assert not any(w.label=='Analisar torção Vlasov (diagnóstico elástico)' for w in app.checkbox)
    assert any('Modo direto separado: PP no CG' in w.value for w in app.caption)
    assert TORSION_FIELD not in app.session_state.data
    assert {k:v for k,v in app.session_state.data.items() if k!='roof_top_load'}==before
