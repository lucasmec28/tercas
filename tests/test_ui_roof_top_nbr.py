"""Real UI calculation, retained inputs, and read-only component exports."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from docx import Document
from tercas import ue_reference as single,ue_family_reference as family
from tercas import roof_top_load as roof,roof_top_nbr as nbr
from tercas.batch import calculate_batch, area_bundle
from tercas.application import fingerprint
from tercas.current_calculation_inputs import prepare
from tercas.load_application_policy import active as loads_at_CT
from tercas.pierin_ue_registry_ui import HISTORY
from tercas.study_completion import complete_result
from tercas.global_verification import build_global_verification
from tercas.roof_top_nbr_ui import show,report,TITLE,ROW

APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(a,label):return next(x for x in a.button if x.label==label)


@pytest.mark.parametrize('t',[1.2,3.35])
def test_historical_app_retains_NBR_roof_snapshot_and_exports_without_recalculation(t,monkeypatch):
    d=single.load_reference(angle=0.) if t==1.2 else family.load_reference(t,4000.,0.)
    d['selected_types']=['ELU normal','ELS quase permanente'];d[roof.FIELD]=roof.choice()
    payload=json.dumps(d).encode();monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    a=AppTest.from_file(APP).run(timeout=30)
    button(a,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not a.exception and a.session_state.last_input==d
    number_labels=[w.label for w in a.number_input]
    # The unmarked producer remains a historical lane. Reading that snapshot
    # in today's editor must preserve the old roof/H4 evidence exactly.
    historical=complete_result(calculate_batch(d))
    assert not loads_at_CT(historical['input_data'])
    a.session_state.result=copy.deepcopy(historical)
    a.run(timeout=60)
    assert not a.exception
    result=copy.deepcopy(a.session_state.result)
    assert result==historical
    assert result[nbr.FIELD]['computed_cases']==40
    assert result['aisi_torsion_component']['H4_computed_cases']==(0 if t==1.2 else 40)
    assert a.session_state.last_input==d
    assert [w.label for w in a.number_input]==number_labels
    assert any(w.value==TITLE for w in a.subheader)
    assert any(ROW in w.value.to_string() for w in a.dataframe)
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    doc=Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    text='\n'.join(p.text for p in doc.paragraphs)
    assert TITLE in text and 'MRd,FLT=' in text
    assert 'não momento resistente' in text  # Me itself is still not MRd.
    def fail(*a,**k):raise AssertionError('Component recalculated while reading')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(nbr,'flt_mse',fail)
    a.run(timeout=30)
    assert not a.exception and a.session_state.result==result


@pytest.mark.parametrize('t',[1.2,3.35])
def test_current_app_recalculates_CT_without_mutating_actions_or_historical_line(t,monkeypatch):
    d=single.load_reference(angle=0.) if t==1.2 else family.load_reference(t,4000.,0.)
    d['selected_types']=['ELU normal','ELS quase permanente'];d[roof.FIELD]=roof.choice()
    before=copy.deepcopy(d);expected_combinations=area_bundle(d)['combinations']
    payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    downloads={};original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label in ('Baixar estudo e resultados (JSON)','Baixar memória parcial (Word)'):downloads[label]=data
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_file(APP).run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception and app.session_state.last_input==d
    labels=[w.label for w in app.number_input]
    assert not any(w.label=='Esquema da carga da cobertura' for w in app.selectbox)
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result)
    assert result['input_data']==app.session_state.last_input==prepare(d)
    assert result['input_fingerprint']==fingerprint(result['input_data'])
    assert app.session_state[HISTORY][0]['last_input']==d and d==before
    assert result['input_data'][roof.FIELD]==before[roof.FIELD]
    assert 'roof_top_load_evidence' not in result and nbr.FIELD not in result
    assert [c['combination'] for c in result['cases']]==expected_combinations
    elu=[c for c in result['cases'] if c['combination']['limit_state']=='ELU']
    assert len(elu)==40
    assert all(any(f.get('index') is not None for f in c['evidence']['FLT_segments']) for c in elu)
    assert not result['whole_member_approved']
    assert [w.label for w in app.number_input]==labels
    assert json.loads(downloads['Baixar estudo e resultados (JSON)'])==result
    text='\n'.join(p.text for p in Document(io.BytesIO(downloads['Baixar memória parcial (Word)'])).paragraphs)
    assert result['input_fingerprint'] in text and TITLE not in text
    def fail(*args,**kwargs):raise AssertionError('Current saved result must not recalculate')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(nbr,'flt_mse',fail)
    monkeypatch.setattr('tercas.torsion_study.attach',fail)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==result


SCRIPT='''
import streamlit as st
from tercas.roof_top_nbr_ui import show
from tercas.study_completion import show_global
if 'saved' in st.session_state:
    show(st,st.session_state.saved)
    show_global(st,st.session_state.saved)
'''


def test_missing_sidecar_suppresses_saved_global_promotion():
    d=family.load_reference(2.,4000.,0.);d['selected_types']=['ELU normal'];d[roof.FIELD]=roof.choice()
    result=nbr.attach(roof.attach(calculate_batch(d)));result['global_verification']=build_global_verification(result)
    result.pop(nbr.FIELD)
    app=AppTest.from_string(SCRIPT).run();app.session_state.saved=result;app.run()
    assert not app.exception
    assert any('Panorama não exibido' in w.value for w in app.warning)
    assert not app.error


def test_word_and_UI_pending_component_are_specific():
    d=family.load_reference(2.,4000.,-5.);d['selected_types']=['ELU normal'];d[roof.FIELD]=roof.choice()
    result=nbr.attach(roof.attach(calculate_batch(d)))
    app=AppTest.from_string(SCRIPT).run();app.session_state.saved=result;app.run()
    assert not app.exception
    assert len(app.dataframe)==1
    assert 'desestabilizante' in app.dataframe[0].value.to_string()
    doc=Document();report(doc,result)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'desestabilizante' in text and 'MRd,FLT=' not in text
