"""Pinned normal-library admission and saved-read source binding; no solver."""
import copy
import json
import math

import pytest

from tercas import en_ue_catalog_operators as candidate
from tercas import en_ue_qualified_library as library


@pytest.fixture(scope='module')
def snapshots():
    # index 12 is the deliberately partial Ue100x50x17 t1.20 row.
    from tercas.catalogs import entries
    thin=next(i for i,e in enumerate(entries()) if e['family']=='Ue' and
              e['dimensions_mm']==dict(h=100,bf=50,lip=17,t=1.2))
    return {i:library.build_qualified_component_sections(i) for i in (0,thin,82)}


def _seal(value):
    value['content_sha256']=library._sha({k:v for k,v in value.items() if k!='content_sha256'})


def _thin(snapshots):
    return next(v for v in snapshots.values() if v['nominal_identity']['dimensions_mm']==dict(h=100,bf=50,lip=17,t=1.2))


def test_static_inventory_exact_coverage_no_promotion():
    inventory=library._inventory()
    assert inventory['profile_count']==83
    assert inventory['signed_branch_count']==498
    assert inventory['eligible_signed_branch_count']==400
    counts={name:sum(r['eligible_by_action'][name] for r in inventory['entries'].values()) for name in library.ACTIONS}
    assert counts==dict(N_tension=83,N_compression=83,Mx_positive=60,Mx_negative=60,My_positive=74,My_negative=40)
    assert sum(all(r['eligible_by_action'].values()) for r in inventory['entries'].values())==40
    for row in inventory['entries'].values():
        assert row['source_binding']['action_convention']==library.ACTION_CONVENTION
        for action in library.ACTIONS:
            floor=row['signed_capacity_floor'][action]
            assert (type(floor) is int and floor>0) if row['eligible_by_action'][action] else floor is None


def test_explicit_transition_preserves_original_candidate_and_all_global_flags(snapshots):
    for qualified in snapshots.values():
        c=library._restore_candidate_snapshot(qualified);before=copy.deepcopy(c)
        candidate.verify_catalog_component_sections(c)
        with pytest.raises(ValueError):candidate.verify_catalog_component_sections(qualified)
        output=library.qualify_audited_candidate(c,expected_catalog_index=c['catalog_index'])
        assert c==before and output==qualified
        assert c['schema']==candidate.SCHEMA and c['runtime_release_approved'] is False
        assert c['review_status']=='candidate_pending_independent_review'
        assert 'normal_component_runtime_approved' not in c
        assert qualified['schema']==library.SCHEMA and qualified['normal_component_runtime_approved'] is True
        assert all(qualified[key] is False for key in library.FALSE_FLAGS)
        for component in qualified['components'].values():
            assert component['normal_component_runtime_approved'] is component['eligible']
        assert library.INVENTORY_SHA256 not in json.dumps(qualified)  # no circular hash link


@pytest.mark.parametrize('mutation',['coefficient_1ulp','material','geometry_node','geometry_hash',
                                     'eligibility','audit','convention','method','flags','source_candidate_hash'])
def test_rehashed_qualified_mutations_rejected_even_when_floors_unchanged(snapshots,mutation):
    q=copy.deepcopy(_thin(snapshots));binding=library.source_binding(q)
    if mutation=='coefficient_1ulp':
        values=q['components']['N_tension']['sigma_coefficients_c0_cx_cy']
        old=values[0];values[0]=math.nextafter(old,math.inf)
        assert math.floor(250/old)==math.floor(250/values[0])
    elif mutation=='material':q['material']['E_MPa']=200000.
    elif mutation=='geometry_node':q['nodes_xy_mm'][0][0]=math.nextafter(q['nodes_xy_mm'][0][0],math.inf)
    elif mutation=='geometry_hash':q['nodes_sha256']='0'*64
    elif mutation=='eligibility':q['components']['Mx_positive']['eligible']=True
    elif mutation=='audit':q['components']['N_compression']['stiffeners'][0]['K_N_mm2']+=1.
    elif mutation=='convention':q['stress_convention']='N compression positive'
    elif mutation=='method':q['method_revision']+='-unreviewed'
    elif mutation=='flags':q['whole_member_approved']=True
    else:q['qualification']['source_candidate_content_sha256']='0'*64
    _seal(q)
    with pytest.raises(ValueError):library.validate_saved(q,binding)


def test_rehashed_candidate_not_auto_registered(snapshots):
    q=_thin(snapshots);c=library._restore_candidate_snapshot(q)
    coeff=c['components']['N_tension']['sigma_coefficients_c0_cx_cy'];coeff[0]=math.nextafter(coeff[0],math.inf)
    _seal(c);candidate.verify_catalog_component_sections(c)
    with pytest.raises(ValueError,match='not exactly qualified'):
        library.qualify_audited_candidate(c,expected_catalog_index=q['catalog_index'])
    fake=library._qualified_payload(c,library._reference_id(q['catalog_index']))
    with pytest.raises(ValueError,match='unknown'):library.verify_qualified_component_sections(fake)


def test_known_reference_substitution_rejected_by_original_source(snapshots):
    a,b=list(snapshots.values())[:2]
    library.verify_qualified_component_sections(b)  # genuinely known in isolation
    source=library.source_binding(a)
    with pytest.raises(ValueError,match='same original source'):library.validate_saved(b,source)
    cb=library._restore_candidate_snapshot(b)
    with pytest.raises(ValueError):library.qualify_audited_candidate(cb,expected_catalog_index=a['catalog_index'])
    wrong=copy.deepcopy(a);wrong['qualification']=copy.deepcopy(b['qualification']);_seal(wrong)
    with pytest.raises(ValueError):library.validate_saved(wrong,source)
    for field in ('catalog_index','catalog_id','profile_id','nodes_sha256','nominal_identity_sha256','material','action_convention'):
        changed=copy.deepcopy(source);changed[field]=copy.deepcopy(library.source_binding(b)[field])
        if changed==source:changed[field]='different'
        with pytest.raises(ValueError):library.validate_saved(a,changed)


def test_zero_only_dispenses_the_branch_never_integrity_or_source(snapshots):
    q=_thin(snapshots);binding=library.source_binding(q)
    assert not q['components']['Mx_positive']['eligible']
    assert library.require_component(q,'Mx',0,expected_source_binding=binding) is None
    assert library.require_component(q,'N',1,expected_source_binding=binding)['normal_component_runtime_approved'] is True
    for value in (1.,math.ulp(0.)):
        with pytest.raises(ValueError,match='remains pending'):
            library.require_component(q,'Mx',value,expected_source_binding=binding)
    for value in (True,float('nan')):
        with pytest.raises(ValueError):library.require_component(q,'N',value,expected_source_binding=binding)
    changed=copy.deepcopy(q);changed['catalog_index']=0;_seal(changed)
    with pytest.raises(ValueError):library.require_component(changed,'Mx',0,expected_source_binding=binding)


def test_saved_read_and_normal_provider_never_rebuild(snapshots,monkeypatch):
    from tercas import catalogs,catalog_torsion_section,weak_pierin
    from tercas.three_girt_en_normal import en1993_normal_components
    def forbidden(*args,**kwargs):raise AssertionError('Saved reading must not rederive a section')
    bindings={i:library.source_binding(q) for i,q in snapshots.items()}
    before=copy.deepcopy(snapshots)
    for module,name in ((candidate,'build_catalog_component_sections'),(candidate,'_geometry'),
                        (candidate,'_capacity_floor'),(catalogs,'catalog_entry'),(catalogs,'entries'),
                        (catalog_torsion_section,'prepare'),(catalog_torsion_section,'nominal_channel_nodes'),
                        (weak_pierin,'reference_for_index'),(en1993_normal_components,'build_component_sections'),
                        (library,'build_qualified_component_sections')):
        monkeypatch.setattr(module,name,forbidden)
    library._inventory.cache_clear()  # exercise static file load, not a cached generated section
    for i,q in snapshots.items():
        library.validate_saved(q,bindings[i])
        assert library.require_component(q,'N',1,expected_source_binding=bindings[i])['eligible']
        reference=library.normal_capacity_reference(i,q['content_sha256'])
        assert reference['signed_capacity_floor']==q['signed_capacity_floor']
    assert snapshots==before


def test_normal_provider_is_not_a_shear_or_combined_capacity_qualification(snapshots):
    for index,q in snapshots.items():
        ref=library.normal_capacity_reference(index,q['content_sha256'])
        assert ref['schema']=='EN_Ue_catalog_normal_capacity_reference_v1'
        assert ref['action_convention']==library.ACTION_CONVENTION
        assert ref['inventory_sha256']==library.INVENTORY_SHA256
        assert 'shear_capacity_lower_N' not in ref and 'shear_capacity_qualification' not in ref
        assert all(ref[key] is False for key in library.FALSE_FLAGS)
        assert ref['torsional_interaction_qualified'] is False
        for digest in ('0'*64,q['qualification']['source_candidate_content_sha256']):
            with pytest.raises(ValueError):library.normal_capacity_reference(index,digest)
        ref['signed_capacity_floor']['N_tension']=0
        assert library.normal_capacity_reference(index,q['content_sha256'])['signed_capacity_floor']['N_tension']>0
    with pytest.raises(ValueError):library.qualified_reference(83)  # plain U
    with pytest.raises(ValueError):library.qualified_reference(True)


def test_rehashed_inventory_corruption_rejected_by_external_code_pin(tmp_path,monkeypatch):
    data=copy.deepcopy(library._inventory());data['entries']['0']['signed_capacity_floor']['N_tension']+=1;_seal(data)
    path=tmp_path/'untrusted.json';path.write_text(json.dumps(data))
    monkeypatch.setattr(library,'INVENTORY_PATH',path);library._inventory.cache_clear()
    try:
        with pytest.raises(ValueError,match='trusted release'):library.qualified_reference(0)
    finally:library._inventory.cache_clear()


def test_fresh_build_rederives_and_unknown_fresh_candidate_stays_pending(snapshots,monkeypatch):
    q=_thin(snapshots);original=candidate.build_catalog_component_sections;calls=[]
    def tracked(index,**material):
        calls.append(index);return original(index,**material)
    monkeypatch.setattr(candidate,'build_catalog_component_sections',tracked)
    assert library.build_qualified_component_sections(q['catalog_index'])==q
    assert calls==[q['catalog_index']]
    def corrupted(index,**material):
        value=original(index,**material);value['components']['N_tension']['capacity_audit']['first_yield_lower']+=1e-6
        _seal(value);return value
    monkeypatch.setattr(candidate,'build_catalog_component_sections',corrupted)
    with pytest.raises(ValueError,match='not exactly qualified'):library.build_qualified_component_sections(q['catalog_index'])
