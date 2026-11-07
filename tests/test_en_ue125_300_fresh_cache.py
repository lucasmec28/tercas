"""Synthetic-only fresh-proof cache; imported snapshots still require full replay."""
import copy
import json
import time
import pytest
from tercas import isolated_en_ue125_300 as en
from tercas.en_ue125_300_authority import read
from test_isolated_en_ue125_300 import make,summary


@pytest.fixture(scope='module')
def source():return make()


def clear():
    with en._READ_LOCK:en._VERIFIED_READS.clear()


def kw(d):return dict(normal_snapshot=read(),model_origin='Synthetic fresh proof',source_sha256=en._sha(d))


def generate(d):return en.calculate(d,normal_snapshot=read(),model_origin='Synthetic fresh proof')


def test_output_byte_identical_and_fresh_first_read_does_not_replay(source,monkeypatch):
    clear()
    expected=en._calculate(source,normal_snapshot=read(),model_origin='Synthetic fresh proof')
    assert not en._VERIFIED_READS
    actual=generate(source)
    assert json.dumps(actual,ensure_ascii=False,allow_nan=False)==json.dumps(expected,ensure_ascii=False,allow_nan=False)
    assert len(en._VERIFIED_READS)==1
    def fail(*a,**k):raise AssertionError('Own finished proof must not be recomputed')
    monkeypatch.setattr(en,'_calculate',fail)
    assert en.validate_saved(actual,summary(source),**kw(source))


def test_external_cold_snapshot_always_replays(source,monkeypatch):
    value=json.loads(json.dumps(generate(source)));clear();calls=[];original=en._calculate
    def spy(*a,**k):calls.append(1);return original(*a,**k)
    monkeypatch.setattr(en,'_calculate',spy)
    assert en.validate_saved(value,summary(source),**kw(source))
    assert calls==[1] and len(en._VERIFIED_READS)==1
    assert en.validate_saved(value,summary(source),**kw(source)) and calls==[1]


def test_failed_external_check_seeds_neither_candidate_nor_expected(source):
    value=generate(source);clear();value['mv']['index_upper']=0.
    value['content_sha256']=en._sha({k:v for k,v in value.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(value,summary(source),**kw(source))
    assert not en._VERIFIED_READS


@pytest.mark.parametrize('authority',['validate_normal','validate_shear','section_reference'])
def test_authorities_still_required_after_fresh_generation(source,monkeypatch,authority):
    clear();value=generate(source)
    def fail(*a,**k):raise ValueError('Authority changed')
    monkeypatch.setattr(en,authority,fail)
    with pytest.raises(ValueError,match='Authority changed'):en.validate_saved(value,summary(source),**kw(source))


@pytest.mark.parametrize('mutation',['field','control','native_type','origin'])
def test_mutation_after_generation_cannot_reuse_fresh_entry(source,mutation):
    clear();value=generate(source);args=kw(source)
    if mutation=='field':value['source_demand']['elements'][0]['coefficients']['B_Nmm2'][0]+=1.
    elif mutation=='control':value['stress']['criteria']['normal']['index_upper_bound']=0.
    elif mutation=='native_type':value['source_demand']['node_phi_rad']=tuple(value['source_demand']['node_phi_rad'])
    else:args['model_origin']='Different origin'
    value['content_sha256']=en._sha({k:v for k,v in value.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(value,summary(source),**args)
    assert len(en._VERIFIED_READS)==1


def test_failed_generation_never_seeds(source):
    clear();d=copy.deepcopy(source);d['node_phi_rad'][1]+=.01
    with pytest.raises(ValueError):generate(d)
    assert not en._VERIFIED_READS
