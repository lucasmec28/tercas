"""Public synthetic regression: support-limit M-V evidence, not new resistance."""
import copy
import json

import pytest

from tercas.application import calculate, example, rows
from tercas.batch import calculate_batch, case_inputs, mobile_rows
from tercas.core.envelope_mv import envelope


MV = 'Flexão e cortante concomitantes'


def synthetic(MRd=1e6, VRd=2000., P=500., q=2.):
    """Simple independent numbers; no qualification/research input vector."""
    L = 1000.
    best, _ = envelope(L, q, 0., L/2, L/2, MRd, VRd)
    branch = {'status': 'computed_fixed_load_position', 'result': best,
              'source': 'NBR9.8.4 same position and combination; local MRd denominator'}
    result = {'input_data': {'L_mm': L},
              'NBR_branches': {'MV': branch, 'local': {'MRd_Nmm': MRd}},
              'section_checks': {'shear': {'VRd_N': VRd}}}
    rs = [{'Verificação': MV, 'Índice': best['index_squared'],
           'Situação': 'Atende ao critério calculado', 'Observação': ''}]
    combo = {'id': 'SYNTHETIC_ELU_APOIO', 'limit_state': 'ELU',
             'point_position': 'support_limit', 'q_N_mm': q, 'P_N': P}
    return rs, result, combo


@pytest.mark.parametrize('MRd,VRd,P,governing,tied', [
    (1e6, 2000., 500., 'support_layer', ['support_layer']),
    (1e5, 2000., 500., 'interior_q_only', ['interior_q_only']),
    (125000., 1000., 1000., 'interior_q_only', ['interior_q_only', 'support_layer']),
])
def test_governing_result_and_both_concomitant_states(MRd, VRd, P, governing, tied):
    rs, result, combo = synthetic(MRd, VRd, P)
    if len(tied) == 2:
        # Exact analytic midspan value for this synthetic tie, avoiding
        # polynomial evaluation roundoff in the independent input adapter.
        result['NBR_branches']['MV']['result']['index_squared'] = 4.
        rs[0]['Índice'] = 4.
    before = copy.deepcopy(result)
    original = before['NBR_branches']['MV']['result']
    ev = mobile_rows(rs, result, combo)
    branch = result['NBR_branches']['MV']
    expected = max(original['index_squared'], ((1000.+P)/VRd)**2)
    assert branch['result']['index_squared'] == rs[0]['Índice'] == expected
    assert ev['MV_limit_states']['governing_index_squared'] == expected
    assert branch['status'] == 'computed'
    assert branch['position'] == 'support_limit'
    assert branch['governing_state'] == governing
    assert branch['governing_states'] == tied
    assert branch['interior_q_only_result'] == original
    assert 'P=0' in branch['interior_adapter_note']
    interior = branch['limit_states']['interior_q_only']
    support = branch['limit_states']['support_layer']
    assert interior['index_squared'] == original['index_squared']
    assert interior['x_mm'] == original['x_mm']
    x = interior['x_mm']
    assert interior['M_Nmm'] == combo['q_N_mm']*x*(1000.-x)/2
    assert interior['V_N'] == combo['q_N_mm']*(500.-x)
    assert support['M_Nmm'] == 0.
    assert support['V_N'] == 1000.+P
    assert support['x_mm'] == 0.
    assert 'x<a' in support['position_limit']
    for state in (interior, support, branch['result']):
        assert state['a_mm'] is None
        assert state['a_limit'] == 'a→0+'
    assert branch['result'] == branch['limit_states'][governing]
    assert branch['result'] is not branch['limit_states'][governing]
    assert result['section_checks'] == before['section_checks']
    assert result['NBR_branches']['local'] == before['NBR_branches']['local']
    assert 'same combination' in branch['source']
    json.dumps({'result': result, 'evidence': ev}, allow_nan=False)


def test_signed_support_demand_is_not_changed_to_absolute_evidence():
    rs, result, combo = synthetic(q=-2., P=-500.)
    ev = mobile_rows(rs, result, combo)
    assert ev['V_support_limit_N'] == 1500.
    assert result['NBR_branches']['MV']['limit_states']['support_layer']['V_N'] == -1500.
    assert rs[0]['Índice'] == (1500./2000.)**2


@pytest.mark.parametrize('missing', ['VRd', 'MV_result', 'MV_branch'])
def test_missing_resistance_or_interaction_stays_pending(missing):
    rs, result, combo = synthetic()
    rs[0].update({'Índice': None, 'Situação': 'Não avaliado'})
    if missing == 'VRd':
        result['section_checks']['shear'].pop('VRd_N')
    elif missing == 'MV_result':
        result['NBR_branches']['MV'] = {'status': 'not_evaluated', 'missing': 'local MRd'}
    else:
        result['NBR_branches'].pop('MV')
    before = copy.deepcopy(result)
    ev = mobile_rows(rs, result, combo)
    assert rs[0]['Índice'] is None
    assert rs[0]['Situação'] == 'Não avaliado'
    assert result == before
    assert 'MV_limit_states' not in ev


def test_center_does_not_relabel_fixed_position_or_mutate_evidence():
    rs, result, combo = synthetic()
    combo['point_position'] = 'center'
    before = copy.deepcopy(result)
    old_index = rs[0]['Índice']
    ev = mobile_rows(rs, result, combo)
    assert result == before
    assert rs[0]['Índice'] == old_index
    assert 'MV_limit_states' not in ev


@pytest.fixture(scope='module')
def batch():
    data = example()
    data.update(load_mode='area', selected_types=['ELU normal', 'ELS rara'])
    before = copy.deepcopy(data)
    result = calculate_batch(data)
    assert data == before
    return data, result


def test_batch_trace_matches_same_combination_and_retains_other_branches(batch):
    data, result = batch
    for case in result['cases']:
        c = case['combination']
        if c['limit_state'] != 'ELU':
            continue
        direct = calculate(case_inputs(data, c))
        b = case['evidence']['NBR_branches']
        if c.get('point_position') != 'support_limit':
            assert b == direct['NBR_branches']
            continue
        assert b['MV']['interior_q_only_result'] == direct['NBR_branches']['MV']['result']
        row = next(r for r in case['rows'] if r['Verificação'] == MV)
        assert b['MV']['result']['index_squared'] == row['Índice']
        assert b['MV']['limit_states']['support_layer']['V_N'] == c['q_N_mm']*data['L_mm']/2+c['P_N']
        assert b['local'] == direct['NBR_branches']['local']
        assert case['evidence']['FLT_segments'] == direct['FLT_segments']
        assert case['evidence']['section_checks'] == direct['section_checks']
        assert b['point']['status'] == 'not_evaluated'
        assert b['point']['force_N'] == c['P_N']


def test_els_and_no_approval_guards_are_unchanged(batch):
    data, result = batch
    assert result['whole_member_approved'] is False
    for case in result['cases']:
        c = case['combination']
        assert all(r['Verificação'] not in ('Shear lag', 'Anexo D', 'Carga concentrada',
                                           'Cortante paralelo', 'Flecha paralela à cobertura')
                   for r in case['rows'])
        if c['limit_state'] == 'ELS':
            direct = calculate(case_inputs(data, c))
            assert case['evidence']['ELS'] == direct['ELS']
            assert 'NBR_branches' not in case['evidence']
            assert 'MV_limit_states' not in case['evidence'].get('prescribed_point', {})
    json.dumps(result, allow_nan=False)
