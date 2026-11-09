"""NBR 9.4 strong-axis reference width for the authenticated rounded Ue.

Only bf0 and the span dispensation are extended. No Table 7 reduction, weak-axis
reclassification, material change, effective section or capacity is produced.
The caller must authenticate one of the 66 complete own-contour nominal rows.
"""
import copy
from fractions import Fraction as F

from . import nbr_ue_shear_lag as legacy

SCHEMA = 'NBR_Ue_shear_lag_applicability_v2_strong_reference_geometry'
MEMBER_MODEL = legacy.MEMBER_MODEL
SOURCE = legacy.SOURCE
SOURCE_DOCUMENTS = [
    dict(title='ABNT NBR14762:2010',
         sha256='c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407',
         printed_pages=[8, 32, 33], pdf_pages_one_based=[14, 38, 39],
         clauses=['3.2.2', '9.4', 'Tabela 7'], role='Governing width and physical-span definition'),
    dict(title='ANSI/SDI AISI S100-2024 and Commentary',
         url='https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf',
         sha256='6ec32742f056d08a0823557d9ce58b69d84312e64a6e656b8ba4b3b10cf4b4ca',
         printed_pages=[27, 28, 115], pdf_pages_one_based=[72, 73, 383],
         clauses=['B4.3', 'C-I1.1-4 geometry definitions only'],
         role='Corroborates inside-web-face projection and overall lip convention only; no AISI resistance or connection calculation'),
]


def strong_reference_geometry(external_dimensions_mm, inner_radius_mm):
    """Exact nominal projection, not the flat width between corner tangencies.

    In the adopted origin, inner web face x=t/2 and outer lip face x=bf-t/2.
    Their projection is bf-t; add the declared overall lip. The two flat
    tangencies instead give bf-2(ri+t), which belongs to local plate geometry.
    Rounded corners do not change the overall projection, but they must fit.
    """
    # Reuse the unchanged v1 dimensional validation, without inventing actions.
    legacy.assess(physical_span_mm=1., external_dimensions_mm=external_dimensions_mm,
                  actions=[], member_model=MEMBER_MODEL)
    d = {k: F(external_dimensions_mm[k]) for k in ('h', 'bf', 'lip', 't')}
    ri = legacy._real(inner_radius_mm, 'raio interno')
    if ri < 0:
        raise ValueError('Shear lag NBR: raio interno negativo.')
    t = d['t']; r = ri+t/2; a = d['h']-t; b = d['bf']-t; end = d['lip']-t/2
    if not (a > 2*r and b > 2*r and r < end < a/2):
        raise ValueError('Shear lag NBR: partes planas/lábios do contorno Ue se sobrepõem.')
    face = t/2; edge = d['bf']-t/2
    clear = edge-face
    width = clear+d['lip']
    return dict(schema='NBR_Ue_strong_reference_geometry_v1',
        external_dimensions_mm=copy.deepcopy(external_dimensions_mm), inner_radius_mm=inner_radius_mm,
        convention='Symmetric 90-degree inward lips; external h/bf/lip/t, uniform thickness, rounded own contour',
        inner_web_face_x_exact_mm=str(face), outer_lip_face_x_exact_mm=str(edge),
        flange_projection_exact_mm=str(clear), nominal_lip_exact_mm=str(d['lip']),
        bf0_exact_mm=str(width), bf0_upper_display_mm=legacy._upper(width),
        local_flange_flat_exact_mm=str(b-2*r), flat_width_substituted_for_projection=False,
        source_documents=copy.deepcopy(SOURCE_DOCUMENTS),
        nominal_geometry_only=True, physical_product_verified=False,
        weak_reference_geometry_qualified=False, section_properties_changed=False)


def assess(*, physical_span_mm, external_dimensions_mm, inner_radius_mm, actions, member_model):
    """Use exact strong bf0; retain the unchanged v1 weak sufficient proof.

    Actions stay individual before cancellation. Multiple-P spacing and support
    exemptions remain unused. A short span remains pending, not a failure.
    """
    original = legacy.assess(physical_span_mm=physical_span_mm,
        external_dimensions_mm=external_dimensions_mm, actions=actions, member_model=member_model)
    geometry = strong_reference_geometry(external_dimensions_mm, inner_radius_mm)
    out = copy.deepcopy(original)
    L = F(physical_span_mm); width = F(geometry['bf0_exact_mm']); threshold = 30*width
    row = out['axes']['normal']; points = row['concentrated_action_indices']
    span = L >= threshold
    if not points:
        status = 'not_triggered_no_concentrated_action'
        reason = 'Sem parcela concentrada não nula no eixo forte; o gatilho de 9.4 não está presente.'
    elif span:
        status = 'not_required_exact_strong_reference_span'
        reason = 'L físico ≥ 30 bf0, com bf0 forte = bf externo − t + lip nominal; dispensa de 9.4 demonstrada.'
    else:
        status = 'pending_shear_lag_qualification'
        reason = ('P presente e L físico < 30 bf0 forte. A largura de referência está definida; '
                  'a redução das propriedades pela Tabela 7 e sua composição local ainda não estão qualificadas. '
                  'Isto não é reprovação resistente. Espaçamento de várias P e isenção em apoio não são usados.')
    row.update(qualified=not points or span, status=status, reason=reason,
        bf0_upper_mm=legacy._upper(width), bf0_upper_exact_mm=str(width),
        sufficient_span_upper_mm=legacy._upper(threshold), sufficient_span_exact_mm=str(threshold),
        sufficient_span_proved=span, bf0_exact_determined=True, bf0_exact_mm=str(width),
        width_bound_proof='Projeção desde a face interna da alma até a borda externa da mesa: bf−t; soma do lip nominal externo.',
        reference_geometry=geometry, previous_external_bound=copy.deepcopy(original['axes']['normal']),
        normative_reduction_required_demonstrated=False,
        below_exact_span_threshold=L < threshold)
    qualified = all(r['qualified'] for r in out['axes'].values())
    out.update(schema=SCHEMA, inner_radius_mm=inner_radius_mm,
        source_documents=copy.deepcopy(SOURCE_DOCUMENTS), qualified=qualified,
        status='qualified_shear_lag_applicability' if qualified else 'pending_shear_lag_qualification',
        reason=('Gatilho ausente ou dispensa demonstrada: bf0 forte exato; eixo fraco conserva o majorante histórico.'
                if qualified else 'Dispensa não demonstrada em todos os eixos; redução da seção ainda pendente, não reprovação.'),
        scope='Aplicabilidade de 9.4 no Ue nominal: referência forte exata e prova suficiente fraca; nenhuma redução/resistência nova.',
        strong_reference_geometry_qualified=True, weak_reference_geometry_qualified=False,
        weak_axis_unchanged=True, reduction_distribution_qualified=False,
        resistance_standard='ABNT NBR14762:2010', foreign_strength_rule_used=False)
    return out


def validate_saved(evidence, **inputs):
    if evidence != assess(**inputs):
        raise ValueError('Shear lag NBR v2 salvo diverge do vão, contorno, ações ou referência forte.')
    return evidence
