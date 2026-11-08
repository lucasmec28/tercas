"""Synthetic presentation contracts and real pending authentication, no solves."""
import copy
from unittest.mock import patch
import pytest
from tercas import completion_service_evidence as e, completion_requirements as req
from tercas import isolated_service_component as c
from test_isolated_service_panorama import packet
from test_completion_requirements import source


def trusted_packet(monkeypatch, **kwargs):
    result = packet(**kwargs)
    ev = result[c.FIELD]
    ev['records'][0]['reason'] = ''
    ev['inventory'][0]['limit_mm'] = 20.
    calc = ev['records'][0]['comparison']
    calc['schema'] = c.mechanics.SCHEMA
    calc['envelope']['witness'] = {'station_mm': 1500.}
    monkeypatch.setattr(c, 'saved', lambda result: copy.deepcopy(result[c.FIELD]))
    return result


@pytest.mark.parametrize('sufficient', [True, False])
@pytest.mark.parametrize('criterion', ['nbr_A1_pair', 'declared_limit'])
def test_separate_stiffness_displacement_and_selected_criterion(monkeypatch, sufficient, criterion):
    result = trusted_packet(monkeypatch, sufficient=sufficient, criterion=criterion)
    before = copy.deepcopy(result)
    notes, error = e.presentation(result)
    assert error is None and result == before
    assert set(notes) == {'service_stiffness', 'service_displacement', 'service_criteria'}
    assert '1 campos calculados' in notes['service_stiffness'][0]
    assert ('inconclusiva' in notes['service_stiffness'][1]) is (not sufficient)
    assert ('NBR Tabela A.1 notas e/f' in notes['service_criteria'][0]) is (criterion == 'nbr_A1_pair')
    assert 'frequente' in ' '.join(notes['service_criteria'])
    assert 'Giro linear' in ' '.join(notes['service_displacement'])
    assert 'sem aprovação' in ' '.join(notes['service_criteria'])


@pytest.mark.parametrize('schema', c.mechanics.SCHEMAS)
def test_mechanics_version_kept_without_promotion(monkeypatch, schema):
    result = trusted_packet(monkeypatch)
    result[c.FIELD]['records'][0]['comparison']['schema'] = schema
    assert schema in ' '.join(e.notes(result)['service_stiffness'])


def test_complete_mixed_inventory_and_no_empty_approval(monkeypatch):
    result = trusted_packet(monkeypatch)
    ev = result[c.FIELD]
    ev['records'] += [dict(id='PENDING',kind='pending',status='pending',reason='Rara ausente.',comparison=None),
                      dict(id='ZERO',kind='zero_characteristic_wind',status='not_applicable',reason='',comparison=None)]
    ev['inventory'] += [dict(id='PENDING'),dict(id='ZERO')]
    notes = e.notes(result)
    text = ' '.join(notes['service_criteria'])
    assert 'PENDING' in text and 'ZERO' in text and 'Rara ausente' in text
    assert '3 casos; 1 campos calculados; 1 pendentes; 1 dispensas' in notes['service_stiffness'][0]
    ev['records'] = [];ev['inventory'] = []
    assert 'Inventário de comparações vazio' in ' '.join(e.notes(result)['service_criteria'])


def test_real_pending_and_tampering_without_solver():
    from test_isolated_service_component import source as real_source
    from tercas.application import fingerprint
    result, section, _, _ = real_source()
    result['input_data'][c.CHOICE]['point_xy_from_CG_mm'] = [None, None]
    result['input_fingerprint'] = fingerprint(result['input_data'])
    with patch('tercas.torsion_vlasov.vlasov.solve_member', side_effect=AssertionError('no solver')):
        result = c.finalize(c.attach_dense(result, section))
        notes, error = e.presentation(result)
    assert error is None and '0 campos calculados' in notes['service_stiffness'][0]
    result[c.FIELD]['records'].pop()
    notes, error = e.presentation(result)
    assert notes == {} and 'não autenticada' in error


def test_ui_report_isolate_optional_error_and_preserve_snapshot(monkeypatch):
    from docx import Document
    class UI:
        def __init__(self): self.lines = []
        def expander(self,*a,**kw): return self
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def caption(self,s): self.lines.append(s)
        markdown = warning = caption
    result = req.attach(source()); result[c.FIELD] = {'invalid': True}
    before = copy.deepcopy(result); ui = UI(); doc = Document()
    req.show(ui, result);req.report(doc, result)
    assert result == before and req.saved(result) == before[req.FIELD]
    for text in (' '.join(ui.lines), ' '.join(p.text for p in doc.paragraphs)):
        assert 'não autenticada' in text and 'Empoçamento' in text and 'Ligações' in text
    assert all(row['requirement_state'] == 'closure_not_qualified' for row in result[req.FIELD]['records'] if row['id'].startswith('service_'))


def test_absent_history_not_synthesized():
    result = req.attach(source()); before = copy.deepcopy(result)
    assert e.presentation(result) == ({}, None)
    assert result == before


def test_report_connects_evidence_without_rewriting_old_requirement(monkeypatch):
    from docx import Document
    synthetic = trusted_packet(monkeypatch)
    result = req.attach(source())
    result[c.FIELD] = synthetic[c.FIELD]
    before = copy.deepcopy(result)
    doc = Document(); req.report(doc, result)
    text = ' '.join(p.text for p in doc.paragraphs)
    assert 'Evidência ELS autenticada detalhada a seguir' in text
    assert 'DIRECT_ELS' in text and '1 campos calculados' in text
    assert 'Limite declarado para as combinações ELS selecionadas' in text
    assert result == before
    rows = {r['id']:r for r in req.saved(result)['records']}
    assert rows['service_criteria']['evidence_state'] == 'not_consolidated'
    assert rows['service_criteria']['requirement_state'] == 'closure_not_qualified'
