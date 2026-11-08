"""In-process success reuse, never an offline replacement for source replay."""
import copy
import io
import json
import pytest
from docx import Document
from tercas import nbr_family_validation_cache as cache, nbr_ue_family_application as app
from tercas import ue_catalog_reference as own
from test_nbr_family_height_integration import source


@pytest.fixture(autouse=True)
def fresh_cache():
    cache.clear();yield;cache.clear()


def fail(*a,**kw):raise AssertionError('Warm presentation must not reopen sources or solve')


def test_producer_word_ui_and_json_read_reuse_same_content(monkeypatch):
    from tercas import nbr_ue_family_ui as ui
    r=app.attach(source());before=copy.deepcopy(r)
    monkeypatch.setattr(own,'_source',fail)
    monkeypatch.setattr(app,'_build',fail)
    assert app.preserved(json.loads(json.dumps(r)))==r[app.FIELD]
    doc=Document();ui.report(doc,r);b=io.BytesIO();doc.save(b)
    assert Document(io.BytesIO(b.getvalue())).tables
    class UI:
        def __getattr__(self,name):return lambda *a,**kw:None
    ui.show(UI(),r)
    detached=app.preserved(r);detached['records'].clear()
    assert r==before


def test_cold_versioned_replay_then_warm_reuse(monkeypatch):
    r=source();r[app.FIELD]=app._build(r,legacy_product_floor=True)
    assert r[app.FIELD]['schema']==app.LEGACY_SCHEMA_V5
    real=app._build;calls=[]
    def record(*a,**kw):calls.append(kw);return real(*a,**kw)
    monkeypatch.setattr(app,'_build',record)
    cache.clear();assert app.preserved(r)==r[app.FIELD]
    assert len(calls)==1 and calls[0]['legacy_product_floor'] is True
    assert app.preserved(r)==r[app.FIELD] and len(calls)==1
    cache.clear();assert app.preserved(r)==r[app.FIELD] and len(calls)==2


@pytest.mark.parametrize('mutation',['capacity','input','source','rehash','combination'])
def test_any_consumed_mutation_cannot_reuse_success(monkeypatch,mutation):
    r=app.attach(source());bad=copy.deepcopy(r)
    if mutation=='capacity':bad[app.FIELD]['records'][0]['components'][0]['capacity_Nmm']*=2
    elif mutation=='input':bad['input_data']['q_uls']*=2
    elif mutation=='source':bad[own.EVIDENCE]['geometric_properties']['J_mm4']*=2
    elif mutation=='combination':bad[app.FIELD]['records'][0]['combination']['q_vector']['normal']*=2
    else:
        h=bad[app.FIELD]['records'][0]['height_source'];h['Me_Nmm']*=2
        h.pop('snapshot_sha256');h['snapshot_sha256']=own.digest(h)
    calls=[]
    original=app._preserved_uncached
    def record(x):calls.append(True);return original(x)
    monkeypatch.setattr(app,'_preserved_uncached',record)
    with pytest.raises((ValueError,KeyError)):app.preserved(bad)
    assert calls==[True] and not cache.contains(cache.key(bad))
    with pytest.raises((ValueError,KeyError)):app.preserved(bad)
    assert calls==[True,True]


def test_native_json_aliases_never_share_success(monkeypatch):
    r=app.attach(source());bad=copy.deepcopy(r)
    bad[app.FIELD]['records']=tuple(bad[app.FIELD]['records'])
    assert cache.key(bad) is None and cache.key(r) is not None
    calls=[]
    def ingress(x):calls.append(True);raise ValueError('cold validation invoked')
    monkeypatch.setattr(app,'_preserved_uncached',ingress)
    with pytest.raises(ValueError,match='cold'):app.preserved(bad)
    assert calls==[True]
    bad=copy.deepcopy(r);bad['input_data']['q_uls']=float('nan')
    assert cache.key(bad) is None


def test_missing_null_and_each_dependency_bound():
    base={app.FIELD:{'schema':'synthetic'},'input_data':{}}
    k=cache.key(base)
    for field in cache.DEPENDENCIES:
        other=copy.deepcopy(base);other[field]=None
        assert cache.key(other)!=k
    assert cache.key(dict(base,unconsumed_display_caption='caption'))==k


def test_lru_limit_and_failed_replay_never_stored(monkeypatch):
    for i in range(cache.LIMIT+2):cache.remember(str(i))
    assert not cache.contains('0') and not cache.contains('1')
    assert cache.contains(str(cache.LIMIT+1))
    r={app.FIELD:{'schema':'bad'},'input_data':{}}
    monkeypatch.setattr(app,'_preserved_uncached',lambda x: (_ for _ in ()).throw(ValueError('bad')))
    for _ in range(2):
        with pytest.raises(ValueError):app.preserved(r)
        assert not cache.contains(cache.key(r))


def test_cold_session_still_requires_source_not_offline(monkeypatch):
    r=app.attach(source());monkeypatch.setattr(own,'_source',fail)
    assert app.preserved(r)==r[app.FIELD]
    cache.clear()
    with pytest.raises(AssertionError,match='reopen'):app.preserved(r)
    assert not cache.contains(cache.key(r))



def test_caller_mutation_after_capture_does_not_replace_validated_return(monkeypatch):
    r=app.attach(source());expected=copy.deepcopy(r[app.FIELD])
    contains=cache.contains
    def race(token):
        r[app.FIELD]['records'][0]['components'][0]['capacity_Nmm']*=2
        return contains(token)
    monkeypatch.setattr(cache,'contains',race)
    assert app.preserved(r)==expected
    assert r[app.FIELD]!=expected


def test_girt_source_and_packet_reuse_without_roof_or_solver(monkeypatch):
    from test_girt_flt_adapter import source as girt_source
    r=app.attach(girt_source())
    assert r[app.FIELD]['schema']==app.GIRT_SCHEMA
    monkeypatch.setattr(own,'_source',fail);monkeypatch.setattr(app,'_build',fail)
    assert app.preserved(json.loads(json.dumps(r)))==r[app.FIELD]
