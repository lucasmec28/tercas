"""Exact zero-demand applicability in the versioned isolated CT load model.

This is not a torsional resistance or a normative exemption. In the existing
linear, prismatic Vlasov operator, positive GJ and ECw and homogeneous end twist
constraints make the torsional energy positive definite. With every applied
SC torque exactly zero and free end warping, the unique torsional solution is
zero. Bending and moments about CG are neither zeroed nor reinterpreted.

Readers replay the source actions and canonical section, never a member solve.
A refreshed self-hash alone cannot replace that mechanical/source contract.
"""
import math

from .load_application_policy import MODE
from .isolated_en_application import digest

POLICY = 'isolated_CT_exact_zero_torsional_demand_v1'
FIELD = 'torsional_applicability_policy'
SOURCE = 'Aplicabilidade do operador linear Vlasov isolado com forças no CT'
ZERO_FIELDS = ('T_Nmm', 'Tsv_Nmm', 'Tw_Nmm', 'B_Nmm2', 'phi_rad', 'psi_per_mm',
               'B_constitutive_Nmm2', 'T_constitutive_Nmm')
REACTIONS = ('left_total_moment_about_SC_Nmm', 'right_total_moment_about_SC_Nmm',
             'left_generalized_warping_Nmm2', 'right_generalized_warping_Nmm2',
             'total_external_torque_SC_Nmm', 'torque_equilibrium_residual_Nmm')
SECTION_KEYS = ('profile_id', 'nodes_sha256', 'content_sha256', 'properties',
                'thickness_mm', 'normalization', 'stress_scope', 'physical_geometry_verified')


def eligible(result):
    """Only newly assessed, explicitly versioned isolated result schemas."""
    if not isinstance(result, dict):return False
    data = result.get('input_data', {})
    return (isinstance(data, dict) and result.get('schema') in ('NBR14762_one_span_v1', 'tercas_batch_results_v1')
            and data.get('load_application_policy') == MODE)


def _require(condition, message):
    if not condition:raise ValueError(message)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _zero(value):
    return _finite(value) and value == 0


def _positive(value):
    return _finite(value) and value > 0


def _keys(rows):
    _require(isinstance(rows, list) and bool(rows), 'Inventário torsional vazio ou ausente.')
    keys = [(r['combination_id'], r['limit_state']) for r in rows]
    _require(len(set(keys)) == len(keys) and all(isinstance(c, str) and c.strip()
        and s in ('ELU', 'ELS') for c, s in keys), 'Inventário torsional inválido ou duplicado.')
    _require(any(s == 'ELU' for c, s in keys), 'Inventário sem combinação ELU.')
    return keys


def _inventory(result):
    """Rebuild only load arithmetic from inputs, independent of observed rows."""
    data = result['input_data']
    direct = result['schema'] == 'NBR14762_one_span_v1'
    if direct:
        from .direct_roof_separated import combinations
        from .direct_self_weight import evidence
        _require(data.get('load_mode') == 'direct', 'Modo direto divergente.')
        combos = combinations(data)
        _require(result.get('direct_self_weight_evidence') == evidence(data), 'PP direto divergente.')
        _require(result['torsion_evidence'].get('source_combinations') == combos, 'Combinações diretas divergentes.')
        raw = [result['inclination_evidence'][c['limit_state']] for c in combos]
        bundle = None
    else:
        from .batch import area_bundle
        _require(data.get('load_mode') == 'area', 'Modo de área divergente.')
        bundle = area_bundle(data)
        _require(result.get('load_bundle') == bundle, 'Ações de área divergentes das entradas.')
        combos = bundle['combinations']
        cases = result['cases']
        _require(isinstance(cases, list) and [c['combination'] for c in cases] == combos,
            'Casos ausentes, duplicados ou de outra fonte.')
        raw = [c['evidence']['inclination'] for c in cases]
    keys = _keys([dict(combination_id=c['id'], limit_state=c['limit_state']) for c in combos])
    for c, r in zip(combos, raw):
        _require(all(r.get(k) == c[k] for k in ('q_vector', 'P_vector')),
            'Demanda local e combinação não pertencem à mesma fonte.')
    return combos, keys, bundle


def _state(state, analysis, *, support_limit=False):
    _require(isinstance(state, dict) and state.get('combination_id') == analysis['combination_id']
        and state.get('limit_state') == analysis['limit_state'] and state.get('member_id') == analysis['member_id'],
        'Testemunha torsional de outra fonte.')
    _require(_finite(state.get('x_mm')) and 0 <= state['x_mm'] <= analysis['length_mm'],
        'Posição da testemunha torsional inválida.')
    for field in ZERO_FIELDS:
        if support_limit and field in ('B_constitutive_Nmm2', 'T_constitutive_Nmm'):
            _require(state.get(field) is None, 'Campo constitutivo indevido na camada a→0+.')
        else:_require(_zero(state.get(field)), 'Campo torsional não nulo ou ausente: '+field)


def _analysis(result, record, combo, section, actions):
    from .torsion_vlasov.vlasov import METHOD, resolve_actions
    data = result['input_data'];a = record['analysis']
    _require(isinstance(a, dict), 'Demanda torsional ausente.')
    _require(record.get('status') == 'elastic_demand_computed' and record.get('method') == METHOD
        and record.get('source_input_fingerprint') == result['input_fingerprint'], 'Demanda torsional pendente ou desvinculada.')
    _require(a.get('schema') == 'single_vlasov_member_summary_v1' and a.get('method') == METHOD
        and a.get('combination_id') == combo['id'] and a.get('limit_state') == combo['limit_state']
        and a.get('member_id') == ('WALL_GIRT' if data.get('member_application') == 'wall_girt' else 'PURLIN'),
        'Operador isolado/caso não identificado.')
    _require(a.get('section') == {k:section[k] for k in SECTION_KEYS}, 'Seção da demanda diverge da fonte canônica.')
    _require(a.get('length_mm') == data['L_mm'] and _positive(a['length_mm'])
        and all(a.get(k) == data['properties'][k] and _positive(a[k]) for k in ('E_MPa', 'G_MPa'))
        and all(_positive(section['properties'][k]) for k in ('J_mm4', 'Cw_mm6'))
        and _positive(a['G_MPa']*section['properties']['J_mm4'])
        and _positive(a['E_MPa']*section['properties']['Cw_mm6']), 'Rigidez torsional positiva não demonstrada.')
    supports = a.get('support_hypotheses')
    _require(isinstance(supports, dict) and set(supports) == {'left', 'right'}
        and supports == result['torsion_evidence'].get('supports'), 'Vínculos torsionais divergentes.')
    for s in supports.values():
        _require(isinstance(s, dict) and set(s) == {'twist', 'warping', 'origin'}
            and s['twist'] == 'fixed' and s['warping'] == 'free_assumed'
            and isinstance(s['origin'], str) and bool(s['origin'].strip()), 'Vínculo fora do operador homogêneo adotado.')
    domain = a.get('analysis_domain', {})
    required = dict(method=METHOD, prismatic_single_span=True, intermediate_braces=False,
        order=1, small_rotation_kinematics=True, gross_line_section=True, sheet_contact=False,
        sheet_restraint=False, axial_force_in_this_model_N=0., effective_stiffness=False,
        buckling=False, physical_hypotheses_verified=False, finite_load_intervals_minimum_fraction_of_span=.01,
        mesh_domain_limit_is_normative=False)
    _require(set(domain) <= set(required)|{'declared_hypotheses_scope', 'connection_design', 'point_position_scope'}
        and all(domain.get(k) == v and (type(domain[k]) is bool if type(v) is bool else type(domain[k]) is not bool)
                for k, v in required.items()), 'Domínio não é o operador isolado desacoplado de primeira ordem.')
    _require(a.get('demand_coverage_complete_for_declared_model') is True
        and a.get('numerics', {}).get('qualification_passed') is True
        and all(a.get(k) is False for k in ('physical_design_approved', 'resistance_qualified', 'whole_member_approved')),
        'Cobertura/qualificação da demanda não demonstrada.')
    loads = resolve_actions(section, data['L_mm'], actions)
    _require(a.get('loads') == loads, 'Forças, linhas, binários ou torques não correspondem às entradas CT.')
    for load in loads:
        uniform = load['kind'] == 'uniform'
        _require(_zero(load['couple_N' if uniform else 'couple_Nmm'])
            and _zero(load['torque_SC_N' if uniform else 'torque_SC_Nmm']), 'Solicitação torsional não nula.')
    for key in REACTIONS:_require(_zero(a.get('support_reactions', {}).get(key)), 'Reação torsional não nula ou ausente.')
    for key in ('energy_Nmm', 'half_external_work_Nmm'):
        _require(_zero(a.get('numerics', {}).get(key)), 'Energia torsional não nula ou ausente.')
    _require(type(a.get('element_count')) is int and a['element_count'] > 0
        and type(a.get('state_count')) is int and a['state_count'] >= 2*a['element_count'], 'Campo sem cobertura explícita.')
    witnesses = a.get('witnesses')
    _require(isinstance(witnesses, list) and bool(witnesses), 'Testemunhas torsionais ausentes.')
    support = a.get('support_limit_states')
    _require(isinstance(support, list), 'Inventário da camada de apoio ausente.')
    limit = any(x.get('existing_point_position') == 'support_limit' for x in loads)
    _require(len(support) == (1 if limit else 0), 'Camada de apoio ausente ou inesperada.')
    for s in support:_state(s, a, support_limit=True)
    for s in witnesses:_state(s, a, support_limit=s.get('element_index') is None and limit)
    _state(a.get('max_abs_phi'), a, support_limit=(a.get('max_abs_phi') or {}).get('element_index') is None and limit)
    for field in ZERO_FIELDS:
        env = a.get('field_envelopes', {}).get(field)
        _require(isinstance(env, dict) and set(env) == {'minimum', 'maximum', 'maximum_absolute'}, 'Envelope torsional incompleto.')
        for e in env.values():
            _require(isinstance(e, dict) and set(e) == {'value', 'witness_index'} and _zero(e['value'])
                and type(e['witness_index']) is int and 0 <= e['witness_index'] < len(witnesses)
                and _zero(witnesses[e['witness_index']].get(field)), 'Envelope torsional não nulo ou desvinculado.')
    return dict(combination_id=combo['id'], limit_state=combo['limit_state'],
        source_combination_sha256=digest(combo), source_summary_record_sha256=digest(record))


def proof(result):
    """Strict mechanical/source replay. Invalid or unsupported evidence raises."""
    from .application import fingerprint
    from .model_domain import evidence as domain_evidence
    from .torsion_study import section_for, ROLES
    from .load_application_policy import has_contour, lines, torsion_choice
    from .torsion_vlasov.vlasov import METHOD
    _require(eligible(result), 'Modelo CT isolado versionado requerido.')
    data = result['input_data'];net = data.get('three_girt_model', {})
    _require(isinstance(net, dict) and net.get('enabled', False) is False
        and data.get('member_application', 'purlin') in ('purlin', 'wall_girt') and has_contour(data), 'Rede ou seção sem contorno próprio não coberta.')
    _require(result.get('input_fingerprint') == fingerprint(data), 'Entradas desatualizadas.')
    domain = domain_evidence(data)
    _require(not domain['conflict'] and domain['input_token_present'] and result.get('model_domain_evidence') == domain,
        'Domínio de aplicação não vinculado às entradas.')
    section = section_for(data)
    ev = result['torsion_evidence']
    _require(ev.get('schema') == 'purlin_torsion_batch_summary_v1' and ev.get('method') == METHOD
        and ev.get('load_application_policy') == MODE
        and ev.get('source_input_fingerprint') == result['input_fingerprint'], 'Fonte torsional CT ausente ou inválida.')
    combos, keys, bundle = _inventory(result)
    records = ev['records']
    _require(_keys(records) == keys, 'Inventário da demanda incompleto, duplicado ou inesperado.')
    _require(type(ev.get('computed_cases')) is int and ev['computed_cases'] == len(records)
        and type(ev.get('pending_model_cases')) is int and ev['pending_model_cases'] == 0
        and type(ev.get('pending_numerical_cases')) is int and ev['pending_numerical_cases'] == 0, 'Demanda pendente no inventário.')
    roles = ('PP', 'EXTERNAL', 'P') if bundle is None else ('PP', *ROLES)
    expected_lines = lines(section, roles)
    _require(ev.get('load_lines') == expected_lines and ev.get('choice_snapshot') == torsion_choice(data),
        'Linhas de aplicação não vinculadas ao modelo CT.')
    bindings = []
    for combo, record in zip(combos, records):
        if bundle is None:
            from .direct_torsion import actions
            p = section['properties'];cg = p['centroid_xy_mm'];sc = p['shear_center_xy_mm']
            geometry = dict(coherent_torsion_section=True, CG_xy_mm=cg, SC_xy_mm=sc,
                x_from_CG_mm=sc[0]-cg[0], y_from_CG_mm=sc[1]-cg[1], load_application_policy=MODE,
                source=expected_lines['PP']['origin'])
            actual = actions(combo, geometry)
        else:
            from .torsion_vlasov.adapter import actions_for_combination
            actual, missing = actions_for_combination(bundle, combo, section, expected_lines)
            _require(not missing, 'Ações de área incompletas.')
        bindings.append(_analysis(result, record, combo, section, actual))
    return dict(policy=POLICY, criterion_scope='no_torsional_demand_in_declared_linear_model',
        source_input_fingerprint=result['input_fingerprint'], source_torsion_snapshot_sha256=digest(ev),
        source_section_content_sha256=section['content_sha256'], load_application_policy=MODE,
        operator=METHOD, zero_test='exact_zero_no_tolerance',
        uniqueness_basis='GJ>0, ECw>0; homogeneous end twist; free warping; zero applied SC torque',
        ELU_cases=sum(s == 'ELU' for c, s in keys), case_bindings=bindings,
        normative_exemption=False, resistance_qualified=False, whole_member_approved=False)


def record(result):
    """No marker or failed proof grants no applicability change."""
    if not eligible(result):return None
    try:trace = proof(result)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError, OSError):return None
    from .global_verification import check
    return check('torsion_warping', limit_state='MODEL', source=SOURCE,
        qualified=True, not_applicable=True, reason='Sem solicitação torsional neste modelo.', trace=trace)
