"""Synthetic pure-component applicability, no eigen/member/UI analysis."""
import copy
import pytest
from test_ue_catalog_nbr_weak_annex_e import reference_data
from test_ue_catalog_nbr_weak_mle import data
from tercas import ue_catalog_nbr_weak_positive as pos
from tercas import ue_catalog_reference as own


def qualify(data):
    return pos.qualify_reference(data, sign='positive', axial_force_N=0.)


def test_typed_decision_and_proof(reference_data):
    before = copy.deepcopy(reference_data)
    c = qualify(reference_data)
    d = c['distortional_applicability']
    assert d['Mdist_Nmm'] is None and d['MRdD_Nmm'] is None
    assert not d['T14_exemption'] and not d['roof_distortional_restraint_credit']
    p = d['proof']
    assert p['centroid_x_upper_mm'] == pytest.approx(17.793314, abs=1e-6)
    assert p['connecting_bend_tension_distance_lower_mm'] > 26
    assert p['lip_tension_distance_lower_mm'] > 29
    assert c['MRd_positive_reference_Nmm'] == min(c['MRd_local_Nmm'], c['MRd_FLT_reference_component_Nmm'])
    assert c['MRd_positive_reference_Nmm'] == pytest.approx(1351021.88664031)
    assert c['considered_components'] == ['local_first_yield', 'FLT_reference']
    assert 'governing_components' not in c
    assert 'MRd_Nmm' not in c and c['real_action_applicability'] == 'not_assessed'
    for k in ('actual_load_capacity_qualified','combined_state_distortion_assessed',
              'interaction_9_9_qualified','primary_torsion_assessed','ELS_qualified',
              'global_properties_modified','whole_member_approved'):
        assert c[k] is False
    assert reference_data == before
    assert pos.validate_saved(c, reference_data) == c


@pytest.mark.parametrize('sign', ['negative', 'zero', '', None, 1, True])
def test_wrong_sign(reference_data, sign):
    with pytest.raises(ValueError):
        pos.qualify_reference(reference_data, sign=sign, axial_force_N=0.)


@pytest.mark.parametrize('force', [1., -1., True, None, '0', float('nan'), float('inf')])
def test_not_pure(reference_data, force):
    with pytest.raises(ValueError):
        pos.qualify_reference(reference_data, sign='positive', axial_force_N=force)


@pytest.mark.parametrize('field,value', [('Mdist_Nmm',0.),('MRdD_Nmm',1e100),
    ('T14_exemption',True),('combined_stress_state_covered',True),('sign','negative'),
    ('physical_section_verified',True)])
def test_rehashed_decision_rejected(reference_data, field, value):
    c = qualify(reference_data)
    c['distortional_applicability'][field] = value
    c['snapshot_sha256'] = own.digest({k:v for k,v in c.items() if k != 'snapshot_sha256'})
    with pytest.raises(ValueError):
        pos.validate_saved(c, reference_data)


def test_rehashed_proof_scope_and_number_bool(reference_data):
    for path, value in [(('distortional_applicability','proof','centroid_x_upper_mm'),48.),
            (('MRd_positive_reference_Nmm',),1e12),
            (('domain','axial_force_N'),False),
            (('distortional_applicability','sources'),[])]:
        c = qualify(reference_data)
        target = c
        for key in path[:-1]: target = target[key]
        target[path[-1]] = value
        c['snapshot_sha256'] = own.digest({k:v for k,v in c.items() if k != 'snapshot_sha256'})
        with pytest.raises(ValueError): pos.validate_saved(c, reference_data)


def test_changed_material_geometry_span_and_missing_marker(reference_data):
    c = qualify(reference_data)
    for key, value in [('fy_MPa',350.), ('Iy_cm4',999.)]:
        altered = copy.deepcopy(reference_data)
        altered['properties'][key] = value
        with pytest.raises(ValueError): pos.validate_saved(c, altered)
    changed = copy.deepcopy(reference_data)
    changed['L_mm'] *= 2
    with pytest.raises(ValueError): pos.validate_saved(c, changed)
    reference_data.pop('ue_catalog_reference')
    assert qualify(reference_data) is None
    with pytest.raises(ValueError): pos.validate_saved(c, reference_data)


def test_infinite_fake_D_rejected(reference_data):
    c = qualify(reference_data)
    c['distortional_applicability']['MRdD_Nmm'] = float('inf')
    with pytest.raises(ValueError): pos.validate_saved(c, reference_data)
