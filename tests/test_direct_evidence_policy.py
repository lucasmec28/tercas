"""CT presentation changes only; unmarked direct evidence remains byte-identical."""
import copy
import json
from io import BytesIO

import pytest
from docx import Document

from tercas import direct_self_weight as pp, inclination_adapter as adapter
from tercas import load_application_policy as policy, ue_catalog_reference as own
from tercas.application import calculate, defaults, example, fingerprint
from tercas.report import word


def source(kind):
    data = example()
    if kind == 'own_girt':
        data = defaults(0)
        data['member_application'] = 'wall_girt'
        data = own.activate(pp.activate(data))
        data.pop(pp.FIELD)
    elif kind == 'girt':
        data['member_application'] = 'wall_girt'
    data.update(q_uls=.2, q_sls=.1, q_parallel_uls=.03, q_parallel_sls=-.02,
                P_uls=120., P_sls=80., P_parallel_uls=30., P_parallel_sls=-20.,
                inclination={'value':5., 'unit':'degrees'})
    return data


def historical_direct_evidence(data):
    """Frozen pre-fix producer, independent of the current text-selection branch."""
    auto = pp.active(data)
    effective = pp.calculation_inputs(data)
    result = {}
    for state, key in [('ELU', 'uls'), ('ELS', 'sls')]:
        q = {'normal':effective['q_'+key], 'parallel':effective.get('q_parallel_'+key, 0.)}
        p = {'normal':effective['P_'+key], 'parallel':effective.get('P_parallel_'+key, 0.)}
        result[state] = adapter.evidence(effective, q, p, effective['x_'+key])
        result[state]['convention'] += (' '+pp.TEXT if auto else
            ' Modo direto: cargas já locais e combinadas; não há rotação nem PP automático.')
    return result


@pytest.mark.parametrize('kind', ['roof', 'girt', 'own_girt'])
@pytest.mark.parametrize('automatic_pp', [False, True])
@pytest.mark.parametrize('at_ct', [False, True])
def test_direct_convention_selects_ct_scope_without_changing_fields(kind, automatic_pp, at_ct):
    data = source(kind)
    if automatic_pp:
        data = pp.activate(data)
    if at_ct:
        data = policy.adopt(data)
    before = copy.deepcopy(data)
    expected = historical_direct_evidence(data)
    if automatic_pp and at_ct:
        scope = pp.evidence(data)['scope']
        for item in expected.values():
            item['convention'] = item['convention'].removesuffix(pp.TEXT)+scope
            assert 'no CG' not in item['convention'] and 'topo selecionado' not in item['convention']
    actual = adapter.direct_evidence(data)
    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert data == before and fingerprint(data) == fingerprint(before)


@pytest.mark.parametrize('kind', ['roof', 'girt'])
@pytest.mark.parametrize('at_ct', [False, True])
def test_calculation_json_and_word_change_only_current_convention(kind, at_ct, monkeypatch):
    data = pp.activate(source(kind))
    if at_ct:
        data = policy.adopt(data)
    with monkeypatch.context() as historical:
        historical.setattr(adapter, 'direct_evidence', historical_direct_evidence)
        before = calculate(data)
    after = calculate(data)
    expected = copy.deepcopy(before)
    if at_ct:
        for item in expected['inclination_evidence'].values():
            item['convention'] = item['convention'].removesuffix(pp.TEXT)+pp.evidence(data)['scope']
    assert after == expected
    assert json.loads(json.dumps(after)) == expected
    # Readers serialize the saved record, including old records carrying a CT marker.
    for result in (before, after):
        frozen = copy.deepcopy(result)
        paragraphs = [p.text for p in Document(BytesIO(word(result))).paragraphs]
        for item in result['inclination_evidence'].values():
            assert item['convention'] in paragraphs
        assert result['direct_self_weight_evidence']['scope'] in paragraphs
        assert result == frozen
    if not at_ct:
        assert fingerprint(after) == fingerprint(before)
