"""Original-energy checks on synthetic inputs, no member eigensolver."""
import copy
import math
from decimal import Decimal, localcontext
import numpy as np
import pytest
from tercas import flt_height_energy_floor as floor, flt_height_nbr_floor as nbr
from tercas import pierin_ue_registry as registry
from test_flt_height_effective import data, uniform, point
from test_flt_energy_moment_product import P, A


def solve(actions=A, **kw):
    return floor.solve_floor(**dict(dict(P, Ly_mm=3600.), **kw), actions=actions, method=floor.POLICY_V3)


def test_direct_reference_without_height_matches_uniform_moment_floor():
    r=solve([uniform(.5,0.), point(P=300.,h=0.,x=1300.)])
    with localcontext() as ctx:
        ctx.prec=60
        pi=Decimal('3.14159265358979323846264338327950288419716939937510')
        T=Decimal(P['G_MPa'])*Decimal(P['J_mm4'])+Decimal(P['E_MPa'])*Decimal(P['Cw_mm6'])*(pi/Decimal(P['Lz_mm']))**2
        expected=pi/Decimal(P['L_mm'])*(Decimal(P['E_MPa'])*Decimal(P['Iweak_mm4'])*T).sqrt()
        assert Decimal(r['Me_lower_bound_Nmm'])<=expected
        assert float(expected)==pytest.approx(r['Me_lower_bound_Nmm'],rel=2e-15)
    assert r['direct_curvature_bound']['selected']=='direct_curvature'


@pytest.mark.parametrize('ly',[1800.,2400.,3600.,4500.])
def test_never_weaker_and_no_fictitious_length_benefit(ly):
    params=dict(P,Ly_mm=ly)
    old=floor.solve_floor(**params,actions=A,method=floor.POLICY_V2)
    new=floor.solve_floor(**params,actions=A,method=floor.POLICY_V3)
    assert new['lambda_lower_bound']>=old['lambda_lower_bound']
    for k in ('D_upper_Nmm2','maximum_reference_moment_Nmm','physical_span_mm'):
        assert new[k]==old[k]
    assert not new['physical_supports_created']
    assert not new['historical_physical_solver_lower_bound_claimed']
    assert not new['demand_span_changed']


@pytest.mark.parametrize('seed',range(12))
@pytest.mark.parametrize('lz_factor',[1.,.5])
def test_original_energy_independently_integrated(seed,lz_factor):
    # Explicit free-warping OR clamped trial fields prove the admitted energy
    # inequality in this synthetic test, never by inferring user supports.
    rng=np.random.default_rng(seed);L=3600.; q=.57; force=320.;a=1300.;h=55.
    acts=[uniform(q,h),point(P=force,h=42.,x=a)]
    r=solve(acts,Lz_mm=L*lz_factor)
    n=np.arange(1,7); k=n*math.pi/L
    cu=rng.normal(size=6); cp=rng.normal(size=6)
    nodes,weights=np.polynomial.legendre.leggauss(80)
    lateral=twist=coupling=height=0.
    for lo,hi in [(0.,a),(a,L)]:
        x=(lo+hi)/2+(hi-lo)*nodes/2;w=weights*(hi-lo)/2
        sine=np.sin(k[:,None]*x);cos=np.cos(k[:,None]*x)
        udd=(-cu*k*k)@sine
        if lz_factor==1.:
            phi=cp@sine;pd=(cp*k)@cos;pdd=(-cp*k*k)@sine
        else:
            # Independent clamped-twist trial space, explicitly selected for
            # this mathematical check, NEVER inferred from user Leff.
            kp=2*k;phi=cp@(1-np.cos(kp[:,None]*x))
            pd=(cp*kp)@np.sin(kp[:,None]*x)
            pdd=(cp*kp*kp)@np.cos(kp[:,None]*x)
        M=q*x*(L-x)/2+force*np.minimum((L-a)*x/L,a*(L-x)/L)
        lateral+=P['E_MPa']*P['Iweak_mm4']*sum(w*udd**2)
        twist+=sum(w*(P['G_MPa']*P['J_mm4']*pd**2+P['E_MPa']*P['Cw_mm6']*pdd**2))
        coupling+=sum(w*M*udd*phi)
        height+=q*h*sum(w*phi**2)
    phi_a=cp@np.sin(k*a) if lz_factor==1. else cp@(1-np.cos(2*k*a))
    height+=force*42.*float(phi_a)**2
    lam=r['lambda_lower_bound']
    # Minimize over ALL amplitudes of the chosen lateral trial, not merely one.
    assert twist-lam*height-lam**2*coupling**2/lateral>=-1e-12*twist


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_family_bridge_versions_and_improvement(index):
    d=data(index,ly=3600.,lz=2400.);d['L_mm']=3600.
    before=copy.deepcopy((d,A))
    old=nbr.qualify_family(d,A,method=floor.POLICY_V2)
    new=nbr.qualify_family(d,A,method=floor.POLICY_V3)
    assert new['schema']=='flt_height_declared_energy_nbr_floor_v3'
    assert new['MRd_lower_bound_Nmm']>=old['MRd_lower_bound_Nmm']
    assert nbr.validate_saved(old,d,A)==old
    assert nbr.validate_saved(new,d,A)==new
    assert (d,A)==before
    assert not new['failure_proven'] and not new['whole_member_approved']


def test_current_dispatch_and_historical_v5(monkeypatch):
    from test_nbr_family_height_integration import source
    from tercas import nbr_ue_family_application as app, ue_catalog_reference as own
    from tercas.application import fingerprint
    from tercas import ltb_load_height
    r=source(0,Leff=2400.)
    r['input_data'].update(L_mm=3600.,q_uls=.32,P_uls=240.,x_uls=1800.)
    r['input_fingerprint']=fingerprint(r['input_data']);r=own.attach_source(r)
    monkeypatch.setattr(ltb_load_height,'refined',lambda *a,**k:pytest.fail('No Ritz'))
    old=copy.deepcopy(r);old[app.FIELD]=app._build(r,legacy_product_floor=True)
    assert old[app.FIELD]['schema']==app.LEGACY_SCHEMA_V5
    assert app.preserved(old)==old[app.FIELD]
    new=app.attach(r)
    assert app.preserved(new)==new[app.FIELD]
    assert new[app.FIELD]['schema']==app.SCHEMA


def test_closes_actual_sufficient_case_previously_inconclusive():
    d=data(0,ly=3600.,lz=2400.);d['L_mm']=3600.
    old=nbr.qualify_family(d,A,method=floor.POLICY_V2)
    new=nbr.qualify_family(d,A,method=floor.POLICY_V3)
    assert new['MRd_lower_bound_Nmm']>old['MRd_lower_bound_Nmm']*1.05
    target=(new['MRd_lower_bound_Nmm']+old['MRd_lower_bound_Nmm'])/2
    scale=target/old['maximum_reference_moment_Nmm']
    acts=copy.deepcopy(A)
    for a in acts:
        key='q_down_N_mm' if a['kind']=='uniform' else 'P_down_N'
        a[key]*=scale
    old=nbr.qualify_family(d,acts,method=floor.POLICY_V2)
    new=nbr.qualify_family(d,acts,method=floor.POLICY_V3)
    assert old['status']=='inconclusive_floor_exceeded'
    assert new['status']=='sufficient_under_declared_operator'
    from tercas.flt_height_effective import qualify_family_fresh
    assert not qualify_family_fresh(d,acts)['elastic_reference_eligible']
    assert not new['failure_proven'] and not new['whole_member_approved']


@pytest.mark.parametrize('version',[None,floor.POLICY_V2])
def test_supplied_other_version_rejected(version):
    d=data(0,ly=3600.,lz=2400.);d['L_mm']=3600.
    evidence=floor.qualify_family(d,A,method=version)
    with pytest.raises(ValueError,match='differs from requested method'):
        nbr.qualify_family(d,A,method=floor.POLICY_V3,energy_evidence=evidence)


def test_direct_selected_cancels_ly_and_short_ly_preserves_v2():
    outs=[floor.solve_floor(**dict(P,Ly_mm=ly),actions=A,method=floor.POLICY_V3) for ly in (3600.,4500.)]
    assert all(x['direct_curvature_bound']['selected']=='direct_curvature' for x in outs)
    assert outs[0]['Me_lower_bound_Nmm']==pytest.approx(outs[1]['Me_lower_bound_Nmm'],rel=1e-15)
    old=floor.solve_floor(**P,actions=A,method=floor.POLICY_V2)
    new=floor.solve_floor(**P,actions=A,method=floor.POLICY_V3)
    assert new['direct_curvature_bound']['selected']=='moment_product'
    assert new['Me_lower_bound_Nmm']==old['Me_lower_bound_Nmm']


@pytest.mark.parametrize('acts',[
    [uniform(.7,-40.),point(P=-400.,h=20.,x=700.)],
    [uniform(1.,50.),uniform(-1.,0.,'cancel')],
    [point(P=1e12,h=1e12,x=0.),point(P=-1e12,h=1e12,x=3600.,name="right")],
    [],
])
def test_degenerate_and_mixed_signed_loads(acts):
    old=floor.solve_floor(**P,actions=acts,method=floor.POLICY_V2)
    new=floor.solve_floor(**P,actions=acts,method=floor.POLICY_V3)
    assert new['maximum_reference_moment_Nmm']==old['maximum_reference_moment_Nmm']
    if old['lambda_lower_bound'] is not None:
        assert new['lambda_lower_bound']>=old['lambda_lower_bound']
    else:
        assert new['lambda_lower_bound'] is None
