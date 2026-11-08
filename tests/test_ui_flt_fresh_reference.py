"""Fresh full-span reference for an imported input, without method adoption."""
import copy
import io
import json
import time
from pathlib import Path
from types import SimpleNamespace
from docx import Document
import streamlit as st
from streamlit.testing.v1 import AppTest
from en_ue_test_helpers import inputs
from tercas.resistance_effective_lengths import declare


def test_import_calculate_export_and_reopen_current_reference(monkeypatch):
    data=inputs(0,angle=4.,L=3600.)
    data.update(q_uls=.32,q_sls=.18,P_uls=240.,P_sls=140.,x_uls=1800.,x_sls=1800.)
    data=declare(data,Lx_mm=3600.,Ly_mm=3600.,Lz_mm=3600.,origin='Synthetic independent lengths')
    payload=json.dumps(data).encode();downloads={};timings={}
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    original=st.download_button
    def capture(label,data,*a,**kw):
        downloads[label]=data
        return original(label,data,*a,**kw)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    for label in ('Aplicar entradas do arquivo','Calcular verificações disponíveis'):
        start=time.perf_counter();next(w for w in app.button if w.label==label).click().run(timeout=60)
        timings[label]=time.perf_counter()-start
        assert not app.exception
    result=copy.deepcopy(app.session_state.result)
    from tercas.nbr_ue_family_application import FIELD,SCHEMA
    assert result[FIELD]['schema']==SCHEMA
    from tercas import flt_height_effective as flt
    reference=result[FIELD]['records'][0]['height_source']
    assert reference['schema']==flt.FRESH_SCHEMA
    assert reference['method']==flt.COMBINED_METHOD and reference['elastic_reference_eligible']
    assert reference['Ly_used_mm']==reference['Lz_used_mm']==reference['physical_span_mm']==3600.
    assert flt.COMBINED_FIELD not in result['input_data']
    assert result[FIELD]['records'][0]['height_capacity']['eligible']
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    assert doc.tables
    assert "Ritz" in " ".join(p.text for p in doc.paragraphs)
    from tercas.ui_cache_epoch import EPOCH,KEY
    assert app.session_state[KEY]==EPOCH
    start=time.perf_counter();app.run(timeout=60);timings['rerender']=time.perf_counter()-start
    assert not app.exception and app.session_state.result==result
    print('FLT_FRESH_REFERENCE_UI_SECONDS='+json.dumps(timings,sort_keys=True))
