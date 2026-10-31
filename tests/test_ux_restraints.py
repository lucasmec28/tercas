import copy,unittest,random,math
from io import BytesIO
from docx import Document
from tercas.application import example,calculate,rows,build_spec
from tercas.report import word
from tercas.ux_inputs import CB_LABELS,cb_code,flange_segments,whole_span
from tercas.core.travamentos_nbr import segment_moments,moment

class UXRestraints(unittest.TestCase):
 def data(self):
  d=example();d['segments']=whole_span(d['L_mm'],1000.,3000.,3000.,'one','Teste sintético')
  return d
 def test_positive_uses_upper(self):
  d=self.data();r=calculate(d)['FLT_segments'][0];self.assertEqual(r['compressed_flange'],'superior');self.assertEqual(r['Ly_used_mm'],1000.)
 def test_negative_uses_lower(self):
  d=self.data();d['q_uls']*=-1;d['P_uls']*=-1;r=calculate(d)['FLT_segments'][0];self.assertEqual(r['compressed_flange'],'inferior');self.assertEqual(r['Ly_used_mm'],3000.)
 def test_reversal_both_flange_checks(self):
  d=self.data();d.update(q_uls=1.,P_uls=-2000.,x_uls=500.);r=calculate(d)['FLT_segments'][0]
  self.assertEqual({x['compressed_flange'] for x in r['flange_results']},{'superior','inferior'})
  self.assertEqual(r['index'],max(x['index'] for x in r['flange_results']))
  for f in r['flange_results']:self.assertEqual(f['moments']['Cb_from_moments'],r['full_segment_moments']['Cb_from_moments'])
 def test_no_artificial_zero_moment_brace(self):
  d=self.data();d.update(q_uls=1.,P_uls=-2000.,x_uls=500.);r=calculate(d)['FLT_segments'][0]
  for f in r['flange_results']:self.assertEqual(f['Lz_used_mm'],3000.)
 def test_missing_inactive_flange_is_ok(self):
  d=self.data();d['segments'][0]['Ly_bottom_effective_mm']=None;self.assertIn('index',calculate(d)['FLT_segments'][0])
 def test_missing_active_flange_is_pending(self):
  d=self.data();d['segments'][0]['Ly_top_effective_mm']=None;r=calculate(d)['FLT_segments'][0];self.assertEqual(r['status'],'FLT_not_evaluated');self.assertNotIn('index',r)
 def test_reversal_missing_one_no_partial_pass(self):
  d=self.data();d.update(q_uls=1.,P_uls=-2000.,x_uls=500.);d['segments'][0]['Ly_top_effective_mm']=None
  r=calculate(d)['FLT_segments'][0];self.assertNotIn('index',r);self.assertEqual(len(r['flange_results']),2)
 def test_legacy_equivalence(self):
  d=example();r=calculate(d)['FLT_segments'][0];d['segments']=flange_segments(d['segments']);r2=calculate(d)['FLT_segments'][0];self.assertAlmostEqual(r['index'],r2['index']);self.assertAlmostEqual(r['Me_Nmm'],r2['Me_Nmm'])
 def test_span_not_duplicated(self):
  s=whole_span(4200.,2100.,4200.,4200.)[0];self.assertEqual(s['start_mm'],0);self.assertEqual(s['end_mm'],4200)
 def test_cb_translation_roundtrip(self):
  for k,v in CB_LABELS.items():self.assertEqual(cb_code(v),k);self.assertEqual(cb_code(k),k)
  with self.assertRaises(ValueError):cb_code('invalid')
 def test_support_rows_removed(self):
  r=calculate(self.data());self.assertFalse(any('Apoio' in row['Verificação'] for row in rows(r)))
 def test_word_no_support_verifications_and_no_english_cb(self):
  doc=Document(BytesIO(word(calculate(self.data()))));text='\n'.join(p.text for p in doc.paragraphs)
  self.assertNotIn('Apoio esquerdo',text);self.assertNotIn('Apoio direito',text);self.assertNotIn('Cb one',text);self.assertIn('mesa superior',text)
 def test_zero_demand_not_applicable(self):
  d=self.data();d.update(q_uls=0.,P_uls=0.);self.assertEqual(calculate(d)['FLT_segments'][0]['status'],'not_applicable')
 def test_torsion_length_independent(self):
  d=self.data();r=calculate(d)['FLT_segments'][0];d['segments'][0]['Lz_effective_mm']=1000.;r2=calculate(d)['FLT_segments'][0];self.assertNotEqual(r['Me_Nmm'],r2['Me_Nmm']);self.assertEqual(r['Ly_used_mm'],r2['Ly_used_mm'])
 def test_signed_extrema_vs_dense_grid(self):
  rng=random.Random(781)
  for _ in range(100):
   L=rng.uniform(1000,6000);a=rng.uniform(.1*L,.9*L);q=rng.uniform(-2,2);P=rng.uniform(-4000,4000)
   m=segment_moments(L,q,P,a,0,L);vals=[moment(L*i/2000,L,q,P,a) for i in range(2001)]
   self.assertGreaterEqual(m['Mpositive_Nmm']+1e-6,max(vals));self.assertLessEqual(m['Mnegative_Nmm']-1e-6,min(vals))
   self.assertLess(abs(m['Mpositive_Nmm']-max(vals)),max(1,abs(m['Mmax_Nmm'])*.005))
if __name__=='__main__':unittest.main()
