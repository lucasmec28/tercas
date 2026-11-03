"""Quadrature-only regression: same Ief law, now explicit transition panels.

The U100 witness is synthetic, not a real project. Independent composite
Gauss integration below does not call the application's Ief or integrator.
"""
import math
import numpy as np
import pytest
from numpy.polynomial.legendre import leggauss
from tercas.core.protocolo_ief import model, peak, deflection

E=200000.
IG=614847.8166649565
ML=3476837.6663651397


def independent_delta(L,q,P,a,z,order=128):
    assert q*P>=0
    R=q*L/2+P*(L-a)/L
    sign=1 if q+P>=0 else -1
    threshold=((1+math.sqrt(.12))/2)**2*ML
    knots={0.,a,z,L}
    for lo,hi,B,C in [(0.,a,R,0.),(a,L,R-P,P*a)]:
        coeff=[-sign*q/2,sign*B,sign*C-threshold]
        while coeff and coeff[0]==0:coeff.pop(0)
        if len(coeff)>1:
            for root in np.roots(coeff):
                if abs(root.imag)<1e-10 and lo<root.real<hi:knots.add(float(root.real))
    t,w=leggauss(order)
    result=0.
    for lo,hi in zip(sorted(knots),sorted(knots)[1:]):
        x=lo+(hi-lo)*(t+1)/2
        M=R*x-q*x*x/2-P*np.maximum(x-a,0)
        mu=np.where(x<=z,(L-z)*x/L,z*(L-x)/L)
        lam=np.sqrt(np.abs(M)/ML)
        with np.errstate(divide='ignore',invalid='ignore'):
            rho=np.where(lam<=.673,1.,np.minimum(1.,(1-.22/lam)/lam))
        result+=(hi-lo)/2*float(w@(M*mu/(E*IG*rho)))
    return result


def test_u100_6m_variable_I_witness():
    # Own rounded U100, synthetic CP8/SC25/Vdown40, theta +5 degrees,
    # rare-SLS row ELSR_00007. Old unsplit quad returned 181.80376649908894.
    args=model(6000.,E,IG,ML,.9907673335054957,0.,3000.)
    x,delta=peak(args)
    expected=181.8037650016988
    assert abs(x-3000.)<1e-7
    assert abs(delta-expected)<2e-9
    assert abs(independent_delta(6000.,args[4],0.,3000.,3000.)-expected)<2e-9


@pytest.mark.parametrize('q,P,a_fraction,z_fraction',[
    (1.,0.,.5,.5),(1.,0.,.5,.23),(.2,4000.,.5,.5),
    (.2,4000.,.2,.43),(0.,6000.,.31,.61),
    (.9,1000.,0.,.5),(.9,1000.,1.,.5),
])
@pytest.mark.parametrize('sign',[1.,-1.])
def test_split_quadrature_matches_independent_gauss(q,P,a_fraction,z_fraction,sign):
    L=6000.;a=L*a_fraction;z=L*z_fraction;q*=sign;P*=sign
    args=model(L,E,IG,ML,q,P,a)
    expected=independent_delta(L,q,P,a,z)
    refined=independent_delta(L,q,P,a,z,192)
    assert abs(expected-refined)<1e-10+1e-12*abs(refined)
    actual=deflection(args,z)
    assert abs(actual-expected)<2e-9+1e-11*abs(expected)


def test_full_I_closed_form_and_constant_min_unchanged():
    L=3000.;q=.05;P=20.
    args=model(L,E,IG,ML,q,P,L/2)
    expected=5*q*L**4/(384*E*IG)+P*L**3/(48*E*IG)
    assert abs(deflection(args,L/2)-expected)<1e-12
    assert abs(deflection(args,L/2,True)-expected)<1e-12


def test_support_point_only_does_not_create_interior_bending():
    for a in (0.,6000.):
        for P in (-6000.,6000.):
            assert peak(model(6000.,E,IG,ML,0.,P,a))==(0.,0.)
