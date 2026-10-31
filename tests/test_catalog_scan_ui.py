from pathlib import Path
from streamlit.testing.v1 import AppTest
APP=str(Path(__file__).resolve().parents[1]/'app.py')

def button(a,label):return next(b for b in a.button if b.label==label)

def test_scan_explicit_cancel_and_input_invalidation():
 a=AppTest.from_file(APP).run(timeout=30)
 assert not a.exception
 assert 'catalog_scan_state' not in a.session_state
 button(a,'Calcular todas as seções do catálogo').click().run(timeout=30)
 assert not a.exception
 state=a.session_state.catalog_scan_state
 assert state['next_index']==1 and state['running']
 assert state['rows'][0]['whole_member_approved'] is False
 button(a,'Cancelar comparação').click().run(timeout=30)
 assert not a.exception
 state=a.session_state.catalog_scan_state
 assert state['cancelled'] and not state['running'] and state['next_index']==1
 # A normal rerun does not resume a cancelled scan.
 a.run(timeout=30)
 assert a.session_state.catalog_scan_state['next_index']==1
 next(n for n in a.number_input if n.key=='q_uls_0').set_value(.321).run(timeout=30)
 assert not a.exception
 assert 'catalog_scan_state' not in a.session_state

def test_custom_material_moduli_survive_profile_change():
 from tercas.application import defaults
 from tercas.catalog_scan import inputs_for_section
 d=defaults();d['steel_name']='Personalizado'
 d['properties'].update(E_MPa=190000.,G_MPa=73000.,fy_MPa=280.,fu_MPa=430.)
 a=AppTest.from_file(APP)
 a.session_state.base=d;a.session_state.revision=0
 a.run(timeout=30)
 assert not a.exception
 before=a.session_state.last_input
 a.selectbox[0].set_value(8).run(timeout=30)
 assert not a.exception
 after=a.session_state.last_input
 for key in ['E_MPa','G_MPa','fy_MPa','fu_MPa']:assert after['properties'][key]==before['properties'][key]==d['properties'][key]
 assert after['Ml_Nmm']==inputs_for_section(before,8)['Ml_Nmm']
