"""Independent ODE, exact integration, energy, load-path and rejection controls."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tercas.torsion_vlasov.section import load_profile,from_frozen_profile,section_demands
from tercas.torsion_vlasov.vlasov import solve_member,evaluate,matrix,resolve_actions,NumericalQualificationError,_qualify_numerics
from vlasov_reference import Problem,ExactStateReference,element_matrices

THICKNESSES=[1.20,1.50,2.00,2.25,2.65,3.00,3.35]


def section(t=1.2):return load_profile(ROOT/f'tercas/data/torsion_profiles/ue100x50x17_t{t:.2f}.json')


def supports(left='free_assumed',right='free_assumed'):
    return {end:dict(twist='fixed',warping=bc,origin='Explicit synthetic benchmark, not construction')
            for end,bc in [('left',left),('right',right)]}


def uniform(s, q=(0.,0.), m=.2, at=None, name='uniform'):
    return dict(name=name,kind='uniform',q_xy_N_mm=list(q),couple_N=m,
                application_xy_mm=at or s['properties']['shear_center_xy_mm'],origin='synthetic control')


def point(s, a=2000., F=(0.,0.), T=1000., at=None, name='point'):
    return dict(name=name,kind='point',force_xy_N=list(F),couple_Nmm=T,s_mm=a,
                application_xy_mm=at or s['properties']['shear_center_xy_mm'],origin='synthetic control')


def run(s=None,L=4000.,actions=None,bc=None,n=32):
    s=s or section();actions=actions or [uniform(s)]
    return solve_member(section=s,length_mm=L,E_MPa=200000.,G_MPa=200000./2.6,actions=actions,
        supports=bc or supports(),combination_id='REF',limit_state='REFERENCE',member_id='P1',
        action_accounting_origin='Complete synthetic action set',elements_per_interval=n)


@pytest.mark.parametrize('t',THICKNESSES)
def test_frozen_section_and_normal_shear_resultant_recovery(t):
    s=section(t);rng=np.random.default_rng(721+int(t*100))
    for j in range(4):
        N,Mx,My,Vx,Vy,Tsv,Tw,B=rng.normal(size=8)*[1e3,1e5,1e5,1e3,1e3,1e4,1e4,1e7]
        d=section_demands(s,N_N=N,Mx_Nmm=Mx,My_Nmm=My,Vx_N=Vx,Vy_N=Vy,Tsv_Nmm=Tsv,Tw_Nmm=Tw,B_Nmm2=B)
        np.testing.assert_allclose(d['recovered_normal_N_Mx_My_B'],[N,Mx,My,B],rtol=2e-11,atol=1e-6)
        np.testing.assert_allclose(d['recovered_flow_Vx_Vy_Tw'],[Vx,Vy,Tw],rtol=2e-11,atol=1e-6)
        assert not d['resistance_qualified'] and not d['whole_member_approved']


def test_matrix_independent_gauss_energy():
    rng=np.random.default_rng(812)
    for _ in range(40):
        L=10.**rng.uniform(1,4);S=10.**rng.uniform(5,9);D=10.**rng.uniform(10,16)
        ke,fe=element_matrices(L,S,D,m_left=.4,m_right=.4)
        np.testing.assert_allclose(matrix(L,S,D),ke,rtol=2e-14,atol=2e-8)
        np.testing.assert_allclose(fe,.4*np.array([L/2,L*L/12,L/2,-L*L/12]),rtol=2e-14)


@pytest.mark.parametrize('bc',[
    ('free_assumed','free_assumed'),('restrained_assumed','restrained_assumed'),
    ('free_assumed','restrained_assumed'),('restrained_assumed','free_assumed')])
@pytest.mark.parametrize('kind',['uniform','point','combined'])
def test_ode_reference_and_refinement(bc,kind):
    s=section();L=4000.;actions=[]
    if kind!='point':actions.append(uniform(s,m=.2))
    if kind!='uniform':actions.append(point(s,a=1500.,T=1000.))
    resolved=resolve_actions(s,L,actions);m=sum(a.get('torque_SC_N',0) for a in resolved)
    pp=tuple((a['s_mm']/L,a['torque_SC_Nmm'],0.) for a in resolved if a['kind']=='point')
    p=Problem(length=L,S=200000/2.6*s['properties']['J_mm4'],D=200000*s['properties']['Cw_mm6'],
              m0=m,warping=tuple('free' if b=='free_assumed' else 'restrained' for b in bc),point_actions=pp)
    oracle=ExactStateReference(p)
    errors=[]
    for n in (8,16,32):
        r=run(s,L,actions,supports(*bc),n);ratios=[]
        for i,e in enumerate(r['elements']):
            for u in (0.,.2113248654,.5,.7886751346,1.):
                actual=evaluate(r,i,u);exact=oracle.at(actual['s_mm'],side='left' if actual['side']=='left' else 'right')
                scaled=[]
                for key,ref,scale in [('phi_rad','phi',1.),('psi_per_mm','psi',L),
                                     ('B_Nmm2','B',L*L/p.D),('T_Nmm','T',L**3/p.D),
                                     ('Tsv_Nmm','Tsv',L**3/p.D),('Tw_Nmm','Tw',L**3/p.D)]:
                    scaled.append(abs(actual[key]-exact[ref])*scale)
                ratios.append(max(scaled))
        errors.append(max(ratios))
        assert r['numerics']['relative_energy_error']<2e-7
        assert r['numerics']['scaled_free_residual']<2e-7
        assert abs(r['support_reactions']['torque_equilibrium_residual_Nmm'])<1e-4
    assert errors[-1]<2e-5
    assert errors[-1]<errors[0]/15


@pytest.mark.parametrize('t',THICKNESSES)
def test_uniform_free_closed_form_profile(t):
    s=section(t);r=run(s,n=64);L=r['length_mm'];m=.2
    S=r['G_MPa']*s['properties']['J_mm4'];D=r['E_MPa']*s['properties']['Cw_mm6'];k=math.sqrt(S/D)
    x=L/2
    phi=m/S*(x*(L-x)/2+(1/math.cosh(k*L/2)-1)/k**2)
    B=m*D/S*(1-1/math.cosh(k*L/2))
    z=evaluate(r,32,0.)
    assert math.isclose(z['phi_rad'],phi,rel_tol=3e-7)
    assert math.isclose(z['B_Nmm2'],B,rel_tol=3e-7)
    assert abs(evaluate(r,0,0.)['B_Nmm2'])<1e-3
    assert abs(evaluate(r,63,1.)['B_Nmm2'])<1e-3


def test_point_action_jumps_and_concomitant_bending():
    s=section();cg=s['properties']['centroid_xy_mm']
    act=[uniform(s,q=(.13,-.22),m=.1,at=cg),point(s,a=1500.,F=(400,-900),T=1200,at=cg)]
    r=run(s,actions=act,n=8);li=next(i for i,e in enumerate(r['elements']) if e['b_mm']==1500.)
    a=evaluate(r,li,1.);b=evaluate(r,li+1,0.);load=r['loads'][1]
    assert math.isclose(b['T_Nmm']-a['T_Nmm'],-load['torque_SC_Nmm'],rel_tol=2e-10)
    assert abs(b['B_Nmm2']-a['B_Nmm2'])<1e-3
    assert abs(b['phi_rad']-a['phi_rad'])<1e-12
    assert abs(b['psi_per_mm']-a['psi_per_mm'])<1e-12
    np.testing.assert_allclose([b['Vx_N']-a['Vx_N'],b['Vy_N']-a['Vy_N']],[-400,900],atol=1e-9)
    np.testing.assert_allclose([b['Mx_physical_Nmm'],b['My_physical_Nmm']],
                               [a['Mx_physical_Nmm'],a['My_physical_Nmm']],atol=1e-8)
    assert a['side']=='left' and b['side']=='right' and a['element_id']!=b['element_id']


def test_PP_CG_generates_torsion_when_perpendicular_to_SC_CG():
    s=section();cg=s['properties']['centroid_xy_mm'];sc=s['properties']['shear_center_xy_mm']
    vertical=run(s,actions=[uniform(s,q=(0,-.02),m=0,at=cg,name='self_weight')])
    alongsymmetry=run(s,actions=[uniform(s,q=(.02,0),m=0,at=cg,name='self_weight')])
    throughSC=run(s,actions=[uniform(s,q=(0,-.02),m=0,at=sc)])
    assert abs(vertical['max_abs_phi']['phi_rad'])>.01
    assert abs(alongsymmetry['max_abs_phi']['phi_rad'])<1e-14
    assert abs(throughSC['max_abs_phi']['phi_rad'])<1e-14
    rr=vertical['support_reactions']
    assert abs(rr['left_generalized_torque_at_CG_Nmm'])<1e-3
    assert abs(rr['right_generalized_torque_at_CG_Nmm'])<1e-3
    assert abs(rr['left_total_moment_about_SC_Nmm'])>1000


def test_distinct_lines_do_not_collapse_to_resultant_at_CG():
    s=section();cg=s['properties']['centroid_xy_mm']
    a=uniform(s,q=(0,-.2),m=0,at=cg,name='CP')
    b=uniform(s,q=(0,.2),m=0,at=[cg[0]+30,cg[1]],name='wind')
    r=run(s,actions=[a,b]);assert abs(r['max_abs_phi']['phi_rad'])>.01
    assert max(abs(z['Mforte_R01_Nmm']) for z in r['critical_states'])==0


def test_load_reversal_and_input_isolation():
    s=section();a=[uniform(s,q=(.1,-.2),m=.03),point(s,a=1700.,F=(40,-50),T=300)]
    old=copy.deepcopy((s,a));r=run(s,actions=a);inv=copy.deepcopy(a)
    for x in inv:
        if x['kind']=='uniform':x['q_xy_N_mm']=[-v for v in x['q_xy_N_mm']];x['couple_N']*=-1
        else:x['force_xy_N']=[-v for v in x['force_xy_N']];x['couple_Nmm']*=-1
    z=run(s,actions=inv)
    np.testing.assert_allclose(z['node_phi_rad'],-np.array(r['node_phi_rad']),rtol=1e-12,atol=1e-14)
    assert (s,a)==old
    r['loads'][0]['q_xy_N_mm'][0]=123;r['section']['properties']['A_mm2']=123
    assert (s,a)==old


@pytest.mark.parametrize('station',[0.,4000.])
def test_force_or_torque_applied_at_fixed_endpoint_does_not_deform_span(station):
    s=section();r=run(s,actions=[point(s,a=station,F=(100,-300),T=500)],n=8)
    assert max(abs(x) for x in r['node_phi_rad'])==0.
    assert max(abs(z['Mx_physical_Nmm']) for z in r['critical_states'])<1e-8
    assert max(abs(z['My_physical_Nmm']) for z in r['critical_states'])<1e-8


def test_undeclared_warping_rejected_not_repaired_from_twist():
    bc=supports();del bc['left']['warping']
    with pytest.raises(ValueError,match='warping'):run(bc=bc)


def test_mixed_geometry_properties_rejected():
    s=section();s['properties']['Cw_mm6']*=1.01
    with pytest.raises(ValueError,match='section changed'):run(s)
    p=json.loads((ROOT/'tercas/data/torsion_profiles/ue100x50x17_t1.20.json').read_text());p['own_properties']['J_mm4']*=1.01
    with pytest.raises(ValueError,match='property'):from_frozen_profile(p)


@pytest.mark.parametrize('field',['origin','application_xy_mm','couple_N'])
def test_missing_action_information_rejected(field):
    s=section();a=uniform(s);del a[field]
    with pytest.raises(ValueError):run(s,actions=[a])


def test_cannot_promote_small_rotation_to_design_approval():
    s=section();r=run(s,actions=[uniform(s,m=1e-9)])
    assert not r['small_rotation_warning']
    assert not r['coverage_complete'] and not r['whole_member_approved']
    assert not r['physical_design_approved'] and not r['resistance_qualified']


def test_source_copies_unchanged():
    from tercas.torsion_study import PINS
    for t,digest in PINS.items():
        assert hashlib.sha256((ROOT/f'tercas/data/torsion_profiles/ue100x50x17_t{t:.2f}.json').read_bytes()).hexdigest()==digest
    assert hashlib.sha256((ROOT/'tests/vlasov_reference.py').read_bytes()).hexdigest()=='4f0d9533cff53a89ea289ccd8c239122343be8bf440f0d76c69a61de627c7e79'
    assert hashlib.sha256((ROOT/'tercas/torsion_vlasov/bounded_polynomial.py').read_bytes()).hexdigest()=='2dc3f67ee5c7a8ddee18f9e9b77102432348dd2339e8523a698b6bc78768b2b4'


@pytest.mark.parametrize('bc',[
    ('free_assumed','free_assumed'),('restrained_assumed','restrained_assumed'),
    ('free_assumed','restrained_assumed'),('restrained_assumed','free_assumed')])
def test_finite_tiny_load_intervals_rejected_not_promoted_to_support_limit(bc):
    s=section(1.5)
    for a in (1.,.01,.0001,4000.-.01):
        with pytest.raises(NumericalQualificationError,match='L/100'):
            run(s,actions=[uniform(s),point(s,a=a)],bc=supports(*bc))
    # Coincident loads at exactly one station are legitimate superposition.
    r=run(s,actions=[uniform(s),point(s,a=2000),point(s,a=2000,name='P2')],bc=supports(*bc))
    assert r['numerics']['qualification_passed']


@pytest.mark.parametrize('tamper',['internal_torque','internal_bimoment','global_equilibrium','free_end_B'])
def test_numerical_gate_detects_loss_hidden_by_small_linear_residual(tamper):
    r=run(n=8);r['numerics']['scaled_free_residual']=0.;r['numerics']['relative_energy_error']=0.
    if tamper=='internal_torque':r['elements'][3]['coefficients']['T_Nmm'][0]+=100
    elif tamper=='internal_bimoment':r['elements'][3]['coefficients']['B_Nmm2'][0]+=1e6
    elif tamper=='global_equilibrium':r['support_reactions']['torque_equilibrium_residual_Nmm']=100
    else:r['elements'][0]['coefficients']['B_Nmm2'][0]+=1e6
    with pytest.raises(NumericalQualificationError,match='qualification failed'):_qualify_numerics(r)
