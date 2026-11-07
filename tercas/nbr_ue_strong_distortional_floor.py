"""All-half-wave lower bound of the EXISTING strong-distortion approximation.

The bound is for the AISI elastic scalar formula, not a physical/FSM eigenvalue.
No physical span, effective length, support or rotational restraint is inferred.
Only an explicit new calculation may consume this independently versioned API.
"""
from __future__ import annotations

import copy
import json
import math
from fractions import Fraction

from . import nbr_ue_family_base as base
from .ue_catalog_reference import digest

SCHEMA = 'nbr_ue_strong_distortional_approximation_floor_v1'
METHOD = 'S100_general_strong_distortion_all_q_AMGM_upper_denominator_v1'
SCOPE = (
    'Piso para toda meia-onda positiva da mesma aproximação elástica de distorção '
    'forte, seguido exclusivamente pela curva NBR 14762:2010 §9.8.2.3. '
    'Não é piso físico, autovalor FSM, solução de membro finito ou aprovação global. '
    'Acima do piso, a condição suficiente é inconclusiva, nunca reprovação.')
SOURCE_DOCUMENTS = [
    dict(title='ABNT NBR 14762:2010', clauses=['9.3', '9.8.2.3'],
         role='Adoção da aproximação já documentada e curva resistente NBR.'),
    dict(title='AISI S100-16 (2020) with Supplement 3 (2022)',
         url='https://buildusingsteel-media.s3.amazonaws.com/wp-content/uploads/2023/06/23212327/AISI-S100-16-2020-wS3-22.pdf',
         sha256='706a4bfaf030768d6382324a8d1916acdb749a0e739ef20fa0d7638ba8a9f03a',
         pages_PDF_one_based=[231, 232], pages_printed=['2-12', '2-13'],
         clauses=['Table 2.3.3-1', '2.3.3.1-3', '2.3.3.2(a)-1/2/4/5/6/7'],
         role='Formulação elástica geral; redução algébrica para xi_web=2, beta=1, k_phi=0.'),
    dict(title='ANSI/SDI/AISI S100-2024 and Commentary',
         url='https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf',
         sha256='6ec32742f056d08a0823557d9ce58b69d84312e64a6e656b8ba4b3b10cf4b4ca',
         pages_PDF_one_based=[217, 218, 219, 220],
         clauses=['Table 2.3.3-1', '2.3.3.1-3', '2.3.3.2-1/2/4/5/6/7'],
         role='Mesma formulação já adotada pelo provedor de referência da família.'),
    dict(title='Glauz (2018), Distortional Buckling of Cold-Formed Steel Flanges Under Stress Gradient',
         url='https://scholarsmine.mst.edu/isccss/24iccfss/session1/3/',
         role='Correlação publicada de família, tabela 4 conjunto 4; não garante piso físico ou cada contorno arredondado.'),
]


def _q(value):
    """Exact value of a supplied finite binary scalar, not its decimal display."""
    if isinstance(value, Fraction):
        return value
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite real scalar required; booleans are not numbers')
    return Fraction(value)


def _directed(value, upward=False):
    """Outward binary64 conversion checked against the exact rational result."""
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError('Distortional floor outside finite output range') from exc
    if not math.isfinite(result):
        raise ValueError('Distortional floor outside finite output range')
    if (Fraction(result) < value if upward else Fraction(result) > value):
        result = math.nextafter(result, math.inf if upward else -math.inf)
    if not math.isfinite(result):
        raise ValueError('Distortional floor outside finite output range')
    return result


def _sqrt_bounds(value):
    """Integer-arithmetic enclosure with at least 128 significant binary bits."""
    if value < 0:
        raise ValueError('Negative square-root argument')
    if not value:
        return Fraction(0), Fraction(0)
    exponent = (value.numerator.bit_length()-value.denominator.bit_length())//2
    quantum = Fraction(2)**(exponent-128)
    scaled = value/quantum**2
    integer = math.isqrt(scaled.numerator//scaled.denominator)
    lower = integer*quantum
    upper = lower if lower**2 == value else (integer+1)*quantum
    if not lower**2 <= value <= upper**2:
        raise ArithmeticError('Square-root enclosure failed')
    return lower, upper


def _coefficients(dimensions, material):
    """Exact Table 2.3.3-1 properties, using the same sharp midline convention."""
    h, t, bf, lip = map(_q, (dimensions['h'], dimensions['t'],
                             dimensions['bf'], dimensions['lip']))
    E, G, nu = map(_q, (material['E_MPa'], material['G_MPa'], material['nu']))
    b, lip_depth = bf-t, lip-t/2
    if min(h, t, b, lip_depth, E, G, 1-nu**2) <= 0:
        raise base.OutsideMethod('Positive strong-distortion geometry/material required')
    A = (b+lip_depth)*t
    J = (b+lip_depth)*t**3/3
    Ix = t*(t*t*b*b+4*b*lip_depth**3+t*t*b*lip_depth+lip_depth**4)/(12*(b+lip_depth))
    Iy = t*(b**4+4*lip_depth*b**3)/(12*(b+lip_depth))
    Ixy = t*b*b*lip_depth*lip_depth/(4*(b+lip_depth))
    xo = b*b/(2*(b+lip_depth))
    xh = -(b*b+2*lip_depth*b)/(2*(b+lip_depth))
    yo = -lip_depth**2/(2*(b+lip_depth))
    # Cwf=0 for this simple 90-degree lip, exactly as in the existing provider.
    H = (xo-xh)**2*(Ix-Ixy**2/Iy)
    K = E*t**3/(4*(1-nu**2)*h)
    a, bcoef, c = E*H+K*h**4/720, G*J+2*K*h*h/15, K
    C = Ix+Iy+A*(xh*xh+yo*yo-2*yo*(xo-xh)*Ixy/Iy)
    d = t*h**3/240
    coefficients = dict(a=a, b=bcoef, c=c, C=C, d=d)
    if min(H, *coefficients.values()) <= 0:
        raise base.OutsideMethod('Positive coefficients not proved; no distortional floor')
    properties = dict(h_mm=h, t_mm=t, b_mm=b, d_lip_mm=lip_depth,
        Af_mm2=A, Jf_mm4=J, Ixf_mm4=Ix, Iyf_mm4=Iy, Ixyf_mm4=Ixy,
        Cwf_mm6=Fraction(0), xof_mm=xo, xhf_mm=xh, yof_mm=yo, H_mm6=H, K_N=K)
    return coefficients, properties


def _resistance_floor(W, fy, gamma, md):
    """Monotone capped NBR curve for all Mdist >= the supplied positive floor."""
    if min(W, fy, gamma, md) <= 0:
        raise base.OutsideMethod('Positive resistance inputs required')
    lambda2 = W*fy/md
    lam_lo, lam_hi = _sqrt_bounds(lambda2)
    if lambda2 <= Fraction('0.673')**2:
        factor, branch = Fraction(1), 'gross'
    else:
        # rho decreases for lambda > .44. Above .673 the gross cap removes
        # the small overshoot caused by the printed rounded coefficients.
        factor = min(Fraction(1), (lam_hi-Fraction('0.22'))/lam_hi**2)
        branch = 'distortional_reduction_with_gross_cap'
    value = factor*W*fy/gamma
    if value <= 0:
        raise base.OutsideMethod('Positive resistance floor not proved')
    return value, dict(method='NBR14762:2010 §9.8.2.3',
        lambda_squared_at_floor_fraction=str(lambda2),
        lambda_at_floor_interval=[_directed(lam_lo), _directed(lam_hi, True)],
        rho_lower_fraction=str(factor), rho_lower_bound=_directed(factor),
        branch=branch, gross_cap_used=True, AISI_strength_factors_used=False,
        all_Mdist_at_or_above_floor=True,
        monotonicity='rho=min(1,(lambda-.22)/lambda²) above .673; derivative (-lambda+.44)/lambda³ < 0. Lambda decreases with Mdist.',
        rounded_transition='The capped curve is continuous and nonincreasing; no uncapped overshoot is credited.',
        exact_MRd_floor_fraction=str(value))


def assess(index, *, material=None, Msd_Nmm=None):
    """Return a new own-contour scalar reference; optional signed pure-strong demand.

    Intentionally accepts no span, effective lengths, Lm, restraints or beta.
    A bound for every q>0 needs none and cannot authenticate any of them.
    """
    record = base.registry.select_new_study(index, include_routes=False)
    m = base.material_values(base.DEFAULT_MATERIAL if material is None else material)
    geometry = base.prepare(index)
    section = geometry['section']
    props, p = section['properties'], record['dimensions_mm']
    coefficients, flange = _coefficients(p, m)
    a, b, c, C, d = (coefficients[k] for k in ('a', 'b', 'c', 'C', 'd'))
    root_lo, root_hi = _sqrt_bounds(a*c)
    F_lower = (b+2*root_lo)/(C+d)
    W = _q(props['Ix_strong_mm4'])/(_q(p['h'])/2)
    if W <= 0:
        raise base.OutsideMethod('Positive own-contour strong modulus required')
    # Retain downward exported scalars as the inputs to the subsequent bridge.
    # The replay therefore proves the chain from the actually exported numbers.
    F_output = _directed(F_lower)
    M_lower = W*_q(F_output)
    M_output = _directed(M_lower)
    if min(F_output, M_output) <= 0:
        raise base.OutsideMethod('Positive elastic floor underflows finite output')
    resistance, resistance_proof = _resistance_floor(
        W, _q(m['fy_MPa']), _q(m['gamma']), _q(M_output))
    MRd = _directed(resistance)
    if MRd <= 0:
        raise base.OutsideMethod('Positive resistance floor underflows finite output')
    out = dict(schema=SCHEMA, method=METHOD, scope=SCOPE, eligible=True,
        status='computed_approximate_reference_floor', catalog_index=index,
        catalog_id=record['catalog_id'],
        source_binding=dict(nominal_identity=copy.deepcopy(geometry['nominal_identity']),
            nominal_identity_sha256=geometry['nominal_identity_sha256'],
            nodes_sha256=section['nodes_sha256'], material=m),
        source_documents=copy.deepcopy(SOURCE_DOCUMENTS),
        Fcrd_lower_bound_MPa=F_output, Mdist_lower_bound_Nmm=M_output,
        MRd_lower_bound_Nmm=MRd,
        geometry=dict(global_Ix_mm4=props['Ix_strong_mm4'],
            Sfc_mm3=float(W), Sfc_exact_fraction=str(W),
            Sfc_interval_mm3=[_directed(W), _directed(W, True)],
            global_inner_radius_mm=record['published_properties']['ri_mm'],
            flange_lip_exact={k:str(v) for k,v in flange.items()},
            global_basis='Own rounded midsurface contour; Sfc=Ix/(external h/2)',
            flange_basis='Table 2.3.3-1 sharp midlines b=bf-t and d=lip-t/2, not rounded straight flats',
            lip_angle_degrees=90., flange_corner_radius_included=False),
        proof=dict(coefficients_exact={k:str(v) for k,v in coefficients.items()},
            coefficients_strictly_positive=True,
            F_of_q='(a*q²+b+c/q²)/(C+d*R((q*h)²))',
            R_of_s='(s²+8*s+300)/(s²+28*s+420)',
            R_range='0<R(s)<1 for s>0; denominator-numerator=20*s+120>0',
            numerator_bound='a*q²+c/q² >= 2*sqrt(a*c) for every real q>0',
            denominator_bound='0<C+d*R<C+d',
            bound='F(q)>=(b+2*sqrt(a*c))/(C+d) for every real q>0',
            sqrt_ac_interval_exact=[str(root_lo),str(root_hi)],
            exact_F_floor_fraction=str(F_lower), exact_Mdist_floor_fraction=str(M_lower),
            all_positive_halfwaves=True, exact_minimum_claimed=False,
            existing_Lcr_minimizes='Only a*q²+c/q², not the complete F(q) ratio',
            arithmetic='Exact rational operations on supplied binary scalars; integer square-root enclosure; directed binary64 outputs',
            arithmetic_scope='Bounds the adopted scalar approximation; rounded-contour discretization and model errors are not enclosed'),
        resistance_proof=resistance_proof,
        assumptions=dict(beta=1., xi_web=2., k_phi_N=0.,
            simple_lip_degrees=90., pure_symmetric_strong_bending=True,
            nominal_section_without_holes=True, linear_elastic_small_rotations=True,
            physical_holes_verified=False, physical_restraints_verified=False,
            physical_small_rotation_applicability_verified=False),
        signs=['positive','negative'], elastic_approximation=True,
        approximate_model_lower_bound=True, physical_resistance_bound=False,
        exact_modal_eigenvalue=False, finite_member_eigenvalue_qualified=False,
        member_length_required=False, effective_lengths_used=False,
        physical_supports_created=False, demand_span_changed=False,
        moment_gradient_credit_used=False, panel_restraint_credit_used=False,
        pierin_criticals_transferred=False, weak_axis_qualified=False,
        biaxial_qualified=False, primary_torsion_assessed=False,
        actual_load_capacity_qualified=False, whole_member_approved=False,
        failure_proven=False, floor_exceeded_means='inconclusive_not_failed')
    if Msd_Nmm is not None:
        demand, capacity = abs(_q(Msd_Nmm)), _q(MRd)
        sufficient = demand <= capacity
        out['sufficient_check'] = dict(Msd_Nmm=Msd_Nmm,
            demand_abs_exact_fraction=str(demand),
            utilization_upper_bound=_directed(demand/capacity, True),
            component_sufficient=sufficient, failure_proven=False,
            status='sufficient_under_adopted_approximation' if sufficient else 'inconclusive_floor_exceeded',
            scope='Only the pure strong-axis distortional reference component')
    out['snapshot_sha256'] = digest(out)
    return out


def validate_saved(evidence, *, index, material=None, Msd_Nmm=None):
    """Recompute all source/scalar/scope fields; a rehashed edit is not authority."""
    expected = assess(index, material=material, Msd_Nmm=Msd_Nmm)
    try:
        # Canonical serialization also rejects numeric/boolean substitutions.
        actual_json = json.dumps(evidence, sort_keys=True, allow_nan=False)
        expected_json = json.dumps(expected, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('Malformed strong-distortion floor evidence') from exc
    if actual_json != expected_json:
        raise ValueError('Changed strong-distortion floor or inputs; recalculate explicitly')
    return copy.deepcopy(expected)
