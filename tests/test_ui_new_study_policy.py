"""Creation and imports preserve omitted or explicitly chosen scopes; no timed default."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas.support_scope import activate as exclude_supports
from tercas.direct_self_weight import activate as activate_PP
from tercas.flt_height_effective import activate_combined
from tercas.deflection_scope import FIELD,MODE,LABEL,activate
from tercas.application import example,calculate
from tercas import ue_reference as ue,ue_family_reference as family,homogeneous_reference as homogeneous
from tercas.ui_cache_epoch import KEY,EPOCH
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(a,label):return next(w for w in a.button if w.label==label)
def checkbox(a):return next(w for w in a.checkbox if w.label==LABEL)
def new_app():
    a=AppTest.from_file(APP).run(timeout=30)
    assert not a.exception
    return a

def imported(monkeypatch,data):
    payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *args,**kwargs:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    a=new_app()
    assert a.session_state.last_input[FIELD]==MODE
    button(a,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not a.exception
    return a


def test_fresh_session_and_explicit_example_default_only_new_inputs():
    a=new_app()
    assert a.session_state.base[FIELD]==MODE and checkbox(a).value
    checkbox(a).check().run(timeout=30);a.run(timeout=30)
    assert a.session_state.last_input[FIELD]==MODE
    checkbox(a).uncheck().run(timeout=30)
    assert FIELD not in a.session_state.last_input and not checkbox(a).value
    button(a,'Carregar exemplo didático').click().run(timeout=30)
    assert a.session_state.base==exclude_supports(activate(activate_combined(activate_PP(example())))) and checkbox(a).value


@pytest.mark.parametrize('kind',['generic','ue','family'])
def test_import_without_token_never_inherits_new_session_default(monkeypatch,kind):
    data=example() if kind=='generic' else ue.load_reference() if kind=='ue' else family.load_reference(1.5)
    a=imported(monkeypatch,data)
    assert a.session_state.base==data
    assert FIELD not in a.session_state.last_input and not checkbox(a).value
    a.run(timeout=30)
    assert FIELD not in a.session_state.last_input


@pytest.mark.parametrize('partial',[False,True])
def test_legacy_session_and_history_survive_without_token(partial):
    data=ue.load_reference();data.update(load_mode='direct',q_uls=.1,q_sls=.05,q_parallel_sls=.01)
    old=calculate(data);before=copy.deepcopy(old)
    a=AppTest.from_file(APP)
    if not partial:a.session_state['base']=copy.deepcopy(data)
    a.session_state['last_input']=copy.deepcopy(data)
    a.session_state['revision']=8
    a.session_state[KEY]=EPOCH
    a.session_state['result']=copy.deepcopy(old)
    a.session_state['manual_result_history']=copy.deepcopy(old)
    a.run(timeout=30)
    assert not a.exception
    assert a.session_state.base==data and a.session_state.last_input==data
    assert a.session_state.result==before and a.session_state.manual_result_history==before
    assert not checkbox(a).value and 'deflection_scope_evidence' not in a.session_state.result


def test_profile_switch_preserves_legacy_project_and_omitted_choice(monkeypatch):
    data=ue.load_reference(angle=13.);data.update(project='Preservado',q_uls=.7,x_uls=2300.)
    a=imported(monkeypatch,data)
    next(w for w in a.selectbox if w.label=='Perfil de catálogo').set_value(20).run(timeout=30)
    assert not a.exception
    for key in ('project','q_uls','x_uls','L_mm','inclination','area_inputs'):
        assert a.session_state.last_input[key]==data[key]
    assert FIELD not in a.session_state.last_input and not checkbox(a).value


def test_unknown_legacy_choice_remains_inspection_not_default(monkeypatch):
    data=ue.load_reference();data[FIELD]='future_unknown_model'
    a=imported(monkeypatch,data)
    assert a.session_state.base==data and a.session_state.last_input==data
    assert button(a,'Calcular verificações disponíveis').disabled
    assert not a.number_input


def test_own_plain_U_loader_preserves_its_frozen_scalar_scope():
    a=new_app()
    button(a,'Carregar referência de cálculo').click().run(timeout=30)
    assert not a.exception
    assert a.session_state.last_input==exclude_supports(activate_PP(homogeneous.load_reference('U100')))
    assert FIELD not in a.session_state.last_input
    assert not button(a,'Calcular verificações disponíveis').disabled
