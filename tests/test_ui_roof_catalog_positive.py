"""Real app synthetic own Ue125 route and read-only JSON/Word repeat."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
from docx import Document
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import roof_top_load as roof,roof_top_nbr as nbr
from test_roof_catalog_nbr import inputs


def test_app_positive_json_word_and_readonly_replay(monkeypatch):
    d=inputs();d['steel_name']='Personalizado';payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    next(b for b in app.button if b.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    next(b for b in app.button if b.label=='Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    assert not any('Não foi possível calcular' in e.value for e in app.error)
    assert any('primeira ordem' in e.value for e in app.error)
    result=copy.deepcopy(app.session_state.result)
    assert result[nbr.FIELD]['records'][0]['biaxial']['governing']['index']>0
    assert not result['global_verification']['whole_member_approved']
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    text='\n'.join(p.text for p in Document(io.BytesIO(downloads['Baixar memória parcial (Word)'])).paragraphs)
    assert 'Interação §9.9:' in text and 'AISI RP21-01' in text
    assert any('Flexão biaxial' in table.value.to_string() for table in app.dataframe)
    def fail(*args,**kwargs):raise AssertionError('Replay called structural solver')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(nbr,'flt_mse',fail)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==result
