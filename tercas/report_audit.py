"""Read-only presentation of saved evidence. No structural calculations or verdicts."""
import math
from numbers import Real

TECHNICAL_NOTE=('Quadros técnicos de dados salvos usam até oito algarismos significativos, '
    'sem acrescentar precisão à origem ou executar novo cálculo. Os resumos mantêm '
    'duas casas e o JSON conserva os valores salvos.')


def finite(value):
    return isinstance(value,Real) and not isinstance(value,bool) and math.isfinite(float(value))


def technical_number(value,limit=None):
    """Never zero a small nonzero value; never hide a rounded threshold crossing."""
    if value is None:return 'Não registrado'
    if isinstance(value,bool) or not isinstance(value,Real):return str(value)
    if not finite(value):return 'Não finito — não utilizável'
    n=float(value);shown=format(0. if n==0 else n,'.8g')
    if finite(limit) and n!=float(limit) and shown==format(float(limit),'.8g'):
        return shown.replace('.',',')+' ('+('>' if n>limit else '<')+format(float(limit),'.8g').replace('.',',')+')'
    return shown.replace('.',',')


def technical_value(value):
    if isinstance(value,dict):return '{'+'; '.join(str(k)+': '+technical_value(v) for k,v in value.items())+'}'
    if isinstance(value,(list,tuple)):return '['+'; '.join(technical_value(v) for v in value)+']'
    return technical_number(value)


def _paragraph(doc,text,*,keep_next=False):
    p=doc.add_paragraph(text);p.paragraph_format.keep_together=True
    p.paragraph_format.keep_with_next=keep_next
    return p


def report_fingerprint(doc,value):
    # Keep the final identifier with a preceding body paragraph, not alone on a page.
    if doc.paragraphs:doc.paragraphs[-1].paragraph_format.keep_with_next=True
    _paragraph(doc,'Identificação das entradas: '+str(value))


_MECHANISMS={'local':'Flexão local','distortional':'Distorcional','FLT':'FLT',
    'FLT_height':'FLT com carga no topo — vão inteiro','FLT_coverage':'Cobertura do domínio FLT','shear':'Cortante',
    'MV':'Flexão e cortante concomitantes','biaxial':'Flexão biaxial',
    'point_introduction_scope':'Introdução da força concentrada',
    'axial_scope':'Escopo axial','secondary_shear_scope':'Cortante secundário',
    'deflection':'Componente de deslocamento','combined_ELS_scope':'ELS físico completo',
    'torsion_warping':'Torção e empenamento','model_domain':'Domínio do modelo'}


def saved_issues(result):
    """Group only existing pending/failing records; never rebuild the inventory."""
    record=result.get('global_verification')
    if not isinstance(record,dict) or not isinstance(record.get('checks'),list):return []
    groups={}
    for item in record['checks']:
        if not isinstance(item,dict) or item.get('status') not in ('pending','fails'):continue
        trace=item.get('trace') if isinstance(item.get('trace'),dict) else {}
        state=item.get('limit_state','Não registrado');cid=trace.get('combination_id')
        identity=str(item.get('id','Identidade não registrada'));prefix=str(state)+':'+str(cid)+':'
        mechanism=identity[len(prefix):] if cid is not None and identity.startswith(prefix) else identity
        label=(_MECHANISMS['FLT']+' — trecho '+mechanism[4:] if mechanism.startswith('FLT:') else _MECHANISMS.get(mechanism,mechanism))
        reason=item.get('reason') or 'Motivo não registrado.';source=item.get('source') or 'Fonte não registrada.'
        key=(str(state),label,item['status'],str(reason),str(source))
        if key not in groups:groups[key]=dict(limit_state=str(state),mechanism=label,status=item['status'],reason=str(reason),source=str(source),combination_ids=[],record_ids=[])
        group=groups[key]
        if cid is not None and str(cid) not in group['combination_ids']:group['combination_ids'].append(str(cid))
        group['record_ids'].append(identity)
    return list(groups.values())


def issue_text(group):
    status='Pendente no registro' if group['status']=='pending' else 'Não atende no registro'
    cases=', '.join(group['combination_ids']) if group['combination_ids'] else ('escopo comum do modelo' if group['limit_state']=='MODEL' else 'combinação/escopo não registrado')
    return (group['limit_state']+' — '+group['mechanism']+' — '+status+'. '+
        'Combinação/escopo: '+cases+'. '+group['reason']+' Origem registrada: '+group['source'])


def report_saved_issues(doc,result):
    issues=saved_issues(result)
    if not issues:return
    doc.add_heading('Motivos do estado salvo',2)
    _paragraph(doc,'Pendências e não atendimentos já registrados, agrupados quando o motivo é idêntico. '
        'Este quadro não recompõe contagens, não requalifica históricos e não cria verificações ou índices ativos.')
    for item in issues:_paragraph(doc,issue_text(item))


def show_saved_issues(st,result):
    issues=saved_issues(result)
    if not issues:return
    with st.expander('Motivos do estado salvo',expanded=False):
        st.caption('Somente pendências e não atendimentos já registrados. Sem recompor contagens, recalcular ou requalificar o histórico.')
        for item in issues:st.caption(issue_text(item))


_BRANCH={'a_bound_left':'intervalo à esquerda de P','a_bound_right':'intervalo à direita de P',
    'a_equals_x_left':'seção na posição de P, lado esquerdo',
    'a_equals_x_right':'seção na posição de P, lado direito',
    'support_layer_before_P':'camada junto ao apoio, antes de P'}
_MV_COMPUTED={'computed','computed_fixed_load_position'}


def _mv_state(doc,state,label,normal_point):
    parts=[label]
    if state.get('position_limit'):parts.append(str(state['position_limit']))
    parts.append('x registrado='+technical_number(state.get('x_mm'))+' mm')
    if state.get('a_limit'):parts.append('posição limite de P: '+str(state['a_limit']))
    elif finite(normal_point) and float(normal_point)==0:
        parts.append('sem P normal; a registrado é partição inativa, não carga ativa')
    else:parts.append('a registrado='+technical_number(state.get('a_mm'))+' mm')
    branch=state.get('branch')
    if branch is not None:parts.append('ramo: '+(_BRANCH.get(branch,branch) if isinstance(branch,str) else 'identificador não textual')+' ['+str(branch)+']')
    parts.append('Σ índices² registrado='+technical_number(state.get('index_squared'),limit=1.))
    for key,name,scale,unit in [('M_Nmm','M',1e6,'kN·m'),('V_N','V',1000.,'kN')]:
        parts.append(name+' nesta posição='+technical_number(state[key]/scale)+' '+unit if finite(state.get(key)) else name+' nesta posição: não registrado')
    _paragraph(doc,'; '.join(parts)+'.')


def report_mv_trace(doc,evidence,case_id,normal_point=None,*,point_position=None,expected_a_mm=None):
    b=evidence.get('NBR_branches') if isinstance(evidence,dict) else None
    raw=b.get('MV') if isinstance(b,dict) else None
    if not isinstance(raw,dict):return
    state=raw.get('result')
    if not isinstance(state,dict):return
    _paragraph(doc,'Traço M–V salvo — combinação '+str(case_id)+' (ELU)',keep_next=True)
    if raw.get('status') not in _MV_COMPUTED:
        _paragraph(doc,'Traço não concluído no registro; valores candidatos não são apresentados como verificação. '+str(raw.get('reason') or raw.get('missing') or 'Estado: '+str(raw.get('status','não registrado'))))
        return
    limits=raw.get('limit_states')
    support=point_position=='support_limit' or raw.get('position')=='support_limit'
    if support:
        declared=raw.get('governing_state')
        governing=raw.get('governing_states')
        if governing is None:governing=[declared]
        coherent=(point_position in (None,'support_limit') and raw.get('position')=='support_limit'
            and isinstance(limits,dict) and set(limits)=={'interior_q_only','support_layer'}
            and isinstance(declared,str) and declared in limits and isinstance(governing,list) and bool(governing)
            and all(isinstance(k,str) and k in limits for k in governing)
            and len(set(governing))==len(governing) and declared in governing and state==limits[declared]
            and all(isinstance(v,dict) and v.get('a_mm') is None and v.get('a_limit')=='a→0+'
                    and finite(v.get('x_mm')) and finite(v.get('index_squared')) and v['index_squared']>=0
                    for v in limits.values()))
        if coherent:
            # Consistency of already saved scalars only; no interaction formula or solver.
            saved_max=max(v['index_squared'] for v in limits.values())
            coherent=set(governing)=={k for k,v in limits.items() if v['index_squared']==saved_max}
        if not coherent:
            _paragraph(doc,'Traço M–V legado, incompleto ou inconsistente para P no limite a→0+. '
                'O adaptador interior não identifica uma posição finita física nem o estado governante reconciliado. '
                'Seus valores não são promovidos neste quadro; sem recálculo ou recuperação de outro objeto.')
            return
    elif (not finite(state.get('x_mm')) or not finite(state.get('index_squared')) or state['index_squared']<0
          or (finite(normal_point) and normal_point!=0 and finite(expected_a_mm)
              and (not finite(state.get('a_mm')) or state['a_mm']!=expected_a_mm))):
        _paragraph(doc,'Traço M–V incompleto ou com posição divergente da combinação salva; '
            'valores não apresentados como governantes e nenhuma posição reconstruída.')
        return
    _paragraph(doc,'Base do método registrada: '+str(raw.get('source','Não registrada'))+'. '
        'Critério da verificação: Σ índices² ≤ 1. Posições e parcelas abaixo pertencem à mesma combinação; '
        'não são somas de máximos independentes.',keep_next=True)
    if support:
        for key,item in limits.items():
            if not isinstance(item,dict):continue
            label={'interior_q_only':'Interior após P no limite','support_layer':'Camada junto ao apoio antes de P'}.get(key,str(key))
            if key in governing:label+=' — governante salvo'
            _mv_state(doc,item,label,normal_point)
        _paragraph(doc,'Estados limites distintos preservados. Não há posição finita inventada para a→0+ nem nova varredura de posições.')
    else:_mv_state(doc,state,'Estado governante salvo',normal_point)


def component_record_is_readable(result):
    from . import aa_component as aa,biaxial_component as gross
    for module in (aa,gross):
        if module.claims_result(result):
            try:module.preserved_snapshot(result)
            except (ValueError,TypeError,KeyError,ArithmeticError,IndexError):return False
    return True


def report_els_trace(doc,result,evidence,case_id,reference=None,*,readable=None):
    """Use only the saved ELS object and existing snapshot validators, never inputs to infer a new limit."""
    raw=evidence.get('ELS') if isinstance(evidence,dict) else None
    if not isinstance(raw,dict):return
    if readable is None:readable=component_record_is_readable(result)
    if not readable:return
    if 'upper_bound_mm' in raw:
        from .aa_component import claims_result
        if not claims_result(result):return
    _paragraph(doc,'Critério e grandeza ELS salvos — combinação '+str(case_id),keep_next=True)
    source=raw.get('source')
    if not source:
        local=raw.get('local_uniaxial_component')
        if isinstance(local,dict):source=local.get('formula_source')
    if not source:
        family=raw.get('family_ELS_scope')
        if isinstance(family,dict):source=family.get('source')
    _paragraph(doc,'Base do método: '+str(source or reference or 'Não registrada neste objeto ELS')+'. '
        'A referência do método não define por si só o limite adotado.',keep_next=True)
    origin=raw.get('limit_origin')
    limit=raw.get('limit_mm')
    _paragraph(doc,'Limite declarado salvo: '+(technical_number(limit)+' mm' if finite(limit) else 'não disponível')+
        '. Origem do critério: '+str(origin or 'Não registrada junto ao resultado ELS')+
        '. Não é prescrição normativa automática nem aprovação do sistema.')
    if finite(raw.get('upper_bound_mm')):
        _paragraph(doc,'Grandeza salva: teto conservador '+technical_number(raw['upper_bound_mm'])+
            ' mm, não flecha exata; não há posição de máximo determinada por este teto. '
            'Acima do limite, o teto não demonstra descumprimento físico.')
    elif finite(raw.get('deflection_mm')):
        diagnostic=raw.get('diagnostic_only') is True or raw.get('criterion_status') not in ('meets','fails')
        label='Componente flexional salva, apenas diagnóstica' if diagnostic else 'Componente flexional salva no modelo delimitado'
        position='; x registrado='+technical_number(raw['x_mm'])+' mm' if finite(raw.get('x_mm')) else '; posição do extremo não registrada'
        _paragraph(doc,label+': '+technical_number(raw['deflection_mm'])+' mm'+position+'.')
    else:_paragraph(doc,'Grandeza ELS não disponível neste registro; não foi recuperada de outra rota ou calculada na emissão.')
    _paragraph(doc,'A situação e o índice permanecem os da linha de verificação. Este detalhamento não requalifica o registro nem conclui ELS físico/global.')
