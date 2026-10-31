import math,random,sys,unittest
from pathlib import Path
from tercas.mobile_deflection_bound import mobile_deflection_bound
from tercas.core import protocolo_ief as ref
class Bound(unittest.TestCase):
 def call(self,**kw):
  d=dict(L_mm=3000,E_N_mm2=200000,Ig_mm4=1e6,Ml_Nmm=1e6,q_N_mm=.2,P_N=1000);d.update(kw)
  return mobile_deflection_bound(**d)
 def test_zero(self):self.assertEqual(self.call(q_N_mm=0,P_N=0)['bound_abs_mm'],0)
 def test_elastic_point(self):
  r=self.call(q_N_mm=0,Ml_Nmm=1e20)
  self.assertAlmostEqual(r['bound_abs_mm'],1000*3000**3/(48*200000*1e6))
 def test_elastic_uniform(self):
  r=self.call(P_N=0,Ml_Nmm=1e20)
  self.assertAlmostEqual(r['bound_abs_mm'],5*.2*3000**4/(384*200000*1e6))
 def test_sign(self):self.assertEqual(self.call()['bound_abs_mm'],self.call(q_N_mm=-.2,P_N=-1000)['bound_abs_mm'])
 def test_ief_parity(self):
  for ratio in [0,.4,.673**2,.674**2,1,10,100]:
   r=self.call(q_N_mm=0,P_N=ratio*1e6*4/3000)
   self.assertAlmostEqual(r['constant_Imin_mm4'],ref.ief(1e6,r['global_Mmax_Nmm'],1e6))
 def test_status(self):
  r=self.call();v=r['bound_abs_mm']
  self.assertIn('atende',self.call(limit_mm=v)['status'])
  self.assertIn('inconclusivo',self.call(limit_mm=v/2)['status'])
  self.assertFalse(r['actual_mobile_maximum_computed'])
 def test_invalid(self):
  for kw in [dict(P_N=-1),dict(Ml_Nmm=0),dict(q_N_mm=float('nan')),dict(L_mm=True),dict(limit_mm=0),dict(L_mm=1e308),dict(Ml_Nmm=1e-308)]:
   with self.assertRaises(ValueError):self.call(**kw)
 def test_nonlinear_mobile_grid(self):
  rng=random.Random(4139)
  for _ in range(15):
   L=rng.uniform(500,8000);E=200000;Ig=10**rng.uniform(4,7);Ml=10**rng.uniform(4,7)
   q=rng.uniform(0,2);P=rng.uniform(0,2000)
   bound=mobile_deflection_bound(L_mm=L,E_N_mm2=E,Ig_mm4=Ig,Ml_Nmm=Ml,q_N_mm=q,P_N=P)['bound_abs_mm']
   for a in [0,L*.03,L*.2,L*.37,L/2,L*.68,L*.97,L]:
    args=ref.model(L,E,Ig,Ml,q,P,a)
    z,value=ref.peak(args)
    self.assertLessEqual(abs(value),bound*(1+1e-8)+1e-9)
if __name__=='__main__':unittest.main(verbosity=2)
