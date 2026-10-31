import unittest,json
from io import BytesIO
from docx import Document
from tercas.application import example
from tercas.batch import calculate_batch,area_bundle
from tercas.report import batch_word
class MobileIntegration(unittest.TestCase):
 def data(self):
  d=example();d.update(load_mode='area',patch_mm=None,patch_origin='',selected_types=['ELU normal','ELS rara']);return d
 def test_isolation_selection_and_contact(self):
  d=self.data();d['area_inputs']['live_kgf_m2']=999;d['area_inputs']['wind_up_kgf_m2']=999
  b=area_bundle(d);p=[c for c in b['combinations'] if c['P_N']];self.assertEqual(len(p),10)
  for c in p:self.assertEqual(set(c['coefficients']),{'PP','CP','P'})
  d['selected_types']=['ELS frequente'];self.assertFalse(any(c['P_N'] for c in area_bundle(d)['combinations']))
 def test_prescribed_cases_and_json(self):
  r=calculate_batch(self.data());p=[c for c in r['cases'] if c['combination']['P_N']];self.assertEqual(len(p),10)
  for c in p:
   self.assertIn(c['combination']['point_position'],('center','support_limit'))
   self.assertIn('prescribed_point',c['evidence'])
   self.assertFalse(any(x['Verificação']=='Carga concentrada' for x in c['rows']))
  json.dumps(r,allow_nan=False)
  text='\n'.join(x.text for x in Document(BytesIO(batch_word(r))).paragraphs)
  self.assertIn('P normal=1,50 kN',text);self.assertIn('P normal=1,00 kN',text)
