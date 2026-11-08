"""Current-family criteria replace obsolete legacy denominators in NEW reports.

No history migration, index mixing or whole-member approval. The complete
family packet is authenticated before any record can enter the panorama.
"""
import copy
from .ue_catalog_reference import digest

POLICY='NBR_complete_family_member_conditions_v1'
BINDING='NBR_family_binding'


def _build(result):
    from .nbr_ue_family_application import FIELD, preserved, _not_applicable_basis
    raw=result.get(FIELD)
    if not isinstance(raw,dict) or raw.get('schema') not in ('nbr_ue_family_application_v2','nbr_ue_family_application_v3_rp23_candidate','nbr_ue_family_application_v4_energy_product','nbr_ue_family_application_v5_current_reference'):
        return [],None
    packet=preserved(result)
    rows=packet['records']
    if not rows or not all('member_interaction' in r for r in rows):
        return [],None
    from .global_verification import check
    domain=result.get('model_domain_evidence',{})
    conflict=domain.get('status')!='fixed_model_domain' or bool(domain.get('conflict'))
    records=[]
    for row in rows:
        interaction=row['member_interaction'];active=interaction['arithmetic']['active_signed_branches']
        prefix='ELU:'+row['combination_id']+':'
        components={p['method']:p for p in row['components'] if p['route']=='own_rounded_contour'}
        trace=dict(policy=POLICY,combination_id=row['combination_id'],
            source_binding=copy.deepcopy(interaction['source_binding']),
            material=copy.deepcopy(interaction['material']),
            nominal_Pierin_resistance_mixed=False,old_denominators_recomputed=False,
            criterion_scope='NBR pure-axis reference components in declared isolated N=0 analysis')
        for mode,clause in (('local','9.8.2.1'),('distortional','9.8.2.3'),('FLT','9.8.2.2')):
            selected={};missing=[];exempt=[]
            if mode=='FLT':missing.extend(interaction['zero_moment_rotation_guard']['missing'])
            for name,needed in active.items():
                if not needed:continue
                if mode in ('FLT','distortional'):
                    choices=[p['method'] for p in interaction['selection'][name]['selected'] if mode in p['method']]
                    method=choices[0] if choices else (None if mode=='FLT' else 'distortional' if name.startswith('Mx') else 'weak_'+('positive' if name.endswith('_positive') else 'negative')+'_distortional')
                else:method=mode if name.startswith('Mx') else 'weak_'+('positive' if name.endswith('_positive') else 'negative')+'_'+mode
                p=components.get(method) if method else None
                if p is not None and p.get('index') is not None:
                    selected[method]=p
                    if p.get('capacity_lower_bound_only') and p['index']>1:
                        missing.append(name+':'+mode+':resistance_floor_insufficient_not_failed')
                elif p is not None and mode=='distortional' and _not_applicable_basis(p,packet['sources']) is not None:
                    exempt.append(dict(method=method,basis=_not_applicable_basis(p,packet['sources'])))
                else:missing.append(name+':'+mode)
            index=max((p['index'] for p in selected.values()),default=None)
            records.append(check(prefix+('FLT:family' if mode=='FLT' else mode),limit_state='ELU',
                source='NBR14762:2010 '+clause,qualified=not missing and not conflict,
                not_applicable=not missing and not selected and not conflict,
                index=index,reason=('Componentes atuais da mesma seção; '+('; '.join(missing) if missing else
                    'critérios de eixo/sinal ativos, incluindo aproximações identificadas na fonte.')),
                trace=dict(trace,components=copy.deepcopy(list(selected.values())),
                    exemptions=exempt,missing=missing,model_domain_conflict=conflict)))
        records.append(check(prefix+'FLT_coverage',limit_state='ELU',source=POLICY,
            qualified=not conflict,verdict='meets',reason='Inventário atual de eixos/sinais e comprimentos resistentes; solicitações mantêm o vão físico integral. Não cria apoio intermediário.',
            trace=dict(trace,resistance_lengths=copy.deepcopy(packet['resistance_lengths']),physical_span_mm=packet['physical_span_mm'])))
        arithmetic=interaction['arithmetic'];governing=arithmetic['governing']
        records.append(check(prefix+'biaxial',limit_state='ELU',source=interaction['source'],
            qualified=not conflict and interaction['status']=='component_computed' and arithmetic['criterion_status'] in ('meets','fails'),
            index=governing['index_upper'] if governing else None,
            reason=('Piso resistente insuficiente para provar atendimento; o índice superior não prova reprovação.'
                if interaction['status']=='inconclusive_resistance_floor' else
                'NBR9.9 N=0, esforços concomitantes e mínimo local/FLT/D de cada sinal; torção/cortantes e ELS permanecem separados.'
                if not interaction['missing'] else '; '.join(interaction['missing'])),
            trace=dict(trace,concomitant_state=copy.deepcopy(governing),selection=copy.deepcopy(interaction['selection']),
                approximate_elastic_references=interaction['approximate_elastic_references'])))
        mv=row.get('strong_web_MV')
        if mv is not None:
            shear=mv['web_shear'];arith=mv['arithmetic']
            records.append(check(prefix+'shear',limit_state='ELU',source=mv['NBR_web_capacity']['source'],
                index=shear['index_upper'],qualified=not conflict and shear['criterion_status'] in ('meets','fails'),
                verdict=shear['criterion_status'] if shear['criterion_status'] in ('meets','fails') else None,
                reason='Cortante forte da alma, propriedades próprias e NBR9.8.3; não verifica cortante fraco nem torção.',
                trace=dict(trace,web_shear=copy.deepcopy(shear),web_capacity=copy.deepcopy(mv['NBR_web_capacity']))))
            records.append(check(prefix+'MV',limit_state='ELU',source=mv['source'],
                index=arith['index_squared_upper'] if arith is not None else None,
                qualified=not conflict and mv['criterion_status'] in ('meets','fails'),
                verdict=mv['criterion_status'] if mv['criterion_status'] in ('meets','fails') else None,
                reason='NBR9.8.4: M forte e V da alma concomitantes, MRd local9.8.2.1 da mesma fonte. '+
                    ('; '.join(mv['missing']) if mv['missing'] else mv['scope']),
                trace=dict(trace,strong_web_MV=copy.deepcopy(mv))))
    binding=dict(policy=POLICY,source_packet_sha256=digest(packet),
        record_ids=[r['id'] for r in records],whole_member_approved=False)
    return records,binding


def _replaced(key, prefixes):
    return any(key in (p+'local',p+'distortional',p+'biaxial') or key.startswith(p+'FLT') for p in prefixes)


def apply(result, records):
    additions,binding=_build(result)
    if binding is None:return records,None
    prefixes={r['id'].rsplit(':',1)[0]+':' for r in additions if r['id'].endswith(':local')}
    addition_ids={r['id'] for r in additions}
    out=[r for r in records if not _replaced(r['id'],prefixes) and r['id'] not in addition_ids]
    return out+additions,binding


def validate_saved(result):
    expected,binding=_build(result)
    summary=result.get('global_verification',{})
    if summary.get(BINDING)!=binding:
        raise ValueError('Panorama NBR e componentes da família pertencem a fontes diferentes.')
    if binding is None:return
    prefixes={r['id'].rsplit(':',1)[0]+':' for r in expected if r['id'].endswith(':local')}
    expected_ids={r['id'] for r in expected}
    actual=[r for r in summary.get('checks',[]) if _replaced(r.get('id',''),prefixes) or r.get('id') in expected_ids]
    if actual!=expected:
        raise ValueError('Critérios atuais NBR da família ausentes, alterados ou misturados ao legado.')
