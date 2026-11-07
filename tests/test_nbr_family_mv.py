"""Scalar NBR-only checks; no solver/UI. Fractions are independent oracles."""
import copy
from fractions import Fraction as F
import json
import math
import pytest
from tercas import nbr_family_mv as mv
from tercas import nbr_ue_shear_lag as lag


def combo(q=2., p=8., a=3., weak_q=0., weak_p=0.):
    return dict(id='synthetic', limit_state='ELU', x_mm=a,
        q_vector=dict(normal=q, parallel=weak_q), P_vector=dict(normal=p, parallel=weak_p))


def equilibrium(c, L, x, after):
    q=F(c['q_vector']['normal']);p=F(c['P_vector']['normal']);L=F(L);a=F(c['x_mm'])
    ra=q*L/2+p*(L-a)/L
    return ra*x-q*x*x/2-(p*(x-a) if after else 0), ra-q*x-(p if after else 0)


def bernstein_value(control, u):
    n=len(control)-1
    return sum((b*math.comb(n,k)*u**k*(1-u)**(n-k) for k,b in enumerate(control)), F(0))


def assert_cover(e, c, L, mr, vr2):
    """Cover union plus 5 exact identities proves each full quartic bound."""
    start=F(0);uppers=[];lowers=[]
    for segment in e['envelope_certificate']:
        lo=F(segment['x_start_exact']);hi=F(segment['x_end_exact'])
        assert lo==start and hi>lo;start=hi
        cursor=F(0);leaf_bounds=[]
        for leaf in segment['leaves']:
            l=F(leaf['u_start_exact']);r=F(leaf['u_end_exact'])
            assert l==cursor and r>l;cursor=r
            control=list(map(F,leaf['bernstein_exact']))
            assert len(control)==5
            # Equality of quartics at five distinct exact points is an
            # identity, not merely sampling a claimed maximum.
            for v in (F(0),F(1,4),F(1,2),F(3,4),F(1)):
                u=l+(r-l)*v;x=lo+(hi-lo)*u
                m,shear=equilibrium(c,L,x,segment['after_P'])
                actual=m*m/F(mr)**2+shear*shear/vr2
                assert bernstein_value(control,v)==actual
            assert F(leaf['upper_exact'])==max(control)
            leaf_bounds.append(max(control))
        assert cursor==1
        witness=segment['witness'];x=F(witness['x_exact'])
        m,v=equilibrium(c,L,x,segment['after_P'])
        index=m*m/F(mr)**2+v*v/vr2
        assert F(witness['Mstrong_exact'])==m
        assert F(witness['Vweb_exact'])==v
        assert F(segment['maximum_lower_exact'])==index
        assert F(segment['maximum_upper_exact'])==max(leaf_bounds)
        assert not witness['witness_is_exact_maximum']
        lowers.append(index);uppers.append(max(leaf_bounds))
    assert start==L
    low,up=max(lowers),max(uppers)
    assert F(e['maximum_lower_exact'])==low<=up==F(e['maximum_upper_exact'])
    assert F(e['index_squared_lower'])<=low<=up<=F(e['index_squared_upper'])
    assert e['requested_gap_reached']
    assert up-low<=F(e['requested_relative_gap_exact'])*max(1,up)


@pytest.mark.parametrize('q,p',[(2.,8.),(-2.,-8.),(2.,-11.),(-2.,11.),(0.,0.),(0.,-10.),(2.,0.)])
@pytest.mark.parametrize('a',[0.,2.,3.25,5.,9.999,10.])
def test_exact_continuous_cover_concomitant_signed_loads_and_support_sides(q,p,a):
    c=combo(q,p,a)
    e=mv.interaction(c,10.,MRd_local_Nmm=40.,VRd_N=50.)
    assert_cover(e,c,10,40,F(2500))
    assert len(e['envelope_certificate'])==(1 if a in (0.,10.) else 2)
    assert not e['moving_point_position_envelope']
    assert not e['resistance_qualified'] and not e['whole_member_approved']


def test_one_sided_point_jump_and_no_addition_of_independent_maxima():
    c=combo(2.,8.,3.)
    e=mv.interaction(c,10.,MRd_local_Nmm=50.,VRd_N=20.)
    left,right=e['envelope_certificate']
    vl=list(map(F,left['Vweb_power_exact']));vr=list(map(F,right['Vweb_power_exact']))
    assert sum(vl)-vr[0]==8
    # Separate maximum M and maximum V occur elsewhere and may not be added.
    ra=F(78,5);x=(ra-8)/2
    maxm=equilibrium(c,10,x,True)[0]
    independent=maxm**2/2500+ra**2/400
    assert F(e['maximum_upper_exact'])<independent
    assert e['witness']['x_mm']==3. and e['witness']['side']=='left_limit'


def test_threshold_is_not_relaxed_by_numerical_gap_and_witness_not_claimed_maximum(monkeypatch):
    c=combo(2.,0.,10.)
    e=mv.interaction(c,10.,MRd_local_Nmm=25.,VRd_N=100.)
    assert e['maximum_lower_exact']==e['maximum_upper_exact']=='1'
    assert e['criterion_status']=='meets'
    c['q_vector']['normal']=math.nextafter(2.,math.inf)
    assert mv.interaction(c,10.,MRd_local_Nmm=25.,VRd_N=100.)['criterion_status']=='fails'
    monkeypatch.setattr(mv,'MAX_SUBDIVISIONS',0)
    e=mv.interaction(combo(2.,0.,10.),10.,MRd_local_Nmm=25.,VRd_N=100.)
    assert not e['requested_gap_reached'] and e['maximum_is_enclosed']
    assert e['index_squared_lower']<=1<e['index_squared_upper']
    assert e['criterion_status']=='boundary_inconclusive'


def test_zero_strong_does_not_borrow_weak_actions_or_require_missing_bending_capacity():
    c=combo(0.,0.,3.,weak_q=99.,weak_p=-300.)
    e=mv.interaction(c,10.,MRd_local_Nmm=None,VRd_N=1.)
    assert e['index_squared_upper']==0 and e['MRd_denominator_Nmm'] is None
    assert not e['weak_actions_identically_zero'] and not e['weak_shear_assessed']
    for a in (0.,10.):
        e=mv.interaction(combo(0.,1e9,a),10.,MRd_local_Nmm=None,VRd_N=1.)
        assert e['strong_moment_identically_zero'] and e['index_squared_upper']==0
    with pytest.raises(ValueError):mv.interaction(combo(0.,1.,3.),10.,MRd_local_Nmm=None,VRd_N=1.)


@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),0.,-1.])
@pytest.mark.parametrize('name',['MRd_local_Nmm','VRd_N'])
def test_invalid_resistance_rejected(name,value):
    args=dict(MRd_local_Nmm=40.,VRd_N=50.);args[name]=value
    with pytest.raises(ValueError):mv.interaction(combo(),10.,**args)


@pytest.mark.parametrize('mutation',[
    lambda c:c.update(x_mm=-1.),lambda c:c.update(x_mm=11.),
    lambda c:c['q_vector'].update(normal=True),lambda c:c['P_vector'].update(parallel=float('nan')),
])
def test_invalid_action_inventory_rejected(mutation):
    c=combo();mutation(c)
    with pytest.raises(ValueError):mv.interaction(c,10.,MRd_local_Nmm=40.,VRd_N=50.)


@pytest.mark.parametrize('mutation',[
    lambda e:e['envelope_certificate'][0]['leaves'].pop(),
    lambda e:e['envelope_certificate'][0]['leaves'][0]['bernstein_exact'].__setitem__(0,'0'),
    lambda e:e['witness'].update(index_squared_exact='0'),
    lambda e:e.update(index_squared_upper=0.),
    lambda e:e.update(whole_member_approved=True),
    lambda e:e.update(VRd_squared_exact='1'),
])
def test_arithmetic_tampering_cannot_be_resealed(mutation):
    c=combo();e=mv.interaction(c,10.,MRd_local_Nmm=40.,VRd_N=50.)
    mutation(e)
    with pytest.raises(ValueError):mv.validate_arithmetic(e,c,10.,MRd_local_Nmm=40.,VRd_N=50.)


def binding(h=125.,t=2.,ri=2.,E=200000.,fy=300.):
    return dict(nominal_identity=dict(dimensions_mm=dict(h=h,bf=50.,lip=17.,t=t),inner_radius_mm=ri),
        material=dict(E_MPa=E,G_MPa=77000.,fy_MPa=fy,nu=.3,gamma=1.1))


@pytest.mark.parametrize('flat,expected',[(40.,'yield'),(70.,'intermediate'),(100.,'elastic')])
def test_three_web_branches_exact_squared_normative_decimal_formula(flat,expected):
    b=binding(h=flat+4,t=1,ri=1);e=mv.web_capacity(b)
    if expected=='yield':sq=(F(3,5)*300*F(flat)/F(11,10))**2
    elif expected=='intermediate':sq=(F(13,20)/F(11,10))**2*5*300*200000
    else:sq=(F(181,200)*200000*5/F(flat)/F(11,10))**2
    assert e['branch']==expected and F(e['VRd_squared_exact'])==sq
    assert F(e['VRd_lower_N'])**2<=sq<=F(e['VRd_upper_N'])**2
    assert e['h_flat_mm']==flat and e['kv']==5 and e['gamma_normative_exact']=='11/10'


def test_exact_web_branch_boundaries_and_directed_square_root():
    # E*kv/fy=2500 gives exactly representable h/t boundaries 54 and70.
    for flat,branch in [(54.,'yield'),(math.nextafter(54.,math.inf),'intermediate'),
                         (70.,'intermediate'),(math.nextafter(70.,math.inf),'elastic')]:
        b=binding(h=flat+4,t=1,ri=1,E=150000.,fy=300.)
        assert mv.web_capacity(b)['branch']==branch
    for sq in (F(0),F(2),F(1,10**600),F(1,10**700)):
        lo=mv._sqrt_bound(sq,False);up=mv._sqrt_bound(sq,True)
        assert F(lo)**2<=sq<=F(up)**2


def family_fixture(index=26,L=6000.,q=1.,p=500.,a=2000.,with_gate=True,weak_p=0.):
    from tercas import nbr_ue_family as f
    own=f.assess(index,L_mm=L)
    c=combo(q,p,a,weak_p=weak_p)
    actions=[dict(kind='uniform',q_down_N_mm=q,q_parallel_N_mm=0.),
             dict(kind='point',P_down_N=p,P_parallel_N=weak_p,s_mm=a)]
    row=dict(combination_id=c['id'],limit_state='ELU',combination=c,actions=actions,
        components=[dict(route='own_rounded_contour',method='local',
            capacity_Nmm=own['strong']['local']['MRd_Nmm'],index=.1)])
    if with_gate:
        row['shear_lag_applicability']=lag.assess(physical_span_mm=L,
            external_dimensions_mm=own['source_binding']['nominal_identity']['dimensions_mm'],
            actions=actions,member_model='isolated_simply_supported')
    return row,dict(own_rounded_contour=own)


def test_build_selects_local_mle_without_Ml_and_ignores_other_denominators():
    row,sources=family_fixture(79)
    assert 'Ml_Nmm' not in sources['own_rounded_contour']['strong']['local']
    row['components'] += [dict(route='published_nominal_reference',method='local',capacity_Nmm=1e30,index=0.),
        dict(route='own_rounded_contour',method='FLT_reference',capacity_Nmm=1.,index=999.),
        dict(route='own_rounded_contour',method='distortional',capacity_Nmm=1.,index=999.)]
    e=mv.build(row,sources,6000.)
    assert e['status']=='component_computed'
    assert e['arithmetic']['MRd_denominator_Nmm']==sources['own_rounded_contour']['strong']['local']['MRd_Nmm']
    assert e['arithmetic']['VRd_squared_exact']==e['NBR_web_capacity']['VRd_squared_exact']
    assert not e['FLT_distortional_denominator_used'] and not e['EN_capacity_used']
    assert not e['complete_interaction_qualified'] and not e['whole_member_approved']
    assert e['criterion_status'] in ('meets','fails')


@pytest.mark.parametrize('with_gate',[True,False])
def test_absent_or_unqualified_gate_never_proves_failure(with_gate):
    row,sources=family_fixture(L=1500.,p=1e6,a=500.,with_gate=with_gate)
    e=mv.build(row,sources,1500.)
    assert e['status']=='pending_section94_qualification' and e['criterion_status'] is None
    assert e['arithmetic']['criterion_status']=='fails'  # diagnostic only
    assert not e['section94_qualified']


def test_only_active_strong_axis_gate_needed_and_saved_gate_replayed():
    row,sources=family_fixture(L=3000.,a=1000.,weak_p=500.)
    gate=row['shear_lag_applicability']
    assert gate['axes']['normal']['qualified'] and not gate['axes']['parallel']['qualified']
    e=mv.build(row,sources,3000.)
    assert e['status']=='component_computed' and not e['arithmetic']['weak_shear_assessed']
    gate['axes']['normal']['qualified']=False
    with pytest.raises(ValueError):mv.build(row,sources,3000.)


def test_no_strong_moment_no_local_demand_or_shear_lag_gate_needed():
    row,sources=family_fixture(L=1500.,q=0.,p=0.,a=500.,weak_p=500.,with_gate=False)
    row['components'][0].update(index=None,capacity_Nmm=None)
    sources['own_rounded_contour']['strong']['local'].update(eligible=False,MRd_Nmm=None)
    e=mv.build(row,sources,1500.)
    assert e['criterion_status']=='meets' and e['section94_not_required_for_identically_zero_moment']
    assert e['arithmetic']['MRd_denominator_Nmm'] is None
    assert not e['weak_shear_assessed'] and not e['primary_torsion_assessed']


@pytest.mark.parametrize('change',['capacity','index','lower_only','source','duplicate','ELU','identity','span','gamma'])
def test_consumer_source_domain_and_local_qualification_fail_closed(change):
    row,sources=family_fixture();part=row['components'][0];own=sources['own_rounded_contour']
    if change=='capacity':part['capacity_Nmm']*=2
    elif change=='index':part['index']=None
    elif change=='lower_only':part['capacity_lower_bound_only']=True
    elif change=='source':own['strong']['local']['eligible']=False
    elif change=='duplicate':row['components'].append(copy.deepcopy(part))
    elif change=='ELU':row['combination']['limit_state']='ELS'
    elif change=='identity':row['combination_id']='wrong'
    elif change=='span':own['physical_span_mm']=1.
    elif change=='gamma':own['source_binding']['material']['gamma']=1.
    if change in ('capacity','index','lower_only','source'):
        e=mv.build(row,sources,6000.)
        assert e['criterion_status'] is None and e['arithmetic'] is None
        assert e['web_shear']['criterion_status'] in ('meets','fails')
    else:
        with pytest.raises(ValueError):mv.build(row,sources,6000.)


def test_json_roundtrip_replay_immutability_and_rehashed_change_rejected():
    row,sources=family_fixture();before=copy.deepcopy((row,sources))
    e=mv.build(row,sources,6000.)
    assert (row,sources)==before
    assert mv.validate_saved(json.loads(json.dumps(e)),row,sources,6000.)==e
    e['criterion_status']='forged'
    with pytest.raises(ValueError):mv.validate_saved(e,row,sources,6000.)


# No frame, eigenproblem or UI is run. Family sources are the existing scalar
# analytical provider over the documentary-complete nominal contour catalogue.
from tercas.pierin_ue_registry import new_study_indices
@pytest.mark.parametrize('index',new_study_indices())
def test_complete_family66_has_own_local_and_web_denominator(index):
    row,sources=family_fixture(index,q=1.,p=-1800.,a=2000.)
    e=mv.build(row,sources,6000.)
    assert len(new_study_indices())==66
    assert e['status']=='component_computed'
    assert e['criterion_status'] in ('meets','fails')
    assert e['arithmetic']['requested_gap_reached']
    assert e['source_binding']==sources['own_rounded_contour']['source_binding']
    assert e['NBR_web_capacity']['VRd_lower_N']>0
    assert not e['nominal_reference_mixed'] and not e['whole_member_approved']


def test_web_shear_top_record_is_independent_of_section94_gate():
    row,sources=family_fixture(L=1500.,p=1e6,a=500.)
    e=mv.build(row,sources,1500.)
    assert e['criterion_status'] is None
    assert e['web_shear']==e['arithmetic']['web_shear']
    assert e['web_shear']['criterion_status']=='fails'
    assert not e['web_shear']['torsional_shear_included']
    row['components'][0]['index']=None
    pending=mv.build(row,sources,1500.)
    assert pending['arithmetic'] is None and pending['criterion_status'] is None
    assert pending['web_shear']==e['web_shear']
