"""Consumer selection with explicit synthetic authenticated-component stand-ins."""
import copy
import pytest
from tercas import nbr_family_member as member
from test_nbr_family_biaxial import combo


def fixture(qy=4.):
    methods={'local':120.,'FLT_reference':90.,'distortional':100.,
             'FLT_height_effective_reference':70.,'weak_positive_local':80.,
             'weak_positive_FLT_reference':60.,'weak_positive_distortional':55.,
             'weak_negative_local':40.,'weak_negative_FLT_reference':30.,
             'weak_negative_distortional':35.}
    row=dict(combination_id='synthetic',combination=combo(qy=qy),
        shear_lag_applicability={'axes':{axis:{'qualified':True} for axis in ('normal','parallel')}},
        load_position_by_axis=dict(normal={'classification':'stabilizing'},parallel={'classification':'stabilizing'}),
        components=[dict(route='own_rounded_contour',method=k,capacity_Nmm=v,index=.1,status='component_index',reason='synthetic',approximate=k=='distortional') for k,v in methods.items()])
    own=dict(source_binding=dict(nodes_sha256='synthetic',material=dict(E_MPa=200000.,G_MPa=77000.,fy_MPa=300.,nu=.3,gamma=1.1)),
        strong=dict(distortional={'eligible':True,'status':'computed','MRd_Nmm':100.}),
        weak={s:dict(distortional={'eligible':True,'status':'computed','MRd_Nmm':50.},local={'proof':{}}) for s in ('positive','negative')})
    return row,dict(own_rounded_contour=own)


def part(row,name):return next(p for p in row['components'] if p['method']==name)


def test_minimum_all_same_source_no_nominal_mix():
    r,s=fixture();r['components'].append(dict(route='published_nominal_reference',method='local',capacity_Nmm=1e20,index=0.))
    e=member.build(r,s,10.)
    assert e['arithmetic']['capacities_Nmm']==dict(Mx_positive=90.,Mx_negative=None,My_positive=55.,My_negative=None)
    assert e['status']=='component_computed' and not e['nominal_reference_mixed']
    assert e['approximate_elastic_references'] and not e['whole_member_approved']


def test_height_only_if_usable_and_not_replacing_classical():
    r,s=fixture();part(r,'FLT_reference')['index']=None
    e=member.build(r,s,10.)
    assert e['arithmetic']['capacities_Nmm']['Mx_positive']==70.
    part(r,'FLT_height_effective_reference')['index']=None
    e=member.build(r,s,10.)
    assert e['arithmetic']['governing'] is None
    assert 'Mx_positive:FLT_with_actual_position' in e['missing']


def test_negative_sign_never_reuses_positive_capacity():
    r,s=fixture(-4.);e=member.build(r,s,10.)
    assert e['arithmetic']['capacities_Nmm']['My_negative']==30.
    assert e['arithmetic']['capacities_Nmm']['My_positive'] is None
    part(r,'weak_negative_local')['index']=None
    assert 'My_negative:weak_negative_local' in member.build(r,s,10.)['missing']


def test_exemption_requires_source_status_and_proof():
    r,s=fixture();p=part(r,'weak_positive_distortional')
    p.update(index=None,capacity_Nmm=None,status='not_applicable_lips_in_tension')
    w=s['own_rounded_contour']['weak']['positive']
    w['distortional'].update(eligible=True,status='not_applicable_lips_in_tension',MRd_Nmm=None)
    w['local']['proof']['lips_in_tension_for_positive_pure_weak']=True
    e=member.build(r,s,10.)
    assert e['arithmetic']['capacities_Nmm']['My_positive']==60.
    w['local']['proof']['lips_in_tension_for_positive_pure_weak']=False
    assert member.build(r,s,10.)['arithmetic']['governing'] is None


def test_weak_position_pending_is_not_masked_by_negative_zero_demand():
    r,s=fixture();part(r,'weak_positive_FLT_reference')['index']=None
    assert member.build(r,s,10.)['status']=='pending_actual_member_components'
    r['combination']['q_vector']['parallel']=0.
    assert member.build(r,s,10.)['status']=='component_computed'


def test_duplicate_method_rejected_and_sources_unchanged():
    r,s=fixture();before=copy.deepcopy((r,s));member.build(r,s,10.);assert (r,s)==before
    r['components'].append(copy.deepcopy(r['components'][0]))
    with pytest.raises(ValueError,match='duplicadas'):member.build(r,s,10.)


@pytest.mark.parametrize('height',[100.,-100.])
def test_zero_net_bending_does_not_discard_rotational_load_potential(height):
    r,s=fixture(0.);r['combination']=combo(0.,0.)
    r['actions']=[dict(kind='uniform',q_down_N_mm=q,q_parallel_N_mm=0.,height_above_SC_mm=h,x_from_SC_mm=0.)
                  for q,h in ((1.,height),(-1.,0.))]
    e=member.build(r,s,10.)
    assert e['arithmetic']['governing']['index_exact']=='0'
    assert (e['status']=='pending_actual_member_components') is (height>0)
    assert not e['zero_moment_rotation_guard']['stability_solved']
