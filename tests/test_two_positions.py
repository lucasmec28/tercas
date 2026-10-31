import unittest, json
from io import BytesIO
from docx import Document
from tercas.application import example,calculate,rows
from tercas.batch import area_bundle,calculate_batch,case_inputs
from tercas.report import word,batch_word
class TwoPositions(unittest.TestCase):
 def data(self):
  d=example();d.update(load_mode='area',selected_types=['ELU normal','ELS rara']);return d
 def test_exactly_two_no_sweep(self):
  b=area_bundle(self.data());ps=[c for c in b['combinations'] if c['P_N']]
  self.assertEqual(len(ps),10)
  self.assertEqual(set(c['point_position'] for c in ps),{'center','support_limit'})
  self.assertFalse(any('global_envelope' in c for c in ps))
 def test_support_limit_not_exact_support_load(self):
  d=self.data();r=calculate_batch(d)
  for case in r['cases']:
   c=case['combination']
   if c.get('point_position')!='support_limit' or c['limit_state']!='ELU':continue
   raw=calculate(case_inputs(d,c));self.assertEqual(raw['input_data']['P_uls'],0.)
   rr={x['Verificação']:x for x in case['rows']};vr=raw['section_checks']['shear']['VRd_N']
   self.assertAlmostEqual(rr['Cortante']['Índice'],(c['q_N_mm']*d['L_mm']/2+c['P_N'])/vr)
   base=next(x['Índice'] for x in rows(raw) if x['Verificação']=='Flexão e cortante concomitantes')
   self.assertAlmostEqual(rr['Flexão e cortante concomitantes']['Índice'],max(base,rr['Cortante']['Índice']**2))
   self.assertIn('não certificam',case['scope_notes'][-1])
  self.assertFalse(r['whole_member_approved']);json.dumps(r,allow_nan=False)
 def test_center_keeps_fixed_position_results(self):
  d=self.data();r=calculate_batch(d)
  for case in r['cases']:
   c=case['combination']
   if c.get('point_position')!='center':continue
   raw=calculate(case_inputs(d,c));expected={x['Verificação']:x['Índice'] for x in rows(raw)}
   for row in case['rows']:self.assertEqual(row['Índice'],expected[row['Verificação']])
 def test_excluded_checks_absent_output(self):
  d=self.data();d['inclination']={'value':20};r=calculate_batch(d)
  txt='\n'.join(p.text for p in Document(BytesIO(batch_word(r))).paragraphs)
  txt+='\n'+json.dumps([c['rows'] for c in r['cases']],ensure_ascii=False)
  direct=calculate(d|{'load_mode':'direct'});txt+='\n'+'\n'.join(p.text for p in Document(BytesIO(word(direct))).paragraphs)
  for x in ('Shear lag','Anexo D','Carga concentrada','Cortante paralelo','comprimento de contato'):self.assertNotIn(x,txt)
 def test_support_center_els(self):
  d=self.data();d['selected_types']=['ELS rara'];r=calculate_batch(d);ps=[c for c in r['cases'] if c['combination']['P_N']]
  self.assertEqual(len(ps),2)
  vals={c['combination']['point_position']:c['evidence']['ELS']['deflection_mm'] for c in ps}
  self.assertGreater(vals['center'],vals['support_limit'])

 def test_limit_evidence_and_drawing(self):
  from tercas.drawing_cases import drawing_cases
  from tercas.drawing import svg
  d=self.data();d['selected_types']=['ELU normal'];r=calculate_batch(d)
  for case in r['cases']:
   c=case['combination']
   if c.get('point_position')!='support_limit':continue
   L=d['L_mm'];q=c['q_N_mm'];P=c['P_N'];ev=case['evidence']['inclination']
   self.assertAlmostEqual(c['effects_at_midspan']['M_Nmm'],q*L**2/8)
   self.assertEqual(ev['P_vector'],c['P_vector'])
   boundary=ev['states'][0]
   self.assertAlmostEqual(boundary['normal']['V_N'],q*L/2+P)
   self.assertEqual(boundary['normal']['M_Nmm'],0.)
   for state in ev['states']:self.assertAlmostEqual(state['normal']['Rleft_N'],q*L/2+P)
  preview=next(x for label,x in drawing_cases(d) if x.get('point_position')=='support_limit')
  self.assertIn('x → 0+',svg(preview))
  txt='\n'.join(p.text for p in Document(BytesIO(batch_word(r))).paragraphs)
  self.assertIn('seção antes de P',txt);self.assertIn('interior após P',txt)
