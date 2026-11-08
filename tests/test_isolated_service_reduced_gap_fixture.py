"""Real synthetic saved field: elastic yet inconclusive local stiffness.

These regressions perform arithmetic replay only, never a new member solve.
The fixture is not a physical validation or an approval example.
"""
import copy
import gzip
import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from tercas import isolated_service_mechanics as m
from tercas.isolated_service_diagnostics import explain


@pytest.fixture(scope='module')
def fixture():
    path = Path(__file__).with_name('fixtures') / 'isolated_service_reduced_gap_synthetic.json.gz'
    value = json.loads(gzip.decompress(path.read_bytes()))
    assert value['schema'] == 'synthetic_service_gap_fixture_v1'
    assert value['synthetic_only'] is True
    return value


def test_saved_synthetic_field_replays_without_solver_or_scalar_MSE(fixture):
    from tercas.en_ue125_300_source_replay import validate
    before = copy.deepcopy(fixture)
    with patch('tercas.torsion_vlasov.vlasov.solve_member', side_effect=AssertionError('no solve')), \
         patch('tercas.torsion_vlasov.vlasov.solve', side_effect=AssertionError('no linear solve')), \
         patch('tercas.core.protocolo_ief.peak', side_effect=AssertionError('no scalar substitution')):
        assert validate(fixture['demand'])
        check = m.calculate(fixture['demand'], fixture['dimensions'], fixture['fy_MPa'],
                            fixture['configuration'], fixture['limit_mm'])
    assert fixture == before
    assert check == fixture['comparison']
    assert check['gross_screen']['elastic_field_sufficient'] is True
    assert check['criterion_status'] == 'gross_MLE_sufficient_condition_inconclusive'
    assert check['index_lower'] is None and check['index_upper'] is None
    assert check['diagnostic_ratio_upper'] < 1  # A permissive limit cannot qualify missing stiffness.
    assert not check['combined_ELS_approved'] and not check['whole_member_approved']
    assert explain(check)['Crivo local inconclusivo em'] == 'alma, mesa superior'


def test_fixture_preserves_actual_top_and_PP_lines_and_concurrent_fields(fixture):
    from tercas.torsion_vlasov.vlasov import evaluate
    demand = fixture['demand']
    loads = {row['name']: row for row in demand['loads']}
    assert set(loads) == {'EXTERNAL', 'PP'}
    props = demand['section']['properties']
    cg, sc = props['centroid_xy_mm'], props['shear_center_xy_mm']
    assert loads['PP']['application_xy_mm'] == cg
    assert loads['EXTERNAL']['application_xy_mm'] != cg
    assert loads['EXTERNAL']['application_xy_mm'][0] == 0.
    for row in loads.values():
        qx, qy = row['q_xy_N_mm']
        x, y = row['application_xy_mm']
        assert row['torque_SC_N'] == (x-sc[0])*qy-(y-sc[1])*qx
        assert row['torque_SC_N'] != 0.
    recipe = fixture['recipe']
    weight = recipe['PP_mass_kg_m']*9.80665/1000.
    theta = math.radians(recipe['inclination_deg'])
    assert loads['PP']['q_xy_N_mm'] == pytest.approx([weight*math.sin(theta), -weight*math.cos(theta)], rel=1e-14)
    assert demand['length_mm'] == recipe['physical_span_mm'] == 4000.
    at = evaluate(demand, 15, 1.)
    assert at['s_mm'] == 2000.
    assert all(at[key] != 0. for key in ('Mx_physical_Nmm', 'My_physical_Nmm', 'B_Nmm2'))
    assert all(demand['analysis_domain'][key] is False for key in ('sheet_restraint', 'intermediate_braces'))


def test_physical_weak_moment_sign_is_not_the_app_sign(fixture):
    # Algebraic sign check only, not a new pure-weak service route or load case.
    props = fixture['demand']['section']['properties']
    t = fixture['dimensions']['t']
    web_x = -t/2
    lip_x = fixture['dimensions']['bf']-t/2
    cx, Iy = props['centroid_xy_mm'][0], props['Iy_weak_mm4']
    for physical_My, expected_web_sign in ((-1., -1), (1., 1)):
        web_sigma = -physical_My*(web_x-cx)/Iy
        lip_sigma = -physical_My*(lip_x-cx)/Iy
        assert math.copysign(1, web_sigma) == expected_web_sign
        assert math.copysign(1, lip_sigma) == -expected_web_sign


def test_diagnostic_render_never_changes_the_saved_mechanical_field(fixture):
    from tercas.isolated_service_ui import rows
    before = copy.deepcopy(fixture)
    with patch.object(m, 'calculate', side_effect=AssertionError('display only')):
        result = rows({'records': [dict(id='DIRECT_ELS', reason=None,
            status='computed_linear_comparison', comparison=fixture['comparison'])]})[0]
    assert fixture == before
    assert result['Índice superior no campo linear'] is None
    assert result['Crivo local inconclusivo em'] == 'alma, mesa superior'
    assert '≤ fy' in result['Guarda elástica do campo bruto']
    assert 'Mx+My+B' in result['Alcance da pendência']
