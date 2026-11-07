"""Own Ue125 Annex E REFERENCE, not applicability to actual eccentric actions.

Whole physical span, fork ends, free warping, Cm=1. No manual effective lengths,
roof restraint, favourable gradient/height, D, biaxial or global approval.
"""
import copy
import math

from . import ue_catalog_nbr_bending as base
from . import ue_catalog_nbr_weak_mle as mle
from . import ue_catalog_reference as own
from .core.flt_vrd import chi_flt

SCHEMA = 'ue125_weak_annex_e_reference_v1'
FIELD = 'ue_catalog_nbr_weak_annex_e_reference'
# Exact cubic line integration of the same 134-node rounded/faceted contour.
# Independent Gauss2 and sectorial/SC checks are recorded in tests/docs.
INT_X3_MM5 = 2371211.9640796753
INT_XY2_MM5 = 7479744.204188343
SC_X_MM = -23.516981965583753
SOURCE = 'NBR14762:2010 §9.8.2.2(a), Annex E.2/E.2.1; own rounded contour'


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + ': finite positive numeric value required')
    return float(value)


def _inputs(data):
    binding = base._saved_binding(data)
    from .roof_top_load import configuration
    cfg = configuration(data)
    if cfg is None or cfg['enabled'] is not True:
        raise ValueError('Explicit whole-span fork/free-warping roof model required.')
    return binding, _positive(data.get('L_mm'), 'Physical span L')


def section_constants():
    """Scalar moments of pinned gross contour; no section/member solver."""
    p = base.GEOMETRY
    x0 = mle.CG - SC_X_MM
    ix, iy = p['Ix_cm4']*1e4, p['Iy_cm4']*1e4
    j = (INT_X3_MM5 + INT_XY2_MM5)/(2*iy) + x0
    r2 = (ix + iy)/mle.A + x0*x0
    return dict(A_mm2=mle.A, Ix_mm4=ix, Iy_mm4=iy, J_mm4=p['J_mm4'],
                Cw_mm6=p['Cw_mm6'], CG_x_mm=mle.CG, SC_x_mm=SC_X_MM,
                x0_positive_magnitude_mm=x0, integral_x3_mm5=INT_X3_MM5,
                integral_xy2_mm5=INT_XY2_MM5, j_mm=j, r0_squared_mm2=r2,
                r0_mm=math.sqrt(r2), nodes_sha256=base.PIN['nodes_sha256'],
                coordinates='x,y relative to gross CG; x toward opening, CT has negative x; x0 is magnitude',
                integration='Exact cubic primitives over own straight/faceted midsurface segments; dA=t ds')


def _certificate(data, binding, length):
    sec = section_constants()
    local = mle.qualify(data)
    try:
        q2 = (math.pi/length)**2
        nex = _positive(mle.E*sec['Ix_mm4']*q2, 'Nex')
        nez = _positive((77000.*sec['J_mm4']+mle.E*sec['Cw_mm6']*q2)/sec['r0_squared_mm2'], 'Nez')
        j, r2 = sec['j_mm'], sec['r0_squared_mm2']
        root = math.hypot(j, math.sqrt(r2*nez/nex))
        # Rationalized minus root avoids subtracting near-equal numbers.
        me = {'positive': nex*(root+j), 'negative': r2*nez/(root+j)}
        gross = mle._section(mle.B)
        signs = {}
        for sign, cs in (('positive', 1), ('negative', -1)):
            critical = _positive(me[sign], 'Me reference')
            wc = gross['Wc_web_mm3' if sign == 'positive' else 'Wc_lips_mm3']
            lam = math.sqrt(wc*mle.FY/critical)
            chi, branch = chi_flt(lam)
            effective = mle.flt_effective_section(data, sign, chi)
            flt = _positive(chi*mle.FY*effective['Wcef_mm3']/mle.GAMMA, 'FLT reference component')
            cap = local['local_by_sign'][sign]['MRd_local_Nmm']
            signs[sign] = dict(compression_side='web' if cs == 1 else 'lips', Cs=cs,
                Me_reference_Nmm=critical, Wc_gross_mm3=wc, lambda0=lam,
                chi_FLT=chi, FLT_curve_branch=branch,
                Wcef_at_chi_fy_mm3=effective['Wcef_mm3'],
                effective_section_at_chi_fy=effective['section'],
                MRd_FLT_reference_component_Nmm=flt, MRd_local_Nmm=cap,
                local_FLT_reference_min_Nmm=min(cap, flt),
                local_first_yield_cap_applied=True, D_pending=True,
                real_action_applicability='not_assessed', complete_bending_capacity_qualified=False)
    except (ArithmeticError, ValueError) as exc:
        raise ValueError('Annex E reference arithmetic outside finite supported range: '+str(exc)) from exc
    out = dict(schema=SCHEMA, status='reference_components_only', source=SOURCE,
        source_binding=copy.deepcopy(binding), material=copy.deepcopy(base.MATERIAL),
        local_mle_snapshot_sha256=local['snapshot_sha256'], section_constants=sec,
        domain=dict(physical_span_mm=length, Lx_used_mm=length, Lz_used_mm=length,
            end_restraint='fork_free_warping', intermediate_restraints='none',
            Cm=1., reference_load_position='shear_center',
            axial_force_N=0., bending_reference='pure_weak_axis',
            manual_effective_lengths_used=False, moment_gradient_benefit_used=False,
            favorable_load_height_used=False, roof_restraint_credit=False),
        Nex_N=nex, Nez_N=nez, by_sign=signs,
        real_action_applicability='not_assessed',
        applicability_requirement='Each actual parallel action must pass the separate verified-position classifier; destabilizing/unknown positions remain pending. No inference from resultant sign.',
        Me_reference_qualified=True, actual_load_Me_qualified=False,
        distortional_qualified=False, complete_bending_capacity_qualified=False,
        interaction_9_9_qualified=False, primary_torsion_assessed=False,
        physical_conditions_verified=False, ELS_qualified=False,
        global_properties_modified=False, whole_member_approved=False)
    out['snapshot_sha256'] = own.digest(out)
    return out


def qualify_reference(data):
    """Standalone reference only; never invoked by a production consumer here."""
    if not own.claims_reference(data):
        return None
    binding, length = _inputs(data)
    return _certificate(data, binding, length)


def validate_saved(evidence, data):
    binding, length = _inputs(data)
    expected = _certificate(data, binding, length)
    if not isinstance(evidence, dict) or own.digest(evidence) != own.digest(expected):
        raise ValueError('Saved Annex E reference changed or unsupported; explicit recalculation required.')
    return copy.deepcopy(expected)
