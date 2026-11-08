"""Saved-display diagnostics only; no member/section solve or requalification."""
import copy
from unittest.mock import patch

import pytest

from tercas import isolated_service_diagnostics as d
from tercas import isolated_service_mechanics as m
from tercas import isolated_service_ui as ui


def comparison(mask=0, elastic=True, schema=m.SCHEMA):
    return dict(schema=schema, criterion_status='gross_MLE_sufficient_condition_inconclusive',
        index_upper=None, index_lower=None, diagnostic_ratio_upper=.1,
        limit_mm=20., envelope=dict(abs_displacement_upper_mm=2., witness=dict(station_mm=1500.)),
        gross_screen=dict(walls=[dict(name=name, sufficient=not bool(mask & (1 << i)))
            for i, (name, _) in enumerate(d.WALLS)], elastic_field_sufficient=elastic,
            gross_local_normal_sufficient=not mask and elastic))


@pytest.mark.parametrize('mask', range(32))
@pytest.mark.parametrize('elastic', [True, False])
def test_each_saved_wall_and_elastic_state_is_separate_and_immutable(mask, elastic):
    check = comparison(mask, elastic)
    before = copy.deepcopy(check)
    with patch.object(m, 'calculate', side_effect=AssertionError('no arithmetic replay here')), \
         patch('tercas.torsion_vlasov.vlasov.solve_member', side_effect=AssertionError('no member solve')):
        detail = d.explain(check)
    assert check == before
    expected = [label for i, (_, label) in enumerate(d.WALLS) if mask & (1 << i)]
    assert detail['Crivo local inconclusivo em'] == (', '.join(expected) if expected else 'Nenhuma parede neste crivo suficiente')
    assert ('> fy' in detail['Guarda elástica do campo bruto']) is (not elastic)
    if mask:
        assert 'não demonstra redução real ou falha' in detail['Alcance da pendência']
        assert 'Mx+My+B' in detail['Alcance da pendência']
    elif not elastic:
        assert 'seção reduzida não resolve automaticamente' in detail['Alcance da pendência']
    else:
        assert 'Alcance da pendência' not in detail
    assert all('índice' not in key.lower() for key in detail)


@pytest.mark.parametrize('schema', m.SCHEMAS)
def test_existing_versions_show_detail_without_promoting_or_mutating(schema):
    check = comparison(mask=4, schema=schema)
    packet = {'records': [dict(id='SYNTHETIC', reason=None, status='computed_linear_comparison', comparison=check)]}
    before = copy.deepcopy(packet)
    with patch.object(m, 'calculate', side_effect=AssertionError('no recalculation')):
        row = ui.rows(packet)[0]
    assert packet == before
    assert row['Crivo local inconclusivo em'] == 'alma'
    assert row['Índice superior no campo linear'] is None
    assert row['Índice inferior no campo linear'] is None
    assert row['Deslocamento: limite superior [mm]'] == 2.
    assert row['Situação'] == 'Crivo suficiente MLE inconclusivo'


@pytest.mark.parametrize('mutation', ['missing', 'empty', 'duplicate', 'reorder', 'unknown', 'bool'])
def test_incomplete_detail_cannot_be_reported_as_proved(mutation):
    check = comparison(mask=4)
    screen = check['gross_screen']
    if mutation == 'missing': screen.pop('walls')
    if mutation == 'empty': screen['walls'] = []
    if mutation == 'duplicate': screen['walls'][2] = copy.deepcopy(screen['walls'][1])
    if mutation == 'reorder': screen['walls'].reverse()
    if mutation == 'unknown': screen['walls'][2]['name'] = 'unknown'
    if mutation == 'bool': screen['elastic_field_sufficient'] = 1
    before = copy.deepcopy(check)
    assert d.explain(check) == {'Detalhe do crivo salvo': 'Detalhamento completo das cinco paredes e da guarda elástica não registrado.'}
    assert check == before


def test_report_and_screen_consume_same_authenticated_snapshot(monkeypatch):
    from docx import Document
    check = comparison(mask=6, elastic=False)
    packet = dict(scope='Synthetic saved scope', missing=[],
        configuration=dict(point_label='CG', direction_label='Normal local', criterion_origin='Synthetic'),
        records=[dict(id='SYNTHETIC', reason=None, status='computed_linear_comparison', comparison=check)])
    before = copy.deepcopy(packet)
    reads = []
    monkeypatch.setattr(ui.c, 'saved', lambda result: reads.append(result) or packet)
    doc = Document()
    with patch.object(m, 'calculate', side_effect=AssertionError('no calculation')), \
         patch('tercas.torsion_vlasov.vlasov.solve_member', side_effect=AssertionError('no solver')):
        ui.report(doc, {'saved_result': True})
    assert reads == [{'saved_result': True}]
    assert packet == before
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert 'mesa inferior, alma' in text and '> fy' in text
    assert 'não demonstra redução real ou falha' in text


def test_failed_authentication_does_not_show_partial_diagnostics(monkeypatch):
    from docx import Document
    def denied(result):
        raise ValueError('synthetic changed snapshot')
    monkeypatch.setattr(ui.c, 'saved', denied)
    monkeypatch.setattr(d, 'explain', lambda check: pytest.fail('unauthenticated detail'))
    doc = Document()
    ui.report(doc, {})
    assert len(doc.paragraphs) == 1
    assert 'não exibido' in doc.paragraphs[0].text
