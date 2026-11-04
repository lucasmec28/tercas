import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tercas.torsion_vlasov.intervals import Interval as I,power_to_bernstein,multiply_bernstein,elevate_bernstein
from tercas.torsion_vlasov.yield_envelope import maximize_field,member_yield_envelope,build_stress_patches
from tercas.torsion_vlasov.vlasov import solve_member
from tercas.torsion_vlasov.section import load_profile
from tercas.torsion_vlasov.adapter import support_limit_before_point


def synthetic_patches(sigma,tau):
    s=power_to_bernstein(I(np.asarray(sigma,float)[None,:,:]));t=power_to_bernstein(I(np.asarray(tau,float)[None,:,:]))
    ns,ms=s.lo.shape[-2:];nt,mt=t.lo.shape[-2:]
    a=multiply_bernstein(s,s);b=multiply_bernstein(t,t)
    target_s=max(2*ns-2,2*nt-2);target_r=max(2*ms-2,2*mt-2)
    for axis,degree in [(-2,target_s),(-1,target_r)]:a=elevate_bernstein(a,axis,degree);b=elevate_bernstein(b,axis,degree)
    return dict(sigma=s,tau=t,vm_squared=a+b*3.,patch_count=1)


@pytest.mark.parametrize('s,t,expected',[
    ([[6]],[[8]],math.sqrt(228)),
    ([[0],[1]],[[1],[-1]],math.sqrt(3)),
    ([[0],[4],[-4]],[[0]],1.),
    ([[0]],[[0,0,0],[0,1,-1],[0,-1,1]],math.sqrt(3)/16),
])
def test_known_joint_polynomial_maximum(s,t,expected):
    p=synthetic_patches(s,t);r=maximize_field(p,'von_mises',relative_tolerance=1e-7,absolute_tolerance_MPa=1e-9)
    assert r['converged'] and r['lower_MPa']<=expected<=r['upper_MPa']
    assert r['upper_MPa']-r['lower_MPa']<=max(1e-9,1e-7*r['upper_MPa'])


def section(t=1.5):return load_profile(ROOT/f'tercas/data/torsion_profiles/ue100x50x17_t{t:.2f}.json')


def member(kind='uniform',scale=1.,n=8):
    s=section();cg=s['properties']['centroid_xy_mm'];actions=[]
    if kind in ('uniform','mixed','zero'):
        q=[.03,-.12] if kind!='zero' else [0.,0.]
        actions.append(dict(name='q',kind='uniform',q_xy_N_mm=[scale*x for x in q],couple_N=0.,application_xy_mm=cg,origin='synthetic test'))
    if kind in ('mixed','endpoint','limit'):
        actions.append(dict(name='P',kind='point',force_xy_N=[scale*70,-scale*280],couple_Nmm=scale*300,
            application_xy_mm=[cg[0]+8,cg[1]-6],s_mm=1500. if kind=='mixed' else 0.,origin='synthetic test'))
    r=solve_member(section=s,length_mm=4000.,E_MPa=200000.,G_MPa=200000/2.6,actions=actions,
        supports={side:dict(twist='fixed',warping='free_assumed',origin='synthetic') for side in ('left','right')},
        combination_id=kind,limit_state='REFERENCE',member_id='P1',action_accounting_origin='complete synthetic set',elements_per_interval=n)
    if kind=='limit':r['support_limit_states']=[support_limit_before_point(r)]
    return r


def envelope(r,**kw):return member_yield_envelope(r,fy_MPa=250.,material_origin='Own nominal material, synthetic case',**kw)


def test_source_is_not_mutated_and_all_approval_flags_stay_false():
    r=member();old=copy.deepcopy(r);z=envelope(r);assert r==old
    assert z['all_requested_field_bounds_converged']
    for key in ('normative_resistance_qualified','physical_design_approved','whole_member_approved','coverage_complete','resistance_factor_applied'):
        assert z[key] is False
    vm=z['stress_envelopes']['von_mises'];f=z['proportional_load_to_nominal_material_yield']
    assert f['lower']<=250/vm['upper_MPa'] and f['upper']>=250/vm['lower_MPa']
    assert json.loads(json.dumps(z,allow_nan=False))==z


def test_zero_has_no_finite_first_yield_and_JSON_is_finite():
    z=envelope(member('zero'))
    assert z['nominal_material_state']=='zero_source_field'
    assert z['proportional_load_to_nominal_material_yield']['lower'] is None
    assert z['proportional_load_to_nominal_material_yield']['upper'] is None
    assert not z['proportional_load_to_nominal_material_yield']['finite']
    json.dumps(z,allow_nan=False)


def test_exact_endpoint_and_support_limit_are_distinct():
    a=envelope(member('endpoint'));b=envelope(member('limit'))
    assert a['stress_envelopes']['von_mises']['lower_MPa']==0.
    assert a['stress_envelopes']['von_mises']['upper_MPa']<1e-7
    assert a['proportional_load_to_nominal_material_yield']['upper'] is None
    assert b['stress_envelopes']['von_mises']['lower_MPa']>1.
    w=b['stress_envelopes']['von_mises']['witness']
    assert w['longitudinal_state']['element_index'] is None
    assert 'before P' in w['longitudinal_state']['position_limit']


def test_proportionality_reversal_and_same_point_witnesses():
    a=envelope(member('mixed'));b=envelope(member('mixed',-2.))
    av=a['stress_envelopes']['von_mises'];bv=b['stress_envelopes']['von_mises']
    assert av['lower_MPa']*2<=bv['upper_MPa'] and bv['lower_MPa']<=av['upper_MPa']*2
    for label,opposite in [('normal_tension','normal_compression'),('normal_compression','normal_tension')]:
        x=a['stress_envelopes'][label];y=b['stress_envelopes'][opposite]
        assert x['lower_MPa']*2<=y['upper_MPa'] and y['lower_MPa']<=x['upper_MPa']*2
    for z in (a,b):
        for r in z['stress_envelopes'].values():
            w=r['witness'];assert w['concomitant'] and 0<=w['section_u']<=1 and 0<=w['polynomial_u']<=1
            assert w['longitudinal_state']['combination_id']=='mixed'
            assert w['saint_venant_face_sign'] in (-1,1)


def test_exhausted_budget_keeps_bounds_and_does_not_claim_convergence():
    p=synthetic_patches([[0]],[[0,0,0],[0,1,-1],[0,-1,1]])
    z=maximize_field(p,'von_mises',relative_tolerance=1e-12,absolute_tolerance_MPa=1e-12,max_subdivisions=0)
    expected=math.sqrt(3)/16
    assert not z['converged'] and z['termination']=='subdivision_budget'
    assert z['lower_MPa']<=expected<=z['upper_MPa']


@pytest.mark.parametrize('field,value',[('fy_MPa',0),('fy_MPa',True),('fy_MPa',float('nan')),('relative_tolerance',1e-14),('max_subdivisions',-1),('max_depth',0)])
def test_invalid_controls_fail_closed(field,value):
    r=member('zero');args=dict(fy_MPa=250.,material_origin='test');args[field]=value
    with pytest.raises((ValueError,FloatingPointError)):member_yield_envelope(r,**args)


def test_unqualified_source_is_not_promoted():
    r=member('zero');r['numerics']['qualification_passed']=False
    with pytest.raises(ValueError,match='qualified'):envelope(r)


def test_reviewed_envelope_runtime_hashes():
    pins = {
        'intervals.py': 'c738ca89326f9fd9198199d6df48197f4fa5c632094d33fe13b62626f08f4168',
        'yield_envelope.py': 'e59a828354acdf97f7f9ca82d278b8ef83a93a5d291c1fe42f2abf94e13cc50d',
        'case_study.py': 'd692443b8f49789dfbade283abc564082b120b6ef037be9e91fc60acc21c606b'}
    for source, digest in pins.items():
        assert hashlib.sha256((ROOT/'tercas/torsion_vlasov'/source).read_bytes()).hexdigest() == digest


def test_selected_case_study_preserves_original_and_never_runs_other_cases():
    from tercas.torsion_vlasov.case_study import study_selected_combination
    from tercas.torsion_vlasov.adapter import load_lines_from_cg,attach_torsion_evidence,summarize_torsion_evidence,fingerprint
    from tercas.ue_family_reference import load_reference, calculate_reference
    source=calculate_reference(load_reference(1.5,4000.,5.))
    s=section();chosen=source['cases'][0]['combination']['id']
    declarations={k:dict(declared=True,xy_from_CG_mm=[0.,0.],origin='Explicit synthetic line') for k in ('CP','SC','V_Cima','V_Baixo','P')}
    source['input_data']['torsion_model']=dict(schema='purlin_vlasov_choice_v1',enabled=True,support_hypothesis='R01_fork_free_warping',load_lines=declarations)
    source['input_fingerprint']=fingerprint(source['input_data'])
    lines=load_lines_from_cg(s,declarations)
    bc={side:dict(twist='fixed',warping='free_assumed',origin='Frozen R01 hypothesis') for side in ('left','right')}
    ev=attach_torsion_evidence(source,section=s,load_lines=lines,supports=bc,elements_per_interval=8)['torsion_evidence']
    source['torsion_evidence']=summarize_torsion_evidence(ev)
    source['torsion_evidence']['choice_snapshot']=copy.deepcopy(source['input_data']['torsion_model'])
    old=copy.deepcopy(source)
    out=study_selected_combination(source,chosen,section=s,load_lines=lines,supports=bc,elements_per_interval=8)
    assert source==old and out['source_combination']==old['cases'][0]['combination']
    assert out['status']=='computed_partial_material_envelope' and out['combination_id']==chosen
    assert out['source_input_fingerprint']==source['input_fingerprint']
    assert not out['normative_resistance_qualified'] and not out['whole_member_approved']
    assert out['material_envelope']['combination_id']==chosen
    assert len(out['case_model_sha256'])==64
    with pytest.raises(ValueError,match='does not exist'):
        study_selected_combination(source,'not an existing case',section=s,load_lines=lines,supports=bc)
    with pytest.raises(ValueError,match='lines differ'):
        study_selected_combination(source,chosen,section=s,load_lines={},supports=bc)
    with pytest.raises(ValueError,match='mesh/section differs'):
        study_selected_combination(source,chosen,section=s,load_lines=lines,supports=bc,elements_per_interval=16)
    assert source==old
