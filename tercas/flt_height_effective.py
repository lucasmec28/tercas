"""Documented strong-axis elastic critical references with independent lengths.

ENV 1993-1-1:1992 Annex F, F.2/F.4 and Table F.1.2; the same zj=0 form
is discussed for strong-axis symmetric channels by Vermeylen et al. (2023).
This is NOT a new physical support model, a numerical eigenvalue lower bound,
or a replacement of the historical full-span roof-height solver. Coefficients
are admitted only for the actual distributions and tabulated kz values below.
"""
from __future__ import annotations
import copy
import math

from .ltb_load_height import action_terms, finite, maximum_moment
from .ue_catalog_reference import digest

SCHEMA = 'flt_height_effective_documentary_reference_v1'
METHOD = 'ENV1993_1992_AnnexF_table_F12_zj_zero'
SOURCES = [
    dict(id='ENV1993-1-1:1992', location='Annex F, F.1.2(2)-(5), F.2/F.4, Table F.1.2 rows 1 and 3',
         status='Historical informative elastic formula; not the current EN resistance standard',
         url='https://www.shining-solutions.com/wp-content/uploads/2024/10/DD-ENV-1993-1-1-1992-Steel-Design.pdf'),
    dict(id='Castiglioni_Politecnico_Milano', location='PDF pp47,50; reproduction of ENV Annex F formula/table',
         url='https://www.c430.it/pas/doc/edilizia/acciao-statilimite-ntc.pdf'),
    dict(id='Vermeylen2023', location='Eq1 and discussion of strong-axis symmetric channel sections',
         url='https://orbi.uliege.be/bitstream/2268/306606/1/VermeylenMaxime-Eurosteel%202023.pdf'),
    dict(id='Sahraei2017', location='Eq2: separate uniform/point height potentials',
         url='https://legacy.csce.ca/elf/apps/CONFERENCEVIEWER/conferences/2017/pdfs/EMM/FinalPaper_635.pdf'),
]
# Simply supported IN-PLANE moment diagrams. kz concerns lateral effective
# length, not the in-plane static supports. No interpolation/extrapolation.
COEFFICIENTS = {
    'uniform': {1.: (1.132, .459), .5: (.972, .304)},
    'midspan_point': {1.: (1.365, .553), .5: (1.070, .432)},
}
SCOPE = ('Referência elástica documental de FLT forte com altura e Ly/Lz resistentes '
         'independentes. Diagrama físico biapoiado: somente resultante uniforme ou '
         'concentrada no meio do vão; kz=Ly/L em {0,5;1}, 0,5≤kw=Lz/L≤1. '
         'Sem interpolar coeficientes, alterar o vão das solicitações ou criar apoios. '
         'Não inclui torção primária, pré-deformação, acoplamento biaxial, modos '
         'locais/distorcionais no autovalor nem aprovação global.')


def closed_form(*, E_MPa, G_MPa, Iweak_mm4, J_mm4, Cw_mm6,
                Ly_mm, Lz_mm, C1, C2, zg_mm):
    """Algebraic kernel; the public qualifier owns coefficient/domain selection.

    Ly=kz*L and Lz=kw*L. This never changes the physical M(s) or load stations.
    Rationalized subtraction is stable for large destabilizing height.
    """
    E, G, I, J, Cw, ly, lz, c1 = [finite(v, k, True) for k, v in (
        ('E', E_MPa), ('G', G_MPa), ('Iweak', Iweak_mm4), ('J', J_mm4),
        ('Cw', Cw_mm6), ('Ly', Ly_mm), ('Lz', Lz_mm), ('C1', C1))]
    c2 = finite(C2, 'C2')
    if c2 < 0:
        raise ValueError('C2 must be nonnegative')
    z = finite(c2 * finite(zg_mm, 'zg'), 'C2 zg')
    a = finite((ly/lz)**2*Cw/I + ly*ly*G*J/(math.pi**2*E*I), 'radicand base', True)
    root = math.hypot(math.sqrt(a), z)
    term = a/(root+z) if z >= 0 else root-z
    return finite(c1*math.pi**2*E*I/ly**2*term, 'Me', True)


def symmetry_proof(section):
    """Check reflected contour AND exact cubic Wagner integral, not profile name."""
    p = section['properties']
    cx, cy = p['centroid_xy_mm']; sx, sy = p['shear_center_xy_mm']
    nodes = section['nodes_xy_mm']; t = section['thickness_mm']
    scale = max(1., max(abs(v) for n in nodes for v in n))
    reflection = max(max(abs(a[0]-b[0]), abs(a[1]+b[1]-2*cy))
                     for a, b in zip(nodes, reversed(nodes)))
    terms = []
    for a, b in zip(nodes[:-1], nodes[1:]):
        weight = math.dist(a, b)*t/2
        for u in (.5-.5/math.sqrt(3), .5+.5/math.sqrt(3)):
            x = a[0]+u*(b[0]-a[0])-cx
            y = a[1]+u*(b[1]-a[1])-cy
            terms.append(weight*y*(x*x+y*y))
    integral = math.fsum(terms)
    zj = sy-cy-integral/(2*p['Ix_strong_mm4'])
    ok = (reflection <= 1e-10*scale and abs(sy-cy) <= 1e-10*scale
          and abs(p['Ixy_mm4']) <= 1e-10*math.sqrt(p['Ix_strong_mm4']*p['Iy_weak_mm4'])
          and abs(zj) <= 1e-10*scale)
    return dict(qualified=ok, reflection_residual_mm=reflection,
                strong_Wagner_integral_mm5=integral, strong_zj_residual_mm=zj,
                strong_zj_used_mm=0. if ok else None,
                rationale='Uniform thickness and reflected contour make the strong cubic integrand odd; CG/SC lie on the symmetry axis',
                numerical_tolerance_relative=1e-10)


def _distribution(loads, L):
    """Collapse only actions with IDENTICAL shape functions, by exact sums."""
    uniform = [a for a in loads if a['station'] is None]
    points = [a for a in loads if a['station'] is not None and 0 < a['station'] < L]
    q = math.fsum(a['force'] for a in uniform)
    qh = math.fsum(a['height_tangent_term'] for a in uniform)
    groups = {}
    for action in points:
        groups.setdefault(action['station'], []).append(action)
    point_groups = [dict(station_mm=s, force=math.fsum(a['force'] for a in group),
                         force_height=math.fsum(a['height_tangent_term'] for a in group))
                    for s, group in sorted(groups.items())]
    active_points = [g for g in point_groups if g['force'] or g['force_height']]
    uniform_active = bool(q or qh)
    audit = dict(q_net_N_mm=q, q_height_sum_N=qh, point_groups=point_groups,
                 aggregation='Only identical full-span uniform or collocated point shape functions; heights and torques of individual actions retained',
                 no_action_moved_to_top=True)
    if uniform_active and active_points:
        return None, audit, 'Mistura q+P: coeficientes próprios para esta distribuição não qualificados; nenhuma altura única ou soma harmônica inventada.'
    if uniform_active:
        if q == 0:
            return None, audit, 'q resultante nulo com potencial de altura não nulo: possível instabilidade de giro; não é Me=0 nem caso sem carga.'
        return dict(kind='uniform', signed_force=q, force_height=qh, zg_mm=qh/abs(q)), audit, None
    if active_points:
        if len(active_points) != 1 or active_points[0]['station_mm'] != L/2:
            return None, audit, 'Carga concentrada fora do meio do vão ou múltiplas posições: coeficientes não qualificados.'
        group = active_points[0]; P = group['force']
        if P == 0:
            return None, audit, 'P resultante nulo com potencial de altura não nulo: Me por flexão não definido.'
        return dict(kind='midspan_point', signed_force=P, force_height=group['force_height'],
                    zg_mm=group['force_height']/abs(P)), audit, None
    return None, audit, 'Sem flexão forte de referência nas ações; não se cria uma capacidade nem um índice zero.'


def _finish(evidence):
    evidence['snapshot_sha256'] = digest(evidence)
    return evidence


def qualify_family(data, actions):
    """Fresh deterministic reference for any complete Pierin Ue own contour.

    No local critical or capacity is imported here. A resistance consumer must
    use its own compatible local-section kernel and bind the actions to its
    combination inventory. Readers replay
    this scalar calculation, never the old eigenproblem. No input is mutated.
    """
    from . import pierin_ue_registry as registry
    from . import ue_catalog_reference as own
    from . import roof_top_load as roof
    from .resistance_effective_lengths import configuration
    registry.select_new_study(data['catalog_index'], include_routes=False)
    own.validate(data)
    L = finite(data['L_mm'], 'physical span', True)
    lengths = configuration(data)
    ly = L if lengths is None else lengths['Ly_mm']
    lz = L if lengths is None else lengths['Lz_mm']
    kz, kw = ly/L, lz/L
    section = own.section_for(data); props = section['properties']
    symmetry = symmetry_proof(section)
    material = {k: finite(data['properties'][k], k, True) for k in ('E_MPa', 'G_MPa', 'fy_MPa')}
    evidence = dict(schema=SCHEMA, method=METHOD, status='outside_documented_method',
        elastic_reference_eligible=False, Me_Nmm=None, scope=SCOPE, source_documents=copy.deepcopy(SOURCES),
        physical_span_mm=L, resistance_lengths=copy.deepcopy(lengths), Ly_used_mm=ly, Lz_used_mm=lz,
        kz=kz, kw=kw, manual_effective_lengths_used=lengths is not None,
        physical_supports_created=False, physical_restraints_verified=False,
        length_interpretation='Declared resistance factors in the documentary expression; not reconstructed end springs or newly inferred physical supports',
        demand_span_changed=False, eigenvalue_rescaled_after_solver=False,
        source_binding=dict(catalog_index=data['catalog_index'], nodes_sha256=section['nodes_sha256'],
            section_profile_id=section['profile_id'], property_basis='same own rounded contour', material=material),
        section_properties={k:props[k] for k in ('Ix_strong_mm4','Iy_weak_mm4','J_mm4','Cw_mm6')},
        strong_symmetry=symmetry, actions=copy.deepcopy(actions),
        elastic_formula_is_approximate=True, guaranteed_elastic_lower_bound=False,
        primary_torsion_assessed=False, primary_torsion_predeformation_included=False,
        biaxial_stability_assessed=False, actual_load_capacity_qualified=False,
        whole_member_approved=False)
    # Unknown load heights are a method gap, not silently zero. The existing
    # caller can still present local/distortional components independently.
    if not roof.enabled(data):
        evidence['reason'] = 'Posição de aplicação não adotada: modelo de cobertura ausente ou desabilitado.'
        return _finish(evidence)
    try:
        loads = action_terms(actions, L)
        for a in loads:
            key = 'q_parallel_N_mm' if a['station'] is None else 'P_parallel_N'
            a['parallel_force'] = finite(a.get(key, 0.), key)
    except (ValueError, TypeError) as exc:
        evidence['reason'] = 'Ações não qualificadas: '+str(exc)
        return _finish(evidence)
    evidence.update(
        normal_projection_primary_torque_by_action=[dict(name=a['name'], kind=a['kind'], value=a['primary_torque'],
            units='N' if a['station'] is None else 'Nmm') for a in loads],
        primary_torque_by_action=[dict(name=a['name'], kind=a['kind'],
            value=None if a['primary_torque'] is None else a['primary_torque']-a['height_above_SC_mm']*a['parallel_force'],
            units='N' if a['station'] is None else 'Nmm') for a in loads],
        primary_torque_report_includes_parallel_actions=True,
        height_tangent_by_action=[dict(name=a['name'], value=a['height_tangent_term']) for a in loads],
        maximum_reference_moment_Nmm=float(maximum_moment(L, loads, 0.)),
        normal_projection_only=True,
        individual_parallel_actions_present=any(a.get('q_parallel_N_mm', a.get('P_parallel_N', 0.)) != 0 for a in actions))
    distribution, audit, reason = _distribution(loads, L)
    evidence['load_reduction'] = audit
    if not symmetry['qualified']:
        reason = 'Simetria forte/zj=0 não demonstrados no contorno próprio.'
    elif kz not in (.5, 1.) or not .5 <= kw <= 1.:
        reason = 'Fatores fora do ramo documental implementado: kz deve ser exatamente 0,5 ou 1; kw deve estar entre 0,5 e 1.'
    if reason:
        evidence['reason'] = reason
        return _finish(evidence)
    c1, c2 = COEFFICIENTS[distribution['kind']][kz]
    me = closed_form(E_MPa=material['E_MPa'], G_MPa=material['G_MPa'],
        Iweak_mm4=props['Iy_weak_mm4'], J_mm4=props['J_mm4'], Cw_mm6=props['Cw_mm6'],
        Ly_mm=ly, Lz_mm=lz, C1=c1, C2=c2, zg_mm=distribution['zg_mm'])
    M = evidence['maximum_reference_moment_Nmm']
    expected = abs(distribution['signed_force'])*(L*L/8 if distribution['kind']=='uniform' else L/4)
    if M <= 0 or not math.isclose(M, expected, rel_tol=2e-13, abs_tol=1e-9):
        raise ValueError('Physical maximum differs from documented load distribution')
    evidence.update(status='computed_documentary_elastic_reference', elastic_reference_eligible=True, Me_Nmm=me,
        lambda_reference=me/M, distribution=distribution, C1=c1, C2=c2,
        coefficient_source='ENV1993-1-1:1992 Table F.1.2 row '+('1' if distribution['kind']=='uniform' else '3'),
        coefficient_interpolation_used=False,
        reason='Me documental calculado com as hipóteses declaradas; não é limite inferior certificado nem aprovação da estabilidade física.')
    return _finish(evidence)


def validate_saved(evidence, data, actions):
    """Recheck contour, coefficients, actions, material, lengths and arithmetic."""
    expected = qualify_family(data, actions)
    if evidence != expected:
        raise ValueError('Referência FLT com altura/comprimentos divergente; recalcule explicitamente.')
    return copy.deepcopy(expected)
