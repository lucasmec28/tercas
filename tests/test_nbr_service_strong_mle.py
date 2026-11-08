import math
import pytest
from scipy.integrate import quad
from tercas import nbr_service_strong_mle as s
from tercas import nbr_ue_family as f
from tercas.nbr_ue_family_expansion import OutsideMethod, strong_effective_modulus

@pytest.mark.parametrize('index',s.INDICES)
def test_compatible_service_sections_and_monotone_curve(index):
    p,g=f._geometry(index); m=dict(f.DEFAULT_MATERIAL,fy_MPa=350.)
    previous=0.; previous_i=g['Ix_strong_mm4']*1.00000000001
    for sigma in (1.,50.,100.,150.,200.,225.,250.,275.,300.,325.,350.):
        reference=strong_effective_modulus(p,g,m,sigma)
        moment=sigma*reference['Wc_mm3']; assert moment>previous
        sec=s.section_at_moment(index,moment,material=m)
        assert sec['stress_MPa']==pytest.approx(sigma,abs=1e-7)
        assert abs(sec['residual_MPa'])<1e-7
        assert sec['Ixef_mm4']<=previous_i
        assert sec['web_proof']['fully_effective']
        neg=s.section_at_moment(index,-moment,material=m)
        assert neg['Ixef_mm4']==sec['Ixef_mm4']
        assert neg['sign_reflected_by_horizontal_symmetry']
        previous=moment; previous_i=sec['Ixef_mm4']*1.00000000001

@pytest.mark.parametrize('index',s.INDICES)
def test_gross_uniform_and_point_closed_forms(index):
    g=f._geometry(index)[1]; E=f.DEFAULT_MATERIAL['E_MPa']; I=g['Ix_strong_mm4']; L=6000.
    for q,P,expected in [(1.,0.,5*L**4/(384*E*I)),(0.,1000.,1000*L**3/(48*E*I))]:
        out=s.peak_deflection(index,L_mm=L,q_Nmm=q,P_N=P)
        assert out['peak_x_mm']==pytest.approx(L/2,abs=1e-6)
        assert out['deflection_mm']==pytest.approx(expected,rel=1e-9)
        assert not out['local_elastic_critical_inferred']
        negative=s.peak_deflection(index,L_mm=L,q_Nmm=-q,P_N=-P)
        assert negative['deflection_mm']==pytest.approx(-expected,rel=1e-9)


def test_reduced_section_independent_midspan_curvature_integral():
    index=79; L=6000.; q=10.; m=dict(f.DEFAULT_MATERIAL,fy_MPa=350.)
    out=s.peak_deflection(index,L_mm=L,q_Nmm=q,material=m)
    law,_,g=s._law(index,m)
    # Symmetry: delta(mid)= integral_0^(L/2) M*x/(E*I(M)) dx.
    independent=quad(lambda x: (q*x*(L-x)/2)*x/(m['E_MPa']*law(q*x*(L-x)/2)['Ixef_mm4']),0,L/2,epsabs=1e-8,epsrel=1e-9)[0]
    assert out['deflection_mm']==pytest.approx(independent,rel=1e-8)
    gross=5*q*L**4/(384*m['E_MPa']*g['Ix_strong_mm4'])
    assert out['deflection_mm']>gross
    assert out['section_at_max_moment']['Ixef_mm4']<g['Ix_strong_mm4']


def test_signed_opposing_actions_and_asymmetric_point():
    L=6000.;q=1.;P=-4000.;a=1700.
    out=s.peak_deflection(82,L_mm=L,q_Nmm=q,P_N=P,a_mm=a)
    I=f._geometry(82)[1]['Ix_strong_mm4'];E=f.DEFAULT_MATERIAL['E_MPa']
    # Independent closed form deflection of q and eccentric point force.
    def exact(x):
        uq=q*x*(L**3-2*L*x*x+x**3)/(24*E*I)
        b=L-a
        up=(P*b*x*(L*L-b*b-x*x)/(6*L*E*I) if x<=a else
            P*a*(L-x)*(L*L-a*a-(L-x)**2)/(6*L*E*I))
        return uq+up
    assert out['deflection_mm']==pytest.approx(exact(out['peak_x_mm']),rel=1e-8)
    assert abs(out['deflection_mm'])>=max(abs(exact(L*i/1000)) for i in range(1001))-1e-8


def test_pending_not_gross_fallback():
    with pytest.raises(OutsideMethod):s.section_at_moment(1,1.)
    with pytest.raises(OutsideMethod):s.section_at_moment(79,1e10)
    with pytest.raises(ValueError):s.section_at_moment(79,math.nan)
    with pytest.raises(ValueError):s.peak_deflection(79,L_mm=0)
    assert s.peak_deflection(79,L_mm=6000)['deflection_mm']==0


def test_low_service_does_not_require_full_web_at_yield(monkeypatch):
    original=s.strong_effective_modulus
    def restricted(p,g,m,stress):
        if stress>100.:raise OutsideMethod('Synthetic unavailable high-stress web')
        return original(p,g,m,stress)
    monkeypatch.setattr(s,'strong_effective_modulus',restricted)
    sec=s.section_at_moment(79,1e6)
    assert sec['stress_MPa']<100
    assert sec['root_bracket_MPa'][1]<100


def test_opposite_actions_three_stationary_points():
    out=s.peak_deflection(79,L_mm=6000.,q_Nmm=10.,P_N=-37500.,a_mm=3000.)
    candidates=[(x,d) for x,d in out['stationary_candidates'] if 0<x<6000]
    assert len(candidates)==3
    assert out['absolute_deflection_mm']==pytest.approx(.9209969,rel=2e-7)
    assert abs(next(d for x,d in candidates if abs(x-3000)<.01))<1e-7
