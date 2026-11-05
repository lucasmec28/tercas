"""Small independent fields exercise physical callbacks, not a network solve."""
import math
import numpy as np
import pytest
from tercas.three_girt_en_normal import shear_interaction as si


@pytest.fixture
def field(monkeypatch):
    def run(sigma=(0.,0.,0.),tau=0.,callback=None,**kwargs):
        row=dict(segment_index=0,face=1,sigma=np.array([sigma,[0.,0.,0.],[0.,0.,0.]]),
            omega=np.zeros(3),tau=np.array([[tau,0.,0.],[0.,0.,0.],[0.,0.,0.]]),
            tw_weight=np.zeros(3),normal_xy=[0.,1.],xy_start=np.zeros(2),xy_delta=np.array([1.,0.]),
            sigma_roundoff_scale=sum(abs(v) for v in sigma),tau_roundoff_scale=abs(tau),tw_roundoff_scale=0.)
        tor=dict(h=0.,B0=0.,U=0.,V=0.)
        monkeypatch.setattr(si,'section_fields',lambda *args:([row],tor))
        return si.envelope({},dict(N=[0.],Mx=[0.],My=[0.]),{},tor,[0.],1.,
            max_refinements=0,witness_evaluator=callback,**kwargs)
    return run


def test_artificial_exceedance_is_not_a_physical_witness(field):
    def physical(w):
        return dict(w,sigma_MPa=100.,tau_MPa=20.,witness_error_MPa=1e-10)
    r=field(sigma=(500.,0.,0.),tau=20.,callback=physical)
    for key in ('normal','interaction'):
        assert r[key]['index_lower_witness']<1<r[key]['index_upper_bound']
        assert r[key]['criterion']=='unresolved_numerical_bound'
        assert r[key]['witness']['sigma_MPa']==100.
    assert r['interaction']['witness']['equivalent_MPa']==pytest.approx(math.hypot(100.,math.sqrt(3)*20.))


def test_physical_other_branch_point_explicitly_enlarges_local_upper(field):
    r=field(callback=lambda w:dict(w,sigma_MPa=400.,witness_error_MPa=1e-9))
    assert r['normal']['physical_witness_upper_adjustment']>1.
    assert r['normal']['index_upper_bound']>=r['normal']['index_lower_witness']>1.
    assert r['normal']['criterion']=='above_1_at_concomitant_state'


def test_absent_physical_witness_remains_absent_in_aggregate(field):
    r=field(sigma=(500.,0.,0.),callback=lambda w:None)
    assert r['discarded_witness_count']>0
    for result in (r,si.aggregate([r],True)):
        for key in ('normal','shear','interaction'):
            assert result[key]['witness'] is None
            assert result[key]['index_lower_witness'] is None
            assert result[key]['bound_gap'] is None
        assert result['normal']['criterion']=='unresolved_numerical_bound'
    partial=si.aggregate([r,None],True)
    assert not partial['complete'] and partial['normal']['index_upper_bound'] is None
    assert partial['normal']['partial_index_upper_bound']>1.


def test_roundoff_around_one_cannot_pass_or_create_exceedance(field):
    r=field(sigma=(250.+1e-12,0.,0.),
        callback=lambda w:dict(w,witness_error_MPa=dict(sigma=1e-10,tau=1e-10)))
    assert r['normal']['witness']['index']>1
    assert r['normal']['index_lower_witness']<1<r['normal']['index_upper_bound']
    assert r['normal']['criterion']=='unresolved_numerical_bound'


def test_quadratic_normal_peak_and_endpoint_fiber(field):
    # 25 + 400*x - 400*x^2 has its exact maximum 125 at x=1/2.
    r=field(sigma=(25.,400.,-400.))
    normal=r['normal'];w=normal['witness']
    assert w['t']==.5 and w['u'] in (0.,1.)
    assert w['sigma_MPa']==125.
    assert normal['index_lower_witness']<=.5<=normal['index_upper_bound']
    assert normal['index_upper_bound']-.5<1e-10


@pytest.mark.parametrize('value',[math.nan,math.inf,-math.inf])
def test_nonfinite_callback_stress_is_rejected(field,value):
    with pytest.raises(ValueError,match='Finite physical witness'):
        field(callback=lambda w:dict(w,sigma_MPa=value))


def test_nan_upper_and_inverted_aggregate_are_rejected(field):
    r=field(sigma=(100.,0.,0.))
    r['normal']['index_upper_bound']=math.nan
    with pytest.raises(ValueError,match='Finite complete interval'):
        si.aggregate([r],True)
    r['normal']['index_upper_bound']=0.
    with pytest.raises(ArithmeticError,match='below physical lower'):
        si.aggregate([r],True)


def test_callback_cannot_move_candidate(field):
    with pytest.raises(ValueError,match='preserve the candidate location'):
        field(callback=lambda w:dict(w,t=2.))


def test_callback_zero_error_cannot_remove_engine_roundoff_guard(field):
    r=field(sigma=(250.+1e-12,0.,0.),callback=lambda w:dict(w,witness_error_MPa=0.))
    assert r['normal']['index_lower_witness']<1<r['normal']['index_upper_bound']
    assert r['normal']['criterion']=='unresolved_numerical_bound'


def test_nan_in_nonwinning_lower_is_rejected(field):
    good=field(sigma=(100.,0.,0.));bad=field(sigma=(50.,0.,0.))
    bad['normal']['index_lower_witness']=math.nan
    with pytest.raises(ValueError,match='Finite nonnegative lower'):
        si.aggregate([good,bad],True)


def test_tiny_quadratic_bound_covers_exact_fraction_extrema(field,monkeypatch):
    from fractions import Fraction as F
    left=1/3;right=math.nextafter(left,math.inf)
    p=(.1,1e8,-1e8)
    def forbidden(*args,**kwargs):
        raise AssertionError('Tiny interval must not isolate roots')
    monkeypatch.setattr(si.f,'stress_extrema',forbidden)
    r=field(sigma=p,left=left,right=right)
    points=[F(left),F(right)]
    vertex=-F(p[1])/(2*F(p[2]))
    if points[0]<=vertex<=points[1]:points.append(vertex)
    exact=max(abs(F(p[0])+F(p[1])*x+F(p[2])*x*x) for x in points)/250
    assert F(r['normal']['index_upper_bound'])>=exact
    assert r['normal']['index_lower_witness']<=r['normal']['index_upper_bound']


def test_tiny_hyperbolic_bound_covers_extrema_and_dense_values():
    tor=dict(h=2.7,B0=1e5,U=-3e5,V=2e5);p=[10.,-7.,8.];w=.03
    left=.7;right=left+16*math.ulp(1.)
    raw=si._tiny_interval_magnitude(p,w,tor,left,right)
    # Same magnitude-scaled numerical padding used by the engine.
    c=2*(math.sinh(tor['h']/2)/tor['h'])**2;d=math.sinh(tor['h'])/tor['h']
    pad=128*np.finfo(float).eps*max(1.,sum(abs(v) for v in p)+abs(w)*(abs(tor['B0'])+abs(tor['U'])*c+abs(tor['V'])*d))
    upper=raw+pad
    exact_candidates=si.f.stress_extrema(p,w,tor,left,right)
    assert upper>=abs(exact_candidates['maximum_absolute']['sigma_MPa'])
    for x in np.linspace(left,right,65):
        assert upper>=abs(si.f.sigma_value(p,w,tor,x))
    wide=si.f.stress_extrema(p,w,tor,0.,1.)
    assert upper<=abs(wide['maximum_absolute']['sigma_MPa'])+pad


def test_bounds_only_tiny_fraction_and_no_callback(field):
    from fractions import Fraction as F
    left=1/3;right=math.nextafter(left,math.inf);p=(.1,1e8,-1e8)
    def forbidden(w):raise AssertionError('No witness proposals in bounds-only tiny')
    r=field(sigma=p,left=left,right=right,callback=forbidden,bounds_only_tiny=True)
    exact=max(abs(F(p[0])+F(p[1])*x+F(p[2])*x*x) for x in (F(left),F(right)))/250
    assert F(r['normal']['index_upper_bound'])>=exact
    for key in ('normal','shear','interaction'):
        assert r[key]['witness'] is None and r[key]['index_lower_witness'] is None
        assert r[key]['bound_gap'] is None
    assert r['bounds_only_tiny'] and r['refinements']==0


def test_bounds_only_tiny_matches_padded_scalar_and_rejects_nan(field):
    left=.7;right=left+16*math.ulp(1.)
    a=field(sigma=(45.,-30.,50.),tau=12.,left=left,right=right)
    b=field(sigma=(45.,-30.,50.),tau=12.,left=left,right=right,bounds_only_tiny=True)
    for key in ('normal','shear','interaction'):
        assert b[key]['index_upper_bound']==pytest.approx(a[key]['index_upper_bound'],rel=2e-15)
    with pytest.raises(ValueError,match='Finite prepared'):
        field(sigma=(math.nan,0.,0.),left=left,right=right,bounds_only_tiny=True)
