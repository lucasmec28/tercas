"""Explicit, fail-closed aggregation of checks, without structural calculations.

The generic aggregator can approve a *declared complete checklist*. The current
isolated adapter reports only listed criteria and cannot approve a member.
The current Vlasov adapter inventories its own criteria without that fixed gate.
This module never adds component maxima, invents a resistance, or designs ties.
All input objects and the app's existing numerical results remain unchanged.
"""
from collections import Counter
from copy import deepcopy
from math import isfinite

SCHEMA = 'tercas_global_verification_v1'
CHECK_STATES = ('meets', 'fails', 'pending', 'not_applicable')
COMPUTED = {'computed', 'computed_fixed_load_position',
            'computed_from_supplied_effective_lengths', 'computed_fixed_position',
            'computed_bending_component', 'concomitant_arithmetic_only'}
SCOPE = ('Verificações do perfil no modelo declarado. Não dimensiona tirantes, '
         'cantoneiras, ligações ou ancoragens e não certifica condições de campo.')
_MISSING = object()


def _finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and isfinite(value))


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _safe_trace(value, path='trace'):
    """Keep JSON strict and invalid data explicit; never replace it with zero."""
    if isinstance(value, float) and not isfinite(value):
        return None, [path]
    if isinstance(value, dict):
        out, bad = {}, []
        for key, item in value.items():
            clean, invalid = _safe_trace(item, path+'.'+str(key))
            out[str(key)] = clean
            bad.extend(invalid)
        return out, bad
    if isinstance(value, (list, tuple)):
        out, bad = [], []
        for i, item in enumerate(value):
            clean, invalid = _safe_trace(item, path+'['+str(i)+']')
            out.append(clean)
            bad.extend(invalid)
        return out, bad
    if value is None or isinstance(value, (str, int, float, bool)):
        return value, []
    return None, [path]


def check(check_id, *, limit_state, source, reason='', index=None,
          qualified=False, not_applicable=False, trace=None, verdict=None):
    """No truthiness defaults: None, NaN, strings, booleans and -1 are pending.

    An explicit non-numerical verdict is reserved for coverage/domain checks.
    It cannot contradict a numerical index. A declared exclusion needs a source
    and reason and must not carry a numerical result.
    """
    if not _text(check_id) or limit_state not in ('ELU', 'ELS', 'MODEL'):
        raise ValueError('Identidade da verificação ou estado limite inválido.')
    clean_trace, invalid_trace = _safe_trace(trace or {})
    good = qualified is True and _text(source) and not invalid_trace
    idx = float(index) if _finite(index) and index >= 0 else None
    status = 'pending'
    if not_applicable is True:
        if good and _text(reason) and index is None and verdict is None:
            status = 'not_applicable'
    elif good:
        if idx is not None:
            expected = 'fails' if idx > 1 else 'meets'
            if verdict is None or verdict == expected:
                status = expected
        elif index is None and verdict in ('meets', 'fails') and _text(reason):
            status = verdict
    kind = ('exclusion' if status == 'not_applicable' else 'numeric' if idx is not None
            else 'condition' if status in ('meets', 'fails') else 'unresolved')
    return dict(id=check_id, limit_state=limit_state, status=status, criterion_kind=kind,
                index=idx if status in ('meets', 'fails') else None,
                diagnostic_index=idx if status == 'pending' else None,
                source=source if _text(source) else None,
                reason=reason or ('Resultado ou qualificação aplicável ausente.'
                                  if status == 'pending' else ''),
                trace=clean_trace, invalid_trace_paths=invalid_trace)


def _summary(records, *, inventory_complete=True):
    counts = Counter(r['status'] for r in records)
    if counts['fails']:
        status = 'reprovado'
    elif (not inventory_complete or counts['pending'] or not records
          or not counts['meets']):
        status = 'inconclusivo'
    else:
        status = 'aprovado'
    numeric = [r for r in records if r['status'] in ('meets', 'fails')
               and _finite(r.get('index'))]
    maximum = max(numeric, key=lambda r: r['index']) if numeric else None
    return dict(status=status, complete=bool(records) and inventory_complete
                and not counts['pending'],
                counts={k: counts[k] for k in CHECK_STATES},
                failed_ids=[r['id'] for r in records if r['status'] == 'fails'],
                pending_ids=[r['id'] for r in records if r['status'] == 'pending'],
                maximum_available_check=deepcopy(maximum),
                maximum_is_global_utilization=False)


def aggregate(required_ids, records, *, inventory_qualified=False):
    """Use an inventory independent of the observed outputs.

    A missing combination/check, duplicate id or unexpected result is not
    silently dropped. A known valid failure dominates pending checks, while
    every pending check remains visible. Ratios are never summed or averaged.
    """
    if (not isinstance(required_ids, (list, tuple))
            or any(not _text(k) for k in required_ids)
            or len(set(required_ids)) != len(required_ids)):
        raise ValueError('Inventário deve ter identidades únicas e explícitas.')
    if not isinstance(records, (list, tuple)):
        raise ValueError('Resultados devem formar uma lista.')
    groups = {}
    for item in records:
        if not isinstance(item, dict) or not _text(item.get('id')):
            raise ValueError('Resultado sem identidade.')
        groups.setdefault(item['id'], []).append(item)
    output = []
    for key in required_ids:
        items = groups.pop(key, [])
        if len(items) != 1:
            output.append(check(key, limit_state='MODEL', source=SCHEMA,
                reason='Resultado ausente.' if not items else
                       'Identidade duplicada; nenhuma ocorrência foi escolhida.'))
            continue
        r = deepcopy(items[0])
        if r.get('status') not in CHECK_STATES:
            r = check(key, limit_state='MODEL', source=SCHEMA,
                      reason='Estado de verificação desconhecido.')
        elif r['status'] in ('meets', 'fails'):
            # Revalidate the serialized contract rather than trusting a label.
            r = check(key, limit_state=r.get('limit_state'),
                      source=r.get('source'), reason=r.get('reason', ''),
                      index=r.get('index'), qualified=True,
                      trace=r.get('trace'), verdict=(r['status'] if
                      r.get('criterion_kind') == 'condition' or r.get('index') is not None else None))
        elif r['status'] == 'not_applicable':
            r = check(key, limit_state=r.get('limit_state'),
                      source=r.get('source'), reason=r.get('reason', ''),
                      index=r.get('index'), qualified=True, not_applicable=True,
                      trace=r.get('trace'))
        else:
            # A pending record must not carry an active acceptance index.
            r['index'] = None
        output.append(r)
    for key in sorted(groups):
        output.append(check('unexpected:'+key, limit_state='MODEL', source=SCHEMA,
            reason='Resultado fora do inventário; abrangência requer reconciliação.',
            trace={'unexpected_id': key}))
    inventory_ok = inventory_qualified is True and bool(required_ids) and not groups
    if not inventory_ok:
        output.append(check('inventory_qualification', limit_state='MODEL', source=SCHEMA,
            reason='Inventário vazio, incompleto ou não qualificado.'))
    summary = _summary(output, inventory_complete=inventory_ok)
    model_checks = [r for r in output if r['limit_state'] == 'MODEL']
    listed = {state: _summary([r for r in output if r['limit_state'] == state])
              for state in ('ELU', 'ELS', 'MODEL')}
    by_state = {state: dict(_summary([r for r in output if r['limit_state'] == state]
                                     + model_checks),
                            includes_common_model_gates=True)
                for state in ('ELU', 'ELS')}
    by_state['MODEL'] = listed['MODEL']
    return dict(schema=SCHEMA, scope=SCOPE, **summary, checks=output,
                by_limit_state=by_state, listed_checks_only=listed,
                listed_checks_only_is_complete_limit_state_approval=False,
                approved_within_declared_checklist=summary['status'] == 'aprovado',
                physical_conditions_verified=False,
                rod_connection_design_included=False)


def _record(key, state, raw, *, index=_MISSING, source='', trace=None,
            allowed=COMPUTED, disqualify=False):
    raw = raw if isinstance(raw, dict) else {}
    reason = raw.get('reason') or raw.get('missing') or ''
    if isinstance(reason, (list, tuple)):
        reason = '; '.join(map(str, reason))
    return check(key, limit_state=state, source=source,
                 index=raw.get('index') if index is _MISSING else index,
                 qualified=raw.get('status') in allowed and not disqualify,
                 reason=str(reason), trace=trace)


def _pending(key, state, reason, trace=None):
    return check(key, limit_state=state, source=SCHEMA, reason=reason, trace=trace)


def _zero_components(ev, axis):
    values = [ev.get(k, {}).get(axis) for k in ('q_vector', 'P_vector')]
    return all(_finite(v) and v == 0 for v in values)


def _case_records(result, combination, evidence, *, batch, warnings=(), case_combination=None,roof_component=None,en_context=None):
    """Adapt typed raw evidence, not rounded/localized presentation rows."""
    cid, state = combination['id'], combination['limit_state']
    prefix = state+':'+cid+':'
    data = result.get('input_data', {})
    trace = {'combination_id': cid, 'member_id': 'isolated_span',
             'limit_state': state, 'analysis': 'isolated_span_N_equals_zero'}
    ev = evidence.get('inclination', {}) if batch else evidence.get('inclination_evidence', {}).get(state, {})
    records = []
    domain = result.get('model_domain_evidence', {})
    conflict = bool(domain.get('conflict')) or domain.get('status') != 'fixed_model_domain'
    if state == 'ELU':
        b = evidence.get('NBR_branches', {})
        for key, clause in [('local', '9.8.2.1'), ('distortional', '9.8.2.3')]:
            raw = b.get(key, {})
            exemption = (raw.get('status') == 'exempt_Table14' and
                         isinstance(raw.get('table'), dict) and raw['table'].get('exempt') is True)
            not_applicable = (raw.get('status') == 'not_applicable' and
                              isinstance(raw.get('model_domain'), dict) and
                              raw['model_domain'].get('status') == 'fixed_model_domain' and
                              not raw['model_domain'].get('conflict') and _text(raw.get('reason')))
            if (key == 'distortional' and (exemption or not_applicable)
                    and not conflict):
                records.append(check(prefix+key, limit_state=state, source='NBR14762:2010 '+clause,
                    qualified=True, not_applicable=True, trace=trace,
                    reason=raw.get('reason') or 'Dispensa registrada somente para o eixo forte no domínio atual.'))
            else:
                records.append(_record(prefix+key, state, raw,
                    source='NBR14762:2010 '+clause, trace=trace, disqualify=conflict))
        if roof_component is not None:
            from .roof_top_nbr import COMPUTED as ROOF_COMPUTED, SOURCE as ROOF_SOURCE
            r=next((r for r in roof_component.get('records',[]) if r.get('combination_id')==cid),{})
            roof_trace=dict(trace,roof_top_nbr_snapshot_sha256=roof_component.get('snapshot_sha256'),
                source_me_record_sha256=r.get('source_me_record_sha256'),
                source_combination_sha256=r.get('source_combination_sha256'),
                stability_domain=deepcopy(roof_component.get('domain')),
                source_input_fingerprint=result.get('input_fingerprint'))
            valid=not roof_component.get('error') and not conflict
            records.append(check(prefix+'FLT_height',limit_state=state,source=ROOF_SOURCE,
                qualified=valid and r.get('status')==ROOF_COMPUTED and r.get('criterion_status')!='inconclusive',index=r.get('index'),trace=roof_trace,
                reason=roof_component.get('error') or r.get('reason') or 'Componente FLT no topo ausente.'))
            records.append(check(prefix+'FLT_coverage',limit_state=state,source=ROOF_SOURCE,
                qualified=valid,verdict='meets' if valid else None,trace=roof_trace,
                reason='Vão inteiro [0,L] do esquema de topo; trechos/Cb legados não são vínculos deste modelo.' if valid else
                       roof_component.get('error') or 'Domínio da componente FLT no topo inconsistente.'))
        else:
            segments = evidence.get('FLT_segments', [])
            expected = data.get('segments', [])
            n = len(expected) if isinstance(expected, list) else 0
            if n == 0:
                records.append(_pending(prefix+'FLT_inventory', state, 'Nenhum trecho de estabilidade declarado.', trace))
            for i in range(max(n, len(segments))):
                raw = segments[i] if i < len(segments) else {}
                expected_segment = expected[i] if i < n else None
                snapshot = result.get('input_snapshot', {})
                snapshot_segments = snapshot.get('segments')
                explicit = raw.get('segment')
                binding_ok = (len(segments) == n and i < n and
                              (explicit is None or explicit == expected_segment) and
                              ('segment_id' not in raw or raw['segment_id'] == expected_segment.get('segment_id')) and
                              (snapshot_segments is None or snapshot_segments == expected))
                records.append(_record(prefix+'FLT:'+str(i+1), state, raw,
                    source='NBR14762:2010 9.8.2.2', trace=dict(trace, segment=i+1,
                        segment_input=deepcopy(expected_segment),
                        binding_basis='producer_order_v1',
                        binding_is_independent_identity=False,
                        source_input_fingerprint=result.get('input_fingerprint')),
                    disqualify=conflict or not binding_ok))
            coverage = _segment_coverage(data)
            records.append(check(prefix+'FLT_coverage', limit_state=state, source=SCHEMA,
                qualified=coverage, verdict='meets' if coverage else None,
                reason='Trechos cobrem o vão sem lacuna nem sobreposição.' if coverage else
                       'Cobertura dos trechos de estabilidade ausente ou inconsistente.', trace=trace))
        shear = evidence.get('section_checks', {}).get('shear', {})
        vr = shear.get('VRd_N')
        states = ev.get('states', [])
        values = [s.get('normal', {}).get('V_N') for s in states]
        ratio = (max(abs(v) for v in values)/vr if values
                 and all(_finite(v) for v in values) and _finite(vr) and vr > 0 else None)
        records.append(check(prefix+'shear', limit_state=state, source='NBR14762:2010 9.8.3',
            index=ratio, qualified=ratio is not None and not conflict and
            shear.get('status') == 'computed_from_supplied_inputs',
            reason='' if ratio is not None else 'Solicitações ou resistência ao cortante ausentes.', trace=trace))
        raw = b.get('MV', {})
        governing = raw.get('result', {})
        records.append(_record(prefix+'MV', state, raw,
            index=governing.get('index_squared'), source='NBR14762:2010 9.8.4',
            trace=dict(trace, concomitant_state=deepcopy(governing), numeric_measure='index_squared'),
            disqualify=conflict or not _finite(governing.get('x_mm'))))
        raw = ev.get('biaxial', {})
        governing = raw.get('governing') or {}
        height_biaxial=(r.get('biaxial') if roof_component is not None else None)
        if height_biaxial is not None:
            from .roof_biaxial import SOURCE as BIAXIAL_SOURCE
            g=height_biaxial.get('governing') or {}
            records.append(check(prefix+'biaxial',limit_state=state,source=BIAXIAL_SOURCE,
                qualified=valid and height_biaxial.get('status')=='computed_fixed_position'
                    and height_biaxial.get('criterion_status')!='inconclusive',
                index=g.get('index'),trace=dict(roof_trace,concomitant_state=deepcopy(g)),
                reason=height_biaxial.get('scope','')))
        elif _zero_components(ev, 'parallel') and not conflict:
            records.append(check(prefix+'biaxial', limit_state=state, source=SCHEMA,
                qualified=True, not_applicable=True, trace=trace,
                reason='Estado uniaxial forte N=0: não há parcela de flexão fraca a adicionar. Verificações fortes mantidas.'))
        else:
            records.append(_record(prefix+'biaxial', state, raw,
                index=governing.get('index'), source='NBR14762:2010 9.9, N=0 somente',
                trace=dict(trace, concomitant_state=deepcopy(governing)),
                disqualify=conflict or bool(raw.get('missing')) or
                not all(_finite(governing.get(k)) for k in ('x_mm','Mx_Nmm','My_Nmm')) or
                bool(ev.get('provisional_hypothesis')) or bool(ev.get('u_pierin_assumption'))))
        # Local introduction into the profile is distinct from connection design.
        # A new typed mathematical-limit record is distinct from every real
        # finite contact. Old/malformed exclusions remain pending.
        point = b.get('point', {})
        pnormal = ev.get('P_vector', {}).get('normal')
        pparallel = ev.get('P_vector', {}).get('parallel')
        from .point_limit import saved_exclusion, SOURCE as LIMIT_SOURCE
        mathematical_limit=(batch and not conflict and case_combination==combination
            and saved_exclusion(point,combination,data.get('L_mm'),ev.get('P_vector'))
            and saved_exclusion(point,case_combination,data.get('L_mm'),ev.get('P_vector')))
        if mathematical_limit:
            records.append(check(prefix+'point_introduction_scope',limit_state=state,
                source=LIMIT_SOURCE,qualified=True,not_applicable=True,reason=point['reason'],
                trace=dict(trace,P_normal_N=pnormal,P_parallel_N=pparallel,
                           prescribed_position='support_limit',criterion_scope='mathematical_limit',
                           physical_contact_checked=False,physical_conditions_verified=False,
                           connection_design_checked=False)))
        elif (_finite(pnormal) and _finite(pparallel)
                and pnormal == 0 and pparallel == 0):
            records.append(check(prefix+'point_introduction_scope', limit_state=state,
                source=SCHEMA, qualified=True, not_applicable=True, trace=trace,
                reason='Nenhuma força concentrada P nas duas componentes locais desta combinação.'))
        else:
            from .point_contact import saved_numeric_qualified
            bound = saved_numeric_qualified(point, result, combination, ev.get('P_vector'),
                batch=batch, case_combination=case_combination)
            record = _record(prefix+'point_introduction_scope', state, point,
                source='NBR14762:2010, introdução localizada no perfil, domínio implementado',
                trace=dict(trace, P_normal_N=pnormal, P_parallel_N=pparallel,
                           prescribed_position=combination.get('point_position')),
                disqualify=conflict or not bound)
            if isinstance(point, dict) and point.get('status') == 'computed' and not bound:
                record['reason'] = 'Contato finito salvo não vinculado às ações, posição, declarações ou origem atuais; resistência não recalculada.'
            records.append(record)
        # Internal coverage only. These are not new table/UI rows.
        records.append(check(prefix+'axial_scope', limit_state=state, source=SCHEMA,
            qualified=True, not_applicable=True, trace=trace,
            reason='Rota isolada explicitamente N=0; não é uma verificação de sistema com N concomitante.'))
        from .isolated_en_panorama import secondary_record
        records.append(secondary_record(prefix,state,ev,trace,context=en_context,conflict=conflict))
    else:
        raw = evidence.get('ELS', {})
        gross_record=None
        from .biaxial_component import preserved_snapshot,claims_result
        if claims_result(result):
            try:gross_record=preserved_snapshot(result)
            except (ValueError,TypeError,KeyError,ArithmeticError):conflict=True
        aa_record=None
        from .aa_component import preserved_snapshot as aa_snapshot, claims_result as aa_claims, SCHEMAS as AA_SCHEMAS
        if aa_claims(result):
            try:aa_record=aa_snapshot(result)
            except (ValueError,TypeError,KeyError,ArithmeticError,IndexError):conflict=True
        compatible = (raw.get('criterion_status') in ('meets', 'fails')
                      and raw.get('diagnostic_only') is not True and not conflict)
        records.append(_record(prefix+'deflection', state, raw,
            source=raw.get('source','NBR14762:2010 9.8.5, critério declarado'),
            trace=dict(trace, x_mm=raw.get('x_mm'),
                gross_biaxial_component=(dict(schema=gross_record['schema'],snapshot_sha256=gross_record['snapshot_sha256'],case_id=cid) if gross_record else None),
                **({'aa_web_component':dict(schema=aa_record['schema'],snapshot_sha256=aa_record['snapshot_sha256'],case_id=cid,upper_bound_mm=raw.get('upper_bound_mm'),index_kind=raw.get('index_kind'))} if aa_record else {}),
                criterion_scope=raw.get('criterion_scope'),
                local_uniaxial_component=deepcopy(raw.get('local_uniaxial_component')),
                deflection_scope_evidence=deepcopy(result.get('deflection_scope_evidence'))),
            disqualify=not compatible))
        # A saved local-component calculation defines the requested objective.
        # Do not infer this from an input token on a historical result. Optional
        # combined-service requests retain their own coverage/pending markers.
        from .deflection_scope import MODE as LOCAL_MODE, recorded_local_objective
        if recorded_local_objective(result, raw) and not conflict:
            records.append(check(prefix+'combined_ELS_scope', limit_state=state,
                source='Escopo declarado: '+LOCAL_MODE, qualified=True, not_applicable=True,
                reason='ELS combinado fora do objetivo solicitado de flecha local. '
                       'Análise adicional opcional; sua ausência não é pendência normativa deste critério. '
                       'Esta delimitação não aprova o membro nem comprova deslocamento torsional nulo.',
                trace=dict(trace, criterion_scope='outside_requested_local_deflection_objective',
                           physical_ELS_approval=False, whole_member_approved=False)))
        elif raw.get('component_schema') in ('own_Ue_gross_biaxial_component_snapshot_v1','own_Ue_isolated_girt_gross_biaxial_component_snapshot_v1'):
            records.append(_pending(prefix+'combined_ELS_scope',state,
                ('Componente flexional biaxial integral qualificada no campo/contorno registrado; ' if gross_record and raw.get('qualified_gross_flexural_component') else 'Componente flexional biaxial ainda inconclusiva ou sem registro válido; ')+
                'ELS físico completo permanece pendente, inclusive torção/empenamento e aplicabilidade da primeira ordem.', trace))
        elif raw.get('component_schema') in AA_SCHEMAS:
            records.append(_pending(prefix+'combined_ELS_scope',state,
                ('Teto suficiente da componente flexional AA no modelo registrado; ' if aa_record and raw.get('criterion_status')=='meets' else 'Teto AA inconclusivo ou sem registro válido; ')+
                'não é flecha exata e não qualifica ELS físico completo, torção, empenamento ou estabilidade.',trace))
        elif _zero_components(ev, 'parallel'):
            records.append(_pending(prefix+'combined_ELS_scope', state,
                'Componentes paralelas nulas dispensam somente a flexão fraca. '
                'Não demonstram torque nulo no centro de torção nem deslocamento torsional nulo '
                'no ponto de serviço. ELS completo e aplicabilidade da análise permanecem pendentes.',
                dict(trace, zero_parallel_actions_only=True,
                     torsional_displacement_excluded=False)))
        else:
            records.append(_pending(prefix+'combined_ELS_scope', state,
                'Rigidez efetiva combinada/ELS completo do estado biaxial não qualificados. Flecha escalar/bruta não libera esta verificação.', trace))
    return records


def _segment_coverage(data):
    L, segments = data.get('L_mm'), data.get('segments')
    if not _finite(L) or L <= 0 or not isinstance(segments, list) or not segments:
        return False
    intervals = []
    for seg in segments:
        if not isinstance(seg, dict):
            return False
        a, b = seg.get('start_mm'), seg.get('end_mm')
        if not (_finite(a) and _finite(b) and 0 <= a < b <= L):
            return False
        intervals.append((a, b))
    end = 0.
    for a, b in sorted(intervals):
        if a != end:
            return False
        end = b
    return end == L


def axial_interaction_record(segment, *, expected_combination_id,
                             expected_section_id, expected_stability_member_id,
                             expected_region_id, expected_segment_id):
    """Consume one §9.9 concomitant segment; never rebuild it from extrema.

    An arithmetic check is independent of the global-analysis qualification.
    The latter remains a separate required gate. Missing B stays outside this
    N+M check and cannot be treated as zero or receive an invented denominator.
    """
    identity = (expected_combination_id, expected_section_id, expected_stability_member_id,
                expected_region_id, expected_segment_id)
    key = 'ELU:axial_bending:'+repr(identity)
    ids = dict(combination_id=expected_combination_id, section_id=expected_section_id,
               stability_member_id=expected_stability_member_id,
               region_id=expected_region_id, segment_id=expected_segment_id)
    raw = segment if isinstance(segment, dict) else {}
    maximum = raw.get('maximum')
    states = raw.get('states', [])
    match = all(_text(v) and raw.get(k) == v for k, v in ids.items())
    concomitant = (isinstance(maximum, dict) and isinstance(states, list)
                  and maximum in states
                  and all(isinstance(s, dict) and _finite(s.get('numeric_index'))
                          and s['numeric_index'] >= 0
                          and all(_finite(s.get(k)) for k in
                                  ('N_tension_positive_N', 'Mstrong_Nmm', 'Mweak_Nmm', 'x_mm'))
                          and s.get('side') in ('segment_start_right', 'segment_end_left', 'interior')
                          for s in states)
                  and _finite(maximum.get('numeric_index'))
                  and all(maximum['numeric_index'] >= s['numeric_index'] for s in states)
                  and all(_finite(maximum.get(k)) for k in
                          ('N_tension_positive_N', 'Mstrong_Nmm', 'Mweak_Nmm', 'x_mm'))
                  and maximum.get('side') in ('segment_start_right', 'segment_end_left', 'interior'))
    qualified = (match and concomitant and raw.get('status') == 'concomitant_arithmetic_only'
                 and raw.get('missing_capacity_keys') == [] and raw.get('member_issues') == []
                 and _text(raw.get('origin')))
    return check(key, limit_state='ELU', source=raw.get('origin'), qualified=qualified,
        index=maximum.get('numeric_index') if isinstance(maximum, dict) else None,
        reason='' if qualified else 'Interação N+M ausente, incompleta, fora do domínio ou não vinculada à mesma combinação/seção/região.',
        trace=dict(ids, concomitant_state=deepcopy(maximum),
                   analysis_8_1_qualified=raw.get('analysis_8_1_qualified') is True,
                   torsion_warping_shear_qualified=raw.get('torsion_warping_shear_qualified') is True,
                   missing_capacity_keys=deepcopy(raw.get('missing_capacity_keys'))))


def build_global_verification(result):
    """Read explicit criteria without changing the mechanical result.

    The current 7DOF schema yields a separate inventory. Legacy routes retain
    their own pending checks, after reference ELS and prescribed-P corrections.
    Historical exports never call this builder implicitly.
    """
    if not isinstance(result, dict):
        raise ValueError('Resultado deve ser um objeto.')
    if result.get('schema') == 'three_girt_current_vlasov_demand_v1':
        from .three_girt_assessment.application import assess
        return assess(result)
    records = []
    from .roof_top_nbr import preserved as saved_roof_nbr
    try:roof_component=saved_roof_nbr(result)
    except (ValueError,TypeError,KeyError) as exc:roof_component={'error':str(exc)}
    from .isolated_en_panorama import DEFAULT_TORSION_REASON
    torsion_reason=DEFAULT_TORSION_REASON
    from .isolated_en_application import global_context
    try:en_context=global_context(result,sectional=True)
    except (ValueError,TypeError,KeyError) as exc:
        en_context=None;torsion_reason='Registro EN isolado inválido; tensões não aproveitadas no panorama: '+str(exc)
    if en_context is not None:torsion_reason=en_context['reason']

    schema = result.get('schema')
    model_domain = result.get('model_domain_evidence', {})
    records.append(check('model_domain', limit_state='MODEL', source=SCHEMA,
        qualified=model_domain.get('status') == 'fixed_model_domain' and not model_domain.get('conflict'),
        verdict='meets', reason='Domínio de cálculo registrado, sem crédito da telha. Não certifica condições físicas.'))
    if schema == 'tercas_batch_results_v1':
        wanted = result.get('load_bundle', {}).get('combinations', [])
        cases = result.get('cases', [])
        by_id = {}
        for case in cases:
            c = case.get('combination', {})
            by_id.setdefault((c.get('id'), c.get('limit_state')), []).append(case)
        seen = set()
        for combo in wanted:
            key = (combo.get('id'), combo.get('limit_state'))
            if not _text(key[0]) or key[1] not in ('ELU', 'ELS') or key in seen:
                records.append(_pending('invalid_combination:'+str(len(records)), 'MODEL', 'Identidade de combinação ausente ou duplicada.'))
                continue
            seen.add(key)
            found = by_id.pop(key, [])
            if len(found) != 1:
                records.append(_pending(key[1]+':'+key[0]+':case_missing', key[1],
                    'Combinação solicitada ausente ou duplicada; não descartada do envelope.'))
                continue
            case = found[0]
            records.extend(_case_records(result, combo, case.get('evidence', {}), batch=True,
                                         warnings=case.get('warnings', []),case_combination=case.get('combination'),roof_component=roof_component,en_context=en_context))
        if not wanted or by_id:
            records.append(_pending('combination_inventory', 'MODEL', 'Inventário de combinações vazio ou resultados inesperados.'))
    elif schema == 'NBR14762_one_span_v1':
        for state in ('ELU', 'ELS'):
            records.extend(_case_records(result, {'id': 'DIRECT_'+state, 'limit_state': state},
                                         result, batch=False,roof_component=roof_component,en_context=en_context))
    elif schema == 'tercas_three_girt_results_v1':
        records.extend(_frame_records(result))
    else:
        records.append(_pending('unsupported_result_schema', 'MODEL', 'Resultado histórico/desconhecido não requalificado.'))
    present = {r['limit_state'] for r in records}
    for state in ('ELU', 'ELS'):
        if state not in present:
            records.append(_pending('missing_limit_state:'+state, state,
                'Nenhuma combinação '+state+' avaliada; filtro não é dispensa desse estado limite.'))
    from .isolated_en_panorama import POLICY, torsion_record
    from .isolated_ct_torsion import FIELD as CT_FIELD, POLICY as CT_POLICY, eligible as ct_eligible
    records.append(torsion_record(en_context,torsion_reason,ct_result=result,conflict=bool(model_domain.get('conflict')) or model_domain.get('status')!='fixed_model_domain'))
    from .nbr_family_panorama import apply as apply_family, BINDING as FAMILY_BINDING
    records,family_binding=apply_family(result,records)
    # The new family criteria replace only their authenticated own-contour
    # counterparts. The historical physical-span height result remains stored
    # and separately viewable, but is not a supporting source of this panorama.
    if family_binding is not None:roof_component=None
    from .isolated_service_panorama import apply as apply_service, BINDING as SERVICE_BINDING
    records,service_binding=apply_service(result,records)
    from .support_scope import apply_inventory as apply_support_scope
    records,support_scope=apply_support_scope(result,records)
    summary = aggregate([r['id'] for r in records], records, inventory_qualified=True)
    if support_scope is not None:summary['local_support_scope_exclusion']=support_scope
    summary.update(whole_member_approved=False, torsion_warping_qualified=False,
                   sectional_conditions_policy=POLICY, approved_within_declared_checklist=False,
                   current_adapter_can_approve=False, source_result_schema=schema,
                   source_input_fingerprint=result.get('input_fingerprint'),
                   combined_ELS_approved=False,
                   numerical_results_changed=False)
    if ct_eligible(result):summary[CT_FIELD]=CT_POLICY
    summary['display_summary']=display_summary(summary)
    if en_context is not None:summary['isolated_EN_binding']=en_context['binding']
    if family_binding is not None:summary[FAMILY_BINDING]=family_binding
    if service_binding is not None:summary[SERVICE_BINDING]=service_binding
    if roof_component is not None:
        summary['roof_top_nbr_binding']={k:roof_component.get(k) for k in ('snapshot_sha256','source_roof_snapshot_sha256')}
    excluded=[r['id'] for r in records if r['status']=='not_applicable'
              and r.get('trace',{}).get('criterion_scope')=='mathematical_limit']
    if excluded:
        from .point_limit import SCOPE as LIMIT_SCOPE
        summary['point_limit_exclusion_ids']=excluded
        summary['point_limit_scope_note']=LIMIT_SCOPE
    if roof_component is not None:
        from .roof_top_load import digest as roof_digest
        summary['roof_top_nbr_binding']['global_snapshot_sha256']=roof_digest(summary)
    return summary


def _frame_records(result):
    records = []
    cases = result.get('cases', [])
    if not cases:
        return [_pending('frame_cases', 'MODEL', 'Sistema de travessas sem casos resolvidos.')]
    bundle = result.get('load_bundle')
    wanted = bundle.get('combinations', []) if isinstance(bundle, dict) else []
    if not wanted and result.get('input_data', {}).get('load_mode') == 'direct':
        wanted = [{'id':'DIRETO_ELU', 'limit_state':'ELU'}, {'id':'DIRETO_ELS', 'limit_state':'ELS'}]
    expected_ids = [(c.get('id'), c.get('limit_state')) for c in wanted]
    ids = Counter((c.get('combination', {}).get('id'),
                   c.get('combination', {}).get('limit_state')) for c in cases)
    if not wanted or len(set(expected_ids)) != len(expected_ids):
        records.append(_pending('frame_combination_inventory', 'MODEL',
            'Inventário independente de combinações 3D ausente/duplicado.'))
    for cid, state in dict.fromkeys(expected_ids):
        if not _text(cid) or state not in ('ELU', 'ELS'):
            records.append(_pending('frame_invalid_expected:'+str(len(records)), 'MODEL',
                'Identidade esperada de combinação 3D inválida.'))
        elif ids[(cid, state)] != 1:
            records.append(_pending(state+':'+cid+':frame_case_missing_or_duplicate', state,
                'Combinação solicitada 3D ausente ou duplicada; não omitida do inventário.'))
    for cid, state in ids:
        if wanted and (cid, state) not in expected_ids:
            records.append(_pending('frame_unexpected:'+str(cid)+':'+str(state), 'MODEL',
                'Resultado 3D fora do inventário solicitado.'))
    for pos, case in enumerate(cases):
        combo = case.get('combination', {})
        cid, state = combo.get('id'), combo.get('limit_state')
        if not _text(cid) or state not in ('ELU', 'ELS') or ids[(cid, state)] != 1:
            records.append(_pending('frame_identity:'+str(pos), 'MODEL', 'Identidade de combinação inválida/duplicada.'))
            continue
        prefix = state+':'+cid+':'
        trace = {'combination_id': cid, 'limit_state': state, 'member_ids': ['upper', 'middle', 'lower']}
        records.append(_pending(prefix+'frame_analysis', state,
            'Diagnóstico 3D não qualifica automaticamente o domínio da análise resistente/ELS; manter vínculos, rigidezes e validade da resposta explícitos.', trace))
        if state == 'ELU':
            for name, text in [
                ('axial_bending', 'Interação N+M deve usar a mesma travessa, combinação, seção, lado e região de introdução. Capacidades compatíveis ainda não integradas; rota legada N=0 proibida.'),
                ('stability', 'Estabilidade do elemento/sistema não qualificada. Nó de tirante não reduz comprimento efetivo automaticamente.'),
                ('shear_interaction', 'Resistência ao cortante e interações do campo 3D ainda não qualificadas.')]:
                records.append(_pending(prefix+name, state, text, trace))
        else:
            records.append(_pending(prefix+'deflection', state,
                'Flecha bruta do diagnóstico não equivale a ELS com rigidez efetiva e referência/corda aplicáveis.', trace))
    return records


def display_summary(summary):
    """One concise banner, without resurrecting removed check-table rows."""
    nfail = summary['counts']['fails']
    npending = summary['counts']['pending']
    torsion = ', incluindo torção/empenamento' if 'torsion_warping' in summary['pending_ids'] else ''
    if summary['status'] == 'aprovado' and (summary.get('sectional_conditions_policy')
            or summary.get('current_adapter_can_approve') is False):
        return 'Critérios listados atendidos; conclusão global fora do escopo.'
    if summary['status'] == 'aprovado':
        return 'Aprovado no checklist completo do modelo declarado. Não certifica condições físicas nem itens fora do escopo.'
    if summary['status'] == 'reprovado':
        return (f'Reprovado nos critérios calculados: {nfail} não atendimento(s). '
                + (f'Avaliação global ainda incompleta: {npending} pendência(s){torsion}.'
                   if npending else ('Conclusão global fora do escopo.'
                       if summary.get('sectional_conditions_policy') else 'Checklist declarado concluído.')))
    return (f'Inconclusivo: {npending} pendência(s){torsion}. '
            'Os critérios calculados não constituem aprovação global.')


def attach_global_verification(result):
    """Convenience boundary for a caller that explicitly wants a copied result."""
    if result.get('schema') == 'three_girt_current_vlasov_demand_v1':
        raise ValueError('Use build_global_verification para o panorama separado do Vlasov; anexar altera a cadeia de hashes dos componentes.')
    out = deepcopy(result)
    out['global_verification'] = build_global_verification(result)
    out['whole_member_approved'] = False
    return out
