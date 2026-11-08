"""Current controls, preserved JSON/history and click-only cache binding."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import streamlit as st
from streamlit.testing.v1 import AppTest

from tercas import load_application_policy as loads, support_scope as supports
from tercas.application import fingerprint
from tercas.pierin_ue_registry_ui import HISTORY

CONTROLS = '''
import copy
import streamlit as st
from tercas.current_calculation_inputs import prepare
from tercas.roof_top_load_ui import render_choice as roof
from tercas.torsion_study_ui import render_choice as torsion
from tercas.wall_girt_isolated import render_choice as girt
from tercas.direct_self_weight import render as direct_pp, MODE
if 'data' not in st.session_state:
    st.session_state.data={'ue_catalog_reference':{}, 'member_application':'wall_girt',
        'load_mode':'direct','direct_load_basis':MODE,
        'roof_top_load':{'enabled':True,'load_line':'web_midplane'},
        'torsion_model':{'load_lines':{'CP':{'xy_from_CG_mm':[12.,34.]}}}}
data=prepare(st.session_state.data)
roof(st,data,'roof');torsion(st,data,'torsion');girt(st,data,'girt');direct_pp(st,data,'pp')
'''


def test_no_load_line_controls_notes_or_mutation_for_current_model():
    app=AppTest.from_string(CONTROLS).run(timeout=30)
    assert not app.exception
    assert not app.checkbox and not app.selectbox and not app.number_input
    assert not app.warning and not app.info
    text='\n'.join(w.value for w in app.caption)
    assert '1,25 no ELU e 1,0 no ELS' in text
    assert 'no CG' not in text and 'topo' not in text and 'CT' not in text
    before=copy.deepcopy(app.session_state.data)
    app.run(timeout=30)
    assert not app.exception and app.session_state.data==before
    assert loads.FIELD not in before and supports.FIELD not in before


HISTORY_SCRIPT = '''
import copy,json
import streamlit as st
from tercas.application import fingerprint
from tercas.current_calculation_inputs import prepare,preserve_policy_choices,begin_calculation
from tercas.pierin_ue_registry_ui import restore,HISTORY
if 'base' not in st.session_state:
    st.session_state.base={'ue_catalog_reference':{},'project':'original'}
    st.session_state.last_input=copy.deepcopy(st.session_state.base)
    st.session_state.result={'input_data':copy.deepcopy(st.session_state.base),
        'input_fingerprint':fingerprint(st.session_state.base),'saved_numbers':[1.,2.]}
    st.session_state.revision=0
source=st.session_state.base
d=preserve_policy_choices(prepare(source),source)
st.session_state.last_input=copy.deepcopy(d)
if 'result' in st.session_state and st.session_state.result['input_fingerprint']!=fingerprint(d):
    st.session_state.pop('result')
if st.button('Calculate'):
    d=begin_calculation(st.session_state,d)
    st.session_state.result={'input_data':copy.deepcopy(d),'input_fingerprint':fingerprint(d),'saved_numbers':[3.,4.]}
if 'result' in st.session_state:
    st.json(st.session_state.result)
    st.download_button('Export saved',json.dumps(st.session_state.result),file_name='saved.json')
if HISTORY in st.session_state and st.button('Restore'):
    restore(st.session_state,0);st.rerun()
'''


def test_restore_export_then_recalculate_keeps_old_snapshot_and_current_cache(monkeypatch):
    downloads=[]
    original=st.download_button
    def capture(label,data,*args,**kwargs):
        if label=='Export saved':downloads.append(json.loads(data))
        return original(label,data,*args,**kwargs)
    monkeypatch.setattr(st,'download_button',capture)
    app=AppTest.from_string(HISTORY_SCRIPT).run(timeout=30)
    historical=copy.deepcopy(app.session_state.result)
    app.run(timeout=30)
    assert not app.exception and downloads[-1]==historical
    next(w for w in app.button if w.label=='Calculate').click().run(timeout=30)
    fresh=copy.deepcopy(app.session_state.result)
    assert loads.active(fresh['input_data']) and supports.enabled(fresh['input_data'])
    assert fresh['input_fingerprint']==fingerprint(app.session_state.last_input)
    assert app.session_state[HISTORY][0]['result']==historical
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==fresh
    next(w for w in app.button if w.label=='Restore').click().run(timeout=30)
    assert not app.exception and app.session_state.result==historical and downloads[-1]==historical
    assert loads.FIELD not in app.session_state.last_input
    next(w for w in app.button if w.label=='Calculate').click().run(timeout=30)
    app.run(timeout=30)
    assert not app.exception and app.session_state.result==fresh
    assert app.session_state[HISTORY][0]['result']==historical


def test_real_app_import_does_not_adopt_policies_or_expose_load_line_controls(monkeypatch):
    from tercas import ue_family_reference as family
    data=family.load_reference(1.5)
    before=copy.deepcopy(data);payload=json.dumps(data).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**kw:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=60)
    next(w for w in app.button if w.label=='Aplicar entradas do arquivo').click().run(timeout=60)
    assert not app.exception
    assert app.session_state.base==app.session_state.last_input==before
    labels=[w.label for kind in ('checkbox','selectbox','number_input') for w in getattr(app,kind)]
    assert 'Esquema da carga da cobertura' not in labels
    assert not any('Informar linha' in label or 'Declarar linha' in label for label in labels)
    app.run(timeout=60)
    assert not app.exception and app.session_state.last_input==before and data==before


class Recorder:
    """Deterministic controls only; no engine or numerical response is mocked."""
    def __init__(self):self.labels=[];self.messages=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def expander(self,label,**kwargs):self.labels.append(label);return self
    def columns(self,count):return [self]*count
    def caption(self,message):self.messages.append(message)
    warning=caption
    subheader=caption
    markdown=caption
    def checkbox(self,label,value=False,**kwargs):self.labels.append(label);return value
    def number_input(self,label,value=None,**kwargs):self.labels.append(label);return value
    def text_input(self,label,value='',**kwargs):self.labels.append(label);return value
    def selectbox(self,label,options,index=0,**kwargs):self.labels.append(label);return options[index]


def test_three_girt_controls_keep_real_connections_and_inactive_legacy_offsets():
    from tercas.three_girt_application import defaults
    from tercas.three_girt_ui import render_configuration
    from tercas.direct_self_weight import FIELD, MODE
    old=defaults();old.update(enabled=True,connection_mode='common_arm',
        connection_arm_mm=[0.,-38.,17.],load_y_from_CG_mm=127.,load_z_from_CG_mm=-93.,
        load_line_declared=False,sc_y_mm=-42.,sc_z_mm=0.,sc_origin='synthetic geometry only')
    source=dict(load_mode='direct',member_application='wall_girt',L_mm=6000.,
        area_inputs={'spacing_m':1.4},three_girt_model=old,**{FIELD:MODE})
    data=loads.adopt(source);before=copy.deepcopy(source);recorder=Recorder()
    def number(label,key,value,unit=''):recorder.labels.append(label);return value
    def text(label,key,value):recorder.labels.append(label);return value
    render_configuration(recorder,data,source,1,number,text)
    assert source==before
    assert data['three_girt_model']['connection_arm_mm']==[0.,-38.,17.]
    assert data['three_girt_model']['load_y_from_CG_mm']==127.
    assert data['three_girt_model']['load_z_from_CG_mm']==-93.
    assert data['three_girt_model']['load_line_declared'] is False
    assert 'Braço rígido Y' in recorder.labels and 'CG → centro de cisalhamento: componente Y' in recorder.labels
    assert not any('Linha das ações externas' in label or 'Declaro a linha das cargas' in label for label in recorder.labels)
    assert not any('PP da travessa atua sempre no CG' in text or 'PP no CG' in text for text in recorder.messages)
