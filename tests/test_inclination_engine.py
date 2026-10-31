import unittest,math
from tercas.inclination import *
class Tests(unittest.TestCase):
 def test_unit_roundtrip(self):
  for p in (-80,-10,0,10,80):
   a=angle(p,'percent');self.assertAlmostEqual(angle(a['degrees'])['percent'],p)
 def test_angle_errors(self):
  for v,u in [(90,'degrees'),(-90,'degrees'),(float('nan'),'percent'),(True,'degrees'),(5,'x')]:
   with self.assertRaises(ValueError):angle(v,u)
 def test_flat(self): self.assertEqual(decompose(3,-1,0),{'normal':2.,'parallel':0.})
 def test_vertical_invariant(self):
  for th in (0,.1,.5,-.5):
   q=decompose(4,0,th);self.assertAlmostEqual(math.hypot(*q.values()),4)
 def test_wind_is_not_projected(self):
  for th in (0,.1,.5,-.5):self.assertEqual(decompose(0,-4,th),{'normal':-4.,'parallel':0.})
 def test_reversal(self):
  a=decompose(2,3,.2);b=decompose(2,3,-.2)
  self.assertEqual(a['normal'],b['normal']);self.assertEqual(a['parallel'],-b['parallel'])
 def test_area_bases(self):
  th=math.pi/6
  self.assertAlmostEqual(tributary_width(2,th,'roof','horizontal'),math.sqrt(3))
  self.assertAlmostEqual(tributary_width(math.sqrt(3),th,'horizontal','roof'),2)
  self.assertAlmostEqual(tributary_width(2,th,'horizontal','horizontal'),2)
 def test_area_wind(self):
  q=area_actions(100,2,.3,direction='normal',spacing_basis='roof',load_area_basis='roof')
  self.assertAlmostEqual(q['normal'],1.96133);self.assertEqual(q['parallel'],0)
 def test_selfweight(self):
  q=self_weight(10,.3);self.assertAlmostEqual(math.hypot(*q.values()),.0980665)
 def test_combinations(self):
  a=decompose(2,0,.3);b=decompose(0,-3,.3)
  q=combine({'G':a,'W':b},{'G':1.2,'W':1.4})
  expected=decompose(2*1.2,-3*1.4,.3)
  for k in q:self.assertAlmostEqual(q[k],expected[k])
 def test_annex_direct_both_senses(self):
  nx,nz,r,j,cm=1e5,2e5,30,15,1
  for cs in (-1,1):
   got=annex_e_critical(Nex_N=nx,Nez_N=nz,r0_mm=r,j_mm=j,Cs=cs,Cm=cm,provenance='test')
   expected=cs*nx/cm*(j+cs*math.sqrt(j*j+r*r*nz/nx))
   self.assertAlmostEqual(got['Me_Nmm'],expected)
 def test_annex_product(self):
  opts=dict(Nex_N=1e5,Nez_N=2e5,r0_mm=30,j_mm=15,Cm=1,provenance='test')
  a=annex_e_critical(**opts,Cs=1)['Me_Nmm'];b=annex_e_critical(**opts,Cs=-1)['Me_Nmm']
  self.assertAlmostEqual(a*b,1e5*2e5*30**2,delta=1.)
 def test_annex_large_cancellation(self):
  got=annex_e_critical(Nex_N=1,Nez_N=1,r0_mm=1,j_mm=1e16,Cs=-1,Cm=1,provenance='test')
  self.assertGreater(got['Me_Nmm'],0);self.assertAlmostEqual(got['Me_Nmm']*2e16,1)
 def test_missing_inputs_no_approval(self):
  got=weak_resistance(W_mm3=1000,Wc_mm3=1000,fy_MPa=250,Me_Nmm=1e7,provenance='test')
  self.assertEqual(got['status'],'not_evaluated');self.assertEqual(len(got['missing']),2)
 def test_weak_highcrit_yield(self):
  r=weak_resistance(W_mm3=1000,Wc_mm3=1000,fy_MPa=250,Me_Nmm=1e9,Ml_Nmm=1e9,Mdist_Nmm=1e9,provenance='test')
  self.assertAlmostEqual(r['MRd_Nmm'],250000/1.1);self.assertFalse(r['whole_member_approved'])
 def test_weak_critical_monotonic(self):
  vals=[]
  for me in (1e4,1e5,1e6):
   vals.append(weak_resistance(W_mm3=1000,Wc_mm3=1000,fy_MPa=250,Me_Nmm=me,Ml_Nmm=1e6,Mdist_Nmm=1e6,provenance='test')['MRd_Nmm'])
  self.assertEqual(vals,sorted(vals))
 def test_interaction(self):
  r=biaxial_interaction(-40,30,100,50);self.assertAlmostEqual(r['index'],1);self.assertTrue(r['meets'])
  self.assertEqual(biaxial_interaction(40,1,100,None)['status'],'not_evaluated')
  self.assertAlmostEqual(biaxial_interaction(40,0,100,None)['index'],.4)
 def test_weak_shear_pending(self):
  self.assertEqual(weak_shear_status(50)['status'],'not_evaluated');self.assertEqual(weak_shear_status(0)['status'],'not_demanded')


class BeamTests(unittest.TestCase):
 def test_two_axis_uniform(self):
  got=simply_supported_state(3000,1500,{'normal':2,'parallel':1})
  self.assertEqual(got['normal']['M_Nmm'],2250000)
  self.assertEqual(got['parallel']['M_Nmm'],1125000)
  for axis in got:self.assertEqual(got[axis]['V_N'],0)
 def test_reactions_and_point_jump(self):
  q={'normal':2.,'parallel':1.};p={'normal':1000.,'parallel':500.}
  a=simply_supported_state(3000,1000,q,p,1000,'left');b=simply_supported_state(3000,1000,q,p,1000,'right')
  for axis in q:
   self.assertEqual(a[axis]['M_Nmm'],b[axis]['M_Nmm'])
   self.assertAlmostEqual(a[axis]['V_N']-b[axis]['V_N'],p[axis])
   self.assertAlmostEqual(a[axis]['Rleft_N']+a[axis]['Rright_N'],q[axis]*3000+p[axis])
 def test_support_moments(self):
  for x in (0,3000):
   got=simply_supported_state(3000,x,{'normal':-2,'parallel':1},{'normal':1000,'parallel':200},700)
   for axis in got:self.assertAlmostEqual(got[axis]['M_Nmm'],0)
 def test_outside_domain(self):
  with self.assertRaises(ValueError):simply_supported_state(3000,3100,{'normal':1,'parallel':0})

class DomainTests(unittest.TestCase):
 def test_no_ue_distortional_exemption(self):
  with self.assertRaises(ValueError):
   weak_resistance(W_mm3=1000,Wc_mm3=1000,fy_MPa=250,Me_Nmm=1e9,Ml_Nmm=1e9,distortional_not_applicable=True,family='Ue',provenance='test')
 def test_plain_u_nonapplicability(self):
  got=weak_resistance(W_mm3=1000,Wc_mm3=1000,fy_MPa=250,Me_Nmm=1e9,Ml_Nmm=1e9,distortional_not_applicable=True,family='U',provenance='NBR9.3 plain U no roof-sheet restraint')
  self.assertEqual(got['status'],'computed_restricted')



class ReviewRegressionTests(unittest.TestCase):
 def test_asymmetric_first_yield(self):
  got=weak_resistance(W_mm3=10000,Wc_mm3=20000,fy_MPa=250,Me_Nmm=1e12,Ml_Nmm=1e12,Mdist_Nmm=1e12,provenance='review asymmetric')
  self.assertAlmostEqual(got['MRd_Nmm'],2500000/1.1)
  self.assertAlmostEqual(got['capacities_Nmm']['FLT'],5000000/1.1)
  self.assertAlmostEqual(got['capacities_Nmm']['distortional'],2500000/1.1)
 def test_W_cannot_exceed_Wc(self):
  with self.assertRaises(ValueError):
   weak_resistance(W_mm3=2000,Wc_mm3=1000,fy_MPa=250,Me_Nmm=1e9,provenance='test')
 def test_Cm_domain(self):
  for cm in (.19,1.01):
   with self.assertRaises(ValueError):
    annex_e_critical(Nex_N=1e5,Nez_N=2e5,r0_mm=30,j_mm=15,Cs=1,Cm=cm,provenance='test')
  for cm in (.2,1.):
   self.assertGreater(annex_e_critical(Nex_N=1e5,Nez_N=2e5,r0_mm=30,j_mm=15,Cs=1,Cm=cm,provenance='test')['Me_Nmm'],0)

if __name__=='__main__':unittest.main()
