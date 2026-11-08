import math
import numpy as np
import pytest
from scipy.integrate import simpson
from tercas.nbr_service_strong_mse_signed import peak_deflection
from tercas.core import protocolo_ief as legacy

BASE=dict(L_mm=6000.,E_MPa=200000.,Ig_mm4=1e6,Ml_Nmm=1e6)


def solve(**kw):
    return peak_deflection(**(BASE | kw))


def independent_simpson(result,z,n=40001):
    # Independent equilibrium/Green function and literal stiffness calculation.
    L=result['physical_span_mm'];a=result['a_mm'];q=result['q_Nmm'];P=result['P_N']
    x=np.unique(np.r_[np.linspace(0,L,n),a,z])
    R=q*L/2+P*(L-a)/L
    M=R*x-q*x*x/2-P*np.maximum(x-a,0)
    lam=np.sqrt(np.abs(M)/result['Ml_Nmm'])
    rho=np.ones_like(x)
    mask=lam>.673
    rho[mask]=np.minimum(1,(1-.22/lam[mask])/lam[mask])
    kernel=np.minimum(x,z)*(L-np.maximum(x,z))/L
    return simpson(M*kernel/(result['E_MPa']*result['Ig_mm4']*rho),x=x)


@pytest.mark.parametrize('q,P,a',[(1,2000,1700),(-1,-2000,3800),(1,0,0),(0,2000,1700),(0,-2000,3000)])
def test_same_sign_matches_unchanged_legacy(q,P,a):
    r=solve(q_Nmm=q,P_N=P,a_mm=a)
    args=legacy.model(6000,200000,1e6,1e6,q,P,a)
    x,d=legacy.peak(args)
    assert r['peak_x_mm']==pytest.approx(x,abs=1e-6)
    assert r['deflection_mm']==pytest.approx(d,rel=2e-9,abs=1e-9)
    assert r['min_Ief_mm4']==legacy.ief(1e6,legacy.max_moment(args),1e6)


def test_opposing_three_stationary_noncentral_peak_and_simpson():
    r=solve(q_Nmm=1,P_N=-3700,a_mm=2950)
    assert len(r['stationary_points_mm'])==3
    assert r['peak_x_mm']==pytest.approx(4610.511145,abs=.001)
    for x,d in r['peak_candidates']:
        assert d==pytest.approx(independent_simpson(r,x),abs=2e-7)
    # A dense independent sweep also checks the global peak choice.
    independent=[abs(independent_simpson(r,z,8001)) for z in np.linspace(0,6000,81)]
    assert max(independent)<=r['absolute_deflection_mm']+2e-6
    assert max(independent)>r['absolute_deflection_mm']*.998


def test_signed_stiffness_transitions_and_minimum():
    r=solve(q_Nmm=1,P_N=-3700,a_mm=2950)
    points=r['stiffness_transition_points_mm']
    assert len(points)>=4
    moments=[legacy.moment(x,6000,1,-3700,2950) for x in points]
    assert min(moments)<0<max(moments)
    for m in moments:
        assert abs(m)==pytest.approx(r['stiffness_transition_abs_moment_Nmm'],rel=2e-14)
    grid=np.linspace(0,6000,10001)
    inertias=[legacy.ief(1e6,legacy.moment(x,6000,1,-3700,2950),1e6) for x in grid]
    assert r['min_Ief_mm4']<=min(inertias)*(1+1e-12)
    assert r['min_Ief_mm4']==pytest.approx(min(inertias),rel=.001)


def test_sign_reversal_and_reflection():
    r=solve(q_Nmm=1,P_N=-3700,a_mm=2950)
    s=solve(q_Nmm=-1,P_N=3700,a_mm=2950)
    reflected=solve(q_Nmm=1,P_N=-3700,a_mm=3050)
    assert s['peak_x_mm']==pytest.approx(r['peak_x_mm'],abs=1e-6)
    assert s['deflection_mm']==pytest.approx(-r['deflection_mm'],rel=1e-12)
    assert reflected['peak_x_mm']==pytest.approx(6000-r['peak_x_mm'],abs=1e-6)
    assert reflected['deflection_mm']==pytest.approx(r['deflection_mm'],rel=1e-12)


@pytest.mark.parametrize('a',[0,3000,6000,math.nextafter(3000,0),math.nextafter(6000,0)])
def test_zero_and_point_at_boundaries(a):
    r=solve(q_Nmm=0,P_N=0,a_mm=a)
    assert r['deflection_mm']==0
    assert r['min_Ief_mm4']==1e6
    assert r['zero_curvature_intervals_mm']
    if a in (0,6000):
        endpoint=solve(q_Nmm=0,P_N=500,a_mm=a)
        assert endpoint['deflection_mm']==0
        assert endpoint['zero_curvature_intervals_mm']==[(0,6000)]
    # Very short load patch must not generate a quadrature warning/failure.
    p=solve(q_Nmm=1,P_N=-3600,a_mm=a)
    assert math.isfinite(p['deflection_mm'])


def test_legacy_still_refuses_opposed_actions():
    with pytest.raises(ValueError,match='mesmo sentido'):
        legacy.model(6000,200000,1e6,1e6,1,-3700,2950)


@pytest.mark.parametrize('kw',[dict(L_mm=0),dict(Ml_Nmm=0),dict(q_Nmm=math.nan),dict(a_mm=6001),dict(E_MPa=math.inf)])
def test_invalid_inputs(kw):
    with pytest.raises(ValueError): solve(**kw)


def test_opposed_constant_stiffness_independent_closed_form():
    r=solve(Ml_Nmm=1e12,q_Nmm=1,P_N=-3600,a_mm=3000)
    L=6000.; q=1.; P=-3600.; R=q*L/2+P/2
    c=q*L**3/24+P*L**2/16
    roots=np.roots([q/6,-R/2,0,c])
    left=min(float(t.real) for t in roots if abs(t.imag)<1e-9 and 0<t.real<L/2)
    expected=[left,L/2,L-left]
    assert r['stationary_points_mm']==pytest.approx(expected,abs=1e-6)
    # Integrate v'=c-R*x^2/2+q*x^3/6 directly on the left half.
    displacement=(c*left-R*left**3/6+q*left**4/24)/(200000*1e6)
    assert r['absolute_deflection_mm']==pytest.approx(abs(displacement),rel=1e-12)
