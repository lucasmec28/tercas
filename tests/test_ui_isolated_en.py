import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas import isolated_en_application as en, isolated_en_ui as ui
from test_direct_torsion import inputs

APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(app,label):return next(w for w in app.button if w.label==label)


def prepared(monkeypatch):
    d=inputs(P=20.);payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(APP).run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    return app,d


def test_explicit_en_flow_exports_and_read_only_rerender(monkeypatch):
    downloads={};orig=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return orig(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app,d=prepared(monkeypatch)
    assert en.CHOICE not in app.session_state.last_input
    next(w for w in app.checkbox if w.label==ui.LABEL).check().run(timeout=30)
    assert not app.session_state.last_input[en.CHOICE]['intact_section_model_declared']
    next(w for w in app.checkbox if w.label==ui.DECLARATION).check().run(timeout=30)
    next(w for w in app.text_input if w.label==ui.ORIGIN).set_value('Hipótese sintética declarada').run(timeout=30)
    button(app,'Calcular verificações disponíveis').click().run(timeout=90)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result);ev=en.preserved(result)
    assert ev['computed_cases']==1
    assert any(ui.TITLE in w.value for w in app.subheader)
    table=next(w.value for w in app.dataframe if 'Teto interação σ–τ EN' in w.value.columns)
    assert len(table)==1
    assert table['Teto M–V adicional EN6.27'].notna().all()
    assert table['Teto dos dois cortantes EN'].notna().all()
    assert ev['records'][0]['web_shear_component']['bending_shear_component']['component_qualified']
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    report_text='\n'.join(p.text for p in doc.paragraphs)
    assert ui.TITLE in report_text and 'Mf=0' in report_text and 'primeiro escoamento' in report_text
    def fail(*a,**kw):raise AssertionError('No EN recalculation on saved rendering')
    monkeypatch.setattr(en,'check_member',fail)
    from tercas import isolated_en_mv, en_simplified_interaction
    monkeypatch.setattr(isolated_en_mv,'calculate',fail)
    monkeypatch.setattr(en_simplified_interaction,'capacities',fail)
    app.run(timeout=30)
    next(w for w in app.checkbox if w.label=='Exibir memória numérica salva do caso direto').check().run(timeout=30)
    assert not app.exception and app.session_state.result==result
    next(w for w in app.text_input if w.label==ui.ORIGIN).set_value('Outra hipótese').run(timeout=30)
    assert 'result' not in app.session_state


def test_geometry_change_retains_opt_in_but_clears_declaration(monkeypatch):
    app,_=prepared(monkeypatch)
    next(w for w in app.checkbox if w.label==ui.LABEL).check().run(timeout=30)
    next(w for w in app.checkbox if w.label==ui.DECLARATION).check().run(timeout=30)
    next(w for w in app.text_input if w.label==ui.ORIGIN).set_value('Hipótese inicial').run(timeout=30)
    next(w for w in app.selectbox if w.label=='Espessura proposta da família Ue100 [mm]').select(2.25).run(timeout=30)
    button(app,'Aplicar seção e vão da família Ue100').click().run(timeout=30)
    assert not app.exception
    c=app.session_state.last_input[en.CHOICE]
    assert c['enabled'] and not c['intact_section_model_declared'] and c['model_origin']==''
    assert next(w for w in app.checkbox if w.label==ui.DECLARATION).value is False
