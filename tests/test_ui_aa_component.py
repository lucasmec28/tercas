"""AA option lifecycle, switches, repeated calculations, stored results and export."""
import copy,json
from pathlib import Path
from types import SimpleNamespace
import pytest,streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import ue_family_reference as family,ue_reference as ue,deflection_scope
from tercas.aa_component import activate,MODE,LOCAL_MODE,POSITIVE_MODE,FIELD,LABEL,ROW
from tercas.biaxial_component import LABEL as GROSS_LABEL,MODE as GROSS_MODE
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(a,label):return next(w for w in a.button if w.label==label)
def checkbox(a,label):return next(w for w in a.checkbox if w.label==label)
def imported(monkeypatch,d):
    payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    a=AppTest.from_file(APP).run(timeout=40)
    button(a,'Aplicar entradas do arquivo').click().run(timeout=40)
    assert not a.exception
    return a

def seed(t=1.5):
    d=family.load_reference(t) if t!=1.2 else ue.load_reference()
    d.update(load_mode='direct',q_sls=.025,q_parallel_sls=.0075,P_sls=-75.,P_parallel_sls=-10.,x_sls=1200.)
    return d

@pytest.mark.parametrize('t',[1.2,1.5])
def test_explicit_choice_switches_invalidation_and_repeated_compute(monkeypatch,t):
    d=seed(t);a=imported(monkeypatch,d)
    assert not checkbox(a,LABEL).value
    checkbox(a,LABEL).check().run(timeout=40)
    assert a.session_state.last_input==activate(d)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception and FIELD in a.session_state.result
    first=copy.deepcopy(a.session_state.result)
    a.run(timeout=40);assert a.session_state.result==first
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert a.session_state.result==first
    next(x for x in a.selectbox if x.label=='Método para o teto AA').select(POSITIVE_MODE).run(timeout=40)
    assert 'result' not in a.session_state and a.session_state.last_input==activate(d,POSITIVE_MODE)
    checkbox(a,GROSS_LABEL).check().run(timeout=40)
    assert a.session_state.last_input['deflection_model']==GROSS_MODE and not any(w.label==LABEL for w in a.checkbox)
    checkbox(a,GROSS_LABEL).uncheck().run(timeout=40)
    assert not checkbox(a,LABEL).value and 'deflection_model' not in a.session_state.last_input
    checkbox(a,LABEL).check().run(timeout=40)
    checkbox(a,deflection_scope.LABEL).check().run(timeout=40)
    assert a.session_state.last_input==deflection_scope.activate(d)
    checkbox(a,deflection_scope.LABEL).uncheck().run(timeout=40)
    assert a.session_state.last_input==d and not checkbox(a,LABEL).value


def test_import_keeps_explicit_method_and_exports_exact_inputs(monkeypatch):
    d=activate(seed(),LOCAL_MODE);a=imported(monkeypatch,d)
    assert checkbox(a,LABEL).value and a.session_state.last_input==d
    assert next(w for w in a.selectbox if w.label=='Método para o teto AA').value==LOCAL_MODE
    saved=[];original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label=='Baixar entradas da referência (JSON)':saved.append(json.loads(data))
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    a.run(timeout=40);assert saved[-1]==d
    next(w for w in a.number_input if w.label.startswith('q paralelo ELS')).set_value(.04).run(timeout=40)
    assert 'result' not in a.session_state and a.session_state.last_input['deflection_model']==LOCAL_MODE


def test_fresh_loaders_do_not_activate_AA():
    a=AppTest.from_file(APP).run(timeout=40)
    assert not any(w.label==LABEL for w in a.checkbox)
    button(a,'Carregar família própria Ue100').click().run(timeout=40)
    assert not a.exception and not checkbox(a,LABEL).value
    assert 'deflection_model' not in a.session_state.last_input


@pytest.mark.parametrize('t',[1.2,1.5])
def test_integrity_error_is_friendly_and_removes_previous_result(monkeypatch,t):
    from tercas import aa_component as aa
    d=activate(seed(t));a=imported(monkeypatch,d)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert 'result' in a.session_state and not a.exception
    def unavailable():raise RuntimeError('Injected AA source integrity failure')
    monkeypatch.setattr(aa,'_bundle',unavailable)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception and 'result' not in a.session_state
    assert any('cálculo não emitido' in x.value for x in a.error)
    assert a.session_state.last_input==d
