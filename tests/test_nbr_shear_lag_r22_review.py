"""Review diagnostics only; these tests do not qualify a reduced section."""
from fractions import Fraction as F
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT/'qa/nbr_shear_lag_r22_review'
review = runpy.run_path(str(QA/'check_contract.py'))


@pytest.mark.parametrize('ratio,factor', [
    (6, '0.55'), (8, '0.67'), (10, '0.73'), (12, '0.78'), (14, '0.82'),
    (16, '0.86'), (18, '0.89'), (20, '0.91'), (25, '0.96'), (30, '1'),
])
def test_printed_nodes_only(ratio, factor):
    assert review['printed_factor'](F(ratio)) == F(factor)


@pytest.mark.parametrize('ratio', [F(0), F(5), F(7), F(29), F(31), F(1, 2)])
def test_no_interpolation_extrapolation_or_clamping(ratio):
    with pytest.raises(ValueError, match='No printed node'):
        review['printed_factor'](ratio)


@pytest.mark.parametrize('ratio', [True, 20, 20., '20', float('nan')])
def test_diagnostic_requires_explicit_rational_input(ratio):
    with pytest.raises(TypeError):
        review['printed_factor'](ratio)


def test_geometry_candidates_are_conditional_and_decision_relevant():
    result = review['conditional_geometry']()
    rows = result['conditional_widths']
    assert result['none_of_the_proposals_is_an_exact_bf0_certificate']
    assert rows['unqualified_face_distance_plus_nominal_lip']['width_mm'] == 93
    assert rows['unqualified_flat_width_plus_nominal_lip']['width_mm'] == 85
    assert not rows['unqualified_face_distance_plus_nominal_lip']['span_ge_thirty_times_assumed_width']
    assert rows['unqualified_flat_width_plus_nominal_lip']['span_ge_thirty_times_assumed_width']


def test_same_area_and_centroid_do_not_fix_strong_Ix_for_assembly():
    result = review['same_area_different_Ix']()
    rows = result['distributions']
    assert {r['area_mm2'] for r in rows.values()} == {F('745.8')}
    assert {r['centroid_y_mm'] for r in rows.values()} == {F(0)}
    assert {r['Ix_mm4'] for r in rows.values()} == {F(4642000), F('4740893.8315'), F(4655440)}
    assert result['distributions_are_not_engineering_methods']
    assert result['no_uniform_beta_method_is_adopted']


def test_scalar_strong_method_does_not_require_invented_full_tensor_problem():
    integrate = review['horizontal_interval']
    assert integrate(F(0), F(5), F(100)) == integrate(F(70), F(75), F(100))


def test_saved_receipt_replays_exactly_and_never_extends_production():
    result = review['run']()
    encoded = json.loads(json.dumps(result, default=review['encode']))
    assert encoded == json.loads((QA/'exact_diagnostics.json').read_text())
    for key in ('production_files_changed', 'production_eligibility_extended',
                'bf0_exact_mapping_qualified', 'reduced_resistance_qualified',
                'historical_replay_changed', 'whole_member_approved'):
        assert encoded[key] is False


def test_diagnostic_import_does_not_import_solver_numpy_or_production_provider():
    code = ('import runpy, sys; '
            f'ns=runpy.run_path({str(QA/"check_contract.py")!r}); ns["run"](); '
            'assert "numpy" not in sys.modules; '
            'assert not any(x.startswith("tercas") for x in sys.modules)')
    subprocess.run([sys.executable, '-c', code], check=True, cwd=ROOT)
