"""Listed sectional conditions from validated EN snapshots; never a design approval.

Readers replay inventory and saved-source semantics, without solving the model.
The policy is attached only by a new explicit calculation of the panorama.
"""
from copy import deepcopy

POLICY = 'isolated_EN_listed_sectional_conditions_v1'
SOURCE = 'EN1993-1-3:2006 §§6.1.5, 6.1.10 / Equação 6.27'
STRESS_SOURCE = SOURCE + ' e §6.1.6'
DEFAULT_TORSION_REASON = ('Torção/empenamento pendentes: demanda Tsv/Tw/B e sua verificação devem ser qualificadas no mesmo modelo. '
    'N=0, telha sem contato, rotação torsional fixa ou índice de flexão baixo não demonstram torção nula.')


def sectional_context(result, ev, *, catalog=False):
    """Called only after the corresponding preserved(result) has succeeded."""
    from .isolated_en_application import digest
    inv = ev['source_inventory']
    keys = [(r['combination_id'], r['limit_state']) for r in inv]
    if (not keys or len(set(keys)) != len(keys)
            or any(not isinstance(k, str) or not k.strip() or s not in ('ELU', 'ELS') for k, s in keys)):
        raise ValueError('Inventário EN vazio, inválido ou duplicado; condição seccional não qualificada.')
    elu = [r for r in inv if r['limit_state'] == 'ELU']
    if len({r['combination_id'] for r in elu}) != len(elu):
        raise ValueError('Inventário ELU EN duplicado.')
    if result['schema'] == 'tercas_batch_results_v1':
        wanted = result.get('load_bundle', {}).get('combinations')
        if not isinstance(wanted, list) or [r['source_combination'] for r in inv] != wanted:
            raise ValueError('Inventário EN não cobre as combinações solicitadas da mesma fonte.')
        raw_cases = {(c['combination']['id'], c['combination']['limit_state']): c['evidence'].get('inclination', {})
                     for c in result['cases']}
    elif result['schema'] == 'NBR14762_one_span_v1':
        if keys != [('DIRECT_ELU', 'ELU'), ('DIRECT_ELS', 'ELS')]:
            raise ValueError('Inventário EN direto incompleto ou divergente.')
        raw_cases = {('DIRECT_'+s, s): result.get('inclination_evidence', {}).get(s, {}) for s in ('ELU', 'ELS')}
    else:
        raise ValueError('Condição seccional EN exclusiva do vão isolado.')
    summaries = result.get('torsion_evidence', {}).get('records', [])
    if any(r['status']=='computed' for r in ev['records']) and [(r['combination_id'], r['limit_state']) for r in summaries] != keys:
        raise ValueError('Inventário da demanda EN ausente, duplicado ou de outra fonte.')
    rows = ev['records']
    if [(r['combination_id'], r['limit_state']) for r in rows] != [(r['combination_id'], 'ELU') for r in elu]:
        raise ValueError('Cobertura ELU EN incompleta ou duplicada.')
    cases = {}
    for item, row in zip(elu, rows):
        cid = item['combination_id']; combo = item['source_combination']
        raw = raw_cases[(cid, 'ELU')]
        bound = (isinstance(combo, dict) and combo.get('id') == cid and combo.get('limit_state') == 'ELU'
            and all(isinstance(combo.get(k), dict) and combo[k] == raw.get(k) for k in ('q_vector', 'P_vector')))
        computed = row['status'] == 'computed'
        if catalog:
            c = row.get('check') or {}
            mv = computed and c.get('shear', {}).get('component_sufficient') is True and c.get('mv', {}).get('component_sufficient') is True
            stress = False  # Catalogue shear / 6.27 never contains EN 6.1.6.
        else:
            web = row.get('web_shear_component', {})
            mv = (computed and web.get('web_shear', {}).get('status') == 'meets'
                  and web.get('bending_shear_component', {}).get('component_qualified') is True)
            stress = computed and (row.get('check') or {}).get('section_stress_criteria_sufficiently_satisfied') is True
        cases[cid] = dict(combination_id=cid, source_combination=deepcopy(combo),
            secondary_shear_sufficient=bound and mv,
            stress_and_interaction_sufficient=bound and mv and stress,
            trace=dict(sectional_policy=POLICY, criterion_scope='EN_sectional_sufficient_condition_only',
                EN_component_schema=ev['schema'], EN_snapshot_sha256=ev['snapshot_sha256'],
                source_analysis_sha256=row['source_analysis_sha256'],
                source_summary_record_sha256=row['source_summary_record_sha256'],
                source_combination_sha256=digest(combo), EN_indices_imported_into_NBR=False))
    computed = sum(r['status'] == 'computed' for r in rows)
    pending = len(rows)-computed
    complete = bool(elu) and computed == len(elu) and pending == 0
    return dict(cases=cases, ELU_cases=len(elu), computed_cases=computed, pending_cases=pending,
        joint_sufficient=complete and all(c['stress_and_interaction_sufficient'] for c in cases.values()),
        catalog=catalog)


def secondary_record(prefix, state, ev, trace, *, context=None, conflict=False):
    from .global_verification import check, _pending, _zero_components, SCHEMA
    if _zero_components(ev, 'parallel'):
        return check(prefix+'secondary_shear_scope', limit_state=state, source=SCHEMA,
            qualified=True, not_applicable=True, trace=trace,
            reason='As componentes q e P locais secundárias são ambas exatamente zero.')
    row = (context or {}).get('sectional', {}).get('cases', {}).get(trace['combination_id'])
    if row and row['secondary_shear_sufficient'] and not conflict:
        return check(prefix+'secondary_shear_scope', limit_state=state, source=SOURCE,
            qualified=True, verdict='meets', trace=dict(trace, **row['trace']),
            reason='Condição suficiente seccional EN §6.1.5 e §6.1.10/6.27 para os dois cortantes e interação N/M/V, na mesma combinação e fonte. Não transfere resistências ou índices à NBR nem conclui o elemento.')
    return _pending(prefix+'secondary_shear_scope', state,
        'Condição seccional para os dois cortantes e interação N/M/V ainda não demonstrada por registro EN íntegro e suficiente desta combinação; nenhuma ação ausente foi zerada.', trace)


def torsion_record(context, reason, *, conflict=False):
    from .global_verification import check, _pending
    section = (context or {}).get('sectional', {})
    if section.get('joint_sufficient') is True and not conflict:
        return check('torsion_warping', limit_state='MODEL', source=STRESS_SOURCE,
            qualified=True, verdict='meets', reason=(
                'Tensões seccionais com torção/empenamento e interação N/M/V atendem por condição suficiente '
                'EN §6.1.6 e §6.1.10/6.27 em todos os casos ELU do mesmo inventário. '
                'Este atendimento seccional não conclui estabilidade, introdução local, ELS ou aprovação global.'),
            trace=dict(sectional_policy=POLICY, criterion_scope='EN_sectional_sufficient_condition_only',
                EN_snapshot_sha256=context['binding']['snapshot_sha256'],
                ELU_cases=section['ELU_cases'], computed_cases=section['computed_cases'], pending_cases=section['pending_cases'],
                case_bindings={k:deepcopy(v['trace']) for k,v in section['cases'].items()}, EN_indices_imported_into_NBR=False))
    return _pending('torsion_warping', 'MODEL', reason)


def validate_saved(result, context):
    """Validate the NEW policy against original saved evidence, not self-hashes."""
    from .global_verification import aggregate, display_summary
    summary = result.get('global_verification', {})
    policy = summary.get('sectional_conditions_policy')
    checks = summary.get('checks', [])
    if summary.get('source_result_schema') in ('NBR14762_one_span_v1', 'tercas_batch_results_v1') and any(
            k in summary and summary[k] is not False for k in ('whole_member_approved',
            'current_adapter_can_approve', 'approved_within_declared_checklist')):
        raise ValueError('O adaptador isolado não aprova o elemento ou checklist completo.')
    if policy is None:
        # Old panoramas retain their original pending interpretation, unchanged.
        if any(c.get('trace', {}).get('sectional_policy') is not None
               or (c.get('id')=='torsion_warping' and c.get('status')!='pending')
               or (c.get('id','').endswith(':secondary_shear_scope') and c.get('source')==SOURCE)
               for c in checks):
            raise ValueError('Política seccional EN removida do panorama.')
        return
    if policy != POLICY:
        raise ValueError('Política seccional EN desconhecida; histórico não requalificado.')
    if any(summary.get(k) is not False for k in ('whole_member_approved', 'current_adapter_can_approve',
            'approved_within_declared_checklist', 'torsion_warping_qualified', 'combined_ELS_approved')):
        raise ValueError('Condição seccional EN não pode aprovar o elemento ou checklist completo.')
    if (summary.get('source_result_schema') != result.get('schema')
            or summary.get('source_input_fingerprint') != result.get('input_fingerprint')):
        raise ValueError('Panorama seccional não corresponde ao resultado/entradas salvos.')
    by_id = {c['id']: c for c in checks}
    if len(by_id) != len(checks):raise ValueError('Critério duplicado no panorama salvo.')
    domain = result.get('model_domain_evidence', {})
    conflict = bool(domain.get('conflict')) or domain.get('status') != 'fixed_model_domain'
    actual = by_id.get('torsion_warping')
    expected = torsion_record(context, context['reason'] if context else DEFAULT_TORSION_REASON, conflict=conflict)
    if actual != expected:raise ValueError('Estado seccional torsional do panorama diverge da fonte EN salva.')
    if result.get('schema') == 'NBR14762_one_span_v1':
        cases = [('DIRECT_ELU', result.get('inclination_evidence', {}).get('ELU', {}))]
    elif result.get('schema') == 'tercas_batch_results_v1':
        from collections import Counter
        source = result.get('cases', [])
        counts = Counter((c['combination']['id'], c['combination']['limit_state']) for c in source)
        cases = [(c['id'], next(r for r in source if r['combination'] == c)['evidence'].get('inclination', {}))
            for c in result.get('load_bundle', {}).get('combinations', [])
            if c['limit_state'] == 'ELU' and counts[(c['id'], 'ELU')] == 1
            and any(r['combination'] == c for r in source)]
    else:cases = []
    expected_ids = set()
    for cid, ev in cases:
        trace = dict(combination_id=cid, member_id='isolated_span', limit_state='ELU', analysis='isolated_span_N_equals_zero')
        expected = secondary_record('ELU:'+cid+':', 'ELU', ev, trace, context=context, conflict=conflict)
        expected_ids.add(expected['id'])
        if by_id.get(expected['id']) != expected:raise ValueError('Estado seccional do cortante secundário diverge da fonte EN salva.')
    if {k for k in by_id if k.endswith(':secondary_shear_scope')} != expected_ids:
        raise ValueError('Inventário seccional do panorama divergente.')
    replay = aggregate([r['id'] for r in checks], checks, inventory_qualified=True)
    for key in ('status', 'complete', 'counts', 'failed_ids', 'pending_ids', 'maximum_available_check', 'by_limit_state', 'listed_checks_only'):
        if summary.get(key) != replay[key]:raise ValueError('Resumo dos critérios listados diverge dos registros salvos.')
    if summary.get('display_summary') != display_summary(summary):raise ValueError('Apresentação do panorama amplia o escopo dos critérios listados.')
