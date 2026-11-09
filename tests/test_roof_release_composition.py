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
from tercas import deflection_scope, direct_self_weight, load_application_policy
from tercas import isolated_ct_torsion, ue_family_reference
from tercas.current_calculation_inputs import prepare
from tercas.pierin_ue_registry_ui import HISTORY
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


def assert_historical_own_result(result):
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
    assert_local_service_and_no_global_approval(result)


def assert_local_service_and_no_global_approval(result):
    summary = result['global_verification']
    checks = {item['id']: item for item in summary['checks']}
    local = result['ELS']['local_uniaxial_component']
    assert local['schema'] == deflection_scope.MODE
    assert local['bending_axis'] == 'local_X_strong'
    assert local['displacement_axis'] == 'local_normal_roof_vertical'
    assert local['parallel_actions_removed_from_strength'] is False
    assert result['ELS']['criterion_status'] == 'meets'
    assert result['ELS']['index'] > 0
    # This explicitly requested local objective does not require optional ELS.
    # No historical snapshot is migrated: both producer lanes record the scope.
    combined = checks['ELS:DIRECT_ELS:combined_ELS_scope']
    assert combined['status'] == 'not_applicable' and combined['index'] is None
    assert combined['trace']['criterion_scope'] == 'outside_requested_local_deflection_objective'
    assert not summary['pending_ids']
    assert result['whole_member_approved'] is False
    assert summary['whole_member_approved'] is False
    assert summary['approved_within_declared_checklist'] is False
    assert result['combined_ELS_approved'] is False


def assert_current_own_result(result, imported):
    assert result['input_data'] == prepare(imported)
    assert load_application_policy.active(result['input_data'])
    assert result['input_data'][roof.FIELD] == imported[roof.FIELD]
    assert not roof.enabled(result['input_data'])
    assert nbr.FIELD not in result and roof.preserved(result) is None
    # This is the frozen seven-profile family, not the 66-section consumer.
    own = result['ue_family_reference_evidence']
    expected = ue_family_reference.evidence(imported)
    assert own['global_criticals'] == expected['global_criticals']
    assert own['signed_scalar_capacities'] == expected['signed_scalar_capacities']
    assert own['reference_id'] == expected['reference_id']
    pp = result['direct_self_weight_evidence']
    assert pp['PP_application'] == pp['external_application'] == 'shear_center'
    assert pp['states'] == direct_self_weight.evidence(imported)['states']
    assert [pp['states'][s]['factor'] for s in ('uls', 'sls')] == [1.25, 1.0]
    assert result['inclination_evidence']['ELU']['q_vector']['parallel'] != 0
    checks = {item['id']: item for item in result['global_verification']['checks']}
    assert 'ELU:DIRECT_ELU:FLT_height' not in checks
    for key in ('ELU:DIRECT_ELU:FLT:1', 'ELU:DIRECT_ELU:biaxial'):
        assert checks[key]['status'] == 'meets'
        assert checks[key]['index'] > 0 and 'NBR14762' in checks[key]['source']
    assert checks['ELU:DIRECT_ELU:FLT:1']['index'] == result['FLT_segments'][0]['index']
    assert checks['ELU:DIRECT_ELU:biaxial']['index'] == result['inclination_evidence']['ELU']['biaxial']['governing']['index']
    assert en.preserved(result)['computed_cases'] == 1
    en.validate_saved_global(result)
    nbr.validate_saved_global(result)
    shear = checks['ELU:DIRECT_ELU:secondary_shear_scope']
    assert shear['status'] == 'meets' and shear['index'] is None and 'EN' in shear['source']
    # Exact zero demand at CT is applicability, never a torsional capacity.
    assert checks['torsion_warping'] == isolated_ct_torsion.record(result)
    assert checks['torsion_warping']['status'] == 'not_applicable'
    assert checks['torsion_warping']['index'] is None
    assert_local_service_and_no_global_approval(result)


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


@pytest.mark.parametrize('lane', ['historical_top', 'current_CT'])
def test_real_app_own_five_degrees_combines_all_scopes_and_replays(monkeypatch, lane):
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
    assert not app.exception and app.session_state.last_input == data
    if lane == 'historical_top':
        # Replay the unmarked producer lane without today's calculate click.
        historical = complete_result(calculate(data))
        assert not load_application_policy.active(historical['input_data'])
        app.session_state.result = copy.deepcopy(historical)
        app.run(timeout=60)
    else:
        button('Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    assert any(w.value == RELEASE_CAPTION for w in app.caption)
    result = copy.deepcopy(app.session_state.result)
    if lane == 'historical_top':
        assert result == historical
        assert_historical_own_result(result)
    else:
        assert_current_own_result(result, data)
        assert app.session_state[HISTORY][0]['last_input'] == data
    assert json.loads(downloads['Baixar estudo e resultados (JSON)']) == result
    doc = Document(io.BytesIO(downloads['Baixar memória parcial (Word)']))
    text = '\n'.join(p.text for p in doc.paragraphs)
    if lane == 'current_CT':
        from tercas.torsion_applicability import NO_TORSIONAL_DEMAND
        assert any(w.value == NO_TORSIONAL_DEMAND for w in app.info)
        assert NO_TORSIONAL_DEMAND in text
        assert 'Aplicabilidade da análise de primeira ordem não estabelecida' not in text
        assert 'Interpretação física: Adequação da primeira ordem não estabelecida' not in text
        # AISI has its own analysis. A CT proof for the NBR operator does not
        # remove its separate G8.1/H4 interpretation notice.
        assert 'Interpretação física G8.1/H4: Adequação da primeira ordem não estabelecida' in text
    else:
        assert 'Aplicabilidade da análise de primeira ordem não estabelecida' in text
    assert result['global_verification']['display_summary'] in text
    assert 'conclusão global fora do escopo' in text.lower()
    assert deflection_scope.TEXT in text
    assert result['input_fingerprint'] in text
    assert 'não conclui o estado limite completo' in text.lower()
    assert 'elu: aprovado' not in text.lower() and 'checklist declarado concluído' not in text.lower()
    def forbidden(*a, **k):
        raise AssertionError('A saved-result rerender must not calculate a new model')
    monkeypatch.setattr(roof, 'refined', forbidden)
    monkeypatch.setattr(nbr, 'flt_mse', forbidden)
    monkeypatch.setattr('tercas.direct_torsion.solve_member', forbidden)
    monkeypatch.setattr('tercas.application.evaluate', forbidden)
    monkeypatch.setattr('tercas.torsion_study.attach', forbidden)
    app.run(timeout=60)
    assert not app.exception and app.session_state.result == result
    assert app.session_state.last_input == (data if lane == 'historical_top' else prepare(data))
