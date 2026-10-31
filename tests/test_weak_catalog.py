import unittest,copy,math
from tercas.application import defaults,calculate,rows
from tercas.weak_catalog import automatic_inputs
from tercas.weak_axis import capacities

def case():
 d=defaults(83);p=d['properties'];d.update(q_uls=.1,q_parallel_uls=.1,route_domain=True)
 d['segments'][0].update(Ly_effective_mm=3000,Lz_effective_mm=3000,restraint_provenance='teste')
 d['weak_catalog']={'Lx_mm':3000.,'mean_line':{'am_mm':48.8,'bm_mm':24.4,'cm_mm':0.,'origin':'SYNTHETIC mean-line definition; not qualified catalogue conversion'}}
 d['weak_axis']={s:dict(Ml_Nmm=2e6,Mdist_Nmm=None,plain_u_no_distortion=True,provenance='SYNTHETIC critical specific sign '+s) for s in ('positive','negative')}
 return d
class CatalogTests(unittest.TestCase):
 def test_hypothesis_only_positive(self):
  from tercas.weak_catalog import critical_hypothesis
  h=critical_hypothesis(0);self.assertEqual(h['positive']['Ml_Nmm'],910000);self.assertIsNone(h['negative']['Ml_Nmm']);self.assertIsNone(h['positive']['Mdist_Nmm']);self.assertIn('HIPÓTESE PROVISÓRIA',h['positive']['provenance'])
 def test_family_no_lip_invention(self):
  d=case();d['weak_catalog']['mean_line']['cm_mm']=.1;self.assertEqual(automatic_inputs(d)['status'],'not_evaluated')
 def test_existing_properties(self):
  d=case();z=automatic_inputs(d);self.assertEqual(z['status'],'computed_catalog_inputs');s=z['signs']['positive'];p=d['properties']
  self.assertAlmostEqual(s['Nex_N'],math.pi**2*p['E_MPa']*p['Ix_cm4']*1e4/3000**2)
  self.assertAlmostEqual(s['Nez_N'],(p['G_MPa']*p['J_mm4']+math.pi**2*p['E_MPa']*p['Cw_mm6']/3000**2)/26.3**2)
  self.assertAlmostEqual(s['r0_mm'],26.3);self.assertLessEqual(s['W_mm3'],s['Wc_mm3']);self.assertEqual(s['Cs'],1);self.assertEqual(z['signs']['negative']['Cs'],-1)
 def test_no_meanline_inference(self):
  d=case();del d['weak_catalog']['mean_line'];z=automatic_inputs(d);self.assertEqual(z['status'],'not_evaluated');self.assertIn('am/bm/cm',z['missing'][0])
 def test_auto_capacities(self):
  c=capacities(case(),'U');self.assertTrue(c['positive']['MRd_Nmm']);self.assertTrue(c['negative']['MRd_Nmm']);self.assertNotEqual(c['positive']['annex_e']['Me_Nmm'],c['negative']['annex_e']['Me_Nmm'])
 def test_no_critical_source(self):
  d=case();d['weak_axis']['negative']['provenance']='';self.assertEqual(capacities(d,'U')['negative']['status'],'not_evaluated')
 def test_not_copy_tabulated_critical(self):
  d=case();d['weak_axis']['positive']['Ml_Nmm']=None;self.assertEqual(capacities(d,'U')['positive']['status'],'not_evaluated')
 def test_inconsistent_geometry(self):
  d=case();d['weak_catalog']['mean_line']['bm_mm']=40;z=automatic_inputs(d);self.assertEqual(z['status'],'not_evaluated')
 def test_changed_properties(self):
  d=case();d['properties']['Iy_cm4']*=2;z=automatic_inputs(d);self.assertEqual(z['status'],'not_evaluated')
 def test_missing_torsion_partial(self):
  d=case();d['properties']['J_mm4']=None;r=calculate(d);self.assertEqual(r['inclination_evidence']['ELU']['biaxial']['status'],'not_evaluated')
 def test_max_lz_conservative(self):
  d=case();s=copy.deepcopy(d['segments'][0]);s['Lz_effective_mm']=4000;d['segments'].append(s);self.assertEqual(automatic_inputs(d)['Lz_mm'],4000)
 def test_fixed_cm(self):
  for s in automatic_inputs(case())['signs'].values():self.assertEqual(s['Cm'],1)
if __name__=='__main__':unittest.main()
