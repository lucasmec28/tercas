"""Focused mathematical/negative controls, no whole-member pass."""
import copy,json,math,random,unittest
from decimal import Decimal,localcontext
from pathlib import Path
from unittest.mock import patch
import weak_capacity as w

class TestWeakReference(unittest.TestCase):
 def setUp(self):self.row=w._row(1.5)
 def test_sources(self):w.verify_sources()
 def test_beta_both_sides(self):
  for t in w.THICKNESSES:
   r=w._row(t);a=w.first_yield_and_beta(r,'web');b=w.first_yield_and_beta(r,'lips')
   self.assertAlmostEqual(a['beta']+b['beta'],2)
   self.assertLess(a['beta'],1);self.assertGreater(b['beta'],1)
   self.assertEqual(a['My_Nmm'],b['My_Nmm']);self.assertEqual(a['first_yield_state'],'tension');self.assertEqual(b['first_yield_state'],'compression')
   self.assertEqual(a['depth_perpendicular_to_bending_axis_mm'],50)
 def test_compression_modulus_not_first_yield(self):
  a=w.first_yield_and_beta(self.row,'web')
  self.assertGreater(a['Sfc_mm3'],a['Sf_first_yield_mm3'])
  self.assertAlmostEqual(a['My_Nmm'],959959.5746390079)
 def test_global_independent_decimal(self):
  with localcontext() as ctx:
   ctx.prec=60
   D=lambda x:Decimal(str(x))
   pi=Decimal('3.14159265358979323846264338327950288419716939937510582097494')
   for t in w.THICKNESSES:
    r=w._row(t);p=r['properties']
    for L in (3000,4000,5000,6000):
     P=pi*pi*D(w.E)*D(p['Ix_strong_mm4'])/D(L)**2
     T=D(w.G)*D(p['J_mm4'])+pi*pi*D(w.E)*D(p['Cw_mm6'])/D(L)**2
     j=D(p['beta_mm5'])/(2*D(p['Iy_weak_mm4']))-(D(p['shear_center_xy_mm'][0])-D(p['centroid_xy_mm'][0]))
     for side,sign in [('web',1),('lips',-1)]:
      expected=P*(sign*abs(j)+(j*j+T/P).sqrt());got=w.global_weak(r,L,side)
      self.assertAlmostEqual(float(expected)/got['Mcre_Nmm'],1,places=12)
      self.assertEqual(got['Cs'],sign)
 def test_global_uses_strong_flexural_stiffness(self):
  x=w.global_weak(self.row,4000,'lips');p=self.row['properties']
  self.assertAlmostEqual(x['Pex_N'],math.pi**2*w.E*p['Ix_strong_mm4']/4000**2)
  self.assertGreater(x['Pex_N'],math.pi**2*w.E*p['Iy_weak_mm4']/4000**2)
 def test_global_root_product(self):
  for t in w.THICKNESSES:
   for L in (3000,6000):
    r=w._row(t);a=w.global_weak(r,L,'web');b=w.global_weak(r,L,'lips')
    self.assertAlmostEqual(a['Mcre_Nmm']*b['Mcre_Nmm']/(a['Pex_N']*a['torsion_warping_stiffness_Nmm2']),1,places=13)
 def test_F2_join(self):
  eps=1e-10
  a=w.flexural_floor(1,.5,1,1,.7);b=w.flexural_floor(1,.5+eps,1,1,.7)
  self.assertEqual(a['Mne_floor_Nmm'],.5);self.assertAlmostEqual(b['Mne_floor_Nmm'],.5+eps,places=14)
 def test_algebra_floor_random(self):
  rng=random.Random(20261104)
  for _ in range(12000):
   My=10**rng.uniform(-3,9);Mp=My*rng.uniform(1,3);b=rng.uniform(.4,1.99)
   e=My*10**rng.uniform(-3,4);ell=My*10**rng.uniform(-1.39,4);d=My*10**rng.uniform(-1.39,4)
   f=w.flexural_floor(My,e,ell,d,b);full=w.full_DSM(My,Mp,e,ell,d,b,rng.random(),rng.random())
   self.assertLessEqual(f['Mn_floor_Nmm'],full['Mn']*(1+2e-14))
   self.assertLessEqual(f['Mnl_floor_Nmm'],full['Mnl']*(1+2e-14));self.assertLessEqual(f['Mnd_floor_Nmm'],full['Mnd']*(1+2e-14))
 def test_dist_bound_monotone(self):
  for beta in (.4,.714,1,1.286,1.99):
   a=w.flexural_floor(1,2,.1,.04,beta);b=w.flexural_floor(1,2,.1,20,beta)
   self.assertLess(a['Mnd_floor_Nmm'],b['Mnd_floor_Nmm'])
 def test_sufficient_lambda_not_floor_lambda(self):
  # A very small global floor could hide out-of-domain actual My/local.
  with self.assertRaises(ValueError):w.flexural_floor(100,1,3,100,.71)
 def test_bad_numbers(self):
  for bad in (0,-1,True,float('nan'),float('inf'),'1'):
   for i in range(4):
    a=[1,1,1,1,.71];a[i]=bad
    with self.assertRaises(ValueError):w.flexural_floor(*a)
 def test_bad_beta(self):
  for b in (0,.399,2,3,True,float('nan')):
   with self.assertRaises(ValueError):w.flexural_floor(1,1,1,1,b)
 def test_partial_F2_F3_is_not_capacity(self):
  for side in ('web','lips'):
   r=w.reference_capacity(1.5,4000,side);partial=r['partial_F2_F3']
   self.assertTrue(partial['F4_not_resolved_by_this_partial_result']);self.assertGreater(partial['Ma_F2_F3_only_Nmm'],0)
   if side=='web':self.assertEqual(r['Ma_reference_floor_Nmm'],partial['Ma_F2_F3_only_Nmm'])
   else:self.assertLessEqual(r['Ma_reference_floor_Nmm'],partial['Ma_F2_F3_only_Nmm'])
 def test_scaled_bound_outward(self):
  from fractions import Fraction
  for t in w.THICKNESSES:
   r=w.discrete_web_diagnostic(t,4000,accept_discrete_only=True)
   self.assertTrue(r['scaled_bound_float_not_above_exact'])
   self.assertLessEqual(Fraction(r['spectral_lower_bound_AISI_E_Nmm']),Fraction(r['scaled_bound_exact_rational']))
 def test_web_component_F4_not_applicable(self):
  for t in w.THICKNESSES:
   r=w.reference_capacity(t,4000,'web')
   self.assertGreater(r['Ma_reference_floor_Nmm'],0);self.assertIsNone(r['Mcrd_identified_Nmm'])
   self.assertEqual(r['F4_applicability']['classification'],'F4_NOT_APPLICABLE_PURE_WEAK_WEB')
   self.assertFalse(r['F4_applicability']['mixed_field_waiver']);self.assertFalse(r['F4_applicability']['Mcrd_is_infinite'])
   self.assertFalse(r['H4_for_actual_member_eligible'])
 def test_lips_24_reference_cases(self):
  for t in w.THICKNESSES:
   for L in (3000,4000,5000,6000):
    r=w.reference_capacity(t,L,'lips')
    self.assertGreater(r['Ma_reference_floor_Nmm'],0)
    self.assertLess(r['Ma_reference_floor_Nmm'],.9*r['yield_and_asymmetry']['My_Nmm'])
    self.assertFalse(r['whole_member_approved']);self.assertFalse(r['NBR_capacities_used'])
 def test_diagnostic_not_capacity(self):
  for t in w.THICKNESSES:
   r=w.discrete_web_diagnostic(t,4000,accept_discrete_only=True)
   self.assertIsNone(r['Mcrd_identified_Nmm']);self.assertIsNone(r['capacity_for_H4_Nmm']);self.assertFalse(r['physical_continuum_proof']);self.assertFalse(r['distortional_exemption'])
   self.assertGreater(r['scalar_conditional_floor']['Ma_formula_floor_Nmm'],0)
 def test_F4_mixed_field_rejected(self):
  for key in ['N_N','Mx_Nmm','B_Nmm2','V_N','T_Nmm']:
   for value in [1,-1,True,float('nan')]:
    with self.assertRaises(ValueError):w.f4_pure_web_applicability(self.row,**{key:value})
    with self.assertRaises(ValueError):w.reference_capacity(1.5,4000,'web',**{key:value})
 def test_F4_sense_and_profile_rejected(self):
  for kwargs in [dict(side='lips'),dict(side='positive'),dict(uniform_pure_weak=False),dict(uniform_pure_weak=1)]:
   with self.assertRaises(ValueError):w.f4_pure_web_applicability(self.row,**kwargs)
  for key,value in [('profile_id','other'),('nodes_sha256','changed')]:
   r=copy.deepcopy(self.row);r[key]=value
   with self.assertRaises(ValueError):w.f4_pure_web_applicability(r)
 def test_F4_corner_tension_geometric(self):
  for t in w.THICKNESSES:
   r=w._row(t);g=w.f4_pure_web_applicability(r)
   self.assertGreater(g['lip_corner_clearance_lower_mm'],23)
   self.assertTrue(g['F2_and_F3_still_required']);self.assertFalse(g['fully_braced_RP21_assumption_transferred'])
  r=copy.deepcopy(self.row);r['properties']['centroid_xy_mm'][0]=49
  with self.assertRaises(ValueError):w.f4_pure_web_applicability(r)
 def test_diagnostic_requires_ack(self):
  for flag in (False,1,None):
   with self.assertRaises(ValueError):w.discrete_web_diagnostic(1.5,4000,accept_discrete_only=flag)
 def test_spans_and_thickness(self):
  for L in (0,2999,6001,True,float('nan')):
   with self.assertRaises(ValueError):w.reference_capacity(1.5,L,'lips')
  for t in (1.2,1.6,True,float('inf')):
   with self.assertRaises(ValueError):w.reference_capacity(t,4000,'lips')
 def test_load_support_axial_holes(self):
  for kwargs in [dict(support='fixed_warping'),dict(loading='CG_transverse'),dict(loading='biaxial_with_torsion'),dict(N_N=1),dict(N_N=True),dict(holes=True),dict(holes=None)]:
   with self.assertRaises(ValueError):w.reference_capacity(1.5,4000,'lips',**kwargs)
 def test_invalid_side(self):
  for side in ('positive','negative',1,None):
   with self.assertRaises(ValueError):w.reference_capacity(1.5,4000,side)
 def test_sign_conventions_opposite(self):
  for m in (-1,1):self.assertNotEqual(w.compression_side_from_vlasov_my(m),w.compression_side_from_fsm_my(m))
  self.assertEqual(w.compression_side_from_vlasov_my(1),'lips');self.assertEqual(w.compression_side_from_fsm_my(1),'web')
  self.assertIsNone(w.compression_side_from_vlasov_my(0));self.assertIsNone(w.compression_side_from_fsm_my(0))
 def test_B4(self):
  for t in w.THICKNESSES:self.assertTrue(w.dimensional_gate(t)['passed'])
 def test_actual_nu_E_G_explicit(self):
  r=w.reference_capacity(1.5,4000,'lips');self.assertEqual(r['material'],dict(E_MPa=203000.,G_MPa=78000.,nu_plate=.3,Fy_MPa=250.))
 def test_wrong_material_row_rejected(self):
  row=copy.deepcopy(self.row);row['properties']['j_mm']*=-1
  with self.assertRaises(ValueError):w.global_weak(row,4000,'lips')
 def test_first_yield_modulus_corruption(self):
  row=copy.deepcopy(self.row);row['exterior_moduli']['Wy_first_yield_mm3']*=2
  with self.assertRaises(ValueError):w.first_yield_and_beta(row,'web')
if __name__=='__main__':unittest.main(verbosity=2)
