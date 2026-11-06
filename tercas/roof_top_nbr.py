"""NBR pure-bending components from the preserved per-combination roof-height Me.

No legacy mechanics, M–V denominators or AISI capacities are modified. This
component does not assess primary torsion or approve the whole member.
"""
import copy
import math
from . import roof_top_load as roof
from .core.flt_vrd import flt_mse

FIELD='roof_top_nbr_component'
SCHEMA='roof_top_nbr_component_v1'
COMPUTED='computed_NBR_FLT_height'
SOURCE='NBR14762:2010 §§9.8.2.1/.2/.3; Me com altura: Sahraei2017 Eq2 / Vermeylen2023.'
SCOPE=('Componentes NBR de flexão forte pura, por combinação ELU: seção efetiva, '
       'FLT com altura e distorção aplicável. Um vão com garfos nas extremidades e '
       'empenamento livre, sem travamento da telha ou contenções intermediárias. '
       'Não verifica interação com torção/bimomento, deformação pré-flambagem ou '
       'estabilidade sob grandes giros. Atender à componente não aprova a terça.')


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def _expected(result):
    return [(c['id'],c['limit_state']) for c in roof.combination_inventory(result)
            if c.get('limit_state')=='ELU']


def _source(data,result):
    from . import ue_reference as single,ue_family_reference as family
    if family.claims_reference(data):
        state=family.assess(data)
        if not state['calculable']:raise ValueError('Fonte própria não calculável: '+str(state['reasons']+state['action_errors']))
        ref=family.reference(data['properties']['t'],data['L_mm'])
        distortion='Crítico distorcional forte próprio desta espessura; sem dispensa Tabela14.'
        kind='own_Ue100_family';source_field='ue_family_reference_evidence';fresh=family.evidence(data)
    elif single.claims_reference(data):
        state=single.assess(data)
        if not state['calculable']:raise ValueError('Fonte própria não calculável: '+str(state['reasons']+state['action_errors']))
        ref=single.reference(data['L_mm'])
        distortion='Dispensa NBR Tabela14 desta referência 1,20 mm, somente na componente de flexão forte pura; não dispensa torção/bimomento.'
        kind='own_Ue100_t120';source_field='ue_reference_evidence';fresh=single.evidence(data)
    else:
        raise ValueError('Consumo resistente com altura implementado nas sete referências próprias Ue100. '
                         'Para a fonte de catálogo selecionada, coerência de seção/críticos e este consumo ainda não estão integrados; não é proibição normativa do perfil.')
    if fresh!=result.get(source_field):raise ValueError('Evidência resistente própria salva diverge da fonte qualificada.')
    geo=roof.geometry(data)
    # The frozen 1.20 mm vector and torsion mesh use different explicit IDs.
    # Bind both IDs and verify the pinned contours/properties, not string aliasing.
    from .torsion_study import section_for
    section=section_for(data);p=section['properties'];rp=ref['properties']
    for a,b in (('A_mm2','A_mm2'),('Ix_mm4','Ix_strong_mm4'),('Iy_mm4','Iy_weak_mm4'),('J_mm4','J_mm4'),('Cw_mm6','Cw_mm6')):
        if not math.isclose(rp[a],p[b],rel_tol=2e-12):raise ValueError('Propriedades resistentes e do contorno de Me divergentes: '+a)
    caps=ref['resistances_exterior_primary'];positive,negative=[caps[k] for k in ('strong_positive','strong_negative')]
    for key in ('W_mm3','Wc_mm3','Ml_Nmm','MRd_local_Nmm','MRd_dist_Nmm'):
        if positive[key]!=negative[key]:raise ValueError('Esta componente requer resistências fortes iguais nos dois sentidos.')
    c=positive
    return dict(kind=kind,reference_id=fresh['reference_id'],thickness_mm=data['properties']['t'],
        source_reference_field=source_field,source_reference_sha256=roof.digest(fresh),
        source_documents=copy.deepcopy(fresh['source_documents']),nodes_sha256=geo['nodes_sha256'],
        section_profile_id=geo['section_profile_id'],
        W_mm3=c['W_mm3'],Wc_mm3=c['Wc_mm3'],Ml_Nmm=c['Ml_Nmm'],fy_MPa=ref['model']['fy_MPa'],
        E_MPa=ref['model']['E_MPa'],G_MPa=ref['model']['G_MPa'],
        MRd_section_effective_Nmm=c['MRd_local_Nmm'],MRd_distortional_Nmm=c['MRd_dist_Nmm'],
        strong_distortional_exempt=kind=='own_Ue100_t120',distortion_scope=distortion,
        critical_source='Propriedades e críticos próprios R01 protegidos; Pierin apenas corresponde à família nominal.')


def _save(result,evidence):
    out=copy.deepcopy(result);evidence['snapshot_sha256']=roof.digest(evidence)
    out[FIELD]=evidence;out['whole_member_approved']=False
    return out


def attach(result):
    """Fresh calculation boundary only. Uses saved Me, never runs its solver."""
    ev=roof.preserved(result)
    if ev is None or result['input_data'].get('member_application','purlin')!='purlin':return result
    data=result['input_data'];expected=_expected(result)
    if len(set(expected))!=len(expected):raise ValueError('Inventário ELU de cobertura duplicado.')
    evidence=dict(schema=SCHEMA,source_input_fingerprint=result['input_fingerprint'],
        source_roof_snapshot_sha256=ev['snapshot_sha256'],source=SOURCE,scope=SCOPE,
        source_status=ev.get('status'),source_reason=ev.get('reason'),
        domain=dict(start_mm=0.,end_mm=data['L_mm'],end_restraint='fork_free_warping',
                    intermediate_restraints='none',manual_effective_lengths_used=False),
        source_section=None,records=[],computed_cases=0,pending_cases=0,
        ignored_ELS_cases=sum(c.get('limit_state')=='ELS' for c in roof.combination_inventory(result)),
        NBR_pure_bending_component=True,primary_torsion_assessed=False,AISI_capacities_changed=False,
        M_V_denominators_changed=False,legacy_mechanics_changed=False,
        physical_conditions_verified=False,whole_member_approved=False)
    try:section=_source(data,result)
    except (ValueError,TypeError,KeyError,OSError) as exc:section=None;source_reason=str(exc)
    else:source_reason=None;evidence['source_section']=section
    combos={(c['id'],c['limit_state']):c for c in roof.combination_inventory(result)}
    if result.get('schema')=='tercas_batch_results_v1' and [c.get('combination') for c in result.get('cases',[])]!=result.get('load_bundle',{}).get('combinations',[]):
        raise ValueError('Casos resistentes não correspondem às combinações esperadas.')
    by_id={}
    for r in ev.get('records',[]):
        key=(r.get('combination_id'),r.get('limit_state'))
        if key in by_id:raise ValueError('Componente Me possui identidade duplicada.')
        by_id[key]=r
    if by_id and set(by_id)!={(c['id'],c['limit_state']) for c in roof.combination_inventory(result)}:
        raise ValueError('Componente Me não corresponde ao inventário de combinações.')
    for cid,state in expected:
        r=by_id.get((cid,state));base=dict(combination_id=cid,limit_state=state,
            source_roof_snapshot_sha256=ev['snapshot_sha256'],
            source_combination_sha256=roof.digest(combos[(cid,state)]),
            source_me_record_sha256=roof.digest(r) if r is not None else None,whole_member_approved=False,
            primary_torsion_assessed=False)
        reason=source_reason or (ev.get('reason') if r is None else None)
        if r is None:reason=reason or 'Me ausente para esta combinação.'
        elif (r.get('numerically_converged') is not True or not finite(r.get('Me_Nmm')) or r['Me_Nmm']<=0):
            reason=reason or r.get('reason') or 'Me não utilizável: '+str(r.get('status'))
        if reason:
            evidence['records'].append(dict(base,status='pending',reason=reason,index=None));continue
        M=r.get('maximum_reference_moment_Nmm')
        if not finite(M) or M<=0:raise ValueError('Momento de referência inválido para consumir Me.')
        envelope=r.get('direct_envelope') is True
        if envelope:
            from .direct_roof_envelope import nbr_resistance_floor
            cap=nbr_resistance_floor(section['Wc_mm3'],section['fy_MPa'],section['Ml_Nmm'],r['Me_Nmm'])
        else:cap=flt_mse(section['Wc_mm3'],section['fy_MPa'],section['Ml_Nmm'],r['Me_Nmm'])
        parts=dict(section_effective=section['MRd_section_effective_Nmm'],FLT_height=cap['MRd_flt_Nmm'])
        if section['MRd_distortional_Nmm'] is not None:parts['distortional']=section['MRd_distortional_Nmm']
        minimum=min(parts.values());index=M/cap['MRd_flt_Nmm']
        evidence['records'].append(dict(base,status=COMPUTED,reason=SCOPE,
            Me_Nmm=r['Me_Nmm'],Msd_max_abs_Nmm=M,FLT=cap,index=index,
            criterion_status=('inconclusive' if envelope else 'fails') if index>1 else 'meets',
            MRd_section_effective_Nmm=section['MRd_section_effective_Nmm'],
            MRd_distortional_Nmm=section['MRd_distortional_Nmm'],
            MRd_bending_component_Nmm=minimum,bending_component_index=M/minimum,
            governing_bending_components=[k for k,v in parts.items() if v==minimum],
            Cb_applied_after_Me=False,primary_torque_by_action=copy.deepcopy(r['primary_torque_by_action']),
            M_V_denominator_source='NBR14762 §9.8.4 usa seção efetiva (§9.8.2.1); não alterado por esta componente.'))
        if r.get('separate_axis_capacity_scope',{}).get('applicable'):
            from .roof_biaxial import interaction
            own=result[section['source_reference_field']]
            evidence['records'][-1]['biaxial']=interaction(combos[(cid,state)],data['L_mm'],minimum,own)
        if envelope:
            evidence['records'][-1].update(resistance_is_lower_envelope=True,
                reason=SCOPE+' Altura direta envolvida por hipótese conservadora; índice acima de 1 com piso resistente é inconclusivo, não reprovação da resistência real. Torção e parcelas paralelas ocultas permanecem fora desta garantia.')
    evidence['computed_cases']=sum(r['status']==COMPUTED for r in evidence['records'])
    evidence['pending_cases']=len(expected)-evidence['computed_cases']
    if ev.get('load_basis')=='direct_total_top_envelope':
        evidence['inconclusive_envelope_cases']=sum(r.get('criterion_status')=='inconclusive' for r in evidence['records'])
    if evidence['computed_cases']:
        evidence['status']='components_computed' if not evidence['pending_cases'] else 'partial_components'
    else:
        evidence['status']='pending' if expected or ev.get('reason') or source_reason else 'no_ELU_selected'
    if not expected:evidence['reason']=ev.get('reason') or source_reason or 'Nenhuma combinação ELU selecionada; ELS não recebe resistência de ELU.'
    return _save(result,evidence)


def preserved(result):
    """Validate saved identity/coverage/flags only; no solver or source reopening."""
    saved=result.get(FIELD)
    if saved is None:return None
    try:ev=roof.preserved(result)
    except (AttributeError,TypeError,KeyError) as exc:
        raise ValueError('Componente Me salva malformada.') from exc
    if (not isinstance(saved,dict) or ev is None or saved.get('schema')!=SCHEMA
        or saved.get('source_input_fingerprint')!=result.get('input_fingerprint')
        or saved.get('source_roof_snapshot_sha256')!=ev.get('snapshot_sha256')
        or saved.get('snapshot_sha256')!=roof.digest({k:v for k,v in saved.items() if k!='snapshot_sha256'})
        or saved.get('domain')!=dict(start_mm=0.,end_mm=result['input_data']['L_mm'],
            end_restraint='fork_free_warping',intermediate_restraints='none',manual_effective_lengths_used=False)
        or any(saved.get(k) is not False for k in ('primary_torsion_assessed','AISI_capacities_changed',
            'M_V_denominators_changed','legacy_mechanics_changed','physical_conditions_verified','whole_member_approved'))):
        raise ValueError('Componente resistente NBR no topo desatualizada ou alterada; recalcule explicitamente.')
    section=saved.get('source_section')
    if section is not None:
        if not isinstance(section,dict):raise ValueError('Fonte resistente salva deve ser um objeto.')
        own=result.get(section.get('source_reference_field'))
        if (not isinstance(own,dict) or section.get('source_reference_sha256')!=roof.digest(own)
            or own.get('reference_id')!=section.get('reference_id')
            or section.get('nodes_sha256')!=(ev.get('geometry') or {}).get('nodes_sha256')
            or section.get('section_profile_id')!=(ev.get('geometry') or {}).get('section_profile_id')):
            raise ValueError('Fonte resistente ou contorno da componente salvo divergente.')
        caps=own.get('signed_scalar_capacities',{});model=own.get('model',{})
        if not isinstance(caps,dict) or not isinstance(model,dict):raise ValueError('Evidência resistente salva malformada.')
        for side in ('strong_positive','strong_negative'):
            c=caps.get(side,{})
            if not isinstance(c,dict):raise ValueError('Capacidade resistente salva malformada.')
            for target,origin in (('W_mm3','W_mm3'),('Wc_mm3','Wc_mm3'),('Ml_Nmm','Ml_Nmm'),
                                  ('MRd_section_effective_Nmm','MRd_local_Nmm'),('MRd_distortional_Nmm','MRd_dist_Nmm')):
                if section.get(target)!=c.get(origin):raise ValueError('Valor resistente difere da fonte própria salva: '+target)
        if any(section.get(k)!=model.get(k) for k in ('E_MPa','G_MPa','fy_MPa')):
            raise ValueError('Material resistente difere da fonte própria salva.')
        if section.get('source_documents')!=own.get('source_documents'):
            raise ValueError('Documentos resistentes diferem da fonte própria salva.')
    rows=saved.get('records');expected=_expected(result)
    combos={(c['id'],c['limit_state']):c for c in roof.combination_inventory(result)}
    me_records={(r.get('combination_id'),r.get('limit_state')):r for r in ev.get('records',[])}
    if result.get('schema')=='tercas_batch_results_v1' and [c.get('combination') for c in result.get('cases',[])]!=result.get('load_bundle',{}).get('combinations',[]):
        raise ValueError('Inventário independente de casos/combinações alterado.')
    if (not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows) or [(r.get('combination_id'),r.get('limit_state')) for r in rows]!=expected
        or saved.get('computed_cases')!=sum(r.get('status')==COMPUTED for r in rows)
        or saved.get('pending_cases')!=sum(r.get('status')=='pending' for r in rows)):
        raise ValueError('Inventário resistente NBR no topo incompleto ou inconsistente.')
    if 'inconclusive_envelope_cases' in saved and saved['inconclusive_envelope_cases']!=sum(r.get('criterion_status')=='inconclusive' for r in rows):
        raise ValueError('Contagem de envoltórias inconclusivas alterada.')
    for r in rows:
        key=(r.get('combination_id'),r.get('limit_state'));me_record=me_records.get(key)
        if (r.get('source_combination_sha256')!=roof.digest(combos[key])
            or r.get('source_me_record_sha256')!=(roof.digest(me_record) if me_record is not None else None)):
            raise ValueError('Vínculo individual Me/combinação alterado.')
        if (r.get('status') not in (COMPUTED,'pending') or r.get('whole_member_approved') is not False
            or r.get('primary_torsion_assessed') is not False
            or r.get('source_roof_snapshot_sha256')!=ev['snapshot_sha256']):
            raise ValueError('Registro resistente com domínio/identidade incompatível.')
        if r['status']==COMPUTED:
            if not isinstance(r.get('FLT'),dict):raise ValueError('Curva FLT salva malformada.')
            if (section is None or me_record is None or me_record.get('numerically_converged') is not True
                or not finite(r.get('Me_Nmm')) or r['Me_Nmm']<=0
                or not finite(r.get('Msd_max_abs_Nmm')) or r['Msd_max_abs_Nmm']<=0
                or r.get('Me_Nmm')!=me_record.get('Me_Nmm')
                or r.get('Msd_max_abs_Nmm')!=me_record.get('maximum_reference_moment_Nmm')
                or r.get('primary_torque_by_action')!=me_record.get('primary_torque_by_action')
                or not finite(r.get('index')) or r['index']<0 or r.get('criterion_status')!=((('inconclusive' if me_record.get('direct_envelope') is True else 'fails')) if r['index']>1 else 'meets')
                or r.get('Cb_applied_after_Me') is not False or r.get('FLT',{}).get('gamma')!=1.1
                or not finite(r.get('FLT',{}).get('MRd_flt_Nmm')) or r['FLT']['MRd_flt_Nmm']<=0):
                raise ValueError('Resultado FLT salvo não utilizável.')
            if (any(not finite(r['FLT'].get(k)) or r['FLT'][k]<=0 for k in ('lambda0','chi_flt','lambda_p_reduced_stress','Wceff_mm3'))
                or r['FLT']['chi_flt']>1 or r['FLT']['Wceff_mm3']>section['Wc_mm3']):
                raise ValueError('Parâmetros da curva FLT salva inválidos.')
            if me_record.get('direct_envelope') is True:
                lower=r['FLT'].get('lower_envelope',{})
                if (r.get('resistance_is_lower_envelope') is not True or not isinstance(lower,dict)
                    or lower.get('applied') is not True or lower.get('original_formula_unchanged') is not True
                    or lower.get('arithmetic_floor_only') is not True or lower.get('physical_resistance_bound') is not False
                    or lower.get('lambda_transition')!=1.336 or lower.get('chi_intermediate_limit')!=1.11*(1-.278*1.336**2)
                    or not isinstance(lower.get('original_formula'),dict)):
                    raise ValueError('Envoltória resistente direta salva alterada.')
            elif r.get('resistance_is_lower_envelope') or 'lower_envelope' in r['FLT']:
                raise ValueError('Envoltória direta não pertence ao caso por área.')
            # Serialized arithmetic identities only, not another resistance solve.
            if (r['index']!=r['Msd_max_abs_Nmm']/r['FLT']['MRd_flt_Nmm']
                or r.get('MRd_section_effective_Nmm')!=section['MRd_section_effective_Nmm']
                or r.get('MRd_distortional_Nmm')!=section['MRd_distortional_Nmm']):
                raise ValueError('Índice ou componentes inconsistentes com os valores salvos.')
            parts=dict(section_effective=section['MRd_section_effective_Nmm'],FLT_height=r['FLT']['MRd_flt_Nmm'])
            if section['MRd_distortional_Nmm'] is not None:parts['distortional']=section['MRd_distortional_Nmm']
            minimum=min(parts.values())
            if (r.get('MRd_bending_component_Nmm')!=minimum or r.get('bending_component_index')!=r['Msd_max_abs_Nmm']/minimum
                or r.get('governing_bending_components')!=[k for k,v in parts.items() if v==minimum]):
                raise ValueError('Mínimo de componentes ou índice salvo inconsistente.')
            if 'biaxial' in r:
                from .roof_biaxial import validate_saved
                if not me_record.get('separate_axis_capacity_scope',{}).get('applicable'):
                    raise ValueError('Interação NBR no topo sem posição fraca qualificada.')
                validate_saved(r['biaxial'],dict(combos[key],span_mm=result['input_data']['L_mm']),
                    minimum,result[section['source_reference_field']])
            elif me_record.get('separate_axis_capacity_scope',{}).get('applicable'):
                raise ValueError('Resistência por eixo salva sem interação concomitante.')
        elif r.get('index') is not None or not r.get('reason') or 'biaxial' in r:
            raise ValueError('Pendência FLT salva não pode conter índice ou interação ativa.')
    return copy.deepcopy(saved)


def validate_saved_global(result):
    """Do not display an old promotion after its supporting sidecar is removed."""
    global_record=result.get('global_verification')
    if not isinstance(global_record,dict):return
    binding=global_record.get('roof_top_nbr_binding')
    claims=[r for r in global_record.get('checks',[]) if isinstance(r,dict)
            and isinstance(r.get('trace'),dict) and r['trace'].get('roof_top_nbr_snapshot_sha256') is not None]
    if binding is None and not claims:return
    if not isinstance(binding,dict):raise ValueError('Vínculo do panorama FLT no topo ausente ou inválido.')
    ev=preserved(result)
    clean=copy.deepcopy(global_record)
    recorded_hash=clean.get('roof_top_nbr_binding',{}).pop('global_snapshot_sha256',None)
    if (ev is None or not isinstance(binding,dict)
        or recorded_hash!=roof.digest(clean)
        or global_record.get('source_input_fingerprint')!=result.get('input_fingerprint')
        or global_record.get('whole_member_approved') is not False
        or binding.get('snapshot_sha256')!=ev['snapshot_sha256']
        or binding.get('source_roof_snapshot_sha256')!=ev['source_roof_snapshot_sha256']
        or any(r['trace']['roof_top_nbr_snapshot_sha256']!=ev['snapshot_sha256'] for r in claims)):
        raise ValueError('Panorama salvo reivindica FLT no topo sem a componente vinculada íntegra; recalcule explicitamente.')
    expected={(r['combination_id'],'FLT_height') for r in ev['records']}|{(r['combination_id'],'FLT_coverage') for r in ev['records']}
    expected|={(r['combination_id'],'biaxial') for r in ev['records'] if 'biaxial' in r}
    observed=[(r.get('trace',{}).get('combination_id'),r['id'].rsplit(':',1)[-1]) for r in claims]
    if len(observed)!=len(expected) or set(observed)!=expected:
        raise ValueError('Panorama salvo não conserva o inventário FLT do topo.')
