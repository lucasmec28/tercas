"""Isolated sufficient full-effectiveness comparator, NOT a design release.

No case IDs, critical moments, scalar MSE curves, FEM or reduced-section law
enter this calculation. Read DERIVATION.txt for the comparison and exclusions.
The caller must supply a verified, immutable geometry source SHA256.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path
import hashlib
import json
import math

D = Decimal
PRECISION = 70
GUARD = D('1e-20')  # Deliberately wider than 70-digit arithmetic error here.
LIMIT = D('.673')
NAMES = ('bottom_lip', 'bottom_flange', 'web', 'top_flange', 'top_lip')


def number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite real, not a bool or string.')
    return D(value)  # Exact conversion of the actual binary input, no snapping.


def length(v):
    return sum(a*a for a in v).sqrt()


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def unpack(value):
    if isinstance(value, D):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Result cannot be represented as a finite JSON number.')
        if result == 0. and value != 0:
            raise ValueError('A nonzero result would underflow to zero in JSON binary64 output.')
        return result
    if isinstance(value, dict):
        return {k: unpack(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [unpack(v) for v in value]
    return value


def _empty_result():
    """Fresh JSON-safe failure base. Never retain partially computed results."""
    return dict(schema='Ue_gross_MLE_field_comparator_research_v1',
        sufficient_full_section=False, combined_stiffness_released=False,
        physical_ELS_approved=False, whole_member_approved=False,
        resistance_release=False, torsion_or_warping_qualified=False,
        reduced_biaxial_law_qualified=False, published=False,
        elastic_stress_sufficient=False, support_transfer_and_local_bearing_qualified=False)


@dataclass(frozen=True)
class Geometry:
    source_sha256: str
    nodes: tuple
    t: D
    nominal_lip: D
    walls: tuple
    area: D
    cg: tuple
    Ix: D
    Iy: D
    Ixy: D
    E: D
    nu: D


def load_geometry(path, expected_sha256):
    """Read an independently pinned own Ue geometry, then reintegrate it.

    The own-property fields are checks, never assigned as calculation inputs.
    The model is the faceted line dA=t ds, not a smooth shell or solid strip.
    """
    with localcontext() as ctx:
        ctx.prec = PRECISION
        raw = Path(path).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if type(expected_sha256) is not str or actual != expected_sha256:
            raise ValueError('Geometry source differs from the caller-pinned SHA256.')
        data = json.loads(raw)
        if data['schema'] != 'Ue100_family_geometry_preparation_v1':
            raise ValueError('Unreviewed geometry schema.')
        dims = data['geometry_external_mm']
        if set(dims) != {'h', 'b', 'lip', 't', 'ri'}:
            raise ValueError('Unknown nominal geometry fields.')
        h, b, lip, t, ri = (number(dims[k], k) for k in ('h', 'b', 'lip', 't', 'ri'))
        if min(h, b, lip, t, ri) <= 0 or number(data['thickness_mm'], 'thickness') != t:
            raise ValueError('Invalid or inconsistent thickness/dimensions.')
        identity = data['geometry_identity']
        nf, na = identity['flat_segment_counts'], identity['arc_segment_counts']
        if (len(nf) != 5 or len(na) != 4 or
                any(type(v) is not int or v <= 0 for v in nf+na)):
            raise ValueError('Unrecognized five-flat/four-bend topology.')
        nodes = tuple(tuple(number(v, 'node') for v in p) for p in data['nodes_xy_mm'])
        if any(len(p) != 2 for p in nodes) or len(nodes) != sum(nf)+sum(na)+1:
            raise ValueError('Node count/topology mismatch.')
        if identity['node_count'] != len(nodes):
            raise ValueError('Declared node count mismatch.')
        # Derive the straight-wall intervals from topology, not node IDs.
        walls, start = [], 0
        widths = (lip-ri-t, b-2*ri-2*t, h-2*ri-2*t, b-2*ri-2*t, lip-ri-t)
        directions = ((0, -1), (-1, 0), (0, 1), (1, 0), (0, -1))
        for j, name in enumerate(NAMES):
            end = start+nf[j]
            delta = sub(nodes[end], nodes[start]); width = length(delta)
            if widths[j] <= 0 or abs(width-widths[j]) > D('1e-11'):
                raise ValueError('Own flat width differs from the nominal bend convention.')
            tangent = tuple(x/width for x in delta)
            if max(abs(x-y) for x, y in zip(tangent, directions[j])) > D('1e-12'):
                raise ValueError('This adapter requires orthogonal inward lips and aligned web.')
            for i in range(start, end+1):
                along = dot(sub(nodes[i], nodes[start]), tangent)
                cross = sub(nodes[i], nodes[start])[0]*tangent[1]-sub(nodes[i], nodes[start])[1]*tangent[0]
                if abs(cross) > D('1e-11') or not -D('1e-11') <= along <= width+D('1e-11'):
                    raise ValueError('Nonstraight or reordered wall nodes.')
            walls.append((name, start, end, width, (-tangent[1], tangent[0])))
            start = end + (na[j] if j < 4 else 0)
        segments = [(a, b, t*length(sub(b, a))) for a, b in zip(nodes[:-1], nodes[1:])]
        if any(da <= 0 for _, _, da in segments):
            raise ValueError('Zero-length or invalid segment.')
        area = sum(da for _, _, da in segments)
        cg = tuple(sum(da*(a[k]+b[k])/2 for a, b, da in segments)/area for k in range(2))
        xx = yy = xy = D(0)
        for aa, bb, da in segments:
            a, b = sub(aa, cg), sub(bb, cg)
            xx += da*(a[0]**2+a[0]*b[0]+b[0]**2)/3
            yy += da*(a[1]**2+a[1]*b[1]+b[1]**2)/3
            xy += da*(2*a[0]*a[1]+a[0]*b[1]+b[0]*a[1]+2*b[0]*b[1])/6
        if min(xx, yy) <= 0 or xx*yy-xy*xy <= 0:
            raise ValueError('Nonpositive bending tensor.')
        own = data['own_properties']
        for got, key in ((area, 'A_mm2'), (yy, 'Ix_strong_mm4'), (xx, 'Iy_weak_mm4')):
            if abs(got-number(own[key], key)) > D('1e-10')*abs(got):
                raise ValueError('Reintegrated properties disagree with the own source.')
        if max(abs(cg[j]-number(own['centroid_xy_mm'][j], 'centroid')) for j in range(2)) > D('1e-10'):
            raise ValueError('Centroid source mismatch.')
        material = data['declared_material_for_future_executor']
        E, nu = (number(material[k], k) for k in ('E_MPa', 'nu'))
        if E != 200000 or abs(nu-D('.3')) > D('1e-16'):
            raise ValueError('Material outside the supplied-source contract.')
        return Geometry(actual, nodes, t, lip, tuple(walls), area, cg, yy, xx, xy, E, nu)


def coefficients(g, moments):
    """Compression positive. Mx=integral(sigma*y), My=-integral(sigma*x)."""
    mx, my = moments
    det = g.Ix*g.Iy-g.Ixy*g.Ixy
    return ((-my*g.Ix-mx*g.Ixy)/det, (mx*g.Iy+my*g.Ixy)/det)


def normalized_fields(L, q, P, position, a_mm=None):
    """Exact two-shape convex comparison, including nonproportional loads.

    Q=q L²/8, T=P a(L-a)/L. Let a_weight=||Q||inf/(||Q||inf+||T||inf).
    The normalized source fields Q/a and T/(1-a) bound M/f, with 0<=f<=1.
    Zero terms are omitted. No collinearity tolerance enters acceptance.
    """
    if position not in (None, 'center', 'support_limit', 'finite_interior'):
        raise ValueError('Unsupported point position contract.')
    if position == 'finite_interior':
        a = number(a_mm, 'interior point position')
        if not 0 < a < L:
            raise ValueError('A finite interior point must satisfy 0<a_mm<L exactly.')
    else:
        if a_mm is not None:
            raise ValueError('a_mm is permitted only with finite_interior; no contradictory coordinates.')
        a = L/2
    if position is None and any(P):
        raise ValueError('Nonzero point force requires an explicit position contract.')
    effective = (D(0), D(0)) if position == 'support_limit' else P
    Q = tuple(v*L*L/8 for v in q)
    T = tuple(v*a*(L-a)/L for v in effective)
    sizes = [max(map(abs, vector)) for vector in (Q, T)]
    total = sum(sizes)
    if not total:
        return [], dict(zero_bending_field=True, weights=[D(0), D(0)],
                        summed_individual_peak_moments_Nmm=[D(0), D(0)])
    fields = [tuple(v*total/size for v in vector) for vector, size in zip((Q, T), sizes) if size]
    return fields, dict(zero_bending_field=False, weights=[v/total for v in sizes],
        summed_individual_peak_moments_Nmm=[u+v for u, v in zip(Q, T)],
        summed_peaks_are_concomitant=position in (None, 'center', 'support_limit'),
        finite_point_position_mm=a if position == 'finite_interior' else None,
        moment_cross_product_Q_T=Q[0]*T[1]-Q[1]*T[0],
        same_nonnegative_ray_exact=(Q[0]*T[1] == Q[1]*T[0] and dot(Q, T) >= 0),
        normalized_source_moments_Nmm=fields,
        field_proof='M=f*convex(Q/a,T/b), 0<=f<=1; no sampled-span acceptance')


def web_index(stresses, width, t, E):
    maximum, minimum = max(stresses), min(stresses)
    if maximum <= 0:
        return D(0), None, D(4)
    psi = minimum/maximum
    k = 4+2*(1-psi)+2*(1-psi)**3
    return width/t/D('.95')*(maximum/(E*k)).sqrt(), psi, k


def wall_result(g, wall, source_coefficients, stiffener_bound='shifted_cubic'):
    name, i, j, width, normal = wall
    # The same constant outward safety pad is added to both endpoints.
    # It preserves a linear stress majorant across the flat element.
    endpoints = []
    for point in (g.nodes[i], g.nodes[j]):
        endpoint = max((dot(sub(point, g.cg), c)+g.t/2*abs(dot(normal, c))
                        for c in source_coefficients), default=D(0))
        endpoints.append(endpoint)
    pad = GUARD*max(abs(s) for s in endpoints) if source_coefficients else D(0)
    endpoints = [s+pad for s in endpoints]
    sigma = max(D(0), *endpoints)
    lambda0 = width/g.t/D('.623')*(sigma/g.E).sqrt()
    k, psi, Ia, Ia_upper, Is = D('.43'), None, None, None, None
    threshold = LIMIT*(1-GUARD)
    if name == 'web':
        lam, psi, k = web_index(endpoints, width, g.t, g.E)
        full = lam <= threshold
        scale_limit = (threshold/lam)**2 if lam else None
        route = 'Table5 affine majorant of simultaneous biaxial stress; outer fibres included'
    elif 'flange' in name:
        lip_wall = g.walls[0 if name.startswith('bottom') else 4]
        d = lip_wall[3]
        Is = g.t*d**3/12  # Orthogonal lip. Bends excluded.
        ratio = g.nominal_lip/width
        if not 0 < ratio <= D('.8'):
            raise ValueError('Flange D/b outside the supplied 9.2.3 formula domain.')
        full_k = min(D(4), D('3.57')+D('.43') if ratio <= D('.25')
                     else D('4.82')-5*ratio+D('.43'))
        full_lam = width/g.t/D('.95')*(sigma/(g.E*full_k)).sqrt()
        if lambda0:
            low_limit = (threshold/lambda0)**2
            linear_limit = max(D(0), (Is/(g.t**4*(1+GUARD))-5)/56)
            cubic_limit = LIMIT+(Is/(399*g.t**4*(1+GUARD)))**(D(1)/3)/D('.487')
            stiffener_lambda0_limit = (linear_limit if stiffener_bound == 'linear'
                                      else max(linear_limit, cubic_limit))
            high_limit = min((threshold/full_lam)**2, (stiffener_lambda0_limit/lambda0)**2)
            scale_limit = max(low_limit, high_limit)
        else:
            scale_limit = None
        if lambda0 <= threshold:
            lam = lambda0
            full = True
            route = '9.2.3 low-slenderness branch: edge stiffener not needed'
        else:
            # Two monotone upper bounds are retained. The shifted cube uses
            # .487*(lambda0-.673) instead of .487*lambda0-.328: it is larger
            # by .000249, and is nonnegative on the active branch.
            Ia = min(399*g.t**4*(D('.487')*lambda0-D('.328'))**3,
                     g.t**4*(56*lambda0+5))
            linear_upper = g.t**4*(56*lambda0+5)
            shifted_cube = 399*g.t**4*(D('.487')*max(D(0), lambda0-LIMIT))**3
            Ia_upper = linear_upper if stiffener_bound == 'linear' else min(shifted_cube, linear_upper)
            adequate = Is >= Ia_upper*(1+GUARD)
            k, lam = full_k, full_lam
            full = adequate and lam <= threshold
            route = 'Uniform flange comparator; full stiffener via Is>=monotone '+stiffener_bound+' upper bound on Ia'
    else:
        lam = width/g.t/D('.95')*(sigma/(g.E*k)).sqrt()
        full = lam <= threshold
        scale_limit = (threshold/lam)**2 if lam else None
        route = 'Table6 AL lip: its own uniform compression upper bound'
    return dict(wall=name, b_mm=width, endpoint_upper_MPa=endpoints,
        maximum_compression_upper_MPa=sigma, psi=psi, k=k, lambda_p0=lambda0,
        lambda_local=lam, Is_mm4=Is, Ia_literal_diagnostic_mm4=Ia,
        Ia_monotone_upper_mm4=Ia_upper, stiffener_upper_bound_method=stiffener_bound,
        full_wall_sufficient=full, route=route,
        uniform_action_scale_sufficient_limit=scale_limit)


def assess_case(geometry, model, case, *, stiffener_bound='shifted_cubic'):
    """Fail closed. A negative screen result is inconclusive, never rejection.

    Geometry is a frozen object returned by load_geometry. Model and case
    schemas deliberately reject unknown physical fields. Labels are ignored.
    """
    result = _empty_result()
    try:
        with localcontext() as ctx:
            ctx.prec = PRECISION
            if type(geometry) is not Geometry:
                raise ValueError('Expected independently pinned and reintegrated geometry.')
            if stiffener_bound not in ('shifted_cubic', 'linear'):
                raise ValueError('Unknown stiffener upper-bound policy.')
            required = {'L_mm', 'E_MPa', 'nu', 'fy_MPa', 'N_N', 'B_Nmm2', 'supports', 'prismatic', 'stress_scope'}
            if type(model) is not dict or set(model) != required:
                raise ValueError('Missing or unknown model fields; no physical input may be ignored.')
            L = number(model['L_mm'], 'span')
            if L <= 0 or number(model['E_MPa'], 'E') != geometry.E or number(model['nu'], 'nu') != geometry.nu:
                raise ValueError('Invalid span or geometry/material mismatch.')
            if number(model['fy_MPa'], 'fy') != 250:
                raise ValueError('Yield stress outside the own declared steel contract.')
            if number(model['N_N'], 'N') != 0 or number(model['B_Nmm2'], 'B') != 0:
                raise ValueError('Axial force and warping normal stress are outside this bending-only field.')
            if (model['supports'] != 'simply_supported_bending' or model['prismatic'] is not True or
                    model['stress_scope'] != 'bending_component_only'):
                raise ValueError('Unsupported longitudinal mechanics or scope.')
            if type(case) is not dict or not {'q_N_mm', 'P_N', 'point_position'} <= set(case) or set(case)-{'q_N_mm', 'P_N', 'point_position', 'a_mm', 'id', 'angle'}:
                raise ValueError('Missing or unknown case fields.')
            vectors = []
            for key in ('q_N_mm', 'P_N'):
                value = case[key]
                if type(value) not in (list, tuple) or len(value) != 2:
                    raise ValueError('Each load must contain two simultaneous local components.')
                vectors.append(tuple(number(x, key) for x in value))
            q, P = vectors
            fields, certificate = normalized_fields(L, q, P, case['point_position'], case.get('a_mm'))
            coeffs = [coefficients(geometry, field) for field in fields]
            walls = [wall_result(geometry, wall, coeffs, stiffener_bound) for wall in geometry.walls]
            # All faceted bends are included in the elastic stress guard, and
            # retained according to the declared MLE gross-corner convention.
            absolute_stress = D(0)
            for a, b in zip(geometry.nodes[:-1], geometry.nodes[1:]):
                tangent = sub(b, a); le = length(tangent)
                normal = (-tangent[1]/le, tangent[0]/le)
                for point in (a, b):
                    for c in coeffs:
                        absolute_stress = max(absolute_stress,
                            abs(dot(sub(point, geometry.cg), c))+geometry.t/2*abs(dot(normal, c)))
            elastic = absolute_stress*(1+GUARD) <= D(250)*(1-GUARD)
            elastic_scale = D(250)*(1-GUARD)/(absolute_stress*(1+GUARD)) if absolute_stress else None
            scale_limits = [w['uniform_action_scale_sufficient_limit'] for w in walls
                            if w['uniform_action_scale_sufficient_limit'] is not None]
            if elastic_scale is not None:
                scale_limits.append(elastic_scale)
            scale_limit = min(scale_limits) if scale_limits else None
            full = elastic and all(w['full_wall_sufficient'] for w in walls)
            result.update(status='sufficient_comparator_pass' if full else 'comparator_inconclusive',
                sufficient_full_section=full, geometry_source_sha256=geometry.source_sha256,
                computed_properties=dict(A_mm2=geometry.area, centroid_xy_mm=geometry.cg,
                    Ix_mm4=geometry.Ix, Iy_mm4=geometry.Iy, Ixy_mm4=geometry.Ixy),
                field_certificate=certificate, walls=walls,
                maximum_absolute_normal_stress_upper_MPa=absolute_stress,
                elastic_stress_sufficient=elastic,
                maximum_uniform_action_scale_sufficient=scale_limit,
                uniform_action_scale_contract='Positive common scaling of the actual q and P only, fixed geometry/span/position. Comparator limit, not resistance. Rerun actual proposed binary inputs.',
                elastic_uniform_action_scale_sufficient=elastic_scale,
                support_limit_bending_only=case['point_position'] == 'support_limit',
                support_transfer_and_local_bearing_qualified=False,
                numeric_contract='70-digit decimal; exact binary input conversion; 1e-20 inward acceptance guard',
                interpretation='Sufficient full-effectiveness comparison. Inconclusive is not section reduction or failure.')
            converted = unpack(result)
            # Publication to the caller is atomic: conversion and the strict
            # JSON contract both finish before any computed result is returned.
            json.dumps(converted, allow_nan=False)
            return converted
    except (ValueError, TypeError, KeyError, ArithmeticError, OverflowError) as exc:
        failure = _empty_result()
        failure.update(status='outside_comparator_domain', reason=str(exc))
        return failure


def model_for(g, L):
    return dict(L_mm=L, E_MPa=float(g.E), nu=float(g.nu), fy_MPa=250., N_N=0., B_Nmm2=0.,
                supports='simply_supported_bending', prismatic=True, stress_scope='bending_component_only')
