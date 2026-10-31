from pathlib import Path
import math
from streamlit.testing.v1 import AppTest
APP=str(Path(__file__).resolve().parents[1]/'app.py')
def test_units_keep_same_angle_and_ly_labels():
 a=AppTest.from_file(APP).run(timeout=30)
 next(n for n in a.number_input if n.label.startswith('Inclinação')).set_value(30.).run(timeout=30)
 next(n for n in a.selectbox if n.label=='Unidade de inclinação').set_value('Porcentagem').run(timeout=30)
 assert not a.exception
 assert math.isclose(a.session_state.last_input['inclination']['value'],100/math.sqrt(3),rel_tol=1e-9)
 assert any('Ly — mesa superior (menor inércia)' in n.label for n in a.number_input)
 next(n for n in a.selectbox if n.label=='Unidade de inclinação').set_value('Graus').run(timeout=30)
 assert math.isclose(a.session_state.last_input['inclination']['value'],30.,rel_tol=1e-9)
def test_inclined_area_calculates_but_not_approves_biaxial():
 a=AppTest.from_file(APP).run(timeout=30);a.button[0].click().run(timeout=30)
 a.radio[0].set_value('Cargas por área e combinações automáticas').run(timeout=30)
 next(n for n in a.number_input if n.label.startswith('Inclinação')).set_value(30.).run(timeout=30)
 a.multiselect[0].set_value(['ELS rara']).run(timeout=30)
 a.button[1].click().run(timeout=120)
 assert not a.exception
 r=a.session_state.result
 assert not r['whole_member_approved']
 assert any(c['evidence'].get('inclination') for c in r['cases'])
 assert len(a.get('download_button'))==3
 assert any('graus' in str(r['input_data']['inclination']) or r['input_data']['inclination']['unit']=='degrees' for _ in [0])
def test_direct_parallel_inputs_preserved_on_mode_switch():
 a=AppTest.from_file(APP).run(timeout=30)
 next(n for n in a.number_input if n.label.startswith('q paralelo ELU')).set_value(.7).run(timeout=30)
 a.radio[0].set_value('Cargas por área e combinações automáticas').run(timeout=30)
 a.radio[0].set_value('Ações já combinadas (ELU e ELS)').run(timeout=30)
 assert not a.exception
 assert a.session_state.last_input['q_parallel_uls']==.7
def test_default_rare_and_user_selection_preserved():
 a=AppTest.from_file(APP).run(timeout=30)
 a.radio[0].set_value('Cargas por área e combinações automáticas').run(timeout=30)
 assert a.multiselect[0].value==['ELU normal','ELS rara','ELS frequente']
 a.multiselect[0].set_value(['ELS quase permanente']).run(timeout=30)
 next(n for n in a.number_input if n.label.startswith('Inclinação')).set_value(12.).run(timeout=30)
 a.selectbox[0].set_value(1).run(timeout=30)
 assert a.multiselect[0].value==['ELS quase permanente']
 a.radio[0].set_value('Ações já combinadas (ELU e ELS)').run(timeout=30)
 a.radio[0].set_value('Cargas por área e combinações automáticas').run(timeout=30)
 assert a.multiselect[0].value==['ELS quase permanente']
 assert not a.exception
