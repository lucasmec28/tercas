"""Separate saved normal-force criterion, never a closure of point introduction."""
import copy
import math
from . import sources
from ..support_web import mechanics
from ..support_web.application import fingerprint, summary

SCHEMA='NBR14762_point_web_assessment_v1'
CONFIG_SCHEMA='NBR14762_point_web_choice_v1'
FLAGS=('whole_member_approved','connection_design_checked','physical_conditions_verified',
       'global_approval','complete_load_introduction_qualified','support_reactions_checked',
       'parallel_introduction_checked')
SCOPE=('Somente resistência local da alma à componente normal compressiva de P, NBR14762 §9.5.1/Anexo D. '
       'Ações paralelas e momento concomitantes são registrados, não aprovados por F/FRd. '
       'Não verifica ligação, força fora do plano, torção, M–V, estabilidade ou reação de apoio. '
       'Não substitui point_introduction_scope nem aprova introdução completa. '
       'P no limite matemático do apoio não é contato finito. Origem mecânica imutável.')


def blank_detail():
    return dict(origin='',c_mm=None,physical_ends_match_span=None,connected=None,
                no_opposite_force=None,opposite_clear_distance_mm=None,
                normal_compressive_sign=None,loaded_flange_orientation='')


def reference_configuration(result, extracted=None):
    src=sources.extract(result) if extracted is None else extracted
    return dict(schema=CONFIG_SCHEMA,source_fingerprint=fingerprint(result),
                details={p['point_id']:blank_detail() for p in src['points']})


def _configuration(result,cfg,src):
    if (not isinstance(cfg,dict) or set(cfg)!={'schema','source_fingerprint','details'}
        or cfg.get('schema')!=CONFIG_SCHEMA or cfg.get('source_fingerprint')!=fingerprint(result)
        or not isinstance(cfg.get('details'),dict)
        or set(cfg['details'])!={p['point_id'] for p in src['points']}
        or any(not isinstance(d,dict) or set(d)!=set(blank_detail()) for d in cfg['details'].values())):
        raise ValueError('Detalhes de P não vinculados exatamente ao inventário salvo.')
    return copy.deepcopy(cfg)


def evaluate(section,point,detail):
    actions={k:point[k] for k in ('normal_N','parallel_N','moment_strong_Nmm')}
    common=dict(schema=SCHEMA,source=mechanics.SOURCE,scope=SCOPE,actions=actions,
                local_criterion_only=True,**{k:False for k in FLAGS})
    def pending(code,reason):
        return dict(common,status='not_evaluated',reason_code=code,reason=reason)
    if point['normal_N']==0:
        return dict(common,status='not_applicable',criterion_status='not_applicable',
            reason_code='zero_normal_force',reason='P normal nula dispensa somente esta parcela; reações e P paralela permanecem separadas.')
    if point['mathematical_point_limit']:
        return pending('mathematical_support_limit','P_APOIO é limite matemático, sem área de contato inferida. A reação total de apoio continua exigindo verificação própria.')
    if not mechanics._text(detail.get('loaded_flange_orientation'),2000):
        return pending('loaded_flange_required','Identifique a mesa carregada; ela não é escolhida pelo sinal de P.')
    if detail.get('physical_ends_match_span') is not True:
        return pending('physical_endpoints_required','Declare que os extremos físicos coincidem com 0/L; nenhum contato foi inferido.')
    c=detail.get('c_mm');L=point['L_mm'];x=point['x_mm']
    if not mechanics._finite(c) or c<=0:
        return pending('contact_required','Informe comprimento real positivo de contato c, sem valor presumido.')
    edges=[x-c/2,x+c/2]
    if not all(mechanics._finite(v) for v in edges) or edges[0]<0 or edges[1]>L:
        return pending('patch_outside_member','Contato [x−c/2,x+c/2] fora da peça declarada 0/L; P não é reposicionada.')
    d={k:copy.deepcopy(v) for k,v in detail.items() if k!='physical_ends_match_span'}
    d.update(route='flange_contact',end_distance_mm=min(edges[0],L-edges[1]))
    local=mechanics.evaluate_reaction(section,actions,d)
    # Reuse the reviewed numeric engine, not its support-specific labels.
    out={k:copy.deepcopy(v) for k,v in local.items() if k not in ('schema','scope','reaction','reason')}
    out.update(common)
    out.update(status=local['status'],reason_code=local.get('reason_code'),
               reason=local['reason'].replace('reação de apoio','força aplicada P').replace('reação','força aplicada P').replace('Reação','Força aplicada P'),
               contact_edges_mm=edges,physical_endpoints_mm=[0.,L],detail=copy.deepcopy(detail))
    return out


def calculate(result,configuration):
    src=sources.extract(result);cfg=_configuration(result,configuration,src)
    rows=[dict(source_record=copy.deepcopy(p),detail=copy.deepcopy(cfg['details'][p['point_id']]),
               local=evaluate(src['section'],p,cfg['details'][p['point_id']])) for p in src['points']]
    out=dict(schema=SCHEMA,source_fingerprint=fingerprint(result),configuration=cfg,
        source_inventory=copy.deepcopy(src),rows=rows,summary=summary(rows),scope=SCOPE,
        **{k:False for k in FLAGS})
    out['content_sha256']=fingerprint(out)
    return out


def saved_assessment(result,assessment):
    """Read bound evidence; scalar local replay only, no extraction/member solver."""
    if (not isinstance(assessment,dict) or assessment.get('schema')!=SCHEMA
        or assessment.get('scope')!=SCOPE
        or assessment.get('source_fingerprint')!=fingerprint(result)
        or assessment.get('content_sha256')!=fingerprint({k:v for k,v in assessment.items() if k!='content_sha256'})
        or any(assessment.get(k) is not False for k in FLAGS)):
        raise ValueError('Registro local de P alterado/desvinculado ou com aprovação indevida.')
    src=assessment.get('source_inventory',{})
    _validate_saved_inventory(result,src)
    cfg=_configuration(result,assessment.get('configuration'),src)
    rows=assessment.get('rows')
    if not isinstance(rows,list) or len(rows)!=len(src['points']):raise ValueError('Inventário de P incompleto.')
    for row,p in zip(rows,src['points']):
        d=cfg['details'][p['point_id']];local=row.get('local',{})
        if local!=evaluate(src['section'],p,d):
            raise ValueError('Resistência/domínio/escopo salvo difere da conferência escalar local.')
        if (row.get('source_record')!=p or row.get('detail')!=d
            or local.get('actions')!={k:p[k] for k in ('normal_N','parallel_N','moment_strong_Nmm')}
            or local.get('local_criterion_only') is not True
            or any(local.get(k) is not False for k in FLAGS)):
            raise ValueError('Ações/detalhe/alcance de P incoerentes.')
        status=local.get('status')
        if status not in ('computed','not_evaluated','not_applicable'):raise ValueError('Estado de P inválido.')
        if status=='not_applicable' and p['normal_N']!=0:raise ValueError('Dispensa indevida de P não nula.')
        if status!='computed' and any(k in local for k in ('FRd_N','index')):raise ValueError('Índice sem cálculo.')
        if status=='computed':
            cap=local.get('FRd_N');index=local.get('index');sign=d['normal_compressive_sign']
            if (p['mathematical_point_limit'] or d['physical_ends_match_span'] is not True
                or type(sign) not in (int,float) or sign not in (-1,1) or p['normal_N']*sign<=0
                or not all(mechanics._finite(v) and v>0 for v in (cap,index))
                or local.get('force_N')!=abs(p['normal_N']) or index!=abs(p['normal_N'])/cap
                or local.get('criterion_status')!=('meets' if index<=1 else 'fails')):
                raise ValueError('Aritmética/posição/sentido salvos incoerentes.')
            edges=[p['x_mm']-d['c_mm']/2,p['x_mm']+d['c_mm']/2]
            domain=local.get('domain',{});section=src['section']
            expected=dict(family=section['family'],H_external_mm=section['H'],t_mm=section['t'],ri_mm=section['ri'],fy_MPa=section['fy'],
                c_mm=d['c_mm'],end_distance_mm=min(edges[0],p['L_mm']-edges[1]),connected=d['connected'],
                no_opposite_force=d['no_opposite_force'],opposite_clear_distance_mm=d['opposite_clear_distance_mm'],normal_compressive_sign=sign)
            if (edges[0]<0 or edges[1]>p['L_mm'] or local.get('contact_edges_mm')!=edges
                or not mechanics._text(d.get('loaded_flange_orientation'),2000)
                or local.get('origin')!=d['origin'] or local.get('detail')!=d
                or any(domain.get(k)!=v for k,v in expected.items())):
                raise ValueError('Geometria/detalhe salvos incoerentes.')
    if assessment.get('summary')!=summary(rows):raise ValueError('Resumo de P incoerente.')
    return copy.deepcopy(assessment)


def _validate_saved_inventory(result,src):
    """Compare saved identities/actions to original values, without mechanics."""
    data=result['input_data'];batch=result['schema']=='tercas_batch_results_v1'
    snap=result['common_input_snapshot' if batch else 'input_snapshot']['selected_section']
    fields=snap['fields']
    section=dict(family=snap['family'],H=fields['h']['value'],t=fields['t']['value'],
                 ri=fields['ri_mm']['value'],fy=fields['fy_MPa']['value'])
    if src.get('section')!=section or section['family']!='Ue':raise ValueError('Seção salva de P incoerente.')
    if batch:
        cases=[(c['combination']['id'],c['combination']['x_mm'],c['combination']['P_vector'],
                c['combination'].get('point_position')=='support_limit',c['evidence']['inclination'])
               for c in result['cases'] if c['combination']['limit_state']=='ELU']
    else:
        cases=[('DIRECT_ELU',data['x_uls'],dict(normal=data['P_uls'],parallel=data.get('P_parallel_uls',0.)),False,result['inclination_evidence']['ELU'])]
    points=src.get('points')
    if not isinstance(points,list) or len(points)!=len(cases):raise ValueError('Cobertura salva de P incompleta.')
    for p,(cid,x,force,limit,ev) in zip(points,cases):
        states=[s for s in ev['states'] if s['x_mm']==x]
        if (p.get('point_id')!=cid or p.get('combination_id')!=cid or p.get('limit_state')!='ELU'
            or p.get('x_mm')!=x or p.get('L_mm')!=data['L_mm'] or p.get('mathematical_point_limit') is not limit
            or p.get('normal_N')!=force['normal'] or p.get('parallel_N')!=force['parallel']
            or p.get('concomitant_states')!=states or not states
            or p.get('moment_strong_Nmm')!=states[0]['normal']['M_Nmm']):
            raise ValueError('Inventário salvo de P difere da origem imutável.')
    expected_els=sum(c['combination']['limit_state']=='ELS' for c in result.get('cases',[]))
    if src.get('ELS_combinations_excluded')!=expected_els:raise ValueError('Inventário ELS incoerente.')
    supports=src.get('support_reactions',[])
    if [(s.get('combination_id'),s.get('support_id')) for s in supports]!=[(c[0],side) for c in cases for side in ('left','right')]:
        raise ValueError('Inventário separado de reações incompleto.')

    for p,case in zip(points,cases):
        cid,x,force,limit,ev=case
        if batch:
            combination=next(c['combination'] for c in result['cases'] if c['combination']['id']==cid)
        else:
            combination=dict(id=cid,limit_state='ELU',x_mm=x,q_vector=ev['q_vector'],P_vector=force,origin=data['actions_origin'])
        convention='Força aplicada P sobre a barra, conforme P_vector; sinais não invertidos. '+ev.get('convention','')
        if p.get('combination')!=combination or p.get('source_axis_convention')!=convention:
            raise ValueError('Combinação/convenção salva de P incoerente.')
        for support in [s for s in supports if s['combination_id']==cid]:
            side=support['support_id'];end=0. if side=='left' else data['L_mm']
            states=[st for st in ev['states'] if st['x_mm']==end]
            key='Rleft_N' if side=='left' else 'Rright_N';trace=support.get('trace',{})
            if (not states or support.get('normal_N')!=-states[0]['normal'][key]
                or support.get('parallel_N')!=-states[0]['parallel'][key]
                or support.get('moment_strong_Nmm')!=0. or support.get('x_mm')!=end
                or support.get('limit_state')!='ELU' or support.get('member')!='isolated'
                or trace.get('combination')!=combination or trace.get('concomitant_states')!=states
                or trace.get('q_vector')!=ev['q_vector'] or trace.get('P_vector')!=force
                or trace.get('L_mm')!=data['L_mm'] or trace.get('mathematical_point_limit') is not limit
                or trace.get('source_input_fingerprint')!=result['input_fingerprint']):
                raise ValueError('Reações separadas diferem da evidência salva original.')
