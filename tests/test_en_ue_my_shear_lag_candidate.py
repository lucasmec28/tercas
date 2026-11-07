"""Scalar reference checks only. No solver, UI or old-authority replay."""
import copy
from decimal import Decimal as D, localcontext
from functools import lru_cache
import math
import random

import pytest

from tercas.en_ue_catalog_operators import _properties
from tercas.en_ue_family_kernel import build as normal
from tercas import en_ue_my_shear_lag_candidate as candidate


@lru_cache(None)
def section(index=51):
    return normal(index,fyb_MPa=300.)


def demand(q=.001,L=4100.,P=0.,mesh=False):
    a=L/2
    loads=[dict(kind='uniform',q_xy_N_mm=[q,0.])]
    if P:loads.append(dict(kind='point',s_mm=a,force_xy_N=[P,0.]))
    xs=sorted({0.,L}|({a} if P else set())|({L/4,L/2,3*L/4} if mesh else set()))
    return dict(length_mm=L,loads=loads,
        elements=[dict(a_mm=x,b_mm=y,element_id='synthetic:e'+str(i+1),coefficients={'B_Nmm2':[0.]}) for i,(x,y) in enumerate(zip(xs,xs[1:]))],
        support_reactions=dict(left_force_xy_N=[-q*L/2-P/2,0.],right_force_xy_N=[-q*L/2-P/2,0.]))


@pytest.mark.parametrize('index',(51,52,58,59,60,67))
def test_six_example_shapes_have_new_subyield_certificates(index):
    n=section(index); before=copy.deepcopy(n)
    p=candidate.build(demand(),n)
    assert p['eligible'] and p['applicability_qualified']
    assert not p['consumer_integrated'] and not p['old_signed_components_requalified']
    assert not p['physical_exceedance_witness_permitted'] and not p['whole_member_approved']
    assert set(p['signed_capacity_floor'])=={'My_positive','My_negative'}
    local=p['local_distortional_audit']
    assert local['no_old_local_or_distortional_certificate_copied']
    assert all(v['integral_proved'] for v in local['local_panels'])
    assert local['distortion']['As_red_over_As_proved']==1.
    assert len(local['initial_fyb_lip_integral_certificates'])==2
    assert all(v['rho_initial_proved']==1. for v in local['initial_fyb_lip_integral_certificates'])
    assert p['actual_compression_upper_MPa']<local['design_compression_ceiling_MPa']<300.
    assert n==before


def test_opposite_sign_and_mesh_have_the_same_geometry_and_strength():
    p=candidate.build(demand(),section())
    for d in (demand(q=-.001),demand(mesh=True)):
        q=candidate.build(d,section())
        assert q['eligible']
        for k in ('geometry_audit','local_distortional_audit','beta_groups','signed_capacity_floor','operator_intervals'):
            assert p[k]==q[k]


def test_pure_my_over_own_ceiling_is_not_activated_even_with_a_positive_floor():
    p=candidate.build(demand(q=20.),section())
    assert p['moment_capacity_floor_Nmm']>0
    assert not p['eligible'] and not p['pure_demand_within_integral_ceiling']
    assert p['status']=='pending_demand_above_integral_ceiling'
    assert not p['blocking_reasons'][0]['normative_rejection_inferred']


def test_short_zero_zone_does_not_use_mesh_lengths():
    a=candidate.build(demand(q=.001,P=-3.075),section())
    b=candidate.build(demand(q=.001,P=-3.075,mesh=True),section())
    assert len(a['beta_groups']['web']['zones'])==3
    assert a['beta_groups']==b['beta_groups']


def test_local_and_D_are_recomputed_not_copied_from_components():
    n=copy.deepcopy(section()); n['components']={}; n['signed_capacity_floor']={}
    p=candidate.build(demand(),n)
    assert p['eligible']
    expected=candidate.build(demand(),section())
    for k in ('local_distortional_audit','geometry_audit','signed_capacity_floor'):
        assert p[k]==expected[k]


def test_unsupported_topology_and_historical_source_stay_pending():
    for key,value in [('nodes_xy_mm',[[0.,0.],[1.,1.]]),('method_revision','explicit_material_integral_and_reduced_web_20261106_v1')]:
        n=copy.deepcopy(section());n[key]=value
        p=candidate.build(demand(),n)
        assert not p['eligible'] and p['status']=='pending_method_domain'


def test_chi_envelope_covers_the_138_upward_jump():
    with localcontext() as ctx:
        ctx.prec=60
        left=D('1.47')-D('.723')*D('1.38')
        assert D.from_float(candidate._chi_lower(1.380001))<=left
        for upper in (.3,.65,.650001,1.,1.379999,1.38,1.380001,2.,10.):
            lower=D.from_float(candidate._chi_lower(upper))
            for lam in (.3,.65,.650001,1.,1.379999,1.38,1.380001,upper):
                if lam>upper:continue
                x=D.from_float(lam)
                actual=D(1) if x<=D('.65') else D('1.47')-D('.723')*x if x<D('1.38') else D('.66')/x
                assert lower<=actual


def test_sampled_loss_measures_are_inside_moment_and_centroid_bounds():
    n=section();p=candidate.build(demand(),n);g=p['geometry_audit'];t=n['thickness_mm']
    by_id={r['ids'][0]:r for r in g['loss_groups']}
    rng=random.Random(723)
    for sample in range(60):
        weights={i:1. for i in range(133)}
        for i in range(67):
            j=132-i
            if i not in by_id:continue
            if i in candidate.ARC_IDS:
                factor=rng.random() if sample else 1.
                weights[i]=weights[j]=1.-factor
            else:
                def area(k):
                    a,b=n['nodes_xy_mm'][k:k+2]
                    return t*math.hypot(b[0]-a[0],b[1]-a[1])
                maximum=min(by_id[i]['area_loss_upper_mm2']/area(i),by_id[j]['area_loss_upper_mm2']/area(j))
                factor=maximum*(rng.random() if sample else 1.)
                weights[i]=weights[j]=1.-factor
        weighted=[[i,0.,1.,t*v] for i,v in weights.items() if v>0]
        props=_properties(n['nodes_xy_mm'],weighted)
        assert props['Iy_weak_mm4']>=g['Iy_lower_mm4']
        assert g['centroid_x_interval_mm'][0]<=props['centroid_xy_mm'][0]<=g['centroid_x_interval_mm'][1]
        assert props['A_mm2']>=g['A_retained_lower_mm2']
        assert props['Ix_strong_mm4']>=g['Ix_lower_mm4']
        assert g['Ixy_interval_mm4'][0]<=props['Ixy_mm4']<=g['Ixy_interval_mm4'][1]
        ix,iy,xy=props['Ix_strong_mm4'],props['Iy_weak_mm4'],props['Ixy_mm4']
        cx,cy=-ix/(ix*iy-xy*xy),xy/(ix*iy-xy*xy)
        sx,sy=[props['centroid_xy_mm'][i]-n['gross_properties']['centroid_xy_mm'][i] for i in (0,1)]
        actual=[-cx*sx-cy*sy,cx,cy]
        for value,pair in zip(actual,g['operator_intervals_c0_cx_cy']):
            assert pair[0]<=value<=pair[1]


def test_decimal_capacity_floor_is_below_its_independent_formula():
    p=candidate.build(demand(),section());g=p['geometry_audit']
    with localcontext() as ctx:
        ctx.prec=60
        actual=D.from_float(p['local_distortional_audit']['design_compression_ceiling_MPa'])*D.from_float(g['My_schur_inertia_lower_mm4'])/D.from_float(g['maximum_fibre_arm_upper_mm'])
        assert D(p['moment_capacity_floor_Nmm'])<=actual


def test_every_corner_is_in_the_full_loss_superset():
    n=section();p=candidate.build(demand(),n);rows=p['geometry_audit']['loss_groups']
    corners=[r for r in rows if r['corner']]
    assert len(corners)==128
    assert {r['ids'][0] for r in corners}==set(candidate.ARC_IDS)
    for r in corners:
        a,b=n['nodes_xy_mm'][r['ids'][0]:r['ids'][0]+2]
        area=n['thickness_mm']*math.hypot(b[0]-a[0],b[1]-a[1])
        assert r['area_loss_upper_mm2']>=area


def test_concomitant_mx_or_B_is_not_qualified_by_the_pure_my_floor():
    for action in ('Mx','B'):
        d=demand()
        if action=='Mx':
            d['loads'][0]['q_xy_N_mm'][1]=.001
            for v in d['support_reactions'].values():v[1]=-.001*d['length_mm']/2
        else:d['elements'][0]['coefficients']={'B_Nmm2':[1.]}
        p=candidate.build(d,section())
        assert p['pure_component_capacity_qualified']
        assert p['pure_demand_within_integral_ceiling']
        assert not p['eligible'] and not p['applicability_qualified']
        assert p['status']=='pending_simultaneous_action_guard'
        assert not p['simultaneous_action_local_D_qualified']


def test_missing_or_invalid_B_cannot_be_treated_as_proved_zero():
    for values in (None,[],[math.nan],[math.inf],['0'],[True]):
        d=demand()
        if values is None:del d['elements'][0]['coefficients']['B_Nmm2']
        else:d['elements'][0]['coefficients']['B_Nmm2']=values
        with pytest.raises(ValueError,match='explicit finite B'):
            candidate._demand_bound(d)
    d=demand();d['analysis_domain']={'point_position_scope':'Prescribed a->0+ synthetic limit'}
    with pytest.raises(ValueError,match='support-limit source requires explicit states'):
        candidate._demand_bound(d)


def test_nonintegral_initial_fyb_lip_does_not_borrow_the_full_lip_Is():
    n=copy.deepcopy(section());n['material']['fyb_MPa']=3000.
    p=candidate.build(demand(),n)
    assert not p['eligible'] and p['status']=='pending_method_domain'
    assert 'Initial fyb-uniform lip is not proved integral' in p['blocking_reasons'][0]['detail']
    assert not p['blocking_reasons'][0]['normative_rejection_inferred']
