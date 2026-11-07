"""Analytical and independent energy checks; no matrix eigenproblem."""
import copy
import json
import math
import numpy as np
import pytest
from tercas import flt_height_energy_floor as floor
from tercas import pierin_ue_registry as registry
from test_flt_height_effective import data, actions, uniform, point

P=dict(L_mm=4100.,Ly_mm=2050.,Lz_mm=2050.,E_MPa=200000.,G_MPa=77000.,
       Iweak_mm4=170444.,J_mm4=655.,Cw_mm6=5.69e8)


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_family_q_plus_p_with_independent_lengths(index):
    d=data(index,ly=2733.,lz=3200.);a=actions(d)+[point(P=150.,h=35.,x=1410.)]
    out=floor.qualify_family(d,a)
    assert out['elastic_reference_eligible'] and out['Me_lower_bound_Nmm']>0.
    assert out['energy_bound_hypotheses']['physical_realization_verified'] is False
    assert out['mathematical_lower_bound_of_declared_operator']
    assert out['historical_physical_solver_lower_bound_claimed'] is False
    assert not out['physical_supports_created'] and not out['demand_span_changed']
    assert not out['whole_member_approved']
    assert floor.validate_saved(json.loads(json.dumps(out)),d,a)==out


def test_quadratic_root_independent_calculation():
    from decimal import Decimal,localcontext
    r=floor.solve_floor(**P,actions=[uniform(.9,60.),point(P=200.,h=30.,x=1700.)])
    with localcontext() as c:
        c.prec=60;D=lambda v:Decimal(str(v))
        n,t,b,d=map(D,[r['Ny_assumed_lower_N'],r['T_assumed_lower_Nmm2'],r['B_upper_Nmm'],r['D_upper_Nmm2']])
        expected=((-n*d+(n*n*d*d+4*b*b*n*t).sqrt())/(2*b*b))
    assert r['lambda_lower_bound']==pytest.approx(float(expected),rel=3e-15)
    assert 0<=r['determinant_relative_residual']<5e-12
    assert r['determinant_exact_nonnegative']


@pytest.mark.parametrize('ly,lz',[(4100.,4100.),(2050.,4100.),(4100.,2050.),(2050.,2050.)])
def test_independent_trial_functions_satisfy_energy_bound(ly,lz):
    # Exact Fourier fields meet free-rotation or fully fixed Euler inequalities.
    # No tuning of a critical eigenmode to the tested formula.
    p=dict(P,Ly_mm=ly,Lz_mm=lz);L=p['L_mm']
    a=[uniform(.6,60.),uniform(-.4,0.,'PP'),point(P=300.,h=22.,x=900.),point(P=-80.,h=50.,x=2800.,name='up')]
    r=floor.solve_floor(**p,actions=a);lam=r['lambda_lower_bound']
    rng=np.random.default_rng(9832)
    nodes,weights=np.polynomial.legendre.leggauss(180)
    cuts=[0.,900.,2800.,L]
    def field(x,coeff,L_eff):
        n=np.arange(1,len(coeff)+1);k=n*math.pi/L*(2 if L_eff==L/2 else 1)
        phase=k[:,None]*np.atleast_1d(x)
        if L_eff==L/2:
            return coeff@(1-np.cos(phase)),(coeff*k)@np.sin(phase),(coeff*k*k)@np.cos(phase)
        return coeff@np.sin(phase),(coeff*k)@np.cos(phase),-(coeff*k*k)@np.sin(phase)
    for _ in range(12):
        cu=rng.normal(size=5);cp=rng.normal(size=5)/L
        e=0.;U2=W2=0.
        for lo,hi in zip(cuts[:-1],cuts[1:]):
            x=(lo+hi)/2+(hi-lo)*nodes/2;w=weights*(hi-lo)/2
            _,ud,udd=field(x,cu,ly);ph,pd,pdd=field(x,cp,lz)
            # Independent statics for this explicit combination.
            M=.2*x*(L-x)/2+300*np.minimum((L-900)*x/L,900*(L-x)/L)-80*np.minimum((L-2800)*x/L,2800*(L-x)/L)
            e+=sum(w*(p['E_MPa']*p['Iweak_mm4']*udd**2+p['G_MPa']*p['J_mm4']*pd**2+p['E_MPa']*p['Cw_mm6']*pdd**2+2*lam*M*udd*ph-lam*36.*ph**2))
            U2+=sum(w*ud**2);W2+=sum(w*pd**2)
        e-=lam*300*22*float(field(900.,cp,lz)[0][0])**2
        e-=lam*(-80)*50*float(field(2800.,cp,lz)[0][0])**2
        scalar=r['Ny_assumed_lower_N']*U2+(r['T_assumed_lower_Nmm2']-lam*r['D_upper_Nmm2'])*W2-2*lam*r['B_upper_Nmm']*math.sqrt(U2*W2)
        assert e>=scalar-1e-8*max(abs(e),1.)
        assert scalar>=-1e-9*max(abs(e),1.)


def test_physical_shear_one_sided_extrema_and_end_loads():
    from tercas.ltb_load_height import action_terms
    a=[uniform(1.,0.),point(P=-500.,h=0.,x=1000.),point(P=1e6,h=1e6,x=0.,name='end')]
    r=floor.maximum_shear(4100.,action_terms(a,4100.))
    expected=2050.-500.*3100/4100.
    assert r['maximum_abs_V_N']==pytest.approx(max(expected,abs(expected-4100+500)))
    u=floor.solve_floor(**P,actions=[uniform(1.,0.)])
    v=floor.solve_floor(**P,actions=[uniform(1.,0.),point(P=1e6,h=1e6,x=0.)])
    assert u['Me_lower_bound_Nmm']==v['Me_lower_bound_Nmm']


def test_mixed_sign_height_aggregation_and_zero_reference_bending():
    a=[uniform(1.,60.),uniform(-1.,0.,'opposite')]
    r=floor.solve_floor(**P,actions=a)
    assert r['lambda_lower_bound']>0 and r['Me_lower_bound_Nmm'] is None
    assert r['status']=='rotational_energy_bound_without_reference_bending'
    zero=floor.solve_floor(**P,actions=[])
    assert zero['lambda_lower_bound'] is None and zero['Me_lower_bound_Nmm'] is None
    stabilizing=floor.solve_floor(**P,actions=[uniform(-1.,60.)])
    noheight=floor.solve_floor(**P,actions=[uniform(-1.,0.)])
    assert stabilizing['Me_lower_bound_Nmm']==noheight['Me_lower_bound_Nmm']


@pytest.mark.parametrize('factor',[.01,10.,1000.])
def test_scaling_and_demand_independent_of_lengths(factor):
    a=[uniform(.6,50.),point(P=250.,h=100.,x=1150.)]
    r=floor.solve_floor(**P,actions=a)
    b=[uniform(.6*factor,50.),point(P=250.*factor,h=100.,x=1150.)]
    s=floor.solve_floor(**P,actions=b)
    assert s['Me_lower_bound_Nmm']==pytest.approx(r['Me_lower_bound_Nmm'])
    assert s['lambda_lower_bound']*factor==pytest.approx(r['lambda_lower_bound'])
    t=floor.solve_floor(**dict(P,Ly_mm=3000.,Lz_mm=4000.),actions=a)
    assert t['maximum_reference_moment_Nmm']==r['maximum_reference_moment_Nmm']
    assert t['Me_lower_bound_Nmm']<r['Me_lower_bound_Nmm']


def test_rehashed_operator_hypothesis_or_floor_rejected():
    from tercas.ue_catalog_reference import digest
    d=data();a=actions(d)+[point(x=900.)];r=floor.qualify_family(d,a)
    for key in ('Ny_assumed_lower_N','T_assumed_lower_Nmm2','Me_lower_bound_Nmm','B_upper_Nmm'):
        bad=copy.deepcopy(r);bad[key]*=2
        bad['snapshot_sha256']=digest({k:v for k,v in bad.items() if k!='snapshot_sha256'})
        with pytest.raises(ValueError):floor.validate_saved(bad,d,a)


def test_severe_cancellation_keeps_exact_moment_upper_bound():
    from fractions import Fraction
    p=dict(P,L_mm=1.1,Ly_mm=1.1,Lz_mm=1.1)
    a=[uniform(1e16,0.),uniform(-1e16+2,0.,'cancel')]
    r=floor.solve_floor(**p,actions=a)
    expected=Fraction.from_float(1.1)**2/4
    assert Fraction(r['exact_load_quantities']['Mmax_fraction'])==expected
    assert r['maximum_reference_moment_Nmm']==float(expected)
    assert r['maximum_reference_moment_Nmm']>.3
    assert r['B_upper_Nmm']>=float(expected)


def test_force_height_products_never_cancel_after_individual_rounding():
    from fractions import Fraction
    h1=1.0000000000000002;h2=1.
    a=[uniform(1e16,h1),uniform(-1e16,h2,'cancel')]
    r=floor.solve_floor(**P,actions=a)
    expected=Fraction.from_float(1e16)*(Fraction.from_float(h1)-Fraction.from_float(h2))
    assert Fraction(r['exact_load_quantities']['q_height_fraction'])==expected
    assert r['uniform_height_sum_N']==float(expected)
    assert r['D_upper_Nmm2']>0 and r['lambda_lower_bound']>0
    assert r['Me_lower_bound_Nmm'] is None
    p=[point(P=1e16,h=h1,x=1000.),point(P=-1e16,h=h2,x=1000.,name='cancel')]
    result=floor.solve_floor(**P,actions=p)
    assert result['point_height_bounds'][0]['D_Nmm2']>0


def test_integer_square_root_enclosure_and_directed_conversion():
    from fractions import Fraction
    for value in (Fraction(2),Fraction(1,10**300),Fraction(10**300),Fraction(25,49)):
        upper=floor._sqrt_upper(value)
        assert upper*upper>=value
    tiny=Fraction(1,10**330)
    assert Fraction.from_float(floor._directed(tiny,True))>=tiny
    assert Fraction.from_float(floor._directed(Fraction(1,3),False))<=Fraction(1,3)


def test_family_bound_does_not_depend_on_documentary_float_maximum(monkeypatch):
    from tercas import flt_height_effective
    monkeypatch.setattr(flt_height_effective,'qualify_family',lambda *a,**k:pytest.fail('Documentary Me invoked'))
    d=data();r=floor.qualify_family(d,[uniform(1e16,0.),uniform(-1e16+2,0.,'cancel')])
    assert r['maximum_reference_moment_Nmm']==4100.**2/4
    assert r['elastic_reference_eligible']
