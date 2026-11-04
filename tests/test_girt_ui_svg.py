"""UI/SVG-only tests; no independent qualification of backend mechanics."""
import copy,math,xml.etree.ElementTree as ET
import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tercas.application import defaults
from tercas.drawing import svg
from tercas.member_application import is_girt
from tercas import deflection_scope as scope
APP=str(Path(__file__).resolve().parents[1]/'app.py')
def select(a,label):return next(x for x in a.selectbox if x.label==label)
def number(a,prefix):return next(x for x in a.number_input if x.label.startswith(prefix))
def test_legacy_drawing_and_girt_orientation():
 d=defaults(19);assert not is_girt(d)
 d['inclination']={'value':23.,'unit':'degrees'};p=svg(d)
 assert 'rotate(23 ' in p and 'data-member-application="wall_girt"' not in p
 d['member_application']='wall_girt';frozen=copy.deepcopy(d);s=svg(d)
 root=ET.fromstring(s);ns={'s':'http://www.w3.org/2000/svg'}
 group=root.find('.//s:g[@id="section-oriented"]',ns)
 assert group.attrib['transform'].startswith('rotate(90 ')
 assert root.find('.//s:path[@id="normal-positive"]',ns).attrib['data-direction']=='left'
 assert root.find('.//s:path[@id="parallel-positive"]',ns).attrib['data-direction']=='down'
 assert 'Boca ↓' in s and 'plano forte rebatido' in s and 'superior do referencial = direita física' in s
 assert d==frozen
 d['member_application']='bad'
 try:svg(d)
 except (ValueError,TypeError):pass
 else:raise AssertionError('invalid application silently accepted')
def test_switch_preserves_roof_values_and_warns():
 a=AppTest.from_file(APP).run(timeout=30);assert not a.exception
 number(a,'Inclinação').set_value(23.).run(timeout=30)
 a.radio[0].set_value('Cargas por área e combinações automáticas').run(timeout=30)
 number(a,'Sobrecarga').set_value(77.).run(timeout=30)
 select(a,'Aplicação do elemento').set_value('wall_girt').run(timeout=30)
 assert not a.exception
 d=a.session_state.last_input
 assert d['inclination']['value']==23 and d['area_inputs']['live_kgf_m2']==77
 assert not any(n.label.startswith('Inclinação') or n.label.startswith('Sobrecarga') for n in a.number_input)
 assert any('INATIVAS' in w.value and '77' in w.value for w in a.warning)
 assert any('reinterpretação' in w.value for w in a.warning)
 assert number(a,'Distância entre travessas')
 assert not d['wall_tie_study']['enabled'] and not d['wall_tie_study']['springs']
 select(a,'Aplicação do elemento').set_value('purlin').run(timeout=30)
 assert not a.exception
 assert number(a,'Inclinação').value==23 and number(a,'Sobrecarga').value==77
 assert 'wall_els' in a.session_state.last_input

def test_girt_lengths_distinct_and_direct_preserved():
 a=AppTest.from_file(APP).run(timeout=30)
 number(a,'q paralelo ELU').set_value(.7).run(timeout=30)
 select(a,'Aplicação do elemento').set_value('wall_girt').run(timeout=30)
 d=copy.deepcopy(a.session_state.last_input);assert d['q_parallel_uls']==.7
 number(a,'Lref ELS vertical').set_value(1234.).run(timeout=30)
 z=a.session_state.last_input
 assert z['L_mm']==d['L_mm'] and z['segments']==d['segments'] and z['wall_els']['vertical_reference_mm']==1234
 assert number(a,'q vertical ELU').value==.7
 assert z['wall_tie_study']==dict(enabled=False,anchorage_confirmed=False,origin='',springs=[])
 next(c for c in a.checkbox if c.label=='Ativar estudo elástico bruto de molas verticais').check().run(timeout=30)
 assert not a.exception
 assert not a.session_state.last_input['wall_tie_study']['anchorage_confirmed']
 assert any('não resistência nem aprovação' in w.value for w in a.warning)

def test_invalid_application_stops_ui():
 a=AppTest.from_file(APP);d=defaults();d['member_application']='invalid'
 a.session_state.base=d;a.run(timeout=30)
 assert not a.exception
 assert any('Aplicação inválida' in e.value for e in a.error)
 assert not any(b.label=='Calcular verificações disponíveis' for b in a.button)

@pytest.mark.parametrize('uniaxial',[True,False])
def test_girt_area_calculation_preview_and_evidence(uniaxial):
 a=AppTest.from_file(APP).run(timeout=30)
 assert not next(c for c in a.checkbox if c.label==scope.LABEL).value
 if uniaxial:
  next(c for c in a.checkbox if c.label==scope.LABEL).check().run(timeout=30)
 select(a,'Aplicação do elemento').set_value('wall_girt').run(timeout=30)
 a.radio[0].set_value('Cargas por área e combinações automáticas').run(timeout=30)
 a.multiselect[0].set_value(['ELS rara']).run(timeout=30)
 number(a,'Vento sucção').set_value(60.).run(timeout=30)
 next(b for b in a.button if b.label=='Calcular verificações disponíveis').click().run(timeout=120)
 assert not a.exception
 r=a.session_state.result
 assert r['input_data']['member_application']=='wall_girt'
 assert not r['whole_member_approved']
 assert all(c['combination']['P_N']==0 and 'SC' not in c['combination']['coefficients'] for c in r['cases'])
 # Explicitly choosing the uniaxial scope omits the gross vertical diagnostic.
 # The omitted choice retains it; neither choice removes
 # actual vertical actions or qualifies a full ELS conclusion.
 data=r['input_data']; g=9.80665/1000.
 for case in r['cases']:
  c=case['combination']; factors=c['coefficients']
  expected_vertical=(factors.get('PP',0.)*data['properties']['mass_kg_m']*g+
                     factors.get('CP',0.)*data['area_inputs']['permanent_kgf_m2']*
                     data['area_inputs']['spacing_m']*g)
  assert c['q_vector']['parallel']==pytest.approx(expected_vertical)
 assert any(c['combination']['q_vector']['parallel']>0 for c in r['cases'])
 assert all(('elastic_vertical' in c['evidence']) is (not uniaxial) for c in r['cases'])
 if uniaxial:
  assert all(c['evidence']['ELS']['local_uniaxial_component']['displacement_axis']=='local_normal_horizontal' for c in r['cases'])
  assert any(row['Verificação']==scope.GIRT_ROW for c in r['cases'] for row in c['rows'])
  assert not any('Flecha vertical' in row['Verificação'] for c in r['cases'] for row in c['rows'])
  assert r['combined_ELS_approved'] is False
 else:
  assert scope.FIELD not in data
  assert any('Flecha vertical' in row['Verificação'] and row['Índice'] is None for c in r['cases'] for row in c['rows'])
 assert r['global_verification']['by_limit_state']['ELS']['status']!='aprovado'
 assert len(a.get('download_button'))==3
 # Changing application invalidates all previously computed results, including exports.
 select(a,'Aplicação do elemento').set_value('purlin').run(timeout=30)
 assert not a.exception
 assert 'result' not in a.session_state
 assert len(a.get('download_button'))==0
