"""Closed, opt-in UI contract for three self-computed bending references.

A marker is consent to this UI mode, never proof of mechanical compatibility.
No resistance formula, geometry normalization or catalogue supplementation here.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

VERSION = 'homogeneous_bending_reference_20261103_r1'
FIELD = 'homogeneous_reference'
REPORTING_VERSION = 'homogeneous_reference_ief_transition_20261103_r4'
LEGACY_ELS_STATUS = 'Pendente: propriedades/críticos e resistências do eixo fraco por sentido não fornecidos; sem aprovação biaxial.'
REFERENCE_ELS_STATUS = ('Propriedades e críticos próprios por sentido fornecidos. Flecha forte: componente com Ief uniaxial. '
                        'Rigidez efetiva sob flexão biaxial/Ief combinado e flecha fraca não qualificadas; '
                        'sem conclusão de ELS completo nem aprovação global.')
ROOT = Path(__file__).with_name('data') / 'homogeneous_references'
REFERENCES = ('U100', 'U125', 'U150')
MANIFEST_SHA256 = '0ed0090e3873c3602693ce24b0631ba82b54290358bad50808c812198df9a90d'
SCOPE = ('Referência própria de componentes de flexão: contorno nominal CBCA arredondado, '
         'ri=t=2 mm, propriedades integrais de parede fina e críticos locais FSM facetada convergida. '
         'Não são propriedades misturadas do catálogo nem críticos/sentidos históricos de Pierin. '
         'E=200000 MPa, G=E/2,6, fy=250 MPa; L e comprimentos efetivos=3000 mm, Cb=Cm=1, N=0. '
         'Garfos matemáticos com rotações de flexão e empenamento livres; ligações reais não verificadas. '
         'Telha sem contato/ligação, somente ações, sem contribuição estrutural. PP no CG pode gerar '
         'torque fora desta referência. Sem resistência 3D, torção, conclusão ELS fraca ou aprovação global '
         'de perfil comercial, produto ou projeto. A flecha forte usa Ief uniaxial; a rigidez efetiva sob '
         'flexão biaxial/Ief combinado e o ELS completo não estão qualificados.')
FROZEN = ('Nesta etapa, materiais, seção, críticos e vínculos permanecem congelados: Nex/Nez manuais '
          'são da referência de 3 m. Alterar um valor físico exige nova qualificação; não é exigência '
          'normativa de vão nem licença para extrapolar os críticos.')
TRACE_NOTE = ('Rastreabilidade M–V no limite junto ao apoio: NBR_branches.MV.result registra o estado '
              'governante entre interior_q_only e support_layer, com o mesmo índice da linha calculada '
              'e de prescribed_point.MV_limit_states. Os dois estados concomitantes ficam em limit_states; '
              'interior_q_only_result preserva o adaptador bruto P=0. Nos estados físicos, a_mm é nulo '
              'e a_limit indica a→0+, sem afastamento finito fictício. A transferência local de P '
              'continua não avaliada; isto não amplia as verificações nem aprova o elemento.')

# Only actions and study identification are editable. Everything else, including
# source prose and complete physical domain dictionaries, must match exactly.
EDITABLE = {'project', 'actions_origin', 'load_mode', 'area_inputs', 'selected_types',
            'q_uls', 'q_sls', 'P_uls', 'P_sls', 'x_uls', 'x_sls',
            'q_parallel_uls', 'q_parallel_sls', 'P_parallel_uls', 'P_parallel_sls'}
OPTIONAL = {FIELD, 'model_domain', 'member_application'}
DIRECT_OPTIONAL = {'q_parallel_uls', 'q_parallel_sls', 'P_parallel_uls', 'P_parallel_sls'}


def source(reference_id, angle=0):
    if reference_id not in REFERENCES or angle not in (0, 5, -5):
        raise ValueError('Referência ou caso não registrado.')
    suffix = {0: 'p0', 5: 'p5', -5: 'm5'}[angle]
    raw_manifest = (ROOT / 'sources.json').read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Registro de referências alterado; cálculo de referência desativado.')
    item = json.loads(raw_manifest)[reference_id]
    raw = (ROOT / item['inputs'][suffix]['file']).read_bytes()
    vector = (ROOT / item['reference_vector']).read_bytes()
    if (hashlib.sha256(raw).hexdigest() != item['inputs'][suffix]['sha256'] or
            hashlib.sha256(vector).hexdigest() != item['reference_vector_sha256']):
        raise ValueError('Dados da referência alterados; cálculo de referência desativado.')
    return json.loads(raw)


def differences(actual, expected, path=''):
    """Exact values, no float tolerance, numeric coercion or dropped keys."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):return [path]
        out = [f'{path}.{k}'.strip('.') for k in sorted(set(actual) ^ set(expected))]
        for key in expected.keys() & actual.keys():
            out += differences(actual[key], expected[key], f'{path}.{key}'.strip('.'))
        return sorted(out)
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):return [path]
        return [item for i, (a, e) in enumerate(zip(actual, expected))
                for item in differences(a, e, f'{path}[{i}]')]
    if isinstance(expected, bool) or isinstance(actual, bool):
        return [] if type(actual) is type(expected) and actual == expected else [path]
    return [] if actual == expected and (not isinstance(actual, float) or math.isfinite(actual)) else [path]


def _protected(data):
    out = {k: copy.deepcopy(v) for k, v in data.items() if k not in EDITABLE | OPTIONAL}
    if isinstance(out.get('inclination'), dict):out['inclination'].pop('value', None)
    return out


def _action_errors(data, expected):
    from .inclination_adapter import configuration
    from .application import build_spec
    from .batch import area_bundle, case_inputs
    errors = []
    for key in ('project', 'actions_origin'):
        if not data.get(key, '').strip():errors.append(key + ' vazio')
    try:
        configuration(data)
        if data.get('load_mode') == 'area':
            bundle = area_bundle(data)
            build_spec(case_inputs(data, bundle['combinations'][0]))
        else:
            for key in ('q_uls','q_sls','P_uls','P_sls','x_uls','x_sls',*DIRECT_OPTIONAL):
                value = data.get(key,0 if key in DIRECT_OPTIONAL else None)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                    errors.append(key + ' não finito/numérico')
            build_spec(data)
    except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
        errors.append('ações/domínio: ' + str(exc))
    return errors


def _editor_errors(data, expected):
    """Shape/complete data only. Recoverable values stay in the restricted UI."""
    errors = []
    from .deflection_scope import enabled as uniaxial_component_enabled
    from .torsion_study import configuration as torsion_configuration
    try:torsion_configuration(data)
    except ValueError as exc:errors.append(str(exc))
    try:uniaxial_component_enabled(data)
    except ValueError as exc:errors.append(str(exc))
    missing = (EDITABLE - DIRECT_OPTIONAL) - set(data)
    if missing:errors.append('Campos de ações/identificação ausentes: ' + ', '.join(sorted(missing)))
    for key in ('project', 'actions_origin'):
        if not isinstance(data.get(key), str):errors.append(key + ' deve ser texto.')
    if data.get('load_mode') not in ('area', 'direct'):errors.append('Modo de ações desconhecido.')
    types = data.get('selected_types')
    if (not isinstance(types, list) or any(not isinstance(v, str) for v in types)
            or len(set(types)) != len(types) or not set(types) <= set(expected['selected_types'])):
        errors.append('Formato/famílias de combinações desconhecidos.')
    area = data.get('area_inputs')
    if not isinstance(area, dict) or set(area) != set(expected['area_inputs']):
        errors.append('area_inputs com campos ausentes/desconhecidos.')
    numeric = {key: data[key] for key in ('q_uls','q_sls','P_uls','P_sls','x_uls','x_sls',*DIRECT_OPTIONAL) if key in data}
    if isinstance(area,dict):numeric.update({'area_inputs.'+k:v for k,v in area.items()})
    inclination = data.get('inclination')
    if not isinstance(inclination,dict) or 'value' not in inclination:
        errors.append('inclination.value ausente.')
    else:numeric['inclination.value'] = inclination['value']
    for key,value in numeric.items():
        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):
            errors.append(key + ' tem tipo não editável.')
    return errors


def assess(data):
    """No mutation. Eligibility is physical identity; activation is separate."""
    if not isinstance(data, dict):return dict(eligible=False, active=False, reference_id=None, reasons=['Objeto JSON inválido.'])
    candidates = []
    for ref in REFERENCES:
        try:expected = source(ref)
        except (OSError, ValueError, KeyError) as exc:
            return dict(eligible=False, active=False, reference_id=None, reasons=[str(exc)])
        from .homogeneous_lengths import FIELD as LENGTH_FIELD, expected_inputs
        if LENGTH_FIELD in data:
            try:expected=expected_inputs(expected,data.get('L_mm'),data[LENGTH_FIELD])
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                return dict(eligible=False,active=False,reference_id=None,reasons=['Contrato de comprimentos: '+str(exc)])
        changed = differences(_protected(data), _protected(expected))
        candidates.append((len(changed), ref, expected, changed))
    _, ref, expected, changed = min(candidates, key=lambda item: item[0])
    reasons = ['Campos protegidos divergentes: ' + ', '.join(changed)] if changed else []
    if data.get('member_application', 'purlin') != 'purlin':reasons.append('Somente terça de cobertura N=0; travessa/3D fora desta referência.')
    from .model_domain import VERSION as DOMAIN_VERSION
    if 'model_domain' in data and data['model_domain'] != DOMAIN_VERSION:reasons.append('model_domain incompatível.')
    reasons.extend(_editor_errors(data, expected))
    action_errors = _action_errors(data, expected) if not reasons else []
    marker = data.get(FIELD)
    token = {'schema': VERSION, 'reference_id': ref}
    if FIELD in data and marker != token:reasons.append('Marcador de ativação inválido ou de outra referência.')
    return dict(eligible=not reasons, active=not reasons and marker == token,
                reference_id=ref if not reasons else None, reasons=reasons,
                action_errors=action_errors, calculable=not reasons and marker == token and not action_errors)


def activate(data):
    state = assess(data)
    if not state['eligible']:raise ValueError('Referência não ativada: ' + '; '.join(state['reasons']))
    out = copy.deepcopy(data)
    out[FIELD] = {'schema': VERSION, 'reference_id': state['reference_id']}
    return out


def load_reference(reference_id, angle=0):
    """Only call from an explicit user action; do not replace imported data."""
    return activate(source(reference_id, angle))


def evidence(data):
    state = assess(data)
    if not state.get('calculable'):raise ValueError('Cálculo de referência desativado: ' + '; '.join(state['reasons'] or state.get('action_errors') or ['ative explicitamente a referência.']))
    manifest = json.loads((ROOT / 'sources.json').read_text())
    from .application import fingerprint
    record = {'schema': VERSION, 'reporting_version': REPORTING_VERSION,
            'reference_id': state['reference_id'], 'scope': SCOPE,
            'frozen_scope': FROZEN, 'support_limit_mv_trace': TRACE_NOTE,
            'source_identity': manifest[state['reference_id']],
            'identity_check': 'Comparação integral dos valores protegidos, não autorização por nome, ID ou hash.',
            'input_sha256': fingerprint(data),
            'physical_conditions_verified': False, 'whole_member_approved': False}
    from .homogeneous_lengths import FIELD as LENGTH_FIELD
    if LENGTH_FIELD in data:
        from .homogeneous_lengths import evidence as length_evidence, scope_text, FROZEN_SCOPE, REPORTING_VERSION as LENGTH_REPORT_VERSION
        record.update(reporting_version=LENGTH_REPORT_VERSION,scope=scope_text(SCOPE),frozen_scope=FROZEN_SCOPE,
                      global_length_derivation=length_evidence(data,source(state['reference_id'])))
    return record


def _clarify_reference_els(result):
    """Only replace the exact legacy missing-data text in qualified ELS output.

    ELU, numeric quantities, input snapshots and approval flags are untouched.
    This is applied only after a successful, revalidated reference calculation.
    """
    if result.get('schema') == 'tercas_batch_results_v1':
        blocks = [case['evidence']['inclination'] for case in result['cases']
                  if case['combination']['limit_state'] == 'ELS']
    else:
        blocks = [result['inclination_evidence']['ELS']]
    for block in blocks:
        if block.get('resistance_status') == LEGACY_ELS_STATUS:
            block['resistance_status'] = REFERENCE_ELS_STATUS


def calculate_reference(data):
    record = evidence(data)  # Always revalidate immediately before calculation.
    from .application import calculate
    from .batch import calculate_batch
    result = calculate_batch(data) if data['load_mode'] == 'area' else calculate(data)
    _clarify_reference_els(result)
    result['homogeneous_reference_evidence'] = record
    result['whole_member_approved'] = False
    return result


def report(doc, result):
    record = result.get('homogeneous_reference_evidence')
    if not record:return
    doc.add_heading('Referência própria homogênea — ' + record['reference_id'], 1)
    for key in ('scope', 'frozen_scope'):doc.add_paragraph(record[key])
    # Serialize this result's recorded evidence; never requalify a historical
    # R1/R2 result with the current trace text or require its new key.
    trace = record.get('support_limit_mv_trace', record.get('trace_limitation'))
    if trace is not None:doc.add_paragraph(trace)
    else:doc.add_paragraph('Texto de rastreabilidade M–V não registrado neste resultado; histórico não requalificado.')
    from .homogeneous_lengths import report as length_report
    length_report(doc,record)
    identity = record['source_identity']
    for key in ('geometry_source', 'method', 'source_scope'):doc.add_paragraph(identity[key])
    doc.add_paragraph('SHA-256 do vetor de referência: ' + identity['reference_vector_sha256'])
    doc.add_paragraph('SHA-256 das entradas calculadas: ' + record['input_sha256'])
    doc.add_paragraph('Calculado: ações informadas e verificações disponíveis de componentes de flexão, '
                      'com o vetor próprio integral; cada resultado mantém suas pendências. '
                      'Esta identificação não aprova o perfil comercial nem o elemento.')

