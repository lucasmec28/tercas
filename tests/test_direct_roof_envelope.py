"""Direct scalar height envelope: sign proof, no guessed PP/torque, saved limits."""
import copy
import math
import pytest
from tercas import direct_roof_envelope as direct,roof_top_load as roof,roof_top_nbr as nbr
from tercas import ue_family_reference as family,ue_reference as single
from tercas.application import example,calculate
from tercas.core.flt_vrd import flt_mse
from tercas.ltb_load_height import solve
from tercas.study_completion import complete_result

PARAM=dict(L_mm=4000.,E_MPa=200000.,G_MPa=77000.,Iweak_mm4=160000.,J_mm4=700.,Cw_mm6=4e8,modes=32)


def uniform(name,q,h):
    return dict(name=name,kind='uniform',q_down_N_mm=q,height_above_SC_mm=h,x_from_SC_mm=None)


def point(P):
    return dict(name='P',kind='point',P_down_N=P,s_mm=1500.,height_above_SC_mm=50.,x_from_SC_mm=None)


@pytest.mark.parametrize('q',[-2.,-.1,0.,.1,2.])
@pytest.mark.parametrize('pp',[0.,.1,3.])
@pytest.mark.parametrize('P',[-1000.,0.,1000.])
def test_same_ritz_space_first_positive_factor_orders_for_all_net_signs(q,pp,P):
    env=solve(**PARAM,actions=[uniform('total',q,50.),point(P)])
    actual=solve(**PARAM,actions=[uniform('roof',q-pp,50.),uniform('PP',pp,0.),point(P)])
    assert math.isclose(env['maximum_reference_moment_Nmm'],actual['maximum_reference_moment_Nmm'],abs_tol=1e-8)
    if env['lambda_cr'] is None:
        assert actual['lambda_cr'] is None
    elif actual['lambda_cr'] is not None:
        assert env['lambda_cr']<=actual['lambda_cr']*(1+3e-13)
        if env['Me_Nmm'] is not None:assert env['Me_Nmm']<=actual['Me_Nmm']*(1+3e-13)


def test_negative_PP_counterexample_and_torque_cancellation_are_not_covered():
    env=solve(**PARAM,actions=[uniform('total',1.,50.)])
    actual=solve(**PARAM,actions=[uniform('roof',2.,50.),uniform('PP',-1.,0.)])
    assert env['Me_Nmm']>actual['Me_Nmm']
    # A zero net q can still carry torque: top and CG have different x offsets.
    qpp=.5;qroof=-.5;etop=25.;ecg=42.
    assert qpp+qroof==0 and -etop*qroof-ecg*qpp!=0
    assert 'descendente ou nula' in direct.ASSUMPTIONS['self_weight']


@pytest.mark.parametrize('Ml',[1e5,1e6,1e8])
@pytest.mark.parametrize('lam',[.2,.6,1.,1.334,1.3359,1.336,1.337,1.5,3.,10.])
def test_resistance_floor_covers_existing_rounded_curve_for_every_higher_Me(Ml,lam):
    A=10000.*250.;Me=A/lam**2
    lower=direct.nbr_resistance_floor(10000.,250.,Ml,Me)
    for factor in [1.,1.00001,1.001,1.01,1.1,2.,10.,100.]:
        assert lower['MRd_flt_Nmm']<=flt_mse(10000.,250.,Ml,Me*factor)['MRd_flt_Nmm']*(1+2e-15)
    for boundary in [.6,1.336]:
        for value in [boundary,math.nextafter(boundary,0.),math.nextafter(boundary,math.inf)]:
            other=A/value**2
            if other>=Me:assert lower['MRd_flt_Nmm']<=flt_mse(10000.,250.,Ml,other)['MRd_flt_Nmm']*(1+2e-15)


def test_rounding_jump_is_real_and_corrected_only_by_new_floor():
    W,Fy,Ml=10000.,250.,1e8;Me=W*Fy/1.336**2
    raw=flt_mse(W,Fy,Ml,Me);after=flt_mse(W,Fy,Ml,Me*(1+1e-12))
    assert raw['MRd_flt_Nmm']>after['MRd_flt_Nmm']
    lower=direct.nbr_resistance_floor(W,Fy,Ml,Me)
    assert lower['lower_envelope']['transition_correction_applied']
    assert lower['lower_envelope']['original_formula']==raw
    assert lower['MRd_flt_Nmm']<=after['MRd_flt_Nmm']
    assert flt_mse(W,Fy,Ml,Me)==raw


def own(t=2.,q=.1,P=100.,angle=0.):
    d=single.load_reference(angle=angle) if t==1.2 else family.load_reference(t,4000.,angle)
    d.update(load_mode='direct',roof_top_load=roof.choice(),q_uls=q,P_uls=P,q_sls=-.1,P_sls=-100.)
    return d


def run(d):
    return complete_result(single.calculate_reference(d) if single.claims_reference(d) else family.calculate_reference(d))


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_own_direct_has_me_and_conditional_nbr_without_new_inputs_or_torsion(t):
    d=own(t);before=copy.deepcopy(d);out=run(d)
    assert d==before and out['input_data']==d
    ev=roof.preserved(out);n=nbr.preserved(out)
    assert ev['schema']==direct.SCHEMA and ev['computed_cases']==2
    assert n['computed_cases']==1 and n['ignored_ELS_cases']==1
    assert n['records'][0]['resistance_is_lower_envelope']
    assert out['torsion_evidence']['computed_cases']==0
    assert out['aisi_torsion_component']['H4_computed_cases']==0
    assert out['whole_member_approved'] is False and out['global_verification']['whole_member_approved'] is False
    assert all(t['value'] is None for r in ev['records'] for t in r['primary_torque_by_action'])
    nbr.validate_saved_global(out)


def test_inclination_does_not_rotate_local_direct_input_but_parallel_is_not_erased():
    flat=run(own(angle=0.));inclined=run(own(angle=5.))
    assert [r['Me_Nmm'] for r in flat['roof_top_load_evidence']['records']]==[r['Me_Nmm'] for r in inclined['roof_top_load_evidence']['records']]
    d=own(angle=5.);d['q_parallel_uls']=.01;out=run(d)
    assert out['roof_top_load_evidence']['records'][0]['status']=='pending_biaxial_model'
    assert out['roof_top_load_evidence']['records'][1]['Me_Nmm']>0
    assert out[nbr.FIELD]['computed_cases']==0


def test_no_mass_or_PP_factor_is_invented_and_no_input_areas_used():
    d=example();d['roof_top_load']=roof.choice();a=roof.attach(calculate(d))
    changed=copy.deepcopy(d);changed['properties']['mass_kg_m']*=3
    changed['area_inputs']['permanent_kgf_m2']=800.
    b=roof.attach(calculate(changed))
    assert a['roof_top_load_evidence']['records']==b['roof_top_load_evidence']['records']
    assert not a['roof_top_load_evidence']['self_weight_quantity_assumed']


def test_lower_bound_above_one_is_pending_not_false_failure_in_global_or_UI():
    out=run(own(q=20.,P=10000.));r=nbr.preserved(out)['records'][0]
    assert r['index']>1 and r['criterion_status']=='inconclusive'
    flt=next(c for c in out['global_verification']['checks'] if c['id'].endswith(':FLT_height'))
    assert flt['status']=='pending' and flt['diagnostic_index']==r['index']
    from tercas.roof_top_nbr_ui import summary_rows
    assert 'inconclusiva' in summary_rows(out[nbr.FIELD])[0]['Situação']


def test_saved_direct_no_solver_and_stale_input_or_mode_rejected(monkeypatch):
    out=run(own());before=copy.deepcopy(out)
    def fail(*a,**k):raise AssertionError('unexpected new solve')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(direct,'nbr_resistance_floor',fail)
    assert roof.preserved(out) and nbr.preserved(out)
    nbr.validate_saved_global(out);assert out==before
    for change in ('input','scope','Me','approval','torque'):
        r=copy.deepcopy(out);e=r['roof_top_load_evidence']
        if change=='input':r['input_data']['q_uls']+=1
        if change=='scope':e['direct_envelope_assumptions']['self_weight']='anything'
        if change=='Me':e['records'][0]['Me_Nmm']*=2
        if change=='approval':e['whole_member_approved']=True
        if change=='torque':e['records'][0]['primary_torque_by_action'][0]['value']=0.
        with pytest.raises(ValueError):roof.preserved(r)


def test_historical_v1_direct_pending_stays_pending_without_recalculation():
    d=own();raw=family.calculate_reference(d)
    old=roof._save(copy.deepcopy(raw),roof._pending(raw,roof.configuration(d),'Historical direct decomposition unavailable'))
    before=copy.deepcopy(old)
    assert roof.preserved(old)['schema']=='roof_top_load_evidence_v1'
    assert roof.preserved(old)['records']==[] and roof.combination_inventory(old)==[]
    assert old==before


def test_local_rounded_transition_is_capped_only_in_new_envelope():
    W,Fy,Me=1.,1.,.4;Ml=.4/.67301**2
    raw=flt_mse(W,Fy,Ml,Me);assert raw['Wceff_mm3']>W
    lower=direct.nbr_resistance_floor(W,Fy,Ml,Me)
    assert lower['Wceff_mm3']==W
    assert lower['MRd_flt_Nmm']<raw['MRd_flt_Nmm']
    assert lower['lower_envelope']['local_rounding_gross_cap_applied']
    assert flt_mse(W,Fy,Ml,Me)==raw


def test_saved_actual_direct_word_report_does_not_recompute(monkeypatch):
    from docx import Document
    from tercas.roof_top_load_ui import report
    out=run(own(q=20.,P=10000.));before=copy.deepcopy(out)
    def fail(*a,**k):raise AssertionError('Read-only report recalculated')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(direct,'nbr_resistance_floor',fail)
    doc=Document();report(doc,out);text='\n'.join(p.text for p in doc.paragraphs)
    assert 'não quantificado nem adicionado' in text
    assert 'Envoltória inconclusiva' in text
    assert out==before
