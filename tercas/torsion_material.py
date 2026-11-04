"""Explicit one-case nominal material detail; never a resistance verdict.

Only an explicit UI command calls deepen. Rendering/exporting consumes the
preserved compact snapshot and never reconstructs a field.
"""
import copy
import json

FIELD = 'torsion_nominal_material_details'
SCHEMA = 'selected_torsion_nominal_material_details_v1'
SCOPE = ('Tensões nominais do campo de parede fina de Vlasov, na mesma combinação, '
    'seção, ponto e face. A normal é da linha média; não é a tensão normal completa '
    'da fibra exterior. O fator proporcional até escoamento nominal não é '
    'resistência NBR, carga de primeira falha ou aprovação ELU/ELS. '
    'Não usa coeficiente de resistência e escala todas as ações, inclusive PP. '
    'Instabilidade, introdução local de forças e validade geométrica permanecem '
    'fora desta referência nominal de material.')


def available_cases(result):
    """Offer only cases whose existing field passed its numerical guard."""
    ev = result.get('torsion_evidence')
    if not isinstance(ev, dict):return []
    known = {c['combination']['id'] for c in result.get('cases', [])}
    return [r['combination_id'] for r in ev.get('records', [])
            if r.get('combination_id') in known and
            r.get('status') == 'elastic_demand_computed' and
            isinstance(r.get('analysis'), dict)]


def preserved_details(result):
    """Read a matching snapshot only, without retrospective calculation."""
    if FIELD not in result:return {}
    saved = result[FIELD]
    if (not isinstance(saved, dict) or saved.get('schema') != SCHEMA or
            saved.get('source_input_fingerprint') != result.get('input_fingerprint') or
            not isinstance(saved.get('records'), dict)):
        raise ValueError('Detalhes nominais sem vínculo com o resultado; calcule novamente.')
    from .application import fingerprint
    if fingerprint(result['input_data']) != result['input_fingerprint']:
        raise ValueError('Entradas e resultado divergentes; detalhes antigos não reaproveitados.')
    known = {c['combination']['id']: c['combination'] for c in result.get('cases', [])}
    for case_id, record in saved['records'].items():
        if (not isinstance(record, dict) or record.get('schema') != 'purlin_selected_material_study_v1' or
                record.get('combination_id') != case_id or case_id not in known or
                record.get('source_combination') != known[case_id] or
                record.get('source_input_fingerprint') != result['input_fingerprint'] or
                record.get('normative_resistance_qualified') is not False or
                record.get('whole_member_approved') is not False):
            raise ValueError('Detalhe nominal não corresponde à combinação preservada.')
    from .nominal_snapshot import validate_saved
    validate_saved(saved, result)
    return saved['records']


def deepen(result, combination_id):
    """Return a copy with one additional detail; failure leaves the base intact."""
    from .application import fingerprint
    from .torsion_study import configuration, section_for
    from .torsion_vlasov.case_study import study_selected_combination
    if fingerprint(result['input_data']) != result.get('input_fingerprint'):
        raise ValueError('Entradas e resultado divergentes; calcule novamente.')
    if combination_id not in available_cases(result):
        raise ValueError('Combinação sem demanda de torção qualificada no resultado salvo.')
    previous = preserved_details(result)
    configuration(result['input_data'])
    section = section_for(result['input_data'])
    evidence = result['torsion_evidence']
    packet = study_selected_combination(result, combination_id, section=section,
        load_lines=evidence['load_lines'], supports=evidence['supports'])
    # This also refuses NaN/Infinity before a snapshot can become exportable.
    json.dumps(packet, allow_nan=False)
    out = copy.deepcopy(result)
    records = copy.deepcopy(previous)
    records[combination_id] = packet
    out[FIELD] = dict(schema=SCHEMA,
        source_input_fingerprint=result['input_fingerprint'],
        scope=SCOPE, records=records, executed_only_by_explicit_request=True,
        original_mechanics_changed=False, global_assessment_changed=False,
        normative_resistance_qualified=False, whole_member_approved=False)
    return out
