import unittest,math
from tercas.core.local_table12 import local_critical
from tercas.catalogs import entries
class LocalTableTests(unittest.TestCase):
 def test_u_manual(self):
  r=local_critical('U',200,100,2,20000)
  self.assertAlmostEqual(r['kl'],.5**-1.843)
  self.assertAlmostEqual(r['Ml_Nmm'],.5**-1.843*math.pi**2*200000/(12*.91)*.0001*20000)
 def test_126_u(self):
  for e in entries():
   if e['family']=='U':
    with self.subTest(profile=e['name']):
     d=e['dimensions_mm'];r=local_critical('U',d['h'],d['bf'],d['t'],e['published_properties']['Wx_cm3']*1000)
     self.assertGreater(r['Ml_Nmm'],0)
 def test_endpoints(self):
  for ratio in [.1,1]:self.assertGreater(local_critical('U',100,100*ratio,1,1000)['Ml_Nmm'],0)
  for ratio in [.0999,1.001]:
   with self.assertRaises(ValueError):local_critical('U',100,100*ratio,1,1000)
 def test_ue_cases(self):
  for eta,mu in [(.2,.1),(.6,.2),(.6,.3),(1,.3)]:self.assertGreater(local_critical('Ue',100,100*eta,1,1000,D_mm=mu*100)['Ml_Nmm'],0)
  with self.assertRaises(ValueError):local_critical('Ue',100,50,1,1000,D_mm=5)
 def test_elastic_scaling(self):
  a=local_critical('U',200,100,2,20000);b=local_critical('U',200,100,2,20000,E_MPa=100000)
  self.assertAlmostEqual(a['Ml_Nmm'],2*b['Ml_Nmm'])
if __name__=='__main__':unittest.main()
