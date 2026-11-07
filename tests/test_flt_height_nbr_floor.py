"""Independent scalar/interval checks for the sufficient resistance bridge."""
import copy
from fractions import Fraction
import json
import math
import pytest
from tercas import flt_height_nbr_floor as bridge
from tercas import flt_height_energy_floor as energy
from tercas import nbr_ue_family as provider
from tercas import nbr_ue_family_expansion as mle
from tercas import pierin_ue_registry as registry
from tercas.core.flt_vrd import chi_flt
from tercas.ue_catalog_reference import digest
from test_flt_height_effective import data,actions,uniform,point


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_bridge_family66_and_exact_replay(index):
    d=data(index,ly=2050.,lz=2733.);a=actions(d)+[point(P=150.,h=35.,x=1410.)]
    before=copy.deepcopy((d,a));result=bridge.qualify_family(d,a)
    assert result['resistance_floor_eligible']
    assert result['MRd_lower_bound_Nmm']>0
    assert result['status'] in ('sufficient_under_declared_operator','inconclusive_floor_exceeded')
    assert result['component_sufficient']==(result['utilization_upper_bound']<=1.)
    assert not result['failure_proven'] and not result['actual_load_capacity_qualified']
    assert not result['physical_supports_created'] and not result['whole_member_approved']
    assert result['physical_span_mm']==4100.
    cap=result['resistance_floor']
    assert cap['method'].startswith('MLE_' if index in (79,80,81,82) else 'T12b_')
    assert not cap['distortional_resistance_included']
    assert bridge.validate_saved(json.loads(json.dumps(result)),d,a)==result
    assert (d,a)==before


@pytest.mark.parametrize('index',(79,80,81,82))
@pytest.mark.parametrize('fy',(250.,300.,345.,350.))
def test_mle_uniform_proof_and_independent_stress_interval_sweep(index,fy):
    p,props=provider._geometry(index);m=dict(provider.DEFAULT_MATERIAL,fy_MPa=fy)
    lower,proof=bridge.mle_uniform_modulus_floor(p,props,m)
    assert proof['web_full_for_entire_stress_interval']
    assert proof['retained_y_measure_dominated_by_every_effective_y_measure']
    assert not proof['spatial_flange_subset_or_tensor_claimed']
    q={k:Fraction(v) for k,v in proof['exact_bounds'].items()}
    assert q['centroid_lower']<=q['centroid_upper']
    assert q['web_lambda_upper']<=Fraction('0.673') or q['web_partition_lower']>=q['web_compressed_width_upper']
    # Secondary check, not the proof: a nonuniform grid includes small stresses
    # and the stress endpoints; the algebra covers the unsampled continuum.
    for x in [1e-9,1e-5,.001]+[i/60 for i in range(1,61)]:
        sec=mle.strong_effective_modulus(p,props,m,x*fy)
        edge=sec['edge_stiffener']
        assert sec['Wc_mm3']>=float(lower)*(1-3e-15)
        assert edge['flange_effective_width_mm']>=float(q['flange_width_lower'])*(1-3e-15)
        assert edge['reduced_lip_width_mm']>=float(q['lip_width_lower'])*(1-3e-15)
        assert sec['centroid_y_mm']>=float(q['centroid_lower'])-2e-12
        assert sec['centroid_y_mm']<=float(q['centroid_upper'])+2e-12
        assert sec['web_proof']['fully_effective']


def test_retained_core_moments_independent_decimal():
    from decimal import Decimal,localcontext
    p,props=provider._geometry(79);m=dict(provider.DEFAULT_MATERIAL,fy_MPa=350.)
    lower,proof=bridge.mle_uniform_modulus_floor(p,props,m)
    with localcontext() as c:
        c.prec=100
        D=lambda v:Decimal.from_float(float(v))
        F=lambda key:Decimal(Fraction(proof['exact_bounds'][key]).numerator)/Decimal(Fraction(proof['exact_bounds'][key]).denominator)
        t,ri,h,lip,bf=map(D,(p['t'],p['ri_mm'],p['h'],p['lip'],p['bf']))
        a=h-t;r=ri+t/2;b=bf-2*(ri+t);d=lip-ri-t
        area_flange=(b-F('flange_width_lower'))*t
        y0=a-r-d;y1=a-r-F('lip_width_lower');area_lip=t*(y1-y0)
        A=D(props['A_mm2'])-area_flange-area_lip
        Sy=D(props['A_mm2'])*D(props['centroid_xy_mm'][1])-area_flange*a-area_lip*(y0+y1)/2
        Qy=D(props['Ix_strong_mm4'])+D(props['A_mm2'])*D(props['centroid_xy_mm'][1])**2-area_flange*a*a-area_lip*(y0*y0+y0*y1+y1*y1)/3
        expected=(Qy-Sy*Sy/A)/(a+t/2-Sy/A)
    assert float(lower)==pytest.approx(float(expected),rel=2e-15)


@pytest.mark.parametrize('lam',(0.1,.599999999,.6,.600000001,1.,1.335999999,1.336,1.336000001,2.,30.))
def test_chi_envelope_includes_both_rounded_transitions(lam):
    W,fy=12345.,300.;me=W*fy/lam**2
    chi,proof=bridge.chi_envelope(W,fy,me)
    assert not proof['monotonic_raw_rounded_curve_assumed']
    for x in [0.,.6,math.nextafter(.6,math.inf),math.nextafter(1.336,0.),1.336,lam]+[lam*i/500 for i in range(501)]:
        if x<=lam:
            actual=chi_flt(x)[0]
            assert float(chi)<=actual+3e-15


@pytest.mark.parametrize('index',(26,79))
@pytest.mark.parametrize('lam',(0.5999,.6,.6001,1.3359,1.336,1.3361,2.,10.))
def test_capacity_floor_below_actual_curve_for_every_larger_Me_sample(index,lam):
    p,props=provider._geometry(index);m=dict(provider.DEFAULT_MATERIAL)
    W=props['Ix_strong_mm4']/(p['h']/2);me=W*m['fy_MPa']/lam**2
    cap=bridge.resistance_at_floor(index,material=m,Me_lower_bound_Nmm=me)
    f=cap['MRd_lower_bound_Nmm']
    for factor in (1.,1.00000001,1.1,2.,10.,1e6):
        actual=provider.strong_capacity_at_me(index,material=m,Me_Nmm=me*factor)
        assert f<=actual['MRd_Nmm']*(1+3e-15)
    assert Fraction.from_float(f)<=Fraction(cap['exact_MRd_floor_fraction'])


def test_actual_gamma_used_instead_of_helper_fixed_gamma():
    m=dict(provider.DEFAULT_MATERIAL);a=bridge.resistance_at_floor(26,material=m,Me_lower_bound_Nmm=2e6)
    b=bridge.resistance_at_floor(26,material=dict(m,gamma=1.35),Me_lower_bound_Nmm=2e6)
    assert b['MRd_lower_bound_Nmm']==pytest.approx(a['MRd_lower_bound_Nmm']*1.1/1.35,rel=5e-15)


def test_floor_exceeded_is_inconclusive_not_failure_and_scaling_preserves_capacity():
    d=data();a=[uniform(.001,60.),point(P=.01,h=35.,x=1410.)]
    low=bridge.qualify_family(d,a)
    high=bridge.qualify_family(d,[uniform(100.,60.),point(P=1000.,h=35.,x=1410.)])
    assert low['component_sufficient'] and not low['failure_proven']
    assert not high['component_sufficient'] and not high['failure_proven']
    assert high['status']=='inconclusive_floor_exceeded'
    assert high['MRd_lower_bound_Nmm']==pytest.approx(low['MRd_lower_bound_Nmm'])


def test_zero_bending_rotational_energy_not_promoted_to_resistance():
    d=data();a=[uniform(1.,60.),uniform(-1.,0.,'other')]
    r=bridge.qualify_family(d,a)
    assert not r['resistance_floor_eligible']
    assert r['MRd_lower_bound_Nmm'] is None and r['utilization_upper_bound'] is None
    assert not r['component_sufficient'] and not r['failure_proven']


def test_exact_demand_is_used_even_when_report_rounds():
    d=data();a=[uniform(1e16,0.),uniform(-1e16+2.,0.,'cancel')]
    r=bridge.qualify_family(d,a)
    assert Fraction(r['demand_exact_fraction'])==Fraction(4100**2,4)
    assert Fraction.from_float(r['utilization_upper_bound'])>=Fraction(r['demand_exact_fraction'])/Fraction.from_float(r['MRd_lower_bound_Nmm'])


def test_precomputed_energy_and_resistance_forgery_rejected_after_rehash():
    d=data();a=actions(d)+[point(x=900.)];e=energy.qualify_family(d,a)
    expected=bridge.qualify_family(d,a)
    assert bridge.qualify_family(d,a,energy_evidence=e)==expected
    bad=copy.deepcopy(e);bad['Me_lower_bound_Nmm']*=2
    bad['snapshot_sha256']=digest({k:v for k,v in bad.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):bridge.qualify_family(d,a,energy_evidence=bad)
    for field in ('MRd_lower_bound_Nmm','utilization_upper_bound'):
        r=copy.deepcopy(expected);r[field]*=2
        r['snapshot_sha256']=digest({k:v for k,v in r.items() if k!='snapshot_sha256'})
        with pytest.raises(ValueError):bridge.validate_saved(r,d,a)
    r=copy.deepcopy(expected);r['energy_hypotheses']['physical_realization_verified']=True
    with pytest.raises(ValueError):bridge.validate_saved(r,d,a)


def test_uniform_proof_fails_closed_for_outside_geometry_or_unproved_web():
    p,props=provider._geometry(79);m=dict(provider.DEFAULT_MATERIAL)
    with pytest.raises(mle.OutsideMethod):bridge.mle_uniform_modulus_floor(dict(p,lip=70),props,m)
    with pytest.raises(mle.OutsideMethod):bridge.mle_uniform_modulus_floor(p,props,dict(m,fy_MPa=10000.))


def test_underflowed_output_fails_closed_before_utilization(monkeypatch):
    monkeypatch.setattr(energy,'_directed',lambda value,upward:0.)
    with pytest.raises(mle.OutsideMethod,match='underflows'):
        bridge.resistance_at_floor(26,material=provider.DEFAULT_MATERIAL,Me_lower_bound_Nmm=2e6)
