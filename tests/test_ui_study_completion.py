"""Explicit UI selections, missing data, invalidation and exact input exports."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import ue_family_reference as family
from tercas import torsion_study as torsion
from tercas.batch import calculate_batch, area_bundle
from tercas.study_completion import complete_result
from tercas.current_calculation_inputs import prepare
from tercas.load_application_policy import active as loads_at_CT
from tercas.pierin_ue_registry_ui import HISTORY

APP=str(Path(__file__).resolve().parents[1]/'app.py')
def button(a,label):return next(x for x in a.button if x.label==label)
def checkbox(a,label):return next(x for x in a.checkbox if x.label==label)


def imported(monkeypatch,d):
    payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    a=AppTest.from_file(APP).run(timeout=30)
    button(a,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not a.exception
    return a


def test_historical_missing_lines_remain_pending_in_saved_reader(monkeypatch):
    d=family.load_reference(1.5);d[torsion.FIELD]=torsion.blank_choice()
    historical=complete_result(calculate_batch(d))
    assert not loads_at_CT(d)
    assert historical['torsion_evidence']['pending_model_cases']==58
    assert not historical['whole_member_approved']
    app=imported(monkeypatch,d)
    assert app.session_state.last_input==d
    app.session_state.result=copy.deepcopy(historical)
    def forbidden(*args,**kwargs):raise AssertionError('Historical reader must not solve missing lines')
    monkeypatch.setattr(torsion,'attach',forbidden)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==historical
    assert any('Inconclusivo' in w.value or 'incompleta' in w.value for w in list(app.warning)+list(app.error))
    assert app.session_state.last_input==d


def test_current_area_calculation_has_no_manual_line_controls_and_invalidates_on_action(monkeypatch):
    d=family.load_reference(1.5);before=copy.deepcopy(d)
    expected_combinations=area_bundle(d)['combinations']
    app=imported(monkeypatch,d)
    assert app.session_state.last_input==d
    labels=[w.label for kind in ('checkbox','number_input') for w in getattr(app,kind)]
    assert 'Analisar torção Vlasov (diagnóstico elástico)' not in labels
    assert not any('Informar linha' in label or 'CP: x a partir do CG' in label for label in labels)
    assert not button(app,'Calcular verificações disponíveis').disabled
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result)
    assert result['input_data']==prepare(d)
    assert torsion.FIELD not in result['input_data']
    assert [c['combination'] for c in result['cases']]==expected_combinations
    assert result['torsion_evidence']['computed_cases']==58
    assert result['torsion_evidence']['pending_model_cases']==0
    assert not result['whole_member_approved']
    assert app.session_state[HISTORY][0]['last_input']==d and d==before
    next(w for w in app.number_input if w.label=='Permanente [kgf/m²]').set_value(d['area_inputs']['permanent_kgf_m2']+1.).run(timeout=30)
    assert not app.exception and 'result' not in app.session_state
    assert not button(app,'Calcular verificações disponíveis').disabled
    assert torsion.FIELD not in app.session_state.last_input
    assert app.session_state[HISTORY][0]['last_input']==before


@pytest.mark.parametrize('enabled',[True,False])
@pytest.mark.parametrize('xy',[[5.,-8.],[12.,None]],ids=['complete','partial'])
def test_import_export_and_current_calculation_preserve_inactive_manual_declarations(monkeypatch,enabled,xy):
    d=family.load_reference(2.25);d[torsion.FIELD]=torsion.blank_choice()
    d[torsion.FIELD]['enabled']=enabled
    d[torsion.FIELD]['load_lines']={'CP':dict(declared=True,xy_from_CG_mm=copy.deepcopy(xy),origin='Synthetic test')}
    before=copy.deepcopy(d);app=imported(monkeypatch,d)
    assert app.session_state.last_input==d
    records=[];old=st.download_button
    def capture(label,data,*args,**kwargs):
        if label=='Baixar entradas da referência (JSON)':records.append(json.loads(data))
        return old(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app.run(timeout=30)
    assert records[-1]==d and app.session_state.last_input==d
    assert not any(w.label=='Analisar torção Vlasov (diagnóstico elástico)' for w in app.checkbox)
    assert not any('CP: x a partir do CG' in w.label for w in app.number_input)
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result)
    assert result['input_data']==prepare(d)
    assert result['input_data'][torsion.FIELD]==before[torsion.FIELD]
    assert result['torsion_evidence']['computed_cases']==58
    assert result['torsion_evidence']['pending_model_cases']==0
    assert app.session_state[HISTORY][0]['last_input']==before and d==before
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==result
    assert records[-1]==prepare(d)


def test_global_snapshot_is_fresh_and_old_backend_result_is_not_rewritten(monkeypatch):
    d=family.load_reference(3.35);d['load_mode']='direct'
    a=imported(monkeypatch,d)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception
    fresh=copy.deepcopy(a.session_state.result)
    assert fresh['completion_snapshot']['historical_results_requalified'] is False
    assert 'global_verification' in fresh
    a.run(timeout=30);assert a.session_state.result==fresh
