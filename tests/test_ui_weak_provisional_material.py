"""Explicit replacement of a provisional critical is not physical validation."""
import copy
from pathlib import Path
from streamlit.testing.v1 import AppTest
from test_weak_provisional_material import configured

APP = str(Path(__file__).resolve().parents[1] / 'app.py')
SOURCE_KEY = 'weak_source_positive_0'
REPLACE_KEY = 'weak_replace_hypothesis_positive_0'


def app(data=None):
    d = configured() if data is None else copy.deepcopy(data)
    d['steel_name'] = 'Personalizado'
    d['properties'].update(E_MPa=100000., G_MPa=38500.)
    a = AppTest.from_file(APP)
    a.session_state['base'] = d
    a.session_state['last_input'] = copy.deepcopy(d)
    a.session_state['revision'] = 0
    a.run(timeout=30)
    assert not a.exception
    return a


def calculate(a):
    a.button[1].click().run(timeout=30)
    assert not a.exception
    assert not a.error
    return a.session_state['result']['inclination_evidence']['ELU']


def test_editing_source_alone_does_not_remove_provisional_status():
    a = app()
    a.text_input(key=SOURCE_KEY).set_value('SYNTHETIC manual E=100000, test only').run()
    assert a.session_state['last_input']['weak_axis']['positive']['provisional_hypothesis']
    assert calculate(a)['weak_axis_capacities']['positive']['status'] == 'not_evaluated'


def test_checkbox_without_replacing_legacy_origin_keeps_guard():
    a = app()
    a.checkbox(key=REPLACE_KEY).check().run()
    assert a.session_state['last_input']['weak_axis']['positive']['provisional_hypothesis']
    assert any('origem ainda identifica' in w.value for w in a.warning)
    assert calculate(a)['weak_axis_capacities']['positive']['status'] == 'not_evaluated'


def test_explicit_manual_replacement_survives_rerun_and_reload():
    a = app()
    a.checkbox(key=REPLACE_KEY).check().run()
    a.text_input(key=SOURCE_KEY).set_value('SYNTHETIC independent same-axis critical E=100000; not qualified').run()
    data = copy.deepcopy(a.session_state['last_input'])
    assert not data['weak_axis']['positive']['provisional_hypothesis']
    assert data['weak_axis']['positive']['Ml_Nmm'] == 910000.
    ev = calculate(a)
    assert ev['weak_axis_capacities']['positive']['status'] == 'computed_restricted'
    assert not a.session_state['result']['whole_member_approved']
    assert not ev['provisional_hypothesis']
    a.run()
    assert not a.session_state['last_input']['weak_axis']['positive']['provisional_hypothesis']
    b = app(data)
    assert not b.session_state['last_input']['weak_axis']['positive']['provisional_hypothesis']
    assert calculate(b)['weak_axis_capacities']['positive']['status'] == 'computed_restricted'


def test_empty_manual_origin_stays_pending():
    a = app()
    a.checkbox(key=REPLACE_KEY).check().run()
    a.text_input(key=SOURCE_KEY).set_value('').run()
    ev = calculate(a)
    assert ev['weak_axis_capacities']['positive']['status'] == 'not_evaluated'
