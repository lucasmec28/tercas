"""Integration contract: uniaxial scope sees final PP-inclusive SLS loads."""
import copy
import math

import pytest

from tercas import direct_self_weight as pp, deflection_scope as scope
from tercas import ue_reference as single, ue_family_reference as family
from tercas.application import calculate, example
from tercas.batch import calculate_batch


@pytest.mark.parametrize('t', [1.2, *family.THICKNESSES])
@pytest.mark.parametrize('angle', [-30., 0., 30.])
def test_pp_can_cross_gross_elastic_boundary_and_guard_must_use_total(t, angle):
    d = single.load_reference(L_mm=4000., angle=angle) if t == 1.2 else family.load_reference(t, 4000., angle)
    d = scope.activate(pp.activate(d))
    d.update(load_mode='direct', P_sls=0., q_parallel_sls=.01)
    p = d['properties']
    q_yield = p['fy_MPa']*p['Wx_cm3']*1000*8/d['L_mm']**2
    pp_normal = p['mass_kg_m']*9.80665/1000*math.cos(math.radians(angle))
    d['q_sls'] = q_yield-pp_normal/2
    before = copy.deepcopy(d)
    r = calculate(d)
    g = r['ELS']['local_uniaxial_component']['gross_elastic_guard']
    assert d == before and r['input_data'] == d
    assert r['input_snapshot']['SLS']['q_Nmm'] == pytest.approx(q_yield+pp_normal/2)
    assert d['q_sls'] < q_yield
    assert g['max_abs_M_Nmm'] == pytest.approx((q_yield+pp_normal/2)*d['L_mm']**2/8)
    assert g['sigma_gross_max_MPa'] > p['fy_MPa']
    assert g['passed'] is False and r['ELS'].get('index') is None
    assert r['ELS']['criterion_status'] == 'gross_elastic_model_exceeded'
    assert r['ELS']['local_uniaxial_component']['q_vector_N_mm'] == r['inclination_evidence']['ELS']['q_vector']


def test_girt_vertical_pp_does_not_change_the_horizontal_component():
    d = scope.activate(example())
    d.update(member_application='wall_girt', q_sls=.1, P_sls=0., q_parallel_sls=.02)
    old = calculate(d)
    r = calculate(pp.activate(d))
    assert r['ELS']['local_uniaxial_component']['gross_elastic_guard'] == old['ELS']['local_uniaxial_component']['gross_elastic_guard']
    assert r['ELS']['deflection_mm'] == old['ELS']['deflection_mm']
    assert r['inclination_evidence']['ELS']['q_vector']['parallel'] > old['inclination_evidence']['ELS']['q_vector']['parallel']


def test_area_mode_does_not_apply_direct_pp_twice_to_uniaxial_scope():
    d = scope.activate(single.load_reference(L_mm=4000.))
    old = calculate_batch(d)
    r = calculate_batch(pp.activate(d))
    assert r['cases'] == old['cases']
