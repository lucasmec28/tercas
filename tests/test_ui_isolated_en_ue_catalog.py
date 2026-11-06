"""Real Streamlit opt-in, calculation, JSON/Word and no-solver rerender."""
import copy
import io
import json
import streamlit as st
from docx import Document
from tercas import isolated_en_ue_catalog_application as en
from tercas import isolated_en_ue_catalog_ui as ui
from tercas import direct_torsion,aisi_torsion_component as aisi,en_ue_qualified_library as normal
from en_ue_test_helpers import load_app


def widget(app,kind,label):return next(x for x in getattr(app,kind) if x.label==label)


def test_explicit_en_adoption_exports_replay_and_invalidation(monkeypatch):
    downloads={};original=st.download_button
    def capture(label,data,*a,**k):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*a,**k)
    monkeypatch.setattr(st,'download_button',capture)
    app,_=load_app(monkeypatch)
    widget(app,'button','Aplicar contorno próprio Ue').click().run(timeout=30)
    assert en.CHOICE not in app.session_state.last_input
    widget(app,'checkbox',ui.LABEL).check().run(timeout=30)
    widget(app,'checkbox',ui.DECLARATION).check().run(timeout=30)
    widget(app,'text_input',ui.ORIGIN).set_value('Modelo nominal intacto para QA').run(timeout=30)
    widget(app,'button','Calcular verificações disponíveis').click().run(timeout=90)
    assert not app.exception
    r=copy.deepcopy(app.session_state.result);ev=en.preserved(r)
    assert ev['shear_computed_cases']==ev['mv_computed_cases']==1
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==r
    text='\n'.join(p.text for p in Document(io.BytesIO(downloads['Baixar memória parcial (Word)'])).paragraphs)
    assert ui.TITLE in text and 'NÃO estão resolvidos' in text and 'DIRECT_ELU' in text
    def fail(*a,**k):raise AssertionError('Reading saved results must not solve/build normal sections')
    monkeypatch.setattr(direct_torsion,'solve_member',fail);monkeypatch.setattr(aisi,'_aisi_demand',fail)
    monkeypatch.setattr(normal,'build_qualified_component_sections',fail)
    app.run(timeout=90)
    assert not app.exception and app.session_state.result==r
    widget(app,'number_input','q ELU [kN/m]').set_value(.04).run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    widget(app,'selectbox','Tipo de aço').set_value('USI-CIVIL 300').run(timeout=30)
    assert not app.exception and not app.session_state.last_input[en.CHOICE]['intact_section_model_declared']
