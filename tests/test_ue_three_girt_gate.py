"""Isolation of own Ue provenance at the public 3D diagnostic entry point."""
import copy
import hashlib
import json
import pytest
from tercas import three_girt_application as g
from tercas import ue_reference as u
from test_three_girt_system import ready


def modified_ue():
    d=u.load_reference()
    d.update(member_application='wall_girt',load_mode='direct',q_uls=.1,P_uls=0.,
             q_sls=.1,P_sls=0.,q_parallel_uls=0.,q_parallel_sls=0.)
    c=g.defaults()
    c.update(enabled=True,tie_count=0,geometry_declared=True,axial_bars_declared=True,
        connections_declared=True,load_line_declared=True,
        origin='Regression negative test, not physical acceptance',
        sc_y_mm=-42.81315215903677,sc_z_mm=0.,sc_origin='Declared test geometry',
        brace_self_weight=False,direct_pp_uls_N_mm=0.,direct_pp_sls_N_mm=0.)
    d['three_girt_model']=c
    return d

@pytest.mark.parametrize('claim',['marked','removed_marker','own_source_only','model_only','documents_only','marker_only'])
def test_own_reference_claim_is_rejected_before_any_solver_or_configuration(monkeypatch,claim):
    d=modified_ue()
    keys={u.FIELD,'ue_model','ue_source_documents','active_numeric_reference'}
    keep={'marked':keys,'removed_marker':keys-{u.FIELD},'own_source_only':{'active_numeric_reference'},
          'model_only':{'ue_model'},'documents_only':{'ue_source_documents'},'marker_only':{u.FIELD}}[claim]
    for key in keys-keep:d.pop(key)
    before=copy.deepcopy(d)
    assert u.claims_reference(d) and not u.assess(d)['active']
    calls=[]
    def forbidden(*args,**kwargs):
        calls.append('called');raise AssertionError('Must reject before configuration or solver')
    monkeypatch.setattr(g,'configuration',forbidden)
    monkeypatch.setattr(g,'solve_three_girts',forbidden)
    with pytest.raises(ValueError,match='Referência própria Ue'):g.calculate(d)
    assert not calls and d==before

@pytest.mark.parametrize('area,expected',[
    (False,'a3935dbce77cb90607fbc01b4840c58d3d69a6db1084577420e7d2c1882d1765'),
    (True,'171288f3f601aa84eacda256d46dcbfd589ac6c37097e68081cfe4d69fa75d1c')])
def test_legacy_3d_results_are_exactly_unchanged(area,expected):
    d=ready(area);before=copy.deepcopy(d);assert not u.claims_reference(d)
    r=g.calculate(d)
    assert hashlib.sha256(json.dumps(r,sort_keys=True,allow_nan=False).encode()).hexdigest()==expected
    assert d==before and r['status']=='conditional_elastic_diagnostic'
    assert len(r['cases'])==(19 if area else 2)
    assert r['whole_member_approved'] is False
