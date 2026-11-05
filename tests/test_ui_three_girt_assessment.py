import copy
from streamlit.testing.v1 import AppTest
from test_three_girt_assessment import demand
from tercas.three_girt_assessment import ui
from tercas.three_girt_warping import network

SCRIPT='''
import streamlit as st
from tercas.three_girt_assessment.ui import render
render(st,st.session_state.demand)
'''

def run(app):
    app.run(timeout=60);assert not app.exception;return app


def test_inventory_explicit_readonly_button_and_cache(demand,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('UI inventory cannot solve')
    monkeypatch.setattr(network,'solve',forbidden)
    app=AppTest.from_string(SCRIPT);app.session_state.demand=copy.deepcopy(demand);run(app)
    assert ui.KEY not in app.session_state
    next(x for x in app.button if x.label==ui.LABEL).click();run(app)
    inventory=copy.deepcopy(app.session_state[ui.KEY]);assert inventory['whole_member_approved'] is False
    assert app.session_state.demand==demand
    monkeypatch.setattr(ui,'assess',forbidden);run(app)
    assert app.session_state[ui.KEY]==inventory
    app.session_state.demand['input_data']['project']='Changed source';run(app)
    assert ui.KEY not in app.session_state


def test_changed_sidecar_is_removed(demand):
    app=AppTest.from_string(SCRIPT);app.session_state.demand=demand;run(app)
    next(x for x in app.button if x.label==ui.LABEL).click();run(app)
    app.session_state[ui.KEY]['whole_member_approved']=True;run(app)
    assert ui.KEY not in app.session_state
    assert any('Panorama retirado' in w.value for w in app.warning)
