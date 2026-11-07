"""Explicit imported-study adoption and measured mixed-load presenter replay."""
import copy
import io
import json
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from en_ue_test_helpers import inputs
from tercas.flt_height_effective import COMBINED_FIELD, COMBINED_METHOD
from tercas.pierin_ue_registry_ui import HISTORY


@pytest.mark.parametrize('index',[0,26])
def test_import_adopt_calculate_export_rerender_restore(monkeypatch,index):
    data=inputs(index,angle=5.71,L=4100.)
    data.update(q_uls=.5,q_sls=.2,P_uls=500.,P_sls=200.,x_uls=1537.,x_sls=1537.)
    payload=json.dumps(data).encode();downloads={};timings={}
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    original=st.download_button
    def capture(label,data,*a,**kw):
        downloads[label]=data
        return original(label,data,*a,**kw)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    def click(label,timeout=120):
        start=time.perf_counter()
        next(w for w in app.button if w.label==label).click().run(timeout=timeout)
        timings[label]=time.perf_counter()-start
        assert not app.exception
    click('Aplicar entradas do arquivo')
    before=copy.deepcopy(app.session_state.last_input)
    assert COMBINED_FIELD not in before
    click('Adotar FLT q+P para novo cálculo')
    assert app.session_state.last_input[COMBINED_FIELD]==COMBINED_METHOD
    assert app.session_state[HISTORY][0]['last_input']==before
    click('Calcular verificações disponíveis')
    result=copy.deepcopy(app.session_state.result)
    from tercas.nbr_ue_family_application import FIELD
    assert result[FIELD]['records'][0]['height_source']['method']==COMBINED_METHOD
    assert result[FIELD]['records'][0]['height_source']['elastic_reference_eligible']
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    assert 'Vlasov/Ritz' in '\n'.join(c.text for t in doc.tables for row in t.rows for c in row.cells)
    start=time.perf_counter();app.run(timeout=120);timings['rerender_with_Word_JSON']=time.perf_counter()-start
    assert not app.exception and app.session_state.result==result
    click('Restaurar estudo preservado')
    assert app.session_state.last_input==before and COMBINED_FIELD not in app.session_state.last_input
    print('FLT_MIXED_UI_TIMINGS_SECONDS='+json.dumps(dict(catalog_index=index,timings=timings),sort_keys=True))
