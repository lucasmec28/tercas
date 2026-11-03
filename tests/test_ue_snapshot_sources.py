"""Own section sources apply even when values happen to equal the catalogue."""
import copy
from io import BytesIO
import pytest
from docx import Document
from tercas import ue_reference as u
from tercas.application import defaults,_calculate
from tercas.batch import _calculate_batch
from tercas.report import word,batch_word


def numeric_tree(value,path=''):
    if isinstance(value,dict):
        out={}
        for k,v in value.items():out.update(numeric_tree(v,path+'.'+k))
        return out
    if isinstance(value,list):
        out={}
        for i,v in enumerate(value):out.update(numeric_tree(v,path+'['+str(i)+']'))
        return out
    return {path:value} if isinstance(value,(int,float)) and not isinstance(value,bool) else {}

@pytest.mark.parametrize('area',[False,True])
def test_every_consumed_section_field_has_own_origin_without_numeric_or_input_changes(area):
    d=u.load_reference()
    if not area:d.update(load_mode='direct',q_sls=.1,q_uls=.2)
    original=copy.deepcopy(d)
    raw=_calculate_batch(d,_calculate_case=_calculate) if area else _calculate(d)
    before=copy.deepcopy(raw);numbers=numeric_tree(raw)
    record=u.evidence(d);u._own_snapshot_origins(raw,record)
    assert numeric_tree(raw)==numbers and d==original
    assert raw['input_data']==before['input_data']
    key='common_input_snapshot' if area else 'input_snapshot'
    section=raw[key]['selected_section'];prior=before[key]['selected_section']
    assert section['entry_id']==u.ID
    assert section['nominal_documentary_catalog']['entry_id']==prior['entry_id']
    assert section['source'].startswith('Referência própria R01')
    assert section['nominal_documentary_catalog']['source_url']==prior['source']
    assert 'somente' in section['nominal_documentary_catalog']['scope']
    assert section['history']==prior['history'] and 'somente documental' in section['history_scope']
    for field,item in section['fields'].items():
        assert item['value']==d['properties'][field]
        assert item['origin'].startswith('Referência própria R01')
        assert record['source_documents']['manifest_sha256'] in item['origin']
        assert 'calculistadeaco' not in item['origin']
    catalogue=defaults(d['catalog_index'])['properties']
    for name in ('h','bf','lip','t','ri_mm','E_MPa','fy_MPa','fu_MPa'):
        assert d['properties'][name]==catalogue[name]
        assert section['fields'][name]['origin'].startswith('Referência própria R01')
    blocks=[c['evidence']['section_checks'] for c in raw['cases'] if 'section_checks' in c['evidence']] if area else [raw['section_checks']]
    assert blocks
    for block in blocks:
        assert block['entry_id']==u.ID and block['nominal_documentary_entry_id']=='planilha_v03_r24'
        assert all(v['origin'].startswith('Referência própria R01') for v in block['input_fields'].values())
    frozen=copy.deepcopy(raw);u._own_snapshot_origins(raw,record)
    assert raw==frozen

@pytest.mark.parametrize('area',[False,True])
def test_new_reference_word_never_calls_catalogue_source_of_consumed_fields(area):
    d=u.load_reference()
    if not area:d.update(load_mode='direct',q_sls=.1,q_uls=.2)
    result=u.calculate_reference(d)
    doc=Document(BytesIO(batch_word(result) if area else word(result)))
    text='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert 'Referência própria R01 Ue100, 209 nós' in text
    assert 'geometria declarada ri=1,20 mm' in text
    assert 'calculistadeaco.com' not in text
    assert result['ue_reference_evidence']['source_documents']['manifest_sha256'] in text
    if area:assert 'Correspondência nominal documental' in text
    assert result['input_data']==d
