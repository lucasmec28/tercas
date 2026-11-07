"""Pure sufficient applicability test for NBR14762:2010 9.4, nominal Ue.

This does not apply Table 7 to section properties or qualify a resistance.
The authenticated consumer supplies the complete individual action inventory
and the external dimensions of its own, symmetric 90-degree-lip Ue contour.
No catalogue access, geometry generation, solver, or demand changes occur here.
"""
from fractions import Fraction as F
import math

SCHEMA = 'NBR_Ue_shear_lag_applicability_v1'
SOURCE = 'ABNT NBR14762:2010 9.4, Tabela 7 e definições; páginas impressas 32–33'
MEMBER_MODEL = 'isolated_simply_supported'


def _real(value, name, *, positive=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or (positive and value <= 0)):
        raise ValueError('Shear lag NBR: número finito inválido em ' + name)
    return F(value)


def _upper(value):
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError('Shear lag NBR: cota geométrica fora da faixa numérica.') from exc
    if math.isfinite(result) and F(result) < value:
        result = math.nextafter(result, math.inf)
    if not math.isfinite(result):
        raise ValueError('Shear lag NBR: cota geométrica fora da faixa numérica.')
    return result


def assess(*, physical_span_mm, external_dimensions_mm, actions, member_model):
    """Qualify only absence of the concentrated-load trigger or a safe span.

For the supported simply supported member, the reference L in 9.4 is the
physical span, never Lx/Ly/Lz, a mesh interval or a subinterval split at P.
bf0 is NOT set equal to a nominal width: all widths below are upper bounds.
Point forces are retained individually before resultant cancellation. No
multiple-point spacing exemption or support-point exemption is claimed.

The caller must bind dimensions and actions to its authenticated fresh/replay
source. Only documentary-complete Ue rows are intended for the family hook.
"""
    if member_model != MEMBER_MODEL:
        raise ValueError('Shear lag NBR: somente vão físico de viga isolada simplesmente apoiada.')
    L = _real(physical_span_mm, 'vão físico', positive=True)
    if not isinstance(external_dimensions_mm, dict):
        raise ValueError('Shear lag NBR: dimensões externas Ue ausentes.')
    try:
        d = {k: _real(external_dimensions_mm[k], k, positive=True)
             for k in ('h', 'bf', 'lip', 't')}
    except KeyError as exc:
        raise ValueError('Shear lag NBR: dimensão externa Ue ausente: ' + str(exc)) from exc
    if not (d['h'] > 2*d['lip'] and d['bf'] > d['t'] and d['lip'] > d['t']):
        raise ValueError('Shear lag NBR: dimensões incompatíveis com a Ue nominal adotada.')
    if not isinstance(actions, (list, tuple)):
        raise ValueError('Shear lag NBR: inventário individual de ações ausente.')

    inventory = []
    for i, action in enumerate(actions):
        if not isinstance(action, dict) or action.get('kind') not in ('uniform', 'point'):
            raise ValueError('Shear lag NBR: ação não reconhecida no inventário.')
        point = action['kind'] == 'point'
        keys = ('P_down_N', 'P_parallel_N') if point else ('q_down_N_mm', 'q_parallel_N_mm')
        try:
            forces = [_real(action[k], 'ação ' + str(i) + '/' + k) for k in keys]
            s = _real(action['s_mm'], 'posição P') if point else None
        except KeyError as exc:
            raise ValueError('Shear lag NBR: ação incompleta: ' + str(exc)) from exc
        if point and not 0 <= s <= L:
            raise ValueError('Shear lag NBR: posição P fora do vão físico.')
        inventory.append(dict(action_index=i, kind=action['kind'],
            position_exact_mm=str(s) if point else None,
            normal_exact=str(forces[0]), parallel_exact=str(forces[1])))

    # External bf bounds the clear flange width; the nominal lip must be
    # included for the strong-axis stiffened flange (9.4, printed page 33).
    strong = d['bf'] + d['lip']
    # For weak bending, original web is the plate between the two flanges;
    # bound its reference width by full external h (no half-width credit).
    # Original lips are unstiffened outstands, each <= external lip. Keeping
    # the original flange+lip bound too envelopes all these plate widths.
    bounds = dict(normal=strong, parallel=max(d['h'], strong))
    proofs = dict(
        normal='Largura livre da mesa ≤ bf externo; bf0 da mesa enrijecida ≤ bf + lip nominal.',
        parallel=('Alma original entre duas mesas: largura de referência ≤ h externo, sem crédito de metade. '
                  'Lábios originais em balanço: largura ≤ lip. Mantido também o majorante bf + lip das mesas.'))
    axes = {}
    for axis, width in bounds.items():
        points = [r['action_index'] for r in inventory
                  if r['kind'] == 'point' and F(r[axis + '_exact']) != 0]
        uniform = [r['action_index'] for r in inventory
                   if r['kind'] == 'uniform' and F(r[axis + '_exact']) != 0]
        threshold = 30*width
        span_proved = L >= threshold
        if not points:
            status = 'not_triggered_no_concentrated_action'
            reason = 'Sem parcela concentrada não nula neste eixo; o gatilho de 9.4 não está presente.'
        elif span_proved:
            status = 'not_required_sufficient_span'
            reason = 'L ≥ 30 vezes um majorante de bf0; dispensa de 9.4 demonstrada por condição suficiente.'
        else:
            status = 'pending_shear_lag_qualification'
            reason = ('P presente e dispensa pelo majorante geométrico não demonstrada. '
                      'É preciso qualificar bf0 e, se aplicável, recalcular propriedades com a Tabela 7 '
                      'e reduções locais. Isto não é proibição normativa nem reprovação resistente.')
        axes[axis] = dict(qualified=not points or span_proved, status=status, reason=reason,
            concentrated_action_indices=points, uniform_action_indices=uniform,
            bf0_upper_mm=_upper(width), bf0_upper_exact_mm=str(width),
            sufficient_span_upper_mm=_upper(threshold), sufficient_span_exact_mm=str(threshold),
            physical_span_exact_mm=str(L), sufficient_span_proved=span_proved,
            width_bound_proof=proofs[axis], bf0_exact_determined=False,
            normative_reduction_required_demonstrated=False)
    qualified = all(row['qualified'] for row in axes.values())
    return dict(schema=SCHEMA, source=SOURCE, member_model=member_model,
        physical_span_mm=physical_span_mm,
        external_dimensions_mm={k: external_dimensions_mm[k] for k in d},
        axes=axes, action_inventory=inventory, qualified=qualified,
        status='qualified_shear_lag_applicability' if qualified else 'pending_shear_lag_qualification',
        reason=('Gatilho concentrado ausente ou dispensa suficiente de 9.4 demonstrada em ambos os eixos.'
                if qualified else 'Dispensa de shear lag não demonstrada em todos os eixos; resistência sem esta redução ainda não qualificada.'),
        scope='Somente aplicabilidade de 9.4 à Ue nominal; não verifica segurança global nem flambagem local.',
        sufficient_not_necessary=True, individual_actions_before_cancellation=True,
        support_reactions_invented=False, multiple_point_spacing_exemption_used=False,
        reductions_applied=False, section_properties_changed=False, demands_changed=False,
        physical_geometry_verified=False, whole_member_approved=False)


def validate_saved(evidence, **inputs):
    """Deterministic scalar replay; no saved boolean is trusted in isolation."""
    if evidence != assess(**inputs):
        raise ValueError('Shear lag NBR salvo diverge do vão, geometria, ações ou prova de dispensa.')
    return evidence
