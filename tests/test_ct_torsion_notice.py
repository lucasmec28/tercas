"""Presentation only: one fresh synthetic case, then solver-free saved readers."""
import copy

import pytest
from docx import Document

from tercas import isolated_ct_torsion as ct
from tercas import torsion_applicability as notice
from test_torsion_applicability import Screen, no_solver


@pytest.fixture(scope='module')
def calculated():
    # This explicit synthetic setup is the only calculation in this module.
    from test_roof_release_composition import own_declared
    from tercas.application import calculate
    from tercas.current_calculation_inputs import prepare
    from tercas.study_completion import complete_result
    data = prepare(own_declared())
    data['synthetic'] = True
    return complete_result(calculate(data))


@pytest.fixture
def result(calculated):
    return copy.deepcopy(calculated)


def check(result, suffix):
    return next(r for r in result['global_verification']['checks']
                if r['id'] == suffix or r['id'].endswith(':'+suffix))


@pytest.fixture(autouse=True)
def no_extra_calculation(no_solver, monkeypatch):
    from tercas import application, torsion_study, direct_torsion, ltb_load_height
    from tercas.torsion_vlasov import adapter
    def forbidden(*args, **kwargs):
        pytest.fail('Saved CT presentation must not calculate or attach a result')
    for module, name in ((application, 'calculate'), (application, 'evaluate'),
                         (torsion_study, 'attach'), (direct_torsion, 'solve_member'),
                         (adapter, 'solve_member'), (ltb_load_height, 'refined')):
        monkeypatch.setattr(module, name, forbidden)


def test_current_CT_uses_only_existing_authenticated_zero_conclusion(result):
    before = copy.deepcopy(result)
    assert check(result, 'FLT:1')['status'] == 'meets'
    assert check(result, 'biaxial')['status'] == 'meets'
    assert check(result, 'torsion_warping') == ct.record(result)
    a = result['torsion_evidence']['records'][0]['analysis']
    assert any(r.get('torque_CG_N', 0) != 0 for r in a['loads'])
    assert a['field_envelopes']['T_CG_Nmm']['maximum_absolute']['value'] != 0
    record = notice.saved_notice(result)
    assert record['torsion_not_requested'] is True
    assert record['warning'] is False
    assert record['lines'][0] == notice.NO_TORSIONAL_DEMAND
    assert 'Distância geométrica' in record['lines'][1]
    assert any('sem apoio intermediário' in s for s in record['lines'])
    assert result == before
    assert result['whole_member_approved'] is False
    assert result['global_verification']['whole_member_approved'] is False


@pytest.mark.parametrize('suffix', ['FLT:1', 'biaxial', 'local', 'distortional', 'MV'])
@pytest.mark.parametrize('status', ['pending', 'fails'])
def test_other_criteria_keep_their_pending_or_failed_conclusion(result, suffix, status):
    # The text describes only authenticated torsional demand, not these criteria.
    row = check(result, suffix)
    row.update(status=status, reason='Synthetic saved criterion remains '+status)
    if status == 'pending': row['index'] = None
    else: row['index'] = 1.5
    before = copy.deepcopy(result)
    assert notice.saved_notice(result)['lines'][0] == notice.NO_TORSIONAL_DEMAND
    from tercas.report_audit import saved_issues
    issues = saved_issues(result)
    assert any('Synthetic saved criterion remains '+status in str(r) for r in issues)
    assert result == before


@pytest.mark.parametrize('mutation', ['no_panorama', 'old_panorama', 'no_policy',
    'unknown_policy', 'pending_proof', 'changed_proof', 'duplicate_proof', 'foreign_panorama',
    'non_CT', 'network_schema', 'B', 'Tsv', 'Tw', 'phi', 'torque_SC', 'missing_record'])
def test_historical_missing_or_nonzero_proof_keeps_original_warning(result, mutation):
    g = result['global_verification']
    a = result['torsion_evidence']['records'][0]['analysis']
    if mutation == 'no_panorama': result.pop('global_verification')
    elif mutation == 'old_panorama': result['global_verification'] = {'checks': []}
    elif mutation == 'no_policy': g.pop(ct.FIELD)
    elif mutation == 'unknown_policy': g[ct.FIELD] = 'unknown'
    elif mutation == 'pending_proof': check(result, 'torsion_warping')['status'] = 'pending'
    elif mutation == 'changed_proof': check(result, 'torsion_warping')['trace']['normative_exemption'] = True
    elif mutation == 'duplicate_proof': g['checks'].append(copy.deepcopy(check(result, 'torsion_warping')))
    elif mutation == 'foreign_panorama': g['source_input_fingerprint'] = 'other'
    elif mutation == 'non_CT': result['input_data'].pop('load_application_policy')
    elif mutation == 'network_schema': result['schema'] = 'tercas_three_girt_results_v1'
    elif mutation in ('B', 'Tsv', 'Tw'):
        field = 'B_Nmm2' if mutation == 'B' else mutation+'_Nmm'
        a['field_envelopes'][field]['maximum_absolute']['value'] = 1e-300
    elif mutation == 'phi': a['max_abs_phi']['phi_rad'] = 1e-300
    elif mutation == 'torque_SC': a['loads'][0]['torque_SC_N'] = 1e-300
    elif mutation == 'missing_record': result['torsion_evidence']['records'].pop()
    before = copy.deepcopy(result)
    out = notice.saved_notice(result)
    assert not out.get('torsion_not_requested')
    assert notice.NO_TORSIONAL_DEMAND not in out['lines']
    assert 'não estabelecida' in out['lines'][0] or 'inconsistente' in out['lines'][0]
    assert result == before


def test_large_rotation_and_inconsistent_aisi_still_warn(result):
    from test_torsion_applicability import saved_result
    large = saved_result(phi=.2)
    assert notice.saved_notice(large)['warning'] is True
    result['aisi_torsion_component'] = saved_result()['aisi_torsion_component']
    before = copy.deepcopy(result)
    out = notice.saved_notice(result)
    assert out['warning'] is True and 'inconsistente' in out['lines'][0]
    assert not out.get('torsion_not_requested') and result == before


def test_UI_and_Word_share_neutral_text_and_preserve_saved_numbers(result):
    from tercas.torsion_study_ui import report, show_result, summary_rows
    before = copy.deepcopy(result)
    screen = Screen()
    show_result(screen, result)
    assert ('info', notice.NO_TORSIONAL_DEMAND) in screen.events
    assert not any('Adequação da primeira ordem não estabelecida' in m for _, m in screen.events)
    doc = Document()
    report(doc, result)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert notice.NO_TORSIONAL_DEMAND in text
    assert 'Adequação da primeira ordem não estabelecida' not in text
    assert 'Aplicabilidade da análise de primeira ordem não estabelecida' not in text
    assert 'Giros elevados limitam a interpretação' in text
    historical_rows = summary_rows(result['torsion_evidence'])
    current_rows = summary_rows(result['torsion_evidence'], applicability=notice.saved_notice(result))
    for old, current in zip(historical_rows, current_rows):
        assert current.pop('Interpretação física') == notice.NO_TORSIONAL_DEMAND
        assert old.pop('Interpretação física') == 'Adequação da primeira ordem não estabelecida'
        assert current == old
    assert result == before
