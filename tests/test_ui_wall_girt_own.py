"""Actual app wiring: local girt lines are exposed without roof adoption."""
import copy,json
from pathlib import Path
from types import SimpleNamespace
import streamlit as st
from streamlit.testing.v1 import AppTest
from test_wall_girt_own_isolated import data
from tercas import wall_girt_isolated as girt


def test_girt_local_controls_and_readonly_result(monkeypatch):
    d=data(26);payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    next(w for w in app.button if w.label=='Aplicar entradas do arquivo').click().run(timeout=60)
    assert not app.exception
    assert not any(w.label=='Adotar modelo Vlasov isolado com garfos e empenamento livre' for w in app.checkbox)
    assert not any('x local, vertical para baixo' in w.label for w in app.number_input)
    # The common editor already normalizes length/metadata defaults. The
    # imported base itself and existing mechanical actions stay unchanged.
    assert app.session_state.base==d
    edited=copy.deepcopy(app.session_state.last_input)
    for field in ('q_uls','q_sls','P_uls','P_sls','x_uls','x_sls','properties','torsion_model'):
        assert edited[field]==d[field]
    assert 'load_application_policy' not in edited
    assert app.session_state.last_input['torsion_model']['schema']==girt.SCHEMA
    next(w for w in app.button if w.label=='Calcular verificações disponíveis').click().run(timeout=120)
    assert not app.exception
    result=copy.deepcopy(app.session_state.result)
    assert result['torsion_evidence']['computed_cases']==2
    assert result['deflection_scope_evidence']['application']=='wall_girt'
    from tercas import nbr_ue_family_application as nbr_app
    from tercas import load_application_policy as policy
    from tercas.current_calculation_inputs import prepare
    assert result[nbr_app.FIELD]['schema']==policy.NBR_GIRT_SCHEMA
    assert result['input_data']==prepare(edited)
    from tercas.pierin_ue_registry_ui import HISTORY
    assert app.session_state[HISTORY][0]['last_input']==edited
    assert result['input_data']['torsion_model']==d['torsion_model']
    assert result[nbr_app.FIELD]['records']
    assert not any('PP uma vez no CG' in w.value for w in app.caption)
    from tercas import direct_torsion
    monkeypatch.setattr(direct_torsion,'solve_member',lambda **kw: (_ for _ in ()).throw(AssertionError('Rerender must not solve')))
    app.run(timeout=60)
    assert not app.exception and app.session_state.result==result
