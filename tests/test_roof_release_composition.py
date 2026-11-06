"""Fresh final composition checks, distinct from the workers' individual QA.

All loads are synthetic. A sufficient listed criterion is not member approval.
"""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from tercas import isolated_en_application as en
from tercas import isolated_en_ue_catalog_application as catalog_en
from tercas import roof_top_nbr as nbr, roof_top_load as roof
from tercas import deflection_scope
from tercas.application import calculate
from tercas.study_completion import complete_result
from tercas.release_info import RELEASE_CAPTION
from test_roof_biaxial import inputs as own_inputs
from en_ue_test_helpers import inputs as catalog_inputs


def own_declared():
    data = own_inputs(t=2., angle=5.)
    data[deflection_scope.FIELD] = deflection_scope.MODE
    data[en.CHOICE] = en.choice(data, declared=True, origin='Synthetic intact model for final release QA')
    return data


def assert_own_result(result):
    ev = nbr.preserved(result)
    row = ev['records'][0]
    assert row['index'] == pytest.approx(.2637128303218076, rel=2e-12)
    assert row['biaxial']['governing']['index'] == pytest.approx(.2703624348153767, rel=2e-12)
    assert en.preserved(result)['computed_cases'] == 1
    en.validate_saved_global(result)
    nbr.validate_saved_global(result)
    summary = result['global_verification']
    checks = {item['id']: item for item in summary['checks']}
    for key in ('ELU:DIRECT_ELU:FLT_height', 'ELU:DIRECT_ELU:biaxial',
                'ELU:DIRECT_ELU:secondary_shear_scope', 'torsion_warping'):
        assert checks[key]['status'] == 'meets'
    for key in ('ELU:DIRECT_ELU:secondary_shear_scope', 'torsion_warping'):
        assert checks[key]['index'] is None
        assert 'EN' in checks[key]['source']
    assert set(summary['pending_ids']) == {'ELS:DIRECT_ELS:combined_ELS_scope'}
    assert result['whole_member_approved'] is False
    assert summary['whole_member_approved'] is False
    assert summary['approved_within_declared_checklist'] is False
    assert result['combined_ELS_approved'] is False


@pytest.mark.parametrize('angle', [5., -5.])
def test_catalog_parallel_load_stays_partial_without_breaking_independent_EN(angle):
    data = catalog_inputs(0, angle=angle)
    data[catalog_en.CHOICE] = catalog_en.choice(data, declared=True, origin='Synthetic catalogue QA')
    result = complete_result(calculate(data))
    ev = catalog_en.preserved(result)
    assert ev['shear_computed_cases'] == 1
    assert ev['records'][0]['check']['shear']['weak_ratio_upper'] > 0
    assert result['whole_member_approved'] is False
    assert nbr.preserved(result)['computed_cases'] == 0
    assert all('biaxial' not in row for row in result[nbr.FIELD]['records'])
    assert en.FIELD not in result
    assert result['global_verification']['approved_within_declared_checklist'] is False
    assert next(c for c in result['global_verification']['checks'] if c['id'] == 'torsion_warping')['status'] == 'pending'


def test_real_app_own_five_degrees_combines_all_scopes_and_replays(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    data = own_declared()
    payload = json.dumps(data).encode()
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **k: SimpleNamespace(size=len(payload), getvalue=lambda: payload))
    downloads = {}
    original = st.download_button
    def capture(label, value, *a, **k):
        if label in ('Baixar estudo e resultados (JSON)', 'Baixar memória parcial (Word)'):
            downloads[label] = value
        return original(label, value, *a, **k)
    monkeypatch.setattr(st, 'download_button', capture)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=30)
    button = lambda label: next(w for w in app.button if w.label == label)
    button('Aplicar entradas do arquivo').click().run(timeout=30)
    button('Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    assert any(w.value == RELEASE_CAPTION for w in app.caption)
    result = copy.deepcopy(app.session_state.result)
    assert_own_result(result)
    assert json.loads(downloads['Baixar estudo e resultados (JSON)']) == result
    doc = Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert result['global_verification']['display_summary'] in text
    assert 'não constituem aprovação global' in text.lower()
    assert 'não conclui o estado limite completo' in text.lower()
    assert 'elu: aprovado' not in text.lower() and 'checklist declarado concluído' not in text.lower()
    def forbidden(*a, **k):
        raise AssertionError('A saved-result rerender must not calculate a new model')
    monkeypatch.setattr(roof, 'refined', forbidden)
    monkeypatch.setattr(nbr, 'flt_mse', forbidden)
    monkeypatch.setattr('tercas.direct_torsion.solve_member', forbidden)
    app.run(timeout=60)
    assert not app.exception and app.session_state.result == result
    assert app.session_state.last_input == data
