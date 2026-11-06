"""Pinned Ue125 LOCAL weak MLE only: uniform web reduction, not a general MLE.

No caller, global property, ELS, Me, D or complete bending denominator is changed.
The reader repeats scalar arithmetic; no catalogue, contour or member solve.
"""
import copy
import math

from . import ue_catalog_reference as own
from . import ue_catalog_nbr_bending as base

FIELD = 'ue_catalog_nbr_weak_mle_evidence'
SCHEMA = 'ue125_weak_local_mle_v1'
A = 491.6953270111933
CG = 15.116450045292856
IY = 170444.94310055477
S = A * CG
Q = IY + A * CG * CG
B = 117.
T = 2.
FY = 300.
E = 200000.
GAMMA = 1.1
SIGNS = ('positive', 'negative')
SOURCE = 'NBR14762:2010 §§9.2.2,9.2.3,9.8.2.1(a); CBCA2016 pp61–65,73,113'
URL = 'https://www.skylightestruturas.com.br/downloads/101497_manual_lsf_engenharia_2016.pdf'


def _sign(sign):
    if sign not in SIGNS:
        raise ValueError('Sentido explícito positive/alma ou negative/lábios exigido.')


def _rho(sigma):
    if sigma == 0:
        return 1., 0.
    lam = B / T / .95 * math.sqrt(sigma / (4 * E))
    return (1. if lam <= .673 else (1 - .22 / lam) / lam), lam


def _section(width):
    ae = A - T * (B - width)
    ce = S / ae
    iy = Q - S * S / ae
    return dict(web_effective_width_mm=width, Aef_mm2=ae,
                centroid_effective_xy_mm=[ce, 61.5], Iyef_mm4=iy, Ixyef_mm4=0.,
                Wfirst_mm3=iy / max(ce + 1, 49 - ce),
                Wc_web_mm3=iy / (ce + 1), Wc_lips_mm3=iy / (49 - ce),
                effective_web_y_intervals_mm=[[3., 3. + width / 2],
                                              [120. - width / 2, 120.]],
                corners_preserved=True, global_properties_modified=False)


def _other_elements():
    # Conservative uniform 300 MPa envelope of the actual affine flange stress.
    b, d, nominal_lip = 42., 13., 17.
    l0 = b / T / .623 * math.sqrt(FY / E)
    inertia = T * d**3 / 12
    ia = min(399 * T**4 * (.487 * max(0., l0 - .673))**3,
             T**4 * (56 * l0 + 5))
    k = min(4., 4.82 - 5 * nominal_lip / b + .43)
    lf = b / T / .95 * math.sqrt(FY / (E * k))
    ll = d / T / .95 * math.sqrt(FY / (E * .43))
    if not (inertia >= ia and lf <= .673 and ll <= .673):
        raise ValueError('Demonstração das mesas/lábios integralmente efetivos falhou.')
    return dict(compression_envelope_MPa=FY, flange_flat_mm=b, lip_flat_mm=d,
                nominal_lip_mm=nominal_lip, Is_mm4=inertia, Ia_upper_mm4=ia,
                lambda_p0=l0, flange_k=k, flange_lambda=lf, lip_lambda=ll,
                sufficient_fully_effective=True,
                basis='Uniform compression majorant; tension parts fully effective; bends excluded from Is.')


def _web_local():
    lower = B * _rho(FY)[0]
    lo, hi = lower, B
    # This interval guarantees ce<24: first yield remains on the tension lips.
    amin = _section(lower)['Aef_mm2']
    sigma_min = FY * (CG + 1) / (49 - CG)
    ds_max = 50 * FY * T * S / (49 * amin - S)**2
    slope_bound = B * (.5 / .88 - .22 / .88**2) / sigma_min * ds_max
    if not (_section(lower)['centroid_effective_xy_mm'][0] < 24 and slope_bound < 1):
        raise ValueError('Prova de domínio/contração da alma falhou.')
    def residual(w):
        sec = _section(w)
        ce = sec['centroid_effective_xy_mm'][0]
        sigma = FY * (ce + 1) / (49 - ce)
        return w - B * _rho(sigma)[0]
    if residual(lo) > 0 or residual(hi) < 0:
        raise ValueError('Raiz MLE não contida no intervalo demonstrado.')
    for _ in range(64):
        mid = (lo + hi) / 2
        if residual(mid) < 0:
            lo = mid
        else:
            hi = mid
    # Lower endpoint is conservative because Wfirst increases with width.
    sec = _section(lo)
    ce = sec['centroid_effective_xy_mm'][0]
    sigma = FY * (ce + 1) / (49 - ce)
    rho, lam = _rho(sigma)
    if abs(residual(lo)) > 1e-10 or hi - lo > 1e-10:
        raise ValueError('Raiz MLE sem convergência escalar suficiente.')
    return sec, dict(compression_stress_MPa=sigma, lambda_web=lam, rho_web=rho,
                     initial_bracket_mm=[lower, B], final_bracket_mm=[lo, hi],
                     residual_mm=residual(lo), bisection_steps=64,
                     contraction_upper_bound=slope_bound, first_yield_side='tension_lips',
                     stress_basis='Exterior web compression upper bound, not favourable midsurface stress',
                     monotonicity='Both exterior section moduli increase with Aef; more web removal cannot increase Wfirst.')


def _certificate(binding):
    other = _other_elements()
    web, proof = _web_local()
    gross = _section(B)
    local = {}
    for sign, section, audit in (
            ('positive', web, proof),
            ('negative', gross, dict(web_in_tension=True, first_yield_side='compression_lips'))):
        local[sign] = dict(status='computed_local_only',
                           compression_side='web' if sign == 'positive' else 'lips',
                           method='restricted_MLE_one_uniform_AA_web',
                           section=section, proof=audit,
                           MRd_local_Nmm=section['Wfirst_mm3'] * FY / GAMMA,
                           gamma=GAMMA, complete_bending_capacity_qualified=False)
    out = dict(schema=SCHEMA, status='local_components_only', source=SOURCE,
               source_documents=[dict(url=URL, pages='61–65,73–74,113')],
               source_binding=copy.deepcopy(binding), material=copy.deepcopy(base.MATERIAL),
               local_by_sign=local, other_elements_proof=other,
               sign_convention='My_app positive compresses web; physical Vlasov My has opposite sign.',
               geometry_basis='Pinned rounded midsurface; exterior fibres x=-1,49; only central flat web removed.',
               inherited_criticals_used=False, Me_qualified=False, distortional_qualified=False,
               complete_bending_capacity_qualified=False, interaction_9_9_qualified=False,
               ELS_qualified=False, global_properties_modified=False, whole_member_approved=False)
    out['snapshot_sha256'] = own.digest(out)
    return out


def qualify(data):
    """Explicit pinned marker required; edited/out-of-scope markers fail closed."""
    if not own.claims_reference(data):
        return None
    return _certificate(base._saved_binding(data))


def validate_saved(evidence, data):
    """Scalar replay, including types, rejects tampering even after rehashing."""
    expected = _certificate(base._saved_binding(data))
    if not isinstance(evidence, dict) or own.digest(evidence) != own.digest(expected):
        raise ValueError('Certificado MLE fraco alterado; recálculo explícito necessário.')
    return copy.deepcopy(expected)


def flt_effective_section(data, sign, chi):
    """Wc,ef(chi*fy) arithmetic ONLY. Does not qualify chi, Me or FLT resistance.

    A consumer must retain min(local-first-yield, FLT, applicable D). In
    particular the web-compressed FLT trial must not bypass tension first yield.
    """
    base._saved_binding(data)
    _sign(sign)
    if isinstance(chi, bool) or not isinstance(chi, (int, float)) or not math.isfinite(chi) or not 0 < chi <= 1:
        raise ValueError('χ deve ser finito e 0 < χ ≤ 1; este helper não o qualifica.')
    _other_elements()
    rho, lam = _rho(chi * FY)
    section = _section(B * rho if sign == 'positive' else B)
    return dict(status='effective_section_arithmetic_only', sign=sign, chi_supplied=chi,
                stress_MPa=chi * FY, section=section,
                lambda_web=lam if sign == 'positive' else None,
                Wcef_mm3=section['Wc_web_mm3' if sign == 'positive' else 'Wc_lips_mm3'],
                local_first_yield_cap_required=True, Me_qualified=False,
                FLT_resistance_qualified=False, distortional_qualified=False,
                complete_bending_capacity_qualified=False, whole_member_approved=False)
