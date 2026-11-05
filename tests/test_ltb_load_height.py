import math
import copy
import numpy as np
import pytest
from tercas.ltb_load_height import solve,closed_form,refined,action_terms,maximum_moment

UE=dict(L_mm=5500.,E_MPa=200000.,G_MPa=77000.,Iweak_mm4=157600.,J_mm4=600.,Cw_mm6=381650000.)
PAPER=dict(L_mm=4000.,E_MPa=210000.,G_MPa=210000/2.6,Iweak_mm4=59951.,J_mm4=418.,Cw_mm6=86149594.)

def udl(q=.94,h=50.,ex=30.,name='q'):
    return dict(name=name,kind='uniform',q_down_N_mm=q,height_above_SC_mm=h,x_from_SC_mm=ex)

def point(P=1000.,h=50.,ex=30.,s=2000.,name='P'):
    return dict(name=name,kind='point',P_down_N=P,height_above_SC_mm=h,x_from_SC_mm=ex,s_mm=s)

def me(actions,p=UE,n=32):return solve(**p,actions=actions,modes=n)['Me_Nmm']

@pytest.mark.parametrize('sign',[-1,1])
def test_uniform_moment_exact_nbr(sign):
    p=UE;L=p['L_mm'];E=p['E_MPa'];G=p['G_MPa'];I=p['Iweak_mm4'];J=p['J_mm4'];Cw=p['Cw_mm6']
    expected=math.pi/L*math.sqrt(E*I*(G*J+math.pi**2*E*Cw/L**2))
    for n in [1,4,16,32]:
        actual=solve(**p,actions=[],constant_end_moment_Nmm=sign,modes=n)
        assert actual['Me_Nmm']==pytest.approx(expected,rel=3e-13)

@pytest.mark.parametrize('h,rounded',[(0,.61),(30,.52),(-30,.72)])
def test_published_channel_four_point_benchmark(h,rounded):
    actions=[point(P=1.,h=h,s=s,name=str(s)) for s in [1000.,3000.]]
    actual=refined(**PAPER,actions=actions)
    assert actual['numerically_converged']
    assert round(actual['Me_Nmm']/1e6,2)==rounded
    formula=closed_form(**PAPER,C1=1.04,C2=.42,zg_mm=h)
    assert actual['Me_Nmm']==pytest.approx(formula,rel=.007)
    assert actual['production_resistance_authorized'] is False

def test_height_suction_gravity():
    top=me([udl()]);zero=me([udl(h=0)]);bottom=me([udl(h=-50)])
    assert top<zero<bottom
    assert me([udl(q=-.94)])==pytest.approx(bottom,rel=2e-13)
    assert me([udl(q=-.94,h=-50)])==pytest.approx(top,rel=2e-13)

def test_primary_torque_changes_not_linear_eigenvalue():
    a=solve(**UE,actions=[udl(ex=0)])
    b=solve(**UE,actions=[udl(ex=100)])
    assert a['Me_Nmm']==b['Me_Nmm']
    assert a['primary_torque_by_action'][0]['value']==0
    assert b['primary_torque_by_action'][0]['value']==-94
    assert b['primary_torsion_predeformation_included'] is False

@pytest.mark.parametrize('factor',[.1,1,10,1000])
def test_load_scaling(factor):
    a=[udl(),point()];b=[udl(q=.94*factor),point(P=1000*factor)]
    r=solve(**UE,actions=a);s=solve(**UE,actions=b)
    assert s['lambda_cr']*factor==pytest.approx(r['lambda_cr'],rel=1e-12)
    assert s['Me_Nmm']==pytest.approx(r['Me_Nmm'],rel=1e-12)

def test_pp_must_not_move_to_top():
    # Same net q and same moment: different heights => different elastic Me.
    separate=[udl(q=.8,h=50,name='roof'),udl(q=.14,h=0,name='PP')]
    collapsed=[udl(q=.94,h=50)]
    assert me(separate)>me(collapsed)
    weighted=[udl(q=.94,h=.8*50/.94)]
    assert me(separate)==pytest.approx(me(weighted),rel=5e-13)

def test_opposite_loads_do_not_classify_from_net_q():
    # q_net<0 but destabilizing height term is positive: signs per action matter.
    a=[udl(q=1,h=50,name='roof'),udl(q=-2,h=0,name='control')]
    assert me(a)<me([udl(q=-1,h=0)])

def test_zero_net_bending_rotational_load_is_not_me_zero():
    r=solve(**UE,actions=[udl(q=1,h=50,name='top'),udl(q=-1,h=0,name='zero')])
    assert r['status']=='rotational_eigenvalue_without_reference_bending'
    assert r['lambda_cr']>0 and r['Me_Nmm'] is None

def test_load_position_reflection():
    a=[udl(),point(s=1357)]
    b=[udl(),point(s=5500-1357)]
    assert me(a)==pytest.approx(me(b),rel=1e-12)

def test_load_at_fork_has_no_height_effect():
    a=[udl(h=0),point(s=0,h=10000)]
    b=[udl(h=0)]
    assert me(a)==pytest.approx(me(b),rel=1e-12)

@pytest.mark.parametrize('s',[0.,5500.])
def test_load_exactly_at_fork_never_uses_sin_pi_roundoff(s):
    r=solve(**UE,actions=[point(P=1e20,h=1e20,s=s)])
    assert r['status']=='no_positive_eigenvalue'

def test_mixed_moment_extremum_interior():
    L=5500.;a=[udl(q=-.5,h=0),point(P=1000,s=1200)]
    loads=action_terms(a,L);actual=maximum_moment(L,loads,0.)
    x=np.linspace(0,L,100001)
    from tercas.ltb_load_height import moment_values
    dense=max(abs(moment_values(x,L,loads,0.)))
    assert actual>=dense-1e-8 and actual-dense<.01

def test_pure_zero_load_no_positive_eigenvalue():
    r=solve(**UE,actions=[udl(q=0)])
    assert r['lambda_cr'] is None and r['Me_Nmm'] is None

@pytest.mark.parametrize('key,value',[('L_mm',0),('E_MPa',True),('G_MPa',float('inf')),
    ('Iweak_mm4',float('nan')),('J_mm4',-1),('Cw_mm6','1')])
def test_bad_section_input(key,value):
    p=dict(UE);p[key]=value
    with pytest.raises(ValueError):solve(**p,actions=[udl()])

@pytest.mark.parametrize('edit',[{'q_down_N_mm':True},{'height_above_SC_mm':None},
    {'x_from_SC_mm':float('inf')},{'name':''},{'kind':'triangular'}])
def test_bad_action_input(edit):
    a=udl();a.update(edit)
    with pytest.raises(ValueError):solve(**UE,actions=[a])

@pytest.mark.parametrize('s',[-1,5501])
def test_point_outside(s):
    with pytest.raises(ValueError):solve(**UE,actions=[point(s=s)])

def test_no_mutation():
    a=[udl(),point()];before=copy.deepcopy(a)
    refined(**UE,actions=a)
    assert a==before

def test_no_fabricated_lower_bound_or_approval():
    r=refined(**UE,actions=[udl()])
    assert r['numerically_converged'] and not r['convergence_is_error_bound']
    assert not r['ritz_eigenvalue_is_safe_lower_bound']
    assert not r['whole_member_approved'] and not r['production_resistance_authorized']
