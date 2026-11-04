"""Read-only consistency checks for saved nominal material diagnostics.

This checks the saved schema and cross-references. It never reruns an analysis,
recomputes a stress envelope, repairs a record, or certifies physical validity.
"""
import json
import math
import re

FIELDS = ('von_mises', 'normal_tension', 'normal_compression', 'shear_absolute')
FALSE_FLAGS = ('coverage_complete', 'resistance_qualified',
    'normative_resistance_qualified', 'physical_design_approved', 'whole_member_approved')
# Historical compact records omit the coordinates. These counts belong to the
# seven frozen node identities, not to a nominal label or to a live source read.
SEGMENT_COUNTS = {identity: 208 for identity in (
    '004c9cee5033877e4cf1c619627c968c02413aea26fe67a0a5422218ec003f7d',
    'cd50bf66f299d1c072b5a45016cf2ffca777b390332d3386175c34d53c234931',
    '13c8bf700cce34d8fb2bc607e9ae06c305cc59cd7e0e67234a38fb0218704638',
    'e30a0bd327deb1523b527a5737a9f14ac8f8fd189c884588c0339ef7c0b80e47',
    '243974742f83ef47937ec56c938718a37b3e037248c4016eddae0d42af062746',
    'c3d1e69d48f6ad2980e6779eb2509e42e07a2b957ce71c158095fda6b71a4e00',
    '90bf516ec9761304d22aba266bdf9c2f06bf6f73bc6989b46194bbd5d218eab3',
)}
STATE_KEYS = ('combination_id', 'limit_state', 'member_id', 'element_id', 'element_index',
    'x_mm', 's_mm', 'u', 'side', 'position_limit', 'N_N', 'Mx_physical_Nmm',
    'My_physical_Nmm', 'Mforte_R01_Nmm', 'Mfraco_R01_Nmm', 'Vx_N', 'Vy_N',
    'T_Nmm', 'T_CG_Nmm', 'Tsv_Nmm', 'Tw_Nmm', 'B_Nmm2', 'phi_rad', 'psi_per_mm')


def require(condition, message):
    if not condition:
        raise ValueError('Detalhe nominal salvo inválido: ' + message)


def number(value, name):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except (TypeError, OverflowError):
        valid = False
    require(valid, name + ' deve ser finito.')
    return value


def ordered(pair, name):
    require(isinstance(pair, list) and len(pair) == 2, name + ' deve conter dois limites.')
    lo, hi = (number(v, name) for v in pair)
    require(lo <= hi, name + ' está invertido.')
    return lo, hi


def text(value, name):
    require(isinstance(value, str) and bool(value.strip()), name + ' não informado.')


def false_flags(record, names=FALSE_FLAGS):
    require(all(record.get(name) is False for name in names), 'flags de qualificação incompatíveis.')


def digest(value, name):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None,
            name + ' malformado.')


def zero_actions(analysis):
    for action in analysis['loads']:
        if action['kind'] == 'uniform':
            if any(action['q_xy_N_mm']) or action['couple_N']:
                return False
        elif action['kind'] == 'point':
            if any(action['force_xy_N']) or action['couple_Nmm']:
                return False
        else:
            return False
    return True


def validate_witness_position(witness, analysis):
    state = witness['longitudinal_state']
    for key in ('section_u', 'polynomial_u'):
        require(0 <= number(witness.get(key), key) <= 1, 'parâmetro da testemunha fora de [0,1].')
    count = analysis.get('element_count', len(analysis.get('elements', [])))
    require(type(count) is int and count > 0, 'número de elementos de origem inválido.')
    index = state.get('element_index')
    source_piece = witness.get('source_piece')
    if index is None:
        candidates = analysis.get('support_limit_states', [])
        matches = [i for i, source in enumerate(candidates)
                   if state == {key: source[key] for key in STATE_KEYS if key in source}]
        require(len(matches) == 1 and type(source_piece) is int
                and source_piece == count + matches[0],
                'camada limite não corresponde à ação preservada junto ao apoio.')
    else:
        require(type(index) is int and 0 <= index < count
                and type(source_piece) is int and source_piece == index
                and state.get('element_id') == analysis['member_id'] + ':e' + str(index + 1),
                'identidade do elemento da testemunha inválida.')
        require('position_limit' not in state, 'rótulo de camada limite em elemento finito.')
        u = number(state.get('u'), 'Parâmetro longitudinal')
        require(0 <= u <= 1, 'parâmetro longitudinal fora de [0,1].')
        side = 'right' if u == 0 else 'left' if u == 1 else 'interior'
        require(state.get('side') == side, 'lado da seção incompatível com o parâmetro longitudinal.')


def validate_envelope(env, packet, analysis, result):
    require(isinstance(env, dict) and env.get('schema') == 'vlasov_nominal_material_envelope_v1',
            'esquema da envoltória desconhecido.')
    false_flags(env)
    require(env.get('resistance_factor_applied') is False, 'coeficiente resistente incompatível.')
    combo = packet['source_combination']
    require(env.get('combination_id') == combo['id'] and env.get('limit_state') == combo['limit_state']
            and env.get('member_id') == analysis['member_id'], 'identidade da envoltória divergente.')
    section = analysis['section']
    require(env.get('source_method') == analysis['method']
            and env.get('section_profile_id') == section['profile_id']
            and env.get('section_content_sha256') == section['content_sha256'],
            'método ou seção divergente da análise preservada.')
    digest(env.get('source_field_sha256'), 'Hash do campo')
    fy = number(env.get('fy_MPa'), 'fy')
    require(fy > 0 and fy == result['input_data']['properties']['fy_MPa'],
            'fy divergente do material preservado.')
    text(env.get('material_origin'), 'Origem do material')
    phi = number(env.get('source_max_abs_phi_rad'), 'Giro máximo')
    require(phi == abs(analysis['max_abs_phi']['phi_rad']), 'giro divergente da análise preservada.')
    require(type(env.get('source_small_rotation_warning')) is bool
            and env['source_small_rotation_warning'] == analysis['small_rotation_warning'],
            'aviso de giro divergente da análise preservada.')
    maxima = env.get('stress_envelopes')
    require(isinstance(maxima, dict) and set(maxima) == set(FIELDS), 'campos de tensão ausentes ou desconhecidos.')
    for field in FIELDS:
        row = maxima[field]
        require(isinstance(row, dict) and row.get('objective') == field, 'objetivo de tensão divergente.')
        lo, hi = number(row.get('lower_MPa'), field), number(row.get('upper_MPa'), field)
        require(lo <= hi, 'intervalo de tensão invertido.')
        if field in ('von_mises', 'shear_absolute'):
            require(lo >= 0, 'magnitude de tensão negativa.')
        gap = number(row.get('absolute_gap_MPa'), 'Largura do intervalo')
        require(gap == hi - lo, 'largura do intervalo inconsistente.')
        rt = number(row.get('requested_relative_tolerance'), 'Tolerância relativa')
        at = number(row.get('requested_absolute_tolerance_MPa'), 'Tolerância absoluta')
        require(1e-12 <= rt <= 1e-2 and at > 0, 'tolerância fora do domínio do produtor.')
        converged = gap <= max(at, rt * max(abs(lo), abs(hi)))
        require(type(row.get('converged')) is bool and row['converged'] == converged,
                'estado de convergência inconsistente.')
        require(row.get('termination') == 'tolerance' if converged
                else row.get('termination') in ('subdivision_budget', 'depth_budget'),
                'motivo de término inconsistente.')
        witness = row.get('witness')
        require(isinstance(witness, dict) and witness.get('concomitant') is True,
                'testemunha concomitante ausente.')
        state = witness.get('longitudinal_state')
        require(isinstance(state, dict) and state.get('combination_id') == combo['id']
                and state.get('limit_state') == combo['limit_state']
                and state.get('member_id') == analysis['member_id'], 'identidade da testemunha divergente.')
        x = number(state.get('x_mm'), 'Posição longitudinal')
        require(0 <= x <= analysis['length_mm'], 'testemunha fora do vão preservado.')
        if 's_mm' in state:
            require(number(state['s_mm'], 'Coordenada longitudinal') == x, 'coordenadas longitudinais divergentes.')
        validate_witness_position(witness, analysis)
        segment = witness.get('section_segment_index')
        segment_count = SEGMENT_COUNTS.get(section.get('nodes_sha256'))
        require(segment_count is not None and type(segment) is int and 0 <= segment < segment_count,
                'índice de segmento incompatível com a identidade geométrica preservada.')
        require(type(witness.get('saint_venant_face_sign')) is int
                and witness['saint_venant_face_sign'] in (-1, 1), 'face de Saint-Venant inválida.')
        sigma = ordered(witness.get('sigma_midline_MPa_interval'), 'Intervalo de sigma')
        tau = ordered(witness.get('tau_face_MPa_interval'), 'Intervalo de tau')
        vm = ordered(witness.get('von_mises_MPa_interval'), 'Intervalo de von Mises')
        # Algebraic consistency of this stored point, not a new field maximum.
        from .torsion_vlasov.intervals import Interval
        squared = Interval(*sigma).square() + Interval(*tau).square() * 3.
        joint = Interval(max(0., float(squared.lo)), max(0., float(squared.hi))).sqrt()
        require(vm == (float(joint.lo), float(joint.hi)), 'tensões concomitantes da testemunha inconsistentes.')
        witnessed_lower = {
            'von_mises': vm[0], 'normal_tension': sigma[0], 'normal_compression': -sigma[1],
            'shear_absolute': 0. if tau[0] <= 0 <= tau[1] else min(abs(tau[0]), abs(tau[1])),
        }[field]
        require(lo == witnessed_lower, 'limite inferior não corresponde à sua testemunha.')
    converged = all(maxima[field]['converged'] for field in FIELDS)
    require(type(env.get('all_requested_field_bounds_converged')) is bool
            and env['all_requested_field_bounds_converged'] == converged,
            'resumo de convergência inconsistente.')
    expected_status = 'computed_partial_material_envelope' if converged else 'bounded_material_field_not_converged'
    require(packet.get('status') == expected_status, 'estado do detalhe incompatível com a envoltória.')
    vm = maxima['von_mises']
    low, high = vm['lower_MPa'], vm['upper_MPa']
    factor = env.get('proportional_load_to_nominal_material_yield')
    require(isinstance(factor, dict), 'fator proporcional ausente.')
    text(factor.get('reason'), 'Significado do fator')
    if factor.get('kind') == 'exact_zero_field':
        require(zero_actions(analysis) and phi == 0 and factor.get('lower') is None
                and factor.get('upper') is None and factor.get('finite') is False
                and env.get('nominal_material_state') == 'zero_source_field'
                and env.get('algebraic_max_abs_phi_at_nominal_yield_rad') is None,
                'estado de campo nulo inconsistente.')
    else:
        lower = math.nextafter(fy / high, -math.inf) if high > 0 else None
        upper = math.nextafter(fy / low, math.inf) if low > 0 else None
        require(factor.get('lower') == lower and factor.get('upper') == upper,
                'fator proporcional incompatível com os limites de tensão salvos.')
        for value in (factor.get('lower'), factor.get('upper')):
            if value is not None:
                require(number(value, 'Fator proporcional') >= 0, 'fator proporcional negativo.')
        require(type(factor.get('finite')) is bool and factor['finite'] == (lower is not None and upper is not None),
                'indicador de fator finito inconsistente.')
        require(factor.get('kind') == ('bounded_interval' if upper is not None else 'upper_unbounded_within_numerical_bounds'),
                'tipo do fator proporcional inconsistente.')
        state = ('below_nominal_material_yield_in_this_field' if high <= fy else
                 'nominal_material_elastic_limit_exceeded_in_this_field' if low > fy else
                 'indeterminate_within_numerical_bounds')
        require(env.get('nominal_material_state') == state, 'estado nominal do material inconsistente.')
        twist = env.get('algebraic_max_abs_phi_at_nominal_yield_rad')
        if lower is None:
            require(twist is None, 'giro escalado sem fator inferior.')
        else:
            require(isinstance(twist, dict)
                    and twist.get('lower') == math.nextafter(lower * phi, -math.inf)
                    and twist.get('upper') == (None if upper is None else math.nextafter(upper * phi, math.inf)),
                    'giro escalado incompatível com o registro salvo.')


def validate_saved(saved, result):
    """Validate without live source reads; return no replacement or repaired data."""
    json.dumps(saved, allow_nan=False)
    require(saved.get('executed_only_by_explicit_request') is True, 'origem explícita ausente.')
    false_flags(saved, ('original_mechanics_changed', 'global_assessment_changed',
                        'normative_resistance_qualified', 'whole_member_approved'))
    evidence = result.get('torsion_evidence')
    require(isinstance(evidence, dict) and evidence.get('source_input_fingerprint') == result['input_fingerprint']
            and evidence.get('choice_snapshot') == result['input_data'].get('torsion_model'),
            'modelo de torção preservado ausente ou divergente.')
    sources = evidence.get('records')
    require(isinstance(sources, list), 'análises de origem ausentes.')
    by_id = {record['combination_id']: record for record in sources}
    require(len(by_id) == len(sources), 'combinações de origem duplicadas.')
    sources = by_id
    for case_id, packet in saved['records'].items():
        false_flags(packet)
        require(packet.get('source_snapshot_preserved') is True
                and packet.get('all_existing_strength_and_ELS_results_unchanged') is True,
                'origem preservada não confirmada pelo registro.')
        digest(packet.get('case_model_sha256'), 'Hash do caso')
        require(packet.get('load_lines') == evidence.get('load_lines')
                and packet.get('supports') == evidence.get('supports'),
                'linhas ou apoios divergentes da análise preservada.')
        require(case_id in sources, 'combinação sem análise de origem.')
        source = sources[case_id]
        require(source.get('source_input_fingerprint') == result['input_fingerprint'],
                'análise de origem com identificação divergente.')
        env = packet.get('material_envelope')
        if env is None:
            missing = packet.get('missing')
            require(packet.get('status') in ('pending_model_data', 'pending_numerical_qualification')
                    and isinstance(missing, list) and bool(missing)
                    and all(isinstance(x, str) and x.strip() for x in missing),
                    'detalhe pendente sem motivo válido.')
            continue
        analysis = source.get('analysis')
        require(isinstance(analysis, dict) and source.get('status') == 'elastic_demand_computed',
                'campo elástico de origem indisponível.')
        require(packet.get('source_actions') == analysis.get('loads')
                and packet.get('source_analysis_domain') == analysis.get('analysis_domain')
                and packet.get('source_numerics') == analysis.get('numerics'),
                'ações, domínio ou controles da análise divergentes.')
        validate_envelope(env, packet, analysis, result)
