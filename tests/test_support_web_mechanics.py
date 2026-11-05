"""Local support web tests. All physical arrangements here are synthetic."""
import copy
import json
import math
from decimal import Decimal, localcontext

import pytest

from tercas.support_web.mechanics import evaluate_reaction


def section(**changes):
    return dict(dict(family='Ue', H=100., t=2., ri=2., fy=250.), **changes)


def reaction(**changes):
    return dict(dict(normal_N=1000., parallel_N=0., moment_strong_Nmm=0.), **changes)


def contact(**changes):
    return dict(dict(route='flange_contact', origin='QA sintético: detalhe declarado, sem condição física comprovada.',
                     c_mm=40., end_distance_mm=0., no_opposite_force=True,
                     opposite_clear_distance_mm=None, connected=False,
                     normal_compressive_sign=1,
                     loaded_flange_orientation='Mesa declarada; reação positiva a comprime.'), **changes)


def assert_pending(result):
    assert result['status'] == 'not_evaluated'
    assert result.get('criterion_status') not in ('meets', 'fails')
    assert 'index' not in result and 'FRd_N' not in result
    assert result['whole_member_approved'] is False
    assert result['connection_design_checked'] is False
    assert result['global_approval'] is False
    json.dumps(result, allow_nan=False)


# Independently transcribed Table D.2 rows: (connected, lip, flange count,
# position, ri/t maximum, alpha, Cr, Cc, Ch). Not imported from the implementation.
ROWS_ORACLE = [
    (True, True, 1, 'end', 9, '4.6', '.14', '.35', '.02'),
    (True, True, 1, 'internal', 5, '15.8', '.23', '.14', '.01'),
    (True, True, 2, 'end', 12, '8.6', '.08', '.12', '.048'),
    (True, True, 2, 'internal', 12, '23', '.10', '.08', '.031'),
    (False, True, 1, 'end', 5, '4.3', '.14', '.35', '.02'),
    (False, True, 1, 'internal', 5, '15.8', '.23', '.14', '.01'),
    (False, True, 2, 'end', 3, '15.8', '.32', '.05', '.04'),
    (False, True, 2, 'internal', 3, '25.9', '.52', '.15', '.001'),
    (False, False, 1, 'end', 2, '4.6', '.40', '.60', '.03'),
    (False, False, 1, 'internal', 1, '14.9', '.32', '.10', '.01'),
    (False, False, 2, 'end', 1, '2', '.11', '.37', '.01'),
    (False, False, 2, 'internal', 1, '14', '.47', '.25', '.04'),
]


@pytest.mark.parametrize('connected,lip,count,location,rmax,alpha,Cr,Cc,Ch', ROWS_ORACLE)
def test_all_twelve_table_rows_match_independent_decimal_oracle(connected, lip, count, location, rmax, alpha, Cr, Cc, Ch):
    s = section(family='Ue' if lip else 'U')
    d = contact(connected=connected, no_opposite_force=False,
                opposite_clear_distance_mm=138. if count == 1 else 137.,
                end_distance_mm=0. if location == 'end' else 231.)
    result = evaluate_reaction(s, reaction(), d)
    with localcontext() as ctx:
        ctx.prec = 60
        D = Decimal
        capacity = (D(alpha)*D(2)**2*D(250)
                    * (1-D(Cr)*(D(2)/D(2)).sqrt())
                    * (1+D(Cc)*(D(40)/D(2)).sqrt())
                    * (1-D(Ch)*(D(92)/D(2)).sqrt()) / D('1.35'))
    assert result['status'] == 'computed'
    assert result['FRd_N'] == pytest.approx(float(capacity), rel=5e-15)
    assert result['index'] == pytest.approx(1000./float(capacity), rel=5e-15)
    assert result['domain']['loaded_flange_count'] == count
    assert result['domain']['table_location'] == location
    assert result['domain']['table_coefficients']['ri_t_max'] == rmax
    assert result['domain']['h_flat_mm'] == 92.
    assert result['domain']['transverse_stiffener_model'] == 'unstiffened_web_no_stiffener_credit'


def test_boundary_capacity_meets_and_immediately_larger_fails_only_local():
    capacity = evaluate_reaction(section(), reaction(), contact())['FRd_N']
    for demand, expected in [(capacity, 'meets'), (math.nextafter(capacity, math.inf), 'fails')]:
        result = evaluate_reaction(section(), reaction(normal_N=demand), contact())
        assert result['criterion_status'] == expected
        assert result['whole_member_approved'] is False
        assert result['global_approval'] is False
        assert result['connection_design_checked'] is False
        assert result['physical_conditions_verified'] is False


@pytest.mark.parametrize('normal', [-500., 500.])
def test_declared_web_connection_is_bilateral_and_needs_no_contact_or_connection_design(normal):
    result = evaluate_reaction(None, reaction(normal_N=normal, parallel_N=-25., moment_strong_Nmm=500.),
                               dict(route='web_connection', origin='Alma ligada à viga por detalhe declarado.'))
    assert result['status'] == result['criterion_status'] == 'exempt'
    assert result['reason_code'] == 'web_connection_9_5_1'
    assert result['reaction'] == dict(normal_N=normal, parallel_N=-25., moment_strong_Nmm=500.)
    assert result['connection_design_checked'] is False
    assert result['whole_member_approved'] is False
    assert result['physical_conditions_verified'] is False
    assert 'FRd_N' not in result and 'index' not in result


@pytest.mark.parametrize('origin', [None, '', ' ', True, 0, [], 'a'*2001])
@pytest.mark.parametrize('route', ['web_connection', 'flange_contact'])
def test_origin_is_required_for_both_routes(route, origin):
    assert_pending(evaluate_reaction(section(), reaction(), contact(route=route, origin=origin)))


@pytest.mark.parametrize('detail', [None, {}, [], True, {'route':'unknown'}, {'route':'flange_contact'}])
def test_missing_detail_does_not_invent_contact(detail):
    assert_pending(evaluate_reaction(section(), reaction(), detail))


def test_reaction_is_examined_even_without_external_point_load():
    result = evaluate_reaction(section(), reaction(P_external_N=0., normal_N=2250.), contact())
    assert result['status'] == 'computed'
    assert result['force_N'] == 2250.


@pytest.mark.parametrize('parallel', [-300., 0., 300.])
@pytest.mark.parametrize('moment', [-10000., 0., 10000., None])
def test_parallel_force_and_moment_do_not_create_nonexistent_annex_d_gate(parallel, moment):
    base = evaluate_reaction(section(), reaction(), contact())
    result = evaluate_reaction(section(), reaction(parallel_N=parallel, moment_strong_Nmm=moment), contact())
    assert result['status'] == 'computed'
    assert result['FRd_N'] == base['FRd_N'] and result['index'] == base['index']
    assert result['reaction']['parallel_N'] == result['domain']['parallel_N'] == parallel
    assert result['reaction']['moment_strong_Nmm'] == result['domain']['moment_strong_Nmm'] == moment
    assert result['moment_strong_known'] is (moment is not None)
    assert result['other_actions_checked'] is False


def test_omitted_moment_is_unknown_not_assumed_zero():
    r = reaction(); del r['moment_strong_Nmm']
    result = evaluate_reaction(section(), r, contact())
    assert result['status'] == 'computed'
    assert result['moment_strong_Nmm'] is None and result['moment_strong_known'] is False


def test_zero_normal_means_only_normal_criterion_not_applicable():
    result = evaluate_reaction(None, reaction(normal_N=0., parallel_N=100., moment_strong_Nmm=500.), None)
    assert result['status'] == 'not_applicable'
    assert result['reaction'] == dict(normal_N=0., parallel_N=100., moment_strong_Nmm=500.)
    assert result['other_actions_checked'] is False
    assert result['whole_member_approved'] is False
    assert 'index' not in result and 'FRd_N' not in result


@pytest.mark.parametrize('sign', [-1, 1])
def test_contact_is_unilateral_with_explicit_compression_sign(sign):
    d = contact(normal_compressive_sign=sign)
    valid = evaluate_reaction(section(), reaction(normal_N=sign*1000.), d)
    wrong = evaluate_reaction(section(), reaction(normal_N=-sign*1000.), d)
    assert valid['status'] == 'computed' and valid['force_N'] == 1000.
    assert valid['normal_force_N'] == sign*1000.
    assert_pending(wrong)
    assert wrong['reason_code'] == 'noncompressive_contact'
    assert wrong['loaded_flange_orientation'] == d['loaded_flange_orientation']


@pytest.mark.parametrize('sign', [None, 0, 2, -2, True, False, '1', float('nan'), float('inf')])
def test_invalid_compression_sign_never_selects_flange(sign):
    assert_pending(evaluate_reaction(section(), reaction(), contact(normal_compressive_sign=sign)))


@pytest.mark.parametrize('orientation', [True, 1, [], 'x'*2001])
def test_invalid_physical_orientation_description_stays_pending(orientation):
    assert_pending(evaluate_reaction(section(), reaction(), contact(loaded_flange_orientation=orientation)))


@pytest.mark.parametrize('orientation', [None, '', ' ', 'x'*2000])
def test_flange_description_is_optional_besides_explicit_compression_sign(orientation):
    result = evaluate_reaction(section(), reaction(), contact(loaded_flange_orientation=orientation))
    assert result['status'] == 'computed'
    assert result['loaded_flange_orientation'] == orientation


INVALID_NUMBERS = [None, True, False, '2', [], {}, float('nan'), float('inf'), -float('inf'), 10**1000]


@pytest.mark.parametrize('field', ['normal_N', 'parallel_N', 'moment_strong_Nmm'])
@pytest.mark.parametrize('value', INVALID_NUMBERS)
def test_invalid_reaction_scalars_are_not_coerced(field, value):
    if field == 'moment_strong_Nmm' and value is None:
        return
    assert_pending(evaluate_reaction(section(), reaction(**{field: value}), contact()))


@pytest.mark.parametrize('field', ['H', 't', 'ri', 'fy'])
@pytest.mark.parametrize('value', INVALID_NUMBERS)
def test_invalid_section_scalars_are_not_coerced(field, value):
    assert_pending(evaluate_reaction(section(**{field: value}), reaction(), contact()))


@pytest.mark.parametrize('field', ['c_mm', 'end_distance_mm', 'opposite_clear_distance_mm'])
@pytest.mark.parametrize('value', INVALID_NUMBERS)
def test_invalid_contact_scalars_are_not_coerced(field, value):
    d = contact(no_opposite_force=False, opposite_clear_distance_mm=200., **({field:value} if field != 'opposite_clear_distance_mm' else {}))
    d[field] = value
    assert_pending(evaluate_reaction(section(), reaction(), d))


@pytest.mark.parametrize('field', ['connected', 'no_opposite_force'])
@pytest.mark.parametrize('value', [None, 0, 1, '', 'true', []])
def test_contact_declarations_require_actual_boolean(field, value):
    assert_pending(evaluate_reaction(section(), reaction(), contact(**{field:value})))


@pytest.mark.parametrize('d', [contact(no_opposite_force=False, opposite_clear_distance_mm=None),
                              contact(no_opposite_force=True, opposite_clear_distance_mm=0.),
                              contact(no_opposite_force=False, opposite_clear_distance_mm=-1.)])
def test_opposite_force_cannot_be_inferred_or_contradictory(d):
    assert_pending(evaluate_reaction(section(), reaction(), d))


def test_no_opposite_force_and_declared_clear_distance_can_use_same_one_flange_row():
    absent = evaluate_reaction(section(), reaction(), contact())
    far = evaluate_reaction(section(), reaction(), contact(no_opposite_force=False, opposite_clear_distance_mm=138.))
    assert absent['FRd_N'] == far['FRd_N']
    assert absent['domain']['opposite_clear_distance_mm'] is None
    assert absent['domain']['classification_basis'] != far['domain']['classification_basis']


def test_figure_d1_boundaries_and_note_e_are_strict():
    # h=92 mm: 1.5h=138, 2.5h=230. Equality at 1.5h is end/one flange.
    at = evaluate_reaction(section(), reaction(), contact(end_distance_mm=138., no_opposite_force=False, opposite_clear_distance_mm=138.))
    after = evaluate_reaction(section(), reaction(), contact(end_distance_mm=math.nextafter(138., math.inf), no_opposite_force=False, opposite_clear_distance_mm=math.nextafter(138., -math.inf)))
    assert at['domain']['table_location'] == 'end' and at['domain']['loaded_flange_count'] == 1
    assert after['domain']['table_location'] == 'internal' and after['domain']['loaded_flange_count'] == 2
    for distance in [138.0001, 230.]:
        assert_pending(evaluate_reaction(section(), reaction(), contact(connected=True, end_distance_mm=distance, no_opposite_force=False, opposite_clear_distance_mm=0.)))
    just_after = evaluate_reaction(section(), reaction(), contact(connected=True, end_distance_mm=math.nextafter(230., math.inf), no_opposite_force=False, opposite_clear_distance_mm=0.))
    assert just_after['status'] == 'computed'


@pytest.mark.parametrize('theta', [0, 89.999, 90.001, None, True, '90', float('nan')])
def test_unsupported_contact_angle_is_not_repaired(theta):
    assert_pending(evaluate_reaction(section(), reaction(), contact(theta_degrees=theta)))


@pytest.mark.parametrize('s', [section(H=0.), section(t=0.), section(fy=0.), section(ri=-1.),
                              section(H=8.), section(H=7.), section(family='Z'), section(family=True), None, []])
def test_nonphysical_or_unsupported_section_is_pending(s):
    assert_pending(evaluate_reaction(s, reaction(), contact()))


@pytest.mark.parametrize('d', [contact(c_mm=0.), contact(c_mm=-1.), contact(end_distance_mm=-1.),
                              contact(c_mm=19.999), contact(c_mm=184.001)])
def test_contact_geometry_is_not_clamped(d):
    before = copy.deepcopy(d)
    assert_pending(evaluate_reaction(section(), reaction(), d))
    assert d == before


@pytest.mark.parametrize('family', ['U', 'Ue'])
def test_contact_minimum_and_web_ratio_limits(family):
    s = section(family=family, H=204., t=1., ri=1.)  # h/t=200
    assert evaluate_reaction(s, reaction(), contact(c_mm=20.))['status'] == 'computed'
    assert_pending(evaluate_reaction(dict(s, H=204.00001), reaction(), contact(c_mm=20.)))
    s = section(family=family, H=154., t=1., ri=1.)  # h=150
    assert evaluate_reaction(s, reaction(), contact(c_mm=210.))['status'] == 'computed'
    assert_pending(evaluate_reaction(s, reaction(), contact(c_mm=210.00001)))
    assert evaluate_reaction(section(family=family), reaction(), contact(c_mm=184.))['status'] == 'computed'


@pytest.mark.parametrize('connected,lip,count,location,rmax,alpha,Cr,Cc,Ch', ROWS_ORACLE)
def test_each_row_radius_limit_and_immediately_outside(connected, lip, count, location, rmax, alpha, Cr, Cc, Ch):
    # Adjust external H to retain h=92 while varying the actual radius.
    ri = rmax*2.
    s = section(family='Ue' if lip else 'U', ri=ri, H=92.+2.*(ri+2.))
    d = contact(connected=connected, no_opposite_force=False,
                opposite_clear_distance_mm=138. if count == 1 else 0.,
                end_distance_mm=0. if location == 'end' else 231.)
    assert evaluate_reaction(s, reaction(), d)['status'] == 'computed'
    s.update(ri=ri+1e-9, H=s['H']+2e-9)
    assert_pending(evaluate_reaction(s, reaction(), d))


def test_connected_unstiffened_u_has_no_d2_row_not_a_resistance_failure():
    result = evaluate_reaction(section(family='U'), reaction(), contact(connected=True))
    assert_pending(result)
    assert result['reason_code'] == 'outside_table_domain'


@pytest.mark.parametrize('s,d,r', [
    (section(H=1e308, t=1e308, ri=1e308), contact(), reaction()),
    (section(H=1e308, t=1e307, ri=0.), contact(), reaction()),
    (section(t=1e-308, ri=0.), contact(), reaction()),
    (section(fy=1e308), contact(), reaction()),
    (section(fy=1e-307), contact(), reaction(normal_N=1e308)),
    (section(fy=1e307), contact(), reaction(normal_N=1e-308)),
])
def test_unrepresentable_derived_values_remain_pending_and_json_finite(s, d, r):
    assert_pending(evaluate_reaction(s, r, d))


def test_evaluation_is_pure_and_results_do_not_alias_inputs():
    s, r, d = section(), reaction(parallel_N=125., moment_strong_Nmm=-750.), contact()
    before = copy.deepcopy((s, r, d))
    result = evaluate_reaction(s, r, d)
    assert (s, r, d) == before
    result['reaction']['normal_N'] = 999.
    result['domain']['c_mm'] = 999.
    assert (s, r, d) == before
    json.dumps(result, allow_nan=False)
