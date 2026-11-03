"""Opt-in is not authorization by a token; all physical data remain frozen."""
import copy
import hashlib
import math
import json
from io import BytesIO
import pytest
from docx import Document
from tercas.application import defaults
from tercas.homogeneous_reference import (FIELD, ROOT, REFERENCES, source, assess,
    activate, load_reference, calculate_reference)

@pytest.mark.parametrize('ref', REFERENCES)
@pytest.mark.parametrize('angle', (0, 5, -5))
def test_registered_complete_inputs_require_opt_in_and_roundtrip(ref, angle):
    data = source(ref, angle);before = copy.deepcopy(data)
    state=assess(data)
    assert state['eligible'] and not state['active'] and state['reference_id']==ref and not state['reasons']
    with pytest.raises(ValueError):calculate_reference(data)
    active = activate(data)
    assert data == before
    assert {k:v for k,v in active.items() if k != FIELD} == before
    assert assess(json.loads(json.dumps(active)))['active']
    active.pop('model_domain', None)
    assert assess(active)['active']


def physical_mutations():
    yield 'wrong profile', lambda d: d.update(catalog_index=0)
    for k in source('U100')['properties']:
        yield 'property '+k, lambda d,k=k: d['properties'].__setitem__(k,math.nextafter(d['properties'][k], math.inf))
    for k in ('L_mm','Ml_Nmm'):
        yield k, lambda d,k=k: d.__setitem__(k,d[k]+1)
    for side in ('positive','negative'):
        for k,v in source('U100')['weak_axis'][side].items():
            yield 'weak '+side+' '+k, lambda d,side=side,k=k,v=v: d['weak_axis'][side].__setitem__(k,(not v if isinstance(v,bool) else v+1 if isinstance(v,(int,float)) else 'changed'))
    for k in source('U100')['segments'][0]:
        yield 'segment '+k, lambda d,k=k: d['segments'][0].__setitem__(k,'changed')
    for k in ('property_origin','critical_origin','support_origin','patch_origin','steel_name','route_domain','synthetic','left_web','right_web','ELS_limit_mm','ELS_origin','patch_mm'):
        yield k, lambda d,k=k: d.__setitem__(k,'changed')
    for k,v in [('weak_catalog',{}),('three_girt_model',{'enabled':False}),('N_N',0),('torque_Nmm',0),('u_panel_condition',{'condition':'no_flange_panel'}),('member_application','wall_girt'),('model_domain','fake'),('new_physical_field',123)]:
        yield k, lambda d,k=k,v=v: d.__setitem__(k,v)
    yield 'missing weak', lambda d:d.pop('weak_axis')
    yield 'missing strong', lambda d:d.pop('Ml_Nmm')
    yield 'missing property', lambda d:d['properties'].pop('Cw_mm6')
    yield 'extra area torque', lambda d:d['area_inputs'].update(torque=10)
    yield 'extra inclination', lambda d:d['inclination'].update(rotation=90)
    yield 'different basis', lambda d:d['inclination'].update(spacing_basis='horizontal')

MUTATIONS=list(physical_mutations())
@pytest.mark.parametrize('label,mutate', MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_every_physical_mutation_is_rejected_without_repair(label, mutate):
    data=load_reference('U100');mutate(data);before=copy.deepcopy(data)
    state=assess(data)
    assert not state['active'] and not state['eligible'], (label,state)
    with pytest.raises(ValueError):calculate_reference(data)
    assert data==before

@pytest.mark.parametrize('ref',REFERENCES)
def test_identifier_alone_never_authorizes(ref):
    token=load_reference(ref)[FIELD]
    for data in (defaults(), {'homogeneous_reference':token}, source('U100')):
        data[FIELD]=token
        if ref=='U100' and data.get('properties')==source('U100')['properties']:continue
        assert not assess(data)['active']


def test_mutable_actions_and_identification_preserve_physical_vector():
    data=load_reference('U125')
    data.update(project='Teste de sinais',actions_origin='Ações sintéticas editadas',load_mode='direct',
                q_uls=-.4,P_uls=100.,x_uls=1200.,q_sls=.2,P_sls=-50.,x_sls=700.,
                q_parallel_uls=-.1,P_parallel_uls=40.,q_parallel_sls=.2,P_parallel_sls=-10.)
    data['inclination']['value']=-5.
    assert assess(data)['active']
    result=calculate_reference(data)
    assert result['input_data']==data
    assert result['inclination_evidence']['ELU']['q_vector']['parallel']==-.1
    assert result['inclination_evidence']['ELU']['P_vector']['normal']==100.
    assert result['homogeneous_reference_evidence']['reference_id']=='U125'
    assert result['whole_member_approved'] is False
    from tercas.report import word
    text='\n'.join(p.text for p in Document(BytesIO(word(result))).paragraphs)
    assert 'Referência própria homogênea' in text and 'CBCA 2014' in text and 'SHA-256' in text
    assert 'ri=t=2' in text and 'empenamento livres' in text
    assert 'outputs/' not in text and 'main7d8' not in text


def test_source_files_keep_verified_hashes():
    manifest=json.loads((ROOT/'sources.json').read_text())
    for ref,item in manifest.items():
        assert hashlib.sha256((ROOT/item['reference_vector']).read_bytes()).hexdigest()==item['reference_vector_sha256']
        for f in item['inputs'].values():assert hashlib.sha256((ROOT/f['file']).read_bytes()).hexdigest()==f['sha256']


def test_profile_adapter_never_transfers_reference_marker():
    from tercas.catalog_scan import inputs_for_section
    data=load_reference('U150')
    for index in (0,data['catalog_index']):
        new=inputs_for_section(data,index)
        assert FIELD not in new and 'homogeneous_reference_evidence' not in new
        assert not assess(new)['eligible']


def test_catalog_scan_rejects_reference_and_section_adapter_separates_origins():
    from tercas.catalog_scan import inputs_for_section, scan_catalog
    data=load_reference('U125')
    with pytest.raises(ValueError,match='Referência própria'):scan_catalog(data,indices=[0])
    new=inputs_for_section(data,source('U150')['catalog_index'])
    assert 'Contorno nominal CBCA de U125' not in new['property_origin']
    assert 'não são qualificação' in new['property_origin']
    assert new['properties']['G_MPa']==data['properties']['G_MPa']

@pytest.mark.parametrize('key', ('project','actions_origin','load_mode','q_uls','selected_types'))
def test_missing_editable_fields_are_inspection_not_editable(key):
    data=load_reference('U100');data.pop(key)
    assert not assess(data)['active']


def test_recoverable_invalid_actions_keep_physical_identity_but_block_calculation():
    data=load_reference('U100');data['selected_types']=[]
    state=assess(data)
    assert state['eligible'] and state['active'] and not state['calculable']
    with pytest.raises(ValueError):calculate_reference(data)
    data['load_mode']='direct'
    assert assess(data)['calculable']
    data['x_uls']=-1.
    assert assess(data)['active'] and not assess(data)['calculable']
