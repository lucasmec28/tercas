"""Explicit isolated EN component: dense calculation, immutable saved readers."""
import copy
import hashlib
import json
import math
from pathlib import Path

from .isolated_en_stress import check_member, stress_norm, _sha as field_digest, SCHEMA as BOUND_SCHEMA

CHOICE='isolated_en_stress_model'
CHOICE_SCHEMA='isolated_EN_intact_section_choice_v1'
FIELD='isolated_EN_stress_component'
SCHEMA='isolated_EN_saved_stress_component_v1'
FALSE_FLAGS=('whole_member_approved','complete_EN_design_qualified','global_stability_qualified',
             'NBR_capacities_used','AISI_capacities_used')
MATERIAL=dict(E_MPa=210000.,nu=.3,fyb_MPa=250.,fya_MPa=250.,gamma_M0=1.)
SCOPE=('Complemento independente EN1993-1-3:2006 §6.1.6: tensões normais, '
       'cisalhamento V/Tsv/Tw e interação σ–τ no mesmo campo Vlasov. '
       'Teto ≤1 demonstra somente suficiência dessa componente; teto >1 é inconclusivo. '
       'Não substitui NBR/AISI nem aprova o elemento.')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def identity(data):
    return digest(dict(properties=data.get('properties'),steel_name=data.get('steel_name'),
        own_reference=data.get('ue_family_reference',data.get('ue_reference')),
        member_application=data.get('member_application','purlin')))


def choice(data,*,enabled=True,declared=False,origin=''):
    return dict(schema=CHOICE_SCHEMA,enabled=enabled,intact_section_model_declared=declared,
        model_origin=origin,section_material_identity=identity(data))


def configuration(data):
    c=data.get(CHOICE)
    if c is None:return None
    if (not isinstance(c,dict) or set(c)!=set(choice(data)) or c.get('schema')!=CHOICE_SCHEMA
            or type(c.get('enabled')) is not bool or type(c.get('intact_section_model_declared')) is not bool
            or not isinstance(c.get('model_origin'),str) or not isinstance(c.get('section_material_identity'),str)):
        raise ValueError('Escolha EN isolada malformada; não foi convertida nem ativada automaticamente.')
    return copy.deepcopy(c)


def reset_changed_declaration(data):
    """Keep opt-in intent, never carry physical declaration to another section."""
    c=configuration(data)
    if c is not None and c['section_material_identity']!=identity(data):
        data[CHOICE]=choice(data,enabled=c['enabled'])
        return True
    return False


def _domain_reason(data,c):
    if c['section_material_identity']!=identity(data):
        return 'Seção/material/aplicação mudou; declare novamente o modelo intacto e sua origem.'
    if not c['intact_section_model_declared'] or not c['model_origin'].strip():
        return 'Declaração de seção nominal intacta e origem ainda não preenchidas.'
    network=data.get('three_girt_model',{})
    if not isinstance(network,dict):
        return 'Modelo de três travessas malformado; dado original preservado, sem cálculo EN isolado.'
    if data.get('member_application','purlin')!='purlin' or network.get('enabled'):
        return 'Complemento exclusivo do vão isolado de terça; a rede/travessa usa sua rota própria.'
    fy=data.get('properties',{}).get('fy_MPa')
    if isinstance(fy,bool) or fy!=250.:
        return 'Material fora do domínio: esta componente exige fyb=fya=250 MPa; não converte outro aço.'
    if not (isinstance(data.get('ue_family_reference'),dict) or isinstance(data.get('ue_reference'),dict)):
        return 'Sem referência própria Ue100 íntegra; coincidência dimensional de catálogo não qualifica a seção.'
    return None


def _inventory(result):
    if isinstance(result.get('cases'),list):
        return [dict(combination_id=c['combination']['id'],limit_state=c['combination']['limit_state'],
            source_combination=copy.deepcopy(c['combination'])) for c in result['cases']]
    if result.get('schema')=='NBR14762_one_span_v1':
        source=result.get('torsion_evidence',{}).get('source_combinations')
        if source is not None:
            return [dict(combination_id=c['id'],limit_state=c['limit_state'],source_combination=copy.deepcopy(c)) for c in source]
        return [dict(combination_id='DIRECT_'+ls,limit_state=ls,source_combination=None) for ls in ('ELU','ELS')]
    return []


def _base(result,c):
    inventory=_inventory(result)
    return dict(schema=SCHEMA,configuration=copy.deepcopy(c),source_input_fingerprint=result['input_fingerprint'],
        section_material_identity=identity(result['input_data']),source_inventory=inventory,
        source_fy_MPa=result['input_data'].get('properties',{}).get('fy_MPa'),
        material=copy.deepcopy(MATERIAL),scope=SCOPE,records=[],
        ELU_cases=sum(r['limit_state']=='ELU' for r in inventory),
        ELS_cases_excluded=sum(r['limit_state']=='ELS' for r in inventory),
        computed_cases=0,pending_cases=0,all_section_stress_criteria_satisfied=False,
        historical_results_requalified=False,original_mechanics_changed=False,
        **{k:False for k in FALSE_FLAGS})


def _pending(result,c,reason):
    ev=_base(result,c)
    ev.update(status='pending_component',reason=reason,records=[dict(combination_id=r['combination_id'],
        limit_state='ELU',status='pending',reason=reason,check=None,source_analysis_sha256=None)
        for r in ev['source_inventory'] if r['limit_state']=='ELU'])
    ev['pending_cases']=len(ev['records'])
    return ev


def attach_dense(result,section):
    """Must precede torsion summary; does not mutate the torsion/AISI snapshots."""
    if CHOICE not in result['input_data']:return result
    out=copy.deepcopy(result)
    try:c=configuration(out['input_data'])
    except ValueError as exc:
        out[FIELD]=_pending(out,out['input_data'][CHOICE],str(exc));return out
    if c is None or not c['enabled']:return out
    reason=_domain_reason(out['input_data'],c)
    if reason:out[FIELD]=_pending(out,c,reason);return out
    try:
        from .torsion_study import section_for,PINS
        verified=section_for(out['input_data'])
        if section!=verified:raise ValueError('Seção fornecida não é a fonte própria atual.')
        t=section['thickness_mm']
        path=Path(__file__).with_name('data')/'torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=PINS[t]:raise ValueError('Fonte geométrica EN alterada.')
        profile=json.loads(raw)
        torsion=out.get('torsion_evidence',{})
        if torsion.get('schema')!='purlin_torsion_batch_evidence_v1':
            raise ValueError('Campo integral ausente; não recalcular a partir do resumo histórico.')
        expected=_inventory(out)
        source=torsion.get('records',[])
        if [(r['combination_id'],r['limit_state']) for r in source]!=[(r['combination_id'],r['limit_state']) for r in expected]:
            raise ValueError('Inventário de combinações torsionais divergente.')
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError) as exc:
        out[FIELD]=_pending(out,c,str(exc));return out
    ev=_base(out,c)
    ev['source_profile']=dict(profile_id=section['profile_id'],nodes_sha256=section['nodes_sha256'],
        content_sha256=section['content_sha256'],thickness_mm=section['thickness_mm'],profile_file_sha256=PINS[t])
    for rec in source:
        if rec['limit_state']!='ELU':continue
        row=dict(combination_id=rec['combination_id'],limit_state='ELU',status='pending',
            reason=None,check=None,source_analysis_sha256=None)
        analysis=rec.get('analysis')
        if rec.get('status')!='elastic_demand_computed' or not isinstance(analysis,dict):
            row['reason']='Demanda Vlasov pendente: '+'; '.join(rec.get('missing',[]))
        else:
            try:
                if analysis['combination_id']!=rec['combination_id'] or analysis['limit_state']!='ELU':
                    raise ValueError('Campo pertence a outra combinação/estado limite.')
                row['source_analysis_sha256']=field_digest(analysis)
                row['check']=check_member(analysis,profile,intact_section_model_declared=True,model_origin=c['model_origin'])
                row['status']='computed'
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:row['reason']=str(exc)
        ev['records'].append(row)
    ev['computed_cases']=sum(r['status']=='computed' for r in ev['records'])
    ev['pending_cases']=len(ev['records'])-ev['computed_cases']
    ev['all_section_stress_criteria_satisfied']=bool(ev['records']) and not ev['pending_cases'] and all(
        r['check']['section_stress_criteria_sufficiently_satisfied'] for r in ev['records'])
    ev['status']='computed_components' if not ev['pending_cases'] else 'partial_or_pending_components'
    out[FIELD]=ev
    return out


def finalize(result):
    """Seal only a new calculation, after the compact torsion snapshot is final."""
    if CHOICE not in result['input_data']:return result
    out=copy.deepcopy(result)
    try:
        c=configuration(out['input_data'])
        if c is None or not c['enabled']:return out
        reason=_domain_reason(out['input_data'],c)
    except ValueError as exc:c=out['input_data'][CHOICE];reason=str(exc)
    if FIELD not in out:
        reason=reason or out.get('torsion_evidence',{}).get('reason') or 'Demanda Vlasov integral indisponível; ative um modelo isolado elegível e calcule novamente.'
        out[FIELD]=_pending(out,c,reason)
    ev=out[FIELD];torsion=out.get('torsion_evidence')
    ev['source_torsion_snapshot_sha256']=digest(torsion)
    saved={r['combination_id']:r for r in (torsion or {}).get('records',[])}
    for row in ev['records']:
        row['source_summary_record_sha256']=digest(saved.get(row['combination_id']))
    ev['snapshot_sha256']=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    return out


def _finite_nonnegative(x):
    return type(x) in (float,int) and math.isfinite(x) and x>=0


def _validate_bound(check,row,summary,ev):
    from .isolated_en_stress import _sha, SAVED_SCOPE
    if (not isinstance(check,dict) or check.get('schema')!=BOUND_SCHEMA
            or check.get('content_sha256')!=_sha({k:v for k,v in check.items() if k!='content_sha256'})
            or check.get('combination_id')!=row['combination_id']
            or check.get('source_demand_sha256')!=row['source_analysis_sha256']
            or check.get('material')!=MATERIAL or check.get('model_origin')!=ev['configuration']['model_origin']
            or check.get('normal_limit_MPa')!=250. or check.get('shear_limit_MPa')!=250/math.sqrt(3.)
            or check.get('interaction_limit_MPa')!=275. or check.get('full_member_field_covered') is not True
            or check.get('intact_section_model_declared') is not True
            or any(check.get(k) is not False for k in FALSE_FLAGS)
            or any(check.get(k)!=v for k,v in SAVED_SCOPE.items())):
        raise ValueError('Limites, modelo ou integridade do critério EN salvos inválidos.')
    analysis=summary.get('analysis') if isinstance(summary,dict) else None
    if (not isinstance(analysis,dict) or summary.get('status')!='elastic_demand_computed'
            or analysis.get('schema')!='single_vlasov_member_summary_v1'
            or analysis.get('numerics',{}).get('qualification_passed') is not True
            or analysis.get('analysis_domain',{}).get('axial_force_in_this_model_N')!=0
            or analysis.get('limit_state')!='ELU' or analysis.get('combination_id')!=row['combination_id']
            or check.get('member_id')!=analysis.get('member_id')
            or check.get('source_analysis_material')!=dict(E_MPa=analysis['E_MPa'],G_MPa=analysis['G_MPa'])
            or check.get('source_geometry_sha256')!=analysis['section']['nodes_sha256']
            or check.get('source_geometry_sha256')!=ev['source_profile']['nodes_sha256']):
        raise ValueError('Critério EN e demanda compacta não são da mesma fonte/caso.')
    from .torsion_study import PINS
    profile=ev['source_profile'];saved_section=analysis['section']
    if (profile.get('profile_id')!=saved_section.get('profile_id')
            or profile.get('content_sha256')!=saved_section.get('content_sha256')
            or profile.get('thickness_mm')!=saved_section.get('thickness_mm')
            or profile.get('profile_file_sha256')!=PINS.get(saved_section.get('thickness_mm'))):
        raise ValueError('Fonte geométrica EN salva incompatível com o contorno torsional.')
    if any(a.get('existing_point_position')=='support_limit' for a in analysis['loads']) and not analysis.get('support_limit_states'):
        raise ValueError('Limite a→0+ sem estado before-P preservado.')
    if not isinstance(check.get('source_demand_sha256'),str) or len(check['source_demand_sha256'])!=64:
        raise ValueError('Identidade do campo integral ausente.')
    criteria=check.get('criteria')
    if not isinstance(criteria,dict) or set(criteria)!=set(('normal','shear','interaction')):
        raise ValueError('Três critérios EN independentes requeridos.')
    from .torsion_vlasov.intervals import Interval as I
    limits=dict(normal=I(250.),shear=I(250.)/I(3.).sqrt(),interaction=I(250.)*I(1.1))
    for key,record in criteria.items():
        upper=record.get('index_upper_bound');control=record.get('bound_control',{})
        if (not _finite_nonnegative(upper) or record.get('criterion')!=('within_limit' if upper<=1 else 'inconclusive_upper_bound')
                or record.get('observed_exceedance') is not False or control.get('is_physical_state') is not False):
            raise ValueError('Teto EN não é uma reprovação nem uma testemunha física.')
        sigma=I(*control['sigma_interval_MPa']);tau=I(*control['tau_interval_MPa'])
        value=sigma.abs() if key=='normal' else tau.abs() if key=='shear' else stress_norm(sigma,tau)
        replay=float((value/limits[key]).hi)
        if replay!=upper:raise ValueError('Índice EN divergente do controle de tensão salvo.')
    passed=all(r['index_upper_bound']<=1 for r in criteria.values())
    if check.get('section_stress_criteria_sufficiently_satisfied') is not passed:
        raise ValueError('Estado EN incompatível com seus três tetos.')


def preserved(result):
    """No solver, geometry files, load generation or effective-section builder."""
    ev=result.get(FIELD)
    if ev is None:return None
    from .application import fingerprint
    try:
        c=configuration(result['input_data'])
        if (not isinstance(ev,dict) or ev.get('schema')!=SCHEMA or c is None or not c['enabled']
                or fingerprint(result['input_data'])!=result.get('input_fingerprint')
                or ev.get('source_input_fingerprint')!=result['input_fingerprint']
                or ev.get('configuration')!=c or ev.get('section_material_identity')!=identity(result['input_data'])
                or ev.get('source_inventory')!=_inventory(result)
                or ev.get('source_fy_MPa')!=result['input_data']['properties']['fy_MPa']
                or ev.get('material')!=MATERIAL or ev.get('scope')!=SCOPE
                or ev.get('snapshot_sha256')!=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
                or ev.get('source_torsion_snapshot_sha256')!=digest(result.get('torsion_evidence'))
                or any(ev.get(k) is not False for k in FALSE_FLAGS)
                or ev.get('historical_results_requalified') is not False or ev.get('original_mechanics_changed') is not False):
            raise ValueError('Componente EN incompatível com o estudo salvo; recalcule explicitamente.')
        expected=[r for r in ev['source_inventory'] if r['limit_state']=='ELU']
        rows=ev['records']
        if (not isinstance(rows,list) or [(r['combination_id'],r['limit_state']) for r in rows]
                !=[(r['combination_id'],r['limit_state']) for r in expected]):
            raise ValueError('Cobertura ELU do complemento EN incompleta ou duplicada.')
        summaries={r['combination_id']:r for r in result.get('torsion_evidence',{}).get('records',[])}
        for row in rows:
            summary=summaries.get(row['combination_id'])
            if row['source_summary_record_sha256']!=digest(summary):raise ValueError('Fonte compacta EN alterada.')
            if row['status']=='computed':
                if _domain_reason(result['input_data'],c):raise ValueError('Componente EN calculada fora do domínio declarado.')
                _validate_bound(row['check'],row,summary,ev)
            elif row['status']!='pending' or row['check'] is not None or not row.get('reason'):
                raise ValueError('Pendência EN sem motivo ou com índice fabricado.')
        n=sum(r['status']=='computed' for r in rows)
        passed=bool(rows) and n==len(rows) and all(r['check']['section_stress_criteria_sufficiently_satisfied'] for r in rows)
        if (any(type(ev.get(k)) is not int for k in ('computed_cases','pending_cases','ELU_cases','ELS_cases_excluded'))
                or ev['computed_cases']!=n or ev['pending_cases']!=len(rows)-n or ev['ELU_cases']!=len(rows)
                or ev['ELS_cases_excluded']!=sum(r['limit_state']=='ELS' for r in ev['source_inventory'])
                or ev['all_section_stress_criteria_satisfied'] is not passed):
            raise ValueError('Contagem/atendimento EN divergente do inventário salvo.')
    except (KeyError,TypeError,IndexError,AttributeError) as exc:
        raise ValueError('Registro EN isolado incompleto ou malformado.') from exc
    return copy.deepcopy(ev)


def global_context(result):
    """Inventory wording only: never inserts EN indices into NBR/H4/global sums."""
    ev=preserved(result)
    if ev is None:return None
    text=(f"Tensões EN §6.1.6 avaliadas em {ev['computed_cases']} casos ELU; "
        f"{ev['pending_cases']} casos pendentes de demanda/modelo. ")
    if ev['all_section_stress_criteria_satisfied']:
        text+='As três desigualdades são satisfeitas por condição suficiente no campo declarado. '
    elif ev['computed_cases']:
        text+='Tetos inconclusivos ou cobertura pendente não demonstram reprovação. '
    text+=('Permanecem separadas a flambagem por cisalhamento EN6.1.5, a redução N–M–V EN6.1.10, '
        'a estabilidade e adequação da análise, as forças locais e o ELS completo. '
        'Não é resistência torsional/global integral.')
    return dict(reason=text,binding=dict(snapshot_sha256=ev['snapshot_sha256'],computed_cases=ev['computed_cases'],
        pending_cases=ev['pending_cases'],scope='Independent EN section-stress inventory only; no global approval'))


def validate_saved_global(result):
    context=global_context(result)
    binding=result.get('global_verification',{}).get('isolated_EN_binding')
    expected=None if context is None else context['binding']
    if binding!=expected:raise ValueError('Panorama e complemento EN pertencem a snapshots diferentes.')
