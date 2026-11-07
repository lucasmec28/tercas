"""Isolated simultaneous candidate QA using saved SYNTHETIC dense sources.

All member solves are prohibited here. Geometry/section calculations and
read-only replay of saved fields are scalar/reference arithmetic only.
"""
import copy
import gzip
import json
import math
import random
from decimal import Decimal as D,localcontext
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

import pytest
from tercas import en_ue_concurrent_shear_lag_candidate as method
from tercas import isolated_en_ue_concurrent_candidate as consumer
from tercas import isolated_en_ue_family as legacy
from tercas import isolated_en_ue_catalog_application as arithmetic
from tercas.en_ue_catalog_operators import _properties,_sha


@lru_cache(None)
def fixtures():
    with gzip.open(Path(__file__).parent/'fixtures/en_ue_concurrent_synthetic.json.gz') as stream:
        data=json.load(stream)
    assert data['kind']=='SYNTHETIC_R11_FAMILY_MATRIX_FIXTURES_NOT_USER_PROJECT_DATA'
    return data['cases']


def case(index=51):
    c=fixtures()[str(index)]
    return c['normal'],c['original_check']['source_demand'],c['original_check']


@pytest.fixture(autouse=True)
def no_member_solver(monkeypatch):
    from tercas.torsion_vlasov import vlasov
    monkeypatch.setattr(vlasov,'solve_member',lambda *a,**kw:pytest.fail('No member solve is permitted in candidate QA'))


@pytest.mark.parametrize('index',(51,53))
def test_pending_synthetic_case_gets_new_guarded_schema_without_mutation(index):
    n,d,old=case(index);before=_sha([n,d,old])
    result=consumer.calculate(d,normal_snapshot=n,model_origin=old['model_origin'])
    assert result['schema']==consumer.SCHEMA and old['schema']==legacy.SCHEMA
    assert result['applicability']['qualified'] and result['component_status']['stress']=='computed'
    assert result['stress']['section_stress_criteria_sufficiently_satisfied']
    assert result['mv']['component_sufficient']
    proof=result['concurrent_shear_lag_supplement']
    assert proof['eligible'] and proof['source_authenticated'] and proof['consumer_integrated']
    assert proof['simultaneous_field_below_ceiling'] and proof['simultaneous_uniform_reference']['qualified']
    assert proof['curling_components']['qualified']
    assert proof['pure_My_construction']['eligible'] is False  # Pure API still blocks Mx/B.
    assert proof['simultaneous_normal_stress_upper_MPa']<=proof['integral_local_D_design_ceiling_MPa']<300.
    assert proof['absolute_stress_contributions_upper_MPa']['B']>0
    assert result['source_demand']==d and _sha([n,d,old])==before
    assert result['shear']==old['shear']
    assert all(result[flag] is False for flag in legacy.FALSE_FLAGS)
    assert not any(c['observed_exceedance'] for c in result['stress']['criteria'].values())


def test_already_applicable_legacy_result_is_exactly_unchanged():
    n,d,old=case(0)
    assert consumer.calculate(d,normal_snapshot=n,model_origin=old['model_origin'])==old


def test_new_saved_record_replays_without_solver_and_rejects_resealed_guard():
    n,d,old=case();result=consumer.calculate(d,normal_snapshot=n,model_origin=old['model_origin'])
    summary=legacy._compact_source(d)
    assert consumer.validate_saved(result,summary,normal_snapshot=n,source_sha256=_sha(d),model_origin=old['model_origin'])
    bad=copy.deepcopy(result);bad['concurrent_shear_lag_supplement']['simultaneous_normal_stress_upper_MPa']=0.
    bad['content_sha256']=_sha({k:v for k,v in bad.items() if k!='content_sha256'})
    with pytest.raises(ValueError,match='arithmetic, guards or technical source'):
        consumer.validate_saved(bad,summary,normal_snapshot=n,source_sha256=_sha(d),model_origin=old['model_origin'])


@pytest.mark.parametrize('field',('left','right','B','omega','CG','normal_floor'))
def test_consumer_authenticates_reactions_dense_torsion_and_own_geometry(field):
    nn,dd,old=case();n,d=copy.deepcopy(nn),copy.deepcopy(dd)
    if field in ('left','right'):d['support_reactions'][field+'_force_xy_N'][0]+=1.
    elif field=='B':d['elements'][0]['coefficients']['B_Nmm2'][0]+=.01
    elif field=='omega':d['section']['omega_nodes_mm2'][0]+=.01
    elif field=='CG':d['section']['properties']['centroid_xy_mm'][0]+=.01
    else:
        n['signed_capacity_floor']['Mx_positive']*=2
        n['content_sha256']=_sha({k:v for k,v in n.items() if k!='content_sha256'})
    if field in ('omega','CG'):
        d['section']['content_sha256']=_sha({k:v for k,v in d['section'].items() if k!='content_sha256'})
    with pytest.raises(ValueError):consumer.calculate(d,normal_snapshot=n,model_origin=old['model_origin'])


def test_total_ceiling_not_fy_or_pure_my_controls_activation():
    n,dd,_=case(53);d=copy.deepcopy(dd)
    for e in d['elements']:e['coefficients']['B_Nmm2']=[8*v for v in e['coefficients']['B_Nmm2']]
    p=method.audit(d,n)  # Algebraic stress test, not an authenticated new source.
    assert p['pure_My_construction']['pure_demand_within_integral_ceiling']
    assert p['simultaneous_normal_stress_upper_MPa']<300.
    assert p['simultaneous_normal_stress_upper_MPa']>p['integral_local_D_design_ceiling_MPa']
    assert not p['construction_qualified'] and not p['simultaneous_uniform_reference']['qualified']
    assert {r['code'] for r in p['blocking_reasons']}=={'SIMULTANEOUS_LOCAL_D_CEILING_NOT_PROVED','UNIFORM_LOCAL_D_REFERENCE_NOT_QUALIFIED'}
    assert not p['source_authenticated'] and not p['eligible']


def test_no_favourable_B_cancellation_or_tensile_area_credit():
    n,d,_=case();negative=copy.deepcopy(d)
    for e in negative['elements']:e['coefficients']['B_Nmm2']=[-v for v in e['coefficients']['B_Nmm2']]
    a,b=method.audit(d,n),method.audit(negative,n)
    assert a['absolute_stress_contributions_upper_MPa']==b['absolute_stress_contributions_upper_MPa']
    assert a['simultaneous_normal_stress_upper_MPa']==b['simultaneous_normal_stress_upper_MPa']
    proof=a['simultaneous_uniform_reference']
    assert proof['As_red_over_As_lower_proved']==1.
    assert not proof['real_tensile_subsets_removed_from_As']
    assert not proof['favourable_tensile_stress_credit']
    assert {r['stage'] for r in proof['reference_stages']}=={'initial_uniform_fyb','locally_integral_uniform_reference'}


def test_curling_failure_cannot_be_hidden_by_passed_local_D(monkeypatch):
    n,d,old=case();original=method._curling_components
    def blocked(*a,**kw):
        value=original(*a,**kw);value['qualified']=False;value['axes']['Mx']['qualified']=False
        return value
    monkeypatch.setattr(method,'_curling_components',blocked)
    result=consumer.calculate(d,normal_snapshot=n,model_origin=old['model_origin'])
    assert result['concurrent_shear_lag_supplement']['simultaneous_field_below_ceiling']
    assert not result['concurrent_shear_lag_supplement']['eligible']
    assert any(row['code']=='PURE_COMPONENT_CURLING_NOT_QUALIFIED' for row in result['concurrent_shear_lag_supplement']['blocking_reasons'])
    assert result['component_status']['stress']=='pending'
    assert result['stress']['criteria']['normal']['index_upper_bound'] is None
    assert result['mv']['index_upper'] is None


def test_B_bernstein_encloses_all_polynomial_orders_in_exact_rationals():
    for values in ([7.],[-4.,9.],[1.,-8.,7.],[-9.,2.,30.,-8.]):
        bounds=method._power_bernstein(values)
        for i in range(129):
            u=F(i,128);value=sum((F(v)*u**k for k,v in enumerate(values)),F(0))
            assert min(bounds)<=value<=max(bounds)
    for values in (None,[],[math.nan],[math.inf],['0'],[True],[0.]*5):
        with pytest.raises(ValueError):method._power_bernstein(values)


def test_strong_loss_samples_and_capacity_are_enclosed_independently():
    n,d,_=case();p=method.audit(d,n);g=p['pure_Mx_construction'];rng=random.Random(527)
    for sample in range(50):
        weights={i:1. for i in range(133)}
        for row in g['loss_groups']:
            ids=row['ids']
            area=sum(n['thickness_mm']*math.hypot(n['nodes_xy_mm'][i+1][0]-n['nodes_xy_mm'][i][0],n['nodes_xy_mm'][i+1][1]-n['nodes_xy_mm'][i][1]) for i in ids)
            loss=min(1.,row['area_loss_upper_mm2']/area)*(rng.random() if sample else 1.)
            for i in ids:weights[i]=1.-loss
        props=_properties(n['nodes_xy_mm'],[[i,0.,1.,n['thickness_mm']*v] for i,v in weights.items() if v>0])
        ix,iy,xy=props['Ix_strong_mm4'],props['Iy_weak_mm4'],props['Ixy_mm4'];det=ix*iy-xy*xy
        assert ix>=g['Ix_lower_mm4'] and iy>=g['Iy_lower_mm4']
        assert g['Ixy_interval_mm4'][0]<=xy<=g['Ixy_interval_mm4'][1]
        cx,cy=-xy/det,iy/det
        dx,dy=[props['centroid_xy_mm'][k]-n['gross_properties']['centroid_xy_mm'][k] for k in (0,1)]
        for value,pair in zip([-cx*dx-cy*dy,cx,cy],g['operator_intervals']['Mx_positive']):
            assert pair[0]<=value<=pair[1]
    with localcontext() as ctx:
        ctx.prec=60
        value=D.from_float(p['integral_local_D_design_ceiling_MPa'])*D.from_float(g['Mx_schur_inertia_lower_mm4'])/D.from_float(g['maximum_equivalent_fibre_arm_upper_mm'])
        assert D(g['moment_capacity_floor_Nmm'])<=value


def test_reduced_old_Mx_is_not_scaled_or_requalified_to_make_new_Mx():
    n,d,_=case(53)
    assert n['components']['Mx_positive']['effective_properties']!=n['gross_properties']
    p=method.audit(d,n)
    assert p['construction_qualified']
    assert not p['pure_Mx_construction']['old_reduced_operator_scaled_or_requalified']
    assert p['pure_Mx_construction']['operator_intervals']['Mx_positive'][0][0]<=0.
    assert p['pure_Mx_construction']['operator_intervals']['Mx_positive'][0][1]>=0.


def scaled_algebraic(demand,factor):
    """Only an algebraic audit fixture; this is NOT an authenticated dense field."""
    d=copy.deepcopy(demand)
    for a in d['loads']:
        key='q_xy_N_mm' if a['kind']=='uniform' else 'force_xy_N'
        a[key]=[factor*v for v in a[key]]
    L=d['length_mm'];q=[math.fsum(a['q_xy_N_mm'][j] for a in d['loads'] if a['kind']=='uniform') for j in (0,1)]
    left=[-v*L/2 for v in q];right=left.copy()
    for a in d['loads']:
        if a['kind']=='point':
            for j in (0,1):
                left[j]-=a['force_xy_N'][j]*(L-a['s_mm'])/L
                right[j]-=a['force_xy_N'][j]*a['s_mm']/L
    d['support_reactions'].update(left_force_xy_N=left,right_force_xy_N=right)
    for e in d['elements']:e['coefficients']['B_Nmm2']=[factor*v for v in e['coefficients']['B_Nmm2']]
    for s in d.get('support_limit_states',[]):s['B_Nmm2']*=factor
    return d


def test_full_load_sign_reversal_preserves_absolute_certificate():
    n,d,_=case(53);a,b=method.audit(d,n),method.audit(scaled_algebraic(d,-1.),n)
    assert a['construction_qualified'] and b['construction_qualified']
    assert a['absolute_stress_contributions_upper_MPa']==b['absolute_stress_contributions_upper_MPa']
    assert a['pure_My_construction']['signed_capacity_floor']==b['pure_My_construction']['signed_capacity_floor']
    assert a['pure_Mx_construction']['signed_capacity_floor']==b['pure_Mx_construction']['signed_capacity_floor']
    for axis in ('Mx','My'):
        assert set(a['required_signed_branches'][axis])!=set(b['required_signed_branches'][axis])


@pytest.mark.parametrize('fraction,expected',((.999999,True),(1.000001,False)))
def test_both_sides_of_simultaneous_ceiling(fraction,expected):
    n,d,_=case(53);p=method.audit(d,n)
    cap=p['integral_local_D_design_ceiling_MPa'];scale=cap/p['simultaneous_normal_stress_upper_MPa']*fraction
    p=method.audit(scaled_algebraic(d,scale),n)
    assert p['simultaneous_field_below_ceiling'] is expected
    assert p['construction_qualified'] is expected
    assert p['simultaneous_normal_stress_upper_MPa']==pytest.approx(cap*fraction,rel=1e-12)
    assert p['simultaneous_normal_stress_upper_MPa']<n['normal_yield_limit_MPa']
    assert not p['eligible'] and not p['source_authenticated']
    assert not any(x.get('normative_rejection_inferred') for x in p['blocking_reasons'])


@pytest.mark.parametrize('target',('reaction','section','B','curling'))
def test_resealed_saved_source_and_curling_cannot_bypass_replay(target):
    n,d,old=case();bad=consumer.calculate(d,normal_snapshot=n,model_origin=old['model_origin'])
    bad=copy.deepcopy(bad);source=bad['source_demand'];proof=bad['concurrent_shear_lag_supplement']
    if target=='reaction':source['support_reactions']['left_force_xy_N'][0]+=1.
    elif target=='section':
        source['section']['omega_nodes_mm2'][0]+=.01
        source['section']['content_sha256']=_sha({k:v for k,v in source['section'].items() if k!='content_sha256'})
    elif target=='B':source['elements'][0]['coefficients']['B_Nmm2'][0]+=.01
    else:
        proof['curling_components']['qualified']=True
        proof['curling_components']['axes']['Mx']['panels']['strong']['stress_upper_MPa']=0.
    bad['source_analysis_sha256']=_sha(source)
    proof['source_authentication']['source_demand_sha256']=_sha(source)
    proof['source_authentication']['source_section_sha256']=_sha(source['section'])
    proof['content_sha256']=_sha({k:v for k,v in proof.items() if k!='content_sha256'})
    for row in (bad['applicability'],bad['stress']):row['concurrent_shear_lag_supplement_sha256']=proof['content_sha256']
    bad['stress']['content_sha256']=_sha({k:v for k,v in bad['stress'].items() if k!='content_sha256'})
    bad['content_sha256']=_sha({k:v for k,v in bad.items() if k!='content_sha256'})
    with pytest.raises(ValueError):
        consumer.validate_saved(bad,legacy._compact_source(source),normal_snapshot=n,
            source_sha256=_sha(source),model_origin=old['model_origin'])


def test_batch_dispatch_and_consumed_mv_denominators():
    n,d,old=case();out=consumer.calculate_many([d],normal_snapshot=n,model_origin=old['model_origin'])[0]
    proof=out['concurrent_shear_lag_supplement']
    capacities={**proof['pure_My_construction']['signed_capacity_floor'],**proof['pure_Mx_construction']['signed_capacity_floor']}
    shear,mv,pieces=legacy._interaction(d,n,n['shear'],arithmetic._source_pieces(d),out['applicability'],capacity_overrides=capacities)
    assert (out['shear'],out['mv'],out['pieces'])==(shear,mv,pieces)
    assert any(capacities[k]!=n['components'][k]['first_yield_capacity_floor'] for k in capacities)
    assert consumer.validate_saved_many([dict(check=out,summary=legacy._compact_source(d),source_sha256=_sha(d))],normal_snapshot=n,model_origin=old['model_origin'])
    assert isinstance(consumer.calculate_many([{}],normal_snapshot=n,model_origin=old['model_origin'])[0],Exception)
    n,d,old=case(0)
    assert consumer.calculate_many([d],normal_snapshot=n,model_origin=old['model_origin'])==[old]
    assert consumer.validate_saved_many([dict(check=old,summary=legacy._compact_source(d),source_sha256=_sha(d))],normal_snapshot=n,model_origin=old['model_origin'])


def test_bad_beta_or_schur_stays_pending_not_normative_rejection(monkeypatch):
    n,d,_=case();beta=method._beta_lower
    def no_retained_flange(*a,**kw):
        result=beta(*a,**kw);result['beta_lower']=0.;return result
    monkeypatch.setattr(method,'_beta_lower',no_retained_flange)
    p=method.audit(d,n)
    assert p['status']=='pending_method_domain' and not p['construction_qualified']
    assert not p['eligible'] and not p['source_authenticated']
    assert all(row['normative_rejection_inferred'] is False for row in p['blocking_reasons'])
    assert any('inertia' in row['detail'] or 'Schur' in row['detail'] for row in p['blocking_reasons'])


def test_external_cache_and_new_binding_include_candidate_source_bytes(monkeypatch):
    from tercas import isolated_en_ue_family_application as app
    n,_,old=case();r={app.FIELD:dict(normal_snapshot=n,records=[dict(status='computed')])}
    before=app._cache_authority_key(r);binding=consumer.source_binding();read=Path.read_bytes
    def changed(path):
        data=read(path)
        return data+b'\n# synthetic source revision test\n' if path.name=='isolated_en_ue_concurrent_candidate.py' else data
    monkeypatch.setattr(Path,'read_bytes',changed)
    assert app._cache_authority_key(r)!=before
    assert consumer.source_binding()!=binding


def test_batch_generation_authenticates_provider_once(monkeypatch):
    from tercas import en_ue_family_provider as provider
    n,d,old=case();calls=[];verify=provider.verify
    def count(value):calls.append(1);return verify(value)
    monkeypatch.setattr(provider,'verify',count)
    checks=consumer.calculate_many([d,d],normal_snapshot=n,model_origin=old['model_origin'])
    assert len(calls)==1 and all(not isinstance(c,Exception) for c in checks)


@pytest.mark.parametrize('name,expected',(('P_interior',True),('P_reversed',True),('P_near_left',True),('P_opposes_uniform',False)))
def test_saved_synthetic_point_applications_replay_both_jump_sides(name,expected):
    from tercas import isolated_en_ue_family_application as app
    path=Path(__file__).resolve().parents[1]/'qa/en_ue_concurrent_shear_lag_candidate'/(name+'.json.gz')
    with gzip.open(path) as stream:payload=json.load(stream)
    assert payload['kind']=='SYNTHETIC_POINT_APPLICATION_NOT_USER_PROJECT_DATA'
    result=payload['application_snapshot'];saved=result[app.FIELD]
    n=saved['normal_snapshot'];out=payload['candidate_check'];d=out['source_demand']
    assert consumer.validate_saved(out,legacy._compact_source(d),normal_snapshot=n,
        source_sha256=_sha(d),model_origin=out['model_origin'])
    assert out['concurrent_shear_lag_supplement']['eligible'] is expected
    sides=payload['receipt']['point_sides'];assert {s['side'] for s in sides}=={'left','right'}
    point=next(a for a in d['loads'] if a['kind']=='point');left,right=sorted(sides,key=lambda s:s['side'])
    assert right['Vy_N']-left['Vy_N']==pytest.approx(-point['force_xy_N'][1],abs=1e-10)
    if not expected:
        assert out['stress']['criteria']['normal']['index_upper_bound'] is None
        assert out['mv']['index_upper'] is None
        assert all(not r['normative_rejection_inferred'] for r in out['concurrent_shear_lag_supplement']['blocking_reasons'])


def test_future_two_import_dispatch_uses_same_snapshot_for_document_and_panorama(monkeypatch):
    """Test-only dispatch shim. No production source/import is modified."""
    import sys,types
    from docx import Document
    from tercas import isolated_en_ue_family_application as app
    from tercas import isolated_en_ue_family_ui as ui
    path=Path(__file__).resolve().parents[1]/'qa/en_ue_concurrent_shear_lag_candidate/P_interior.json.gz'
    with gzip.open(path) as stream:payload=json.load(stream)
    r=copy.deepcopy(payload['application_snapshot']);ev=r[app.FIELD];row=ev['records'][0]
    row['check']=copy.deepcopy(payload['candidate_check']);row['reason']=None
    ev.update(app._counts(ev));ev['snapshot_sha256']=_sha({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    shim=types.ModuleType(legacy.__name__);shim.__dict__.update(legacy.__dict__)
    shim.calculate_many=consumer.calculate_many;shim.validate_saved_many=consumer.validate_saved_many
    monkeypatch.setitem(sys.modules,legacy.__name__,shim)
    app._VALIDATED_RESULTS.clear()
    view=app._presentation_view(r);data=ui.rows(view);doc=Document();ui.report(doc,r)
    assert len(data)==1 and data[0]['Teto EN6.1.6 normal']==row['check']['stress']['criteria']['normal']['index_upper_bound']
    assert data[0]['Teto M–V EN6.27']==row['check']['mv']['index_upper']
    assert data[0]['Tensões suficientes'] and data[0]['M–V suficiente']
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'EN família salvo inválido' not in text and 'tensões calculadas: 1' in text
    context=app.global_context(r,sectional=True)
    assert context['binding']['snapshot_sha256']==ev['snapshot_sha256']
    assert 'tensões: 1' in context['reason']
    before=_sha(r);app._presentation_view(r);assert _sha(r)==before


@pytest.mark.parametrize('index',(25,30))
def test_own_authenticated_CGs_may_differ_without_binary_tolerance(index):
    n,d,old=case(index)
    assert n['nodes_sha256']==d['section']['nodes_sha256']
    assert n['gross_properties']['centroid_xy_mm']!=d['section']['properties']['centroid_xy_mm']
    # Both independently deterministic references authenticate; old v3 still wins.
    assert consumer.calculate(d,normal_snapshot=n,model_origin=old['model_origin'])==old
    p=method.audit(scaled_algebraic(d,.01),n)
    assert p['construction_qualified']
    transport=p['operator_reference_transport'];assert transport['translation_applied']
    assert transport['N_identically_zero_proved'] and transport['original_B_omega_Cw_shear_torque_and_demand_unchanged']
    own={**p['pure_Mx_construction']['operator_intervals'],**p['pure_My_construction']['operator_intervals']}
    normal_cg=list(map(F,n['gross_properties']['centroid_xy_mm']));source_cg=list(map(F,d['section']['properties']['centroid_xy_mm']))
    for key,pairs in own.items():
        # Every original coefficient-box vertex maps inside the transported box.
        import itertools
        for vertex in itertools.product(*pairs):
            c0,cx,cy=map(F,vertex);expected=c0+cx*(source_cg[0]-normal_cg[0])+cy*(source_cg[1]-normal_cg[1])
            box=p['operator_intervals'][key][0]
            assert F(box[0])<=expected<=F(box[1])
    assert p['absolute_stress_contributions_upper_MPa']['B']>0


def test_origin_transport_is_an_exact_coordinate_rule_not_a_CG_tolerance():
    original={'My_positive':[[1.,2.],[3.,4.],[-7.,-5.]]}
    translated,proof=method._transport_operator_origin(original,[4.,8.],[128.,-256.])
    assert proof['translation_applied']
    for x,y in ((0.,0.),(4.,8.),(100.,200.)):
        for c0 in original['My_positive'][0]:
            for cx in original['My_positive'][1]:
                for cy in original['My_positive'][2]:
                    value=F(c0)+F(cx)*(F(x)-4)+F(cy)*(F(y)-8)
                    from tercas.torsion_vlasov.intervals import Interval as I
                    pairs=translated['My_positive'];bound=I(*pairs[0])+I(*pairs[1])*I(x-128.)+I(*pairs[2])*I(y+256.)
                    assert F(float(bound.lo))<=value<=F(float(bound.hi))
    assert original=={'My_positive':[[1.,2.],[3.,4.],[-7.,-5.]]}
