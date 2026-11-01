"""Integration in isolated app copy: existing host + experimental page."""
import unittest,sys,types,copy
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tercas.application import defaults,calculate
ROOT=Path(__file__).resolve().parents[1]
class Integration(unittest.TestCase):
 def test_page_initial_and_calculation(self):
  a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();self.assertFalse(a.exception)
  next(x for x in a.button if x.label=='Abrir laboratório experimental').click().run();self.assertFalse(a.exception)
  next(x for x in a.button if x.label=='Calcular assinatura experimental').click().run();self.assertFalse(a.exception);self.assertFalse(a.error);r=a.session_state['tercas_fsm_lab_result'];self.assertIsNone(r['local_Mcr_kNm']);self.assertFalse(r['design_approved']);self.assertTrue(any(x.proto.label=='Exportar estudo experimental JSON' for x in a.get('download_button')))
 def test_host_span_preserved_open_and_compute(self):
  a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();next(x for x in a.number_input if 'Vão entre' in x.label).set_value(4321.).run();self.assertFalse(a.exception)
  next(x for x in a.button if x.label=='Abrir laboratório experimental').click().run();self.assertEqual(next(x.value for x in a.number_input if 'Vão entre' in x.label),4321.)
  next(x for x in a.button if x.label=='Calcular assinatura experimental').click().run();self.assertFalse(a.exception);self.assertEqual(next(x.value for x in a.number_input if 'Vão entre' in x.label),4321.)
 def test_real_host_result_and_lab_edits(self):
  a=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();a.button[0].click().run();next(x for x in a.number_input if 'Vão entre' in x.label).set_value(4321.).run();a.button[1].click().run();self.assertFalse(a.exception)
  previous=copy.deepcopy(a.session_state['result']);previous_input=copy.deepcopy(a.session_state['last_input'])
  next(x for x in a.button if x.label=='Abrir laboratório experimental').click().run();next(x for x in a.button if x.label=='Calcular assinatura experimental').click().run();self.assertFalse(a.exception)
  self.assertEqual(previous,a.session_state['result']);self.assertEqual(previous_input,a.session_state['last_input'])
  next(x for x in a.number_input if x.label=='Alma externa h [mm]').set_value(210.).run();self.assertFalse(a.exception);self.assertEqual(previous,a.session_state['result']);self.assertFalse(any(x.proto.label=='Exportar estudo experimental JSON' for x in a.get('download_button')))
 def test_real_host_loaded_no_collision(self):
  # Load actual host packages plus generic modules already occupied before import.
  import tercas.core,tercas.application,tercas.weak_axis
  old=sys.modules.get('core');sys.modules['core']=types.ModuleType('host_core')
  try:
   from experimental_fsm.app_integration.adapter import run
   q={'geometry':{'h_mm':50,'b_mm':25,'lip_mm':0,'t_mm':1.2},'E_MPa':200000,'nu':.3,'axis':'y','moment_sign':1,'mesh_n':2,'halfwaves_mm':[15,25,50]};r=run(q);self.assertFalse(r['design_approved']);self.assertEqual(sys.modules['core'].__name__,'host_core')
  finally:
   if old is None:sys.modules.pop('core',None)
   else:sys.modules['core']=old
 def test_host_inputs_result_preserved(self):
  src=f"""import sys\nsys.path.insert(0,{str(ROOT)!r})\nimport streamlit as st\nfrom tercas.application import defaults,example,calculate\nfrom experimental_fsm.app_integration.panel import render\nif 'base' not in st.session_state:st.session_state.base=example()\nif 'result' not in st.session_state:st.session_state.result=calculate(st.session_state.base)\nrender(st,'tercas_fsm_lab')\n"""
  a=AppTest.from_string(src,default_timeout=30).run();self.assertFalse(a.exception);base=copy.deepcopy(a.session_state['base']);result=copy.deepcopy(a.session_state['result']);a.button[0].click().run();self.assertFalse(a.exception);self.assertEqual(base,a.session_state['base']);self.assertEqual(result,a.session_state['result'])
if __name__=='__main__':unittest.main()
