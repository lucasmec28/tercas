import copy

import pytest

from tercas import torsion_material_ui as ui
from tercas.torsion_material import FIELD
from test_ui_torsion_nominal import prepared, button


@pytest.mark.parametrize('mutation', ['missing_fy', 'wrong_warning'])
def test_incomplete_or_inconsistent_saved_annex_does_not_break_app_or_downloads(monkeypatch, mutation):
    app = prepared(monkeypatch)
    button(app, 'Detalhar tensões desta combinação').click().run(timeout=60)
    assert not app.exception
    damaged = copy.deepcopy(app.session_state.result)
    envelope = next(iter(damaged[FIELD]['records'].values()))['material_envelope']
    if mutation == 'missing_fy':
        del envelope['fy_MPa']
    else:
        envelope['source_small_rotation_warning'] = not envelope['source_small_rotation_warning']
    before = copy.deepcopy(damaged)
    app.session_state.result = damaged
    def forbidden(*args, **kwargs):
        raise AssertionError('Rerun/export must not rebuild a saved nominal field')
    monkeypatch.setattr(ui, 'deepen', forbidden)
    app.run(timeout=30)
    assert not app.exception
    assert any('anexo nominal salvo é inválido' in item.value for item in app.error)
    labels = [item.label for item in app.get('download_button')]
    for label in ('Baixar memória parcial (Word)', 'Baixar estudo e resultados (JSON)', 'Baixar entradas (JSON)'):
        assert labels.count(label) == 1
    assert app.session_state.result == before
    assert app.session_state.result['global_verification']['whole_member_approved'] is False
