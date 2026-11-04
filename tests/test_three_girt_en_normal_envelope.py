import math
import numpy as np
import pytest
from tercas.three_girt_en_normal import field_envelope as e

@pytest.mark.parametrize('h',[0.,1e-8,.1,1.,5.,10.])
def test_bimoment_ode_and_derivatives(h):
    field=dict(h=h,B0=21.,U=-38.,V=5.)
    for t in (0.,.3,1.):
        assert e.bimoment(field,t,2)-h*h*e.bimoment(field,t)==pytest.approx(-38-h*h*21,abs=2e-9)
        delta=1e-5
        numerical=(e.bimoment(field,t+delta)-e.bimoment(field,t-delta))/(2*delta)
        assert numerical==pytest.approx(e.bimoment(field,t,1),rel=2e-8,abs=1e-7)

@pytest.mark.parametrize('seed',range(8))
def test_extrema_against_independent_dense_grid(seed):
    rng=np.random.default_rng(seed)
    ts=np.linspace(0,1,20001)
    for _ in range(35):
        h=float(rng.uniform(.001,10));B0,U,V=rng.normal(size=3)*100
        field=dict(h=h,B0=float(B0),U=float(U),V=float(V))
        p=rng.normal(size=3)*100;w=float(rng.normal())
        r=e.stress_extrema(p.tolist(),w,field)
        val=p[0]+p[1]*ts+p[2]*ts**2+w*(B0+U*2*(np.sinh(h*ts/2)/h)**2+V*np.sinh(h*ts)/h)
        assert r['maximum']['sigma_MPa']>=val.max()-1e-7
        assert r['minimum']['sigma_MPa']<=val.min()+1e-7
        assert r['maximum_absolute']['sigma_MPa']==pytest.approx(e.sigma_value(p,w,field,r['maximum_absolute']['t']))
        # A dense grid is a lower bound, not the envelope algorithm.
        assert abs(r['maximum_absolute']['sigma_MPa'])==pytest.approx(np.max(abs(val)),rel=2e-7,abs=1e-6)


def test_four_analytical_roots_are_partitioned():
    # Construct derivative with three zeros: sinh(2(t-.5))-k(t-.5).
    # k=2.2 produces roots at .5 and two symmetric nonzero offsets.
    h=2.;U=math.cosh(1)*h;V=-math.sinh(1);field=dict(h=h,B0=0.,U=U,V=V)
    p=[0.,1.1,-1.1]
    r=e.stress_extrema(p,1.,field)
    assert r['candidate_count']==5
    assert r['maximum']['t']>0


def test_zero_h_and_zero_w_have_quadratic_limit():
    f=dict(h=0.,B0=2.,U=-8.,V=0.)
    r=e.stress_extrema([0.,4.,0.],1.,f)
    assert r['maximum']==dict(t=.5,sigma_MPa=3.)
    r=e.stress_extrema([1.,2.,-2.],0.,dict(h=10.,B0=2.,U=3.,V=4.))
    assert r['maximum']==dict(t=.5,sigma_MPa=1.5)


def test_sign_partition_does_not_delete_small_axial():
    parts=e.sign_intervals(dict(N=[1e-250],Mx=[.1875,-1,1],My=[0.]))
    assert [(r['left'],r['right']) for r in parts]==[(0.,.25),(.25,.75),(.75,1.)]
    assert all(r['signs']['N']==1 and r['signs']['My']==0 for r in parts)
    assert [r['signs']['Mx'] for r in parts]==[1,-1,1]


def test_exterior_fibers_combine_same_endpoint_omega():
    section=dict(nodes_xy_mm=[[0.,0.],[2.,0.],[2.,3.]],omega_nodes_mm2=[1.,4.,8.],
        thickness_mm=2.,properties=dict(centroid_xy_mm=[1.,1.],Cw_mm6=4.))
    fibers=e.exterior_fibers(section)
    assert len(fibers['xy_mm'])==8
    assert fibers['xy_mm'][0]==[-1.,-2.]
    assert fibers['xy_mm'][1]==[-1.,0.]
    assert fibers['omega_over_Cw'][:4]==[.25,.25,1.,1.]
    assert fibers['identities'][4]['midsurface_node_index']==1


def test_concomitant_field_not_sum_of_component_maxima():
    # N+Mx: x-coordinate stress rises while B falls, cancelling exactly.
    polys=dict(N=[2.],Mx=[0.,10.],My=[0.])
    coefficients=dict(N=[1.,0.,0.],Mx=[1.,0.,0.])
    f=dict(h=0.,B0=10.,U=0.,V=-10.)
    r=e.envelope(polys,coefficients,[[0.,0.],[1.,1.]],[1.,1.],f)
    assert r['maximum_absolute']['sigma_MPa']==12.
    assert r['maximum_absolute']['sigma_MPa']!=2+10+10

@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'1'])
def test_bad_numeric_rejected(value):
    with pytest.raises(ValueError):e.stress_extrema([value,0.,0.],0.,dict(h=0.,B0=0.,U=0.,V=0.))

@pytest.mark.parametrize('coeff',[
    [1.3780268742046483e17,-5.392385729883294e17,5.2752642934906016e17],
    [121495.82832884698,-492137.55517960404,498369.73118658905],
    [math.nextafter(.25,-math.inf),-1.,1.],
    [1.,-2.,math.nextafter(1.,-math.inf)]])
def test_close_quadratic_roots_preserve_negative_sign(coeff):
    parts=e.sign_intervals(dict(N=[0.],Mx=[0.],My=coeff))
    assert any(-1 in r['required_signs']['My'] for r in parts)
    assert all(r['right']>r['left'] for r in parts)


def test_sub_ulp_boundary_root_never_erases_opposite_sign():
    # Exact root near 1 is rounded to 1 by binary64 and by 100-digit arithmetic.
    # The exact polynomial is negative at 1, so its tiny negative tail exists.
    coeff=[1e308,-1e308,-5e-324]
    parts=e.sign_intervals(dict(N=[0.],Mx=[0.],My=coeff))
    assert any(-1 in r['required_signs']['My'] for r in parts)
    assert any(1 in r['required_signs']['My'] for r in parts)
