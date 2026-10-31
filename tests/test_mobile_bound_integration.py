import unittest,copy
from tercas.application import example,calculate
from tercas.batch import calculate_batch,case_inputs
from tercas.mobile_deflection_adapter import apply_bound
class BoundIntegration(unittest.TestCase):
 def fixture(self):
  d=example();d.update(load_mode='area',selected_types=['ELS rara']);r=calculate_batch(d);case=r['cases'][-1];raw=calculate(case_inputs(d,case['combination']));return d,case,raw
 def row(self):return {'Verificação':'Flecha — flexão','Índice':None,'Observação':''}
 def test_success_is_bound_not_actual(self):
  _,case,raw=self.fixture();row=self.row();b=apply_bound(row,raw,case['combination'])
  self.assertLessEqual(row['Índice'],1);self.assertIn('limite superior',row['Situação']);self.assertFalse(b['actual_mobile_maximum_computed']);self.assertIn('não é flecha exata',row['Observação'])
 def test_inconclusive_not_failure(self):
  _,case,raw=self.fixture();raw['ELS']['limit_mm']=.1;raw['ELS']['index']=.5;row=self.row();b=apply_bound(row,raw,case['combination']);self.assertGreater(b['upper_bound_ratio'],1);self.assertIsNone(row['Índice']);self.assertIn('Inconclusivo',row['Situação'])
 def test_preserves_failure(self):
  _,case,raw=self.fixture();raw['ELS']['index']=2.;row=self.row();apply_bound(row,raw,case['combination']);self.assertEqual(row['Índice'],2.);self.assertIn('Não atende',row['Situação'])
 def test_opposed_or_missing_not_promoted(self):
  _,case,raw=self.fixture()
  for change in ('opposed','missing','source','base'):
   c=copy.deepcopy(case['combination']);r=copy.deepcopy(raw)
   if change=='opposed':c['q_N_mm']=-1.
   if change=='missing':r['input_data']['properties']['Ix_cm4']=None
   if change=='source':r['input_data']['critical_origin']=''
   if change=='base':r['ELS']['status']='not_evaluated'
   row=self.row();b=apply_bound(row,r,c);self.assertEqual(b['status'],'not_evaluated');self.assertIsNone(row['Índice'])
 def test_inclination_only_normal(self):
  d=example();d.update(load_mode='area',selected_types=['ELS rara'],inclination={'value':30});r=calculate_batch(d);case=r['cases'][-1];row=next(x for x in case['rows'] if x['Verificação']=='Flecha paralela à cobertura');self.assertIsNone(row['Índice']);self.assertFalse(r['whole_member_approved'])
