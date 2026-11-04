"""Run from any cwd: python /absolute/path/test_consumer_independent.py"""
import ast, copy, hashlib, importlib.util, json, math, pathlib, sys, unittest
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('independent_weak',ROOT/'weak_capacity.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class ConsumerReview(unittest.TestCase):
 def test_source_pins(self):w.verify_sources()
 def test_sides_and_zero(self):
  for m in [-1e20,-1,1,1e20]:
   self.assertEqual(w.compression_side_from_vlasov_my(m),'lips' if m>0 else 'web')
   self.assertEqual(w.compression_side_from_fsm_my(m),'web' if m>0 else 'lips')
  self.assertIsNone(w.compression_side_from_vlasov_my(0));self.assertIsNone(w.compression_side_from_fsm_my(0))
  for m in [True,False,float('nan'),float('inf'),'1',None]:
   for fn in [w.compression_side_from_vlasov_my,w.compression_side_from_fsm_my]:
    with self.subTest(m=m,fn=fn.__name__),self.assertRaises(ValueError):fn(m)
 def test_all_six_profiles(self):
  for t in w.THICKNESSES:
   r=w._row(t);p=r['properties'];ex=r['exterior_moduli']['extents_mm']['x'];cx=p['centroid_xy_mm'][0]
   for L in [3000,3501.25,4000,5000,5999.99,6000]:
    for side in w.SIDES:
     with self.subTest(t=t,L=L,side=side):
      q=w.reference_capacity(t,L,side);y=q['yield_and_asymmetry'];c=q['global_elastic'];cr=r['modal_criticals']
      self.assertAlmostEqual(y['My_Nmm'],250*p['Iy_weak_mm4']/max(cx-ex[0],ex[1]-cx))
      self.assertEqual(y['first_yield_state'],'tension' if side=='web' else 'compression')
      self.assertAlmostEqual(y['beta'],max(.4,2*(cx-ex[0] if side=='web' else ex[1]-cx)/50))
      self.assertAlmostEqual(q['Mcrl_Nmm'],1.015*cr[side+'_local']['value_Nmm'])
      self.assertEqual(c['Cs'],1 if side=='web' else -1)
      Pex=math.pi**2*203000*p['Ix_strong_mm4']/L**2
      T=78000*p['J_mm4']+math.pi**2*203000*p['Cw_mm6']/L**2
      expected=Pex*(c['Cs']*abs(p['j_mm'])+math.sqrt(p['j_mm']**2+T/Pex))
      self.assertTrue(math.isclose(c['Mcre_Nmm'],expected,rel_tol=1e-12))
      self.assertFalse(q['whole_member_approved']);self.assertFalse(q['NBR_capacities_used']);self.assertFalse(q['H4_for_actual_member_eligible'])
      if side=='web':
       self.assertIsNone(q['Mcrd_identified_Nmm']);self.assertIsNone(q['reference_formula_floor']['Mnd_floor_Nmm'])
       self.assertEqual(q['status'],'CONDITIONAL_IDEAL_REFERENCE_FLOOR')
       f=q['F4_applicability'];self.assertEqual(f['classification'],'F4_NOT_APPLICABLE_PURE_WEAK_WEB')
       self.assertFalse(f['Mcrd_is_infinite']);self.assertFalse(f['mixed_field_waiver']);self.assertTrue(f['F2_and_F3_still_required'])
       partial=q['partial_F2_F3'];self.assertEqual(q['Ma_reference_floor_Nmm'],.9*min(partial['Mne_floor_Nmm'],partial['Mnl_floor_Nmm']))
       d=w.discrete_web_diagnostic(t,L,accept_discrete_only=True)
       self.assertIsNone(d['capacity_for_H4_Nmm']);self.assertIsNone(d['Mcrd_identified_Nmm']);self.assertFalse(d['physical_continuum_proof']);self.assertFalse(d['distortional_exemption']);self.assertTrue(d['scaled_bound_float_not_above_exact'])
      else:self.assertGreater(q['Ma_reference_floor_Nmm'],0)
 def test_magnitude_j_and_cancel_stability(self):
  r=w._row(1.5);p=r['properties'];positive=w.global_weak(r,4000,'lips')
  r2=copy.deepcopy(r);p2=r2['properties'];x0=p2['shear_center_xy_mm'][0]-p2['centroid_xy_mm'][0]
  p2['j_mm']=-p2['j_mm'];p2['beta_mm5']=2*p2['Iy_weak_mm4']*(p2['j_mm']+x0)
  negative=w.global_weak(r2,4000,'lips')
  self.assertTrue(math.isclose(positive['Mcre_Nmm'],negative['Mcre_Nmm'],rel_tol=1e-14))
  a=w.global_weak(r,1e-8,'web')['Mcre_Nmm'];b=w.global_weak(r,1e-8,'lips')['Mcre_Nmm']
  self.assertGreater(b,0);self.assertGreater(a,b)
 def test_reference_rejects_changed_domain(self):
  bad=[dict(L=2999),dict(L=6001),dict(L=float('nan')),dict(L=True),dict(t=1.2),dict(t=2.01),dict(side='major'),dict(side=None),dict(support='fixed'),dict(loading='uniform'),dict(N_N=1e-9),dict(N_N=True),dict(holes=True),dict(holes=0)]
  for extra in bad:
   args=dict(t=1.5,L=4000,side='web');args.update(extra)
   with self.subTest(extra=extra),self.assertRaises(ValueError):w.reference_capacity(**args)
  for ack in [False,None,1,'true']:
   with self.subTest(ack=ack),self.assertRaises(ValueError):w.discrete_web_diagnostic(1.5,4000,accept_discrete_only=ack)
 def test_slenderness_and_transition(self):
  for b in [.4,.71,1,1.29,1.999]:
   r=w.flexural_floor(100,50,4,4,b)
   self.assertEqual(r['Mne_floor_Nmm'],50)
   self.assertAlmostEqual(r['Mnl_floor_Nmm'],50/(1+.55*b*50/4))
   self.assertAlmostEqual(r['Mnd_floor_Nmm'],100/(1+.60*b*25))
   for ell,d in [(3.999999,4),(4,3.999999)]:
    with self.assertRaises(ValueError):w.flexural_floor(100,50,ell,d,b)
  for b in [.399999,2,-1,0,float('nan'),float('inf'),True]:
   with self.assertRaises(ValueError):w.flexural_floor(100,50,10,10,b)
 def test_control_helper_domain(self):
  for args in [(100,120,60,2.39,100,.7,0,0),(100,120,60,100,3.99,.7,0,0),(100,120,60,100,100,.39,0,0),(100,120,60,100,100,2,0,0)]:
   with self.subTest(args=args),self.assertRaises(ValueError):w.full_DSM(*args)
 def test_public_api_calls_complete_source_verification(self):
  from unittest.mock import patch
  with patch.object(w,'verify_sources',side_effect=ValueError('qualification blocked')) as gate:
   with self.assertRaisesRegex(ValueError,'qualification blocked'):w.reference_capacity(1.5,4000,'lips')
   gate.assert_called_once()
 def test_f4_rejects_mixed_action_and_unreviewed_geometry(self):
  for t in w.THICKNESSES:
   r=w._row(t);self.assertGreater(w.f4_pure_web_applicability(r)['lip_corner_clearance_lower_mm'],0)
   for field in ['N_N','Mx_Nmm','B_Nmm2','V_N','T_Nmm']:
    for value in [1e-20,-1e-20,True,float('nan'),float('inf')]:
     with self.subTest(t=t,field=field,value=value),self.assertRaises(ValueError):w.f4_pure_web_applicability(r,**{field:value})
     with self.subTest(t=t,field=field,value=value),self.assertRaises(ValueError):w.reference_capacity(t,4000,'web',**{field:value})
   for extra in [dict(side='lips'),dict(uniform_pure_weak=False),dict(uniform_pure_weak=1)]:
    with self.assertRaises(ValueError):w.f4_pure_web_applicability(r,**extra)
   for mutate in ['profile_id','nodes_sha256','centroid']:
    bad=copy.deepcopy(r)
    if mutate=='centroid':bad['properties']['centroid_xy_mm'][0]+=.01
    else:bad[mutate]='unreviewed'
    with self.subTest(t=t,mutate=mutate),self.assertRaises(ValueError):w.f4_pure_web_applicability(bad)
 def test_f4_manifest_fails_closed(self):
  import tempfile
  from unittest.mock import patch
  row=w._row(1.5)
  with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).resolve().parent) as tmp:
   base=pathlib.Path(tmp)/'f4_applicability/independent';base.mkdir(parents=True)
   (base/'MANIFEST.json').write_text('{}')
   with patch.object(w,'ROOT',pathlib.Path(tmp)),self.assertRaisesRegex(ValueError,'manifest mismatch'):w.f4_pure_web_applicability(row)
 def test_no_external_resistance_imports(self):
  tree=ast.parse((ROOT/'weak_capacity.py').read_text());imports=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.Import):imports.extend(x.name for x in n.names)
   elif isinstance(n,ast.ImportFrom):imports.append(n.module)
  self.assertEqual(set(imports),{'pathlib','hashlib','json','math','fractions'})
  for n in ast.walk(tree):
   if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.endswith(('.py','.json','.npz')):self.assertNotIn('nbr',n.value.lower())
if __name__=='__main__':unittest.main(verbosity=2)
