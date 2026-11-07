"""Only synthetic inputs; successful full-validation tokens, never authority bypass."""
import copy,json
from pathlib import Path
import numpy as np
import pytest
from tercas import isolated_en_ue_family_application as app
from tercas import en_ue_family_provider as provider
from tercas import en_ue_family_geometry as geometry
from test_isolated_en_ue_family import data
from en_ue_test_helpers import run


@pytest.fixture(scope='module')
def live():return run(data())


@pytest.fixture
def result(live):
    app._VALIDATED_RESULTS.clear()
    return json.loads(json.dumps(live))


def counter(monkeypatch):
    calls=[];original=app._validate_preserved_uncached
    def counted(value):calls.append(1);return original(value)
    monkeypatch.setattr(app,'_validate_preserved_uncached',counted)
    return calls


def test_cold_warm_real_content_and_detached(result,monkeypatch):
    calls=counter(monkeypatch);auth=[];original=provider.verify
    def verify(value):auth.append(1);return original(value)
    monkeypatch.setattr(provider,'verify',verify)
    ev=app.preserved(result)
    assert len(calls)==1
    before=len(auth)
    # A separately deserialized object must share content, never object id.
    clone=json.loads(json.dumps(result));view=app._presentation_view(clone)
    app.global_context(clone)
    assert len(calls)==1 and len(auth)==before+2
    ev['records'].clear();view['records'].clear()
    assert app.preserved(result)['records']
    assert len(calls)==1
    app._VALIDATED_RESULTS.clear();app.preserved(result)
    assert len(calls)==2


@pytest.mark.parametrize('where',['input','case','source','proof','count','unrelated'])
def test_any_mutation_forces_full_validation_even_resealed(result,monkeypatch,where):
    calls=counter(monkeypatch);app.preserved(result)
    changed=copy.deepcopy(result);ev=changed[app.FIELD]
    if where=='input':changed['input_data']['properties']['fy_MPa']=345.
    elif where=='case':ev['records'][0]['combination_id']='OTHER'
    elif where=='source':changed['torsion_evidence']['records'][0]['analysis']['E_MPa']+=1.
    elif where=='proof':
        check=ev['records'][0]['check'];check['shear']['strong_ratio_upper']+=.125
        check['content_sha256']=app.digest({k:v for k,v in check.items() if k!='content_sha256'})
    elif where=='count':ev['shear_computed_cases']=0
    else:changed['unrelated_new_field']=['must force complete validation']
    ev['snapshot_sha256']=app.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    before=len(app._VALIDATED_RESULTS)
    if where=='unrelated':app.preserved(changed)
    else:
        with pytest.raises(ValueError):app.preserved(changed)
        assert len(app._VALIDATED_RESULTS)==before
    assert len(calls)==2


@pytest.mark.parametrize('alias',[lambda:(1,2),lambda:np.float64(1.),lambda:np.int64(1),lambda:np.array([1,2])])
def test_non_native_alias_disables_cache_without_normalizing(result,monkeypatch,alias):
    calls=counter(monkeypatch)
    result['external_alias']=alias()
    assert app._cache_result_key(result) is None
    before=len(app._VALIDATED_RESULTS)
    app.preserved(result);app.preserved(result)
    assert len(calls)==2 and len(app._VALIDATED_RESULTS)==before


def test_tuple_cannot_reuse_list_token(result,monkeypatch):
    calls=counter(monkeypatch);result['external_alias']=[1,2]
    app.preserved(result);app.preserved(result);assert len(calls)==1
    result['external_alias']=(1,2)
    app.preserved(result);assert len(calls)==2
    result['external_alias']=[1,2]
    app.preserved(result);assert len(calls)==2


def test_current_authority_checked_on_warm_read(result,monkeypatch,tmp_path):
    root=provider._SOURCE_ROOT
    for name in provider.TECHNICAL_SOURCES:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((root/name).read_bytes())
    monkeypatch.setattr(provider,'_SOURCE_ROOT',tmp_path)
    app.preserved(result)
    p=tmp_path/'en_ue_family_kernel.py';p.write_bytes(p.read_bytes()+b'\n# changed current authority\n')
    with pytest.raises(ValueError,match='deterministic method'):app.preserved(result)


def test_current_geometry_changes_force_full_validation(result,monkeypatch):
    calls=counter(monkeypatch);app.preserved(result)
    original=geometry.section
    def different(index):
        out=original(index);out['omega_nodes_mm2'][0]+=.1;return out
    monkeypatch.setattr(geometry,'section',different)
    with pytest.raises(ValueError,match='Geometria'):app.preserved(result)
    assert len(calls)==2


def test_source_change_not_in_certificate_forces_full_validation(result,monkeypatch):
    calls=counter(monkeypatch);app.preserved(result)
    original=provider._source_key
    monkeypatch.setattr(provider,'_source_key',lambda:original()+'_changed_validation_source')
    app.preserved(result);assert len(calls)==2


def test_bounded_tokens_and_no_failed_entries(result,monkeypatch):
    monkeypatch.setattr(app,'_VALIDATED_RESULTS_LIMIT',2)
    for i in range(3):result['external_revision']=i;app.preserved(result)
    assert len(app._VALIDATED_RESULTS)==2
    result[app.FIELD]['computed_cases']=-1
    with pytest.raises(ValueError):app.preserved(result)
    assert len(app._VALIDATED_RESULTS)==2


def test_live_result_cache_eligibility_report(live,monkeypatch):
    """Report actual fresh objects too, without converting unsupported types."""
    paths=[]
    def walk(value,path='$'):
        t=type(value)
        if t is dict:
            for k,v in value.items():walk(v,path+'.'+str(k))
        elif t is list:
            for i,v in enumerate(value):walk(v,path+'['+str(i)+']')
        elif t not in (str,int,float,bool,type(None)):paths.append((path,t.__module__+'.'+t.__name__))
    walk(live)
    app._VALIDATED_RESULTS.clear();calls=counter(monkeypatch)
    app.preserved(live);app._presentation_view(live);app.global_context(live)
    expected=3 if app._cache_result_key(live) is None else 1
    assert len(calls)==expected
    print('LIVE_RESULT_CACHE',json.dumps(dict(eligible=expected==1,full_validations=len(calls),reads=3,non_native_paths=paths),ensure_ascii=False))


def test_checked_tuple_alias_cannot_share_warm_token(result,monkeypatch):
    calls=counter(monkeypatch);app.preserved(result)
    coefficients=result[app.FIELD]['normal_snapshot']['components']['Mx_positive']['sigma_coefficients_c0_cx_cy']
    result[app.FIELD]['normal_snapshot']['components']['Mx_positive']['sigma_coefficients_c0_cx_cy']=tuple(coefficients)
    assert app._cache_result_key(result) is None
    with pytest.raises(ValueError):app.preserved(result)
    assert len(calls)==2


def test_absent_component_keeps_legacy_constant_time_path(monkeypatch):
    monkeypatch.setattr(app,'_cache_result_key',lambda value:pytest.fail('No family means no full-result hashing'))
    assert app.preserved({'legacy':object()}) is None


def test_mutation_during_hit_authority_check_requires_full_revalidation(result,monkeypatch):
    calls=counter(monkeypatch);app.preserved(result)
    original=app._cache_authority_key
    def mutate(value):
        key=original(value)
        value[app.FIELD]['computed_cases']=-1
        return key
    monkeypatch.setattr(app,'_cache_authority_key',mutate)
    with pytest.raises(ValueError):app.preserved(result)
    assert len(calls)==2
