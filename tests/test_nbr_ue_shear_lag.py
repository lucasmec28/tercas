"""Scalar applicability tests: no section builder, solver, UI or network."""
import copy
from fractions import Fraction as F
import json
import math

import pytest

from tercas import nbr_ue_shear_lag as lag
from tercas import pierin_ue_registry as registry


DIMS = dict(h=200., bf=75., lip=20., t=2.)


def uniform(normal=1., parallel=0.):
    return dict(kind='uniform', q_down_N_mm=normal, q_parallel_N_mm=parallel)


def point(normal=1., parallel=0., s=500.):
    return dict(kind='point', P_down_N=normal, P_parallel_N=parallel, s_mm=s)


def inputs(actions=None, L=1000., dims=None):
    return dict(physical_span_mm=L, external_dimensions_mm=DIMS if dims is None else dims,
                actions=[uniform()] if actions is None else actions, member_model=lag.MEMBER_MODEL)


@pytest.mark.parametrize('actions', [[], [uniform()], [uniform(-1., 2.)],
                                   [uniform(), uniform(-1.)], [uniform(), point(0.)]])
def test_no_applied_point_force_does_not_invent_reactions_or_require_long_span(actions):
    e = lag.assess(**inputs(actions, L=1000.))
    assert e['qualified']
    assert all(a['status'] == 'not_triggered_no_concentrated_action' for a in e['axes'].values())
    assert not e['axes']['normal']['sufficient_span_proved']
    assert not e['support_reactions_invented']


@pytest.mark.parametrize('P', [1., -1., 1e-300, -1e-300])
def test_short_strong_point_force_pending_for_both_signs_without_epsilon(P):
    e = lag.assess(**inputs([point(P)]))
    assert not e['qualified'] and not e['axes']['normal']['qualified']
    assert e['axes']['parallel']['qualified']
    assert e['axes']['normal']['status'] == 'pending_shear_lag_qualification'
    assert not e['axes']['normal']['normative_reduction_required_demonstrated']
    assert not e['reductions_applied'] and not e['whole_member_approved']


@pytest.mark.parametrize('L, expected', [(2250., False), (2849., False), (2850., True), (2851., True)])
def test_strong_majorant_includes_lip_and_equality_is_allowed(L, expected):
    e = lag.assess(**inputs([point()], L=L))
    assert e['qualified'] is expected
    a = e['axes']['normal']
    assert a['bf0_upper_mm'] == 95.
    assert a['sufficient_span_exact_mm'] == '2850'
    assert not a['bf0_exact_determined']


@pytest.mark.parametrize('L, expected', [(2850., False), (5999., False), (6000., True), (6001., True)])
def test_weak_point_force_uses_original_web_lips_and_flange_envelope(L, expected):
    e = lag.assess(**inputs([point(0., 1.)], L=L))
    assert e['qualified'] is expected
    assert e['axes']['normal']['qualified']
    assert e['axes']['parallel']['bf0_upper_mm'] == 200.
    assert 'sem crédito de metade' in e['axes']['parallel']['width_bound_proof']


def test_weak_bound_keeps_flange_lip_when_it_exceeds_web_height():
    e = lag.assess(**inputs([point(0., 1.)], L=4200., dims=dict(h=100., bf=120., lip=20., t=2.)))
    assert e['axes']['parallel']['bf0_upper_mm'] == 140. and e['qualified']


@pytest.mark.parametrize('actions', [[uniform(-.001), point()], [point(), point(-1.)],
                                   [point(s=1.), point(-1., s=2.)]])
def test_uniform_resultant_or_opposing_points_do_not_erase_individual_P(actions):
    e = lag.assess(**inputs(actions))
    assert not e['qualified']
    assert e['individual_actions_before_cancellation']
    assert not e['multiple_point_spacing_exemption_used']
    assert len(e['axes']['normal']['concentrated_action_indices']) == sum(a['kind'] == 'point' for a in actions)


@pytest.mark.parametrize('s', [0., 1000.])
def test_applied_point_at_support_does_not_claim_unimplemented_exemption(s):
    e = lag.assess(**inputs([point(s=s)]))
    assert not e['qualified']


def test_near_boundary_is_exact_not_rounded_or_tolerance_based():
    threshold = 2850.
    assert not lag.assess(**inputs([point()], L=math.nextafter(threshold, -math.inf)))['qualified']
    assert lag.assess(**inputs([point()], L=threshold))['qualified']


def test_binary_float_geometry_is_compared_as_exact_rationals():
    dims = dict(h=200., bf=75.1, lip=20.2, t=2.)
    threshold = 30*(F(dims['bf']) + F(dims['lip']))
    L = float(threshold)
    e = lag.assess(**inputs([point()], L=L, dims=dims))
    assert e['axes']['normal']['qualified'] is (F(L) >= threshold)
    assert F(e['axes']['normal']['sufficient_span_upper_mm']) >= threshold
    assert e['axes']['normal']['sufficient_span_exact_mm'] == str(threshold)


@pytest.mark.parametrize('index', registry.new_study_indices())
def test_each_complete_documentary_Ue_has_scalar_q_and_P_proofs(index):
    row = registry.select_new_study(index, include_routes=False)
    dims = row['dimensions_mm']
    threshold = 30*max(F(dims['h']), F(dims['bf']) + F(dims['lip']))
    L = float(threshold)
    if F(L) < threshold:
        L = math.nextafter(L, math.inf)
    both = [point(1., -1., s=L/2)]
    passed = lag.assess(**inputs(both, L=L, dims=dims))
    assert passed['qualified'] and all(a['qualified'] for a in passed['axes'].values())
    short = lag.assess(**inputs([point(1., -1., s=5.)], L=10., dims=dims))
    assert not short['qualified']
    assert lag.assess(**inputs([uniform(1., -1.)], L=10., dims=dims))['qualified']


@pytest.mark.parametrize('change', [
    lambda p: p.update(physical_span_mm=0.),
    lambda p: p.update(physical_span_mm=float('nan')),
    lambda p: p.update(physical_span_mm=True),
    lambda p: p.update(member_model='continuous'),
    lambda p: p.update(member_model='cantilever'),
    lambda p: p.update(actions=None),
    lambda p: p.update(actions=[dict(kind='moment')]),
    lambda p: p.update(actions=[dict(kind='uniform', q_down_N_mm=1.)]),
    lambda p: p.update(actions=[point(float('inf'))]),
    lambda p: p.update(actions=[point(s=-1.)]),
    lambda p: p.update(actions=[point(s=1001.)]),
    lambda p: p.update(actions=[point(s=True)]),
    lambda p: p['external_dimensions_mm'].pop('lip'),
    lambda p: p['external_dimensions_mm'].update(lip=0.),
    lambda p: p['external_dimensions_mm'].update(t=20.),
    lambda p: p['external_dimensions_mm'].update(h=40.),
])
def test_malformed_or_outside_member_model_cannot_be_silently_qualified(change):
    params = copy.deepcopy(inputs())
    change(params)
    with pytest.raises(ValueError):
        lag.assess(**params)


def test_pure_detached_json_roundtrip_replay_without_mutation():
    params = inputs([uniform(), point(-1., .1)], L=6000.)
    before = copy.deepcopy(params)
    e = lag.assess(**params)
    assert params == before
    assert lag.validate_saved(json.loads(json.dumps(e, allow_nan=False)), **params) == e
    assert not e['demands_changed'] and not e['section_properties_changed']
    e['external_dimensions_mm']['bf'] = 1.
    assert params == before


@pytest.mark.parametrize('mutation', [
    lambda e: e.update(qualified=True),
    lambda e: e['axes']['normal'].update(qualified=True),
    lambda e: e['axes']['normal'].update(sufficient_span_exact_mm='10'),
    lambda e: e['action_inventory'][0].update(normal_exact='0'),
    lambda e: e.update(reductions_applied=True),
])
def test_saved_proof_tampering_rejected(mutation):
    params = inputs([point()])
    e = lag.assess(**params)
    mutation(e)
    with pytest.raises(ValueError, match='salvo diverge'):
        lag.validate_saved(e, **params)


def test_changed_live_actions_geometry_or_physical_span_invalidates_saved_proof():
    params = inputs([point()])
    e = lag.assess(**params)
    for change in (dict(physical_span_mm=6000.), dict(actions=[uniform()]),
                   dict(external_dimensions_mm=dict(DIMS, lip=21.))):
        with pytest.raises(ValueError, match='salvo diverge'):
            lag.validate_saved(e, **dict(params, **change))
