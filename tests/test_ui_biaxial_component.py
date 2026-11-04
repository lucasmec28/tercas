"""Explicit model choice and saved-only presentation; no timed default."""
import copy,json
from pathlib import Path
from types import SimpleNamespace
import pytest,streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import ue_family_reference as family,ue_reference as ue,deflection_scope
from tercas.biaxial_component import activate,MODE,FIELD,LABEL,ROW
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(a,label):return next(w for w in a.button if w.label==label)
def checkbox(a,label):return next(w for w in a.checkbox if w.label==label)
def imported(monkeypatch,d):
    p=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(p),getvalue=lambda:p))
    a=AppTest.from_file(APP).run(timeout=30)
    button(a,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not a.exception
    return a

def seed(t=1.5):
    d=family.load_reference(t) if t!=1.2 else ue.load_reference()
    d.update(load_mode='direct',q_sls=.025,q_parallel_sls=.0075,P_sls=-75.,P_parallel_sls=-10.,x_sls=1200.)
    return d

@pytest.mark.parametrize('t',[1.2,1.5])
def test_choice_explicit_invalidates_and_modes_are_exclusive(monkeypatch,t):
    d=seed(t);a=imported(monkeypatch,d)
    assert not checkbox(a,LABEL).value and not checkbox(a,deflection_scope.LABEL).value
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert FIELD not in a.session_state.result
    checkbox(a,LABEL).check().run(timeout=30)
    assert 'result' not in a.session_state and a.session_state.last_input==activate(d)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    r=copy.deepcopy(a.session_state.result);assert r[FIELD]['qualified_cases']==1
    assert any('seção integral demonstrada em 1 de 1' in x.value for x in a.info)
    assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'
    a.run(timeout=30);assert a.session_state.result==r
    checkbox(a,deflection_scope.LABEL).check().run(timeout=30)
    assert 'result' not in a.session_state
    assert a.session_state.last_input==deflection_scope.activate(d)
    assert not any(w.label==LABEL for w in a.checkbox)
    checkbox(a,deflection_scope.LABEL).uncheck().run(timeout=30)
    assert a.session_state.last_input==d and not checkbox(a,LABEL).value

@pytest.mark.parametrize('t',[1.2,1.5])
def test_import_roundtrip_and_repeated_choice_preserves_exact_data(monkeypatch,t):
    d=activate(seed(t));a=imported(monkeypatch,d)
    assert checkbox(a,LABEL).value and a.session_state.last_input==d
    records=[];old=st.download_button
    def capture(label,data,*args,**kwargs):
        if label=='Baixar entradas da referência (JSON)':records.append(json.loads(data))
        return old(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    a.run(timeout=30);assert records and records[-1]==d
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    before=copy.deepcopy(a.session_state.result)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert a.session_state.result==before
    next(n for n in a.number_input if n.label.startswith('q paralelo ELS')).set_value(.04).run(timeout=30)
    assert 'result' not in a.session_state and a.session_state.last_input['deflection_model']==MODE


def test_new_loaders_do_not_choose_a_model():
    a=AppTest.from_file(APP).run(timeout=30)
    assert 'deflection_model' not in a.session_state.last_input
    assert not any(w.label==LABEL for w in a.checkbox)
    button(a,'Carregar referência própria Ue100').click().run(timeout=30)
    assert not a.exception and 'deflection_model' not in a.session_state.last_input
    assert not checkbox(a,LABEL).value and not checkbox(a,deflection_scope.LABEL).value
    a=AppTest.from_file(APP).run(timeout=30)
    button(a,'Carregar família própria Ue100').click().run(timeout=30)
    assert not a.exception and 'deflection_model' not in a.session_state.last_input
    assert not checkbox(a,LABEL).value and not checkbox(a,deflection_scope.LABEL).value


def test_inconclusive_ui_does_not_recover_scalar(monkeypatch):
    d=seed(1.2);d.update(q_sls=.1,q_parallel_sls=.03,P_sls=-300.,P_parallel_sls=-40.)
    a=imported(monkeypatch,activate(d))
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception
    r=a.session_state.result
    assert r[FIELD]['qualified_cases']==0 and 'index' not in r['ELS']
    assert any('Não é reprovação' in w.value for w in a.warning)
    assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'
