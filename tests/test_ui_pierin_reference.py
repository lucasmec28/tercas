import copy
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tercas.application import defaults
from test_pierin_official_reference import U
APP=str(Path(__file__).resolve().parents[1]/'app.py')
def test_U_official_reference_visible_without_silent_sense_assignment():
 d=defaults(U);a=AppTest.from_file(APP);a.session_state['base']=d;a.session_state['last_input']=copy.deepcopy(d);a.session_state['revision']=0;a.run(timeout=30)
 assert not a.exception
 assert any('referência oficial adotada' in x.value for x in a.markdown)
 assert any('Ml,y = 3,26' in x.value for x in a.caption)
 for sign in ['positive','negative']:assert a.session_state['last_input']['weak_axis'][sign]['Ml_Nmm'] is None

def test_Ue_keeps_value_but_explains_provisional_sense():
 a=AppTest.from_file(APP).run(timeout=30);assert not a.exception
 assert a.session_state['last_input']['weak_axis']['positive']['Ml_Nmm']==910000
 assert a.session_state['last_input']['weak_axis']['positive']['provisional_hypothesis']
 assert any('seu sentido aplicado é' in x.value for x in a.caption)
