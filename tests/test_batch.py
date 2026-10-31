import unittest,copy,json
from io import BytesIO
from docx import Document
from tercas.application import defaults,example,calculate,rows
from tercas.batch import calculate_batch,case_inputs,area_bundle
from tercas.catalogs import catalog_labels
from tercas.load_combinations import COMBINATION_TYPES
from tercas.report import batch_word
class BatchTests(unittest.TestCase):
 def data(self):
  d=example();d.update(load_mode='area',selected_types=list(COMBINATION_TYPES));d['area_inputs'].update(spacing_m=1.5,permanent_kgf_m2=10.,live_kgf_m2=25.,wind_up_kgf_m2=100.,wind_down_kgf_m2=50.);return d
 def test_full_matrix_and_signs(self):
  d=self.data();r=calculate_batch(d);self.assertEqual(len(r['cases']),53);self.assertFalse(r['whole_member_approved']);self.assertTrue(any(c['combination']['q_N_mm']<0 for c in r['cases']))
  for item in r['cases']:
   c=item['combination']
   if c.get('P_N'):continue
   direct=calculate(case_inputs(d,c));rr=rows(direct);expected=[x for x in rr if (x['Verificação']=='Flecha — flexão')==(c['limit_state']=='ELS')];self.assertEqual(item['rows'],expected)
 def test_only_els_no_elu(self):
  d=self.data();d['selected_types']=['ELS rara'];r=calculate_batch(d);self.assertEqual(len(r['cases']),9);self.assertEqual(len(r['summary']),1);self.assertTrue(all('ELS' in c['evidence'] for c in r['cases']))
 def test_only_elu_no_els(self):
  d=self.data();d['selected_types']=['ELU normal'];r=calculate_batch(d);self.assertEqual(len(r['cases']),36);self.assertTrue(all(c['combination']['limit_state']=='ELU' for c in r['cases']));self.assertFalse(any(x['Verificação'].startswith('Flecha') for x in r['summary']))
 def test_els_limits_sign(self):
  d=self.data();r=calculate_batch(d)
  for c in r['cases']:
   if c['combination']['limit_state']=='ELS':self.assertEqual(c['evidence']['ELS']['limit_mm'],d['L_mm']/(180 if c['combination']['q_N_mm']>=0 else 120))
 def test_no_selection_invalid(self):
  d=self.data();d['selected_types']=[]
  with self.assertRaises(ValueError):calculate_batch(d)
 def test_invalid_area_and_mass(self):
  for key,value in [('spacing_m',0.),('permanent_kgf_m2',-1.),('wind_up_kgf_m2',float('nan'))]:
   d=self.data();d['area_inputs'][key]=value
   with self.assertRaises(ValueError):calculate_batch(d)
 def test_word_and_json(self):
  d=self.data();d['selected_types']=['ELS quase permanente'];r=calculate_batch(d);doc=Document(BytesIO(batch_word(r)));txt='\n'.join(p.text for p in doc.paragraphs);self.assertIn('NÃO É APROVAÇÃO GLOBAL',txt);self.assertIn('ELS quase permanente',txt);json.dumps(r,allow_nan=False)
 def test_default_u_fallback(self):
  labels=catalog_labels();idx=next(i for i,x in enumerate(labels) if x.startswith('U ') );d=defaults(idx);self.assertGreater(d['Ml_Nmm'],0);self.assertIn('Tabela 12',d['critical_origin'])
 def test_partial_missing_lz_visible(self):
  d=self.data();d['segments'][0]['Lz_effective_mm']=None;r=calculate_batch(d);flt=next(x for x in r['summary'] if x['Verificação'].startswith('FLT'));self.assertGreater(flt['Casos pendentes'],0);self.assertIn('Parcial',flt['Situação'])

 def test_short_span_ignores_inactive_point_coordinates(self):
  d=self.data();d['L_mm']=1000.;d['segments'][0]['end_mm']=1000.;d['selected_types']=['ELS quase permanente'];r=calculate_batch(d);self.assertEqual(len(r['cases']),2)

 def test_import_structure_rejects_invalid_hidden_fields(self):
  from tercas.application import build_spec
  for key,value in [('steel_name','bad'),('load_mode','bad'),('selected_types',['bad']),('area_inputs',{}),('ELS_down_denominator',None)]:
   d=self.data();d['load_mode']='direct';d[key]=value
   with self.assertRaises(ValueError,msg=key):build_spec(d)

 def test_invalid_custom_steel_rejected(self):
  d=self.data();d['steel_name']='Personalizado';d['properties'].update(fy_MPa=500.,fu_MPa=400.)
  with self.assertRaisesRegex(ValueError,'fu não pode'):calculate_batch(d)
  d['load_mode']='direct'
  with self.assertRaisesRegex(ValueError,'fu não pode'):calculate(d)
