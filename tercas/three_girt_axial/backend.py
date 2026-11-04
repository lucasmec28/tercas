"""Research copy: NBR 14762:2010 axial arithmetic and concomitant §9.9 envelope.

N, mm, MPa. Not imported by the app. No rod/connection design, automatic
second-order prescription, warping restraint, ELS or whole-member approval.
The implemented local-compression domain is deliberately FULLY EFFECTIVE only;
an unsupported/reduced element returns no Aef instead of silently using Ag.
"""
import math
import json
from pathlib import Path
from numpy.polynomial import Polynomial

AXES = (('Nt', 'Nc'), ('Mstrong_pos', 'Mstrong_neg'), ('Mweak_pos', 'Mweak_neg'))


def _number(value, name, positive=False, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ': finite numeric value required')
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValueError(name + ': outside nonnegative/positive domain')
    return float(value)


def _origin(value, name='origin'):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + ': explicit provenance/domain required')
    return value


def partial_bolted_U_web_ct(*, eccentricity_mm, connection_length_mm,
                            bolts_along_force, origin):
    """§9.6.2 partial-element U, web bolted, >=2 bolts along force.

    This helper is NOT the welded-U branch or a flange-connected fictitious
    angle construction. It computes shear-lag Ct, not real load eccentricity.
    """
    _origin(origin)
    x = _number(eccentricity_mm, 'eccentricity_mm', nonnegative=True)
    length = _number(connection_length_mm, 'connection_length_mm', positive=True)
    if isinstance(bolts_along_force, bool) or not isinstance(bolts_along_force, int) or bolts_along_force < 2:
        raise ValueError('This partial-element bolted branch needs at least two bolts along force')
    raw = 1 - 1.2*x/length
    return dict(Ct=None if raw < .4 else min(raw, .9), raw_Ct=raw,
                status='prohibited_below_0.4' if raw < .4 else 'arithmetic_qualified_declared_domain',
                origin=origin, clause='NBR14762:2010 9.6.2, web-connected bolted U',
                connection_strength_verified=False, applied_force_eccentricity_removed=False)


def tension_capacity(*, Ag_mm2, fy_MPa, fu_MPa, An0_mm2=None, An_mm2=None,
                     Ct=None, origin, outside_area_origin=None, connection_origin=None):
    """Three §9.6.2 branches. Missing An0/An/Ct never defaults to gross area.

    An must already include the applicable net-area rule and every relevant
    path; Ct must come from an applicable connection branch. This function
    does not enumerate hole paths or qualify a fastener/connection assembly.
    """
    _origin(origin)
    A = _number(Ag_mm2, 'Ag', positive=True)
    fy = _number(fy_MPa, 'fy', positive=True)
    fu = _number(fu_MPa, 'fu', positive=True)
    if fu < fy:
        raise ValueError('fu must not be lower than fy in this declared material domain')
    branches = {'gross_yield_N': A*fy/1.10}
    missing = []
    if An0_mm2 is None:
        missing.append('An0 outside connection')
    else:
        a0 = _number(An0_mm2, 'An0', positive=True)
        if a0 > A:
            raise ValueError('An0 must not exceed Ag')
        _origin(outside_area_origin, 'outside_area_origin')
        branches['outside_net_rupture_N'] = a0*fu/1.35
    if An_mm2 is None or Ct is None:
        missing.append('An and applicable Ct within connection')
    else:
        an = _number(An_mm2, 'An', positive=True)
        ct = _number(Ct, 'Ct', positive=True)
        if an > A or ct > 1:
            raise ValueError('An<=Ag and Ct<=1 required; branch-specific Ct limits remain applicable')
        _origin(connection_origin, 'connection_origin')
        branches['connection_net_rupture_N'] = ct*an*fu/1.65
    return dict(Nt_Rd_N=None if missing else min(branches.values()), branches=branches,
                missing=missing, status='partial' if missing else 'arithmetic_qualified_declared_domain',
                origin=origin, outside_area_origin=outside_area_origin,
                connection_origin=connection_origin, whole_member_approved=False,
                connection_strength_verified=False,
                scope='Axial tensile section resistance only; inputs require geometric/connection applicability')


def tension_slenderness(*, member_length_mm, A_mm2, Imin_mm4, origin):
    """§9.6.3 recommendation, not an invented compression limit or prohibition."""
    _origin(origin)
    ratio = _number(member_length_mm, 'length', positive=True)/math.sqrt(
        _number(Imin_mm4, 'Imin', positive=True)/_number(A_mm2, 'A', positive=True))
    return dict(L_over_r=ratio, recommended_limit=300., recommendation_satisfied=ratio <= 300,
                rule_type='recommendation', clause='NBR14762:2010 9.6.3', origin=origin)


def monossymmetric_elastic_compression(*, A_mm2, I_sym_mm4, I_orth_mm4,
                                      J_mm4, Cw_mm6, x0_mm, E_MPa, G_MPa,
                                      fy_MPa, effective_L_sym_mm,
                                      effective_L_orth_mm, effective_L_torsion_mm,
                                      origin, effective_lengths_origin):
    """§9.7.2.2, x is symmetry axis, y0=0, principal axes, open U/Ue.

    Effective lengths are declared stability-member lengths, never inferred
    from FE segmentation/tie count. No end warping restraint is created.
    r0 is derived consistently from supplied I/A and x0, not rounded radii.
    """
    _origin(origin); _origin(effective_lengths_origin, 'effective_lengths_origin')
    A = _number(A_mm2, 'A', positive=True)
    ix = _number(I_sym_mm4, 'I_sym', positive=True)
    iy = _number(I_orth_mm4, 'I_orth', positive=True)
    J = _number(J_mm4, 'J', positive=True)
    cw = _number(Cw_mm6, 'Cw', nonnegative=True)
    x = _number(x0_mm, 'x0')
    E = _number(E_MPa, 'E', positive=True)
    G = _number(G_MPa, 'G', positive=True)
    fy = _number(fy_MPa, 'fy', positive=True)
    lx, ly, lz = [_number(v, n, positive=True) for v, n in [
        (effective_L_sym_mm, 'KL_sym'), (effective_L_orth_mm, 'KL_orth'),
        (effective_L_torsion_mm, 'KL_torsion')]]
    r02 = (ix+iy)/A+x*x
    beta = ((ix+iy)/A)/r02
    nx, ny = math.pi**2*E*ix/lx**2, math.pi**2*E*iy/ly**2
    nz = (math.pi**2*E*cw/lz**2+G*J)/r02
    # Stable smaller root: algebraically identical to printed §9.7.2.2.
    disc = (nx-nz)**2+4*(1-beta)*nx*nz
    nxz = 2*nx*nz/(nx+nz+math.sqrt(disc))
    ne = min(ny, nxz)
    lam = math.sqrt(A*fy/ne)
    chi = .658**(lam*lam) if lam <= 1.5 else .877/(lam*lam)
    sx, sy = lx/math.sqrt(ix/A), ly/math.sqrt(iy/A)
    return dict(A_mm2=A, E_MPa=E, G_MPa=G, fy_MPa=fy, r0_mm=math.sqrt(r02), beta=beta,
                Nex_N=nx, Ney_N=ny, Nez_N=nz, Nexz_N=nxz, Ne_N=ne,
                lambda0=lam, chi=chi, sigma_effective_MPa=chi*fy,
                compression_slenderness={'symmetry_axis': sx, 'orthogonal_axis': sy,
                    'limit': 200., 'satisfied': max(sx, sy) <= 200.},
                origin=origin, effective_lengths_origin=effective_lengths_origin,
                stability_member_lengths_mm=[lx, ly, lz],
                warping_restraint_inferred=False, whole_member_approved=False)


def fully_effective_U_Ue(*, family, h_mm, bf_mm, t_mm, ri_mm, lip_mm=0,
                        A_mm2, E_MPa, stress_MPa, origin):
    """§9.2 MLE subset: uniform compression and every element fully effective.

    U/Ue: equal flanges, uniform thickness, 90-degree bends, no openings.
    External nominal dimensions; flat widths exclude corners. Gross area
    includes bends and remains the supplied area if no reduction is required.
    For reduced area, unsupported lip geometry, or inadequate lip inertia,
    Aef=None. This is not a hidden gross-section fallback.
    """
    _origin(origin)
    if family not in ('U', 'Ue'):
        raise ValueError('Only symmetric-flange U/Ue implemented')
    h, bf, t, A, E, stress = [_number(v, n, positive=True) for v, n in [
        (h_mm, 'h'), (bf_mm, 'bf'), (t_mm, 't'), (A_mm2, 'A'),
        (E_MPa, 'E'), (stress_MPa, 'stress')]]
    ri = _number(ri_mm, 'ri', nonnegative=True)
    D = _number(lip_mm, 'lip', nonnegative=True)
    web = h-2*(ri+t)
    flange = bf-(2 if family == 'Ue' else 1)*(ri+t)
    lip = D-ri-t
    if (web <= 0 or flange <= 0 or family == 'Ue' and (lip <= 0 or 2*D >= h)
            or family == 'U' and D != 0):
        raise ValueError('Invalid external geometry or unsupported lip convention')
    issues = []
    result = dict(family=family, origin=origin, A_gross_mm2=A, E_MPa=E,
                  nominal_geometry=dict(family=family,h_mm=h,bf_mm=bf,t_mm=t,lip_mm=D),
                  flat_widths_mm={'web': web, 'flange': flange},
                  stress_MPa=stress, method='MLE fully-effective uniform-compression subset')
    ks = {'web': 4., 'flange': .43}
    widths = {'web': web, 'flange': flange}
    if family == 'Ue':
        widths['lip'] = lip; ks['lip'] = .43
        result['flat_widths_mm']['lip'] = lip
        lp0 = flange/t/(.623*math.sqrt(E/stress))
        result['lambda_p0'] = lp0
        # D/b is the nominal lip dimension divided by flat flange width.
        D_b = D/flange
        if D_b > .8:
            issues.append('Ue lip geometry outside implemented §9.2.3.1 D/b<=0.8')
        if lp0 <= .673:
            ks['flange'] = 4.
            result['stiffener_required_by_this_branch'] = False
        else:
            Is = t*lip**3/12
            Ia = min(399*t**4*(.487*lp0-.328)**3, t**4*(56*lp0+5))
            if Ia <= 0:
                # Printed rounded coefficients leave a narrow interval above
                # .673 with nonpositive Ia. Do not calibrate the standard or
                # turn a negative Ia into a full-effective lip silently.
                return dict(result, Aef_mm2=None, Is_mm4=Is, Ia_mm4=Ia,
                            issues=['Nonpositive Ia from rounded coefficients near lambda_p0=0.673; branch unresolved'],
                            status='outside_implemented_effective_area_domain')
            ratio = min(Is/Ia, 1.)
            n = max(.582-.122*lp0, 1/3)
            factor = 3.57 if D_b <= .25 else 4.82-5*D_b
            k = min(factor*ratio**n+.43, 4.)
            if k <= 0:
                issues.append('Nonpositive flange k outside supported geometry')
                k = .43  # Diagnostic only; issues prevent a capacity.
            ks['flange'] = k
            result.update(Is_mm4=Is, Ia_mm4=Ia, Is_over_Ia_raw=Is/Ia,
                          Is_over_Ia_used=ratio, n=n, k_flange=k,
                          stiffener_required_by_this_branch=True)
            if ratio < 1:
                issues.append('Lip-inertia reduction required; reduced Aef not implemented')
    lambdas = {key: width/t/(.95*math.sqrt(ks[key]*E/stress))
               for key, width in widths.items()}
    for key, value in lambdas.items():
        if value > .673:
            issues.append(key+': local effective-width reduction required')
    result.update(element_lambda_p=lambdas, element_k=ks, issues=issues,
                  Aef_mm2=None if issues else A,
                  status='outside_implemented_effective_area_domain' if issues else 'fully_effective_qualified_declared_geometry')
    return result


def section_width_limits(*, local, t_mm, bending_present=False, origin):
    """Separate §9.1.2/Table4 screen; not an effective-area or strength factor.

    Ue web classification (both edges connected to AA flanges) is explicit.
    The beam-web 200 row is applied only when bending_present is declared.
    30 and 250 footnotes are recommendations, not replacement hard limits.
    """
    _origin(origin)
    if not isinstance(bending_present, bool):
        raise ValueError('bending_present must be explicitly boolean')
    t = _number(t_mm, 't', positive=True)
    if local.get('family') not in ('U', 'Ue'):
        raise ValueError('U/Ue local geometry required')
    w = local['flat_widths_mm']; family = local['family']
    rows = [('flange', 60., 30. if family == 'Ue' else None, 'Ue simple lip-supported flange' if family == 'Ue' else 'U AL flange')]
    rows += [('web', 500. if family == 'Ue' else 90., 250. if family == 'Ue' else None,
              'Ue web, both borders connected to AA flanges' if family == 'Ue' else 'U unstiffened web, uniform compression')]
    if family == 'Ue':
        rows.append(('lip', 60., None, 'AL lip'))
    if bending_present:
        rows.append(('web', 200., None, 'beam web without transverse stiffeners, declared bending'))
    checks = [dict(element=key, b_over_t=w[key]/t, hard_limit=limit,
                   hard_limit_satisfied=w[key]/t <= limit, recommended_limit=rec,
                   recommendation_satisfied=None if rec is None else w[key]/t <= rec,
                   classification=classification) for key, limit, rec, classification in rows]
    return dict(checks=checks, hard_limits_satisfied=all(c['hard_limit_satisfied'] for c in checks),
                recommendations_satisfied=all(c['recommendation_satisfied'] is not False for c in checks),
                bending_present=bending_present, origin=origin, clause='NBR14762:2010 9.1.2 Table4',
                section_strength_qualified=False)


def compression_capacity(*, elastic, local, distortion, origin, geometry_limits=None):
    """Combine distinct axial gates, never turn a numeric stage into approval.

    distortion: {'status':'exempt', 'origin':...} or a qualified declared
    {'status':'capacity', 'Nc_dist_Rd_N':..., 'origin':...}; otherwise pending.
    The caller must preserve the scope of any exemption (centered compression).
    """
    _origin(origin)
    if local.get('A_gross_mm2') != elastic['A_mm2'] or local.get('E_MPa') != elastic['E_MPa']:
        raise ValueError('Local/global gross-area or elastic-material identity mismatch')
    if distortion.get('nominal_geometry') is not None and distortion['nominal_geometry'] != local['nominal_geometry']:
        raise ValueError('Distortion and local-area nominal geometry mismatch')
    missing = []
    Aef = local.get('Aef_mm2')
    if Aef is None:
        missing.append('effective area outside implemented/qualified domain')
        global_capacity = None
    else:
        Aef = _number(Aef, 'Aef', positive=True)
        if Aef > elastic['A_mm2']:
            raise ValueError('Aef cannot exceed Ag')
        if not math.isclose(local['stress_MPa'], elastic['sigma_effective_MPa'], rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError('Local effective area was not evaluated at this chi*fy')
        global_capacity = elastic['chi']*Aef*elastic['fy_MPa']/1.20
    dstatus = distortion.get('status')
    dvalue = None
    if dstatus in ('exempt', 'capacity'):
        _origin(distortion.get('origin'), 'distortion origin')
        if distortion.get('scope') != 'centered_compression':
            raise ValueError('Compression distortion evidence must explicitly address centered compression')
        if dstatus == 'capacity':
            dvalue = _number(distortion.get('Nc_dist_Rd_N'), 'Nc_dist_Rd_N', positive=True)
    else:
        missing.append('centered-compression distortional gate')
    value = None if missing else min(global_capacity, dvalue) if dvalue is not None else global_capacity
    member_issues = []
    if not elastic['compression_slenderness']['satisfied']:
        member_issues.append('NBR14762:2010 9.7.4 compression KL/r exceeds 200')
    if geometry_limits is not None and not geometry_limits['hard_limits_satisfied']:
        member_issues.append('NBR14762:2010 9.1.2 width/thickness limit exceeded')
    return dict(Nc_Rd_N=value, global_local_stage_N=global_capacity,
                distortion_stage_N=dvalue, missing=missing, member_issues=member_issues,
                origin=origin, status='partial' if missing else 'arithmetic_qualified_declared_domain',
                whole_member_approved=False, gamma_global=1.20, geometry_limits=geometry_limits,
                scopes_not_verified=['analysis applicability under 8.1', 'actual restraint properties',
                                     'bending, shear, torsion and warping interaction', 'connections',
                                     'independent geometric limits under 9.1.2'])


def centered_compression_distortion(*, family, h_mm, bf_mm, t_mm, lip_mm=0, origin):
    """Compression only: U §9.3; Ue Table11 with no extrapolation.

    Table11 uses nominal dimensions, not flat widths. Success here is NOT
    transferable to either direction of weak-axis bending or the panel case.
    """
    _origin(origin)
    h = _number(h_mm, 'h', positive=True)
    bf = _number(bf_mm, 'bf', positive=True)
    t = _number(t_mm, 't', positive=True)
    d = _number(lip_mm, 'lip', nonnegative=True)
    base = dict(scope='centered_compression', origin=origin,
                nominal_geometry=dict(family=family,h_mm=h,bf_mm=bf,t_mm=t,lip_mm=d),
                bending_exemption=False, actual_profile_identity_verified=False)
    if family == 'U' and d == 0:
        return dict(base, status='exempt', clause='NBR14762:2010 9.3, unstiffened U in centered compression')
    if family != 'Ue' or d <= 0:
        return dict(base, status='pending', reason='Unsupported family/lip geometry for this compression-only gate')
    grid = json.loads((Path(__file__).resolve().parent/'compression_reference'/'table11_compression.json').read_text())
    xs = [r['bf_over_bw'] for r in grid['rows']]
    ys = grid['columns_bw_over_t']
    x, y = bf/h, h/t
    if not min(xs) <= x <= max(xs) or not min(ys) <= y <= max(ys):
        return dict(base, status='pending', reason='Outside Table11 grid; no extrapolation', bf_bw=x, bw_t=y)
    # Find surrounding cell independently of the reference oracle's bounds.
    i = min(max(sum(v < x for v in xs)-1, 0), len(xs)-2)
    j = min(max(sum(v > y for v in ys)-1, 0), len(ys)-2)
    u = (x-xs[i])/(xs[i+1]-xs[i]); v = (y-ys[j])/(ys[j+1]-ys[j])
    z0 = grid['rows'][i]['minimum_D_over_bw']; z1 = grid['rows'][i+1]['minimum_D_over_bw']
    limit = z0[j]*(1-u)*(1-v)+z0[j+1]*(1-u)*v+z1[j]*u*(1-v)+z1[j+1]*u*v
    return dict(base, status='exempt' if d/h >= limit else 'pending',
                reason='Table11 centered-compression exemption met' if d/h >= limit else 'Table11 exemption not met; distortional capacity needed',
                clause='NBR14762:2010 9.7.3 Table11', bf_bw=x, bw_t=y, D_bw=d/h,
                minimum_D_bw=limit, interpolation='successive linear interpolation in nominal ratios')


def denominator(*, key, value, section_id, stability_member_id, region_id, origin,
                member_issues=()):
    """Explicit capacity binding, avoiding a generic scalar reused elsewhere."""
    if key not in sum(AXES, ()):
        raise ValueError('Unknown capacity key')
    for name, text in [('section_id', section_id), ('stability_member_id', stability_member_id),
                       ('region_id', region_id), ('origin', origin)]:
        _origin(text, name)
    if value is not None:
        value = _number(value, 'capacity', positive=True)
    return dict(key=key, value=value, unit='N' if key in AXES[0] else 'Nmm',
                section_id=section_id, stability_member_id=stability_member_id,
                region_id=region_id, origin=origin, member_issues=list(member_issues),
                whole_member_approved=False)


def _poly(coefficients, name, max_degree):
    if not isinstance(coefficients, (list, tuple)) or not coefficients:
        raise ValueError(name+': nonempty coefficient list required')
    c = [_number(v, name) for v in coefficients]
    while len(c) > 1 and c[-1] == 0:
        c.pop()
    if len(c) > max_degree+1:
        raise ValueError(name+': unsupported polynomial degree; do not sample to bypass')
    return Polynomial(c)


def _roots(p, lo, hi):
    return sorted(float(r.real) for r in p.roots()
                  if abs(r.imag) <= 1e-10*max(1., abs(r.real)) and lo < r.real < hi)


def interaction_segment(*, N_coeff, Mstrong_coeff, Mweak_coeff, capacities,
                        combination_id, section_id, stability_member_id,
                        region_id, segment_id, x_start_mm, length_mm, origin):
    """Exact piecewise quadratic §9.9 arithmetic using SAME-section demands.

    N positive=tension; moments signed in declared frame axes. Signed moments
    choose the appropriate directional denominator; adverse contributions use
    nonnegative magnitudes. Opposite actions cannot cancel in the scalar check.
    N is constant on each force-introduction region; this does NOT shorten the
    physical stability member. Moments are at most quadratic (uniform loads).
    At a discontinuity call separately for both sides. No mixed combinations.

    Missing required denominators -> no numeric maximum. Exact zero polynomial
    needs no corresponding denominator; no normative 'small-force' tolerance.
    Result always remains a diagnostic, not complete §9/structural acceptance.
    """
    for name, value in [('combination_id', combination_id), ('section_id', section_id),
                        ('stability_member_id', stability_member_id), ('region_id', region_id),
                        ('segment_id', segment_id), ('origin', origin)]:
        _origin(value, name)
    start = _number(x_start_mm, 'x_start_mm')
    length = _number(length_mm, 'length_mm', positive=True)
    ps = [_poly(N_coeff, 'N', 0), _poly(Mstrong_coeff, 'Mstrong', 2),
          _poly(Mweak_coeff, 'Mweak', 2)]
    if not isinstance(capacities, dict):
        raise ValueError('Capacities must be a mapping')
    for key, cap in capacities.items():
        if key not in sum(AXES, ()) or not isinstance(cap, dict) or cap.get('key') != key:
            raise ValueError('Invalid capacity binding')
        for field, expected in [('section_id', section_id), ('stability_member_id', stability_member_id), ('region_id', region_id)]:
            if cap.get(field) != expected:
                raise ValueError('Capacity '+key+' does not match demand '+field)
        if cap.get('unit') != ('N' if key in AXES[0] else 'Nmm'):
            raise ValueError('Capacity units mismatch')
        _origin(cap.get('origin'), 'capacity origin')
        if cap.get('value') is not None:
            _number(cap['value'], 'capacity '+key, positive=True)
    splits = sorted(set([0., 1.]+[r for p in ps for r in _roots(p, 0., 1.)]))
    active = [any(c != 0 for c in p.coef) for p in ps]
    intervals, missing, issues = [], set(), set()
    for lo, hi in zip(splits, splits[1:]):
        signs = [1 if p((lo+hi)/2) >= 0 else -1 for p in ps]
        keys = [pair[0 if s > 0 else 1] if a else None for pair, s, a in zip(AXES, signs, active)]
        for key in keys:
            if key is None:
                continue
            cap = capacities.get(key)
            if cap is None or cap.get('value') is None:
                missing.add(key)
            if cap:
                issues.update(cap.get('member_issues', []))
        intervals.append((lo, hi, signs, keys))
    states = []
    for lo, hi, signs, keys in intervals:
        weighted = Polynomial([0.])
        if not missing:
            for p, s, key in zip(ps, signs, keys):
                if key is not None:
                    weighted += s*p/capacities[key]['value']
        points = [lo, hi]+([] if missing else _roots(weighted.deriv(), lo, hi))
        # Retain component extrema too, but do not mistake them for sum extrema.
        points += [r for p in ps for r in _roots(p.deriv(), lo, hi)]
        for u in sorted(set(points)):
            vals = [float(p(u)) for p in ps]
            value = None if missing else sum(abs(v)/capacities[key]['value']
                                            for v, key in zip(vals, keys) if key is not None)
            states.append(dict(x_normalized=u, x_mm=start+length*u,
                               N_tension_positive_N=vals[0], Mstrong_Nmm=vals[1], Mweak_Nmm=vals[2],
                               interval=[lo, hi], capacity_keys=keys, numeric_index=value,
                               side='segment_start_right' if u == 0 else 'segment_end_left' if u == 1 else 'interior'))
    maximum = None if missing else max(states, key=lambda s: s['numeric_index'])
    return dict(combination_id=combination_id, section_id=section_id,
                stability_member_id=stability_member_id, region_id=region_id, segment_id=segment_id,
                origin=origin, maximum=maximum, states=states,
                missing_capacity_keys=sorted(missing), member_issues=sorted(issues),
                status='incomplete_denominators' if missing else 'concomitant_arithmetic_only',
                second_order_automatically_imposed=False, analysis_8_1_qualified=False,
                torsion_warping_shear_qualified=False, whole_member_approved=False)
