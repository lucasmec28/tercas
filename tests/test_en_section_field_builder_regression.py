"""Exact arithmetic and ownership tests for the calculation-local EN builder.

The stateless oracle is the original section_fields implementation at
ae0d90a5660eb1cabe5fb5c02e8a4b1722bffd70, before geometry preparation was hoisted.
It never calls the production builder or section_fields implementation.
Only repository profile fixtures are used; no external checkout or snapshot,
network solve, envelope refinement, or UI is involved.
"""

import copy
import json
import math
import struct
from pathlib import Path

import numpy as np
import pytest

from tercas.three_girt_en_normal import shear_interaction as actual
from tercas.torsion_vlasov.section import from_frozen_profile, verify_section


def oracle_pad(values):
    out = np.zeros(3)
    out[:len(values)] = values
    return out


def oracle_section_fields(section, polynomials, coefficients, torsion, total_torque, L_mm):
    verify_section(section)
    if not math.isfinite(L_mm) or L_mm <= 0:
        raise ValueError('Positive beam length required')
    p = section['properties']
    th = section['thickness_mm']
    J = p['J_mm4']
    Cw = p['Cw_mm6']
    xy = np.asarray(section['nodes_xy_mm'])-p['centroid_xy_mm']
    omega = np.asarray(section['omega_nodes_mm2'])/Cw
    vx = -np.polynomial.polynomial.polyder(polynomials['My'])/L_mm
    vy = np.polynomial.polynomial.polyder(polynomials['Mx'])/L_mm
    vx = oracle_pad(vx)
    vy = oracle_pad(vy)
    torque = oracle_pad(total_torque)
    h = torsion['h']
    tw = dict(h=h, B0=torsion['V']/L_mm, U=h*h*torsion['V']/L_mm, V=torsion['U']/L_mm)
    rows = []
    for i, (a, b) in enumerate(zip(xy[:-1], xy[1:])):
        d = b-a
        normal = np.array([-d[1], d[0]])/np.linalg.norm(d)
        static = np.asarray(section['segment_static_coefficients'][i])
        for face in (-1, 1):
            sigma = np.zeros((3, 3))
            sigma_scale = 0.
            w = np.array([omega[i], omega[i+1]-omega[i], 0.])
            for key, action in polynomials.items():
                if not any(action):
                    continue
                c = np.asarray(coefficients[key])
                section_power = np.array([c[0]+c[1:]@(a+face*th/2*normal), c[1:]@d, 0.])
                sigma += section_power[:, None]*oracle_pad(action)[None, :]
                face_pos = a+face*th/2*normal
                section_scale = abs(c[0])+sum(abs(c[1:]*face_pos))+sum(abs(c[1:]*d))
                sigma_scale += float(section_scale*sum(abs(v) for v in action))
            tau = -(static[0, :, None]*vx[None, :]/p['Iy_weak_mm4']+
                    static[1, :, None]*vy[None, :]/p['Ix_strong_mm4'])/th
            tau_scale = float(np.sum(abs(static[0]))*sum(abs(vx))/p['Iy_weak_mm4']/th+
                              np.sum(abs(static[1]))*sum(abs(vy))/p['Ix_strong_mm4']/th+th/J*sum(abs(torque)))
            tau[0] -= face*th/J*torque
            v = -static[2]/(Cw*th)
            v = v.copy()
            v[0] += face*th/J
            rows.append(dict(segment_index=i, face=face, sigma=sigma, omega=w,
                             tau=tau, tw_weight=v, normal_xy=normal.tolist(),
                             sigma_roundoff_scale=sigma_scale, tau_roundoff_scale=tau_scale,
                             tw_roundoff_scale=float(np.sum(abs(static[2]))/(Cw*th)+th/J),
                             xy_start=a+face*th/2*normal, xy_delta=d))
    return rows, tw


def bitwise(value):
    if isinstance(value, np.ndarray):
        return 'array', value.dtype.str, value.shape, value.tobytes()
    if type(value) is float or isinstance(value, np.floating):
        return type(value).__name__, struct.pack('!d', value)
    if isinstance(value, dict):
        return 'dict', tuple((key, bitwise(val)) for key, val in value.items())
    if isinstance(value, (tuple, list)):
        return type(value).__name__, tuple(bitwise(val) for val in value)
    return type(value).__name__, value


def load_section(thickness):
    path = Path(actual.__file__).resolve().parents[1]/'data'/'torsion_profiles'/f'ue100x50x17_t{thickness:.2f}.json'
    return from_frozen_profile(json.loads(path.read_text()))


def cases():
    yield (dict(N=[0.], Mx=[0.], My=[0.]), {}, dict(h=0., B0=0., U=0., V=0.), [0.], 1333.3333333333333)
    yield (dict(N=[100.], Mx=[1e4, -2e4, 3e4], My=[-3e4, 4e4, -2e4]),
           dict(N=[.001, 1e-7, -2e-7], Mx=[1e-5, -2e-6, 4e-6], My=[-1e-5, 3e-6, -5e-6]),
           dict(h=2.7, B0=1e5, U=-3e5, V=2e5), [10000., -17000.], 1333.3333333333335)
    yield (dict(N=[-0.], Mx=[-0., 2e4], My=[5e4, -1e5, 5e4]),
           dict(Mx=[-0., 2e-6, -3e-6], My=[1e-5, -2e-6, 4e-6]),
           dict(h=-0., B0=-0., U=2e5, V=-0.), [-0., 2e3], 4000.)
    yield (dict(My=[1e4, 2e4], N=[-100.], Mx=[1e5, -2e5, 1e5]),
           dict(N=[.002, -2e-7, 1e-7], Mx=[2e-5, 3e-6, -4e-6], My=[-3e-5, 1e-6, 2e-6]),
           dict(h=10., B0=-1e8, U=2e8, V=-3e8), [4e6, -2e6], 4000.)


@pytest.mark.parametrize('thickness', [1.2, 2.65, 3.35])
def test_builder_and_public_path_match_original_arrays_bit_for_bit(thickness):
    section = load_section(thickness)
    before = copy.deepcopy(section)
    build = actual.section_field_builder(section)
    for args in cases():
        args_before = copy.deepcopy(args)
        expected = bitwise(oracle_section_fields(section, *args))
        assert bitwise(build(*args)) == expected
        assert bitwise(actual.section_fields(section, *args)) == expected
        assert args == args_before
    assert section == before


def test_builder_owns_frozen_section_and_public_path_still_revalidates():
    section = load_section(1.2)
    build = actual.section_field_builder(section)
    args = list(cases())[1]
    expected = bitwise(oracle_section_fields(section, *args))
    section['properties']['J_mm4'] *= 2
    section['nodes_xy_mm'][0][0] += 100
    section['omega_nodes_mm2'][0] += 100
    section['segment_static_coefficients'][0][0][0] += 100
    assert bitwise(build(*args)) == expected
    with pytest.raises(ValueError, match='Constructed coherent section changed'):
        actual.section_fields(section, *args)
    with pytest.raises(ValueError, match='Constructed coherent section changed'):
        actual.section_field_builder(section)


def test_no_returned_array_or_list_can_modify_builder_or_another_call():
    section = load_section(1.2)
    build = actual.section_field_builder(section)
    args = list(cases())[1]
    first = build(*args)
    second = build(*args)
    expected = bitwise(second)
    for a, b in zip(first[0], second[0]):
        for key, value in a.items():
            if isinstance(value, np.ndarray):
                assert not np.shares_memory(value, b[key]), key
                value[...] = 987654321.
            elif isinstance(value, list):
                assert value is not b[key], key
                value[0] = 987654321.
    first[1]['U'] = 987654321.
    assert bitwise(second) == expected
    assert bitwise(build(*args)) == expected


@pytest.mark.parametrize('length', [0., -1., math.nan, math.inf])
def test_builder_rejects_invalid_length_without_poisoning_next_call(length):
    section = load_section(1.2)
    build = actual.section_field_builder(section)
    args = list(cases())[1]
    with pytest.raises(ValueError, match='Positive beam length required'):
        build(*args[:-1], length)
    assert bitwise(build(*args)) == bitwise(oracle_section_fields(section, *args))
