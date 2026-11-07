"""Synthetic UI/transition tests. No calculation, solver or new authority."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tercas.application import defaults
from tercas.pierin_ue_registry_ui import HISTORY, PREFIX, DURABLE_KEYS, start, restore
from tercas.pierin_ue_registry import new_study_indices

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def widget(app, kind, label):
    return next(w for w in getattr(app, kind) if w.label == label)


def test_explicit_new_selector_has_66_and_browsing_preserves_open_inputs():
    app = AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    assert app.selectbox[0].label == 'Perfil de catálogo'
    before = copy.deepcopy(app.session_state.last_input)
    selector = widget(app, 'selectbox', 'Perfil Ue para novo estudo')
    assert len(selector.options) == 66
    selector.set_value(26).run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input == before
    assert widget(app, 'button', 'Iniciar novo estudo Ue').disabled
    assert HISTORY not in app.session_state
    assert any('dados tabulados completos' in c.value for c in app.caption)


def test_explicit_start_preserves_prior_study_and_can_restore():
    app = AppTest.from_file(APP).run(timeout=30)
    prior = copy.deepcopy(app.session_state.last_input)
    widget(app, 'selectbox', 'Perfil Ue para novo estudo').set_value(26).run(timeout=30)
    widget(app, 'checkbox', 'Confirmo iniciar outro estudo e preservar o atual nesta sessão').check().run(timeout=30)
    widget(app, 'button', 'Iniciar novo estudo Ue').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input['catalog_index'] == 26
    from tercas.direct_self_weight import FIELD, MODE
    assert app.session_state.last_input[FIELD] == MODE
    assert app.session_state.last_input['q_uls'] == 0
    assert app.session_state.last_input['load_mode'] == 'direct'
    assert app.session_state[HISTORY][0]['last_input'] == prior
    widget(app, 'button', 'Restaurar estudo preservado').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input == prior
    assert len(app.session_state[HISTORY]) == 2


def test_incomplete_import_preserved_in_inspection_and_not_in_new_options(monkeypatch):
    data = defaults(4)
    data.update(project='SINTÉTICO: legado incompleto', Ml_Nmm=None)
    data['weak_axis'] = {'positive': {'W_mm3': None, 'Cs': 1, 'provenance': 'Fonte sintética histórica'}}
    payload = json.dumps(data).encode()
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **kw: SimpleNamespace(size=len(payload), getvalue=lambda: payload))
    app = AppTest.from_file(APP).run(timeout=30)
    widget(app, 'button', 'Aplicar entradas do arquivo').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input == data
    assert app.session_state.base == data
    assert 4 not in new_study_indices()
    widget(app, 'selectbox', 'Perfil Ue para novo estudo').set_value(26).run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input == data
    assert app.session_state.base == data
    widget(app, 'checkbox', 'Confirmo iniciar outro estudo e preservar o atual nesta sessão').check().run(timeout=30)
    widget(app, 'button', 'Iniciar novo estudo Ue').click().run(timeout=30)
    assert not app.exception
    widget(app, 'button', 'Restaurar estudo preservado').click().run(timeout=30)
    assert not app.exception
    assert app.session_state.last_input == data
    assert app.session_state.base == data
    assert 'direct_load_basis' not in app.session_state.last_input


def test_transition_retains_results_inputs_and_durable_drafts_without_widget_writes():
    state = dict(base={'catalog_index': 4}, last_input={'catalog_index': 4}, revision=7,
                 result={'historical_result': 'synthetic only'}, custom_steel_draft={'fy': 250},
                 catalog_scan_state={'rows': [1]}, old_widget='draft', calculation_cache_epoch='same')
    original = copy.deepcopy(state)
    def load(new):
        state.update(base=new, last_input=copy.deepcopy(new), revision=8)
        for k in ('result', 'custom_steel_draft', 'catalog_scan_state'):
            state.pop(k, None)
    start(state, 26, lambda i: {'catalog_index': i}, lambda x: x, load)
    assert state[HISTORY][0] == {k:v for k,v in original.items() if k in DURABLE_KEYS}
    assert 'result' not in state
    restore(state, 0)
    assert {k:v for k,v in state.items() if k in DURABLE_KEYS} == {k:v for k,v in original.items() if k in DURABLE_KEYS}
    assert state['revision'] == 9
    assert 'old_widget' not in state[HISTORY][0]
    assert state[HISTORY][-1]['last_input'] == {'catalog_index': 26}


def test_revalidation_rejects_incomplete_without_touching_open_study():
    state = dict(base={'catalog_index': 26}, result={'synthetic': True})
    original = copy.deepcopy(state)
    with pytest.raises(ValueError, match='Incomplete'):
        start(state, 4, lambda i: pytest.fail('factory called'), lambda x: x,
              lambda x: pytest.fail('load called'))
    assert state == original


def test_invalid_restore_never_changes_state():
    state = {HISTORY: [{'base': {'catalog_index': 0}}], 'base': {'catalog_index': 26}}
    original = copy.deepcopy(state)
    for position in (-1, 10, True):
        with pytest.raises(ValueError):
            restore(state, position)
        assert state == original
