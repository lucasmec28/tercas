"""Small, coordinated real member solve suite; no large family matrix."""
import math
import pytest
from tercas import isolated_service_mechanics as m
from tercas.torsion_vlasov.vlasov import solve_member
from test_isolated_service_mechanics import synthetic,DIMS,CFG


@pytest.mark.parametrize('where,qx,qy',[('sc',0.,-.002),('top',0.,-.002),('top',.001,-.002),('top',-.001,.002)])
def test_same_field_member_vs_independent_uniform_midspan(where,qx,qy):
    s=synthetic()['section'];p=s['properties'];L=3000.;E=200000.;G=E/2.6
    location=p['shear_center_xy_mm'] if where=='sc' else [0.,100.-1.5/2]
    a=solve_member(section=s,length_mm=L,E_MPa=E,G_MPa=G,
        actions=[dict(name='uniform',kind='uniform',q_xy_N_mm=[qx,qy],couple_N=0.,application_xy_mm=location,origin='Synthetic source')],
        supports={side:dict(twist='fixed',warping='free_assumed',origin='Synthetic ideal fork') for side in ('left','right')},
        combination_id='REAL_SLS',limit_state='ELS',member_id='PURLIN',action_accounting_origin='Synthetic check',elements_per_interval=32)
    check=m.calculate(a,DIMS,250.,CFG,20.)
    assert check['gross_screen']['gross_local_normal_sufficient']
    # Independent uniform-load exact ODE solution at midspan, at the CG point.
    torque=(location[0]-p['shear_center_xy_mm'][0])*qy-(location[1]-p['shear_center_xy_mm'][1])*qx
    S=G*p['J_mm4'];D=E*p['Cw_mm6'];k=math.sqrt(S/D)
    phi=torque/S*(L*L/8-(1-1/math.cosh(k*L/2))/(k*k))
    flex=5*(-qy)*L**4/(384*E*p['Ix_strong_mm4'])
    expected=abs(flex-(p['centroid_xy_mm'][0]-p['shear_center_xy_mm'][0])*phi)
    actual=check['envelope']['abs_displacement_lower_mm']
    # Numerical FE demand is not claimed to bound the exact continuum solution.
    assert math.isclose(actual,expected,rel_tol=3e-6,abs_tol=1e-8)
    assert check['envelope']['converged'] and check['index_upper']<1
    assert not check['combined_ELS_approved']
