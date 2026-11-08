"""Own-reference isolated application, immutable imports and horizontal criterion."""
import copy,json
from pathlib import Path
from types import SimpleNamespace
import pytest,streamlit as st
from streamlit.testing.v1 import AppTest
from tercas import ue_reference as ue,ue_family_reference as family,deflection_scope,torsion_study
from tercas.ue_member_application import apply,FIELD as APPLICATION_FIELD
from tercas.biaxial_component import activate,FIELD,GIRT_SCHEMA,GIRT_ROW,LABEL
from tercas.current_calculation_inputs import prepare
from tercas.pierin_ue_registry_ui import HISTORY
from tercas.direct_self_weight import FIELD as PP_FIELD
APP=str(Path(__file__).resolve().parents[1]/'app.py')


def widget(a,kind,label):return next(w for w in getattr(a,kind) if w.label==label)
def run(a):
    a.run(timeout=60);assert not a.exception;return a

def imported(monkeypatch,data):
    raw=json.dumps(data).encode();monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(raw),getvalue=lambda:raw))
    a=run(AppTest.from_file(APP));widget(a,'button','Aplicar entradas do arquivo').click();return run(a)

def seed(t):
    d=ue.load_reference(angle=5.) if t==1.2 else family.load_reference(t,4000.,5.)
    d.update(load_mode='direct',q_sls=.025,q_parallel_sls=.0075,P_sls=-75.,P_parallel_sls=-10.,x_sls=1200.)
    return d


@pytest.mark.parametrize('t',[1.2,1.5])
def test_application_requires_explicit_apply_and_preserves_round_trip(monkeypatch,t):
    d=seed(t);a=imported(monkeypatch,d)
    widget(a,'button','Calcular verificações disponíveis').click();run(a)
    assert 'result' in a.session_state
    current=prepare(d)
    assert a.session_state.last_input==current
    assert a.session_state[HISTORY][0]['last_input']==d
    widget(a,'selectbox','Aplicação da referência própria').select('wall_girt');run(a)
    assert a.session_state.last_input==current and 'result' not in a.session_state
    assert widget(a,'button','Calcular verificações disponíveis').disabled
    widget(a,'button','Aplicar aplicação isolada da referência').click();run(a)
    expected=apply(current,'wall_girt');assert a.session_state.last_input==expected
    assert not any(x.label=='Inclinação da cobertura [graus]' for x in a.number_input)
    widget(a,'number_input','Comprimento de referência horizontal [mm]').set_value(3500.);run(a)
    widget(a,'number_input','Denominador do limite horizontal').set_value(140.);run(a)
    widget(a,'checkbox',LABEL).check();run(a)
    widget(a,'button','Calcular verificações disponíveis').click();run(a)
    r=copy.deepcopy(a.session_state.result);assert r[FIELD]['schema']==GIRT_SCHEMA
    assert r['ELS']['limit_mm']==25. and r['ELS']['index']==abs(r['ELS']['deflection_mm'])/25.
    assert not r['global_verification']['combined_ELS_approved']
    assert any('horizontal normal ao fechamento' in x.value for x in a.info)
    saved=copy.deepcopy(a.session_state.last_input);run(a);assert a.session_state.result==r
    widget(a,'selectbox','Aplicação da referência própria').select('purlin');run(a)
    assert 'result' not in a.session_state
    widget(a,'button','Aplicar aplicação isolada da referência').click();run(a)
    assert a.session_state.last_input==apply(saved,'purlin')
    assert a.session_state.last_input['wall_els']==saved['wall_els']
    assert any(x.label=='Inclinação da cobertura [graus]' for x in a.number_input)


@pytest.mark.parametrize('t',[1.2,1.5])
def test_import_horizontal_criterion_and_inactive_torsion_are_preserved(monkeypatch,t):
    d=apply(seed(t),'wall_girt');d['torsion_model']=torsion_study.blank_choice();d=activate(d)
    before=copy.deepcopy(d);a=imported(monkeypatch,d)
    assert a.session_state.last_input==before
    assert not any(w.label=='Analisar torção Vlasov (diagnóstico elástico)' for w in a.checkbox)
    assert not any(x.value=='Para demanda isolada, adote explicitamente o contorno próprio da travessa. Declarações antigas são preservadas.' for x in a.caption)
    assert not any(w.label=='Adotar modelo Vlasov isolado com garfos e empenamento livre' for w in a.checkbox)
    assert a.session_state.last_input['torsion_model']['schema']==torsion_study.SCHEMA
    widget(a,'button','Calcular verificações disponíveis').click();run(a)
    r=copy.deepcopy(a.session_state.result)
    # These direct values are legacy TOTALS. CT does not invent a separated
    # external/PP contract merely to satisfy the Vlasov producer.
    assert r['torsion_evidence']['computed_cases']==0 and r['input_data']==prepare(d)
    assert PP_FIELD not in r['input_data'] and PP_FIELD not in a.session_state.last_input
    for key in ('q_uls','q_sls','q_parallel_uls','q_parallel_sls','P_uls','P_sls','P_parallel_uls','P_parallel_sls','x_uls','x_sls'):
        assert r['input_data'].get(key)==before.get(key)
    assert a.session_state[HISTORY][0]['last_input']==before
    assert r['input_data']['torsion_model']==before['torsion_model']
    assert r['ELS']['component_schema']==GIRT_SCHEMA
    widget(a,'checkbox',deflection_scope.LABEL).check();run(a)
    assert 'result' not in a.session_state and a.session_state.last_input['member_application']=='wall_girt'
    assert a.session_state.last_input['torsion_model']==d['torsion_model']
    widget(a,'checkbox',deflection_scope.LABEL).uncheck();run(a)
    assert 'deflection_model' not in a.session_state.last_input
    assert not widget(a,'checkbox',LABEL).value


def test_horizontal_limit_invalid_draft_is_recoverable(monkeypatch):
    d=activate(apply(seed(1.5),'wall_girt'));a=imported(monkeypatch,d)
    widget(a,'button','Calcular verificações disponíveis').click();run(a)
    widget(a,'number_input','Denominador do limite horizontal').set_value(None);run(a)
    assert 'result' not in a.session_state and a.session_state.last_input['wall_els']['normal_denominator'] is None
    assert widget(a,'button','Calcular verificações disponíveis').disabled
    widget(a,'number_input','Denominador do limite horizontal').set_value(120.);run(a)
    widget(a,'button','Calcular verificações disponíveis').click();run(a)
    assert 'result' in a.session_state and a.session_state.result['ELS']['limit_mm']==4000./120.


def test_invalid_preserved_vertical_draft_has_explicit_repair(monkeypatch):
    d=activate(apply(seed(1.5),'wall_girt'));d['wall_els']['vertical_denominator']=None
    a=imported(monkeypatch,d)
    assert a.session_state.last_input['wall_els']['vertical_denominator'] is None
    assert widget(a,'button','Calcular verificações disponíveis').disabled
    widget(a,'number_input','Reparar denominador vertical preservado').set_value(180.);run(a)
    assert a.session_state.last_input['wall_els']['vertical_denominator']==180.
    widget(a,'button','Calcular verificações disponíveis').click();run(a)
    assert a.session_state.result['ELS']['component_schema']==GIRT_SCHEMA
    assert a.session_state.result['ELS']['limit_mm']==4000./120.
    assert not a.session_state.result['global_verification']['combined_ELS_approved']


@pytest.mark.parametrize('encoded',['1e999','-'+str(10**400),str(2**53+1)])
def test_json_numeric_overflow_or_rounding_stays_in_inspection(monkeypatch,encoded):
    d=apply(seed(1.5),'wall_girt');d['wall_els']['normal_denominator']=987654321.123
    raw=json.dumps(d).replace('987654321.123',encoded).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(raw),getvalue=lambda:raw))
    a=run(AppTest.from_file(APP));widget(a,'button','Aplicar entradas do arquivo').click();run(a)
    assert 'result' not in a.session_state
    assert a.session_state.last_input['wall_els']['normal_denominator']==json.loads(encoded)
    assert not any(x.label=='Denominador do limite horizontal' for x in a.number_input)
    assert any('não editável' in x.value for x in a.warning)
