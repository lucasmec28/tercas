"""Explicit, source-bound sidecar for local web checks at support reactions.

This component never modifies loads or runs the member solver. Opening a saved
assessment does not call the bearing formula or reconstruct missing reactions.
"""
import copy
import hashlib
import json
import math
from . import mechanics, sources

SCHEMA='NBR14762_support_web_assessment_v1'
CONFIG_SCHEMA='NBR14762_support_web_choice_v1'
FALSE_FLAGS=('whole_member_approved','connection_design_checked','physical_conditions_verified',
             'global_stability_qualified','complete_load_introduction_qualified')
LIMITS=[
    'Componente local NBR14762:2010 §9.5.1 e Anexo D nas reações de apoio declaradas, inclusive sem P externa.',
    'Ligação da alma a outra viga ou pilar registra a exceção de enrijecedor §9.5.1; não dimensiona nem aprova ligação ou solda.',
    'Contato na mesa verifica somente a parcela normal compressiva da reação e a geometria tabulada. Forças paralelas, torção, M–V, estabilidade e outras introduções locais permanecem separadas.',
    'Não se mistura interação M+F de outra norma com FRd NBR. Momento nulo no nó ideal não comprova momento nulo em toda a região finita de contato.',
    'Hashes vinculam o conteúdo salvo, não comprovam levantamento físico nem autenticidade de um arquivo deliberadamente reescrito.',
]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def source_fingerprint(result):
    return fingerprint(result)


def blank_detail():
    return dict(route=None,origin='',c_mm=None,end_distance_mm=None,no_opposite_force=None,
                opposite_clear_distance_mm=None,connected=None,normal_compressive_sign=None,
                loaded_flange_orientation='')


def reference_configuration(result, extracted=None):
    src=sources.extract(result) if extracted is None else extracted
    details={row['support_id']:blank_detail() for row in src['supports']}
    for sid,detail in src.get('legacy_details',{}).items():
        if sid in details:
            details[sid].update({k:copy.deepcopy(detail[k]) for k in ('route','origin')})
    return dict(schema=CONFIG_SCHEMA,source_fingerprint=source_fingerprint(result),details=details)


def _configuration(result, config, src):
    if (not isinstance(config,dict) or set(config)!={'schema','source_fingerprint','details'}
            or config.get('schema')!=CONFIG_SCHEMA
            or config.get('source_fingerprint')!=source_fingerprint(result)
            or not isinstance(config.get('details'),dict)
            or set(config['details'])!={row['support_id'] for row in src['supports']}):
        raise ValueError('Detalhes dos apoios não vinculados exatamente ao resultado atual.')
    for sid,d in config['details'].items():
        if not isinstance(d,dict) or set(d)!=set(blank_detail()):
            raise ValueError('Estrutura dos detalhes de apoio desconhecida: '+sid)
    return copy.deepcopy(config)


def calculate(result, config):
    """Evaluate only the local component after source adapter validation."""
    from ..support_scope import saved as saved_scope
    if saved_scope(result) is not None:
        raise ValueError('Verificação local dos apoios fora do escopo por decisão do usuário; nenhum índice calculado.')
    src=sources.extract(result)
    cfg=_configuration(result,config,src)
    if not src['supports']:
        raise ValueError('Não há registros ELU de apoio disponíveis para esta fonte.')
    rows=[]
    for record in src['supports']:
        if record.get('limit_state')!='ELU':
            raise ValueError('Adaptador deve fornecer somente reações ELU, sem misturar ELS.')
        detail=cfg['details'][record['support_id']]
        local=mechanics.evaluate_reaction(src['section'],record,detail)
        rows.append(dict(source_record=copy.deepcopy(record),detail=copy.deepcopy(detail),local=local))
    out=dict(schema=SCHEMA,source_fingerprint=source_fingerprint(result),
             source_schema=result.get('schema'),source_input_fingerprint=result.get('input_fingerprint'),
             configuration=cfg,section=copy.deepcopy(src['section']),
             source_scope=src.get('scope'),legacy_detail_evidence=copy.deepcopy(src.get('legacy_details',{})),source_metadata={k:copy.deepcopy(v) for k,v in src.items()
                 if k not in ('supports','legacy_details','section')},rows=rows,limits=copy.deepcopy(LIMITS),
             **{key:False for key in FALSE_FLAGS})
    out['summary']=summary(rows)
    out['content_sha256']=fingerprint(out)
    return out


def summary(rows):
    counts={k:0 for k in ('meets','fails','exempt','not_applicable','pending')}
    for row in rows:
        local=row['local'];status=local.get('status')
        if status=='computed':
            value=local.get('index')
            key=('meets' if value<=1 else 'fails') if type(value) in (int,float) and math.isfinite(value) else 'pending'
        elif status in ('exempt','stiffener_exception_9_5_1'):key='exempt'
        elif status=='not_applicable':key='not_applicable'
        else:key='pending'
        counts[key]+=1
    return dict(counts,records=len(rows),all_local_records_decided=counts['pending']==0,
                all_decided_local_checks_satisfied=counts['pending']==0 and counts['fails']==0,
                whole_member_approved=False)


def saved_assessment(result, assessment):
    """Read saved output only: no source extraction, bearing or member solver."""
    if not isinstance(assessment,dict) or assessment.get('schema')!=SCHEMA:
        raise ValueError('Registro local de apoios desconhecido.')
    expected=assessment.get('content_sha256')
    payload={k:v for k,v in assessment.items() if k!='content_sha256'}
    if expected!=fingerprint(payload) or assessment.get('source_fingerprint')!=source_fingerprint(result):
        raise ValueError('Registro de apoios alterado ou pertencente a outra demanda; não recalculado.')
    if any(assessment.get(k) is not False for k in FALSE_FLAGS):
        raise ValueError('Registro local não pode aprovar ligação, condições físicas ou barra inteira.')
    cfg=assessment.get('configuration');rows=assessment.get('rows')
    if (not isinstance(cfg,dict) or cfg.get('schema')!=CONFIG_SCHEMA
            or cfg.get('source_fingerprint')!=assessment['source_fingerprint']
            or not isinstance(cfg.get('details'),dict) or not isinstance(rows,list) or not rows):
        raise ValueError('Contrato salvo de apoios incompleto.')
    identities=set()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Linha local de apoio inválida.')
        record=row.get('source_record');local=row.get('local');detail=row.get('detail')
        if not isinstance(record,dict) or not isinstance(local,dict):raise ValueError('Evidência local incompleta.')
        sid=record.get('support_id');cid=record.get('combination_id')
        if not isinstance(sid,str) or not isinstance(cid,str) or (sid,cid) in identities:
            raise ValueError('Identidade de apoio/combinação inválida ou duplicada.')
        identities.add((sid,cid))
        if record.get('limit_state')!='ELU' or detail!=cfg['details'].get(sid):
            raise ValueError('Detalhe de apoio desvinculado da combinação salva.')
        actions=local.get('reaction')
        if (not isinstance(actions,dict) or any(actions.get(k)!=record.get(k) for k in ('normal_N','parallel_N','moment_strong_Nmm'))
                or any(local.get(k) is not False for k in ('whole_member_approved','connection_design_checked','physical_conditions_verified'))):
            raise ValueError('Ações ou alcance da verificação local salvos são incoerentes.')
        if local.get('status') not in ('computed','exempt','not_applicable','not_evaluated'):
            raise ValueError('Estado local salvo desconhecido.')
        if local.get('status')=='exempt' and (detail.get('route')!='web_connection'
                or not isinstance(detail.get('origin'),str) or not detail['origin'].strip()
                or local.get('origin')!=detail['origin'] or local.get('route')!='web_connection'):
            raise ValueError('Exceção de apoio não vinculada à declaração de alma.')
        if local.get('status')=='not_applicable' and record.get('normal_N')!=0:
            raise ValueError('Reação não nula não pode dispensar o critério local por força zero.')
        if local.get('status')!='computed' and any(k in local for k in ('FRd_N','index')):
            raise ValueError('Estado não calculado não pode apresentar resistência ou índice.')
        if local.get('status')=='computed':
            cap=local.get('FRd_N');force=local.get('force_N');index=local.get('index')
            sign=detail.get('normal_compressive_sign');normal=record.get('normal_N')
            if (detail.get('route')!='flange_contact' or type(sign) not in (int,float) or sign not in (-1,1)
                    or type(normal) not in (int,float) or not math.isfinite(normal) or normal*sign<=0
                    or force!=abs(normal) or local.get('route')!=detail['route']
                    or local.get('origin')!=detail.get('origin')):
                raise ValueError('Força, sentido ou detalhe desvinculado da resistência salva.')
            domain=local.get('domain');section=assessment.get('section',{})
            if not isinstance(domain,dict):raise ValueError('Domínio salvo da resistência ausente.')
            expected={'H_external_mm':section.get('H'),'t_mm':section.get('t'),'ri_mm':section.get('ri'),
                      'fy_MPa':section.get('fy'),'family':section.get('family'),'c_mm':detail.get('c_mm'),
                      'end_distance_mm':detail.get('end_distance_mm'),'opposite_clear_distance_mm':detail.get('opposite_clear_distance_mm'),
                      'no_opposite_force':detail.get('no_opposite_force'),'connected':detail.get('connected'),
                      'normal_compressive_sign':sign,'theta_degrees':90,'gamma':1.35}
            if any(domain.get(k)!=v for k,v in expected.items()):
                raise ValueError('Geometria/material do contato salvos são incoerentes.')
            if not all(type(v) in (int,float) and math.isfinite(v) for v in (cap,force,index)) or min(cap,force)<=0 or index!=force/cap:
                raise ValueError('Aritmética salva da resistência local incoerente.')
            if local.get('criterion_status')!=('meets' if index<=1 else 'fails'):
                raise ValueError('Decisão salva da resistência local incoerente.')
    schema=result.get('schema')
    if schema=='NBR14762_one_span_v1':
        required={('left','DIRECT_ELU'),('right','DIRECT_ELU')}
    elif schema=='tercas_batch_results_v1':
        required={(sid,c['combination']['id']) for c in result['cases']
                  if c['combination']['limit_state']=='ELU' for sid in ('left','right')}
    elif isinstance(result.get('cases'),list) and result.get('status')=='conditional_elastic_vlasov_demand':
        from ..three_girt_scope import members
        required={(level+'_'+side,c['combination']['id']) for c in result['cases']
                  if c['combination']['limit_state']=='ELU' for level in members(result) for side in ('left','right')}
    else:required=None
    if required is not None and identities!=required:
        raise ValueError('Cobertura de apoios/combinações salva não corresponde à fonte.')
    if set(cfg['details'])!={sid for sid,_ in identities}:
        raise ValueError('Detalhes salvos não cobrem exatamente os apoios.')
    if assessment.get('summary')!=summary(rows):
        raise ValueError('Resumo salvo de apoios incoerente.')
    return copy.deepcopy(assessment)
