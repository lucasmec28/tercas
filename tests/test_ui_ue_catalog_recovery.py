"""Actual reconstructed opt-in UI: calculations, exports and invalidation."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas.application import defaults
from tercas import direct_self_weight as pp,roof_top_load as roof,ue_catalog_reference as own
from tercas import aisi_torsion_component as aisi,direct_torsion

APP=str(Path(__file__).resolve().parents[1]/'app.py')


def import_app(monkeypatch):
    d=pp.activate(defaults(0));d.update(q_uls=.1,q_sls=.06,roof_top_load=roof.choice())
    payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(APP).run(timeout=60)
    next(w for w in app.button if w.label=='Aplicar entradas do arquivo').click().run(timeout=60)
    assert not app.exception
    return app


def test_explicit_optin_JSON_Word_readonly_and_action_invalidation(monkeypatch):
    downloads={};original=st.download_button
    def capture(label,data,*a,**kw):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*a,**kw)
    monkeypatch.setattr(st,'download_button',capture)
    app=import_app(monkeypatch)
    assert not own.claims_reference(app.session_state.last_input)
    next(w for w in app.button if w.label=='Aplicar contorno próprio Ue').click().run(timeout=60)
    assert not app.exception and own.claims_reference(app.session_state.last_input)
    assert app.session_state.last_input['q_uls']==.1
    next(w for w in app.button if w.label=='Calcular verificações disponíveis').click().run(timeout=120)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result);e=aisi.preserved(result)
    assert e['G81_computed_cases']==1 and e['H4_computed_cases']==0
    assert own.preserved(result)
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    assert 'Contorno próprio Ue' in '\n'.join(p.text for p in doc.paragraphs)
    def fail(*a,**k):raise AssertionError('Rerender must not solve')
    monkeypatch.setattr(direct_torsion,'solve_member',fail);monkeypatch.setattr(aisi,'_aisi_demand',fail)
    app.run(timeout=60)
    assert not app.exception and app.session_state.result==result
    next(w for w in app.number_input if w.label.startswith('q ELU')).set_value(.2).run(timeout=60)
    assert not app.exception and 'result' not in app.session_state


def test_material_change_requires_reapply_and_profile_change_drops_marker(monkeypatch):
    app=import_app(monkeypatch)
    next(w for w in app.button if w.label=='Aplicar contorno próprio Ue').click().run(timeout=60)
    next(w for w in app.selectbox if w.label=='Tipo de aço').select('USI-CIVIL 300').run(timeout=60)
    assert not app.exception
    assert any('Material alterado' in w.value for w in app.warning)
    next(w for w in app.button if w.label=='Reaplicar contorno próprio Ue').click().run(timeout=60)
    assert not app.exception and own.validate(app.session_state.last_input)
    next(w for w in app.selectbox if w.label=='Perfil de catálogo').select(1).run(timeout=60)
    assert not app.exception and not own.claims_reference(app.session_state.last_input)
