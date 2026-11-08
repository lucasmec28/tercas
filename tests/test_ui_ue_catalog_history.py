"""Explicit contour adoption archives old studies; rendering never migrates them."""
import copy

import pytest

from tercas import load_application_policy as policy, ue_catalog_ui as ui
from tercas.application import defaults
from tercas.pierin_ue_registry_ui import HISTORY, DURABLE_KEYS


class Controls:
    def __init__(self, state, clicked):
        self.session_state=state;self.clicked=clicked;self.rerun_requested=False
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def expander(self,*args,**kwargs):return self
    def caption(self,*args,**kwargs):pass
    success=caption
    warning=caption
    error=caption
    def button(self,*args,**kwargs):return self.clicked
    def rerun(self):self.rerun_requested=True


@pytest.mark.parametrize('application',['purlin','wall_girt'])
@pytest.mark.parametrize('reapply',[False,True])
def test_explicit_contour_apply_or_reapply_archives_before_load(monkeypatch,application,reapply):
    data=defaults(0);data['member_application']=application
    if reapply:data[ui.FIELD]={'existing':'synthetic UI dispatch binding'}
    state=dict(base=copy.deepcopy(data),last_input=copy.deepcopy(data),revision=4,
        result={'saved':'unchanged original result'},catalog_scan_state={'rows':[{'old':True}]},
        custom_steel_draft={'fy':300.},three_girt_warping_result={'old network':True})
    before=copy.deepcopy(state)
    changed=policy.adopt(data);changed[ui.FIELD]={'new':'synthetic UI dispatch binding'}
    seen=[]
    def activate(current):
        assert policy.active(current)
        assert data==before['last_input']
        seen.append(copy.deepcopy(current))
        return copy.deepcopy(changed)
    monkeypatch.setattr(ui,'activate',activate)
    monkeypatch.setattr(ui,'validate',lambda current: True)
    def load(current):
        state['base']=copy.deepcopy(current);state['last_input']=copy.deepcopy(current)
        state['revision']+=1
        for key in ('result','catalog_scan_state','custom_steel_draft'):state.pop(key,None)
    controls=Controls(state,True)
    ui.render_choice(controls,data,'contour',load)
    assert len(seen)==1 and controls.rerun_requested
    assert state['base']==state['last_input']==changed
    assert 'result' not in state and 'catalog_scan_state' not in state
    assert state[HISTORY]==[{k:v for k,v in before.items() if k in DURABLE_KEYS}]
    assert state[HISTORY][0]['result']==before['result']
    assert data==before['last_input']


@pytest.mark.parametrize('reapply',[False,True])
def test_contour_render_without_apply_does_not_archive_or_adopt(monkeypatch,reapply):
    data=defaults(0)
    if reapply:data[ui.FIELD]={'existing':'synthetic UI dispatch binding'}
    state=dict(base=copy.deepcopy(data),last_input=copy.deepcopy(data),result={'saved':True})
    before=copy.deepcopy(state)
    monkeypatch.setattr(ui,'validate',lambda current: True)
    def forbidden(*args,**kwargs):pytest.fail('Render must not activate or load')
    monkeypatch.setattr(ui,'activate',forbidden)
    controls=Controls(state,False)
    ui.render_choice(controls,data,'contour',forbidden)
    assert state==before and data==before['last_input']
    assert HISTORY not in state and not controls.rerun_requested
