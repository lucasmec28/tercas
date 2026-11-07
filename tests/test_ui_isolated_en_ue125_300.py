"""Synthetic Streamlit opt-in, JSON/Word and saved no-solver rerender."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas import isolated_en_ue125_300_application as en
from tercas import isolated_en_ue125_300_ui as ui
from test_isolated_en_ue125_300_application import data


def widget(app,kind,label):return next(x for x in getattr(app,kind) if x.label==label)


def test_optin_exports_and_rerender(monkeypatch):
    d=data();d.pop(en.CHOICE);payload=json.dumps(d).encode();downloads={};original=st.download_button
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    def capture(label,data,*a,**k):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*a,**k)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    widget(app,'button','Aplicar entradas do arquivo').click().run(timeout=60)
    assert not app.exception
    assert en.CHOICE not in app.session_state.last_input
    widget(app,'checkbox',ui.LABEL).check().run(timeout=60)
    widget(app,'checkbox',ui.DECLARATION).check().run(timeout=60)
    widget(app,'text_input',ui.ORIGIN).set_value('Synthetic nominal intact QA').run(timeout=60)
    widget(app,'button','Calcular verificações disponíveis').click().run(timeout=180)
    assert not app.exception
    r=copy.deepcopy(app.session_state.result);assert en.preserved(r)['computed_cases']==1
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==r
    text='\n'.join(p.text for p in Document(io.BytesIO(downloads['Baixar memória parcial (Word)'])).paragraphs)
    assert ui.TITLE in text and 'Denominadores' in text and '300 MPa' in text
    from tercas import direct_torsion,en_ue125_300_builder
    def fail(*a,**k):raise AssertionError('Saved rerender must not solve/build')
    monkeypatch.setattr(direct_torsion,'solve_member',fail)
    # Input widgets retain their existing geometric preview; saved readers are
    # separately tested with prepare blocked. No analysis or normal builder runs.
    for name in ('build','build_qualified_component_sections'):
        if hasattr(en_ue125_300_builder,name):monkeypatch.setattr(en_ue125_300_builder,name,fail)
    app.run(timeout=180)
    assert not app.exception and app.session_state.result==r
    widget(app,'checkbox',ui.LABEL).uncheck().run(timeout=60)
    assert not app.exception and 'result' not in app.session_state
    widget(app,'selectbox','Tipo de aço').set_value('ASTM A36').run(timeout=60)
    assert not app.exception and not app.session_state.last_input[en.CHOICE]['intact_section_model_declared']
