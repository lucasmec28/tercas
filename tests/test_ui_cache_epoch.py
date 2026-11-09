"""One-time legacy session cache removal, not a runtime attestation."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from tercas.ui_cache_epoch import EPOCH,KEY,refresh
from tercas.application import fingerprint
APP=str(Path(__file__).resolve().parents[1]/'app.py')
FIXTURE=Path(__file__).parent/'data/legacy_ief_cache_r3.json'

@pytest.mark.parametrize('old',(None,'old_epoch',
    'active_ui_caches_Ue_EN_certificates_strong_width_20261108_r22'))
def test_migration_changes_only_three_active_caches_and_epoch(old):
    state={'base':{'custom':'base'},'last_input':{'custom':'input'},'revision':9,
           'widget_key':17.,'custom_steel_draft':{'value':None},'length_draft_values_9':{'Lx':None},
           'manual_result_history':{'past':'untouched'},'catalog_scan_history':{'past':'untouched'},
           'three_girt_result_history':{'past_3D':'untouched'},
           'three_girt_warping_result':{'old_3D':1},
           'result':{'old':1},'catalog_scan_state':{'running':True,'next_index':42}}
    if old is not None:state[KEY]=old
    before=copy.deepcopy(state)
    assert refresh(state)
    expected={k:v for k,v in before.items() if k not in ('result','catalog_scan_state','three_girt_warping_result',KEY)}|{KEY:EPOCH}
    assert state==expected
    state['result']={'new':2};state['catalog_scan_state']={'running':False}
    state['three_girt_warping_result']={'new_3D':2}
    current=copy.deepcopy(state)
    assert not refresh(state) and state==current


def test_r23_epoch_identifies_only_CT_presentation():
    assert EPOCH == 'active_ui_caches_CT_presentation_20261109_r23'


def test_empty_session_initializes_epoch_without_notification_or_extra_inputs():
    state={};assert not refresh(state);assert state=={KEY:EPOCH}


def test_old_three_girt_cache_alone_triggers_notice_without_touching_inputs_or_history():
    state={'last_input':{'unchanged':True},'three_girt_warping_result':{'old_3D':1},
           'three_girt_result_history':{'historical_3D':1},'three_warping_7_origin':'kept'}
    before=copy.deepcopy(state)
    assert refresh(state)
    assert state=={k:v for k,v in before.items() if k!='three_girt_warping_result'}|{KEY:EPOCH}


def button(app,label):return next(w for w in app.button if w.label==label)
def loaded(monkeypatch,data):
    payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(APP).run(timeout=30)
    button(app,'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    return app

@pytest.mark.parametrize('old',(None,'old_epoch'))
def test_real_old_result_and_running_comparison_removed_before_routes(monkeypatch,old):
    previous=json.loads(FIXTURE.read_text());before=copy.deepcopy(previous)
    app=loaded(monkeypatch,previous['last_input'])
    assert app.session_state.last_input==previous['last_input']
    assert fingerprint(app.session_state.last_input)==previous['result']['input_fingerprint']
    app.session_state['result']=previous['result']
    app.session_state['catalog_scan_state']=previous['catalog_scan_state']
    app.session_state['historical_snapshot_for_test']=copy.deepcopy(previous)
    app.session_state['unrelated_draft_for_test']={'Lx':None,'retained':True}
    if old is None:del app.session_state[KEY]
    else:app.session_state[KEY]=old
    base=copy.deepcopy(app.session_state.base);revision=app.session_state.revision
    widget_values={w.key:w.value for w in app.number_input}
    def unexpected(*a,**kw):raise AssertionError('No hidden calculation or scan is permitted during migration')
    with monkeypatch.context() as scoped:
        scoped.setattr('tercas.application.calculate',unexpected)
        scoped.setattr('tercas.batch.calculate_batch',unexpected)
        scoped.setattr('tercas.catalog_scan.scan_catalog',unexpected)
        app.run(timeout=30)
    assert not app.exception
    assert 'result' not in app.session_state and 'catalog_scan_state' not in app.session_state
    assert app.session_state[KEY]==EPOCH
    assert app.session_state.base==base and app.session_state.last_input==previous['last_input']
    assert app.session_state.revision==revision
    assert {w.key:w.value for w in app.number_input}==widget_values
    assert app.session_state.historical_snapshot_for_test==before
    assert app.session_state.unrelated_draft_for_test=={'Lx':None,'retained':True}
    assert previous==before and KEY not in app.session_state.last_input
    assert any('Atualização do cálculo' in w.value for w in app.info)


def test_current_session_retains_results_and_finished_comparison_on_normal_reruns(monkeypatch):
    from tercas.catalog_scan import scan_catalog
    from tercas.model_domain import VERSION
    previous=json.loads(FIXTURE.read_text());app=loaded(monkeypatch,previous['last_input'])
    button(app,'Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception and app.session_state[KEY]==EPOCH
    result=copy.deepcopy(app.session_state.result)
    data=copy.deepcopy(app.session_state.last_input);part=scan_catalog(data,indices=[0])
    state=dict(model_domain_version=VERSION,fingerprint=fingerprint(data),inputs=data,rows=part['rows'],
               next_index=1,running=False,cancelled=True,elapsed_seconds=part['elapsed_seconds'])
    app.session_state['catalog_scan_state']=copy.deepcopy(state)
    app.run(timeout=30);app.run(timeout=30)
    assert not app.exception
    assert app.session_state.result==result and app.session_state.catalog_scan_state==state
    assert app.session_state.last_input==data and KEY not in data
