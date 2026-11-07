"""Scalar synthetic shear-lag area-loss proofs; no member solver."""
from fractions import Fraction as F
from decimal import Decimal as D,localcontext
import copy
import math
import pytest
from tercas import en_ue_family_kernel as normal
from tercas import en_ue_family_shear_lag as lag

INDICES=(51,52,58,59,60,67)


def demand(q=.03,P=0.,a=2000.,L=4000.,weak=0.,mesh=False):
    loads=[dict(kind='uniform',q_xy_N_mm=[weak,q])]
    if P:loads.append(dict(kind='point',s_mm=a,force_xy_N=[0.,P]))
    left=[-weak*L/2,-q*L/2];right=left.copy()
    if P:left[1]-=P*(L-a)/L;right[1]-=P*a/L
    xs=sorted({0.,L}|({a} if P else set())|({1000.,2000.,3000.} if mesh else set()))
    elements=[dict(a_mm=x,b_mm=y,element_id='synthetic:e'+str(j+1)) for j,(x,y) in enumerate(zip(xs,xs[1:]))]
    return dict(length_mm=L,loads=loads,elements=elements,
        support_reactions=dict(left_force_xy_N=left,right_force_xy_N=right))


def proof(i=51,**kwargs):
    n=normal.build(i,fyb_MPa=300)
    return lag.build(sourced_demand(n,**kwargs),n,{'axes':{'Mx':{'shear_lag_qualified':False}}}),n


@pytest.mark.parametrize('index',INDICES)
def test_six_sections_are_bounded_without_relocating_area(index):
    p,n=proof(index)
    assert p['eligible'] and p['Ix_lower_mm4']>0
    assert not p['exact_effective_tensor_claimed'] and not p['exact_physical_stress_distribution_claimed']
    assert not p['whole_member_approved'] and not p['physical_exceedance_witness_permitted']
    assert set(p['signed_capacity_floor'])=={'Mx_positive','Mx_negative'}
    assert p['moment_capacity_floor_Nmm']<n['signed_capacity_floor']['Mx_positive']
    assert p['beta_global_lower']<1
    for audit in p['local_distortional_audit'].values():
        assert all(x['rho']==1 for x in audit['local_panels'])
        st=audit['stiffener']
        assert st['sigma_As_upper_MPa']<=st['chi_d_fyb_lower_MPa']
        assert st['As_red_over_As_proved']==1
    for bounds in p['operator_intervals'].values():
        assert bounds[1]==[0.,0.] and bounds[2][0]==0
        assert bounds[2][1]>=1/p['Ix_lower_mm4']


def test_physical_zeros_not_mesh_or_point_splits_and_sign_inversion():
    base,_=proof(P=20.)
    split,_=proof(P=20.,mesh=True)
    reverse,_=proof(P=-20.,q=-.03)
    assert base['eligible'] and split['eligible'] and reverse['eligible']
    assert len(base['physical_zero_zones'])==1
    assert base['physical_zero_zones']==split['physical_zero_zones']==reverse['physical_zero_zones']
    assert base['Ix_lower_mm4']==split['Ix_lower_mm4']==reverse['Ix_lower_mm4']
    changed,_=proof(P=-90.)
    assert changed['eligible'] and len(changed['physical_zero_zones'])==3
    assert [z['Le_mm'] for z in changed['physical_zero_zones']]==pytest.approx([1000,2000,1000])
    assert changed['moment_capacity_floor_Nmm']<base['moment_capacity_floor_Nmm']


def test_fraction_zero_lengths_are_converted_outward():
    p,_=proof(q=.031,P=-80.321,a=1234.567)
    assert p['eligible']
    for z in p['physical_zero_zones']:
        exact=F(*z['Le_exact'])
        assert F(z['Le_lower_mm'])<=exact


def test_beta_envelope_covers_point_seven_upward_formula_jump():
    p=lag._beta_lower(.70001)
    with localcontext() as ctx:
        ctx.prec=60;k=D('.7')
        exact=(D('.55')+D('.025')/k)/(1+D('6.4')*k*k)
        assert D.from_float(p['beta_lower'])<=exact
        assert p['kappa_point_seven_left_limit_lower'] is not None
    for upper in (.020001,.1,.7,.70001,1.,4.):
        p=lag._beta_lower(upper)
        for k in (.02,.020001,.05,.2,.699999,.7,.700001,upper):
            if k>upper:continue
            with localcontext() as ctx:
                ctx.prec=60;x=D.from_float(k)
                if x<=D('.02'):expected=D(1)
                else:
                    b1=1/(1+D('6.4')*x*x) if x<=D('.7') else 1/(D('5.9')*x)
                    b2=1/(1+6*(x-1/(2500*x))+D('1.6')*x*x) if x<=D('.7') else 1/(D('8.6')*x)
                    b0=min(b1,(D('.55')+D('.025')/x)*b1)
                    expected=min(b0,b1,b2)
                assert D.from_float(p['beta_lower'])<=expected


@pytest.mark.parametrize('index',INDICES)
def test_decimal_inertia_loss_and_integer_capacity_are_independent(index):
    p,n=proof(index)
    with localcontext() as ctx:
        ctx.prec=60;t=D.from_float(n['thickness_mm']);h=D(n['nominal_identity']['dimensions_mm']['h'])
        center=(h-t)/2;ix=D(0);areas=[D(0),D(0)]
        for aa,bb in zip(n['nodes_xy_mm'],n['nodes_xy_mm'][1:]):
            a,b=[[D.from_float(v) for v in point] for point in (aa,bb)]
            area=t*((b[0]-a[0])**2+(b[1]-a[1])**2).sqrt()
            u,v=a[1]-center,b[1]-center
            ix+=area*(u*u+u*v+v*v)/3
            if a[0]==b[0]==0:continue
            areas[0 if (a[1]+b[1])/2<center else 1]+=area
        assert D.from_float(p['geometry_audit']['Ix_gross_interval_mm4'][0])<=ix<=D.from_float(p['geometry_audit']['Ix_gross_interval_mm4'][1])
        beta=D.from_float(p['beta_global_lower'])
        candidate=ix-2*(1-beta)*max(areas)*(h/2)**2
        assert D.from_float(p['Ix_lower_mm4'])<=candidate
        assert D(p['moment_capacity_floor_Nmm'])<=D(300)*candidate/(h/2)


@pytest.mark.parametrize('kwargs,reason',[({'weak':.001},'independent My')])
def test_uncovered_domain_stays_pending(kwargs,reason):
    p,_=proof(**kwargs)
    assert not p['eligible'] and reason in p['blocking_reasons'][0]['detail']
    assert not p['blocking_reasons'][0]['normative_rejection_inferred']


def sourced_demand(n,**kwargs):
    d=demand(**kwargs)
    d['section']=dict(nodes_sha256=n['nodes_sha256'],properties=copy.deepcopy(n['gross_properties']))
    return d


@pytest.mark.parametrize('weak',[.001,-.001])
def test_nonzero_my_uses_independent_source_dispensation_and_unchanged_operators(weak):
    from tercas.en_ue_family_applicability import assess
    n=normal.build(51,fyb_MPa=300);before=copy.deepcopy(n)
    d=sourced_demand(n,L=6000.,a=3000.,P=-135.,weak=weak)
    applicable=assess(d,n)
    assert not applicable['axes']['Mx']['shear_lag_qualified']
    assert applicable['axes']['My']['qualified']
    assert len(applicable['axes']['Mx']['zero_zones'])==3
    assert len(applicable['axes']['My']['zero_zones'])==1
    p=lag.build(d,n,applicable)
    assert p['eligible'] and set(p['operator_intervals'])=={'Mx_positive','Mx_negative'}
    assert set(p['signed_capacity_floor'])=={'Mx_positive','Mx_negative'}
    assert p['independent_My_companion']['applicability']==applicable['axes']['My']
    assert not p['independent_My_companion']['shared_effective_tensor_claimed']
    qualified=lag.apply_applicability(applicable,p)
    assert qualified['qualified'] and qualified['axes']['My']==applicable['axes']['My']
    pure=sourced_demand(n,L=6000.,a=3000.,P=-135.)
    pure_proof=lag.build(pure,n,assess(pure,n))
    for key in ('Ix_lower_mm4','operator_intervals','signed_capacity_floor','local_distortional_audit'):
        assert p[key]==pure_proof[key]
    assert n==before


def test_concomitant_my_flags_cannot_replace_actual_source_dispensation():
    from tercas.en_ue_family_applicability import assess
    n=normal.build(51,fyb_MPa=300)
    d=sourced_demand(n,weak=.001)
    supplied=assess(d,n)
    assert not supplied['axes']['My']['shear_lag_qualified']
    supplied['axes']['My'].update(shear_lag_qualified=True,curling_qualified=True,qualified=True)
    p=lag.build(d,n,supplied)
    assert not p['eligible'] and 'independent My' in p['blocking_reasons'][0]['detail']


def test_concomitant_my_curling_remains_required(monkeypatch):
    n=normal.build(51,fyb_MPa=300)
    d=sourced_demand(n,L=6000.,a=3000.,P=-135.,weak=.001)
    source_assess=lag.assess
    def curled(*args):
        out=source_assess(*args)
        out['axes']['My'].update(curling_qualified=False,qualified=False)
        return out
    monkeypatch.setattr(lag,'assess',curled)
    p=lag.build(d,n,{'axes':{'Mx':{'shear_lag_qualified':False}}})
    assert not p['eligible'] and 'curling' in p['blocking_reasons'][0]['detail']


def test_concomitant_my_cannot_supply_missing_signed_operator():
    n=normal.build(51,fyb_MPa=300)
    d=sourced_demand(n,L=6000.,a=3000.,P=-135.,weak=.001)
    n['components']['My_positive']['eligible']=False
    p=lag.build(d,n,{'axes':{'Mx':{'shear_lag_qualified':False}}})
    assert not p['eligible'] and 'eligible unchanged' in p['blocking_reasons'][0]['detail']


def test_reduced_local_section_and_r10_are_not_silently_promoted():
    p,_=proof(19)
    assert not p['eligible'] and 'integral' in p['blocking_reasons'][0]['detail']
    from tercas._en_ue_family_r10.en_ue_family_kernel import build
    n=build(51,fyb_MPa=300);before=copy.deepcopy(n)
    p=lag.build(demand(),n,{'axes':{'Mx':{'shear_lag_qualified':False}}})
    assert not p['eligible'] and 'Historical R10' in p['blocking_reasons'][0]['detail']
    assert n==before


def test_nonpositive_inertia_bound_is_not_promoted(monkeypatch):
    original=lag._inertia_and_area
    def insufficient(n):
        ix,area,center,audit=original(n)
        return lag.I(1),area,center,audit
    monkeypatch.setattr(lag,'_inertia_and_area',insufficient)
    p,_=proof()
    assert not p['eligible'] and 'nonpositive' in p['blocking_reasons'][0]['detail']


def test_short_physical_zone_uses_equations_not_arbitrary_length_guard():
    p,_=proof(L=50.,a=25.)
    assert p['eligible'] and p['moment_capacity_floor_Nmm']>0
    assert p['beta_global_lower']<.1
