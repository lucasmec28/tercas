"""Prescribed-rotation geometry, never a corrected structural response or gate."""
import math

SCOPE = ('Diferença geométrica para rotação prescrita igual ao phi linear salvo; '
         'não estima o erro da resposta física nem resolve equilíbrio não linear.')
FIXED_DIRECTION = 'hypothetical_force_direction_fixed_in_saved_section_axes'


def _number(x):
    if type(x) not in (int, float) or not math.isfinite(x):
        raise ValueError('Finite real number required, excluding bool')
    return float(x)


def _xy(v):
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise ValueError('Two explicit components required')
    return tuple(_number(x) for x in v)


def prescribed_rotation(phi_rad, arm_mm, force_xy=None, *, force_unit=None):
    """Force option is an explicitly hypothetical fixed-direction scenario.

    No physical dead/follower classification is inferred from a saved load.
    Units are N for a point force or N/mm for a distributed force.
    """
    p = _number(phi_rad)
    x, y = _xy(arm_mm)
    s = math.sin(p)
    cm1 = -2 * math.sin(p / 2) ** 2
    # Preserve the cubic remainder rather than subtract near-identical numbers.
    smp = (p**3 * (-1/6 + p*p*(1/120-p*p/5040))
           if abs(p) < 1e-3 else s-p)
    linear = [-p*y, p*x]
    finite = [cm1*x-s*y, s*x+cm1*y]
    defect = [cm1*x-smp*y, smp*x+cm1*y]
    out = dict(scope=SCOPE, phi_prescribed_rad=p, arm_mm=[x, y],
               linear_rotation_displacement_mm=linear,
               prescribed_finite_rotation_displacement_mm=finite,
               geometric_difference_per_radius=math.hypot(cm1, smp),
               geometric_difference_mm=defect,
               geometric_difference_norm_mm=math.hypot(*defect))
    if force_xy is not None:
        if force_unit not in ('N', 'N/mm'):
            raise ValueError('Explicit force unit N or N/mm required')
        fx, fy = _xy(force_xy)
        initial = x*fy-y*fx
        change = finite[0]*fy-finite[1]*fx
        out['force_scenario'] = dict(
            hypothesis=FIXED_DIRECTION, physical_load_direction_law_established=False,
            force_xy=[fx, fy], force_unit=force_unit,
            torque_unit='Nmm' if force_unit == 'N' else 'N',
            initial_arm_torque=initial,
            prescribed_rotated_arm_torque=initial+change,
            torque_difference=change)
    elif force_unit is not None:
        raise ValueError('Force unit without force')
    values = linear + finite + defect + [out['geometric_difference_norm_mm']]
    if force_xy is not None:
        values += [initial, initial+change, change]
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Geometry result exceeds finite numerical range')
    return out



def normalized_rotation_difference(phi_rad):
    """Pure distance per radius for prescribed rotation; no saved-data reader.

    Its square has derivative 2*p*(1-cos(p)) >= 0 for p >= 0, so
    max(abs(phi)) bounds this geometry over that same saved linear field.
    """
    return prescribed_rotation(phi_rad, [1., 0.])['geometric_difference_per_radius']


def saved_maximum_twist_load_lines(result):
    """Read coherent saved source at its maximum-twist witness, without solve.

    This is not a maximum of geometric differences or torque sensitivity.
    Point forces at other stations are explicitly unavailable here. No UI or
    saved snapshot mutation. Existing reader validates input binding; where
    AISI evidence exists it additionally checks its torsion snapshot hash.
    """
    from .torsion_applicability import _saved_lines
    if _saved_lines(result) is None:
        return None
    records = []
    for rec in result['torsion_evidence']['records']:
        a = rec.get('analysis')
        if a is None:
            continue
        w = a['max_abs_phi']
        if not isinstance(a.get('member_id'), str) or not a['member_id'].strip():
            raise ValueError('Explicit saved member identity required')
        if any(w.get(k) != a.get(k) for k in ('combination_id', 'limit_state', 'member_id')):
            raise ValueError('Saved twist witness identity mismatch')
        station, length = _number(w['s_mm']), _number(a['length_mm'])
        if not 0 <= station <= length or _number(w['x_mm']) != station:
            raise ValueError('Saved twist witness station mismatch')
        sc = _xy(a['section']['properties']['shear_center_xy_mm'])
        rows, unavailable, ids = [], [], set()
        for load in a['loads']:
            name = load['name']
            if not isinstance(name, str) or not name.strip() or name in ids:
                raise ValueError('Unique saved load identity required')
            ids.add(name)
            xy = _xy(load['application_xy_mm'])
            arm = [xy[j]-sc[j] for j in (0, 1)]
            kind = load['kind']
            if kind == 'point':
                point = _number(load['s_mm'])
                if not 0 <= point <= length:
                    raise ValueError('Saved point force outside member')
                force, unit = _xy(load['force_xy_N']), 'N'
                couple, torque = _number(load['couple_Nmm']), _number(load['torque_SC_Nmm'])
            elif kind == 'uniform':
                force, unit = _xy(load['q_xy_N_mm']), 'N/mm'
                couple, torque = _number(load['couple_N']), _number(load['torque_SC_N'])
            else:
                raise ValueError('Unsupported saved action kind')
            expected = arm[0]*force[1]-arm[1]*force[0]+couple
            if not math.isclose(expected, torque, rel_tol=1e-12, abs_tol=1e-10):
                raise ValueError('Saved initial torque inconsistent with arm and force')
            if kind == 'point' and point != station:
                unavailable.append(dict(name=name, reason='No concomitant phi at point-force station in this witness'))
                continue
            rows.append(dict(name=name, kind=kind,
                direct_couple_excluded=couple,
                diagnostic=prescribed_rotation(w['phi_rad'], arm, force, force_unit=unit)))
        records.append(dict(combination_id=rec['combination_id'], limit_state=rec['limit_state'],
                            station_mm=station,
                            maximum_geometric_difference_per_radius=normalized_rotation_difference(w['phi_rad']),
                            normalized_maximum_scope='Rotation-only geometry per radius over the saved phi field; not physical response error',
                            rows=rows, unavailable=unavailable))
    return dict(scope=SCOPE, sampling='saved_maximum_twist_witness_only_not_an_envelope',
                records=records)
