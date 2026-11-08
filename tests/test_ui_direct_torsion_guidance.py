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


def test_current_direct_panel_does_not_require_manual_line_adoption():
    app,before=app_for(True)
    assert not app.checkbox and not app.selectbox and not app.number_input
    assert not app.info and not app.warning and not app.caption
    assert app.session_state.data[FIELD]==MODE
    assert app.session_state.data==before
    app.run(timeout=30)
    assert not app.exception and app.session_state.data==before


def test_legacy_direct_PP_meaning_is_not_converted_by_rendering():
    app,before=app_for(False)
    assert FIELD not in app.session_state.data
    assert not app.checkbox and not app.selectbox and not app.number_input
    assert app.session_state.data==before
    app.run(timeout=30)
    assert not app.exception and app.session_state.data==before


def test_saved_top_and_manual_lines_are_inactive_but_preserved():
    from tercas.roof_top_load import choice
    from tercas.torsion_study import blank_choice
    app,before=app_for(True)
    before['roof_top_load']=choice('flange_midwidth')
    before[TORSION_FIELD]=blank_choice()
    before[TORSION_FIELD]['load_lines']['CP']={
        'declared':True,'xy_from_CG_mm':[12.,34.],'origin':'synthetic historical line'}
    app.session_state.data=copy.deepcopy(before)
    for _ in range(2):
        app.run(timeout=30)
        assert not app.exception and app.session_state.data==before
        assert not app.checkbox and not app.selectbox and not app.number_input
        assert not app.info and not app.warning and not app.caption
