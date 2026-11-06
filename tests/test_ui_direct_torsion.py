"""Actual app direct workflow, saved reports, and read-only rerender."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas import aisi_torsion_component as aisi, aisi_roof_height as height, direct_torsion
from test_direct_torsion import inputs

APP=str(Path(__file__).resolve().parents[1]/'app.py')


def test_direct_PP_H4_screen_exports_and_readonly_rerender(monkeypatch):
    d=inputs(P=20.);payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(APP).run(timeout=30)
    next(x for x in app.button if x.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    labels=[w.label for w in app.number_input]
    next(x for x in app.button if x.label=='Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result);e=aisi.preserved(result)
    assert e['H4_computed_cases']==1 and e['schema']==height.DIRECT_SCHEMA
    assert app.session_state.last_input==d and [w.label for w in app.number_input]==labels
    assert not any('H4 permanecem pendentes no modo direto' in w.value for w in app.warning)
    assert any('Modo direto separado' in w.value for w in app.caption)
    table=next(x.value for x in app.dataframe if 'Ma,piso AISI [kN·m]' in x.value.columns)
    assert len(table)==1 and table.iloc[0]['Combinação']=='DIRECT_ELU'
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'DIRECT_ELU' in text and '1,25 no ELU e 1,0 no ELS' in text
    assert 'Cisalhamento e suas interações' in text and not result['whole_member_approved']
    def fail(*args,**kwargs):raise AssertionError('Saved UI must not solve')
    monkeypatch.setattr(height,'refined',fail);monkeypatch.setattr(aisi,'_aisi_demand',fail)
    monkeypatch.setattr(direct_torsion,'solve_member',fail)
    app.run(timeout=30)
    next(x for x in app.checkbox if x.label=='Exibir memória numérica salva do caso direto').check().run(timeout=30)
    assert not app.exception and app.session_state.result==result
