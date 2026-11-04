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


def test_no_implicit_choice_then_explicit_pending(monkeypatch):
    d=family.load_reference(1.5)
    a=imported(monkeypatch,d)
    assert a.session_state.last_input==d
    checkbox(a,'Analisar torção Vlasov (diagnóstico elástico)').check().run(timeout=30)
    assert not a.exception
    chosen=a.session_state.last_input
    assert chosen[torsion.FIELD]==torsion.blank_choice()
    assert not button(a,'Calcular verificações disponíveis').disabled
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception
    result=a.session_state.result
    assert result['torsion_evidence']['pending_model_cases']==58
    assert not result['whole_member_approved']
    assert any('Inconclusivo' in w.value or 'incompleta' in w.value for w in list(a.warning)+list(a.error))
    checkbox(a,'Informar linha — '+torsion.LABELS['CP']).check().run(timeout=30)
    assert not a.exception and 'result' not in a.session_state
    assert a.session_state.last_input[torsion.FIELD]['load_lines']['CP']['xy_from_CG_mm']==[None,None]
    # A partially entered line remains in the editable reference, not inspection.
    next(x for x in a.number_input if x.label=='CP: x a partir do CG [mm]').set_value(12.).run(timeout=30)
    assert not a.exception and not button(a,'Calcular verificações disponíveis').disabled
    assert a.session_state.last_input[torsion.FIELD]['load_lines']['CP']['xy_from_CG_mm']==[12.,None]


def test_import_export_and_deactivate_preserve_declarations(monkeypatch):
    d=family.load_reference(2.25);d[torsion.FIELD]=torsion.blank_choice()
    d[torsion.FIELD]['load_lines']={'CP':dict(declared=True,xy_from_CG_mm=[5.,-8.],origin='Synthetic test')}
    a=imported(monkeypatch,d)
    assert a.session_state.last_input==d
    records=[];old=st.download_button
    def capture(label,data,*args,**kwargs):
        if label=='Baixar entradas da referência (JSON)':records.append(json.loads(data))
        return old(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    a.run(timeout=30);assert records[-1]==d
    checkbox(a,'Analisar torção Vlasov (diagnóstico elástico)').uncheck().run(timeout=30)
    expected=copy.deepcopy(d);expected[torsion.FIELD]['enabled']=False
    assert a.session_state.last_input==expected


def test_global_snapshot_is_fresh_and_old_backend_result_is_not_rewritten(monkeypatch):
    d=family.load_reference(3.35);d['load_mode']='direct'
    a=imported(monkeypatch,d)
    button(a,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not a.exception
    fresh=copy.deepcopy(a.session_state.result)
    assert fresh['completion_snapshot']['historical_results_requalified'] is False
    assert 'global_verification' in fresh
    a.run(timeout=30);assert a.session_state.result==fresh
