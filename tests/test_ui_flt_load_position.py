import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class FLTLoadPositionUI(unittest.TestCase):
 def test_domain_option_and_round_trip_preserve_pending(self):
  app=str(Path(__file__).resolve().parents[1]/'app.py')
  a=AppTest.from_file(app).run(timeout=30)
  self.assertFalse(a.exception)
  select=next(x for x in a.selectbox if x.label=='Domínio da expressão de Me nesta emissão')
  self.assertEqual(select.options,['Não informado / outra situação','Eixo forte de simetria; cargas no CT ou estabilizantes, sem torção primária'])
  self.assertEqual(select.value,'Não informado / outra situação')
  self.assertTrue(any('Não exclui o giro do modo de FLT' in x.value for x in a.caption))
  a.button[0].click().run(timeout=30)
  a.button[1].click().run(timeout=30)
  self.assertFalse(a.exception)
  self.assertTrue(a.session_state.result['input_data']['route_domain'])
  self.assertIn('index',a.session_state.result['FLT_segments'][0])
  select=next(x for x in a.selectbox if x.label=='Domínio da expressão de Me nesta emissão')
  select.set_value('Não informado / outra situação').run(timeout=30)
  self.assertNotIn('result',a.session_state)
  a.button[1].click().run(timeout=30)
  self.assertFalse(a.exception)
  self.assertFalse(a.session_state.result['input_data']['route_domain'])
  f=a.session_state.result['FLT_segments'][0]
  self.assertNotIn('index',f)
  select=next(x for x in a.selectbox if x.label=='Domínio da expressão de Me nesta emissão')
  select.set_value(select.options[1]).run(timeout=30)
  self.assertNotIn('result',a.session_state)
  a.button[1].click().run(timeout=30)
  self.assertFalse(a.exception)
  self.assertTrue(a.session_state.result['input_data']['route_domain'])
  self.assertIn('index',a.session_state.result['FLT_segments'][0])


if __name__=='__main__':unittest.main()
