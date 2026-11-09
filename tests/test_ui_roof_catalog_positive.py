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
from tercas.application import calculate, fingerprint
from tercas.study_completion import complete_result
from tercas.current_calculation_inputs import prepare
from tercas import load_application_policy as policy, nbr_ue_family_application as current_nbr
from tercas.pierin_ue_registry_ui import HISTORY


def test_historical_positive_roof_json_word_and_readonly_replay(monkeypatch):
    d=inputs();d['steel_name']='Personalizado';payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    next(b for b in app.button if b.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    # Produce an unmarked historical snapshot, then display/export it only.
    edited=copy.deepcopy(app.session_state.last_input)
    assert not policy.active(edited)
    historical=complete_result(calculate(edited))
    app.session_state.result=copy.deepcopy(historical)
    app.run(timeout=60)
    assert not app.exception
    assert not any('Não foi possível calcular' in e.value for e in app.error)
    assert any('primeira ordem' in e.value for e in app.error)
    result=copy.deepcopy(app.session_state.result)
    assert result==historical
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



def test_current_catalogue_CT_result_keeps_forces_and_new_snapshot_readonly(monkeypatch):
    from tercas.direct_self_weight import evidence as self_weight_evidence
    from tercas.nbr_ue_family_ui import TITLE as CURRENT_TITLE
    d=inputs();d['steel_name']='Personalizado';before=copy.deepcopy(d)
    payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    next(b for b in app.button if b.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception and app.session_state.base==d
    edited=copy.deepcopy(app.session_state.last_input)
    expected_weights=self_weight_evidence(edited)['states']
    next(b for b in app.button if b.label=='Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception and not any('Não foi possível calcular' in e.value for e in app.error)
    result=copy.deepcopy(app.session_state.result)
    assert result['input_data']==prepare(edited)
    assert result['input_fingerprint']==fingerprint(result['input_data'])
    assert app.session_state[HISTORY][0]['last_input']==edited and d==before
    assert result['direct_self_weight_evidence']['states']==expected_weights
    for field in ('q_uls','q_sls','P_uls','P_sls','q_parallel_uls','q_parallel_sls','P_parallel_uls','P_parallel_sls','x_uls','x_sls'):
        assert result['input_data'][field]==before[field]
    assert 'roof_top_load_evidence' not in result and nbr.FIELD not in result
    evidence=result[current_nbr.FIELD]
    assert evidence['schema']==policy.NBR_SCHEMA and len(evidence['records'])==1
    row=evidence['records'][0]
    interaction=row['member_interaction']['arithmetic']['governing']
    assert interaction is not None and interaction['index_upper']>0
    assert all(item['classification']=='shear_center' for item in row['load_position_by_axis'].values())
    assert not result['global_verification']['whole_member_approved']
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    text='\n'.join(p.text for p in Document(io.BytesIO(downloads['Baixar memória parcial (Word)'])).paragraphs)
    assert CURRENT_TITLE in text and result['input_fingerprint'] in text
    assert any(w.value==CURRENT_TITLE for w in app.subheader)
    pp_scope=result['direct_self_weight_evidence']['scope']
    for item in result['inclination_evidence'].values():
        assert item['convention'].endswith(pp_scope)
        assert item['convention'] in text
        assert any(w.value==item['convention'] for w in app.caption)
    assert 'O programa soma PP no CG' not in text
    assert 'Demais cargas no topo selecionado' not in text
    def fail(*args,**kwargs):raise AssertionError('Replay called structural solver')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(nbr,'flt_mse',fail)
    monkeypatch.setattr('tercas.torsion_study.attach',fail)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==result
