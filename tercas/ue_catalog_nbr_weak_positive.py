"""Pinned positive pure-weak reference capacity, not combined-state D approval."""
import copy
import math

from . import ue_catalog_nbr_weak_annex_e as annex
from . import ue_catalog_nbr_weak_mle as mle
from . import ue_catalog_reference as own

SCHEMA = 'ue125_positive_pure_weak_reference_v1'
FIELD = 'ue_catalog_nbr_weak_positive_reference'
RP_URL = ('https://www.buildusingsteel.org/wp-content/uploads/2021/03/'
          'AISI-RP21-01-Development-of-Design-Tables-for-the-Cold-Formed-Steel-Cross-Sections-in-AISI-D100.pdf')


def qualify_reference(data, *, sign, axial_force_N):
    """Explicit pure-component scope. Zero My demand is handled by consumers."""
    if sign != 'positive':
        raise ValueError('Only positive My_app pure weak reference is qualified.')
    if (isinstance(axial_force_N, bool) or not isinstance(axial_force_N, (float, int))
            or not math.isfinite(axial_force_N) or axial_force_N != 0):
        raise ValueError('Pure weak reference requires numeric axial_force_N=0.')
    reference = annex.qualify_reference(data)
    if reference is None:
        return None
    # Smallest certified web area gives largest possible CG for both local
    # first yield and the full chi*fy interval used by Annex E.
    width_min = mle.B*mle._rho(mle.FY)[0]
    cg_max = mle._section(width_min)['centroid_effective_xy_mm'][0]
    lip_min, bend_min = 47., 44.  # Exterior fibers; not midsurface values.
    if not (mle.CG <= cg_max < bend_min <= lip_min):
        raise ValueError('Both lips and connecting bends must remain wholly in tension.')
    decision = dict(status='not_applicable_to_positive_pure_weak_reference',
        mechanism='conventional_flange_lip_distortional_buckling',
        sign='positive', compression_side='web', axial_force_N=0.,
        nodes_sha256=reference['section_constants']['nodes_sha256'],
        material=copy.deepcopy(reference['material']),
        analytical_geometry='Pinned symmetric C; smooth unperforated web, simple lips, rounded corners; no intermediate stiffeners',
        proof=dict(stress_convention='compression-positive sigma=-My_app*(x-CG)/Iy',
            web_effective_width_lower_mm=width_min, centroid_x_upper_mm=cg_max,
            both_lips_exterior_x_lower_mm=lip_min,
            connecting_bends_exterior_x_lower_mm=bend_min,
            lip_tension_distance_lower_mm=lip_min-cg_max,
            connecting_bend_tension_distance_lower_mm=bend_min-cg_max,
            both_lips_wholly_in_tension=True,
            scope='Pure positive weak bending; gross/local/chi-fy effective sections'),
        sources=[dict(document='AISI RP21-01 (2021)', url=RP_URL,
            printed_pages=[5, 10, 11], pdf_pages=[10, 15, 16],
            role='Technical applicability evidence, not NBR normative text or imported DSM resistance',
            evidence='Example I conventional lipped C: web-compression limit states exclude distortional buckling because lips are in tension; global bracing is a separate reason for excluding global buckling.'),
            dict(document='NBR14762:2010', clauses=['9.3', '9.8.2.3'],
                 role='Distortional verification for susceptible sections'),
            dict(document='CBCA Steel Framing Engenharia 2016', printed_pages=[76],
                 role='Distortional verification conditional on susceptibility')],
        T14_exemption=False, roof_distortional_restraint_credit=False,
        Mdist_Nmm=None, MRdD_Nmm=None,
        negative_weak_covered=False, strong_axis_covered=False,
        combined_stress_state_covered=False, physical_section_verified=False)
    positive = reference['by_sign']['positive']
    out = dict(schema=SCHEMA, status='positive_pure_weak_reference_only',
        source_binding=copy.deepcopy(reference['source_binding']),
        annex_e_reference_snapshot_sha256=reference['snapshot_sha256'],
        domain=copy.deepcopy(reference['domain']), sign='positive',
        distortional_applicability=decision,
        MRd_local_Nmm=positive['MRd_local_Nmm'],
        MRd_FLT_reference_component_Nmm=positive['MRd_FLT_reference_component_Nmm'],
        MRd_positive_reference_Nmm=positive['local_FLT_reference_min_Nmm'],
        considered_components=['local_first_yield', 'FLT_reference'],
        nonapplicable_D_excluded_from_minimum=True,
        positive_pure_reference_capacity_qualified=True,
        real_action_applicability='not_assessed',
        actual_load_capacity_qualified=False,
        combined_state_distortion_assessed=False, interaction_9_9_qualified=False,
        primary_torsion_assessed=False, ELS_qualified=False,
        global_properties_modified=False, whole_member_approved=False)
    out['snapshot_sha256'] = own.digest(out)
    return out


def validate_saved(evidence, data):
    expected = qualify_reference(data, sign='positive', axial_force_N=0.)
    if expected is None or not isinstance(evidence, dict) or own.digest(evidence) != own.digest(expected):
        raise ValueError('Saved positive pure weak reference changed or unsupported; recalculate explicitly.')
    return copy.deepcopy(expected)
