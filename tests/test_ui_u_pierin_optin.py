import copy,json
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tercas.weak_u_assumption import FIELD
from test_u_pierin_optin import configured,opted,INDICES
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def app(d=None):
 d=configured() if d is None else d
 a=AppTest.from_file(APP);a.session_state['base']=copy.deepcopy(d);a.session_state['last_input']=copy.deepcopy(d);a.session_state['revision']=0;a.run(timeout=30)
 assert not a.exception
 return a

def data(a):return a.session_state['last_input']

def test_default_off_then_explicit_on_and_off_clears_generated_values():
 a=app();assert not a.checkbox(key='u_pierin_optin_0').value
 assert data(a)['weak_axis']['positive']['Ml_Nmm'] is None
 a.checkbox(key='u_pierin_optin_0').check().run();assert not a.exception
 assert data(a)['weak_axis']['positive'][FIELD]['acknowledged_as_inference'] is True
 assert data(a)['weak_axis']['negative']['Ml_Nmm'] is None
 assert any('hipótese de sentido inferida, pendente de confirmação' in x.value for x in a.warning)
 assert any('domínio fixo sem ligação de mesa a painel' in x.value for x in a.caption)
 a.checkbox(key='u_pierin_optin_0').uncheck().run();assert not a.exception
 p=data(a)['weak_axis']['positive'];assert FIELD not in p and p['Ml_Nmm'] is None and not p['provenance']

def test_optout_restores_manual_draft_not_generated_hypothesis():
 a=app();a.number_input(key='weak_positive_Ml_Nmm_0').set_value(1.23).run()
 a.text_input(key='weak_source_positive_0').set_value('SYNTHETIC manual draft, not verified').run()
 prior=copy.deepcopy(data(a)['weak_axis']['positive'])
 a.checkbox(key='u_pierin_optin_0').check().run();a.checkbox(key='u_pierin_optin_0').uncheck().run()
 assert not a.exception
 now=data(a)['weak_axis']['positive'];assert now['Ml_Nmm']==prior['Ml_Nmm'] and now['provenance']==prior['provenance']
 assert FIELD not in now and not now['provisional_hypothesis']

def test_imported_optin_is_visible_and_optout_without_draft_clears_it():
 a=app(json.loads(json.dumps(opted())));assert a.checkbox(key='u_pierin_optin_0').value
 assert any('Exploratório' in x.value for x in a.warning)
 a.checkbox(key='u_pierin_optin_0').uncheck().run();assert not a.exception
 assert data(a)['weak_axis']['positive']['Ml_Nmm'] is None
 assert FIELD not in data(a)['weak_axis']['positive']

def test_imported_value_tampering_is_not_silently_corrected():
 d=opted();d['weak_axis']['positive']['Ml_Nmm']=9e6;a=app(d)
 assert data(a)['weak_axis']['positive']['Ml_Nmm']==9e6
 assert any('diverge do valor oficial' in x.value for x in a.warning)
 next(b for b in a.button if b.label=='Calcular verificações disponíveis').click().run(timeout=30)
 assert not a.exception
 cap=a.session_state['result']['inclination_evidence']['ELU']['weak_axis_capacities']['positive']
 assert cap['status']=='not_evaluated' and 'MRd_Nmm' not in cap

def test_profile_change_drops_explicit_selection_even_to_another_covered_case():
 a=app(opted());a.selectbox(key='catalog_0').set_value(INDICES[-1]).run(timeout=30)
 assert not a.exception
 assert not a.checkbox(key='u_pierin_optin_1').value
 assert data(a)['weak_axis']['positive']['Ml_Nmm'] is None
 assert FIELD not in data(a)['weak_axis']['positive']

def test_optout_invalidates_prior_result_and_exports():
 a=app(opted());next(b for b in a.button if b.label=='Calcular verificações disponíveis').click().run(timeout=30)
 assert 'result' in a.session_state
 a.checkbox(key='u_pierin_optin_0').uncheck().run();assert not a.exception
 assert 'result' not in a.session_state
