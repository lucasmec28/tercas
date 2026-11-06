"""Fresh independent composition guards after restoring the exact adapter.

These tests are new recovery evidence, not a reconstruction of the lost receipt.
"""
import copy
import pytest
from tercas import en_ue_catalog_capacity_reference as c


HASH = 'a' * 64
CONDITIONS = {'curling': 'required', 'shear_lag': 'required'}


def authorities():
    normal = dict(schema=c.NORMAL_SCHEMA, qualification_status=c.STATUS,
        catalog_index=0, catalog_id='synthetic-row', profile_id='synthetic-profile',
        component_sections_sha256=HASH, family='Ue', action_convention=c.CONVENTION,
        material=copy.deepcopy(c.MATERIAL), nominal_identity_sha256='b'*64,
        nodes_sha256='c'*64, inventory_sha256='d'*64, source_candidate_sha256='e'*64,
        eligible_components={key: True for key in c.BRANCHES},
        signed_capacity_floor={key: 100 for key in c.BRANCHES},
        normal_component_runtime_approved=True,
        normal_integration_conditions=copy.deepcopy(CONDITIONS),
        **{key:False for key in c.FALSE_FLAGS})
    shear = dict(schema=c.SHEAR_SCHEMA,
        source_binding={key:copy.deepcopy(normal[key]) for key in c.COMMON},
        method=c.SHEAR_METHOD,
        shear_capacity_lower_N={'strong':25, 'weak':20},
        shear_capacity_geometry={'source':'independent synthetic test'},
        integration_conditions={'transverse_only':True},
        applicability={'qualified':True},
        **{key:False for key in ('normal_operators_qualified','runtime_release_approved',
            'whole_member_approved','global_stability_qualified','physical_geometry_verified',
            'complete_EN_design_qualified','pierin_criticals_transferred',
            'NBR_capacities_used','AISI_capacities_used')})
    shear['shear_capacity_qualification'] = dict(status=c.STATUS,method=c.SHEAR_METHOD,
        walls={'strong':1,'weak':2},nodes_sha256=normal['nodes_sha256'],
        nominal_identity_sha256=normal['nominal_identity_sha256'],
        material=copy.deepcopy(c.MATERIAL),support_stiffener_credit=False,
        lip_or_corner_resistance_credit=False,source_sha256='f'*64,inventory_sha256='1'*64)
    seal(shear)
    return normal,shear


def seal(shear):
    shear['content_sha256']=c._sha({k:v for k,v in shear.items() if k!='content_sha256'})


@pytest.fixture
def source(monkeypatch):
    normal,shear=authorities()
    monkeypatch.setattr(c,'_normal_reference',lambda *a:normal)
    monkeypatch.setattr(c,'_shear_reference',lambda *a:shear)
    monkeypatch.setattr(c,'_normal_conditions',lambda:copy.deepcopy(CONDITIONS))
    return normal,shear


def test_exact_sources_remain_separate_and_inputs_are_immutable(source):
    normal,shear=source; before=copy.deepcopy(source)
    result=c.qualified_reference(0,HASH)
    assert source==before
    assert result['inventory_sha256']==normal['inventory_sha256']
    assert result['shear_capacity_qualification']['inventory_sha256']=='1'*64
    assert result['normal_integration_conditions']==CONDITIONS
    assert result['shear_integration_conditions']==shear['integration_conditions']
    assert all(result[key] is False for key in c.FALSE_FLAGS)
    assert result['content_sha256']==c._sha({k:v for k,v in result.items() if k!='content_sha256'})
    result['normal_integration_conditions']['curling']='removed'
    assert normal['normal_integration_conditions']==CONDITIONS


@pytest.mark.parametrize('key',c.COMMON)
def test_rehashed_shear_with_other_source_is_rejected(source,key):
    source[1]['source_binding'][key]='another source'
    seal(source[1])
    with pytest.raises(ValueError):c.qualified_reference(0,HASH)


@pytest.mark.parametrize('key',c.FALSE_FLAGS)
def test_normal_scope_cannot_be_promoted(source,key):
    source[0][key]=True
    with pytest.raises(ValueError):c.qualified_reference(0,HASH)


@pytest.mark.parametrize('key',c.BRANCHES)
def test_missing_branch_remains_absent_without_fallback(source,key):
    source[0]['eligible_components'][key]=False
    source[0]['signed_capacity_floor'][key]=None
    assert c.qualified_reference(0,HASH)['signed_capacity_floor'][key] is None
    source[0]['signed_capacity_floor'][key]=100
    with pytest.raises(ValueError):c.qualified_reference(0,HASH)


@pytest.mark.parametrize('value',[None,{}, {'curling':'required'}, {'curling':'removed','shear_lag':'required'}])
def test_normal_conditions_cannot_disappear(source,value):
    source[0]['normal_integration_conditions']=value
    with pytest.raises(ValueError):c.qualified_reference(0,HASH)


@pytest.mark.parametrize('key,value',[
    ('support_stiffener_credit',True),('lip_or_corner_resistance_credit',True),
    ('walls',{'strong':1,'weak':1}),('method','other'),('status','candidate'),
    ('nodes_sha256','0'*64),('source_sha256',None),('inventory_sha256','not a pin')])
def test_rehashed_shear_proof_cannot_change(source,key,value):
    source[1]['shear_capacity_qualification'][key]=value;seal(source[1])
    with pytest.raises(ValueError):c.qualified_reference(0,HASH)


@pytest.mark.parametrize('value',[0,-1,True,None,float('nan'),float('inf')])
def test_invalid_shear_floor_is_rejected(source,value):
    source[1]['shear_capacity_lower_N']['weak']=value
    if isinstance(value,float) and not __import__('math').isfinite(value):
        with pytest.raises(ValueError):seal(source[1])
        return
    seal(source[1])
    with pytest.raises(ValueError):c.qualified_reference(0,HASH)


@pytest.mark.parametrize('index,sha',[(True,HASH),(-1,HASH),(0.,HASH),('0',HASH),(0,'A'*64),(0,None),(0,'a'*63)])
def test_external_identity_requires_exact_types(source,index,sha):
    with pytest.raises(ValueError):c.qualified_reference(index,sha)
