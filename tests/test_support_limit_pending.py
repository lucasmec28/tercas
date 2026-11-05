"""Demand/evidence must survive missing web resistance at the support limit."""
import copy,json,unittest
from io import BytesIO
from docx import Document
from tercas.application import example,calculate
from tercas.batch import calculate_batch,case_inputs
from tercas.report import batch_word
from tercas.presentation import fmt

class SupportLimitPending(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=example();cls.data.update(load_mode='area',selected_types=['ELU normal'],inclination={'value':5.})
  cls.data['area_inputs']['permanent_kgf_m2']=8.
  cls.data['properties']['ri_mm']=None
  cls.before=copy.deepcopy(cls.data);cls.result=calculate_batch(cls.data)
  cls.limits=[c for c in cls.result['cases'] if c['combination'].get('point_position')=='support_limit']
 def test_four_limits_and_input_unchanged(self):
  self.assertEqual(len(self.limits),4);self.assertEqual(self.data,self.before)
 def test_demand_includes_P_without_VRd(self):
  for case in self.limits:
   with self.subTest(case=case['combination']['id']):
    c=case['combination'];row=next(r for r in case['rows'] if r['Verificação']=='Cortante')
    expected=abs(c['q_N_mm']*self.data['L_mm']/2+c['P_N'])
    self.assertEqual(row['Demanda / valor'],f'{expected/1000:.6f} kN')
    self.assertIsNone(row['Índice']);self.assertEqual(row['Situação'],'Não avaliado')
    self.assertAlmostEqual(case['evidence']['prescribed_point']['V_support_limit_N'],expected)
    self.assertAlmostEqual(case['evidence']['inclination']['states'][0]['normal']['V_N'],expected)
 def test_local_transfer_not_claimed_absent(self):
  for case in self.limits:
   with self.subTest(case=case['combination']['id']):
    p=case['evidence']['NBR_branches']['point']
    self.assertEqual(p['status'],'not_applicable');self.assertEqual(p['position'],'support_limit')
    self.assertEqual(p['scope'],'mathematical_limit');self.assertFalse(p['physical_contact_checked'])
    self.assertEqual(p['force_N'],case['combination']['P_N'])
    self.assertNotIn('Sem força',p['reason']);self.assertIn('transferência local permanece',p['reason'])
    self.assertNotIn('FRd_N',p);self.assertNotIn('index',p)
 def test_interior_bending_is_still_q_only(self):
  for case in self.limits:
   c=case['combination'];d=case_inputs(self.data,c);self.assertEqual(d['P_uls'],0.)
   direct=calculate(d)
   self.assertEqual(case['evidence']['NBR_branches']['local'],direct['NBR_branches']['local'])
   self.assertEqual(case['evidence']['FLT_segments'],direct['FLT_segments'])
 def test_center_and_zero_point_states_unchanged(self):
  for case in self.result['cases']:
   c=case['combination']
   if c.get('point_position')=='support_limit':continue
   direct=calculate(case_inputs(self.data,c))
   self.assertEqual(case['evidence']['NBR_branches']['point'],direct['NBR_branches']['point'])
 def test_JSON_retains_scope_and_no_approval(self):
  output=json.loads(json.dumps(self.result,allow_nan=False))
  self.assertFalse(output['whole_member_approved'])
  for case in output['cases']:
   if case['combination'].get('point_position')=='support_limit':self.assertEqual(case['evidence']['NBR_branches']['point']['status'],'not_applicable')
 def test_report_demand_and_requested_exclusions(self):
  doc=Document(BytesIO(batch_word(self.result)))
  txt='\n'.join(p.text for p in doc.paragraphs)
  for case in self.limits:
   v=case['evidence']['prescribed_point']['V_support_limit_N']/1000
   self.assertIn(fmt(v),txt)
  for excluded in ('Shear lag','Anexo D','Carga concentrada','Cortante paralelo','comprimento de contato'):
   self.assertNotIn(excluded,txt)

if __name__=='__main__':unittest.main()
