import copy
from pathlib import Path
from streamlit.testing.v1 import AppTest
from test_three_girt_system import ready
from tercas.application import defaults
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def checkbox(a,prefix):return next(c for c in a.checkbox if c.label.startswith(prefix))
def button(a,prefix):return next(c for c in a.button if c.label.startswith(prefix))
def select(a,label):return next(c for c in a.selectbox if c.label==label)
def number(a,prefix):return next(c for c in a.number_input if c.label.startswith(prefix))


def test_ready_three_girt_ui_has_only_diagnostic_results():
 a=AppTest.from_file(APP);a.session_state.base=ready();a.run(timeout=30);assert not a.exception
 assert button(a,'Calcular todas').disabled
 assert not any(c.label.startswith('Ativar estudo elástico bruto de molas') for c in a.checkbox)
 assert not any(c.label=='Calcular verificações disponíveis' for c in a.button)
 button(a,'Calcular diagnóstico 3D').click().run(timeout=30);assert not a.exception
 result=copy.deepcopy(a.session_state.result);assert result['schema']=='tercas_three_girt_results_v1'
 assert not result['whole_member_approved'] and len(a.get('download_button'))==3
 assert any('SEM CONCLUSÃO' in x.value for x in a.error)
 assert not any('Resultados por verificação' in x.value for x in a.subheader)
 assert not any('Atende' in str(x.value) for x in a.dataframe)
 number(a,'Quantidade de linhas').set_value(3).run(timeout=30);assert not a.exception
 assert 'result' not in a.session_state and len(a.get('download_button'))==0
 button(a,'Calcular diagnóstico 3D').click().run(timeout=30);assert len(a.session_state.result['cases'][0]['model']['bars'])==8
 # Turning the system off restores stored spring/strength inputs, not its actions.
 checkbox(a,'Analisar sistema 3D').uncheck().run(timeout=30);assert not a.exception
 assert not button(a,'Calcular todas').disabled and button(a,'Calcular verificações disponíveis')
 assert 'result' not in a.session_state
 assert a.session_state.last_input['three_girt_model']['tie_count']==3


def test_missing_data_stays_blocked_and_old_projects_default_off():
 a=AppTest.from_file(APP);d=defaults();d['member_application']='wall_girt';a.session_state.base=d;a.run(timeout=30)
 assert not checkbox(a,'Analisar sistema 3D').value
 checkbox(a,'Analisar sistema 3D').check().run(timeout=30);assert not a.exception
 assert number(a,'Distância entre travessas')
 button(a,'Calcular diagnóstico 3D').click().run(timeout=30);assert not a.exception
 r=a.session_state.result;assert not r['cases'] and r['status']=='not_solved' and r['missing']
 assert len(a.get('download_button'))==3


def test_profile_switch_invalidates_section_coordinates():
 a=AppTest.from_file(APP);a.session_state.base=ready();a.run(timeout=30)
 button(a,'Calcular diagnóstico 3D').click().run(timeout=30);assert not a.exception
 index=a.session_state.last_input['catalog_index'];select(a,'Perfil de catálogo').set_value(index+1).run(timeout=30)
 assert not a.exception and 'result' not in a.session_state
 c=a.session_state.last_input['three_girt_model'];assert c['sc_y_mm'] is None and not c['connections_declared'] and not c['load_line_declared']
 assert c['tie_count']==2 and c['enabled']


def test_three_girt_area_and_return_to_roof_preserve_inputs():
 a=AppTest.from_file(APP);d=ready(True);d['inclination']={'value':23.,'unit':'degrees'};a.session_state.base=d;a.run(timeout=30)
 assert not a.exception
 assert len([n for n in a.number_input if n.label.startswith('Distância entre travessas')])==1
 assert any('telha/revestimento' in n.label and 'sem PP do perfil' in n.label for n in a.number_input)
 button(a,'Calcular diagnóstico 3D').click().run(timeout=60);assert not a.exception
 assert len(a.session_state.result['cases'])==19
 assert a.session_state.last_input['area_inputs']['live_kgf_m2']==888.
 select(a,'Aplicação do elemento').set_value('purlin').run(timeout=30);assert not a.exception
 assert 'result' not in a.session_state and button(a,'Calcular verificações disponíveis')
 assert a.session_state.last_input['inclination']['value']==23.
 assert a.session_state.last_input['three_girt_model']['enabled']
 select(a,'Aplicação do elemento').set_value('wall_girt').run(timeout=30);assert not a.exception
 assert checkbox(a,'Analisar sistema 3D').value and button(a,'Calcular diagnóstico 3D')
