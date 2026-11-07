"""Parameterized EN section method for complete nominal Pierin Ue rows.

Versioned extraction of the reviewed EN300 equations. No material globals are
modified. Original authorities and saved snapshots remain separate and intact.
Eligibility is a signed section-method result, never whole-member approval.
"""
from __future__ import annotations
import copy
import math
from types import MappingProxyType
from decimal import Decimal, localcontext, ROUND_CEILING, ROUND_FLOOR
from .en_ue_catalog_operators import (_sha, _properties, _eval, _vertices,
    _domain, _ends, _bands, _base, _accept, _assembly)
from .three_girt_en_normal.en1993_normal_components import PURE_ACTIONS, PANEL_NAMES
from .catalogs import catalog_entry
from .catalog_torsion_section import CONVENTION, nominal_channel_nodes
from .weak_pierin import reference_for_index

SCHEMA = 'EN_complete_Pierin_Ue_family_N0_v1'
REVISION = 'explicit_material_integral_and_reduced_web_20261106_v1'
ACTIONS = ('Mx_positive', 'Mx_negative', 'My_positive', 'My_negative')
ARC_SEGMENTS = 32

def material(fyb_MPa, gamma_M0=1.):
    for label, value in [('fyb_MPa', fyb_MPa), ('gamma_M0', gamma_M0)]:
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Positive finite material value required: ' + label)
    # EN13 3.2.1(5) / EN11 3.2.6, distinct from demand E/G.
    return MappingProxyType(dict(E_MPa=210000., nu=.3, fyb_MPa=float(fyb_MPa),
                                 fya_MPa=float(fyb_MPa), gamma_M0=float(gamma_M0)))

def _geometry(index, material):
    entry = catalog_entry(index)
    if entry['family'] != 'Ue':
        raise ValueError('Only Ue is in this candidate extension; plain U is deferred')
    reference = reference_for_index(index)
    if reference['status'] != 'tabulated_adopted_reference':
        raise ValueError('Exact nominal Pierin row required; no interpolation')
    d = entry['dimensions_mm']
    t = float(d['t'])
    ri = entry['published_properties']['ri_mm']
    identity = dict(catalog_id=entry['id'], dimensions_mm=d, inner_radius_mm=ri, arc_segments=ARC_SEGMENTS, convention=CONVENTION)
    nodes = nominal_channel_nodes(h_mm=d['h'], bf_mm=d['bf'], lip_mm=d['lip'], t_mm=t, ri_mm=ri, arc_segments=ARC_SEGMENTS)
    bounds = [0, 17, 50, 83, 116, 133]
    if len(nodes) != 134:
        raise ValueError('32-chord five-panel topology changed')
    normals = [d['bf'] - t, 0.0, 0.0, d['h'] - t, d['bf'] - t]
    groups = []
    for j, (a, b) in enumerate(zip(bounds, bounds[1:])):
        axis = 1 if j % 2 == 0 else 0
        values = [p[axis] for p in nodes[a:b + 1]]
        groups.append(dict(panel=PANEL_NAMES[j], ids=list(range(a, b)), axis=axis, lo=min(values), hi=max(values), b_mm=max(values) - min(values), normal_mm=normals[j]))
    full = [[i, 0.0, 1.0, t] for i in range(len(nodes) - 1)]
    gross = _properties(nodes, full)
    mirror_error = max((abs(nodes[i][0] - nodes[-1 - i][0]) for i in range(len(nodes))))
    mirror_error = max(mirror_error, max((abs(nodes[i][1] + nodes[-1 - i][1] - (d['h'] - t)) for i in range(len(nodes)))))
    if mirror_error > 1e-10 or abs(gross['Ixy_mm4']) > 1e-12 * math.sqrt(gross['Ix_strong_mm4'] * gross['Iy_weak_mm4']):
        raise ValueError('Horizontal nominal symmetry not demonstrated')
    guard = dict(external_b_over_t=d['bf'] / t, external_c_over_t=d['lip'] / t, external_h_over_t=d['h'] / t, external_c_over_b=d['lip'] / d['bf'], notional_c_over_b=groups[0]['b_mm'] / groups[1]['b_mm'], inner_radius_mm=ri, radius_limit_mm=0.04 * t * material['E_MPa'] / material['fyb_MPa'], lip_angle_degrees=90.0, mirror_max_error_mm=mirror_error, reference='EN13 5.1(6), 5.2/Table5.1/Eq5.2a, 5.5.3.2(1)', notional_ratio_extra_implementation_restriction='Inherited 0.2 <= bp,c/bp <= 0.6; distinct from external Eq5.2 ratio')
    guard['satisfied'] = guard['external_b_over_t'] <= 60.0 and guard['external_c_over_t'] <= 50.0 and (guard['external_h_over_t'] <= 500.0) and (0.2 <= guard['external_c_over_b'] <= 0.6) and (0.2 <= guard['notional_c_over_b'] <= 0.6) and (ri <= guard['radius_limit_mm'])
    return (entry, reference, identity, nodes, t, groups, full, gross, guard)

class _MethodDomainError(ValueError):
    def __init__(self, message, audit):
        super().__init__(message)
        self.audit = audit


class _Kernel:

    def __init__(self, values):
        self.material = values

    def _critical(self, k, t, b):
        return k * math.pi ** 2 * self.material['E_MPa'] / (12 * (1 - self.material['nu'] ** 2)) * (t / b) ** 2

    def _internal_certificate(self, g, t, stress):
        """EN 1993-1-5 Table 4.1, Eq.4.2 at fyb, NOT at service stress."""
        s0, s1 = stress
        if max(stress) <= 1e-10:
            return {'panel': g['panel'], 'branch': 'tension', 'rho': 1.0, 'b_mm': g['b_mm'], 'compression_stress_ends_MPa': stress}
        psi = min(stress) / max(stress)
        if psi < -3.0 - 1e-12 or psi > 1.0 + 1e-12:
            raise ValueError('Table4.1 stress ratio outside [-3,1]')
        psi = max(-3.0, min(1.0, psi))
        if abs(psi - 1.0) <= 1e-12:
            k = 4.0
        elif abs(psi + 1.0) <= 1e-12:
            k = 23.9
        elif psi > 0.0:
            k = 8.2 / (1.05 + psi)
        elif psi > -1.0:
            k = 7.81 - 6.29 * psi + 9.78 * psi ** 2
        else:
            k = 5.98 * (1 - psi) ** 2
        critical = self._critical(k, t, g['b_mm'])
        slenderness = math.sqrt(self.material['fyb_MPa'] / critical)
        limit = 0.5 + math.sqrt(0.085 - 0.055 * psi)
        rho = 1.0 if slenderness <= limit else min(1.0, (slenderness - 0.055 * (3 + psi)) / slenderness ** 2)
        bc = 1.0 if psi >= 0.0 else 1.0 / (1.0 - psi)
        first = rho * bc * (2.0 / (5.0 - psi) if psi >= 0.0 else 0.4)
        second = rho * bc - first
        lip_start = 1.0 - first if s1 > s0 else 1.0 - second
        return {'panel': g['panel'], 'branch': 'EN1993-1-5_Table4.1_ULS_fyb', 'b_mm': g['b_mm'], 'compression_stress_ends_MPa': stress, 'psi': psi, 'k_sigma': k, 'sigma_cr_MPa': critical, 'lambda_p': slenderness, 'lambda_p_integral_limit': limit, 'rho': rho, 'flange_lip_adjacent_start_fraction': lip_start, 'slenderness_reference_stress_MPa': self.material['fyb_MPa']}

    def _lip_certificate(self, g, flange, t, stress):
        if max(stress) <= 1e-10:
            return {'panel': g['panel'], 'branch': 'tension', 'rho': 1.0, 'b_mm': g['b_mm'], 'compression_stress_ends_MPa': stress}
        if min(stress) < -1e-10:
            raise ValueError('Mixed-sign lip outside the implemented pure-component domain')
        ratio = g['b_mm'] / flange['b_mm']
        if not 0.2 <= ratio <= 0.6:
            raise ValueError('Lip/flange ratio outside EN1993-1-3 Eq.5.2')
        k = 0.5 if ratio <= 0.35 else 0.5 + 0.83 * (ratio - 0.35) ** (2.0 / 3.0)
        critical = self._critical(k, t, g['b_mm'])
        slenderness = math.sqrt(self.material['fyb_MPa'] / critical)
        rho = 1.0 if slenderness <= 0.748 else min(1.0, (slenderness - 0.188) / slenderness ** 2)
        return {'panel': g['panel'], 'branch': 'EN1993-1-3_Eq5.13_ULS_fyb', 'b_mm': g['b_mm'], 'compression_stress_ends_MPa': stress, 'bpc_over_bp': ratio, 'k_sigma': k, 'sigma_cr_MPa': critical, 'lambda_p': slenderness, 'lambda_p_integral_limit': 0.748, 'rho': rho, 'slenderness_reference_stress_MPa': self.material['fyb_MPa']}

    def _distortion(self, st, other, t, hw):
        b1 = st['b1_mm']
        b2 = other['b1_mm'] if other else 0.0
        kr = other['As_mm2'] / st['As_mm2'] if other else 0.0
        K = self.material['E_MPa'] * t ** 3 / (4 * (1 - self.material['nu'] ** 2)) / (b1 * b1 * hw + b1 ** 3 + 0.5 * b1 * b2 * hw * kr)
        critical = 2 * math.sqrt(K * self.material['E_MPa'] * st['Is_mm4']) / st['As_mm2']
        ld = math.sqrt(self.material['fyb_MPa'] / critical)
        chi = 1.0 if ld <= 0.65 else 1.47 - 0.723 * ld if ld < 1.38 else 0.66 / ld
        raw = chi * self.material['fyb_MPa'] / self.material['gamma_M0'] / st['sigma_com_Ed_MPa']
        st.update(kr_area=kr, hw_mm=hw, K_N_mm2=K, sigma_cr_MPa=critical, lambda_d=ld, chi_d=chi, Eq5_17_unclamped_As_ratio_at_ULS=raw, Eq5_17_As_red_over_As_at_ULS=min(1.0, raw), step3_optional_refinement_used=False, source='EN13 Eq5.10b/5.12/5.15/5.17, physical As on own rounded contour')

    def _outstand(self, nodes, t, lip, flange, comp):
        lip_audit = _domain(nodes, t, [[i, 0.0, 1.0] for i in lip['ids']], comp)
        margin = max((_eval(comp, p) - self.material['fyb_MPa'] * (1 - (p[0] - flange['lo']) / flange['b_mm']) for p in _vertices(nodes, t, [[i, 0.0, 1.0] for i in flange['ids']])))
        critical = 1.7 * math.pi ** 2 * self.material['E_MPa'] / (12 * (1 - self.material['nu'] ** 2)) * (t / flange['b_mm']) ** 2
        lp = math.sqrt(self.material['fyb_MPa'] / critical)
        rho = 1.0 if lp <= 0.748 else min(1.0, (lp - 0.188) / lp ** 2)
        good = lip_audit['max_line_or_face_compression_MPa'] <= 0.0 and margin <= 0.0 and (rho == 1.0)
        return dict(panel=flange['panel'], rho=rho, lambda_p=lp, k_sigma=1.7, maximum_actual_minus_bound_MPa=margin, lip_stress_domain_audit=lip_audit, integral_bound=good, reference='EN15 Table4.2 psi=0, supported web edge, free lip-side edge', lip_restraint_credited=False, translating_junction_modes_qualified=False)

    def _integral_moment(self, name, nodes, t, groups, full, gross):
        base = _base(name)
        axis, sign = PURE_ACTIONS[name]
        cg = gross['centroid_xy_mm']
        Ix, Iy, Ixy = [gross[k] for k in ('Ix_strong_mm4', 'Iy_weak_mm4', 'Ixy_mm4')]
        det = Ix * Iy - Ixy * Ixy
        coeff = [0.0, -Ixy / det, Iy / det] if axis == 1 else [0.0, -Ix / det, Ixy / det]
        absolute = [-coeff[1] * cg[0] - coeff[2] * cg[1], coeff[1], coeff[2]]
        refs = [r[:3] for r in full]
        maximum = max((abs(_eval(absolute, p)) for p in _vertices(nodes, t, refs)))
        scale = self.material['fyb_MPa'] / self.material['gamma_M0'] / maximum
        comp = [-sign * scale * v for v in absolute]
        meta = {j: self._internal_certificate(groups[j], t, _ends(groups[j], comp)) for j in (1, 2, 3)}
        for l, f in ((0, 1), (4, 3)):
            meta[l] = self._lip_certificate(groups[l], groups[f], t, _ends(groups[l], comp))
        if name == 'My_negative' and meta[2]['rho'] < 1.0:
            web = _domain(nodes, t, [[i, 0.0, 1.0] for i in groups[2]['ids']], comp)
            stress = web['max_line_or_face_compression_MPa']
            if not 0.0 < stress <= self.material['fyb_MPa']:
                raise ValueError('Invalid web pure-ULS compression bound')
            lp = meta[2]['lambda_p'] * math.sqrt(stress / self.material['fyb_MPa'])
            rho = 1.0 if lp <= meta[2]['lambda_p_integral_limit'] else min(1.0, (lp - 0.055 * (3 + meta[2]['psi'])) / lp ** 2)
            meta[2]['Eq4_4_integral_ULS_trial'] = dict(sigma_com_Ed_MPa=stress, lambda_p_reduced=lp, rho=rho, rho_at_fyb=meta[2]['rho'], lambda_p_at_fyb=meta[2]['lambda_p'], reference='EN15 4.4(4)/Eq4.4 at the pure face-normalized ULS, not service stress', condition='Eligible only when all local widths and As thicknesses stay unchanged')
            if rho == 1.0:
                meta[2]['rho'] = 1.0
                meta[2]['branch'] = 'EN1993-1-5_Table4.1_Eq4.4_integral_pure_ULS_trial'
        base['local_panels'] = [meta[j] for j in range(5)]
        if any((m['rho'] != 1.0 for m in meta.values())):
            base['blocking_reasons'].append(dict(code='PURE_MOMENT_LOCAL_REDUCTION_NOT_QUALIFIED', panels=[dict(panel=m['panel'], rho=m['rho']) for m in meta.values() if m['rho'] != 1.0]))
            return base
        stiff = []
        bounds = []
        tension = []
        for l, f in ((0, 1), (4, 3)):
            if meta[l]['branch'] == 'tension':
                audit = _domain(nodes, t, [[i, 0.0, 1.0] for i in groups[l]['ids'] + groups[f]['ids']], comp)
                tension.append(dict(flange=groups[f]['panel'], **audit))
                if audit['max_line_or_face_compression_MPa'] > 0.0:
                    if name != 'My_negative':
                        raise ValueError('Unqualified mixed flange with a tensile lip')
                    bound = self._outstand(nodes, t, groups[l], groups[f], comp)
                    bounds.append(bound)
                    if not bound['integral_bound']:
                        raise ValueError('Free-outstand integral majorant not demonstrated')
                stiff.append(None)
            else:
                stiff.append(_assembly(nodes, t, groups[l], groups[f], meta[f], comp))
        hw = max((p[1] for p in nodes)) - min((p[1] for p in nodes))
        for st, other in zip(stiff, stiff[::-1]):
            if st is None:
                continue
            self._distortion(st, other, t, hw)
            if st['Eq5_17_As_red_over_As_at_ULS'] != 1.0:
                base['blocking_reasons'].append(dict(code='PURE_MOMENT_DISTORTIONAL_REDUCTION_NOT_QUALIFIED', flange=st['flange'], As_red_over_As=st['Eq5_17_As_red_over_As_at_ULS']))
        base.update(stiffeners=[s for s in stiff if s], outstand_flange_bounds=bounds, tension_assemblies=tension, ULS_pure_effort_signed=sign * scale, pure_ULS_compression_coefficients_absolute=comp)
        if base['blocking_reasons']:
            return base
        base.update(section_status='integral_pure_moment_ULS_fixed_point', proof='EN13 5.5.2/5.5.3/6.1.4.1(4); EN15 Table4.1/4.2. Every local rho=1 and compressed physical As exact Eq5.17 cap=1. Tensile-lip mixed flanges require a separate free-outstand majorant.', fixed_point_statement='All widths and thicknesses unchanged at the pure-ULS reference; therefore same stress field on re-evaluation.', assembly_interpretation='Inherited EN stiffener-as-column model: wholly compressed physical As; kr=As2/As1 when both exist, kr=0 only for the wholly tensile opposite assembly. Not a coupled translating-junction eigenmode proof.')
        return _accept(base, coeff, copy.deepcopy(gross), copy.deepcopy(full), gross)

    def _capacity_floor(self, nodes, t, cg, coeff):
        """Outward arithmetic for the exact supplied binary64 operator/contour.

    This encloses evaluation, not uncertainty in material or effective widths.
    It does not use a pure-ULS normalization as a resistance denominator.
    """
        from .torsion_vlasov.intervals import Interval as I, stack
        import numpy as np
        p = I(nodes)
        g = I(cg)
        c = I(coeff)
        d = p[1:] - p[:-1]
        length = (d[:, 0].square() + d[:, 1].square()).sqrt()
        normal = stack([-d[:, 1] / length, d[:, 0] / length], axis=-1)
        xy = stack([p[:-1] - g, p[1:] - g], axis=1)
        maximum = 0.0
        for side in (-1, 0, 1):
            face = xy + normal[:, None, :] * (side * t / 2)
            sigma = c[0] + c[1] * face[:, :, 0] + c[2] * face[:, :, 1]
            maximum = max(maximum, float(np.max(sigma.abs().hi)))
        lower = float((I(self.material['fya_MPa']) / I(self.material['gamma_M0']) / I(maximum)).lo)
        floor = math.floor(lower)
        if floor <= 0:
            raise ValueError('Nonpositive first-yield capacity floor')
        return dict(integer_floor=floor, first_yield_lower=lower, maximum_abs_unit_stress_upper=maximum, domain='ALL physical line/offset-face endpoints; contains the retained effective material', numerical_scope='Outward rounding for supplied binary64 operator/contour, not interval proof of effective-width derivation', reference='EN13 6.1.2/6.1.3/6.1.4.1; elastic first yield, no plastic/cold-work enhancement')

    def _reduced_state(self, rho, nodes, t, groups, gross):
        if type(rho) not in (int, float) or not math.isfinite(rho) or (not 0 < rho <= 1):
            raise ValueError('rho outside (0,1]')
        refs = []
        for j, g in enumerate(groups):
            refs.extend(_bands(nodes, g, [(0.0, rho / 2), (1 - rho / 2, 1.0)] if j == 2 else [(0.0, 1.0)]))
        weighted = [[*r, t] for r in refs]
        eff = _properties(nodes, weighted)
        cx, cy = eff['centroid_xy_mm']
        iy = eff['Iy_weak_mm4']
        if abs(cy - gross['centroid_xy_mm'][1]) > 1e-10 or abs(eff['Ixy_mm4']) > 1e-07:
            raise ValueError('Effective geometry lost symmetry')
        pts = list(_vertices(nodes, t, refs))
        scale = self.material['fyb_MPa'] / max((abs(p[0] - cx) for p in pts))
        comp = [scale * cx, -scale, 0.0]
        web = _domain(nodes, t, [[i, 0.0, 1.0] for i in groups[2]['ids']], comp)
        stress = web['max_line_or_face_compression_MPa']
        lam = math.sqrt(stress / self._critical(4, t, groups[2]['b_mm']))
        target = 1.0 if lam <= 0.5 + math.sqrt(0.03) else (lam - 0.22) / lam ** 2
        bounds = [self._outstand(nodes, t, groups[l], groups[f], comp) for l, f in ((0, 1), (4, 3))]
        if not all((b['integral_bound'] for b in bounds)) or not 0 < target <= 1 or (not 0 < stress <= self.material['fyb_MPa']):
            raise _MethodDomainError('Reduced web requires integral flange majorants and admissible web stress/rho', dict(flange_bounds=bounds, target_rho=target, web_stress_MPa=stress, fyb_MPa=self.material['fyb_MPa']))
        coeff = [(cx - gross['centroid_xy_mm'][0]) / iy, -1 / iy, 0.0]
        return dict(rho=rho, target=target, residual=target - rho, lambda_red=lam, web_bound_MPa=stress, props=eff, weighted=weighted, comp=comp, coefficients=coeff, effort=-scale * iy, bounds=bounds)

    def _negative_my(self, nodes, t, groups, gross, initial_rho=1.0):
        rho = initial_rho
        history = []
        for n in range(150):
            state = self._reduced_state(rho, nodes, t, groups, gross)
            history.append({k: state[k] for k in ('rho', 'target', 'residual', 'lambda_red', 'web_bound_MPa')})
            if abs(state['residual']) < 1e-13:
                break
            rho = state['target']
        else:
            raise ValueError('No fixed point convergence')
        state = self._reduced_state(rho, nodes, t, groups, gross)
        if abs(state['residual']) >= 1e-13 or not 0 < rho < 1:
            raise ValueError('Final recheck failed')
        base = _accept(_base('My_negative'), state['coefficients'], state['props'], state['weighted'], gross)
        base.update(section_status='effective_web_reduced_negative_My_ULS', rho_web=rho, ULS_pure_effort_signed=state['effort'], pure_ULS_compression_coefficients_absolute=state['comp'], outstand_flange_bounds=state['bounds'], fixed_point_audit=dict(initial_rho=initial_rho, iterations=len(history), history=history, residual=state['residual'], final_recheck=True, tolerance=1e-13), proof='EN15 4.4(4), Eq4.4 Note1; uniform web bound k=4; free-outstand flanges Table4.2 psi=0 k=1.70; EN13 6.1.4.1(4).', lip_restraint_credited=False, translating_junction_modes_qualified=False)
        return base


def _wall_floor(hw_mm, t_mm, walls, values):
    """Directed Decimal EN13 Table6.1; never scale a stored resistance."""
    with localcontext() as ctx:
        ctx.prec=60; ctx.rounding=ROUND_CEILING
        h,t=Decimal(str(hw_mm)),Decimal(str(t_mm))
        fy,E,gamma=(Decimal(str(values[k])) for k in ('fyb_MPa','E_MPa','gamma_M0'))
        root=(fy/E).sqrt().next_plus()
        lam=Decimal('.346')*(h/t)*root
        ctx.rounding=ROUND_FLOOR
        if lam<=Decimal('.83'):
            strength=Decimal('.58')*fy; branch='lambda_le_0.83'
        elif lam<Decimal('1.4'):
            strength=Decimal('.48')*fy/lam; branch='0.83_lt_lambda_lt_1.4'
        else:
            strength=Decimal('.67')*fy/lam/lam; branch='lambda_ge_1.4'
        capacity=Decimal(walls)*h*t*strength/gamma
        floor=int(capacity.to_integral_value(rounding=ROUND_FLOOR))
        lu,fl=float(lam),float(strength)
        if Decimal.from_float(lu)<lam: lu=math.nextafter(lu,math.inf)
        if Decimal.from_float(fl)>strength: fl=math.nextafter(fl,-math.inf)
    return dict(walls=walls,hw_mm=float(h),sw_upper_mm=float(h),lambda_upper=lu,
                fbv_lower_MPa=fl,table61_branch=branch,capacity_floor_N=float(floor),
                rounding='directed_decimal_60_digits_then_integer_N_floor')


def _shear(identity,nodes,t,values):
    d=identity['dimensions_mm']; ri=identity['inner_radius_mm']
    h=Decimal(str(d['h']))-Decimal(str(d['t']))
    b=Decimal(str(d['bf']))-Decimal(str(d['t']))
    sw_h=abs(nodes[83][1]-nodes[50][1])
    sw_b=[abs(nodes[17][0]-nodes[50][0]),abs(nodes[116][0]-nodes[83][0])]
    checks=dict(external_b_over_t=d['bf']/t<=60,external_c_over_t=d['lip']/t<=50,
                external_h_over_t=d['h']/t<=500,external_c_over_b=.2<=d['lip']/d['bf']<=.6,
                radius=ri<=.04*t*values['E_MPa']/values['fyb_MPa'],core_thickness=.45<=t<=15.,
                corner_midpoint_bounds=0<sw_h<=float(h) and all(0<s<=float(b) for s in sw_b))
    eligible=all(checks.values())
    walls=dict(strong=_wall_floor(h,t,1,values),weak=_wall_floor(b,t,2,values)) if eligible else {}
    return dict(eligible=eligible,applicability_checks=checks,
                blocking_reasons=[key for key,value in checks.items() if not value],
                shear_capacity_geometry=walls,
                shear_capacity_lower_N={axis:w['capacity_floor_N'] for axis,w in walls.items()},
                source='EN1993-1-3 6.1.5 / Table6.1, unstiffened web and two rotated flange webs',
                support_stiffener_credit=False,lip_or_corner_resistance_credit=False)


def _reduced_contraction(kernel,nodes,t,groups,full,gross,rho):
    """Per-candidate analytic contraction where removed web is straight x=0.

    Strict binary64 margins, not an interval-arithmetic or global uniqueness
    claim. Unsupported brackets remain unavailable, with no gross fallback.
    """
    width=groups[2]['b_mm']; A0=gross['A_mm2']; S=A0*gross['centroid_xy_mm'][0]
    fy=kernel.material['fyb_MPa']; critical=kernel._critical(4.,t,width)
    xmin=min(p[0] for p in _vertices(nodes,t,[r[:3] for r in full]))
    xmax=max(p[0] for p in _vertices(nodes,t,[r[:3] for r in full]))
    for delta in (.05,.02,.005,.001,.0001):
        lo,hi=max(1e-8,rho-delta),min(1.-1e-8,rho+delta)
        removed_lo=groups[2]['lo']+width*lo/2
        removed_hi=groups[2]['hi']-width*lo/2
        straight=[(nodes[i][1],nodes[i+1][1]) for i in groups[2]['ids']
                  if abs(nodes[i][0])<1e-14 and abs(nodes[i+1][0])<1e-14]
        if not any(min(a,b)<=removed_lo<removed_hi<=max(a,b) for a,b in straight):continue
        def target(r):
            area=A0-t*width*(1-r); cx=S/area
            if not 0<cx-xmin<=xmax-cx:
                raise ValueError('Reduced web proof requires tension-side face normalization')
            stress=fy*(cx-xmin)/(xmax-cx); lam=math.sqrt(stress/critical)
            return (lam-.22)/lam**2,lam,cx
        flo,lammax,cxmax=target(lo); fhi,lammin,_=target(hi)
        if not (lo<flo<=fhi<hi and lammin>.5+math.sqrt(.03)):continue
        amin=A0-t*width*(1-lo)
        bound=(1/lammin**2)*(1/(2*critical*lammin))*fy*(xmax-xmin)/(xmax-cxmax)**2*S*t*width/amin**2
        if not 0<=bound<1:continue
        state=kernel._reduced_state(rho,nodes,t,groups,gross)
        if abs(target(rho)[0]-state['target'])>1e-12:
            raise ValueError('Closed-form reduced web and contour evaluation disagree')
        kernel._reduced_state(lo,nodes,t,groups,gross)
        kernel._reduced_state(hi,nodes,t,groups,gross)
        return dict(bracket=[lo,hi],endpoint_targets=[flo,fhi],derivative_absolute_upper=bound,
                    removed_material='straight x=0 web only; A=A0-t*b*(1-rho), first moment S unchanged',
                    formula='sigma=fy*(cx-xmin)/(xmax-cx); lambda=sqrt(sigma/sigma_cr); F=(lambda-.22)/lambda^2',
                    proof='monotone invariant bracket with analytical contraction bound < 1',
                    arithmetic='binary64 evaluation with strict margins; no interval-arithmetic claim')
    raise ValueError('Reduced web analytical contraction subdomain not demonstrated')


def _material_declaration(values,declaration):
    from .catalogs import STEELS
    if declaration is None:
        matches=[dict(name=name,fu_MPa=steel['fu_MPa'],source=steel['source'])
                 for name,steel in STEELS.items() if steel['fy_MPa']==values['fyb_MPa']]
        declaration=matches[0] if len(matches)==1 else dict(name='Custom nominal yield',fu_MPa=None,source=None)
    if not isinstance(declaration,dict) or set(declaration)-{'name','fu_MPa','source'}:
        raise ValueError('Material declaration accepts name, fu_MPa and source only')
    declaration=copy.deepcopy(declaration)
    for key in ('name','source'):
        if declaration.get(key) is not None and not isinstance(declaration[key],str):
            raise ValueError('Material declaration text required: '+key)
    fu=declaration.get('fu_MPa')
    if fu is not None and (type(fu) not in (int,float) or not math.isfinite(fu) or fu<values['fyb_MPa']):
        raise ValueError('Declared fu must be finite and at least fy')
    return dict(**declaration,fyb_MPa=values['fyb_MPa'],fu_used_in_N0_equations=False,
                conformance_status='not_verified',
                conformance_required='EN1993-1-3 3.1/3.2: product standard, yield/tensile properties and ductility; a numeric fy alone cannot establish applicability',
                gamma_M0_basis='1.0, fixed choice of the current normal proof normalization')


def _classify_blocking_reasons(component,guard):
    for reason in component['blocking_reasons']:
        code=reason['code']; detail=reason.get('detail','')
        if code=='EN_GEOMETRICAL_PROPORTIONS_NOT_QUALIFIED':
            normative=(guard['external_b_over_t']<=60. and guard['external_c_over_t']<=50.
                       and guard['external_h_over_t']<=500. and .2<=guard['external_c_over_b']<=.6
                       and guard['inner_radius_mm']<=guard['radius_limit_mm'])
            reason['category']='implementation_method_not_covered' if normative else 'outside_normative_geometric_domain'
        elif detail in ('No fixed point convergence','Final recheck failed','Reduced web depends on fixed point seed'):
            reason['category']='numerical_failure'
        elif detail in ('Effective geometry lost symmetry','Closed-form reduced web and contour evaluation disagree'):
            reason['category']='integrity_failure'
        else:reason['category']='implementation_method_not_covered'
        reason['normative_rejection_inferred']=reason['category']=='outside_normative_geometric_domain'
    component['qualification_scope']='signed_section_method_only'


def build(index,*,fyb_MPa,gamma_M0=1.,material_declaration=None):
    """Fresh N=0 four signed moments and independent shear, complete rows only."""
    from .pierin_ue_registry import select_new_study
    select_new_study(index,include_routes=False)
    values=material(fyb_MPa,gamma_M0)
    declaration=_material_declaration(values,material_declaration)
    if values['gamma_M0']!=1.:
        raise ValueError('Normal proof normalization currently implements gamma_M0=1 only')
    kernel=_Kernel(values)
    entry,reference,identity,nodes,t,groups,full,gross,guard=_geometry(index,values)
    components={}
    for name in ACTIONS:
        result=_base(name)
        if not guard['satisfied']:
            result['blocking_reasons']=[dict(code='EN_GEOMETRICAL_PROPORTIONS_NOT_QUALIFIED',audit=guard)]
        else:
            try:
                result=kernel._integral_moment(name,nodes,t,groups,full,gross)
                if name=='My_negative' and not result['eligible']:
                    integral_trial=copy.deepcopy(result)
                    result=kernel._negative_my(nodes,t,groups,gross)
                    seeds=[]
                    for initial in (.25,.5,.75):
                        trial=kernel._negative_my(nodes,t,groups,gross,initial)
                        if abs(trial['rho_web']-result['rho_web'])>1e-11:
                            raise ValueError('Reduced web depends on fixed point seed')
                        seeds.append(dict(initial_rho=initial,rho_web=trial['rho_web'],residual=trial['fixed_point_audit']['residual']))
                    result['fixed_point_audit']['independent_seeds']=seeds
                    result['fixed_point_audit']['contraction_certificate']=_reduced_contraction(kernel,nodes,t,groups,full,gross,result['rho_web'])
                    result['integral_trial']=integral_trial
            except ValueError as error:
                result=_base(name)
                result['blocking_reasons']=[dict(code='SIGNED_COMPONENT_DOMAIN_NOT_QUALIFIED',detail=str(error),audit=getattr(error,'audit',None))]
        if result['eligible']:
            audit=kernel._capacity_floor(nodes,t,gross['centroid_xy_mm'],result['sigma_coefficients_c0_cx_cy'])
            result['capacity_audit']=audit; result['first_yield_capacity_floor']=audit['integer_floor']
        _classify_blocking_reasons(result,guard)
        components[name]=result
    result=dict(schema=SCHEMA,method_revision=REVISION,catalog_index=index,catalog_id=entry['id'],
                nominal_identity=identity,nominal_identity_sha256=_sha(identity),nodes_xy_mm=nodes,
                nodes_sha256=_sha(nodes),thickness_mm=t,
                profile_id='OWN_PIERIN_NOMINAL_'+entry['id']+'_'+_sha(identity)[:16],
                material=dict(values),material_declaration=declaration,material_normative_conformance_verified=False,
                eligibility_scope='Section equations under declared nominal yield; not a product or material conformity certificate',
                gross_properties=gross,panels=groups,geometry_guard=guard,components=components,
                shear=_shear(identity,nodes,t,values),
                signed_capacity_floor={k:v['first_yield_capacity_floor'] for k,v in components.items()},
                normal_yield_limit_MPa=values['fya_MPa']/values['gamma_M0'],
                stress_convention='N tension positive, Mx=integral(y*sigma)dA, My=-integral(x*sigma)dA',
                coordinate_origin='Own contour gross centroid; c0 includes effective centroid shift',
                action_scope='N=0; EN My is opposite to app NBR My',
                material_origin='Declared nominal fyb=fya, no cold-work enhancement; EN E=210000 MPa, nu=.3, not demand E/G',
                source_basis=[dict(url='https://www.gfos.unios.hr/download/en-1993-1-1-2005.pdf',clauses='3.2.6'),
                              dict(url='https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf',clauses='3.2.1(5),5.5,6.1.4,6.1.5,6.1.6'),
                              dict(url='https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.5.2006.pdf',clauses='4.4 Eq4.4 Note1, Tables4.1/4.2')],
                review_status='deterministic_family_method_pending_independent_review',
                runtime_release_approved=False,whole_member_approved=False,complete_EN_design_qualified=False,
                physical_geometry_verified=False,first_order_analysis_qualified=False,global_stability_qualified=False,
                torsion_qualified=False,pierin_criticals_transferred=False,legacy_certificates_changed=False,
                not_checked=['axial force','EN6.27 and concurrent normal/shear/torsion interaction',
                             'curling/shear lag applicability','member stability/second order',
                             'connections/net section','physical product/material','coupled translating-junction eigenmodes'])
    result['content_sha256']=_sha(result)
    return result


def table61_unstiffened_fbv(lambda_w,*,fyb_MPa):
    """Literal scalar equation, not section qualification."""
    fy=material(fyb_MPa)['fyb_MPa']
    if type(lambda_w) not in (int,float) or not math.isfinite(lambda_w) or lambda_w<0:
        raise ValueError('Finite nonnegative web slenderness required')
    if lambda_w<=.83:return .58*fy
    if lambda_w<1.4:return .48*fy/lambda_w
    return .67*fy/lambda_w/lambda_w
