"""All support panels are read-only; historical records remain immutable."""
from streamlit.testing.v1 import AppTest
from tercas import support_scope as scope
from tercas.support_web.ui import LABEL,BUTTON


def test_current_panel_has_no_checkbox_calculate_or_local_index(monkeypatch):
    from test_ui_support_web import forbid_new_support
    forbid_new_support(monkeypatch)
    app=AppTest.from_string('''
import streamlit as st
from tercas.application import example,calculate
from tercas.support_scope import activate
from tercas.support_web.ui import render
if 'result' not in st.session_state:st.session_state.result=calculate(activate(example()))
render(st,st.session_state.result)
''').run(timeout=30)
    assert not app.exception
    before=app.session_state.result
    assert not any(x.label==LABEL for x in app.checkbox)
    assert not any(x.label==BUTTON for x in app.button)
    assert any(scope.TEXT==x.value for x in app.caption)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==before



def test_legacy_inputs_adopt_current_calculation_payload_without_mutating_history():
    from tercas.application import example
    import copy
    old=example();history={'input_data':copy.deepcopy(old),'result':'unchanged'}
    before=copy.deepcopy(history)
    current=scope.adopt_for_calculation(old)
    assert scope.enabled(current) and scope.FIELD not in old
    assert history==before


import pytest

@pytest.mark.parametrize('reference',['homogeneous','ue','family'])
def test_frozen_editor_keeps_history_until_recalculate_and_retains_fresh(reference):
    """Exercise the real combined CT/support calculation boundary and history."""
    import copy
    from pathlib import Path
    from tercas import homogeneous_reference as h,ue_reference as u,ue_family_reference as f
    from tercas.pierin_ue_registry_ui import HISTORY
    from tercas.ui_cache_epoch import KEY,EPOCH
    module={'homogeneous':h,'ue':u,'family':f}[reference]
    data=(h.load_reference('U100') if reference=='homogeneous' else u.load_reference() if reference=='ue' else f.load_reference(1.5))
    data.update(load_mode='direct',q_uls=.1,q_sls=.05)
    old=module.calculate_reference(data);before=copy.deepcopy(old)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'))
    app.session_state.base=copy.deepcopy(data)
    app.session_state.last_input=copy.deepcopy(data)
    app.session_state.result=copy.deepcopy(old)
    app.session_state.revision=41
    app.session_state[KEY]=EPOCH
    app.run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input==data and app.session_state.result==before
    next(w for w in app.button if w.label=='Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    fresh=copy.deepcopy(app.session_state.result)
    assert scope.saved(fresh) is not None
    assert app.session_state.base==app.session_state.last_input==fresh['input_data']
    assert app.session_state[HISTORY][-1]['result']==before
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==fresh
    assert app.session_state[HISTORY][-1]['result']==before
    assert not any(w.label==LABEL for w in app.checkbox)
