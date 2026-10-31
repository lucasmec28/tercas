import unittest,copy,json,math
from io import BytesIO
from docx import Document
from tercas.application import *
from tercas.report import word
from tercas.drawing import svg
class Tests(unittest.TestCase):
 def test_default_partial(self):
  r=calculate(defaults());self.assertFalse(r['whole_member_approved']);self.assertEqual(r['NBR_branches']['point']['status'],'not_applicable')
 def test_didactic_all(self):
  r=calculate(example());self.assertGreater(r['FLT_segments'][0]['index'],1);self.assertTrue(r['synthetic']);self.assertEqual(r['NBR_branches']['point']['force_N'],1500)
 def test_traceability(self):
  d=example();r=calculate(d);d['L_mm']=5;self.assertEqual(r['input_data']['L_mm'],3000);self.assertIn('sintético',r['input_snapshot']['selected_section']['fields']['fy_MPa']['origin'])
 def test_shear_result_units(self):
  r=calculate(example());row=next(x for x in rows(r) if x['Verificação']=='Cortante');self.assertAlmostEqual(row['Índice'],(0.30726527*3000/2+750)/r['section_checks']['shear']['VRd_N'])
 def test_negative_and_nan(self):
  for key,v in [('L_mm',-1),('x_uls',0),('q_uls',float('nan'))]:
   d=example();d[key]=v
   with self.assertRaises(ValueError):calculate(d)
 def test_geometry_cannot_change(self):
  d=example();d['properties']['h']=200
  with self.assertRaises(ValueError):calculate(d)
 def test_bad_radius(self):
  d=example();d['properties']['ri_mm']=-1
  with self.assertRaises(ValueError):calculate(d)
 def test_missing_material_retains_other_outputs(self):
  d=example();d['properties']['fy_MPa']=None;r=calculate(d);self.assertEqual(r['NBR_branches']['local']['status'],'not_evaluated');self.assertIn('deflection_mm',r['ELS'])
 def test_missing_lengths(self):
  d=example();d['segments'][0]['Lz_effective_mm']=None;r=calculate(d);self.assertEqual(r['FLT_segments'][0]['status'],'FLT_not_evaluated');self.assertEqual(r['NBR_branches']['local']['status'],'computed')
 def test_unsupported_domain(self):
  d=example();d['route_domain']=False;r=calculate(d);self.assertEqual(r['FLT_segments'][0]['status'],'route_domain_not_declared')
 def test_sls_sign_mixed_partial(self):
  d=example();d['q_sls']=-1;r=calculate(d);self.assertEqual(r['ELS']['status'],'invalid_or_outside_implemented_domain');self.assertIn('index',r['FLT_segments'][0])
 def test_load_factor_linearity(self):
  d=example();r=calculate(d);d['q_uls']*=2;d['P_uls']*=2;r2=calculate(d);self.assertAlmostEqual(r2['NBR_branches']['local']['index'],2*r['NBR_branches']['local']['index'])
 def test_report_is_explicit(self):
  r=calculate(example());doc=Document(BytesIO(word(r)));t='\n'.join(x.text for x in doc.paragraphs);self.assertIn('NÃO É APROVAÇÃO GLOBAL',t);self.assertIn('SINTÉTICOS',t)
 def test_json_roundtrip(self):
  d=json.loads(json.dumps(example()));self.assertEqual(fingerprint(d),fingerprint(example()));self.assertEqual(calculate(d)['version'],VERSION)
 def test_svg_no_user_markup(self):
  d=example();d['project']='<script>bad</script>';self.assertNotIn('script',svg(d));self.assertIn('1500',svg(d))
 def test_ue_without_mdist(self):
  d=defaults(1);d['properties'].update(example()['properties']);base=defaults(1)
  for k in ['h','bf','lip','t','A_cm2','Ix_cm4','Wx_cm3','Iy_cm4','mass_kg_m']:d['properties'][k]=base['properties'][k]
  d.update(Ml_Nmm=4e6,critical_origin='synthetic test');r=calculate(d);self.assertFalse(r['whole_member_approved'])
if __name__=='__main__':unittest.main()

class Robustness(unittest.TestCase):
 def test_bad_json_roots(self):
  for d in [None,[],1,'x']:
   with self.assertRaises(ValueError):build_spec(d)
 def test_missing_import_fields(self):
  for key in ['project','ELS_origin','properties','synthetic']:
   d=example();d.pop(key)
   with self.assertRaises(ValueError):build_spec(d)
 def test_empty_segments_visible(self):
  d=example();d['segments']=[];r=calculate(d);self.assertTrue(r['coverage_warnings'])
 def test_shear_lag_visible(self):
  d=example();d['L_mm']=1000;d['x_uls']=d['x_sls']=500;d['segments']=[];r=calculate(d)
  row=next(x for x in rows(r) if 'Shear lag' in x['Verificação']);self.assertEqual(row['Situação'],'Enquadramento pendente')
  t='\n'.join(p.text for p in Document(BytesIO(word(r))).paragraphs);self.assertIn('§9.4',str(rows(r)));self.assertIn('largura livre',t)
 def test_values_in_report(self):
  t='\n'.join(p.text for p in Document(BytesIO(word(calculate(example())))).paragraphs);self.assertIn('Resistência/limite',t);self.assertIn('mm em x=',t)

class Segments(unittest.TestCase):
 def test_malformed_segment(self):
  d=example();d['segments']=[{}]
  with self.assertRaises(ValueError):build_spec(d)
 def test_invalid_segment_export(self):
  d=example();d['segments'][0]['start_mm']=None;r=calculate(d);self.assertTrue(word(r))

class DrawingLoads(unittest.TestCase):
 def test_point_force_arrow_matches_sign(self):
  import xml.etree.ElementTree as ET
  for value,direction in [(1500,'down'),(-1500,'up'),(0,None)]:
   with self.subTest(P=value):
    d=example();d['P_uls']=value;root=ET.fromstring(svg(d))
    arrow=next((e for e in root.iter() if e.attrib.get('id')=='point-load-arrow'),None)
    if direction is None:self.assertIsNone(arrow)
    else:
     self.assertEqual(arrow.attrib['data-direction'],direction)
     self.assertIn('v55' if value>0 else 'v-55',arrow.attrib['d'])
