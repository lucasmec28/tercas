"""Official table value is independent of missing sense/material qualification."""
import copy,json
from io import BytesIO
import pytest
from docx import Document
from tercas.catalogs import entries
from tercas.weak_pierin import reference_for_index,reference_for_inputs
from tercas.weak_catalog import critical_hypothesis
from tercas.weak_axis import capacities
from tercas.application import defaults,calculate
from tercas.batch import calculate_batch
from tercas.catalog_scan import scan_catalog
from tercas.report import word,batch_word
from test_weak_provisional_material import configured
U=next(i for i,e in enumerate(entries()) if e['family']=='U' and e['dimensions_mm']==dict(h=100,bf=50,lip=0,t=2))

def test_inventory_and_exact_missing_geometries():
 refs=[reference_for_index(i) for i in range(209)]
 assert sum(r['status']=='tabulated_adopted_reference' for r in refs)==207
 assert sum(r.get('family')=='U' for r in refs)==124
 assert sum(r.get('family')=='Ue' for r in refs)==83
 assert [entries()[i]['name'] for i,r in enumerate(refs) if r['status']=='not_tabulated']==['U 100 x 75 x 3,00','U 250 x 100 x 6,35']

def test_existing_Ue_values_unchanged_and_U_not_assigned():
 for i,e in enumerate(entries()):
  h=critical_hypothesis(i);r=reference_for_index(i)
  assert h['negative']['Ml_Nmm'] is None and h['positive']['Mdist_Nmm'] is None
  if e['family']=='Ue':
   assert h['positive']['Ml_Nmm']==e['critical_values']['Mly_Nmm']==r['Mly_Nmm']
   assert h['positive']['provisional_hypothesis'] and 'SOMENTE de sentido' in h['positive']['provenance']
  else:
   assert e['critical_values']['Mly_Nmm'] is None # Workbook origin preserved.
   assert h['positive']['Ml_Nmm'] is None and not h['positive']['provisional_hypothesis']

def test_selected_source_and_defensive_copy():
 r=reference_for_index(U)
 assert r['Mly_Nmm']==3260000 and r['table']==1 and r['printed_page']==29 and r['PDF_page']==9
 assert r['source_E_MPa']==200000 and r['source_G_MPa'] is None and r['source_nu'] is None
 assert r['source_sign'] is None and not r['automatically_qualified_for_both_senses']
 r['dimensions_mm']['h']=1;assert reference_for_index(U)['dimensions_mm']['h']==100

@pytest.mark.parametrize('key,value',[('E_MPa',100000),('G_MPa',38500),('h',51),('bf',26),('lip',11),('t',1.25)])
def test_inherited_weak_critical_blocks_incompatible_configuration(key,value):
 d=configured();d['properties'][key]=value;before=copy.deepcopy(d)
 ref=reference_for_inputs(d);assert not ref['original_configuration_unchanged'] and ref['compatibility_reasons']
 c=capacities(d,'Ue')['positive'];assert c['status']=='not_evaluated' and 'MRd_Nmm' not in c
 assert d==before

def test_misassigned_automatic_source_is_blocked():
 d=configured();d['weak_axis']['positive']=critical_hypothesis(1)['positive'];d['weak_axis']['positive']['Mdist_Nmm']=1e6
 c=capacities(d,'Ue')['positive'];assert c['status']=='not_evaluated'
 assert any('seção/linha' in s for s in c['missing'])

def test_source_unknowns_not_removed_by_original_configuration():
 r=reference_for_inputs(defaults(U));assert r['original_configuration_unchanged'] and not r['resistance_release']
 assert r['source_G_MPa'] is None and r['source_nu'] is None and r['sense_qualification']=='not_explicit_in_source'

def test_new_U_reference_does_not_release_resistance_or_biaxial():
 d=defaults(U);d.update(q_uls=.01,q_parallel_uls=.01,weak_catalog={'geometry_mode':'catalog'},weak_axis=critical_hypothesis(U))
 z=calculate(d);r=z['weak_critical_reference'];assert r['Mly_Nmm']==3260000
 assert z['inclination_evidence']['ELU']['biaxial']['status']=='not_evaluated'
 for c in z['inclination_evidence']['ELU']['weak_axis_capacities'].values():assert c['status']=='not_evaluated'
 text='\n'.join(p.text for p in Document(BytesIO(word(z))).paragraphs)
 assert 'referência oficial adotada' in text and '3,26' in text and 'não explicita o lado comprimido' in text
 assert json.loads(json.dumps(z))['weak_critical_reference']==r

def test_official_reference_preserves_strong_G_guard():
 d=configured();d['properties']['G_MPa']=38500;z=calculate(d)
 assert z['strong_critical_qualification']['fields']['Ml']['status']=='not_evaluated_incompatible_elastic_inputs'
 assert z['NBR_branches']['local']['status']=='not_evaluated'
 assert z['inclination_evidence']['ELU']['weak_axis_capacities']['positive']['status']=='not_evaluated'
 assert z['weak_critical_reference']['source_G_MPa'] is None

def test_manual_route_still_explicit_and_not_relabelled_as_table():
 d=configured();d['properties']['G_MPa']=38500
 d['weak_axis']['positive'].update(provisional_hypothesis=False,provenance='SYNTHETIC independently supplied critical, compatible E/G; regression only')
 assert capacities(d,'Ue')['positive']['status']=='computed_restricted'
 assert not reference_for_inputs(d)['original_configuration_unchanged']

def test_batch_and_scan_keep_reference_without_assigning_U():
 d=defaults(U);d.update(load_mode='area',selected_types=['ELU normal'])
 b=calculate_batch(d);assert b['weak_critical_reference']['Mly_Nmm']==3260000
 text='\n'.join(p.text for p in Document(BytesIO(batch_word(b))).paragraphs)
 assert 'referência oficial adotada' in text and 'Novos valores U não são atribuídos' in text
 d=defaults(U);scan=scan_catalog(d,[U]);assert scan['rows'][0]['weak_critical_reference']['Mly_Nmm']==3260000
 assert not scan['whole_member_approved']


def test_provisional_same_row_cannot_be_copied_to_opposite_sense():
 d=configured();d['weak_axis']['negative']=copy.deepcopy(d['weak_axis']['positive'])
 c=capacities(d,'Ue');assert c['positive']['status']=='computed_restricted'
 assert c['negative']['status']=='not_evaluated' and 'MRd_Nmm' not in c['negative']
 assert any('somente para Ue' in s for s in c['negative']['missing'])


def test_provisional_value_mismatch_requires_explicit_manual_replacement():
 d=configured();d['weak_axis']['positive']['Ml_Nmm']*=10
 c=capacities(d,'Ue')['positive'];assert c['status']=='not_evaluated'
 assert any('difere do valor tabelado' in s for s in c['missing'])
