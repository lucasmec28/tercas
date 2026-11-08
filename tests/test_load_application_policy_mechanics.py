"""CT is an applied-load location, not a command to zero torsional response."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
from tercas import load_application_policy as policy


@pytest.mark.parametrize('kind',['roof','girt'])
def test_vlasov_zero_external_torque_emerges_from_load_coordinates(kind):
    from en_ue_test_helpers import inputs
    from test_wall_girt_own_isolated import data
    from tercas.application import calculate
    from tercas.study_completion import complete_result
    d=inputs(26,angle=5.71) if kind=='roof' else data(26)
    d.update(q_uls=.15,q_parallel_uls=.08,P_uls=150.,P_parallel_uls=20.,x_uls=1537.,P_sls=100.,x_sls=1600.)
    original=copy.deepcopy(d)
    r=complete_result(calculate(policy.adopt(d)))
    assert d==original and 'roof_top_load_evidence' not in r
    assert len(r['torsion_evidence']['records'])==2
    for row in r['torsion_evidence']['records']:
        assert row['status']=='elastic_demand_computed'
        a=row['analysis'];sc=a['section']['properties']['shear_center_xy_mm']
        assert {'EXTERNAL','PP','P'}=={x['name'] for x in a['loads']}
        for load in a['loads']:
            assert load['application_xy_mm']==sc
            assert load['torque_SC_N' if load['kind']=='uniform' else 'torque_SC_Nmm']==0.
        for key in ('T_Nmm','Tsv_Nmm','Tw_Nmm','B_Nmm2','phi_rad','psi_per_mm'):
            assert a['field_envelopes'][key]['maximum_absolute']['value']==0.
        # A torque about a different reference point is NOT erased.
        assert abs(a['field_envelopes']['T_CG_Nmm']['maximum_absolute']['value'])>0.
    assert not r['whole_member_approved']


def test_network_weight_load_arm_changes_without_changing_connection_stiffness(monkeypatch):
    from tercas.three_girt_warping import application as w,network
    from tercas.three_girt_assessment import application as assessment
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    old=src['input_data'];cfg=src['configuration']
    # Direct inputs shorten the fixture to two states; keep all six real bars,
    # their connections and nonzero self-weight.
    old.update(load_mode='direct',q_uls=.2,q_sls=.1,q_parallel_uls=.12,q_parallel_sls=.08,
               P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.)
    cfg['three_girt'].update(brace_self_weight=True,direct_brace_factor_uls=1.25,
        direct_brace_factor_sls=1.,direct_pp_uls_N_mm=.04,direct_pp_sls_N_mm=.03)
    runs=[];original=network.solve
    def capture(*args,**kwargs):
        run=original(*args,**kwargs);runs.append(run);return run
    monkeypatch.setattr(network,'solve',capture)
    legacy=w.calculate(old,cfg)
    new_data=policy.adopt(old);new_cfg=copy.deepcopy(cfg)
    new_cfg['three_girt']['load_line_declared']=False
    current=w.calculate(new_data,new_cfg)
    assert assessment.validate_demand(legacy) and assessment.validate_demand(current)
    assert legacy['configuration']['connections']==current['configuration']['connections']
    assert len(runs)==4
    for before,after in zip(runs[:2],runs[2:]):
        assert np.array_equal(before['K'].toarray(),after['K'].toarray())
        assert np.array_equal(before['fixed'],after['fixed'])
        assert np.array_equal(before['xyz'],after['xyz'])
        assert before['inputs']['connections']==after['inputs']['connections']
        for ob,nb in zip(before['bars'],after['bars']):
            assert ob['self_weight_N']==nb['self_weight_N']
            assert np.array_equal(ob['beta'],nb['beta'])
        s=after['section']
        for q in after['inputs']['loads']:
            assert q['distributed_torque_CG_N']-s['sc_y_mm']*q['q_z_N_mm']+s['sc_z_mm']*q['q_y_N_mm']==pytest.approx(0.,abs=1e-12)
        for node in range(len(after['xyz'])):
            f=after['physical_nodal'][7*node:7*node+7]
            assert f[3]-s['sc_y_mm']*f[2]+s['sc_z_mm']*f[1]==pytest.approx(0.,abs=1e-12)
        assert sum(after['physical_nodal'][1::7])==pytest.approx(-sum(b['self_weight_N'] for b in after['bars']))
        # Actual connections retain eccentricity: no overwrite of internal T.
        assert any(abs(b['physical_girt_actions'][:,3]).max()>1. for b in after['bars'])
    from tercas.three_girt_axial import application as axial
    axial._validate(current,axial.reference_configuration(current))


def test_legacy_network_CT_weight_model_has_balanced_force_and_moment():
    from test_three_girt_system import ready
    from tercas.three_girt_application import calculate
    d=policy.adopt(ready());d['three_girt_model'].update(sc_z_mm=8.,load_line_declared=False,brace_self_weight=True)
    r=calculate(d)
    assert r['status']=='conditional_elastic_diagnostic'
    for row in r['cases']:
        m=row['model'];assert m['inputs'][policy.FIELD]==policy.MODE
        assert max(map(abs,m['residuals']['global_force_N']))<1e-8
        assert max(map(abs,m['residuals']['global_moment_Nmm']))<1e-5
