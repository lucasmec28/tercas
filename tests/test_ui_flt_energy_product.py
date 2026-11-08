"""Fresh imported short-effective-length calculation, without method adoption."""
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


def test_import_calculate_export_and_reopen_v2_energy(monkeypatch):
    data=inputs(0,angle=4.,L=3600.)
    data.update(q_uls=.32,q_sls=.18,P_uls=240.,P_sls=140.,x_uls=1800.,x_sls=1800.)
    data=declare(data,Lx_mm=1800.,Ly_mm=1800.,Lz_mm=2400.,origin='Synthetic independent lengths')
    payload=json.dumps(data).encode();downloads={};timings={}
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    original=st.download_button
    def capture(label,data,*a,**kw):
        downloads[label]=data
        return original(label,data,*a,**kw)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    for label in ('Aplicar entradas do arquivo','Calcular verificações disponíveis'):
        start=time.perf_counter();next(w for w in app.button if w.label==label).click().run(timeout=120)
        timings[label]=time.perf_counter()-start
        assert not app.exception
    result=copy.deepcopy(app.session_state.result)
    from tercas.nbr_ue_family_application import FIELD,SCHEMA
    assert result[FIELD]['schema']==SCHEMA
    bound=result[FIELD]['records'][0]['height_energy_floor']
    assert bound['schema']=='flt_height_declared_energy_nbr_floor_v2'
    assert bound['energy_floor']['Ly_used_mm']==1800.
    assert bound['energy_floor']['Lz_used_mm']==2400.
    assert bound['energy_floor']['physical_span_mm']==3600.
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    assert doc.tables
    start=time.perf_counter();app.run(timeout=120);timings['rerender']=time.perf_counter()-start
    assert not app.exception and app.session_state.result==result
    print('FLT_ENERGY_V2_UI_SECONDS='+json.dumps(timings,sort_keys=True))
