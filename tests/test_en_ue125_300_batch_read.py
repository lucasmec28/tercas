"""Batch authentication and detached presentation use fabricated inputs only."""
import copy
import json
import pytest
from tercas import isolated_en_ue125_300 as core
from tercas import isolated_en_ue125_300_application as app
from tercas import isolated_en_ue125_300_ui as ui
from tercas import en_ue125_300_authority as authority
from tercas import en_ue125_shear300 as shear
from test_isolated_en_ue125_300 import make,summary
from test_isolated_en_ue125_300_application import data
from en_ue_test_helpers import run


@pytest.fixture(scope='module')
def saved():
    source=make();normal=authority.read();origin='Synthetic batch reader'
    check=core.calculate(source,normal_snapshot=normal,model_origin=origin)
    request=dict(check=check,summary=summary(source),source_sha256=core._sha(source))
    return request,normal,origin


def batch(saved,requests=None):
    request,normal,origin=saved
    return core.validate_saved_many(requests if requests is not None else [request],normal_snapshot=normal,model_origin=origin)


def test_forty_requests_authenticate_common_authorities_once_per_call(saved,monkeypatch):
    batch(saved);counts={k:0 for k in ('validate_normal','validate_shear','section_reference','_authenticate_shear_files','_authenticate_normal_file')}
    for key in counts:
        original=getattr(core,key)
        def wrapped(*a,_key=key,_fn=original,**kw):
            counts[_key]+=1
            return _fn(*a,**kw)
        monkeypatch.setattr(core,key,wrapped)
    requests=[copy.deepcopy(saved[0]) for _ in range(40)]
    before=core._sha(requests)
    assert batch(saved,requests)
    assert counts==dict.fromkeys(counts,1)
    assert batch(saved,requests)
    assert counts==dict.fromkeys(counts,2)  # reauthenticate even on warm hits
    assert core._sha(requests)==before


@pytest.mark.parametrize('path_name',['SOURCE_PATH','INVENTORY_PATH'])
def test_warm_batch_rejects_current_rehashed_shear_files(saved,monkeypatch,tmp_path,path_name):
    batch(saved)
    value=json.loads(getattr(shear,path_name).read_text())
    value['unqualified_revision']='synthetic tamper'
    value['content_sha256']=shear._sha({k:v for k,v in value.items() if k!='content_sha256'})
    path=tmp_path/'changed.json';path.write_text(json.dumps(value))
    monkeypatch.setattr(shear,path_name,path)
    with pytest.raises(ValueError,match='authority file'):batch(saved)
    # The legacy single-check API also reauthenticates the actual files.
    request,normal,origin=saved
    with pytest.raises(ValueError):core.validate_saved(request['check'],request['summary'],normal_snapshot=normal,
        source_sha256=request['source_sha256'],model_origin=origin)


def test_native_types_required_even_when_canonical_json_hash_matches(saved):
    batch(saved);request=copy.deepcopy(saved[0])
    nodes=request['check']['source_demand']['section']['nodes_xy_mm']
    nodes[0]=tuple(nodes[0])
    assert core._sha(request)==core._sha(saved[0])
    with pytest.raises(ValueError,match='native JSON'):batch(saved,[request])


@pytest.mark.parametrize('change',['stress','shear','source_node','summary'])
def test_changed_rehashed_request_is_not_a_warm_proof(saved,change):
    batch(saved);request=copy.deepcopy(saved[0]);check=request['check']
    if change=='stress':check['stress']['criteria']['normal']['index_upper_bound']=0.
    elif change=='shear':
        # Keep the same declared hash: grouping must use real certificate content.
        check['shear_source_snapshot']['shear_capacity_lower_N']['strong']*=2
    elif change=='source_node':
        demand=check['source_demand'];section=demand['section'];section['nodes_xy_mm'][0][0]+=.01
        section['content_sha256']=core._sha({k:v for k,v in section.items() if k!='content_sha256'})
        request['source_sha256']=check['source_analysis_sha256']=core._sha(demand)
        request['summary']=summary(demand)
    else:request['summary']['small_rotation_warning']=not request['summary']['small_rotation_warning']
    check['content_sha256']=core._sha({k:v for k,v in check.items() if k!='content_sha256'})
    with pytest.raises(ValueError):batch(saved,[saved[0],request])


def test_authority_failure_after_warm_batch_still_rejects(saved,monkeypatch):
    batch(saved)
    def fail(*a,**k):raise ValueError('Synthetic changed normal authority file')
    monkeypatch.setattr(core,'validate_normal',fail)
    with pytest.raises(ValueError,match='changed normal'):batch(saved)


@pytest.fixture(scope='module')
def result():return run(data())


def test_presentation_is_detached_and_preserved_api_is_complete(result):
    before=json.dumps(result,ensure_ascii=False,sort_keys=True)
    full=app.preserved(result);view=app._presentation_view(result)
    assert ui.rows(full)==ui.rows(view) and ui.text_lines(full)==ui.text_lines(view)
    assert full['records'][0]['check']['source_demand']
    assert full['records'][0]['check']['pieces']
    assert 'source_demand' not in view['records'][0]['check']
    assert 'pieces' not in view['records'][0]['check']
    view['normal_snapshot']['material']['fyb_MPa']=0.
    view['records'][0]['check']['stress']['criteria']['normal']['index_upper_bound']=0.
    assert json.dumps(result,ensure_ascii=False,sort_keys=True)==before
    assert app.preserved(result)==full


def test_panorama_and_word_view_have_identical_content(result,monkeypatch):
    new=app.global_context(result,sectional=True)
    monkeypatch.setattr(app,'_presentation_view',app.preserved)
    assert app.global_context(result,sectional=True)==new


def test_forged_presentation_never_skips_full_validation(result):
    changed=copy.deepcopy(result);ev=changed[app.FIELD]
    ev['records'][0]['check']['source_demand']['elements'][0]['coefficients']['B_Nmm2'][0]+=.1
    ev['snapshot_sha256']=app.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):app._presentation_view(changed)


def test_unavailable_shear_file_fails_closed_after_hit(saved,monkeypatch,tmp_path):
    batch(saved)
    monkeypatch.setattr(shear,'SOURCE_PATH',tmp_path/'missing.json')
    with pytest.raises(ValueError,match='unavailable'):batch(saved)


def test_current_normal_file_rehashed_after_warmup_is_rejected(saved,monkeypatch,tmp_path):
    batch(saved)
    value=json.loads(authority.PATH.read_text());value['material']['fyb_MPa']=301.
    value['content_sha256']=authority._sha({k:v for k,v in value.items() if k!='content_sha256'})
    path=tmp_path/'normal.json';path.write_text(json.dumps(value));monkeypatch.setattr(authority,'PATH',path)
    with pytest.raises(ValueError,match='normal authority file'):batch(saved)
    path.unlink()
    with pytest.raises(ValueError,match='unavailable'):batch(saved)
