"""Local synthetic UI workflow; no hosted upload or project information."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas import isolated_en_ue_family_application as en
from tercas import isolated_en_ue_concurrent_candidate as extension
from tercas import isolated_en_ue_family_ui as ui
from tercas import ue_catalog_reference as own
from test_en_concurrent_r12_application import data


def test_new_method_calculation_exports_and_saved_rerender(monkeypatch):
    d=data();d['steel_name']='Personalizado'
    origin=d[en.CHOICE]['model_origin'];d=own.activate(d);d=en.activate(d,model_origin=origin)
    payload=json.dumps(d).encode();downloads={};original=st.download_button
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    next(x for x in app.button if x.label=='Aplicar entradas do arquivo').click().run(timeout=60)
    assert not app.exception
    assert app.session_state.last_input['properties']['fy_MPa']==300.
    next(x for x in app.checkbox if x.label==ui.DECLARATION).check().run(timeout=60)
    next(x for x in app.text_input if x.label==ui.ORIGIN).set_value('Synthetic UI intact-section declaration').run(timeout=60)
    assert app.session_state.last_input[en.CHOICE]['intact_section_model_declared']
    next(x for x in app.button if x.label=='Calcular verificações disponíveis').click().run(timeout=180)
    assert not app.exception
    assert 'result' in app.session_state,[x.value for x in app.error]
    result=copy.deepcopy(app.session_state.result);ev=en.preserved(result)
    assert ev['records'][0]['check']['schema']==extension.SCHEMA
    assert ev['stress_computed_cases']==ev['mv_computed_cases']==1
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    text='\n'.join(p.text for p in Document(io.BytesIO(downloads['Baixar memória parcial (Word)'])).paragraphs)
    assert 'pisos próprios consumidos em EN6.27' in text
    assert 'Sem crédito por cancelamento' in text
    from tercas import direct_torsion
    from tercas.torsion_vlasov import vlasov
    def forbidden(*a,**k):raise AssertionError('Saved UI must not solve a member')
    monkeypatch.setattr(direct_torsion,'solve_member',forbidden)
    monkeypatch.setattr(vlasov,'solve_member',forbidden)
    app.run(timeout=60)
    assert not app.exception and app.session_state.result==result
    assert not result['whole_member_approved']
