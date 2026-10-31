import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
APP=str(Path(__file__).resolve().parents[1]/'app.py')
class BatchUI(unittest.TestCase):
 def app(self):
  a=AppTest.from_file(APP).run(timeout=60);self.assertFalse(a.exception);return a
 def area(self):
  a=self.app();a.button[0].click().run(timeout=60);a.radio[0].set_value('Cargas por área e combinações automáticas').run(timeout=60);self.assertFalse(a.exception);return a
 def test_material_presets(self):
  a=self.app();next(s for s in a.selectbox if s.label=='Tipo de aço').set_value('USI-CIVIL 350').run(timeout=60);a.button[1].click().run(timeout=60);self.assertFalse(a.exception);self.assertEqual(a.session_state.result['input_data']['properties']['fy_MPa'],350)
 def test_custom_material(self):
  a=self.app();next(s for s in a.selectbox if s.label=='Tipo de aço').set_value('Personalizado').run(timeout=60);next(n for n in a.number_input if n.label.startswith('fy personalizado')).set_value(280.).run();a.button[1].click().run(timeout=60);self.assertFalse(a.exception);self.assertEqual(a.session_state.result['input_data']['properties']['fy_MPa'],280)
 def test_area_compute_and_invalidate(self):
  a=self.area();next(n for n in a.number_input if n.label.startswith('Vento para cima')).set_value(100.).run();a.button[1].click().run(timeout=120);self.assertFalse(a.exception);self.assertEqual(len(a.session_state.result['cases']),51);self.assertEqual(len(a.get('download_button')),3)
  a.multiselect[0].set_value(['ELS rara']).run(timeout=60);self.assertNotIn('result',a.session_state);a.button[1].click().run(timeout=120);self.assertEqual(len(a.session_state.result['cases']),9)
 def test_empty_selection_clears(self):
  a=self.area();a.button[1].click().run(timeout=120);a.multiselect[0].set_value([]).run();a.button[1].click().run(timeout=60);self.assertFalse(a.exception);self.assertNotIn('result',a.session_state);self.assertTrue(a.error)
 def test_mode_switch_clears(self):
  a=self.area();a.button[1].click().run(timeout=120);a.radio[0].set_value('Ações já combinadas (ELU e ELS)').run(timeout=60);self.assertFalse(a.exception);self.assertNotIn('result',a.session_state)
 def test_catalog_change_preserves_area(self):
  a=self.area();next(n for n in a.number_input if n.label.startswith('Carregamento permanente')).set_value(20.).run();a.selectbox[0].set_value(2).run(timeout=60);self.assertFalse(a.exception);self.assertEqual(next(n for n in a.number_input if n.label.startswith('Carregamento permanente')).value,20.)
 def test_modes_preserve_hidden_inputs(self):
  a=self.area();next(n for n in a.number_input if n.label.startswith('Carregamento permanente')).set_value(42.).run();a.multiselect[0].set_value(['ELS rara']).run()
  a.radio[0].set_value('Ações já combinadas (ELU e ELS)').run();next(n for n in a.number_input if n.label.startswith('q ELU')).set_value(2.3).run()
  a.radio[0].set_value('Cargas por área e combinações automáticas').run();self.assertEqual(next(n for n in a.number_input if n.label.startswith('Carregamento permanente')).value,42.);self.assertEqual(a.multiselect[0].value,['ELS rara'])
  a.radio[0].set_value('Ações já combinadas (ELU e ELS)').run();self.assertEqual(next(n for n in a.number_input if n.label.startswith('q ELU')).value,2.3)
if __name__=='__main__':unittest.main()
