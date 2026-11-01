import copy,math,unittest,xml.etree.ElementTree as ET
from tercas.application import defaults,example
from tercas.drawing import svg
from tercas.inclination import angle,decompose
from tercas.inclination_adapter import direct_evidence
class SignedView(unittest.TestCase):
 def test_signed_rotations_and_global_gravity(self):
  for theta in [-5,0,5]:
   with self.subTest(theta=theta):
    d=defaults();d['inclination']={'value':theta,'unit':'degrees'};original=copy.deepcopy(d)
    root=ET.fromstring(svg(d));items={e.get('id'):e for e in root.iter() if e.get('id')}
    self.assertIn(f'rotate({theta} ',items['section-oriented'].get('transform'))
    self.assertIn(items['section-local-axes'],list(items['section-oriented']))
    self.assertNotIn(items['gravity-global'],list(items['section-oriented']))
    self.assertEqual(d,original)
 def test_force_signs(self):
  for value in [-5,0,5]:
   a=angle(value)['radians'];v=decompose(1,0,a);wind=decompose(0,-1,a)
   self.assertAlmostEqual(v['normal'],math.cos(a));self.assertAlmostEqual(v['parallel'],math.sin(a))
   self.assertEqual(wind,{'normal':-1,'parallel':0})
 def test_direct_not_rotated(self):
  d=example();d.update(q_uls=1.23,q_sls=.7,q_parallel_uls=-.4,q_parallel_sls=.2,P_parallel_uls=130,P_parallel_sls=-70)
  for value in [-5,0,5]:
   d['inclination']={'value':value,'unit':'degrees'};e=direct_evidence(d)
   self.assertEqual(e['ELU']['q_vector'],{'normal':1.23,'parallel':-.4})
   self.assertEqual(e['ELU']['P_vector']['parallel'],130)
   self.assertEqual(e['ELS']['q_vector'],{'normal':.7,'parallel':.2})
   self.assertIn('NÃO gira novamente',svg(d))
 def test_degrees_percent_same_svg(self):
  d=defaults();d['inclination']={'value':-5,'unit':'degrees'};a=svg(d)
  d['inclination']={'value':100*math.tan(math.radians(-5)),'unit':'percent'}
  self.assertEqual(a,svg(d))
 def test_ui_negative_angle_persists(self):
  from pathlib import Path
  from streamlit.testing.v1 import AppTest
  at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
  next(n for n in at.number_input if n.label=='Inclinação [°]').set_value(-5.).run(timeout=30)
  self.assertFalse(at.exception)
  self.assertTrue(any('data-angle-degrees="-5"' in x.value for x in at.markdown))
  next(x for x in at.selectbox if x.label=='Unidade de inclinação').set_value('Porcentagem').run(timeout=30)
  next(x for x in at.radio if x.label=='Forma de entrada').set_value('Cargas por área e combinações automáticas').run(timeout=30)
  next(x for x in at.selectbox if x.label=='Perfil de catálogo').set_value(1).run(timeout=30)
  self.assertFalse(at.exception)
  self.assertAlmostEqual(at.session_state.last_input['inclination']['value'],100*math.tan(math.radians(-5)))
  self.assertTrue(any('data-angle-degrees="-5"' in x.value for x in at.markdown))
