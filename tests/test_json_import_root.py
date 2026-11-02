"""Reject syntactically valid JSON scalars/arrays without breaking the study."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tercas.inclination_adapter import configuration
from tercas.application import build_spec, example

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


@pytest.mark.parametrize('value', [None, [], 'entrada', 0, True])
def test_configuration_rejects_non_object_root(value):
    with pytest.raises(ValueError, match='objeto de entradas JSON'):
        configuration(value)


def test_invalid_import_preserves_existing_study_and_result(monkeypatch):
    upload = SimpleNamespace(size=2, getvalue=lambda: b'[]')
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs: upload)
    app = AppTest.from_file(APP).run(timeout=30)
    next(b for b in app.button if b.label == 'Carregar exemplo didático').click().run(timeout=30)
    next(b for b in app.button if b.label == 'Calcular verificações disponíveis').click().run(timeout=30)
    before = copy.deepcopy(app.session_state.last_input)
    result_fingerprint = app.session_state.result['input_fingerprint']
    next(b for b in app.button if b.label == 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    assert any('Arquivo não aplicado: O arquivo deve conter um objeto de entradas JSON.' in e.value for e in app.error)
    assert app.session_state.last_input == before
    assert app.session_state.result['input_fingerprint'] == result_fingerprint
    assert len(app.get('download_button')) == 3


def test_exported_inputs_round_trip_without_silent_changes(monkeypatch):
    app = AppTest.from_file(APP).run(timeout=30)
    next(b for b in app.button if b.label == 'Carregar exemplo didático').click().run(timeout=30)
    before = copy.deepcopy(app.session_state.last_input)
    payload = json.dumps(before).encode()
    upload = SimpleNamespace(size=len(payload), getvalue=lambda: payload)
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs: upload)
    app.run(timeout=30)
    next(b for b in app.button if b.label == 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input == before
    assert 'result' not in app.session_state


def reopen(app, data, monkeypatch):
    payload = json.dumps(data).encode()
    upload = SimpleNamespace(size=len(payload), getvalue=lambda: payload)
    monkeypatch.setattr(st, 'file_uploader', lambda *args, **kwargs: upload)
    app.run(timeout=30)
    next(b for b in app.button if b.label == 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception


def custom_app():
    app = AppTest.from_file(APP).run(timeout=30)
    next(s for s in app.selectbox if s.label == 'Tipo de aço').set_value('Personalizado').run(timeout=30)
    next(w for w in app.text_input if w.label == 'Origem do aço personalizado').set_value('Certificado sintético QA; histórico livre').run(timeout=30)
    return app


def test_custom_steel_origin_survives_repeated_round_trips(monkeypatch):
    app = custom_app()
    before = copy.deepcopy(app.session_state.last_input)
    assert before['custom_steel_origin'] == 'Certificado sintético QA; histórico livre'
    for _ in range(3):
        reopen(app, copy.deepcopy(app.session_state.last_input), monkeypatch)
        assert app.session_state.last_input == before


def test_legacy_custom_origin_is_preserved_without_parsing_or_self_wrapping(monkeypatch):
    app = custom_app()
    legacy = copy.deepcopy(app.session_state.last_input)
    legacy.pop('custom_steel_origin')
    reopen(app, legacy, monkeypatch)
    loaded = copy.deepcopy(app.session_state.last_input)
    assert {k: loaded[k] for k in legacy} == legacy
    assert loaded['custom_steel_origin'] == legacy['property_origin']
    reopen(app, loaded, monkeypatch)
    assert app.session_state.last_input == loaded


def test_custom_origin_survives_profile_change_and_steel_toggle():
    app = custom_app()
    origin = app.session_state.last_input['custom_steel_origin']
    next(s for s in app.selectbox if s.label == 'Perfil de catálogo').set_value(8).run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input['custom_steel_origin'] == origin
    next(s for s in app.selectbox if s.label == 'Tipo de aço').set_value('ASTM A36').run(timeout=30)
    next(s for s in app.selectbox if s.label == 'Tipo de aço').set_value('Personalizado').run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input['custom_steel_origin'] == origin


def test_preset_export_does_not_restore_an_inactive_custom_certificate(monkeypatch):
    app = custom_app()
    next(w for w in app.number_input if w.label == 'fy personalizado [MPa]').set_value(320.).run(timeout=30)
    custom = copy.deepcopy(app.session_state.last_input)
    reopen(app, custom, monkeypatch)
    next(s for s in app.selectbox if s.label == 'Tipo de aço').set_value('ASTM A36').run(timeout=30)
    preset = copy.deepcopy(app.session_state.last_input)
    assert 'custom_steel_origin' not in preset
    assert preset['properties']['fy_MPa'] == 250.
    reopen(app, preset, monkeypatch)
    assert 'custom_steel_origin' not in app.session_state.last_input
    next(s for s in app.selectbox if s.label == 'Tipo de aço').set_value('Personalizado').run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input['properties']['fy_MPa'] == 250.
    assert app.session_state.last_input['custom_steel_origin'] == preset['property_origin']
    assert app.session_state.last_input['custom_steel_origin'] != custom['custom_steel_origin']


@pytest.mark.parametrize('origin', [None, [], 1, True, 'x' * 2001])
def test_optional_custom_origin_validates_type_and_limit(origin):
    data = example()
    data['custom_steel_origin'] = origin
    with pytest.raises(ValueError, match='custom_steel_origin'):
        build_spec(data)
