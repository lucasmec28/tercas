"""Elastic scope guard is not an effective-stress check or a resistance edit."""
import copy
from io import BytesIO
import warnings

from docx import Document
import pytest
from scipy.integrate import IntegrationWarning

from tercas import deflection_scope as scope, ue_reference, ue_family_reference
from tercas.application import calculate, defaults, example, rows
from tercas.batch import calculate_batch
from tercas.report import word, batch_word


def inputs(t=1.2, q=.1, P=0., a=1333.):
    d = ue_reference.load_reference(L_mm=4000.) if t == 1.2 else ue_family_reference.load_reference(t, 4000.)
    d.update(load_mode='direct', q_sls=q, P_sls=P, x_sls=a,
             q_uls=.2, q_parallel_sls=.05)
    return scope.activate(d)


def guard(result):
    return result['ELS']['local_uniaxial_component']['gross_elastic_guard']


@pytest.mark.parametrize('t', [1.2, 1.5, 3.35])
@pytest.mark.parametrize('sign', [-1., 1.])
def test_own_references_do_not_emit_component_index_above_gross_yield(t, sign):
    d = inputs(t, q=sign*20.)
    before = copy.deepcopy(d)
    r = calculate(d)
    g = guard(r)
    assert d == before
    assert g['max_abs_M_Nmm'] == pytest.approx(20.*4000.**2/8.)
    assert g['sigma_gross_max_MPa'] == pytest.approx(g['max_abs_M_Nmm']/g['Wg_mm3'])
    assert g['passed'] is False
    assert g['effective_section_stress_qualified'] is False
    assert r['ELS']['deflection_mm']*sign > 0
    assert r['ELS']['limit_mm'] == d['ELS_limit_mm']
    assert 'index' not in r['ELS']
    assert r['ELS']['criterion_status'] == 'gross_elastic_model_exceeded'
    row = next(row for row in rows(r) if row['Verificação'] == scope.PURLIN_ROW)
    assert row['Índice'] is None and 'Pendente' in row['Situação']
    assert 'fy=' in row['Observação']
    unselected = copy.deepcopy(d)
    unselected.pop(scope.FIELD)
    old = calculate(unselected)
    assert r['ELS']['deflection_mm'] == old['ELS']['deflection_mm']
    for key in ('NBR_branches', 'FLT_segments', 'section_checks'):
        assert r[key] == old[key]


@pytest.mark.parametrize('q,P,a', [(0., 500., 1234.), (.1, 100., 2700.), (-.1, -100., 2700.), (0., 0., 1333.)])
def test_exact_moment_candidates_and_ordinary_component_index(q, P, a):
    d = inputs(q=q, P=P, a=a)
    r = calculate(d)
    g = guard(r)
    L = d['L_mm']
    R = q*L/2+P*(L-a)/L
    xs = [0., a, L]
    if q:
        if 0. <= R/q <= a:xs.append(R/q)
        if a <= (R-P)/q <= L:xs.append((R-P)/q)
    m = max(abs(R*x-q*x*x/2-P*max(0., x-a)) for x in xs)
    assert g['max_abs_M_Nmm'] == pytest.approx(m)
    assert g['passed'] is True
    assert r['ELS']['index'] == abs(r['ELS']['deflection_mm'])/d['ELS_limit_mm']


def test_even_a_generous_declared_limit_cannot_pass_above_gross_yield():
    d = scope.activate(example())
    d.update(q_sls=20., P_sls=0., ELS_limit_mm=1e8)
    r = calculate(d)
    assert abs(r['ELS']['deflection_mm']) < r['ELS']['limit_mm']
    assert guard(r)['passed'] is False
    assert 'index' not in r['ELS']


@pytest.mark.parametrize('key', ['Wx_cm3', 'fy_MPa'])
def test_missing_gross_guard_input_does_not_invent_a_pass(key):
    d = scope.activate(defaults(19))
    d.update(q_sls=.1, ELS_limit_mm=100., ELS_origin='Synthetic declared limit')
    d['properties'][key] = None
    r = calculate(d)
    assert guard(r)['passed'] is None
    assert r['ELS']['criterion_status'] == 'missing_gross_elastic_inputs'
    assert 'index' not in r['ELS']


def test_numerical_failure_keeps_precedence_over_gross_guard(monkeypatch):
    from tercas.core import especificacao_unica as core
    old = core.peak
    def warn(*args, **kwargs):
        warnings.warn('Synthetic quadrature warning', IntegrationWarning)
        return old(*args, **kwargs)
    monkeypatch.setattr(core, 'peak', warn)
    r = calculate(inputs(q=20.))
    assert guard(r)['passed'] is False
    assert r['ELS']['criterion_status'] == 'not_evaluated_numerical_warning'
    assert 'index' not in r['ELS']


def test_area_support_limit_guard_uses_interior_actions_once():
    d = inputs()
    d['load_mode'] = 'area'
    r = calculate_batch(d)
    for case in r['cases']:
        c = case['combination']
        if c['limit_state'] != 'ELS':continue
        g = case['evidence']['ELS']['local_uniaxial_component']['gross_elastic_guard']
        if c.get('point_position') == 'support_limit':
            assert g['max_abs_M_Nmm'] == pytest.approx(abs(c['q_vector']['normal'])*d['L_mm']**2/8.)
            assert c['P_vector']['normal'] > 0
        assert g['effective_section_stress_qualified'] is False


def test_guard_uses_consumed_snapshot_not_external_input_fields():
    r = calculate(inputs(q=20.))
    expected = guard(r)
    r['input_data'].update(q_sls=0., P_sls=0.)
    assert scope._elastic_guard(r) == expected


def test_gross_yield_equality_is_not_an_added_strict_limit():
    r = calculate(inputs())
    r['input_snapshot']['selected_section']['fields']['Wx_cm3']['value'] = 1.
    r['input_snapshot']['selected_section']['fields']['fy_MPa']['value'] = 250.
    r['input_snapshot']['SLS'].update(q_Nmm=.125, P_N=0.)
    g = scope._elastic_guard(r)
    assert g['sigma_gross_max_MPa'] == 250.
    assert g['passed'] is True


@pytest.mark.parametrize('mode', ['direct', 'area'])
def test_report_reads_saved_guard_without_recalculation(mode, monkeypatch):
    d = inputs(q=20.)
    d['load_mode'] = mode
    r = calculate(d) if mode == 'direct' else calculate_batch(d)
    before = copy.deepcopy(r)
    monkeypatch.setattr(scope, '_elastic_guard', lambda *args: pytest.fail('Rendering must not calculate'))
    blob = word(r) if mode == 'direct' else batch_word(r)
    text = '\n'.join(p.text for p in Document(BytesIO(blob)).paragraphs)
    assert 'Guarda de consistência adotada pelo aplicativo' in text
    assert 'σg,max=' in text
    assert r == before


def test_old_scope_text_is_not_rewritten_with_a_guard_not_calculated():
    r = calculate(inputs())
    old_text = 'Historical isolated component scope without the new elastic guard.'
    r['deflection_scope_evidence']['text'] = old_text
    r['deflection_scope_evidence'].pop('gross_elastic_guard')
    r['ELS']['local_uniaxial_component'].pop('gross_elastic_guard')
    row = next(row for row in rows(r) if row['Verificação'] == scope.PURLIN_ROW)
    assert old_text in row['Observação']
    assert 'Se a própria tensão' not in row['Observação']
    text = '\n'.join(p.text for p in Document(BytesIO(word(r))).paragraphs)
    assert 'Guarda de consistência adotada pelo aplicativo' not in text
