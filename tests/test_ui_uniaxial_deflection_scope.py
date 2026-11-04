"""Mode persistence, scope display, stale removal and invalid import isolation."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import deflection_scope as scope, ue_reference as ue, ue_family_reference as family
from tercas.application import rows

APP=str(Path(__file__).resolve().parents[1]/'app.py')


def button(app,label):return next(x for x in app.button if x.label==label)
def checkbox(app,label):return next(x for x in app.checkbox if x.label==label)


def imported(monkeypatch,data):
    payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(APP).run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    return app


@pytest.mark.parametrize('t',[1.2,1.5])
def test_toggle_preserves_physics_and_forces_recalculation(monkeypatch,t):
    data=ue.load_reference(angle=5.) if t==1.2 else family.load_reference(t,4000.,5.)
    data.update(load_mode='direct',q_sls=.1,q_uls=.2,q_parallel_sls=.05,q_parallel_uls=.025)
    app=imported(monkeypatch,data)
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert app.session_state.result['ELS'].get('index') is None
    checkbox(app,scope.LABEL).check().run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    assert app.session_state.last_input==scope.activate(data)
    assert not button(app,'Calcular verificações disponíveis').disabled
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert app.session_state.result['ELS'].get('index') is not None
    assert next(r for r in rows(app.session_state.result) if r['Verificação']==scope.PURLIN_ROW)
    assert any('O índice confronta somente' in x.value for x in app.caption)
    checkbox(app,scope.LABEL).uncheck().run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    assert app.session_state.last_input==data
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert app.session_state.result['ELS'].get('index') is None


@pytest.mark.parametrize('t',[1.2,1.5])
def test_imported_explicit_choice_and_export_are_exact(monkeypatch,t):
    data=ue.load_reference(angle=5.) if t==1.2 else family.load_reference(t,4000.,5.)
    data=scope.activate(data)
    app=imported(monkeypatch,data)
    assert checkbox(app,scope.LABEL).value
    assert app.session_state.last_input==data
    records=[];old=st.download_button
    def record(label,data,*args,**kwargs):
        if label=='Baixar entradas da referência (JSON)':records.append(json.loads(data))
        return old(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',record)
    app.run(timeout=30)
    assert records and records[-1]==data


@pytest.mark.parametrize('t',[1.2,1.5])
@pytest.mark.parametrize('bad',[True,None,'invented'])
def test_bad_import_not_silently_fixed_or_executed(monkeypatch,t,bad):
    data=ue.load_reference() if t==1.2 else family.load_reference(t)
    data[scope.FIELD]=bad
    app=imported(monkeypatch,data)
    assert app.session_state.last_input==data
    assert button(app,'Calcular verificações disponíveis').disabled
    assert not app.number_input
