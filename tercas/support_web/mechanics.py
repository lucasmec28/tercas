"""Pure local web assessment for a declared support load path.

``evaluate_reaction(section, reaction, detail)`` consumes no solver/model state.
Section: ``family`` U/Ue, external ``H``, ``t``, ``ri`` in mm and ``fy`` in MPa.
Reaction: signed ``normal_N`` and ``parallel_N``; ``moment_strong_Nmm`` may be
omitted/None when unknown. They are simultaneous actions, not load envelopes.
Detail: explicit ``route`` (web_connection/flange_contact) and nonempty ``origin``.
For flange_contact, supply real ``c_mm``, ``end_distance_mm``, boolean
``no_opposite_force`` and ``connected``, and ``normal_compressive_sign`` (+1/-1).
When no_opposite_force=False, also supply ``opposite_clear_distance_mm``.
``connected`` means local rotational restraint of the loaded flange, not a web
connection. Distances follow Figure D.1; the support coordinate is not a distance.
The compression sign explicitly identifies which signed normal reaction presses
the declared flange. Optional ``loaded_flange_orientation`` records its physical
description. No contact, flange switching or dimension is inferred from a sign.
The flange/web geometry in this subset is nominally orthogonal (theta=90 deg);
an optional different ``theta_degrees`` is rejected, never normalized to 90.
The flange-contact calculation models an unstiffened web region under D.1;
it gives no credit to, and does not design, a transverse stiffener.

Only the local normal-force criterion is calculated or exempted. Concurrent
parallel force and strong-axis moment are recorded, not discarded, combined
with FRd, or used to invent an extra Annex D interaction requirement.
"""

import math

from ..core.anexo_d import ROWS, classify, frd


SCHEMA = 'support_web_reaction_v1'
SOURCE = 'ABNT NBR 14762:2010 §9.5.1; Anexo D, Tabela D.2 e Figura D.1'
SCOPE = (
    'Somente resistência local da alma à componente normal da reação de apoio. '
    'A rota e os dados físicos são declarados, não inferidos da posição ou do sinal da reação. '
    'No contato, avalia o modelo de alma sem enrijecedor transversal do Anexo D; '
    'não dá crédito nem dimensiona enrijecedor. '
    'Componente paralela e momento forte concomitantes são registrados; flexão, '
    'cortante, suas interações, estabilidade, torção, ligações e aprovação global '
    'continuam em verificações independentes. Não modifica ações nem vínculos.'
)


def _finite(value):
    """No numeric strings, booleans, NaN/inf, or unrepresentable integers."""
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (ValueError, TypeError, OverflowError):
        return False


def _text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def evaluate_reaction(section, reaction, detail=None):
    """Return computed/exempt/not_applicable/not_evaluated, always local only.

    Missing data, malformed values and an unsupported domain are pending, never
    resistance failures. Only a computed finite demand/capacity ratio can fail.
    Inputs are not mutated. An absent load-path detail is not a default contact.
    """
    actions = {name: None for name in ('normal_N', 'parallel_N', 'moment_strong_Nmm')}
    if isinstance(reaction, dict):
        for name in actions:
            if _finite(reaction.get(name)):
                actions[name] = reaction[name]
    common = dict(
        schema=SCHEMA, source=SOURCE, scope=SCOPE, reaction=actions,
        local_criterion_only=True, physical_conditions_verified=False,
        connection_design_checked=False, whole_member_approved=False,
        global_approval=False, other_actions_checked=False,
        moment_strong_known=actions['moment_strong_Nmm'] is not None,
    )

    def pending(code, reason, **extra):
        return dict(common, status='not_evaluated', reason_code=code,
                    reason=reason, **extra)

    if not isinstance(reaction, dict):
        return pending('invalid_reaction', 'Reação ausente ou inválida; nenhuma componente foi presumida.')
    missing = [name for name in ('normal_N', 'parallel_N') if not _finite(reaction.get(name))]
    if missing:
        return pending('invalid_reaction', 'Componentes da reação devem ser números finitos explícitos.',
                       pending_fields=missing)
    moment = reaction.get('moment_strong_Nmm')
    if moment is not None and not _finite(moment):
        return pending('invalid_moment', 'Momento forte informado é inválido; não foi substituído por zero.',
                       pending_fields=['moment_strong_Nmm'])
    normal = reaction['normal_N']
    common.update(normal_force_N=normal, parallel_force_N=reaction['parallel_N'],
                  moment_strong_Nmm=moment)
    if normal == 0:
        return dict(common, status='not_applicable', criterion_status='not_applicable',
                    force_N=0., reason_code='zero_normal_force',
                    reason='Componente normal da reação nula: somente o critério local de força normal não se aplica. '
                           'Componente paralela, momento e demais verificações permanecem independentes.')
    if not isinstance(detail, dict):
        return pending('missing_load_path', 'Falta declarar como a reação é transmitida: alma ligada ou contato em mesa.')
    route = detail.get('route')
    if route not in ('web_connection', 'flange_contact'):
        return pending('missing_load_path', 'Rota de transmissão da reação ausente ou fora do subconjunto implementado.')
    common['route'] = route
    if not _text(detail.get('origin'), 2000):
        return pending('missing_origin', 'Falta a origem do detalhe físico de transmissão da reação.',
                       pending_fields=['origin'])
    common['origin'] = detail['origin']
    if route == 'web_connection':
        return dict(common, status='exempt', criterion_status='exempt',
                    reason_code='web_connection_9_5_1',
                    reason='Dispensada a exigência de enrijecedor transversal neste apoio, conforme §9.5.1, '
                           'pela alma declarada ligada a outra viga ou pilar. '
                           'Esta declaração não dimensiona nem aprova a ligação.',
                    exemption_basis='declared_web_connected_to_beam_or_column')

    sign = detail.get('normal_compressive_sign')
    if not _finite(sign) or sign not in (-1, 1):
        return pending('missing_compression_orientation',
                       'Declare o sinal +1 ou −1 da reação normal que comprime a mesa deste contato; '
                       'a mesa não é escolhida pelo sinal calculado.', pending_fields=['normal_compressive_sign'])
    orientation = detail.get('loaded_flange_orientation')
    if orientation is not None and (not isinstance(orientation, str) or len(orientation) > 2000):
        return pending('invalid_flange_orientation', 'Descrição da orientação da mesa inválida.',
                       pending_fields=['loaded_flange_orientation'])
    common.update(normal_compressive_sign=sign, loaded_flange_orientation=orientation)
    if normal * sign <= 0:
        return pending('noncompressive_contact',
                       'Reação normal não compressiva na mesa declarada; não há troca automática de mesa '
                       'nem verificação de tração/ancoragem por contato.', force_N=abs(normal))
    force = abs(normal)
    common['force_N'] = force

    if not isinstance(section, dict) or section.get('family') not in ('U', 'Ue'):
        return pending('unsupported_section', 'Família fora do subconjunto de seções U/Ue implementado.')
    names = ('H', 't', 'ri', 'fy')
    missing = [name for name in names if not _finite(section.get(name))]
    if missing:
        return pending('invalid_section', 'Altura externa, espessura, raio interno e fy devem ser números finitos explícitos.',
                       pending_fields=missing)
    H, t, ri, fy = (section[name] for name in names)
    if min(H, t, fy) <= 0 or ri < 0:
        return pending('invalid_section', 'Exigem-se H, t e fy positivos e raio interno não negativo.')
    h = H - 2 * (ri + t)
    if not _finite(h) or h <= 0:
        return pending('invalid_flat_web', 'Altura plana h=H−2(ri+t) não finita ou não positiva.')
    c, end_distance = detail.get('c_mm'), detail.get('end_distance_mm')
    missing = [name for name in ('c_mm', 'end_distance_mm') if not _finite(detail.get(name))]
    if missing:
        return pending('invalid_contact_geometry', 'Contato e distância livre ao extremo físico devem ser informados em mm, sem inferência.',
                       pending_fields=missing)
    if c <= 0 or end_distance < 0:
        return pending('invalid_contact_geometry', 'O contato deve ser positivo e a distância livre ao extremo físico não negativa.')
    connected, no_opposite = detail.get('connected'), detail.get('no_opposite_force')
    missing = [name for name in ('connected', 'no_opposite_force') if type(detail.get(name)) is not bool]
    if missing:
        return pending('missing_contact_declarations',
                       'Ligação que restringe a rotação da mesa e ausência de força na mesa oposta exigem booleanos explícitos.',
                       pending_fields=missing)
    opposite_distance = detail.get('opposite_clear_distance_mm')
    if no_opposite:
        if opposite_distance is not None:
            return pending('conflicting_opposite_force', 'Ausência de força oposta não admite distância concorrente à força oposta.')
    elif not _finite(opposite_distance) or opposite_distance < 0:
        return pending('missing_opposite_distance',
                       'Informe a distância livre entre regiões de forças concentradas adjacentes em mesas opostas, '
                       'ou declare explicitamente sua ausência.', pending_fields=['opposite_clear_distance_mm'])
    theta = detail.get('theta_degrees', 90)
    if not _finite(theta) or theta != 90:
        return pending('unsupported_angle', 'O subconjunto da Tabela D.2 requer alma a 90° da superfície de apoio/carregamento.')
    ratios = (h/t, c/t, c/h, ri/t)
    if not all(_finite(value) for value in (*ratios, 1.5*h, 2.5*h)):
        return pending('unrepresentable_geometry', 'Razões ou distâncias de classificação não representáveis por números finitos.')
    trace = dict(family=section['family'], H_external_mm=H, h_flat_mm=h,
                 t_mm=t, ri_mm=ri, fy_MPa=fy, c_mm=c,
                 end_distance_mm=end_distance, opposite_clear_distance_mm=opposite_distance,
                 no_opposite_force=no_opposite, connected=connected,
                 flange_connection='connected' if connected else 'unconnected',
                 theta_degrees=theta, gamma=1.35,
                 transverse_stiffener_model='unstiffened_web_no_stiffener_credit',
                 classification_basis='no_opposite_concentrated_force_declared' if no_opposite else 'declared_opposite_clear_distance',
                 normal_compressive_sign=sign, loaded_flange_orientation=orientation,
                 normal_N=normal, parallel_N=reaction['parallel_N'], moment_strong_Nmm=moment)
    common['domain'] = trace
    if c < 20:
        return pending('contact_below_table_limit', 'Contato c inferior a 20 mm, fora do domínio da Tabela D.2; nenhum comprimento foi aumentado.')
    if h/t > 200 or c/t > 210 or c/h > 2:
        return pending('geometry_outside_table', 'Geometria fora da Tabela D.2: h/t ≤ 200, c/t ≤ 210 e c/h ≤ 2.')
    try:
        count, location = classify(h, end_distance, opposite_distance, no_opposite_force=no_opposite)
        trace.update(loaded_flange_count=count, table_location=location)
        row = ROWS.get((connected, section['family'] == 'Ue', count, location))
        if row is not None:
            trace['table_coefficients'] = dict(zip(('ri_t_max', 'alpha', 'Cr', 'Cc', 'Ch'), row))
        capacity = frd(h=h, t=t, ri=ri, c=c, fy=fy, end_distance=end_distance,
                       opposite_clear_distance=opposite_distance, no_opposite_force=no_opposite,
                       connected=connected, lip=section['family'] == 'Ue', theta=theta)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return pending('outside_table_domain', 'Resistência local não calculada no domínio implementado: '+str(exc))
    if not _finite(capacity) or capacity <= 0:
        return pending('invalid_capacity', 'Resistência local não finita ou não positiva; sem índice de aceitação.')
    index = force / capacity
    if not _finite(index) or index <= 0:
        return pending('invalid_index', 'Índice local não representável por número finito e positivo; sem aceitação.')
    return dict(common, status='computed', FRd_N=capacity, index=index,
                criterion_status='meets' if force <= capacity else 'fails',
                reason_code='local_normal_force_checked',
                reason='Verificado somente F normal compressiva/FRd da alma na reação de apoio; demais ações e critérios são independentes.')
