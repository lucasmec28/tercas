"""Pure synthetic geometry and saved-reader checks, no structural solver."""
import copy
import math
import pytest
from tercas.rotation_geometry_diagnostic import prescribed_rotation, saved_maximum_twist_load_lines
from test_torsion_applicability import saved_result, no_solver


@pytest.mark.parametrize('phi', [0., math.pi/2, -math.pi/2, math.pi, -math.pi, 7.])
def test_prescribed_coordinates(phi):
    r = prescribed_rotation(phi, [3., 4.])
    expected = [3*math.cos(phi)-4*math.sin(phi)-3, 3*math.sin(phi)+4*math.cos(phi)-4]
    assert r['prescribed_finite_rotation_displacement_mm'] == pytest.approx(expected)
    assert r['geometric_difference_mm'] == pytest.approx([expected[0]+4*phi, expected[1]-3*phi])
    assert 'erro da resposta física' in r['scope']


def test_small_rotation_remainder():
    p = 1e-9
    r = prescribed_rotation(p, [1., 0.])
    assert r['geometric_difference_mm'][0] == pytest.approx(-p*p/2, rel=1e-12, abs=0)
    assert r['geometric_difference_mm'][1] == pytest.approx(-p**3/6, rel=1e-12, abs=0)


@pytest.mark.parametrize('unit,torque_unit', [('N','Nmm'), ('N/mm','N')])
def test_zero_initial_torque_becomes_nonzero(unit, torque_unit):
    d = prescribed_rotation(math.pi/2, [2., 0.], [3., 0.], force_unit=unit)['force_scenario']
    assert d['initial_arm_torque'] == 0
    assert d['prescribed_rotated_arm_torque'] == pytest.approx(-6)
    assert d['torque_unit'] == torque_unit
    assert d['physical_load_direction_law_established'] is False


def test_covariance_and_no_mutation():
    arm, force = [3., 4.], [6., -2.]
    old = copy.deepcopy([arm, force])
    a = prescribed_rotation(.4, arm, force, force_unit='N')
    b = prescribed_rotation(.4, [-4., 3.], [2., 6.], force_unit='N')
    assert b['geometric_difference_mm'] == pytest.approx([-a['geometric_difference_mm'][1], a['geometric_difference_mm'][0]])
    assert b['force_scenario']['torque_difference'] == pytest.approx(a['force_scenario']['torque_difference'])
    assert [arm, force] == old


@pytest.mark.parametrize('bad', [True, float('nan'), float('inf'), '1'])
def test_invalid_number(bad):
    with pytest.raises(ValueError): prescribed_rotation(bad, [1., 0.])
    with pytest.raises(ValueError): prescribed_rotation(1., [bad, 0.])


@pytest.mark.parametrize('kwargs', [{'force_unit':'N'}, {'force_xy':[1,2]}, {'force_xy':[1,2], 'force_unit':'kN'}])
def test_units_fail_closed(kwargs):
    with pytest.raises(ValueError): prescribed_rotation(.2, [1,2], **kwargs)


def rich_saved():
    r = saved_result(with_aisi=False)
    for rec in r['torsion_evidence']['records']:
        a = rec['analysis']; a['member_id'] = 'synthetic'
        a['max_abs_phi'].update(member_id='synthetic', combination_id=a['combination_id'], limit_state=a['limit_state'], s_mm=1800.)
        a['section'] = {'properties': {'shear_center_xy_mm':[0., 0.]}}
        a['loads'] = [dict(name='q', kind='uniform', application_xy_mm=[2., 0.], q_xy_N_mm=[3., 0.], couple_N=4., torque_SC_N=4.),
                      dict(name='P', kind='point', application_xy_mm=[2., 0.], force_xy_N=[3., 0.], s_mm=1000., couple_Nmm=0., torque_SC_Nmm=0.)]
    return r


def test_saved_concomitance_and_preservation():
    r = rich_saved(); before = copy.deepcopy(r)
    out = saved_maximum_twist_load_lines(r)
    assert r == before
    assert len(out['records']) == 2
    row = out['records'][0]
    assert row['station_mm'] == 1800.
    assert len(row['rows']) == 1 and row['unavailable'][0]['name'] == 'P'
    assert row['rows'][0]['direct_couple_excluded'] == 4.
    assert row['rows'][0]['diagnostic']['force_scenario']['initial_arm_torque'] == 0
    assert 'not_an_envelope' in out['sampling']


def test_concomitant_point():
    r = rich_saved()
    for rec in r['torsion_evidence']['records']: rec['analysis']['loads'][1]['s_mm'] = 1800.
    assert len(saved_maximum_twist_load_lines(r)['records'][0]['rows']) == 2


@pytest.mark.parametrize('bad', ['station','identity','torque','source','sc','point','duplicate'])
def test_bad_saved_source(bad):
    r = rich_saved(); a = r['torsion_evidence']['records'][0]['analysis']
    if bad == 'station': a['max_abs_phi']['s_mm'] = 10.
    if bad == 'identity': a['max_abs_phi']['member_id'] = 'other'
    if bad == 'torque': a['loads'][0]['torque_SC_N'] = 3.
    if bad == 'source': r['input_data']['L_mm'] += 1
    if bad == 'sc': a['section']['properties']['shear_center_xy_mm'][0] = float('nan')
    if bad == 'point': a['loads'][1]['s_mm'] = -1.
    if bad == 'duplicate': a['loads'][1]['name'] = 'q'
    with pytest.raises(ValueError): saved_maximum_twist_load_lines(r)


def test_no_saved_evidence():
    assert saved_maximum_twist_load_lines({}) is None


def test_zero_arm_force_and_large_output_rejected():
    assert prescribed_rotation(7., [0., 0.])['geometric_difference_norm_mm'] == 0
    d = prescribed_rotation(2., [4., 5.], [0., 0.], force_unit='N')['force_scenario']
    assert d['torque_difference'] == 0
    with pytest.raises(ValueError): prescribed_rotation(1e308, [1e308, 0.])


def test_torque_as_potential_derivative():
    # Potential V=-F dot Rr; torque=-dV/dphi. Independent finite difference.
    p, h, x, y, fx, fy = .4, 1e-6, 2., 3., 4., -5.
    def potential(t):
        return -(fx*(x*math.cos(t)-y*math.sin(t)) + fy*(x*math.sin(t)+y*math.cos(t)))
    q = prescribed_rotation(p, [x,y], [fx,fy], force_unit='N')['force_scenario']
    assert q['prescribed_rotated_arm_torque'] == pytest.approx(-(potential(p+h)-potential(p-h))/(2*h), rel=1e-9)


def test_normalized_difference_independent_of_point_and_monotone():
    previous = -1
    for p in (0., 1e-8, .1, 1., math.pi, 2*math.pi, 7., 20.):
        a = prescribed_rotation(p, [3., 4.])
        b = prescribed_rotation(-p, [-5., 12.])
        n = a['geometric_difference_per_radius']
        assert n >= previous
        assert a['geometric_difference_norm_mm'] == pytest.approx(5*n, abs=1e-30)
        assert b['geometric_difference_per_radius'] == n
        previous = n
