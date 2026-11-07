"""Reconstructed full-span adapter: numerical qualification, not physical approval."""
import copy
import json
import pytest
from tercas import flt_height_effective as flt
from tercas import pierin_ue_registry as registry, ue_catalog_reference as own
from test_flt_height_effective import data, uniform, point


def model(index=26):
    return flt.activate_combined(data(index, ly=4100., lz=4100.))


@pytest.mark.parametrize('index', registry.new_study_indices())
@pytest.mark.parametrize('sign', [-1., 1.])
def test_all_66_full_span_normal_combined(index, sign):
    d=model(index); h=d['properties']['h']/2
    a=[uniform(sign*.1, 0., 'PP'), uniform(sign*.9,h), point(sign*500.,h,x=1537.)]
    before=copy.deepcopy((d,a))
    r=flt.qualify_family(d,a)
    assert r['method']==flt.COMBINED_METHOD and r['elastic_reference_eligible']
    assert r['Me_Nmm']>0 and r['numerical_critical']['numerically_converged']
    assert r['numerical_critical']['scaled_eigen_residual']<1e-12
    assert r['Ly_used_mm']==r['Lz_used_mm']==r['physical_span_mm']==4100.
    assert not r['physical_supports_created'] and not r['whole_member_approved']
    assert not r['guaranteed_elastic_lower_bound']
    assert r['height_tangent_by_action'][0]['value']==0.
    assert (d,a)==before


@pytest.mark.parametrize('station',[0.,1e-6,2050.,4099.999999,4100.])
@pytest.mark.parametrize('sign',[-1.,1.])
def test_support_limit_center_both_signs(station,sign):
    d=model(); a=[uniform(.7,50.),point(sign*500.,60.,station)]
    r=flt.qualify_family(d,a)
    assert r['elastic_reference_eligible']
    assert (r['method']==flt.METHOD)==(station in (0.,4100.))


def test_legacy_never_solver_and_pure_env_preferred(monkeypatch):
    from tercas import ltb_load_height
    monkeypatch.setattr(ltb_load_height,'refined',lambda **kw:pytest.fail('legacy/pure solver'))
    d=data(ly=4100.,lz=4100.); a=[uniform(.7,50.),point()]
    assert flt.qualify_family(d,a)['Me_Nmm'] is None
    for acts in ([uniform(.7,50.)],[point()]):
        assert flt.qualify_family(d,acts)==flt.qualify_family(flt.activate_combined(d),acts)


@pytest.mark.parametrize('ly,lz',[(2050.,2050.),(2050.,4100.),(4100.,2050.),(3000.,4100.)])
def test_lengths_never_infer_fixity(ly,lz,monkeypatch):
    from tercas import ltb_load_height
    monkeypatch.setattr(ltb_load_height,'refined',lambda **kw:pytest.fail('effective fixity'))
    d=flt.activate_combined(data(ly=ly,lz=lz))
    assert not flt.qualify_family(d,[uniform(1.,60.),point()])['elastic_reference_eligible']


@pytest.mark.parametrize('mutation',[
    lambda r:r.update(Me_Nmm=1e20),
    lambda r:r['numerical_critical'].update(lambda_cr=1e20),
    lambda r:r['actions'][1].update(s_mm=100.),
    lambda r:r.update(whole_member_approved=True),
])
def test_rehash_replay_rejects(mutation):
    d=model(); a=[uniform(.7,50.),point()];r=flt.qualify_family(d,a)
    assert flt.validate_saved(json.loads(json.dumps(r)),d,a)==r
    mutation(r);r['snapshot_sha256']=own.digest({k:v for k,v in r.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):flt.validate_saved(r,d,a)


def test_bad_marker_and_disabled_roof():
    d=model();d[flt.COMBINED_FIELD]='invented'
    with pytest.raises(ValueError):flt.qualify_family(d,[uniform(1.,50.),point()])
    d=model();d['roof_top_load']['enabled']=False
    assert not flt.qualify_family(d,[uniform(1.,50.),point()])['elastic_reference_eligible']


@pytest.mark.parametrize('sign',[-1.,1.])
def test_inclination_parallel_guard_all_66(sign):
    from tercas import roof_top_load as roof
    from tercas.roof_biaxial import classify
    results=[]
    for index in registry.new_study_indices():
        d=model(index); g=roof.geometry(d)
        a=[dict(uniform(1.,g['height_above_SC_mm'],ex=g['x_from_SC_mm']),q_parallel_N_mm=sign*.1),
           dict(point(h=g['height_above_SC_mm']),x_from_SC_mm=g['x_from_SC_mm'],P_parallel_N=sign*10.)]
        scope=classify(a,g)
        r=flt.qualify_family(d,a)
        assert r['elastic_reference_eligible']==scope['applicable']
        results.append(r['elastic_reference_eligible'])
    # Exact documented contour boundary, not extrapolation from sample sections.
    assert sum(results)==(66 if sign>0 else 0)


def test_load_scaling_and_individual_heights():
    d=model();a=[uniform(.2,0.,'PP'),uniform(.8,60.),point(500.,30.,1537.)]
    r=flt.qualify_family(d,a); b=copy.deepcopy(a)
    for x in b:
        key='q_down_N_mm' if x['kind']=='uniform' else 'P_down_N';x[key]*=3
    t=flt.qualify_family(d,b)
    assert t['Me_Nmm']==pytest.approx(r['Me_Nmm'],rel=1e-12)
    assert t['lambda_reference']*3==pytest.approx(r['lambda_reference'],rel=1e-12)
    b=copy.deepcopy(a);b[0]['height_above_SC_mm']=60.
    assert flt.qualify_family(d,b)['Me_Nmm']<r['Me_Nmm']


def test_new_producer_marker_and_existing_partial_state():
    from tercas.new_study_policy import for_new_study, initialize_session
    d=data(ly=4100.,lz=4100.)
    fresh=for_new_study(d)
    assert fresh[flt.COMBINED_FIELD]==flt.COMBINED_METHOD
    state={'last_input':d}
    initialize_session(state,lambda:pytest.fail('must preserve old study'))
    assert flt.COMBINED_FIELD not in state['base']


@pytest.mark.parametrize('index',[0,26,53,79])
def test_consumer_uses_numerical_me_and_replays_saved_inventory(index):
    from test_nbr_family_height_integration import source
    from tercas import nbr_ue_family_application as app
    from tercas.application import fingerprint
    r=source(index,Leff=4100.)
    d=flt.activate_combined(r['input_data'])
    d.update(P_uls=500.,x_uls=1537.)
    # Keep angle and individual load projections as produced by the application.
    r=own.attach_source(dict(input_data=d,input_fingerprint=fingerprint(d),schema='NBR14762_one_span_v1',
        model_domain_evidence=dict(status='fixed_model_domain',conflict=False)))
    out=app.attach(r); ev=app.preserved(json.loads(json.dumps(out)))
    row=ev['records'][0]
    assert row['height_source']['method']==flt.COMBINED_METHOD
    assert row['height_source']['elastic_reference_eligible']
    assert row['height_capacity']['MRd_Nmm']>0
    assert next(c for c in row['components'] if c['method']=='FLT_height_effective_reference')['index'] is not None


def test_refinement_failure_never_creates_capacity(monkeypatch):
    from tercas import ltb_load_height
    monkeypatch.setattr(ltb_load_height,'refined',lambda **kw:dict(numerically_converged=False,Me_Nmm=None,reason='budget exhausted'))
    r=flt.qualify_family(model(),[uniform(1.,60.),point()])
    assert not r['elastic_reference_eligible'] and r['Me_Nmm'] is None
    assert r['status']=='pending_numerical_qualification'
    assert r['reason']=='budget exhausted'


def own_parallel_actions(d, sign=1.):
    from tercas.roof_top_load import geometry
    g=geometry(d)
    return [dict(uniform(.1,0.,'PP',g['CG_xy_mm'][0]-g['SC_xy_mm'][0]),q_parallel_N_mm=sign*.01),
            dict(uniform(.9,g['height_above_SC_mm'],ex=g['x_from_SC_mm']),q_parallel_N_mm=sign*.09),
            dict(point(500.,g['height_above_SC_mm'],1537.),x_from_SC_mm=g['x_from_SC_mm'],P_parallel_N=sign*50.)]


def test_v1_pending_not_promoted_to_v2_and_marker_absence_exact():
    d=model(53);a=own_parallel_actions(d)
    legacy=copy.deepcopy(d);legacy[flt.COMBINED_FIELD]=flt.LEGACY_COMBINED_METHOD
    old=flt.qualify_family(legacy,a)
    assert not old['elastic_reference_eligible'] and old['method']==flt.LEGACY_COMBINED_METHOD
    assert flt.validate_saved(copy.deepcopy(old),legacy,a)==old
    assert flt.qualify_family(d,a)['elastic_reference_eligible']
    unmarked=copy.deepcopy(d);unmarked.pop(flt.COMBINED_FIELD)
    assert flt.qualify_family(unmarked,a)==flt._documentary_family(unmarked,a)


@pytest.mark.parametrize('field',['CG_xy_mm','SC_xy_mm','load_line','source_binding','position'])
def test_authenticated_geometry_tampering_rehashed_rejected(field):
    d=model(53);a=own_parallel_actions(d);r=flt.qualify_family(d,a)
    bound=r['authenticated_family_geometry'];g=bound['geometry']
    if field in ('CG_xy_mm','SC_xy_mm'):g[field][0]+=1.
    elif field=='load_line':g['load_line']='flange_midwidth'
    elif field=='source_binding':g['ue_catalog_source_binding']['nodes_sha256']='f'*64
    else:r['actions'][2]['x_from_SC_mm']=-abs(r['actions'][2]['x_from_SC_mm'])
    r['snapshot_sha256']=own.digest({k:v for k,v in r.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):flt.validate_saved(r,d,a)


@pytest.mark.parametrize('field',['CG_xy_mm','SC_xy_mm','load_line','source_binding'])
def test_fresh_geometry_must_match_source_not_claimed_hash(field):
    from tercas.roof_top_load import geometry
    d=model(53);a=own_parallel_actions(d);g=geometry(d)
    if field in ('CG_xy_mm','SC_xy_mm'):g[field][0]+=1.
    elif field=='load_line':g['load_line']='flange_midwidth'
    else:g['ue_catalog_source_binding']['nodes_sha256']='f'*64
    g['snapshot_sha256']=own.digest(g)
    with pytest.raises(ValueError):flt.authenticate_family_geometry(d,g,a)


def test_individual_position_cannot_impersonate_authenticated_top():
    d=model(53);a=own_parallel_actions(d)
    a[-1]['x_from_SC_mm']=1e9
    r=flt.qualify_family(d,a)
    assert not r['elastic_reference_eligible'] and 'Posição individual' in r['reason']
    a=own_parallel_actions(d);a[-1]['P_parallel_N']=-50.
    r=flt.qualify_family(d,a)
    assert not r['elastic_reference_eligible'] and 'desestabilizante' in r['reason']


def test_area_producer_uses_own_lines_and_keeps_physical_inventory():
    from tercas.batch import area_bundle
    from tercas import roof_top_load as roof
    from tercas.roof_biaxial import classify
    from tercas.ltb_load_height import action_terms, maximum_moment
    d=model(53);d['load_mode']='area'
    bundle=area_bundle(d);before=copy.deepcopy(bundle);g=roof.geometry(d)
    mixed=0
    for combo in bundle['combinations']:
        if combo['limit_state']!='ELU' or not combo['P_vector']['normal']:
            continue
        a,parallel=roof._actions(bundle,combo,g,include_parallel=True)
        r=flt.qualify_family(d,a)
        assert r['maximum_reference_moment_Nmm']==float(maximum_moment(d['L_mm'],action_terms(a,d['L_mm']),0.))
        if r['method']==flt.COMBINED_METHOD:
            mixed+=1
            assert r['elastic_reference_eligible']==(not parallel or classify(a,g)['applicable'])
            assert r['physical_span_mm']==d['L_mm']
        assert next(x for x in a if x['name']=='PP')['height_above_SC_mm']==0.
    assert mixed>0 and bundle==before


def test_v1_eligible_numerical_replay_stays_v1():
    d=model(26);d[flt.COMBINED_FIELD]=flt.LEGACY_COMBINED_METHOD;a=own_parallel_actions(d)
    r=flt.qualify_family(d,a)
    assert r['elastic_reference_eligible'] and r['method']==flt.LEGACY_COMBINED_METHOD
    assert 'authenticated_family_geometry' not in r
    assert flt.validate_saved(json.loads(json.dumps(r)),d,a)==r
