"""Current calculations adopt CT without rewriting the historical domain choice."""
import copy
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tercas.application import example
from tercas.load_application_policy import active
from tercas.pierin_ue_registry_ui import HISTORY


class FLTLoadPositionUI(unittest.TestCase):
 def test_current_domain_without_selector_preserves_prior_study_and_invalidation(self):
  source=example();source['route_domain']=False
  app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'))
  app.session_state.base=copy.deepcopy(source);app.session_state.last_input=copy.deepcopy(source)
  app.run(timeout=30)
  self.assertFalse(app.exception)
  self.assertEqual(app.session_state.last_input['route_domain'],False)
  self.assertFalse(any(w.label=='Domínio da expressão de Me nesta emissão' for w in app.selectbox))
  before=copy.deepcopy(app.session_state.last_input)
  next(w for w in app.button if w.label=='Calcular verificações disponíveis').click().run(timeout=60)
  self.assertFalse(app.exception)
  result=copy.deepcopy(app.session_state.result)
  self.assertTrue(active(result['input_data']))
  self.assertFalse(result['input_data']['route_domain'])
  self.assertIn('index',result['FLT_segments'][0])
  self.assertEqual(app.session_state[HISTORY][0]['last_input'],before)
  app.run(timeout=30)
  self.assertFalse(app.exception);self.assertEqual(app.session_state.result,result)
  field=next(w for w in app.number_input if w.label=='q ELU [kN/m]')
  field.set_value(field.value+.1).run(timeout=30)
  self.assertNotIn('result',app.session_state)
  next(w for w in app.button if w.label=='Calcular verificações disponíveis').click().run(timeout=60)
  self.assertFalse(app.exception)
  self.assertIn('index',app.session_state.result['FLT_segments'][0])
  self.assertEqual(app.session_state[HISTORY][0]['last_input'],before)


if __name__=='__main__':unittest.main()
