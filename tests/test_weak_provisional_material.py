"""Critical provenance guard, not a new resistance formula or material rule.

The reviewed Rev07 section 5 records Pierin's E=200 GPa. Its tabulated
provisional My hypothesis must not silently survive changed elastic inputs.
Synthetic Mdist below exercises the branch; it is not a qualified critical.
"""
import copy
import pytest
from tercas.application import defaults, calculate, rows
from tercas.weak_catalog import critical_hypothesis
from tercas.weak_axis import capacities


def configured():
    d = defaults(0)
    d.update(q_uls=.01, q_parallel_uls=.01, route_domain=True,
             weak_catalog={'geometry_mode': 'catalog'},
             weak_axis=critical_hypothesis(0))
    d['segments'][0].update(Ly_effective_mm=3000., Lz_effective_mm=3000.,
                            restraint_provenance='SYNTHETIC guard test only')
    d['weak_axis']['positive']['Mdist_Nmm'] = 1e6
    d['weak_axis']['positive']['provenance'] += '; Mdist SYNTHETIC guard test only'
    return d


@pytest.mark.parametrize('E', [100000., 199999., 200001., 400000.])
def test_changed_E_does_not_reuse_provisional_catalogue_Mly(E):
    d = configured()
    d['properties']['E_MPa'] = E
    before = copy.deepcopy(d)
    cap = capacities(d, 'Ue')['positive']
    assert cap['status'] == 'not_evaluated'
    assert 'MRd_Nmm' not in cap
    assert any('E' in text and '200000' in text for text in cap['missing'])
    assert d == before


def test_original_E_keeps_the_existing_restricted_result():
    cap = capacities(configured(), 'Ue')['positive']
    assert cap['status'] == 'computed_restricted'
    assert cap['MRd_Nmm'] == pytest.approx(177272.72727272726)


def test_legacy_provisional_text_is_also_guarded():
    d = configured()
    d['weak_axis']['positive'].pop('provisional_hypothesis')
    d['properties']['E_MPa'] = 100000.
    assert capacities(d, 'Ue')['positive']['status'] == 'not_evaluated'


def test_missing_weak_critical_preserves_independent_calculations():
    d = configured()
    d['properties']['E_MPa'] = 100000.
    z = calculate(d)
    # The combined strong guard also holds inherited Ml after E changes.
    # Preserve genuinely independent shear, not a stale catalogue resistance.
    assert z['NBR_branches']['local']['status'] == 'not_evaluated'
    assert z['section_checks']['shear']['VRd_N'] > 0
    assert z['inclination_evidence']['ELU']['biaxial']['status'] == 'not_evaluated'
    row = next(r for r in rows(z) if r['Verificação'] == 'Flexão biaxial')
    assert row['Índice'] is None
    assert 'hipótese provisória' in row['Situação']
    assert not z['whole_member_approved']


def test_traceable_manual_critical_is_not_automatically_reinterpreted():
    d = configured()
    d['properties']['E_MPa'] = 100000.
    d['weak_axis']['positive'].update(provisional_hypothesis=False,
        provenance='SYNTHETIC independent critical for E=100000 MPa; not catalogue data')
    assert capacities(d, 'Ue')['positive']['status'] == 'computed_restricted'


def test_fy_change_is_not_an_elastic_modulus_change():
    d = configured()
    d['properties']['fy_MPa'] = 345.
    assert capacities(d, 'Ue')['positive']['status'] == 'computed_restricted'
