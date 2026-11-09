"""Read integrity: hashes alone cannot authenticate a numerical EN decision."""
import copy
import json
from pathlib import Path
import pytest
from docx import Document
from tercas.three_girt_en_normal import application as en, centroid_policy as cp, snapshot_policy as sp
from tercas.three_girt_en_normal import ui, report
from tercas.three_girt_assessment import application as assessment


def historical():
    return json.loads((Path(__file__).parent/'data/EN_snapshot_synthetic_CT_v5.json').read_text())


def reseal(d):
    c=d[en.FIELD]
    c['content_sha256']=en.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})


def erase_observations(d):
    def mutate(v):
        if isinstance(v,list):
            for r in v:mutate(r)
        elif isinstance(v,dict):
            for k in list(v):
                if k in ('complete_envelope','partial_maximum','maximum_absolute'):v[k]=None
                elif k=='observed_normal_exceedance':v[k]=False
                elif k=='normal_criterion':v[k]='within_1_by_full_interval_upper_bound'
                elif k=='index_upper_bounds':v[k]={x:0. for x in v[k]}
                elif k!='EN_bending_shear_component':mutate(v[k])
            if 'index_lower_witness' in v and 'index_upper_bound' in v:
                v.update(witness=None,index_lower_witness=None,index_upper_bound=0.,partial_index_upper_bound=None,
                         bound_gap=None,criterion='within_1_by_full_interval_upper_bound')
    c=d[en.FIELD];mutate(c['rows']);mutate(c['per_member'])
    for row in c['rows']:row[cp.FIELD]=cp.build(row,c['component_sections'])
    reseal(d)


def forbidden_reads(monkeypatch):
    from tercas.three_girt_warping import network
    def forbidden(*a,**k):raise AssertionError('Reader searched or solved the model')
    monkeypatch.setattr(network,'solve',forbidden)
    monkeypatch.setattr(en.si,'envelope',forbidden)
    monkeypatch.setattr(en.f,'stress_extrema',forbidden)
    monkeypatch.setattr(en,'calculate',forbidden)
    monkeypatch.setattr(en,'build_component_sections',forbidden)


@pytest.mark.parametrize('adulterated',[False,True])
def test_historical_observations_are_immutable_not_current_decisions(monkeypatch,adulterated):
    d=historical()
    if adulterated:erase_observations(d)
    before=copy.deepcopy(d);forbidden_reads(monkeypatch)
    c=en.saved_component(d)
    assert c is d[en.FIELD]
    assert cp.decision(c,'middle','normal',c['per_member']['middle']['normal_criterion'])==sp.PENDING
    summary=en.summary(c)
    assert summary['members']['middle']['normal_criterion']==sp.PENDING
    assert all(summary['members']['middle']['shear_interaction'][k]['criterion']==sp.PENDING for k in ('normal','shear','interaction'))
    assert 'não autenticada' in ui.rows(c)[0]['Resultado']
    assert all('não autenticada' in row['Resultado'] for row in ui.shear_rows(c))
    checks=assessment._en(d,c,None)
    assert all(r['status']=='pending' for r in checks)
    doc=Document();report.append(doc,d)
    assert sp.NOTICE in '\n'.join(p.text for p in doc.paragraphs)
    assert 'decisão não autenticada' in '\n'.join(p.text for p in doc.paragraphs)
    assert d==before
    assert json.loads(json.dumps(d))==before


@pytest.fixture(scope='module')
def fresh():
    d=historical();config=d[en.FIELD]['configuration'];d.pop(en.FIELD)
    return en.attach(d,config)


def test_new_certificate_roundtrip_no_search(monkeypatch,fresh):
    d=json.loads(json.dumps(fresh));before=copy.deepcopy(d);forbidden_reads(monkeypatch)
    c=en.saved_component(d)
    assert c['schema']==en.CENTRAL_SCHEMA
    assert sp.certified(c)
    assert all(row['branches'][0]['bound_certificate'] for r in c['rows'] for row in r['pieces'] if row['complete'])
    checks=assessment._en(d,c,None)
    assert {r['status'] for r in checks}=={'fails'}
    assert all(cp.decision(c,'middle',k,(c['per_member']['middle']['normal'] if k=='normal' else c['per_member']['middle']['shear_interaction'][k])['criterion']).startswith('above_1') for k in ('normal','shear','interaction'))
    doc=Document();report.append(doc,d)
    assert sp.NOTICE not in '\n'.join(p.text for p in doc.paragraphs)
    assert d==before


def test_coordinated_zero_rehash_rejected(monkeypatch,fresh):
    d=copy.deepcopy(fresh);erase_observations(d);forbidden_reads(monkeypatch)
    with pytest.raises(ValueError):en.saved_component(d)


def test_false_witness_rehash_rejected(monkeypatch,fresh):
    d=copy.deepcopy(fresh)
    def mutate(v):
        if isinstance(v,list):
            for x in v:mutate(x)
        elif isinstance(v,dict):
            if 'sigma_MPa' in v:v['sigma_MPa']+=.25
            for x in v.values():mutate(x)
    mutate(d[en.FIELD]);reseal(d);forbidden_reads(monkeypatch)
    with pytest.raises(ValueError,match='witness'):en.saved_component(d)


def test_legacy_cache_cannot_reactivate_decision():
    c=historical()[en.FIELD]
    for status in ('meets','fails'):
        with pytest.raises(ValueError,match='Panorama'):
            sp.verify_assessment(c,dict(checks=[dict(id='EN:middle:normal',status=status)]),('middle',))


def test_other_thickness_certificate_rejected(fresh):
    from tercas.three_girt_en_normal.snapshot_certificate import verify
    from tercas.three_girt_en_normal.en1993_normal_components import build_component_sections
    d=copy.deepcopy(fresh);c=d[en.FIELD]
    profile=json.loads((Path(__file__).parents[1]/'tercas/data/torsion_profiles/ue100x50x17_t2.65.json').read_text())
    c['component_sections']=build_component_sections(profile)
    with pytest.raises(ValueError,match='section differs|referência resistente'):verify(c,d)


def test_forged_v6_assessment_rejected_without_search(monkeypatch,fresh):
    d=copy.deepcopy(fresh);a=assessment.assess(d)
    assert any(r['status']=='fails' for r in a['checks'] if r['id'].startswith('EN:'))
    forbidden_reads(monkeypatch)
    assert assessment.saved_assessment(d,a) is a
    for records in (a['checks'],next(g for g in a['groups'] if g['id']=='EN_section')['checks']):
        for r in records:
            if r['id'].startswith('EN:'):r.update(status='meets',index=0.)
    a['content_sha256']=assessment.fingerprint({k:v for k,v in a.items() if k!='content_sha256'})
    with pytest.raises(ValueError,match='inventory decisions'):assessment.saved_assessment(d,a)


@pytest.mark.parametrize('target',['group','summary','banner'])
def test_forged_assessment_summary_rejected(monkeypatch,fresh,target):
    d=copy.deepcopy(fresh);a=assessment.assess(d);forbidden_reads(monkeypatch)
    if target=='group':next(g for g in a['groups'] if g['id']=='EN_section')['status']='aprovado'
    elif target=='summary':a['status']='aprovado'
    else:a['display_summary']='Critérios atendidos'
    a['content_sha256']=assessment.fingerprint({k:v for k,v in a.items() if k!='content_sha256'})
    with pytest.raises(ValueError):assessment.saved_assessment(d,a)


def test_semantic_validation_cache_binds_actual_bytes_and_never_failures(monkeypatch,fresh):
    en._validated_snapshot.cache_clear();d=copy.deepcopy(fresh)
    before=copy.deepcopy(d);assert en.saved_component(d) is d[en.FIELD]
    count=en._validated_snapshot.cache_info().hits
    assert en.saved_component(copy.deepcopy(d))==d[en.FIELD]
    assert en._validated_snapshot.cache_info().hits==count+1
    size=en._validated_snapshot.cache_info().currsize
    erase_observations(d)
    with pytest.raises(ValueError):en.saved_component(d)
    assert en._validated_snapshot.cache_info().currsize==size
    assert fresh==before


@pytest.mark.parametrize('alias',[lambda d:d[en.FIELD].update(rows=tuple(d[en.FIELD]['rows'])),
    lambda d:d['input_data'].update(alias={1:'non-string key'}),
    lambda d:d['input_data'].update(alias=float('nan'))])
def test_semantic_validation_cache_rejects_non_json_aliases(fresh,alias):
    d=copy.deepcopy(fresh);en.saved_component(d);alias(d)
    with pytest.raises(ValueError):en.saved_component(d)


def test_semantic_validation_cache_success_eviction_is_not_authority(fresh):
    from functools import lru_cache
    cache=lru_cache(maxsize=1)(en._validated_snapshot.__wrapped__)
    source=en.mechanical_source(fresh);payload=en._validation_payload(fresh[en.FIELD],source)
    profile=(Path(__file__).parents[1]/'tercas/data/torsion_profiles/ue100x50x17_t3.35.json').read_bytes()
    assert cache(en.VALIDATION_CACHE_REVISION,payload,profile)
    other=copy.deepcopy(fresh);other[en.FIELD]['configuration']['section_model_origin']+=' alternate QA'
    reseal(other)
    alternate=en._validation_payload(other[en.FIELD],en.mechanical_source(other))
    assert cache(en.VALIDATION_CACHE_REVISION,alternate,profile)
    assert cache(en.VALIDATION_CACHE_REVISION,payload,profile)
    assert cache.cache_info().misses==3 and cache.cache_info().currsize==1


def test_semantic_cache_bool_and_order_are_distinct_actual_bytes(fresh):
    assert en._validation_payload(dict(x=True),{})!=en._validation_payload(dict(x=1),{})
    assert en._validation_payload(dict(x=1,y=2),{})!=en._validation_payload(dict(y=2,x=1),{})
    d=copy.deepcopy(fresh);en.saved_component(d)
    d[en.FIELD]['normal_limit_MPa']=True;reseal(d)
    with pytest.raises(ValueError):en.saved_component(d)


def test_mutation_during_validation_cannot_return_a_different_snapshot(monkeypatch,fresh):
    d=copy.deepcopy(fresh)
    def change(*args):d[en.FIELD]['normal_limit_MPa']=1.;return True
    monkeypatch.setattr(en,'_validated_snapshot',change)
    with pytest.raises(ValueError,match='during validation'):en.saved_component(d)


def test_new_attach_json_boundary_preserves_serialized_bytes_and_original(monkeypatch):
    import numpy as np
    source=dict(input_data=dict(a=np.float64(.125)),cases=[dict(actions=[1.,-0.,2.])],
                service_metadata=dict(points=(np.float64(2.5),3.)))
    original=copy.deepcopy(source)
    component=dict(schema=en.CENTRAL_SCHEMA,value=np.float64(1.25))
    monkeypatch.setattr(en,'calculate',lambda demand,config:copy.deepcopy(component))
    expected=copy.deepcopy(source);expected[en.FIELD]=component
    before=json.dumps(expected,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    result=en.attach(source,{})
    after=json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    assert before==after and en.fingerprint(result)==en.fingerprint(expected)
    assert source==original and en.FIELD not in source
    en._validation_payload(result[en.FIELD],en.mechanical_source(result))


@pytest.mark.parametrize('mv_mode',['absent','pending'])
def test_operator_authority_cannot_be_bypassed_without_optional_mv(fresh,mv_mode):
    d=copy.deepcopy(fresh);en.saved_component(d)
    c=d[en.FIELD]
    for row in c['rows']:
        row.pop('EN_bending_shear_component',None)
        if mv_mode=='pending':row['EN_bending_shear_error']='Synthetic optional component unavailable'
    if mv_mode=='absent':c.pop('EN_bending_shear_schema',None)
    cert=c['component_sections'];coefficients=cert['components']['Mx_positive']['sigma_coefficients_c0_cx_cy']
    before=coefficients[2];assert before!=0.
    coefficients[2]*=.01;assert coefficients[2]!=before
    cert['content_sha256']=en.fingerprint({k:v for k,v in cert.items() if k!='content_sha256'})
    for row in c['rows']:row[cp.FIELD]=cp.build(row,cert)
    reseal(d)
    with pytest.raises(ValueError,match='referência resistente'):en.saved_component(d)


def test_replacing_entire_component_during_validation_is_detected(monkeypatch,fresh):
    d=copy.deepcopy(fresh)
    def replace(*args):
        other=copy.deepcopy(d[en.FIELD]);other['normal_limit_MPa']=1.;d[en.FIELD]=other
        return True
    monkeypatch.setattr(en,'_validated_snapshot',replace)
    with pytest.raises(ValueError,match='during validation'):en.saved_component(d)


def test_warm_semantic_cache_does_not_skip_external_reference_gates(monkeypatch,fresh):
    from tercas import ue_family_reference as family
    en.saved_component(fresh)
    def changed():raise ValueError('Synthetic changed external reference')
    monkeypatch.setattr(family,'gate',changed)
    with pytest.raises(ValueError,match='changed external reference'):en.saved_component(fresh)


def test_owned_cold_validation_preserves_aliases_and_cannot_mutate_original(monkeypatch,fresh):
    d=copy.deepcopy(fresh);shared=dict(values=[1.,2.,3.]);d['qa_a']=shared;d['qa_b']=shared
    d[en.FIELD]['source_demand_sha256']=en.fingerprint(en.mechanical_source(d));reseal(d)
    before=copy.deepcopy(d);original=en._saved_component_uncached
    def check_owned(value):
        assert value['qa_a'] is value['qa_b'] and value['qa_a'] is not shared
        return original(value)
    monkeypatch.setattr(en,'_saved_component_uncached',check_owned);en._validated_snapshot.cache_clear()
    assert en.saved_component(d) is d[en.FIELD] and d==before


def test_mutated_owned_copy_cannot_enter_success_cache(monkeypatch,fresh):
    d=copy.deepcopy(fresh);before=copy.deepcopy(d);en._validated_snapshot.cache_clear()
    def change_owned(value):value[en.FIELD]['normal_limit_MPa']=1.;return value[en.FIELD]
    monkeypatch.setattr(en,'_saved_component_uncached',change_owned)
    with pytest.raises(ValueError,match='owned snapshot changed during'):en.saved_component(d)
    assert d==before and en._validated_snapshot.cache_info().currsize==0


def test_full_new_result_matches_scalar_certificate_implementation(monkeypatch,fresh):
    from en_scalar_stress_oracle import scalar_verify
    from tercas.three_girt_en_normal import bound_certificate as bc
    source=copy.deepcopy(fresh);expected=source.pop(en.FIELD)
    before=copy.deepcopy(source)
    monkeypatch.setattr(bc,'verify',scalar_verify)
    actual=en.calculate(source,expected['configuration'])
    assert actual==expected and source==before
