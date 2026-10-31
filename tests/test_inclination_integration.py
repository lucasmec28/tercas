import unittest,math,copy
from tercas.application import example,calculate,rows
from tercas.batch import area_bundle,calculate_batch
class Tests(unittest.TestCase):
 def d(self):
  d=example();d.update(load_mode='area',selected_types=['ELU normal','ELS rara'],inclination={'value':30,'unit':'degrees'});d['area_inputs']['permanent_kgf_m2']=10.;return d
 def test_normal_wind_and_gravity(self):
  d=self.d();b=area_bundle(d);v=b['case_vectors_N_mm'];self.assertEqual(v['V_Cima']['parallel'],0);self.assertAlmostEqual(v['CP']['parallel']/v['CP']['normal'],math.tan(math.pi/6))
  self.assertAlmostEqual(math.hypot(*v['PP'].values()),d['properties']['mass_kg_m']*9.80665/1000)
 def test_p_and_simultaneous(self):
  d=self.d();r=calculate_batch(d);p=next(x for x in r['cases'] if x['combination']['id'].startswith('P_ELU'))
  c=p['combination'];self.assertAlmostEqual(c['P_N'],1500*math.cos(math.pi/6));self.assertAlmostEqual(c['P_vector']['parallel'],750)
  ev=p['evidence']['inclination'];mid=next(x for x in ev['states'] if x['x_mm']==d['L_mm']/2)
  for axis in ('normal','parallel'):self.assertAlmostEqual(mid[axis]['M_Nmm'],c['q_vector'][axis]*d['L_mm']**2/8+c['P_vector'][axis]*d['L_mm']/4)
  self.assertTrue(any(x['Verificação']=='Flexão biaxial' and x['Índice'] is None for x in p['rows']))
 def test_direct_does_not_rotate(self):
  d=self.d();d['load_mode']='direct';d['q_parallel_uls']=.5;r=calculate(d);self.assertEqual(r['inclination_evidence']['ELU']['q_vector']['normal'],d['q_uls']);self.assertTrue(any(x['Verificação']=='Flexão biaxial' for x in rows(r)))
 def test_flat_no_new_pending(self):
  d=self.d();d['inclination']={'value':0};r=calculate_batch(d);self.assertFalse(any('biaxial' in x['Verificação'] for c in r['cases'] for x in c['rows']))
 def test_percent_equivalent(self):
  d=self.d();a=area_bundle(d);d['inclination']={'value':100*math.tan(math.pi/6),'unit':'percent'};b=area_bundle(d);self.assertEqual(a['case_vectors_N_mm'],b['case_vectors_N_mm'])
 def test_invalid_cfg(self):
  d=self.d();d['inclination']={'value':90}
  with self.assertRaises(ValueError):area_bundle(d)
