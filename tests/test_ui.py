import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
APP=str(Path(__file__).resolve().parents[1]/'app.py')
class Tests(unittest.TestCase):
 def run_app(self):
  at=AppTest.from_file(APP).run(timeout=30);self.assertFalse(at.exception);return at
 def example(self):
  at=self.run_app();at.button[0].click().run(timeout=30);self.assertFalse(at.exception);return at
 def test_initial_render(self):
  at=self.run_app();self.assertIn('Terças',at.title[0].value)
  # New application selector is intentional; preserve the nine legacy controls.
  legacy=[x for x in at.selectbox if x.label!='Aplicação do elemento']
  self.assertEqual(len(legacy),9)
  application=[x for x in at.selectbox if x.label=='Aplicação do elemento']
  self.assertEqual(len(application),1);self.assertEqual(application[0].value,'purlin')
  self.assertEqual(application[0].options,['Terça de cobertura','Travessa lateral — boca para baixo'])
  self.assertNotIn('Cs — My positivo',[x.label for x in at.selectbox])
 def test_example_calculates_and_downloads(self):
  at=self.example();at.button[1].click().run(timeout=30);self.assertFalse(at.exception);self.assertIn('result',at.session_state);self.assertEqual(len(at.get('download_button')),3)
 def test_change_invalidates(self):
  at=self.example();at.button[1].click().run(timeout=30);next(x for x in at.number_input if 'Vão entre' in x.label).set_value(3100.).run(timeout=30);self.assertFalse(at.exception);self.assertNotIn('result',at.session_state);self.assertEqual(len(at.get('download_button')),0)
 def test_invalid_clears_results(self):
  at=self.example();at.button[1].click().run(timeout=30);next(x for x in at.number_input if 'Vão entre' in x.label).set_value(-1.).run(timeout=30);at.button[1].click().run(timeout=30);self.assertFalse(at.exception);self.assertNotIn('result',at.session_state);self.assertTrue(at.error)
 def test_switch_catalog_clears(self):
  at=self.example();at.button[1].click().run(timeout=30);at.selectbox[0].set_value(1).run(timeout=30);self.assertFalse(at.exception);self.assertNotIn('result',at.session_state)
 def test_repeat_calculate(self):
  at=self.example();at.button[1].click().run(timeout=30);fp=at.session_state.result['input_fingerprint'];at.button[1].click().run(timeout=30);self.assertFalse(at.exception);self.assertEqual(fp,at.session_state.result['input_fingerprint'])
if __name__=='__main__':unittest.main()


class SimplifiedInputs(unittest.TestCase):
 run_app=Tests.run_app
 example=Tests.example
 def test_portuguese_no_support_selection(self):
  at=self.run_app()
  labels=[x.label for x in at.selectbox]
  self.assertNotIn('Apoio esquerdo',labels);self.assertNotIn('Apoio direito',labels)
  cb=next(x for x in at.selectbox if x.label=='Coeficiente Cb')
  self.assertEqual(cb.options,['Adotar Cb = 1,0','Calcular pelos momentos do trecho'])
  self.assertFalse(at.get('data_editor'))
 def test_flange_inputs_and_span_auto(self):
  at=self.example()
  next(x for x in at.number_input if 'Vão entre' in x.label).set_value(4000.).run()
  next(x for x in at.number_input if 'mesa superior' in x.label).set_value(2000.).run()
  next(x for x in at.number_input if 'mesa inferior' in x.label).set_value(4000.).run()
  at.button[1].click().run(timeout=30)
  self.assertFalse(at.exception);s=at.session_state.result['input_data']['segments'][0]
  self.assertEqual((s['start_mm'],s['end_mm']),(0,4000));self.assertEqual(s['Ly_top_effective_mm'],2000);self.assertEqual(s['Ly_bottom_effective_mm'],4000)
 def test_lengths_invalidate_results(self):
  at=self.example();at.button[1].click().run(timeout=30)
  next(x for x in at.number_input if 'mesa inferior' in x.label).set_value(1500.).run()
  self.assertNotIn('result',at.session_state);self.assertFalse(at.get('download_button'))
 def test_advanced_mode_no_crash(self):
  at=self.example();at.checkbox[0].check().run(timeout=30)
  self.assertFalse(at.exception);at.button[1].click().run(timeout=30);self.assertFalse(at.exception)
 def test_custom_length_survives_span_and_mode(self):
  at=self.example()
  next(x for x in at.number_input if 'mesa superior' in x.label).set_value(1500.).run()
  next(x for x in at.number_input if 'Vão entre' in x.label).set_value(4000.).run()
  self.assertEqual(next(x for x in at.number_input if 'mesa superior' in x.label).value,1500.)
  at.checkbox[0].check().run();at.button[1].click().run(timeout=30)
  self.assertEqual(at.session_state.result['input_data']['segments'][0]['Ly_top_effective_mm'],1500.)
  at.checkbox[0].uncheck().run()
  self.assertEqual(next(x for x in at.number_input if 'mesa superior' in x.label).value,1500.)
 def test_auto_cb_short_length_has_visible_fallback(self):
  at=self.example()
  next(x for x in at.number_input if 'mesa superior' in x.label).set_value(1500.).run()
  next(x for x in at.selectbox if x.label=='Coeficiente Cb').set_value('Calcular pelos momentos do trecho').run()
  self.assertTrue(any('posição física' in x.value for x in at.warning))
  at.button[1].click().run(timeout=30)
  self.assertEqual(at.session_state.result['input_data']['segments'][0]['Cb_mode'],'one')
