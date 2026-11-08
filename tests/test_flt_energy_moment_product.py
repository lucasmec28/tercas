"""Synthetic whole-span signed loads; no real project and no eigenproblem."""
import copy
import math
from fractions import Fraction
import numpy as np
import pytest
from tercas import flt_height_energy_floor as floor
from tercas import flt_height_nbr_floor as nbr
from tercas import pierin_ue_registry as registry
from tercas.ue_catalog_reference import digest
from tercas.ltb_load_height import action_terms
from test_flt_height_effective import data, uniform, point

P=dict(L_mm=3600.,Ly_mm=1800.,Lz_mm=2400.,E_MPa=205000.,G_MPa=79000.,
       Iweak_mm4=190000.,J_mm4=720.,Cw_mm6=6.2e8)
A=[uniform(.38,0.,'PP'),uniform(.57,55.),point(P=320.,h=42.,x=1800.)]


def solve(actions=A, **changes):
    return floor.solve_floor(**dict(P,**changes),actions=actions,method=floor.POLICY_V2)


def test_stronger_bound_and_exact_same_demand_and_hypotheses():
    old=floor.solve_floor(**P,actions=A); new=solve()
    assert new['schema']==floor.SCHEMA_V2
    assert new['Me_lower_bound_Nmm']>old['Me_lower_bound_Nmm']*1.2
    assert new['B_upper_Nmm']<old['B_upper_Nmm']
    for key in ('maximum_reference_moment_Nmm','D_upper_Nmm2','Ny_assumed_lower_N',
                'T_assumed_lower_Nmm2','energy_bound_hypotheses'):
        assert new[key]==old[key]
    assert not new['physical_supports_created'] and not new['demand_span_changed']
    assert not new['historical_physical_solver_lower_bound_claimed']


@pytest.mark.parametrize('seed',range(12))
def test_distributional_identity_and_bound_independent_quadrature(seed):
    rng=np.random.default_rng(seed);L=3600.
    q=float(rng.uniform(-1,1));ps=rng.uniform(-800,800,4);xs=np.array([430.,1250.,1800.,2870.])
    acts=[uniform(q,30.)]+[point(P=float(p),h=40.,x=float(x),name=str(i)) for i,(p,x) in enumerate(zip(ps,xs))]
    result=solve(acts)
    coeff=rng.normal(size=7);n=np.arange(1,8);k=n*math.pi/L
    def ph(x):return coeff@np.sin(k[:,None]*np.atleast_1d(x))
    def pd(x):return (coeff*k)@np.cos(k[:,None]*np.atleast_1d(x))
    def M(x):return q*x*(L-x)/2+sum(p*np.minimum((L-a)*x/L,a*(L-x)/L) for a,p in zip(xs,ps))
    reaction=q*L/2+sum(ps*(L-xs)/L)
    nodes,weights=np.polynomial.legendre.leggauss(90)
    lhs=rhs=W2=0.
    for lo,hi in zip([0.,*xs],[*xs,L]):
        x=(lo+hi)/2+(hi-lo)*nodes/2;w=weights*(hi-lo)/2
        v=reaction-q*x-sum(p for a,p in zip(xs,ps) if a<=lo)
        lhs+=sum(w*(v*ph(x)+M(x)*pd(x))**2)
        rhs+=sum(w*(M(x)**2*pd(x)**2+q*M(x)*ph(x)**2))
        W2+=sum(w*pd(x)**2)
    rhs+=sum(p*M(a)*float(ph(a)[0])**2 for a,p in zip(xs,ps))
    assert lhs==pytest.approx(rhs,rel=2e-12)
    witness=result['moment_product_bound']
    B2=float(Fraction(witness['B_squared_upper_fraction']))
    assert lhs <= B2*W2*(1+2e-12)
    assert result['determinant_exact_nonnegative']
    assert result['lambda_lower_bound']>=floor.solve_floor(**P,actions=acts)['lambda_lower_bound']


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_family66_versioned_resistance_bridge_and_replay(index):
    d=data(index,ly=1800.,lz=2400.);d['L_mm']=3600.
    old=nbr.qualify_family(d,A)
    new=nbr.qualify_family(d,A,method=floor.POLICY_V2)
    assert old['schema']=='flt_height_declared_energy_nbr_floor_v1'
    assert new['schema']=='flt_height_declared_energy_nbr_floor_v2'
    assert new['resistance_floor_eligible']
    assert new['MRd_lower_bound_Nmm']>=old['MRd_lower_bound_Nmm']
    assert new['energy_floor']['maximum_reference_moment_Nmm']==old['energy_floor']['maximum_reference_moment_Nmm']
    assert nbr.validate_saved(new,d,A)==new
    assert not new['failure_proven'] and not new['whole_member_approved']
    assert nbr.validate_saved(old,d,A)==old


def test_cancelled_and_support_forces_do_not_pollute_bound():
    base=solve()
    extra=A+[point(P=1e12,h=1e12,x=0.,name='left'),point(P=-1e12,h=1e12,x=3600.,name='right'),
             point(P=2048.,h=30.,x=1400.,name='plus'),point(P=-2048.,h=30.,x=1400.,name='minus')]
    other=solve(extra)
    for key in ('B_upper_Nmm','D_upper_Nmm2','Me_lower_bound_Nmm'):
        assert base[key]==other[key]
    zero=solve([uniform(1.,50.),uniform(-1.,0.,'cancel')])
    assert zero['Me_lower_bound_Nmm'] is None and zero['lambda_lower_bound']>0


def test_policy_and_witness_tampering_rejected():
    d=data(0,ly=1800.,lz=2400.);d['L_mm']=3600.
    r=floor.qualify_family(d,A,method=floor.POLICY_V2)
    for key in ('B_squared_upper_fraction','uniform_qM_max_positive_fraction'):
        bad=copy.deepcopy(r);bad['moment_product_bound'][key]='0';bad['snapshot_sha256']=digest(bad)
        with pytest.raises(ValueError):floor.validate_saved(bad,d,A)
    with pytest.raises(ValueError):floor.qualify_family(d,A,method='unknown')
    bad=copy.deepcopy(r);bad['schema']=floor.SCHEMA
    with pytest.raises(ValueError):floor.validate_saved(bad,d,A)


@pytest.mark.parametrize('factor',[.001,10.,1e5])
def test_load_scale_and_independent_lengths(factor):
    scaled=copy.deepcopy(A)
    for a in scaled:
        k='q_down_N_mm' if a['kind']=='uniform' else 'P_down_N';a[k]*=factor
    base=solve();r=solve(scaled)
    assert r['Me_lower_bound_Nmm']==pytest.approx(base['Me_lower_bound_Nmm'])
    for ly,lz in [(3600.,2400.),(1800.,3600.),(3600.,3600.)]:
        out=solve(Ly_mm=ly,Lz_mm=lz)
        assert out['maximum_reference_moment_Nmm']==base['maximum_reference_moment_Nmm']
        assert out['Me_lower_bound_Nmm']<base['Me_lower_bound_Nmm']

@pytest.mark.parametrize('acts',[
    [uniform(.7,40.)],
    [point(P=400.,h=20.,x=1800.)],
    [point(P=400.,h=20.,x=700.,name='one'),point(P=-600.,h=25.,x=2400.,name='two')],
    [point(P=400.,h=60.,x=1800.,name='one'),point(P=-400.,h=10.,x=1800.,name='two')],
    [],
])
def test_pure_cases_and_degenerate_zero_moment(acts):
    old=floor.solve_floor(**P,actions=acts);new=solve(acts)
    assert new['maximum_reference_moment_Nmm']==old['maximum_reference_moment_Nmm']
    if old['lambda_lower_bound'] is None:
        assert new['lambda_lower_bound'] is None
    else:
        assert new['lambda_lower_bound']>=old['lambda_lower_bound']
        assert new['determinant_exact_nonnegative']
    if not new['maximum_reference_moment_Nmm']:
        assert new['Me_lower_bound_Nmm'] is None


@pytest.mark.parametrize('x',[0.,1e-9,3600.-1e-9,3600.])
def test_point_support_and_one_sided_limits(x):
    base=solve([uniform(.7,40.)])
    out=solve([uniform(.7,40.),point(P=320.,h=30.,x=x)])
    assert out['Me_lower_bound_Nmm']==pytest.approx(base['Me_lower_bound_Nmm'],rel=1e-10)


@pytest.mark.parametrize('ly,lz',[(4100.,4100.),(2050.,4100.),(4100.,2050.),(2050.,2050.)])
def test_existing_independent_full_energy_trial_against_new_bound(monkeypatch,ly,lz):
    # Reuse independently integrated actual energy, never an eigenmode.
    from test_flt_height_energy_floor import test_independent_trial_functions_satisfy_energy_bound
    original=floor.solve_floor
    monkeypatch.setattr(floor,'solve_floor',lambda **kw:original(**kw,method=floor.POLICY_V2))
    test_independent_trial_functions_satisfy_energy_bound(ly,lz)


def test_fresh_imported_inputs_use_v3_floor_but_saved_v3_replays_v1(monkeypatch):
    from test_nbr_family_height_integration import source
    from tercas import nbr_ue_family_application as application
    from tercas.application import fingerprint
    r=source(0,Leff=1800.)
    r['input_data'].update(L_mm=3600.,q_uls=.32,P_uls=240.,x_uls=1800.)
    r['input_fingerprint']=fingerprint(r['input_data'])
    from tercas import ue_catalog_reference as own
    r=own.attach_source(r)
    old=copy.deepcopy(r)
    old[application.FIELD]=application._build(old,legacy_energy_floor=True)
    before=copy.deepcopy(old)
    from tercas import ltb_load_height
    monkeypatch.setattr(ltb_load_height,'refined',lambda *a,**k:pytest.fail('No Ritz solver expected'))
    assert old[application.FIELD]['schema']==application.LEGACY_SCHEMA_V3
    assert application.preserved(old)==old[application.FIELD]
    assert old==before
    fresh=application.attach(r)
    assert fresh[application.FIELD]['schema']==application.SCHEMA
    assert application.preserved(fresh)==fresh[application.FIELD]
    previous=old[application.FIELD]['records'][0]['height_energy_floor']
    current=fresh[application.FIELD]['records'][0]['height_energy_floor']
    assert previous['schema']=='flt_height_declared_energy_nbr_floor_v1'
    assert current['schema']=='flt_height_declared_energy_nbr_floor_v3'
    assert current['MRd_lower_bound_Nmm']>=previous['MRd_lower_bound_Nmm']
    assert current['maximum_reference_moment_Nmm']==previous['maximum_reference_moment_Nmm']
    assert fresh['input_data']==old['input_data']


def test_requested_v2_cannot_silently_consume_v1_evidence():
    d=data(0,ly=1800.,lz=2400.);d['L_mm']=3600.
    old=floor.qualify_family(d,A)
    with pytest.raises(ValueError):
        nbr.qualify_family(d,A,method=floor.POLICY_V2,energy_evidence=old)
