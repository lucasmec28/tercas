import unittest,math
from tercas.catalogs import entries,catalog_labels,catalog_entry,critical_defaults,material,apply_material
from tercas.core.selecao import select,edit
class CatalogTests(unittest.TestCase):
 def test_count(self):
  es=entries();self.assertEqual(len(es),209);self.assertEqual(sum(e['family']=='Ue' for e in es),83);self.assertEqual(len(set(catalog_labels())),209)
 def test_full_import(self):
  for i,e in enumerate(entries()):
   with self.subTest(index=i):
    raw=e['raw_source_values'];p=e['published_properties'];s=select(i)
    self.assertEqual(p['J_mm4'],raw['It cm⁴']*1e4);self.assertEqual(p['Cw_mm6'],raw['Cw cm⁶']*1e6)
    self.assertEqual(s['fields']['ri_mm']['value'],raw['ri mm']);self.assertEqual(s['fields']['J_mm4']['value'],p['J_mm4']);self.assertEqual(s['fields']['Cw_mm6']['value'],p['Cw_mm6'])
    self.assertEqual(critical_defaults(i)['Ml_Nmm'],None if raw['Ml,x kNm'] is None else raw['Ml,x kNm']*1e6)
    self.assertFalse(s['whole_member_approved'])
 def test_missing_not_filled(self):
  es=entries();self.assertEqual(sum(e['critical_values']['Ml_Nmm'] is None for e in es),133)
  self.assertTrue(all(e['critical_values']['Mdist_Nmm'] is None for e in es if e['family']=='U'))
 def test_indices(self):
  for i in [-1,209,True,1.1]:
   with self.assertRaises(ValueError):catalog_entry(i)
 def test_edit_invalidation(self):
  s=select(0);edit(s,'ri_mm',2.,'Teste');self.assertIsNone(s['fields']['J_mm4']['value'])
 def test_materials(self):
  for name,fy,fu in [('ASTM A36',250,400),('USI-CIVIL 300',300,400),('USI-CIVIL 350',350,500),('ASTM A572 Gr.50',345,450)]:
   m=material(name);self.assertEqual(m['properties']['fy_MPa'],fy);self.assertEqual(m['properties']['fu_MPa'],fu)
 def test_custom(self):
  self.assertEqual(material('Personalizado',{'fy_MPa':280,'fu_MPa':420})['properties']['fy_MPa'],280)
  for v in [None,{'fy_MPa':float('nan'),'fu_MPa':400},{'fy_MPa':True,'fu_MPa':400},{'fy_MPa':500,'fu_MPa':400}]:
   with self.assertRaises(ValueError):material('Personalizado',v)
 def test_no_input_mutation(self):
  d={'properties':{'fy_MPa':None}};out=apply_material(d,'ASTM A36');self.assertIsNone(d['properties']['fy_MPa']);self.assertEqual(out['properties']['fy_MPa'],250)
if __name__=='__main__':unittest.main()
