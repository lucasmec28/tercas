"""Read-only ELS evidence for the completion inventory, never a snapshot upgrade.

The component reader authenticates its complete inventory and mechanics versions.
This presentation does not replace closure requirements or infer a design approval.
"""


def notes(result):
    from .isolated_service_component import saved
    from .isolated_service_ui import rows
    packet = saved(result)
    if packet is None:
        return {}
    cfg = packet['configuration']
    counts = {state: sum(r['status'] == state for r in packet['records'])
              for state in ('computed_linear_comparison', 'pending', 'not_applicable')}
    coverage = ('Inventário autenticado: ' + str(len(packet['records'])) + ' casos; ' +
                str(counts['computed_linear_comparison']) + ' campos calculados; ' +
                str(counts['pending']) + ' pendentes; ' + str(counts['not_applicable']) +
                ' dispensas somente do caso suplementar explicitamente nulo.')
    displayed = rows(packet)
    stiffness = [coverage]
    displacement = []
    criteria = []
    for record, item, row in zip(packet['records'], packet['inventory'], displayed):
        prefix = record['id'] + ' (' + record['kind'] + '): '
        comparison = record['comparison']
        if comparison is None:
            state = ('Somente sucção característica explicitamente nula; não dispensa ELS geral.'
                     if record['status'] == 'not_applicable' else record['reason'] or 'Campo pendente.')
            stiffness.append(prefix + state)
            displacement.append(prefix + state)
            criteria.append(prefix + state)
            continue
        stiffness.append(prefix + row['Rigidez de serviço'] + '. Versão calculada: ' + comparison['schema'] + '.')
        envelope = comparison['envelope']
        displacement.append(prefix + 'Envelope absoluto no campo linear [mm]: [' +
            str(envelope['abs_displacement_lower_mm']) + ', ' + str(envelope['abs_displacement_upper_mm']) + ']. Giro linear máximo salvo [rad]: ' +
            str(comparison.get('stored_linear_twist_max_rad')) +
            '; alerta de giro: ' + str(comparison.get('rotation_screening_warning')) +
            '. Sem limite angular normativo ou qualificação física inferidos.')
        criteria.append(prefix + row['Situação'] + '; limite [mm]: ' + str(item['limit_mm']) +
            '; intervalo do índice: [' + str(comparison['index_lower']) + ', ' + str(comparison['index_upper']) + '].')
    criterion = ('NBR Tabela A.1 notas e/f: rara de mesmo sentido L/180 e sucção característica separada L/120.'
                 if cfg['criterion'] == 'nbr_A1_pair' else
                 'Limite declarado para as combinações ELS selecionadas.' if cfg['criterion'] == 'declared_limit' else
                 'Critério ainda não selecionado.')
    if not packet['records']:
        criteria.append('Inventário de comparações vazio; não há conclusão por ausência de casos.')
    criteria.extend(packet['missing'])
    from .isolated_service_panorama import SYSTEM_SCOPE
    criteria.extend([SYSTEM_SCOPE['construction_stages'], SYSTEM_SCOPE['ponding']['service_combination']])
    return dict(
        service_stiffness=stiffness,
        service_displacement=['Ponto: ' + cfg['point_label'] + '; direção: ' + cfg['direction_label'] +
            '; referência declarada: ' + ('corda dos extremos físicos do mesmo ponto.' if cfg['reference_declared'] else 'ainda pendente.')]+displacement,
        service_criteria=[criterion, 'Evidência do cálculo escolhido, sem aprovação de ELS físico/integral ou da terça.', 'Parcela/origem declarada: ' + cfg['criterion_origin']]+criteria)


def presentation(result):
    """Optional evidence errors do not hide the independent saved inventory."""
    try:
        return notes(result), None
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return {}, 'Evidência ELS combinada não autenticada/exibida: ' + str(exc)
