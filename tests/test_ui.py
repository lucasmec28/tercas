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
  at=self.run_app();self.assertIn('Terças',at.title[0].value);self.assertEqual(len(at.selectbox),4)
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
