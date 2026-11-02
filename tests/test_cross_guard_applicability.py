"""Independent integration review: provenance warnings are not blanket demands."""
import copy
import json
from tercas.application import defaults, calculate
from tercas.weak_axis import strong_capacity


def case(index=19):
    d = defaults(index)
    d.update(q_uls=.01, q_parallel_uls=.01, route_domain=True,
             Ml_Nmm=1234567.,
             critical_origin='SYNTHETIC independent Ml for E100000; Mdist table is not used when exempt')
    d['properties']['E_MPa'] = 100000.
    d['segments'][0].update(Ly_effective_mm=3000., Lz_effective_mm=3000.,
                            restraint_provenance='SYNTHETIC integration review')
    weak = dict(W_mm3=10000., Wc_mm3=20000., Ml_Nmm=4e6,
                Mdist_Nmm=5e6, Nex_N=1e6, Nez_N=1e6, r0_mm=20.,
                j_mm=-10., Cm=1., Cs=1, provisional_hypothesis=False,
                provenance='SYNTHETIC independent weak criticals, same axis and E100000')
    d['weak_axis'] = {'positive': weak, 'negative': copy.deepcopy(weak)}
    return d


def test_exempt_distortion_does_not_create_an_extra_critical_requirement():
    d = case()
    r = calculate(d)
    assert r['NBR_branches']['distortional']['status'] == 'exempt_Table14'
    assert r['NBR_branches']['local']['MRd_Nmm'] > 0
    assert r['strong_critical_qualification']['fields']['Mdist']['status'] == 'not_evaluated_incompatible_elastic_inputs'
    assert r['input_snapshot']['Mdist']['value'] is None
    assert strong_capacity(r) is not None
    assert r['inclination_evidence']['ELU']['biaxial']['status'] == 'computed_fixed_position'
    assert not r['whole_member_approved']


def test_required_distortion_stays_pending():
    r = calculate(case(0))
    assert r['NBR_branches']['distortional']['status'] == 'not_evaluated'
    assert strong_capacity(r) is None
    assert 'strong' in r['inclination_evidence']['ELU']['biaxial']['missing']


def test_real_coverage_gap_still_blocks_even_when_distortion_is_exempt():
    d = case()
    d['segments'][0]['end_mm'] = 1500.
    r = calculate(d)
    assert r['NBR_branches']['distortional']['status'] == 'exempt_Table14'
    assert r['coverage_warnings']
    assert strong_capacity(r) is None


def test_json_roundtrip_does_not_restore_held_critical():
    d = case()
    r = calculate(json.loads(json.dumps(d)))
    assert r['input_data'] == d
    assert r['input_snapshot']['Mdist']['value'] is None
    assert r['strong_critical_qualification']['fields']['Mdist']['inherited_tabulated']


def test_manual_weak_inputs_do_not_remove_strong_table_guard():
    d = case(0)
    d['Ml_Nmm'] = defaults(0)['Ml_Nmm']
    r = calculate(d)
    assert r['inclination_evidence']['ELU']['weak_axis_capacities']['positive']['status'] == 'computed_restricted'
    assert r['input_snapshot']['Ml']['value'] is None
    assert r['input_snapshot']['Mdist']['value'] is None
    assert 'strong' in r['inclination_evidence']['ELU']['biaxial']['missing']
