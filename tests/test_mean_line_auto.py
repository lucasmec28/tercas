import unittest,copy
from tercas.application import defaults
from tercas.weak_catalog import automatic_inputs,nominal_mean_line,geometry_mode
from tercas.annex_e_properties import channel_properties
from tercas.catalogs import entries

class AutoGeometry(unittest.TestCase):
 def data(self,index):
  d=defaults(index);d['weak_catalog']={'geometry_mode':'catalog'};d['segments'][0]['Lz_effective_mm']=3000;return d
 def test_cbca_ex08_geometry_and_j(self):
  d=self.data(19);g=nominal_mean_line(d);self.assertAlmostEqual(g['am_mm'],98.8);self.assertAlmostEqual(g['bm_mm'],48.8);self.assertAlmostEqual(g['cm_mm'],16.4)
  p=channel_properties(**{k:g[k] for k in ('am_mm','bm_mm','cm_mm')},t_mm=1.2,Iy_mm4=10.12e4,Iy_provenance='CBCA2014 Ex08 p69 same section')
  self.assertAlmostEqual(p['xm_mm'],17.37,delta=.01);self.assertAlmostEqual(p['x0_mm'],42.9,delta=.02);self.assertAlmostEqual(p['j_mm'],60.6,delta=.05)
 def test_u_midline_at_free_tip(self):
  g=nominal_mean_line(self.data(83));self.assertAlmostEqual(g['am_mm'],48.8);self.assertAlmostEqual(g['bm_mm'],24.4);self.assertEqual(g['cm_mm'],0)
 def test_lip_half_thickness_not_full(self):
  g=nominal_mean_line(self.data(0));self.assertAlmostEqual(g['cm_mm'],9.4);self.assertNotEqual(g['cm_mm'],8.8)
 def test_corner_difference_not_normative_block(self):
  z=automatic_inputs(self.data(0));self.assertEqual(z['status'],'computed_catalog_inputs');self.assertGreater(z['checks']['Iy_mean_line_relative_difference'],.03);self.assertTrue(z['warnings'])
 def test_ri_not_inferred_or_modified(self):
  d=self.data(0);old=copy.deepcopy(d);z=automatic_inputs(d);self.assertEqual(d,old);self.assertEqual(d['properties']['ri_mm'],old['properties']['ri_mm'])
 def test_missing_ri_not_invented(self):
  d=self.data(0);d['properties']['ri_mm']=None;z=automatic_inputs(d);self.assertEqual(z['status'],'computed_catalog_inputs');self.assertIsNone(d['properties']['ri_mm'])
 def test_explicit_legacy_preserved(self):
  cfg={'mean_line':{'am_mm':48.8,'bm_mm':23.8,'cm_mm':8.8,'origin':'explicit test'}};self.assertEqual(geometry_mode(cfg),'explicit')
  d=self.data(0);d['weak_catalog']=cfg;z=automatic_inputs(d);self.assertEqual(z['mean_line']['cm_mm'],8.8);self.assertFalse(z['mean_line_conversion_verified']);self.assertEqual(z['status'],'not_evaluated')
 def test_empty_legacy_automates(self):
  cfg={'mean_line':{'am_mm':None,'bm_mm':None,'cm_mm':None,'origin':''}};self.assertEqual(geometry_mode(cfg),'catalog')
 def test_invalid_mode_rejected(self):
  with self.assertRaises(ValueError):geometry_mode({'geometry_mode':'guessed'})
 def test_original_low_wy_conservative_warning(self):
  z=automatic_inputs(self.data(107));self.assertEqual(z['status'],'computed_catalog_inputs');self.assertTrue(any('Wy original' in w for w in z['warnings']));self.assertAlmostEqual(z['signs']['positive']['W_mm3'],2680)
 def test_low_wy_exception_not_for_edited_properties(self):
  d=self.data(107);d['properties']['J_mm4']*=2;self.assertEqual(automatic_inputs(d)['status'],'not_evaluated')
 def test_explicit_arbitrary_small_dimensions_do_not_mix_catalogue(self):
  d=self.data(0);d['weak_catalog']={'geometry_mode':'explicit','mean_line':{'am_mm':20,'bm_mm':10,'cm_mm':2,'origin':'test arbitrary'}};self.assertEqual(automatic_inputs(d)['status'],'not_evaluated')
 def test_all_families_conversion_no_radius_guess(self):
  for i,e in enumerate(entries()):
   d=self.data(i);g=nominal_mean_line(d);p=d['properties']
   with self.subTest(i=i):
    self.assertEqual(g['am_mm'],p['h']-p['t']);self.assertEqual(g['cm_mm'],0 if e['family']=='U' else p['lip']-p['t']/2);self.assertEqual(d['properties']['ri_mm'],e['published_properties']['ri_mm'])
if __name__=='__main__':unittest.main()
