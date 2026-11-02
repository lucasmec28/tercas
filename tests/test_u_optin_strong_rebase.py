"""Integration with the published 9a730eb8 strong Pierin route."""
import copy
import pytest
from tercas.application import calculate
from tercas.weak_axis import strong_capacity
from tercas.weak_u_assumption import FIELD
from tercas.batch import calculate_batch
from tercas.catalog_scan import inputs_for_section
from test_u_pierin_optin import configured,opted,INDICES

@pytest.mark.parametrize('index',INDICES)
def test_weak_optin_never_changes_published_strong_routes(index):
 off=configured(index);on=opted(index);a=calculate(off);b=calculate(on)
 for key in ('NBR_branches','FLT_segments','section_checks','strong_critical_reference','strong_critical_qualification'):
  assert a[key]==b[key],key
 assert strong_capacity(a)==strong_capacity(b)
 assert b['weak_sense_assumption'] and a['weak_sense_assumption'] is None

def test_combined_batch_keeps_both_metadata_and_strong_per_case():
 d=opted();d.update(load_mode='area',selected_types=['ELU normal'],inclination={'value':10.,'unit':'degrees'})
 d['area_inputs']['permanent_kgf_m2']=10.
 r=calculate_batch(d)
 assert r['strong_critical_reference'] and r['weak_sense_assumption']
 assert all(c['evidence']['strong_critical_qualification'] for c in r['cases'])
 off=copy.deepcopy(d);off['weak_axis']=configured()['weak_axis'];rb=calculate_batch(off)
 assert rb['strong_critical_reference']==r['strong_critical_reference']
 for a,b in zip(rb['cases'],r['cases']):
  assert a['evidence']['strong_critical_qualification']==b['evidence']['strong_critical_qualification']

def test_scan_drops_weak_choice_without_losing_strong_adoption():
 a=opted();b=configured()
 for i in INDICES:
  aa=inputs_for_section(a,i);bb=inputs_for_section(b,i)
  assert FIELD not in aa['weak_axis']['positive'] and aa['weak_axis']['positive']['Ml_Nmm'] is None
  for key in ('Ml_Nmm','Mdist_Nmm','critical_origin','strong_pierin'):assert aa.get(key)==bb.get(key)
  assert calculate(aa)['strong_critical_reference']==calculate(bb)['strong_critical_reference']

@pytest.mark.parametrize('property_name', ['E_MPa','G_MPa'])
def test_explicit_manual_weak_recovery_does_not_release_new_strong_guard(property_name):
 d=opted();d['properties'][property_name]/=2
 w=d['weak_axis']['positive'];w.pop(FIELD);w['provisional_hypothesis']=False
 w['provenance']='SYNTHETIC manual weak critical for changed material; regression only'
 r=calculate(d)
 assert r['inclination_evidence']['ELU']['weak_axis_capacities']['positive']['MRd_Nmm']>0
 assert r['NBR_branches']['local']['status']=='not_evaluated'
 assert strong_capacity(r) is None
