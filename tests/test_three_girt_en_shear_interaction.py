import json
import math
from pathlib import Path
import numpy as np
import pytest
from tercas.three_girt_en_normal import shear_interaction as si
from tercas.three_girt_en_normal.en1993_normal_components import build_component_sections
from tercas.torsion_vlasov.section import from_frozen_profile


def setup(t=2.65):
    path=Path(__file__).parents[1]/'tercas/data/torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
    profile=json.loads(path.read_text());section=from_frozen_profile(profile)
    cert=build_component_sections(profile)
    coeff={key:cert['components'][name]['sigma_coefficients_c0_cx_cy']
        for key,name in [('N','N_tension'),('Mx','Mx_positive'),('My','My_positive')]}
    return section,coeff


def test_bernstein_power_conversion_and_convex_hull():
    rng=np.random.default_rng(47)
    for _ in range(50):
        c=rng.normal(size=(3,3));a,b=sorted(rng.uniform(size=2));be=si._bernstein(c,a,b)
        for v in np.linspace(0,1,11):
            u=a+(b-a)*v;direct=np.array([1,u,u*u])@c
            value=np.array([(1-v)**2,2*v*(1-v),v*v])@be
            np.testing.assert_allclose(value,direct,atol=2e-14)
            assert np.linalg.norm(value)<=max(map(np.linalg.norm,be))+2e-14


def test_surface_Saint_Venant_sign_from_positive_torque():
    section,c=setup();zero=dict(N=[0.],Mx=[0.],My=[0.]);torsion=dict(h=0.,B0=0.,U=0.,V=0.)
    fields,tw=si.section_fields(section,zero,c,torsion,[10000.,0.],1000.)
    # Horizontal +x wall: +normal is +y, tau_x=-2 G phi' y, -y*tau_x>0.
    row=next(r for r in fields if r['face']==1 and r['normal_xy'][1]>.99)
    _,tau=si._evaluate(row,torsion,tw,.5,.5)
    assert tau<0
    assert tau==pytest.approx(-10000*section['thickness_mm']/section['properties']['J_mm4'])
    opposite=next(r for r in fields if r['face']==-1 and r['segment_index']==row['segment_index'])
    assert si._evaluate(opposite,torsion,tw,.5,.5)[1]==pytest.approx(-tau)


def test_constant_pure_torsion_limits_and_both_faces():
    s,c=setup();th=s['thickness_mm'];J=s['properties']['J_mm4'];desired=50.
    r=si.envelope(s,dict(N=[0.],Mx=[0.],My=[0.]),c,
        dict(h=0.,B0=0.,U=0.,V=0.),[desired*J/th],1000.)
    assert r['section_facets']==208 and r['faces_per_facet']==2
    assert r['shear']['index_lower_witness']==pytest.approx(desired/(250/math.sqrt(3)))
    assert r['interaction']['index_lower_witness']==pytest.approx(math.sqrt(3)*desired/275)
    assert r['shear']['criterion']=='within_1_by_full_interval_upper_bound'
    assert r['shear']['index_upper_bound']>=r['shear']['index_lower_witness']
    assert r['refinements']==0


def test_bounds_cover_dense_same_fiber_stress_and_interior_wall_peak():
    s,c=setup();polys=dict(N=[1300.],Mx=[6e4,-7e4,4e4],My=[2e4,5e4,-3e4])
    torsion=dict(h=1.7,B0=2e5,U=-3e5,V=4e5);T=[12000.,-17000.];L=1800.
    r=si.envelope(s,polys,c,torsion,T,L)
    fields,tw=si.section_fields(s,polys,c,torsion,T,L)
    peaks={'shear':0.,'interaction':0.}
    for row in fields:
        for x in np.linspace(0,1,13):
            for u in np.linspace(0,1,9):
                sigma,tau=si._evaluate(row,torsion,tw,x,u)
                peaks['shear']=max(peaks['shear'],abs(tau)/r['shear_limit_MPa'])
                peaks['interaction']=max(peaks['interaction'],math.hypot(sigma,math.sqrt(3)*tau)/r['equivalent_limit_MPa'])
    for key in peaks:
        assert peaks[key]<=r[key]['index_upper_bound']+1e-12
        w=r[key]['witness'];row=next(v for v in fields if v['segment_index']==w['segment_index'] and v['face']==w['thickness_face_sign'])
        sigma,tau=si._evaluate(row,torsion,tw,w['t'],w['u'])
        assert sigma==pytest.approx(w['sigma_MPa']) and tau==pytest.approx(w['tau_MPa'])
    xy=np.asarray(s['nodes_xy_mm'])-s['properties']['centroid_xy_mm']
    x,y=(xy[100]+xy[101])/2
    ratio=-y*s['properties']['Iy_weak_mm4']/(x*s['properties']['Ix_strong_mm4'])
    vr=si.envelope(s,dict(N=[0.],Mx=[0.,1e6],My=[0.,-1e6*ratio]),c,
        dict(h=0.,B0=0.,U=0.,V=0.),[0.],1000.)
    assert 0<vr['shear']['witness']['u']<1


def test_budget_exhaustion_and_partial_coverage_cannot_pass():
    s,c=setup();polys=dict(N=[0.],Mx=[0.,1e6],My=[0.]);tor=dict(h=0.,B0=0.,U=0.,V=0.)
    seed=si.envelope(s,polys,c,tor,[10000.,-10000.],1000.)
    low=seed['interaction']['index_lower_witness'];hi=seed['interaction']['index_upper_bound'];assert hi>low
    factor=2/(low+hi);scaled={k:[factor*v for v in p] for k,p in polys.items()}
    r=si.envelope(s,scaled,c,tor,[factor*10000.,-factor*10000.],1000.,max_refinements=0)
    assert r['interaction']['index_lower_witness']<1<r['interaction']['index_upper_bound']
    assert r['interaction']['criterion']=='unresolved_numerical_bound'
    partial=si.aggregate([seed,None],False);assert partial['complete'] is False
    for key in ('shear','interaction'):
        assert partial[key]['index_upper_bound'] is None
        assert partial[key]['criterion']!='within_1_by_full_interval_upper_bound'


def test_load_scaling_and_reversal_preserve_bounds():
    s,c=setup();p=dict(N=[200.],Mx=[3000.,15000.,-12000.],My=[4000.,-2000.]);tor=dict(h=2.,B0=14000.,U=-9000.,V=5000.)
    a=si.envelope(s,p,c,tor,[2000.,-2500.],1200.);factor=-7.
    b=si.envelope(s,{k:[factor*v for v in arr] for k,arr in p.items()},c,
        {k:v if k=='h' else factor*v for k,v in tor.items()},[factor*2000.,factor*-2500.],1200.)
    for key in ('shear','interaction'):
        assert b[key]['index_lower_witness']==pytest.approx(7*a[key]['index_lower_witness'],rel=2e-12)
        assert b[key]['index_upper_bound']==pytest.approx(7*a[key]['index_upper_bound'],abs=2e-12)
