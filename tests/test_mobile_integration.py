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
  b=area_bundle(d);p=[c for c in b['combinations'] if c['P_N']];self.assertEqual(len(p),5)
  for c in p:self.assertEqual(set(c['coefficients']),{'PP','CP','P'})
  d['selected_types']=['ELS frequente'];self.assertFalse(any(c['P_N'] for c in area_bundle(d)['combinations']))
 def test_global_and_partial(self):
  r=calculate_batch(self.data());p=[c for c in r['cases'] if c['combination']['P_N']];self.assertEqual(len(p),5)
  for c in p:
   rows={x['Verificação']:x for x in c['rows']}
   if c['combination']['limit_state']=='ELU':
    self.assertIsNotNone(rows['Cortante']['Índice']);self.assertIsNotNone(rows['Flexão e cortante concomitantes']['Índice'])
    flt=rows['FLT — trecho 1'];self.assertTrue(flt['Índice'] is None or (flt['Índice']>1 and 'Não atende' in flt['Situação']));self.assertIsNone(rows['Carga concentrada']['Índice'])
    self.assertAlmostEqual(c['evidence']['mobile_point']['global_envelope']['V_abs_N'],c['combination']['q_N_mm']*1500+1500)
   else:self.assertIn('limite superior conservador',rows['Flecha — flexão']['Situação']);self.assertLessEqual(rows['Flecha — flexão']['Índice'],1)
  json.dumps(r,allow_nan=False)
  text='\n'.join(x.text for x in Document(BytesIO(batch_word(r))).paragraphs)
  self.assertIn('P normal=1,50 kN',text);self.assertIn('P normal=1,00 kN',text)
 def test_known_central_failure_not_hidden(self):
  from tercas.batch import mobile_rows
  d=self.data();d['selected_types']=['ELS rara'];r=calculate_batch(d);case=r['cases'][-1]
  from tercas.application import calculate
  from tercas.batch import case_inputs
  raw=calculate(case_inputs(d,case['combination']))
  row={'Verificação':'Flecha — flexão','Índice':1.2,'Demanda / valor':'x','Observação':''}
  mobile_rows([row],raw,case['combination']);self.assertEqual(row['Índice'],1.2);self.assertIn('Não atende',row['Situação'])
