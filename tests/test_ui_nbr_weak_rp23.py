"""Real app calculation/exports for a previously missing negative local branch.
Run only in the coordinated AppTest/solver window. Synthetic input, no project.
"""
import copy
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas import nbr_ue_family_application as family, nbr_ue_family_ui as ui
from tercas import ue_catalog_reference as own
from en_ue_test_helpers import inputs


def test_real_app_negative_weak_gap_calculation_exports_and_rerender(monkeypatch,tmp_path):
    d=inputs(53,L=6000.)
    d.update(steel_name='Personalizado',q_uls=-.03,q_parallel_uls=-.03,
        P_parallel_uls=0.,P_uls=0.,x_uls=3000.)
    d['properties'].update(fy_MPa=300.,fu_MPa=450.)
    d=own.activate(d)
    payload=json.dumps(d).encode();downloads={};original=st.download_button
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=90)
    next(x for x in a.button if x.label=='Aplicar entradas do arquivo').click().run(timeout=90)
    assert not a.exception
    assert a.session_state.last_input['catalog_index']==53
    assert a.session_state.last_input['properties']['fy_MPa']==300.
    next(x for x in a.button if x.label=='Calcular verificações disponíveis').click().run(timeout=240)
    assert not a.exception
    assert 'result' in a.session_state,[x.value for x in a.error]
    result=copy.deepcopy(a.session_state.result);ev=family.preserved(result)
    branch=ev['sources']['own_rounded_contour']['weak']['negative']['local']
    assert branch['method']=='RP23_01_Eq28_30_lips_compressed'
    assert branch['elastic_approximation'] and not branch['guaranteed_lower_bound']
    assert any(x.value==ui.TITLE for x in a.subheader)
    assert any('weak_negative_local' in x.value.to_string() for x in a.dataframe)
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    word=downloads['Baixar memória parcial (Word)']
    text='\n'.join(p.text for p in Document(io.BytesIO(word)).paragraphs)
    assert ui.TITLE in text and 'RP23-01' in text
    from tercas import direct_torsion,roof_top_load
    from tercas.torsion_vlasov import vlasov
    def forbidden(*a,**k):raise AssertionError('Saved rerender must not solve a member')
    monkeypatch.setattr(direct_torsion,'solve_member',forbidden)
    monkeypatch.setattr(vlasov,'solve_member',forbidden)
    monkeypatch.setattr(roof_top_load,'refined',forbidden)
    a.run(timeout=90)
    assert not a.exception and a.session_state.result==result
    assert not result['whole_member_approved']
    out=Path(os.environ.get('TERCAS_RP23_QA_DIR',str(tmp_path)));out.mkdir(parents=True,exist_ok=True)
    (out/'app53_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (out/'app53_word.docx').write_bytes(word)
    (out/'app53_receipt.json').write_text(json.dumps(dict(index=53,fy_MPa=300,
        calculated=True,RP23_negative_local=True,JSON_matches=True,Word_contains_RP23=True,
        rerender_unchanged=True,no_solver_on_rerender=True,whole_member_approved=False),indent=2))
