"""Saved, explicitly conditional point-displacement criteria in the panorama.

This adapter consumes authenticated ELS evidence. It never solves a member,
changes old displacement results, removes concrete model checks or approves global ELS.
Only a fresh builder calls apply; historical readers call validate_saved.
"""
import copy
import math
from .completion_requirements import digest
from .serviceability_plan import SOURCE_SHA256

POLICY='isolated_service_point_linear_panorama_v1'
BINDING='isolated_service_binding'
SUFFIX='combined_point_linear'
ANNOTATION='isolated_service_linear_comparison'
COVERAGE_SCOPE=('Cobertura do cálculo do deslocamento declarado: disponibilidade do campo, rigidez, ponto, direção, corda e critério. '
                'Cobertura não significa atendimento do índice nem aprovação física/global.')
COVERAGE_SOURCE='NBR14762:2010 §8.1, §9.8.5(a), Anexo A A.2.4/A.3.3; cobertura do cálculo declarado'
SCOPE=('Critério do deslocamento projetado no ponto e na direção declarados, relativo à corda dos extremos físicos do mesmo ponto, '
       'no campo linear concomitante salvo. Não é aprovação do ELS físico integral, estabilidade ou validade de giro finito.')
SYSTEM_SCOPE=dict(
    calculated_portion='Deslocamento total da combinação selecionada, sem dedução de contraflecha, relativo à corda do mesmo ponto.',
    construction_stages='Não afirma cobrir automaticamente todas as parcelas/etapas pertinentes de A.2.4/A.3.3.',
    ponding=dict(requirement='NBR14762:2010 Tabela A.1 nota g: evitar empoçamento.',
        status='outside_point_displacement_calculation',
        service_combination='NBR14762 A.2.4: combinação frequente quando deslocamentos causam empoçamento; não substituída pelo par e/f.',
        reason='O campo do ponto não avalia a superfície deformada da cobertura, drenagem ou caminho de escoamento. Exigência do sistema no inventário separado, sem reprovação nem dispensa inferida.'))
FALSE_FLAGS=('whole_member_approved','combined_ELS_approved','approved_within_declared_checklist','current_adapter_can_approve','physical_conditions_verified')


def _number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def _case_ids(result):
    if result.get('schema')=='NBR14762_one_span_v1':return {'DIRECT_ELS'}
    wanted=[r.get('id') for r in result.get('load_bundle',{}).get('combinations',[]) if r.get('limit_state')=='ELS']
    actual=[r.get('combination',{}).get('id') for r in result.get('cases',[]) if r.get('combination',{}).get('limit_state')=='ELS']
    return {cid for cid in wanted if wanted.count(cid)==actual.count(cid)==1}


def _coverage(packet,cid,row,identity,source_hash,conflict,*,outside_pair=False,combination=None):
    from .isolated_service_component import missing_configuration
    cfg=packet['configuration'];missing=missing_configuration(cfg)
    missing.extend(packet['missing'])
    if conflict:missing.append('Domínio do modelo ausente ou incompatível.')
    if row is None and not outside_pair:
        missing.append('Nenhum campo combinado desta combinação consta do inventário do critério selecionado.')
    elif row is not None and row['status']!='computed_linear_comparison':
        missing.append(row.get('reason') or 'Campo combinado desta combinação ainda não calculado.')
    elif row is not None and row['comparison']['gross_screen']['gross_local_normal_sufficient'] is not True:
        missing.append('Crivo suficiente MLE inconclusivo; rigidez efetiva combinada ainda não qualificada por este método.')
    missing=list(dict.fromkeys(missing))
    calc=row.get('comparison') if row else None
    coverage_status='pending' if missing else 'not_applicable' if outside_pair else 'meets'
    return dict(criterion_id=None if outside_pair else identity,source_packet_sha256=source_hash,
        source_record_sha256=digest(row) if row else None,
        criterion_status_in_linear_model=calc['criterion_status'] if calc else None,
        coverage_status=coverage_status,missing=missing,
        source_combination=copy.deepcopy(combination),criterion_selection=cfg['criterion'],
        outside_selected_A1_pair_only=outside_pair,general_ELS_exemption=False,system_scope=copy.deepcopy(SYSTEM_SCOPE),
        calculation_portion='total_selected_combination_without_camber_relative_to_same_point_end_chord',
        physical_first_order_flag_is_coverage_gate=False,
        stored_linear_twist_max_rad=calc.get('stored_linear_twist_max_rad') if calc else None,
        rotation_screening_warning=calc.get('rotation_screening_warning') if calc else None,
        rotation_warning_is_normative_limit=False,
        reason=('Cobertura do cálculo pendente: '+'; '.join(missing) if missing else
                'Combinação fora somente do par selecionado da Tabela A.1 notas e/f; não é dispensa geral de ELS. A sucção característica possui caso separado.' if outside_pair else
                'Cálculo combinado completo para o ponto, direção, corda, parcela total sem contraflecha e critério declarados. '
                'A comparação numérica está em '+identity+' e pode atender, exceder ou permanecer inconclusiva. '
                'Não depende de certificação física adicional; não constitui aprovação física/global.'))


def _default_method_replacement(result,packet,row,coverage,source_hash):
    """Retire only an unavailable automatic route with NO effective criterion.

    A pending MSE/Ml computation is not a separate code requirement where the
    caller selected a complete MLE point criterion. No field equivalence or
    dominance is inferred: torsion can cancel the flexural component.
    """
    if result.get('schema')!='NBR14762_one_span_v1' or coverage['coverage_status']!='meets':return None
    data=result.get('input_data',{});spec=result.get('input_snapshot');raw=result.get('ELS')
    if 'deflection_model' in data or not isinstance(spec,dict) or not isinstance(raw,dict):return None
    # Absence in root inputs alone is insufficient: an adapter may inject an
    # effective per-case limit (e.g. batch L/denominator or own-reference L/180).
    effective=spec.get('ELS_limit_mm')
    if (data.get('load_mode')!='direct' or 'ELS_limit_mm' not in data
        or data['ELS_limit_mm'] is not None or not isinstance(data.get('ELS_origin'),str)
        or data['ELS_origin'].strip() or not isinstance(effective,dict)
        or set(effective)!={'value','origin'} or effective['value'] is not None
        or not isinstance(effective['origin'],str) or effective['origin'].strip()):return None
    if (raw.get('status')!='not_evaluated' or raw.get('missing')!=['Ml with origin']
        or raw.get('index') is not None or raw.get('deflection_mm') is not None
        or raw.get('criterion_status') not in (None,'not_evaluated')):return None
    return dict(criterion_id=coverage['criterion_id'],source_packet_sha256=source_hash,
        source_record_sha256=digest(row),source_legacy_ELS_sha256=digest(raw),
        source_effective_input_snapshot_sha256=digest(spec),effective_legacy_limit=copy.deepcopy(effective),
        root_legacy_limit=None,root_legacy_limit_origin=data['ELS_origin'],
        replacement_kind='automatic_unavailable_method_replaced_by_explicit_point_objective',
        physical_equivalence_or_dominance_claimed=False,old_MSE_or_Ml_calculated=False,
        general_service_stiffness_exemption=False,independent_legacy_criterion_present=False,
        reason='Somente a rota MSE automática indisponível e sem critério próprio foi substituída pelo objetivo de deslocamento no ponto explicitamente escolhido. '
               'A rigidez desse objetivo está coberta pelo crivo MLE completo da fonte combinada. '
               'Não afirma equivalência com a flecha flexional, não usa cancelamento para provar essa componente e não afirma MSE/Ml antigos calculados.')


def _project(result):
    from .isolated_service_component import FIELD,saved
    if result.get(FIELD) is None:return [],None,{}
    packet=saved(result)
    if packet is None:raise ValueError('Componente ELS declarada sem fonte autenticada.')
    from .global_verification import check
    domain=result.get('model_domain_evidence',{})
    conflict=domain.get('status')!='fixed_model_domain' or bool(domain.get('conflict'))
    cfg=packet['configuration'];source_hash=digest(packet);existing=_case_ids(result)
    records=[];annotations={}
    for row,item in zip(packet['records'],packet['inventory']):
        cid=row['id'];identity='ELS:'+cid+':'+SUFFIX
        trace=dict(policy=POLICY,combination_id=cid,limit_state='ELS',criterion_scope=SCOPE,
            source_packet_sha256=source_hash,source_record_sha256=digest(row),
            source_configuration=copy.deepcopy(cfg),source_combination=copy.deepcopy(item.get('source_combination')),
            source_case_kind=item['kind'],source_dense_sha256=row.get('source_dense_sha256'),
            source_summary_sha256=row.get('source_summary_sha256'),
            supplementary_summary_sha256=digest(row.get('supplementary_summary')),
            source_input_fingerprint=packet['source_input_fingerprint'],
            source_torsion_snapshot_sha256=packet['source_torsion_snapshot_sha256'],
            physical_ELS_approval=False,model_domain_conflict=conflict,system_scope=copy.deepcopy(SYSTEM_SCOPE))
        kwargs=dict(index=None,qualified=False)
        if row['status']=='not_applicable':
            reason='Somente este caso suplementar dispensado: sucção característica explicitamente nula; não dispensa os demais critérios de serviço.'
            kwargs.update(qualified=not conflict,not_applicable=True)
        elif row['status']=='pending':
            reason='Comparação linear ainda pendente: '+(row.get('reason') or '; '.join(packet['missing']) or 'Campo/dados aplicáveis indisponíveis.')
        elif row['status']=='computed_linear_comparison':
            calc=row['comparison'];lo=calc['index_lower'];hi=calc['index_upper']
            trace.update(index_lower=lo,index_upper=hi,limit_mm=calc['limit_mm'],
                displacement_lower_mm=calc['envelope']['abs_displacement_lower_mm'],
                displacement_upper_mm=calc['envelope']['abs_displacement_upper_mm'],
                criterion_status_in_linear_model=calc['criterion_status'],
                stored_linear_twist_max_rad=calc.get('stored_linear_twist_max_rad'),
                rotation_screening_warning=calc.get('rotation_screening_warning'),
                rotation_warning_is_normative_limit=False,
                gross_MLE_sufficient=calc['gross_screen']['gross_local_normal_sufficient'])
            if lo is None and hi is None:
                reason='Campo combinado e envelope calculados; condição suficiente MLE da rigidez bruta inconclusiva. Sem índice de aceitação e sem conclusão de falha.'
            elif not (_number(lo) and _number(hi) and lo<=hi):
                raise ValueError('Intervalo do índice ELS inválido.')
            elif calc['gross_screen']['gross_local_normal_sufficient'] is not True:
                raise ValueError('Índice ELS não pode contornar o crivo da rigidez.')
            elif hi<=1:
                kwargs.update(index=hi,qualified=not conflict)
                trace['selected_index_bound']='upper'
                reason='Atende condicionalmente ao critério linear declarado: limite superior do índice ≤1. '+SCOPE
            elif lo>1:
                kwargs.update(index=lo,qualified=not conflict)
                trace['selected_index_bound']='lower'
                reason='Excede condicionalmente o critério linear declarado: limite inferior do índice >1. Não é prova de ruína nem da aplicabilidade física. '+SCOPE
            else:
                kwargs['index']=hi
                trace['selected_index_bound']='diagnostic_upper_only'
                reason='Intervalo do índice atravessa 1: comparação linear inconclusiva. Limite superior >1, isoladamente, não prova excesso.'
        else:raise ValueError('Estado de componente ELS desconhecido.')
        if conflict:reason+=' Domínio do modelo ausente ou incompatível; critério não qualificado no panorama.'
        source=('NBR14762:2010 §9.8.5(a), Anexo A, Tabela A.1 notas e/f; critério linear selecionado'
                if cfg['criterion']=='nbr_A1_pair' else 'NBR14762:2010 §9.8.5(a); limite de deslocamento declarado para o campo linear')
        records.append(check(identity,limit_state='ELS',source=source,reason=reason,trace=trace,**kwargs))
    if not records:
        records.append(check('ELS:SERVICE_SELECTION:'+SUFFIX,limit_state='ELS',source=POLICY,
            reason='Seleção de serviço sem inventário de comparações; nenhuma aprovação por lista vazia.',
            trace=dict(policy=POLICY,criterion_scope=SCOPE,source_packet_sha256=source_hash,missing=copy.deepcopy(packet['missing']))))
    by_id={r['id']:r for r in packet['records'] if r['kind']=='existing'}
    source_cases={r['id']:r for r in result.get('load_bundle',{}).get('combinations',[]) if r.get('limit_state')=='ELS'}
    source_cases.update({r['id']:r.get('source_combination') for r in packet['inventory'] if r['kind']=='existing'})
    for cid in sorted(existing):
        identity='ELS:'+cid+':'+SUFFIX
        outside_pair=(cfg['criterion']=='nbr_A1_pair' and result.get('schema')=='tercas_batch_results_v1' and cid not in by_id)
        coverage=_coverage(packet,cid,by_id.get(cid),identity,source_hash,conflict,
            outside_pair=outside_pair,combination=source_cases.get(cid))
        annotations['ELS:'+cid+':combined_ELS_scope']=coverage
        replacement=_default_method_replacement(result,packet,by_id.get(cid),coverage,source_hash)
        if replacement is not None:annotations['ELS:'+cid+':deflection']=replacement
    binding=dict(policy=POLICY,source_packet_sha256=source_hash,
        source_input_fingerprint=packet['source_input_fingerprint'],
        source_torsion_snapshot_sha256=packet['source_torsion_snapshot_sha256'],
        source_model_domain_sha256=digest(domain),normative_source_sha256=SOURCE_SHA256,
        criterion_scope=SCOPE,calculation_coverage_scope=COVERAGE_SCOPE,system_scope=copy.deepcopy(SYSTEM_SCOPE),record_ids=[r['id'] for r in records],
        annotated_scope_ids=list(annotations),whole_member_approved=False,combined_ELS_approved=False)
    return records,binding,annotations


def _owned(row):
    key=row.get('id','')
    return key.endswith(':'+SUFFIX) or row.get('trace',{}).get('policy')==POLICY


def _annotate(row,annotation):
    if row.get('status')!='pending' or row.get('index') is not None:
        raise ValueError('Cobertura deve substituir somente o marcador genérico de cálculo pendente.')
    from .global_verification import check
    if annotation.get('replacement_kind')=='automatic_unavailable_method_replaced_by_explicit_point_objective':
        return check(row['id'],limit_state='ELS',source='NBR14762 §9.8.5(a): rigidez MLE do objetivo de serviço escolhido; substituição de rota automática',
            qualified=True,not_applicable=True,reason=annotation['reason'],
            trace={ANNOTATION:copy.deepcopy(annotation),'combination_id':row['id'][4:-len(':deflection')],
                'criterion_scope':'automatic_legacy_method_only_not_general_service_requirement',
                'physical_ELS_approval':False})
    return check(row['id'],limit_state='ELS',source=COVERAGE_SOURCE,
        qualified=annotation['coverage_status'] in ('meets','not_applicable'),
        not_applicable=annotation['coverage_status']=='not_applicable',
        verdict='meets' if annotation['coverage_status']=='meets' else None,
        reason=annotation['reason'],trace={ANNOTATION:copy.deepcopy(annotation),
            'combination_id':row['id'][4:-len(':combined_ELS_scope')],
            'criterion_scope':COVERAGE_SCOPE,'coverage_is_numerical_acceptance':False,
            'physical_ELS_approval':False})


def apply(result,records):
    additions,binding,annotations=_project(result)
    if binding is None:return records,None
    if any(_owned(r) for r in records):raise ValueError('Panorama ELS linear já aplicado; não duplicar critérios.')
    out=copy.deepcopy(records)
    for identity,annotation in annotations.items():
        positions=[i for i,r in enumerate(out) if r.get('id')==identity]
        if len(positions)!=1:raise ValueError('Marcador de cobertura ELS ausente/duplicado: '+identity)
        i=positions[0];out[i]=_annotate(out[i],annotation)
    return out+additions,binding


def validate_saved(result):
    """Authenticate only an explicitly bound new panorama; no historical upgrade."""
    summary=result.get('global_verification',{})
    if BINDING not in summary:
        if any(_owned(r) or ANNOTATION in r.get('trace',{}) for r in summary.get('checks',[])):
            raise ValueError('Critérios ELS novos sem vínculo explícito; não são histórico legado.')
        return
    expected,binding,annotations=_project(result)
    if binding is None or summary[BINDING]!=binding:
        raise ValueError('Panorama ELS linear não corresponde à componente autenticada.')
    if any(summary.get(k) is not False for k in FALSE_FLAGS) or result.get('whole_member_approved') is not False:
        raise ValueError('Comparação linear não pode aprovar ELS físico/global.')
    actual=[r for r in summary.get('checks',[]) if _owned(r)]
    if actual!=expected:raise ValueError('Critérios ELS lineares ausentes, duplicados ou alterados.')
    annotated=[r.get('id') for r in summary['checks'] if ANNOTATION in r.get('trace',{})]
    if sorted(annotated)!=sorted(annotations):
        raise ValueError('Anotação ELS órfã, ausente ou duplicada.')
    from .global_verification import aggregate, display_summary
    projected=aggregate([r['id'] for r in summary['checks']],summary['checks'],inventory_qualified=True)
    for key in ('status','complete','counts','failed_ids','pending_ids','maximum_available_check',
                'maximum_is_global_utilization','by_limit_state','listed_checks_only',
                'listed_checks_only_is_complete_limit_state_approval'):
        if summary.get(key)!=projected[key]:raise ValueError('Resumo global divergente dos critérios salvos: '+key)
    if summary.get('display_summary')!=display_summary(summary):
        raise ValueError('Texto do panorama divergente dos critérios salvos.')
    for identity,annotation in annotations.items():
        rows=[r for r in summary['checks'] if r.get('id')==identity]
        shell=dict(id=identity,status='pending',index=None)
        if len(rows)!=1 or rows[0]!=_annotate(shell,annotation):
            raise ValueError('Cobertura do cálculo ELS ausente, alterada ou fora do alcance declarado.')
