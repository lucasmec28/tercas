"""Sufficient EN 1993-1-3:2006 6.1.6 stress check for an isolated Vlasov field.

Optional backend with explicit app integration since schema v2. NOT an
AISI/NBR resistance or whole-member check. Uses EN pure effective sections and the
existing recovered polynomial demand. No new beam solver or buckling model.

The convex norm of common-degree tensor Bernstein controls gives an upper
bound over every element, wall segment and face. Both signed effective-section
operators are included: this may overestimate, but never removes a needed
sign at a root. A bound above one is inconclusive, never proven failure.
"""
import copy
import hashlib
import itertools
import json
import math

import numpy as np

from .three_girt_en_normal.en1993_normal_components import build_component_sections
from .torsion_vlasov.section import from_frozen_profile, verify_section
from .torsion_vlasov.intervals import Interval as I, stack, power_to_bernstein, elevate_bernstein
from .torsion_vlasov.yield_envelope import _member_polynomials

SCHEMA = 'isolated_EN_6_1_6_sufficient_stress_bounds_v2'


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode()).hexdigest()


def stress_norm(sigma, tau):
    squared = sigma.square() + 3 * tau.square()
    return I(np.maximum(0., squared.lo), np.maximum(0., squared.hi)).sqrt()


def _support_limit_guard(demand):
    points = [a for a in demand['loads'] if a['kind'] == 'point']
    scope = demand.get('analysis_domain', {}).get('point_position_scope', '')
    declared = scope.startswith(('Prescribed a->0+', 'Prescribed a→0+')) or any(
        a.get('existing_point_position') == 'support_limit' for a in points)
    states = demand.get('support_limit_states', [])
    if not isinstance(states, list) or any(not isinstance(x, dict) for x in states):
        raise ValueError('Explicit list of support-limit states required')
    if declared:
        from .torsion_vlasov.adapter import support_limit_before_point
        if len(points) != 1 or points[0]['s_mm'] != 0.:
            raise ValueError('Declared support limit requires one left-support point')
        expected = support_limit_before_point(demand)
        # The established area adapter appends this scope note AFTER recovering
        # before-P. Compare every state value, ignoring only that later note.
        actual = copy.deepcopy(states)
        for state in actual + [expected]:
            state.get('analysis_domain', {}).pop('point_position_scope', None)
        if actual != [expected]:
            raise ValueError('Declared support limit requires its complete coherent before-P state')
    elif states:
        raise ValueError('Support-limit states require an explicit a->0+ source convention')
    else:
        for action in points:
            if action['s_mm'] in (0., demand['length_mm']) and action.get('existing_point_position') != 'fixed':
                raise ValueError('Endpoint point needs explicit fixed-position or a->0+ semantics')


def _validate(demand, profile, intact_section_model_declared, model_origin):
    if intact_section_model_declared is not True or not isinstance(model_origin, str) or not model_origin.strip():
        raise ValueError('Explicit intact-section declaration and model origin required')
    if demand.get('schema') != 'single_vlasov_member_demand_v1' or demand.get('limit_state') != 'ELU':
        raise ValueError('Complete isolated Vlasov ELU field required')
    if demand.get('numerics', {}).get('qualification_passed') is not True:
        raise ValueError('Numerically qualified Vlasov field required')
    axial = demand.get('analysis_domain', {}).get('axial_force_in_this_model_N')
    if isinstance(axial, bool) or axial != 0:
        raise ValueError('This isolated source contract is N=0; axial force is not discarded')
    verify_section(demand['section'])
    if demand['section'] != from_frozen_profile(profile):
        raise ValueError('Demand and EN effective sections must use the exact same frozen contour')
    elements = demand.get('elements', [])
    if not elements or len(elements) * (len(demand['section']['nodes_xy_mm']) - 1) * 2 > 100000:
        raise ValueError('Missing field or numerical resource budget exceeded')
    previous = 0.
    for element in elements:
        a, b = element['a_mm'], element['b_mm']
        if isinstance(a, bool) or isinstance(b, bool) or not all(math.isfinite(x) for x in (a, b)) or a != previous or b <= a:
            raise ValueError('Complete ordered continuous element coverage required')
        previous = b
    if previous != demand['length_mm']:
        raise ValueError('Element coverage does not span the whole member')
    _support_limit_guard(demand)
    return build_component_sections(profile)


def _field_controls(demand, certificate):
    """Yield signed-operator supersets; no fictitious control is a witness."""
    pol, identities = _member_polynomials(demand)
    section = demand['section']; p = section['properties']; th = section['thickness_mm']
    nodes = I(section['nodes_xy_mm']); xy = nodes - I(p['centroid_xy_mm'])
    delta = nodes[1:] - nodes[:-1]
    length = (delta[:, 0].square() + delta[:, 1].square()).sqrt()
    normal = stack([-delta[:, 1] / length, delta[:, 0] / length], axis=-1)
    omega = I(section['omega_nodes_mm2'])
    w = stack([omega[:-1], omega[1:] - omega[:-1]], axis=-1)
    static = I(section['segment_static_coefficients'])
    def outer(a, b):
        return a[:, None, :, None] * b[None, :, None, :]
    flow = -(outer(pol['Vx'] / p['Iy_weak_mm4'], static[:, 0, :])
        + outer(pol['Vy'] / p['Ix_strong_mm4'], static[:, 1, :])
        + outer(pol['Tw'] / p['Cw_mm6'], static[:, 2, :])) / th
    constant = I(np.column_stack([np.ones(len(xy.lo) - 1), np.zeros((len(xy.lo) - 1, 2))]))
    sv = outer(pol['Tsv'] * th / p['J_mm4'], constant)
    for signs in itertools.product(('positive', 'negative'), repeat=2):
        selected = dict(Mx='Mx_' + signs[0], My='My_' + signs[1])
        coefficients = {}
        for action, key in selected.items():
            component = certificate['components'][key]
            if not component['eligible']:
                raise ValueError('EN signed effective section unavailable: ' + key)
            coefficients[action] = I(component['sigma_coefficients_c0_cx_cy'])
        for face in (-1, 1):
            position = xy[:-1] + normal * (face * th / 2)
            sigma = outer(pol['B'] / p['Cw_mm6'], w)
            for action, coefficient in coefficients.items():
                section_power = stack([coefficient[0] + coefficient[1] * position[:, 0]
                    + coefficient[2] * position[:, 1],
                    coefficient[1] * delta[:, 0] + coefficient[2] * delta[:, 1]], axis=-1)
                sigma = sigma + outer(pol[action], section_power)
            # Face sign is geometric: n=(-dy,dx)/length, tauSV=-face*Tsv*t/J.
            tau = flow - face * sv
            sigma = elevate_bernstein(power_to_bernstein(sigma), -1, 2)
            tau = elevate_bernstein(power_to_bernstein(tau), -2, 3)
            yield selected, face, sigma, tau, identities


def check_member(demand, profile, *, intact_section_model_declared=False, model_origin=''):
    """Upper<=1 is sufficient for these three section criteria only.

    No branch sum is interpreted as a concurrent physical maximum. An upper
    bound >1 gives only 'inconclusive_upper_bound', not 'failed'. Existing NBR
    combinations/material stiffness are retained and explicitly labelled.
    """
    certificate = _validate(demand, profile, intact_section_model_declared, model_origin)
    normal_limit = certificate['normal_yield_limit_MPa']
    limit_intervals = dict(normal=I(normal_limit),
        shear=I(normal_limit) / I(3.).sqrt(), interaction=I(normal_limit) * I(1.1))
    bounds = dict(normal=0., shear=0., interaction=0.)
    controls = {}; count = 0
    for selected, face, sigma, tau, identities in _field_controls(demand, certificate):
        values = dict(normal=sigma.abs(), shear=tau.abs(),
            interaction=stress_norm(sigma, tau))
        for key, values_at_controls in values.items():
            ratios = values_at_controls / limit_intervals[key]
            index = np.unravel_index(np.argmax(ratios.hi), ratios.hi.shape)
            upper = float(ratios.hi[index])
            if upper >= bounds[key]:
                bounds[key] = upper
                controls[key] = dict(source_piece=identities[index[0]], wall_segment=int(index[1]),
                    face=face, longitudinal_control=int(index[2]), wall_control=int(index[3]),
                    signed_operator_superset=selected,
                    sigma_interval_MPa=[float(sigma.lo[index]),float(sigma.hi[index])],
                    tau_interval_MPa=[float(tau.lo[index]),float(tau.hi[index])],
                    is_physical_state=False, semantics='Bernstein bound control, not a stress witness')
        count += sigma.lo.shape[0] * sigma.lo.shape[1]
    criteria = {key:dict(index_upper_bound=value,
        criterion='within_limit' if value <= 1 else 'inconclusive_upper_bound',
        bound_control=controls[key], observed_exceedance=False) for key, value in bounds.items()}
    output = dict(schema=SCHEMA, status='computed_sufficient_EN_section_stress_bounds',
        combination_id=demand['combination_id'], member_id=demand['member_id'],
        source_demand_sha256=_sha(demand), source_geometry_sha256=demand['section']['nodes_sha256'],
        component_sections_sha256=certificate['content_sha256'],
        material=certificate['material'], model_origin=model_origin,
        intact_section_model_declared=True, criteria=criteria,
        full_member_field_covered=True, section_stress_criteria_sufficiently_satisfied=all(v <= 1 for v in bounds.values()),
        normal_limit_MPa=normal_limit, shear_limit_MPa=normal_limit/math.sqrt(3.),
        interaction_limit_MPa=1.1*normal_limit, polynomial_patches_checked=count,
        source_analysis_material=dict(E_MPa=demand['E_MPa'], G_MPa=demand['G_MPa']),
        method='EN1993-1-3:2006 6.1.6(3)-(5); tensor Bernstein sufficient bounds; signed-section union',
        demand_basis='Original first-order isolated ELU demand retained, not recalculated as EN action combinations',
        stress_scope='Effective pure-section bending normal stresses at both exterior faces; gross B/V/Tsv/Tw; N=0',
        numerical_scope='Outward-rounded bounds of the recovered polynomial field only, not an FE-error certificate',
        NBR_capacities_used=False, AISI_capacities_used=False, whole_member_approved=False,
        complete_EN_design_qualified=False, global_stability_qualified=False,
        excluded=['EN6.1.5 shear buckling resistance and EN6.1.10 N-M-V interaction',
            'Global/member stability and applicability of first-order/small-rotation analysis',
            'Local force introduction, connections, holes/net-section rupture and actual restraint details',
            'Full serviceability and physical geometry/material verification'],
        integration_status='Separate EN section component; explicit caller opt-in; no global approval')
    output['content_sha256'] = _sha(output)
    return output

SAVED_SCOPE = {
 'method':'EN1993-1-3:2006 6.1.6(3)-(5); tensor Bernstein sufficient bounds; signed-section union',
 'demand_basis':'Original first-order isolated ELU demand retained, not recalculated as EN action combinations',
 'stress_scope':'Effective pure-section bending normal stresses at both exterior faces; gross B/V/Tsv/Tw; N=0',
 'numerical_scope':'Outward-rounded bounds of the recovered polynomial field only, not an FE-error certificate',
 'integration_status':'Separate EN section component; explicit caller opt-in; no global approval',
 'excluded':['EN6.1.5 shear buckling resistance and EN6.1.10 N-M-V interaction',
   'Global/member stability and applicability of first-order/small-rotation analysis',
   'Local force introduction, connections, holes/net-section rupture and actual restraint details',
   'Full serviceability and physical geometry/material verification']}


def check_web_shear(demand, profile, *, intact_section_model_declared=False, model_origin=''):
    """Independent optional §§6.1.5/6.1.10 web component; not a stress recheck."""
    certificate = _validate(demand, profile, intact_section_model_declared, model_origin)
    from .isolated_en_shear import calculate_validated
    return calculate_validated(demand, profile, model_origin, certificate=certificate)
