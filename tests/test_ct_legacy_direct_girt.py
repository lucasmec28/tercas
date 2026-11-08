"""A new load location cannot reinterpret old combined direct-load totals."""
import copy
import json
import pytest
from tercas import direct_self_weight as pp, load_application_policy as ct
from tercas import torsion_study, ue_reference, ue_family_reference
from tercas.application import calculate, fingerprint
from tercas.ue_member_application import apply


def inputs(t):
    d=ue_reference.load_reference(angle=5.) if t==1.2 else ue_family_reference.load_reference(t,4000.,5.)
    d.update(load_mode='direct',q_uls=.031,q_parallel_uls=.009,P_uls=-95.,P_parallel_uls=-12.,x_uls=1300.,
             q_sls=.025,q_parallel_sls=.0075,P_sls=-75.,P_parallel_sls=-10.,x_sls=1200.)
    d=apply(d,'wall_girt')
    d['torsion_model']=torsion_study.blank_choice()
    assert pp.FIELD not in d
    return d


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_CT_legacy_direct_totals_do_not_enter_separated_solver(t,monkeypatch):
    from tercas import direct_torsion
    d=ct.adopt(inputs(t));original=copy.deepcopy(d)
    def forbidden(*args,**kwargs):
        pytest.fail('Combined legacy totals must not enter the separated-PP solver')
    monkeypatch.setattr(direct_torsion,'attach',forbidden)
    r=dict(schema='NBR14762_one_span_v1',input_data=d,input_fingerprint=fingerprint(d),
           ULS={'sentinel':1},ELS={'sentinel':2},whole_member_approved=False)
    before=copy.deepcopy(r);out=torsion_study.attach(r);ev=out.pop('torsion_evidence')
    assert out==before and r==before and d==original
    assert ev['status']=='pending_model_data' and ev['computed_cases']==0
    assert ev['pending_model_cases']==2 and not ev['coverage_complete']
    assert not ev['resistance_qualified'] and not ev['whole_member_approved']
    assert ev['reason_code']=='direct_totals_without_separated_actions'
    assert ev['records']==[] and ev['source_input_fingerprint']==fingerprint(d)
    assert pp.evidence(d) is None and pp.calculation_inputs(d)==d


@pytest.mark.parametrize('t',[1.2,1.5])
def test_complete_CT_legacy_direct_preserves_scalar_results_and_history(t):
    from tercas.study_completion import complete_result
    old=inputs(t);before=copy.deepcopy(old)
    historical=complete_result(calculate(old));saved=json.dumps(historical,sort_keys=True)
    d=ct.adopt(old);raw=calculate(d);out=complete_result(raw)
    assert old==before and json.dumps(historical,sort_keys=True)==saved
    assert out['input_data']==d and pp.FIELD not in out['input_data']
    assert 'direct_self_weight_evidence' not in out
    # Completion may add assessments, but it cannot recalculate any scalar.
    assert all(out[key]==value for key,value in raw.items())
    for state in ('ULS','SLS'):
        assert out['input_snapshot'][state]==historical['input_snapshot'][state]
    assert out['ELS']==historical['ELS']
    assert out['torsion_evidence']['reason_code']=='direct_totals_without_separated_actions'
    assert not out['whole_member_approved']
    checks=out['global_verification']['checks']
    assert any(row['id']=='torsion_warping' and row['status']=='pending' for row in checks)


def test_CT_separated_direct_contract_still_dispatches_to_solver(monkeypatch):
    from tercas import direct_torsion
    d=ct.adopt(pp.activate(inputs(1.2)))
    r=dict(schema='NBR14762_one_span_v1',input_data=d,input_fingerprint=fingerprint(d))
    calls=[];sentinel=object()
    def expected(result,choice):
        calls.append((result,choice));return sentinel
    monkeypatch.setattr(direct_torsion,'attach',expected)
    assert torsion_study.attach(r) is sentinel
    assert len(calls)==1 and calls[0][0] is r
    assert calls[0][1]==ct.torsion_choice(d)
