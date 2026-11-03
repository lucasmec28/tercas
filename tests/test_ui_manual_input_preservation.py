"""Imported Annex E vectors remain an exact inspection, never a UI approval.

The fixture is a self-computed thin-wall rounded U100 reference, NOT Pierin's
historical vector, a certified product, or a qualified structural project.
No test clicks Calculate. Existing UI tests cover ordinary catalogue flows.
"""
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tercas.application import fingerprint, defaults
from tercas.weak_catalog import critical_hypothesis

ROOT = Path(__file__).resolve().parents[1]
APP = os.environ.get('TERCAS_UI_TEST_APP', str(ROOT / 'app.py'))
FIXTURE = Path(__file__).with_name('data') / 'u100_rounded_manual_inputs.json'


def manual():
    return json.loads(FIXTURE.read_text())


def button(app, label):
    return next(b for b in app.button if b.label == label)


def upload(monkeypatch, data):
    payload = json.dumps(data, ensure_ascii=False).encode()
    value = SimpleNamespace(size=len(payload), getvalue=lambda: payload)
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **kw: value)


def imported(monkeypatch, data=None):
    upload(monkeypatch, manual() if data is None else data)
    app = AppTest.from_file(APP).run(timeout=30)
    button(app, 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    return app


def assert_preserved(app, data):
    assert app.session_state.base == data
    assert app.session_state.last_input == data
    assert fingerprint(app.session_state.last_input) == fingerprint(data)
    assert 'result' not in app.session_state
    assert 'catalog_scan_state' not in app.session_state


@pytest.mark.parametrize('angle', [0., 5., -5.])
def test_import_preserves_every_field_and_fingerprint_without_calculating(monkeypatch, angle):
    data = manual()
    data['inclination']['value'] = angle
    app = imported(monkeypatch, data)
    assert_preserved(app, data)
    assert 'weak_catalog' not in app.session_state.last_input
    assert app.session_state.last_input['properties']['G_MPa'] == 200000. / 2.6


def test_manual_inspection_blocks_both_calculation_paths_and_offers_exact_export(monkeypatch):
    downloads = []
    original_download = st.download_button
    def record_download(label, data, *args, **kwargs):
        if label == 'Baixar entradas preservadas (JSON)':
            downloads.append(data)
        return original_download(label, data, *args, **kwargs)
    monkeypatch.setattr(st, 'download_button', record_download)
    app = imported(monkeypatch)
    assert downloads
    assert json.loads(downloads[-1]) == manual()
    assert fingerprint(json.loads(downloads[-1])) == fingerprint(manual())
    assert 'inspection_only' not in json.loads(downloads[-1])
    assert button(app, 'Calcular verificações disponíveis').disabled
    assert button(app, 'Calcular todas as seções do catálogo').disabled
    assert any('inspeção' in w.value and 'não edita' in w.value for w in app.warning)
    assert any('não comprova' in w.value for w in app.warning)
    assert not app.number_input
    assert len(app.get('download_button')) == 1
    assert app.get('download_button')[0].label == 'Baixar entradas preservadas (JSON)'
    assert json.loads(app.json[0].value) == manual()


def test_inspection_survives_repeated_reruns_and_reimports(monkeypatch):
    data = manual()
    app = imported(monkeypatch, data)
    for _ in range(3):
        app.run(timeout=30)
        assert_preserved(app, data)
        button(app, 'Aplicar entradas do arquivo').click().run(timeout=30)
        assert_preserved(app, data)


def test_bad_import_does_not_destroy_preserved_vector(monkeypatch):
    data = manual()
    app = imported(monkeypatch, data)
    upload(monkeypatch, [])
    app.run(timeout=30)
    button(app, 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    assert any('Arquivo não aplicado' in e.value for e in app.error)
    assert_preserved(app, data)


def test_profile_change_clears_section_vector_and_restores_normal_editor(monkeypatch):
    app = imported(monkeypatch)
    next(s for s in app.selectbox if s.label == 'Perfil de catálogo').set_value(0).run(timeout=30)
    assert not app.exception
    actual = app.session_state.last_input
    assert actual['catalog_index'] == 0
    assert actual['properties']['G_MPa'] == defaults(0)['properties']['G_MPa']
    assert actual['weak_catalog']['geometry_mode'] == 'catalog'
    assert actual['weak_axis']['positive']['Ml_Nmm'] == critical_hypothesis(0)['positive']['Ml_Nmm']
    assert 'W_mm3' not in actual['weak_axis']['positive']
    assert not button(app, 'Calcular verificações disponíveis').disabled
    assert not button(app, 'Calcular todas as seções do catálogo').disabled
    assert app.number_input


def test_example_can_leave_manual_inspection(monkeypatch):
    app = imported(monkeypatch)
    button(app, 'Carregar exemplo didático').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input['project'] == 'EXEMPLO DIDÁTICO — não é projeto'
    assert not button(app, 'Calcular verificações disponíveis').disabled
    assert 'W_mm3' not in app.session_state.last_input['weak_axis']['positive']


@pytest.mark.parametrize('mixed', [False, True])
def test_partial_or_ambiguous_manual_fields_are_not_silently_discarded(monkeypatch, mixed):
    data = manual()
    if mixed:
        data['weak_catalog'] = {'geometry_mode': 'catalog', 'Lx_mm': 2500.}
    else:
        data['weak_axis'] = {'positive': {'W_mm3': None, 'Cs': 1, 'provenance': 'Incomplete explicit source'}}
    app = imported(monkeypatch, data)
    assert_preserved(app, data)
    assert button(app, 'Calcular verificações disponíveis').disabled


def test_illegal_geometry_is_still_rejected_before_manual_inspection(monkeypatch):
    data = manual()
    data['properties']['h'] += 1.
    upload(monkeypatch, data)
    app = AppTest.from_file(APP).run(timeout=30)
    before = copy.deepcopy(app.session_state.last_input)
    button(app, 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    assert any('Geometria alterada' in e.value for e in app.error)
    assert app.session_state.last_input == before
    assert not button(app, 'Calcular verificações disponíveis').disabled


def test_nonmanual_json_reopens_regular_editor_on_same_profile(monkeypatch):
    app = imported(monkeypatch)
    regular = defaults(manual()['catalog_index'])
    upload(monkeypatch, regular)
    app.run(timeout=30)
    button(app, 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    assert app.number_input
    assert not button(app, 'Calcular verificações disponíveis').disabled
    assert app.session_state.last_input['properties']['G_MPa'] == regular['properties']['G_MPa']
    assert 'W_mm3' not in app.session_state.last_input['weak_axis']['positive']


def test_existing_result_and_catalog_scan_cannot_leak_into_inspection(monkeypatch):
    app = imported(monkeypatch)
    app.session_state['result'] = {'input_fingerprint': fingerprint(manual()), 'stale': True}
    app.session_state['catalog_scan_state'] = {'running': True, 'stale': True}
    app.run(timeout=30)
    assert not app.exception
    assert_preserved(app, manual())
    assert not app.get('dataframe')
    assert app.session_state.manual_result_history == {'input_fingerprint': fingerprint(manual()), 'stale': True}
    assert app.session_state.manual_catalog_history == {'running': True, 'stale': True}


def manual_inactive_3d(conflicting_material=False):
    from test_three_girt_system import ready
    data = ready()
    data['weak_axis'] = copy.deepcopy(manual()['weak_axis'])
    if not conflicting_material:
        data['properties']['G_MPa'] = 77000.
    return data


def test_3d_does_not_block_or_drop_inactive_manual_weak_fields(monkeypatch):
    data = manual_inactive_3d()
    app = imported(monkeypatch, data)
    assert app.session_state.last_input['weak_axis'] == data['weak_axis']
    assert app.session_state.last_input['properties'] == data['properties']
    assert not button(app, 'Calcular diagnóstico 3D').disabled
    assert button(app, 'Calcular todas as seções do catálogo').disabled
    assert not any('modo de inspeção' in w.value for w in app.warning)


def test_3d_material_conflict_is_reported_specifically_and_preserved(monkeypatch):
    data = manual_inactive_3d(conflicting_material=True)
    app = imported(monkeypatch, data)
    assert_preserved(app, data)
    assert button(app, 'Calcular diagnóstico 3D').disabled
    assert any('G_MPa' in w.value and 'não são o motivo' in w.value for w in app.warning)


@pytest.mark.parametrize('transition', ['disable_3d', 'return_roof'])
def test_leaving_3d_preserves_manual_weak_contract_before_resistance_editor(monkeypatch, transition):
    app = imported(monkeypatch, manual_inactive_3d())
    before = copy.deepcopy(app.session_state.last_input)
    if transition == 'disable_3d':
        next(c for c in app.checkbox if c.label.startswith('Analisar sistema 3D')).uncheck().run(timeout=30)
    else:
        next(s for s in app.selectbox if s.label == 'Aplicação do elemento').set_value('purlin').run(timeout=30)
    assert not app.exception
    assert button(app, 'Calcular verificações disponíveis').disabled
    after = copy.deepcopy(app.session_state.last_input)
    assert after['weak_axis'] == before['weak_axis']
    assert after['properties'] == before['properties']
    assert after['property_origin'] == before['property_origin']
    assert 'weak_catalog' not in after
    expected = copy.deepcopy(before)
    if transition == 'disable_3d':
        expected['three_girt_model']['enabled'] = False
    else:
        expected['member_application'] = 'purlin'
    assert after == expected
