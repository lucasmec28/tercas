"""Fresh optional calculation failures must not be labelled as legacy data."""
import copy

from docx import Document

from tercas import isolated_en_ui as ui


ERROR = 'Seções efetivas EN fora da referência resistente M–V qualificada.'


def evidence(*, error=ERROR):
    web = {
        'web_shear': {'index_upper': .0036, 'status': 'meets'},
        'no_web_shear_reduction': {'status': 'pending'},
    }
    if error is not None:
        web['bending_shear_error'] = error
    return {
        'configuration': {'model_origin': 'Synthetic presentation QA'},
        'computed_cases': 1, 'pending_cases': 0, 'ELS_cases_excluded': 1,
        'records': [{'combination_id': 'ELU', 'check': {
            'criteria': {}, 'section_stress_criteria_sufficiently_satisfied': True,
        }, 'web_shear_component': web}],
        'source_torsion_snapshot_sha256': 'a' * 64,
    }


def test_fresh_error_is_pending_not_historical_and_does_not_claim_weak_shear():
    ev = evidence(); before = copy.deepcopy(ev)
    row = ui.rows(ev)[0]; text = '\n'.join(ui.text_lines(ev))
    assert row['M–V adicional EN6.27'] == 'Pendente no cálculo salvo'
    assert row['Redução adicional por V EN'] == 'Pendente: cálculo EN6.27 indisponível'
    assert row['Motivo'] == ERROR
    assert row['Teto M–V adicional EN6.27'] is None
    assert row['Teto dos dois cortantes EN'] is None
    assert row['Teto cortante transversal da alma EN'] == .0036
    assert ERROR in text and 'EN6.27 pendente em 1 caso do cálculo salvo' in text
    assert 'Registro histórico' not in text
    assert 'duas mesas originais' not in text
    assert ev == before


def test_legacy_without_attempt_still_has_legacy_label():
    ev = evidence(error=None)
    assert ui.rows(ev)[0]['M–V adicional EN6.27'] == 'Sem registro adicional'
    assert 'Registro histórico restrito à alma' in '\n'.join(ui.text_lines(ev))
    assert 'EN6.27 pendente em' not in '\n'.join(ui.text_lines(ev))


def test_mixed_records_report_current_failure_and_preserve_legacy_separately():
    ev = evidence()
    ev['records'].append(evidence(error=None)['records'][0])
    text = '\n'.join(ui.text_lines(ev))
    assert 'EN6.27 pendente em 1 caso do cálculo salvo' in text
    assert 'Registro histórico restrito à alma' in text
    assert ERROR in text


def test_word_preserves_error_without_recalculation(monkeypatch):
    ev = evidence(); before = copy.deepcopy(ev)
    monkeypatch.setattr(ui.a, 'preserved', lambda result: ev)
    doc = Document(); ui.report(doc, {})
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert ERROR in text and 'Pendente no cálculo salvo' in text
    assert 'Registro histórico restrito à alma' not in text
    assert ev == before
