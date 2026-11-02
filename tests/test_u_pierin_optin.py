"""Explicit exploratory inference must not silently become catalogue authority."""
import copy,json
from io import BytesIO
import pytest
from docx import Document
from tercas.application import defaults,calculate,rows,build_spec
from tercas.catalogs import entries
from tercas.weak_catalog import critical_hypothesis
from tercas.weak_axis import capacities,provisional_hypothesis
from tercas.weak_u_assumption import FIELD,COVERED,covered,input_row,evidence
from tercas.catalog_scan import inputs_for_section,scan_catalog,summarize
from tercas.batch import calculate_batch,case_inputs
from tercas.report import word,batch_word

INDICES=[i for i in range(len(entries())) if covered(i)]

def configured(index=None):
 i=INDICES[0] if index is None else index
 d=defaults(i);d.update(weak_catalog={'geometry_mode':'catalog'},weak_axis=critical_hypothesis(i),q_uls=.01,q_parallel_uls=.01,route_domain=True)
 d['segments'][0].update(Ly_effective_mm=3000.,Lz_effective_mm=3000.,restraint_provenance='SYNTHETIC opt-in regression')
 return d

def opted(index=None):
 d=configured(index);d['weak_axis']['positive']=input_row(d['catalog_index']);return d

def texts(blob):
 doc=Document(BytesIO(blob));return '\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for r in t.rows for c in r.cells)

def test_default_no_U_assignment_anywhere():
 for i,e in enumerate(entries()):
  assert FIELD not in defaults(i).get('weak_axis',{}).get('positive',{})
  if e['family']=='U':assert critical_hypothesis(i)['positive']['Ml_Nmm'] is None
 assert len(INDICES)==len(COVERED)==4

@pytest.mark.parametrize('index',INDICES)
def test_explicit_only_positive_conditional_without_approval(index):
 d=configured(index);assert capacities(d,'U')['positive']['status']=='not_evaluated'
 d['weak_axis']['positive']=input_row(index);before=copy.deepcopy(d);r=calculate(d);assert d==before
 ev=r['inclination_evidence']['ELU'];cap=ev['weak_axis_capacities']['positive']
 assert cap['MRd_Nmm']>0 and not cap['design_approved'] and not cap['source_sign_declared']
 assert ev['weak_axis_capacities']['negative']['status']=='not_evaluated'
 biax=next(x for x in rows(r) if x['Verificação']=='Flexão biaxial')
 assert 'Exploratório' in biax['Situação'] and 'pendente de confirmação' in biax['Situação'] and 'Atende' not in biax['Situação']
 assert not summarize(rows(r))['criteria_satisfied'] and not r['whole_member_approved']
 assert r['weak_critical_reference']['source_sign'] is None

@pytest.mark.parametrize('prop,value',[('E_MPa',100000.),('G_MPa',38500.),('Iy_cm4',1.),('A_cm2',1.),('J_mm4',1.),('ri_mm',99.),('h',51.)])
def test_changed_material_or_section_properties_block(prop,value):
 d=opted();d['properties'][prop]=value;c=capacities(d,'U')['positive']
 assert c['status']=='not_evaluated' and 'MRd_Nmm' not in c

@pytest.mark.parametrize('key,value',[('version','stale'),('catalog_id','other'),('reference_id','other'),('source_pdf_sha256','other'),('compression_side','free_edges'),('acknowledged_as_inference',False)])
def test_wrong_or_unacknowledged_token_blocks(key,value):
 d=opted();d['weak_axis']['positive'][FIELD][key]=value
 assert capacities(d,'U')['positive']['status']=='not_evaluated'

@pytest.mark.parametrize('token',[None,True,{}, {'acknowledged_as_inference':True}])
def test_malformed_token_rejected_on_import(token):
 d=opted();d['weak_axis']['positive'][FIELD]=token
 with pytest.raises(ValueError,match='Hipótese U/alma'):build_spec(d)

def test_acknowledgement_is_not_truthiness():
 d=opted();d['weak_axis']['positive'][FIELD]['acknowledged_as_inference']=1
 with pytest.raises(ValueError,match='booleano'):build_spec(d)

def test_token_survives_removed_boolean_and_marker_alone_is_not_consent():
 d=opted();s=d['weak_axis']['positive'];s['provisional_hypothesis']=False
 assert provisional_hypothesis(s) and capacities(d,'U')['positive']['conditional_assumption']
 s.pop(FIELD);assert provisional_hypothesis(s)
 assert capacities(d,'U')['positive']['status']=='not_evaluated'

@pytest.mark.parametrize('key,value',[('Ml_Nmm',9999999.),('Mdist_Nmm',1e6),('plain_u_no_distortion',False),('provenance','Other source')])
def test_value_or_origin_tampering_never_silently_recovers_manual(key,value):
 d=opted();d['weak_axis']['positive'][key]=value
 assert capacities(d,'U')['positive']['status']=='not_evaluated'

def test_opposite_sense_other_section_and_missing_catalog_route_block():
 d=opted();d['weak_axis']['negative']=copy.deepcopy(d['weak_axis']['positive'])
 assert capacities(d,'U')['negative']['status']=='not_evaluated'
 other=configured(INDICES[-1]);other['weak_axis']['positive']=copy.deepcopy(d['weak_axis']['positive'])
 assert capacities(other,'U')['positive']['status']=='not_evaluated'
 d=opted();d.pop('weak_catalog');assert capacities(d,'U')['positive']['status']=='not_evaluated'

def test_four_is_evidence_coverage_not_thickness_rule():
 for i,e in enumerate(entries()):
  if e['family']=='U' and not covered(i):
   with pytest.raises(ValueError,match='lista explícita'):input_row(i)

def test_negative_demand_remains_pending_not_abs_M_reused():
 d=opted();d['q_parallel_uls']=-.01;r=calculate(d);ev=r['inclination_evidence']['ELU']
 assert ev['biaxial']['status']=='not_evaluated' and 'negative' in ev['biaxial']['missing']

def test_result_greater_than_one_stays_exploratory():
 d=opted();d['q_parallel_uls']=100;r=calculate(d)
 b=next(x for x in rows(r) if x['Verificação']=='Flexão biaxial')
 assert b['Índice']>1 and 'índice calculado maior que 1' in b['Situação']
 assert 'Atende' not in b['Situação']

def test_json_and_word_preserve_selection_and_pending_source():
 d=opted();reloaded=json.loads(json.dumps(d));r=calculate(reloaded)
 assert r['input_data']==d and r['weak_sense_assumption']['source_sign'] is None
 text=texts(word(r));assert 'hipótese de sentido inferida, pendente de confirmação' in text
 assert 'acknowledged_as_inference' in text and 'não é declaração de sentido de Pierin' in text
 assert json.loads(json.dumps(r))['weak_sense_assumption']==r['weak_sense_assumption']

def test_no_parallel_demand_still_exports_warning_and_choice():
 d=opted();d['q_parallel_uls']=0;r=calculate(d)
 assert r['weak_sense_assumption'] and any('Exploratório' in w for w in r['critical_warnings'])

def test_scan_drops_optin_even_for_original_section():
 d=opted()
 for i in [d['catalog_index'],INDICES[-1]]:
  fresh=inputs_for_section(d,i);assert evidence(fresh) is None and fresh['weak_axis']['positive']['Ml_Nmm'] is None
 scan=scan_catalog(d,indices=[d['catalog_index']]);assert not scan['rows'][0]['criteria_satisfied']
 assert any('Flexão biaxial' in p for p in scan['rows'][0]['pending'])

def test_same_section_batch_preserves_conditional_choice_and_summary():
 d=opted();d.update(load_mode='area',selected_types=['ELU normal'],inclination={'value':10.,'unit':'degrees'})
 d['area_inputs']['permanent_kgf_m2']=10.
 r=calculate_batch(d);assert r['weak_sense_assumption'] and not r['whole_member_approved']
 bx=next(x for x in r['summary'] if x['Verificação']=='Flexão biaxial')
 assert bx['Casos pendentes'] and 'hipótese inferida' in bx['Situação'] and 'Atende' not in bx['Situação']
 assert 'hipótese de sentido inferida, pendente de confirmação' in texts(batch_word(r))
 dd=case_inputs(d,dict(id='negative',type='ELU normal',expression='SYNTHETIC',limit_state='ELU',q_N_mm=.01,q_vector={'parallel':-.01}))
 assert FIELD in dd['weak_axis']['positive']
 assert 'negative' in calculate(dd)['inclination_evidence']['ELU']['biaxial']['missing']

def test_weak_option_does_not_release_strong_elastic_guard():
 d=opted();d['properties']['E_MPa']=100000.;r=calculate(d)
 assert r['NBR_branches']['local']['status']=='not_evaluated'
 assert r['inclination_evidence']['ELU']['weak_axis_capacities']['positive']['status']=='not_evaluated'
