"""Automatic per-action load height for an explicitly selected roof scheme.

This is an elastic-critical component; existing resistance denominators are
not silently replaced. No roof restraint, automatic PP duplication or inferred
zero horizontal eccentricity is introduced.
"""
import copy
import math
import hashlib
import json
from .ltb_load_height import refined,finite

FIELD='roof_top_load'
SCHEMA='roof_top_load_v1'
LINES=('web_midplane','flange_midwidth')
SCOPE=('Me elástico do esquema de cobertura: um vão inteiro, garfos ideais nas '
       'extremidades e empenamento livre, sem travamento intermediário ou rigidez '
       'da telha. PP no CG e demais ações na cota superior da seção. A posição '
       'de cada ação entra separadamente. Não calcula resistência conjunta com '
       'torção, deformação pré-flambagem, modos locais/distorcionais ou aprovação global.')
REFERENCE='Vlasov: Sahraei et al. CSCE2017 Eq2; canal: Vermeylen et al. Eurosteel2023; NBR14762 §9.8.2.2 p48.'

LEGACY_COMPARATOR_NOTE=('Comparador da referência no CT, com Cb=1: os Me e MRd/FLT deste bloco não são a resistência da carga no topo. O Me com altura está na componente própria da cobertura; MRd com altura, quando calculado, consta no bloco NBR próprio e não é substituído por estes comparadores no CT.')


def choice(load_line='web_midplane'):
    return dict(schema=SCHEMA,enabled=True,load_line=load_line,
                end_restraint='fork_free_warping',intermediate_restraints='none')


def configuration(data):
    if FIELD not in data:return None
    c=data[FIELD]
    if (not isinstance(c,dict) or set(c)!=set(choice()) or c.get('schema')!=SCHEMA
        or type(c.get('enabled')) is not bool or c.get('load_line') not in LINES
        or c.get('end_restraint')!='fork_free_warping' or c.get('intermediate_restraints')!='none'):
        raise ValueError('Esquema de carga no topo inválido; dados preservados, sem conversão automática.')
    return copy.deepcopy(c)


def enabled(data):
    c=configuration(data)
    return bool(c and c['enabled'])


def geometry(data):
    c=configuration(data)
    if c is None:raise ValueError('Selecione o esquema de aplicação no topo.')
    from .catalogs import catalog_entry
    entry=catalog_entry(data['catalog_index'])
    if entry['family'] not in ('U','Ue'):raise ValueError('Esquema para U/Ue simétrico no eixo forte.')
    p=data['properties'];h,b,t=[finite(p[k],k,True) for k in ('h','bf','t')]
    if h<=2*t or b<=t:raise ValueError('Dimensões incompatíveis com a seção do esquema.')
    g=dict(h_mm=h,bf_mm=b,t_mm=t,height_above_SC_mm=h/2,
        load_x_from_web_midplane_mm=0. if c['load_line']=='web_midplane' else (b-t)/2,
        web_midplane_to_flange_midwidth_mm=(b-t)/2,
        load_line=c['load_line'],x_from_CG_mm=None,x_from_SC_mm=None,
        coherent_torsion_section=False,
        source='Altura externa nominal h/2; seção U/Ue simétrica no eixo forte: CG e CT na meia-altura. '
               'Abscissa/torque do catálogo não inferidos de convenções geométricas divergentes.',
        physical_load_line_verified=False,scheme_is_assumed_model=True)
    from .ue_family_reference import claims_reference as family_claims
    from .ue_reference import claims_reference as single_claims
    from .ue_catalog_reference import claims_reference as catalog_claims, source_binding
    if family_claims(data) or single_claims(data) or catalog_claims(data):
        from .torsion_study import section_for
        s=section_for(data);sp=s['properties'];cg=sp['centroid_xy_mm'];sc=sp['shear_center_xy_mm']
        # R01 source origin is intersection of web/lower-flange midsurfaces.
        # Physical outer top = h-t/2, web midsurface x=0; total width midpoint
        # spans the physical outside interval [-t/2,bf-t/2].
        x=0. if c['load_line']=='web_midplane' else (b-t)/2
        y=h-t/2
        if not math.isclose(sc[1],(h-t)/2,abs_tol=1e-9,rel_tol=1e-12):
            raise ValueError('Contorno próprio não corresponde à simetria/cota do esquema.')
        g.update(height_above_SC_mm=y-sc[1],x_from_CG_mm=x-cg[0],x_from_SC_mm=x-sc[0],
            y_from_CG_mm=y-cg[1],CG_xy_mm=list(cg),SC_xy_mm=list(sc),
            coherent_torsion_section=True,section_profile_id=s['profile_id'],
            nodes_sha256=s['nodes_sha256'],source='Contorno próprio R01 verificado: cota externa superior e posição do esquema, com CG/CT do mesmo contorno.')
    if catalog_claims(data):
        g['source']='Contorno próprio Ue nominal: CG/CT e linha de topo do mesmo contorno.'
        g['ue_catalog_source_binding']=source_binding(data)
    return g


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _source_snapshot(result, schema='roof_top_load_evidence_v1'):
    from . import direct_roof_envelope as direct
    from . import direct_roof_separated as separated
    if schema==separated.SCHEMA:
        return digest(dict(schema=result.get('schema'),direct_separated_inputs=separated.combinations(result['input_data'])))
    if schema==direct.SCHEMA:
        return digest(dict(schema=result.get('schema'),direct_combined_inputs=direct.combinations(result['input_data'])))
    return digest(dict(schema=result.get('schema'),load_bundle=result.get('load_bundle'),
        combinations=[r.get('combination') for r in result.get('cases',[])]))


def _save(result,evidence):
    evidence['source_load_snapshot_sha256']=_source_snapshot(result,evidence['schema'])
    evidence['snapshot_sha256']=digest(evidence)
    result['roof_top_load_evidence']=evidence
    result['whole_member_approved']=False
    return result


def preserved(result):
    """Validate saved numbers without recalculation or reopening section sources."""
    ev=result.get('roof_top_load_evidence')
    if ev is None:return None
    from .application import fingerprint
    from . import direct_roof_envelope as direct,direct_roof_separated as separated
    if (not isinstance(ev,dict) or ev.get('schema') not in ('roof_top_load_evidence_v1',direct.SCHEMA,separated.SCHEMA)
        or fingerprint(result['input_data'])!=result.get('input_fingerprint')
        or ev.get('source_input_fingerprint')!=result.get('input_fingerprint')
        or ev.get('choice_snapshot')!=configuration(result['input_data'])
        or ev.get('source_load_snapshot_sha256')!=_source_snapshot(result,ev.get('schema'))
        or ev.get('snapshot_sha256')!=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
        or ev.get('resistance_qualified') is not False or ev.get('whole_member_approved') is not False
        or any(r.get('whole_member_approved',False) is not False or
            r.get('production_resistance_authorized',False) is not False for r in ev.get('records',[]))):
        raise ValueError('Componente Me no topo incompatível com o snapshot; recalcule explicitamente.')
    if ev['schema']==direct.SCHEMA:
        if (result['input_data'].get('load_mode')!='direct' or result.get('schema')!='NBR14762_one_span_v1'
            or ev.get('load_basis')!=direct.BASIS or ev.get('direct_envelope_assumptions')!=direct.ASSUMPTIONS
            or ev.get('self_weight_added') is not False or ev.get('primary_torque_enveloped') is not False):
            raise ValueError('Contrato da envoltória direta alterado.')
        rows=ev.get('records',[])
        if rows and [(r.get('combination_id'),r.get('limit_state')) for r in rows]!=[(c['id'],c['limit_state']) for c in direct.combinations(result['input_data'])]:
            raise ValueError('Inventário direto da envoltória incompleto.')
        if any(r.get('direct_envelope') is not True or
            any(t.get('value') is not None for t in r.get('primary_torque_by_action',[])) for r in rows):
            raise ValueError('Envoltória de altura não pode declarar torque real.')
    if ev['schema']==separated.SCHEMA:
        from .direct_self_weight import evidence as pp_evidence
        if (ev.get('load_basis')!=separated.BASIS or ev.get('direct_self_weight')!=pp_evidence(result['input_data'])
            or ev.get('self_weight_added') is not True or ev.get('primary_torque_enveloped') is not False):
            raise ValueError('Contrato de PP separado alterado.')
        rows=ev.get('records',[])
        if rows and [(r.get('combination_id'),r.get('limit_state')) for r in rows]!=[(c['id'],c['limit_state']) for c in separated.combinations(result['input_data'])]:
            raise ValueError('Inventário direto separado incompleto.')
    for r in ev.get('records',[]):
        if 'separate_axis_capacity_scope' in r:
            from .roof_biaxial_geometry import supported_geometry,validate_geometry
            if supported_geometry(ev.get('geometry') or {}):
                validate_geometry(ev['geometry'],result['input_data'])
            from .roof_biaxial import classify_for_roof as classify,torque_records
            combo=next(c for c in combination_inventory(result) if c['id']==r['combination_id'])
            expected_actions=separated.actions(combo,ev['geometry'],include_parallel=True)[0] if ev['schema']==separated.SCHEMA else _actions(result['load_bundle'],combo,ev['geometry'],include_parallel=True)[0]
            if r['actions']!=expected_actions:
                raise ValueError('Ações por eixo não correspondem às parcelas salvas.')
            scope=classify(r['actions'],ev.get('geometry') or {})
            if scope!=r['separate_axis_capacity_scope'] or (r.get('Me_Nmm') is not None and not scope['applicable']):
                raise ValueError('Domínio por eixo da componente Me salvo divergente.')
            if 'primary_torque_by_action' in r:
                if (r.get('primary_torque_report_includes_parallel_actions') is not True
                    or r['primary_torque_by_action']!=torque_records(r['actions'],True)
                    or r.get('normal_projection_primary_torque_by_action')!=torque_records(r['actions'],False)):
                    raise ValueError('Torque total/projeção normal da componente Me salvo divergente.')
    return copy.deepcopy(ev)


def combination_inventory(result):
    """Saved-model identity, no solver and no retroactive v1 direct promotion."""
    from . import direct_roof_envelope as direct
    ev=result.get('roof_top_load_evidence',{})
    from . import direct_roof_separated as separated
    if ev.get('schema')==separated.SCHEMA and ev.get('load_basis')==separated.BASIS:
        return separated.combinations(result['input_data'])
    if ev.get('schema')==direct.SCHEMA and ev.get('load_basis')==direct.BASIS:
        return direct.combinations(result['input_data'])
    return copy.deepcopy(result.get('load_bundle',{}).get('combinations',[]))


def _pending(result,c,reason,geo=None):
    return dict(schema='roof_top_load_evidence_v1',status='pending_model_scope',reason=reason,
        source_input_fingerprint=result['input_fingerprint'],choice_snapshot=c,geometry=geo,
        scope=SCOPE,source=REFERENCE,records=[],computed_cases=0,
        resistance_qualified=False,whole_member_approved=False)


def _actions(bundle,combo,geo, *, include_parallel=False):
    acts=[];parallel=[]
    for role,factor in combo['coefficients'].items():
        if role=='P':continue
        vector=bundle['case_vectors_N_mm'][role]
        normal=factor*vector['normal'];x=factor*vector['parallel']
        if x!=0:parallel.append(role)
        if normal==0 and x==0:continue
        is_pp=role=='PP';ex=None
        if geo['coherent_torsion_section']:
            ex=geo['CG_xy_mm'][0]-geo['SC_xy_mm'][0] if is_pp else geo['x_from_SC_mm']
        acts.append(dict(name=role,kind='uniform',q_down_N_mm=normal,q_parallel_N_mm=x,
            height_above_SC_mm=0. if is_pp else geo['height_above_SC_mm'],x_from_SC_mm=ex,
            load_line_source='PP no CG, somado uma vez' if is_pp else geo['source']))
    pv=combo['P_vector']
    if pv['parallel']!=0:parallel.append('P')
    if pv['normal']!=0 or pv['parallel']!=0:
        acts.append(dict(name='P',kind='point',P_down_N=pv['normal'],P_parallel_N=pv['parallel'],s_mm=combo['x_mm'],
            height_above_SC_mm=geo['height_above_SC_mm'],x_from_SC_mm=geo['x_from_SC_mm'],
            load_line_source=geo['source'],position=combo.get('point_position','fixed')))
    if not include_parallel:
        for a in acts:
            a.pop('q_parallel_N_mm',None);a.pop('P_parallel_N',None)
    return acts,parallel


def attach(result):
    """Only for a fresh explicit calculation; rendering never calls this function."""
    data=result['input_data'];c=configuration(data)
    if c is None or not c['enabled']:return result
    from .application import fingerprint
    if result.get('input_fingerprint')!=fingerprint(data):raise ValueError('Resultado de cobertura desatualizado.')
    out=copy.deepcopy(result)
    if data.get('member_application','purlin')!='purlin':
        ev=_pending(result,c,
            'Esquema de cobertura armazenado, inativo na travessa. A fachada exige orientação e ações próprias; o programa não interpreta sua face carregada como topo da terça.')
        return _save(out,ev)
    if data.get('load_mode')=='direct' and result.get('schema')=='NBR14762_one_span_v1':
        from .direct_self_weight import active as pp_active
        return _attach_direct_separated(result,c) if pp_active(data) else _attach_direct(result,c)
    if data.get('load_mode')!='area' or result.get('schema')!='tercas_batch_results_v1':
        ev=_pending(result,c,
            'Me com altura requer separar PP e cargas da cobertura. No modo direto, q já combinado não revela essa divisão: nenhum PP foi acrescentado nem toda a carga foi deslocada ao topo. Use ações por área para este esquema.')
        return _save(out,ev)
    from .model_domain import evidence
    if evidence(data)['conflict']:
        ev=_pending(result,c,evidence(data)['conflict']);return _save(out,ev)
    try:geo=geometry(data)
    except (ValueError,TypeError,KeyError,OSError) as exc:
        return _save(out,_pending(result,c,'Geometria do esquema não qualificada: '+str(exc)))
    from .batch import area_bundle
    expected=area_bundle(data)
    if expected!=result.get('load_bundle'):raise ValueError('Ações por área salvas divergem das entradas; recalcule.')
    combos=expected['combinations']
    if [x['combination'] for x in result['cases']]!=combos:raise ValueError('Combinações salvas incompletas ou alteradas.')
    p=data['properties']
    try:
        params=dict(L_mm=finite(data['L_mm'],'L',True),E_MPa=finite(p['E_MPa'],'E',True),
            G_MPa=finite(p['G_MPa'],'G',True),Iweak_mm4=finite(p['Iy_cm4'],'Iy',True)*1e4,
            J_mm4=finite(p['J_mm4'],'J',True),Cw_mm6=finite(p['Cw_mm6'],'Cw',True))
    except (ValueError,TypeError,KeyError) as exc:
        return _save(out,_pending(result,c,'Propriedades elásticas para Me não disponíveis: '+str(exc),geo))
    records=[]
    for combo in combos:
        base=dict(combination_id=combo['id'],limit_state=combo['limit_state'])
        acts,parallel=_actions(expected,combo,geo,include_parallel=True)
        if parallel:
            from .roof_biaxial import classify_for_roof as classify
            scope=classify(acts,geo);base['separate_axis_capacity_scope']=scope
            if not scope['applicable']:
                records.append(dict(base,status='pending_biaxial_model',Me_Nmm=None,lambda_cr=None,
                    reason='Interação por resistências separadas pendente: '+scope['reason'],actions=acts));continue
        try:
            calc=refined(**params,actions=acts)
        except (ValueError,ArithmeticError) as exc:
            records.append(dict(base,status='pending_numerical_qualification',reason=str(exc),Me_Nmm=None,lambda_cr=None,actions=acts));continue
        if parallel:
            from .roof_biaxial import annotate_projection
            calc=annotate_projection(calc,acts)
        records.append(dict(base,**calc,actions=acts))
    count=sum(r.get('numerically_converged') is True and r.get('Me_Nmm') is not None for r in records)
    ev=dict(schema='roof_top_load_evidence_v1',
        status='elastic_critical_component' if count else 'pending_model_scope',
        source_input_fingerprint=result['input_fingerprint'],choice_snapshot=c,geometry=geo,
        scope=SCOPE,source=REFERENCE,records=records,computed_cases=count,pending_cases=len(records)-count,
        resistance_qualified=False,whole_member_approved=False,
        torsion_assessment_separate=True,legacy_bending_denominators_unchanged=True,
        manual_effective_lengths_used=False,
        length_scope='Vão inteiro do esquema; comprimentos efetivos manuais armazenados não são usados por esta componente.')
    return _save(out,ev)


def _attach_direct(result,c):
    from . import direct_roof_envelope as direct
    from .model_domain import evidence
    data=result['input_data'];out=copy.deepcopy(result)
    ev=_pending(result,c,'')
    ev.update(schema=direct.SCHEMA,scope=direct.SCOPE,load_basis=direct.BASIS,
        direct_envelope_assumptions=copy.deepcopy(direct.ASSUMPTIONS),
        self_weight_added=False,self_weight_quantity_assumed=False,primary_torque_enveloped=False,
        manual_effective_lengths_used=False,legacy_bending_denominators_unchanged=True)
    if evidence(data)['conflict']:
        ev['reason']=evidence(data)['conflict'];return _save(out,ev)
    try:
        geo=geometry(data);ev['geometry']=geo;p=data['properties']
        params=dict(L_mm=finite(data['L_mm'],'L',True),E_MPa=finite(p['E_MPa'],'E',True),
            G_MPa=finite(p['G_MPa'],'G',True),Iweak_mm4=finite(p['Iy_cm4'],'Iy',True)*1e4,
            J_mm4=finite(p['J_mm4'],'J',True),Cw_mm6=finite(p['Cw_mm6'],'Cw',True))
    except (ValueError,TypeError,KeyError,OSError) as exc:
        ev['reason']='Dados do modelo direto não qualificados: '+str(exc);return _save(out,ev)
    rows=[]
    for combo in direct.combinations(data):
        acts,parallel=direct.actions(combo,geo)
        base=dict(combination_id=combo['id'],limit_state=combo['limit_state'],direct_envelope=True,
            load_height_substitution_is_conservative_in_declared_scalar_model=True,
            physical_applicability_verified=False,actions=acts)
        if parallel:
            rows.append(dict(base,status='pending_biaxial_model',Me_Nmm=None,lambda_cr=None,
                reason='Componente paralela direta não nula em '+', '.join(parallel)+'. Não é apagada para liberar a envoltória uniaxial.'));continue
        try:calc=refined(**params,actions=acts)
        except (ValueError,ArithmeticError) as exc:
            rows.append(dict(base,status='pending_numerical_qualification',Me_Nmm=None,lambda_cr=None,reason=str(exc)));continue
        rows.append(dict(base,**calc))
    count=sum(r.get('numerically_converged') is True and r.get('Me_Nmm') is not None for r in rows)
    ev.update(status='elastic_critical_component' if count else 'pending_model_scope',reason='',
        records=rows,computed_cases=count,pending_cases=len(rows)-count,
        torsion_assessment_separate=True,
        length_scope='Vão inteiro do esquema; comprimentos efetivos manuais não entram nesta componente.')
    return _save(out,ev)


def _attach_direct_separated(result,c):
    from . import direct_roof_separated as direct
    from .direct_self_weight import evidence as pp_evidence
    from .model_domain import evidence
    data=result['input_data'];out=copy.deepcopy(result)
    ev=_pending(result,c,'')
    ev.update(schema=direct.SCHEMA,load_basis=direct.BASIS,
        direct_self_weight=pp_evidence(data),self_weight_added=True,
        primary_torque_enveloped=False,manual_effective_lengths_used=False,
        legacy_bending_denominators_unchanged=True)
    if evidence(data)['conflict']:
        ev['reason']=evidence(data)['conflict'];return _save(out,ev)
    try:
        geo=geometry(data);ev['geometry']=geo;p=data['properties']
        params=dict(L_mm=finite(data['L_mm'],'L',True),E_MPa=finite(p['E_MPa'],'E',True),
            G_MPa=finite(p['G_MPa'],'G',True),Iweak_mm4=finite(p['Iy_cm4'],'Iy',True)*1e4,
            J_mm4=finite(p['J_mm4'],'J',True),Cw_mm6=finite(p['Cw_mm6'],'Cw',True))
    except (ValueError,TypeError,KeyError,OSError) as exc:
        ev['reason']='Dados do modelo direto não qualificados: '+str(exc);return _save(out,ev)
    records=[]
    for combo in direct.combinations(data):
        acts,parallel=direct.actions(combo,geo,include_parallel=True)
        base=dict(combination_id=combo['id'],limit_state=combo['limit_state'],
                  direct_envelope=False,physical_applicability_verified=False,actions=acts)
        if parallel:
            from .roof_biaxial import classify_for_roof as classify
            scope=classify(acts,geo);base['separate_axis_capacity_scope']=scope
            if not scope['applicable']:
                records.append(dict(base,status='pending_biaxial_model',Me_Nmm=None,lambda_cr=None,
                    reason='Interação por resistências separadas pendente: '+scope['reason']));continue
        try:calc=refined(**params,actions=acts)
        except (ValueError,ArithmeticError) as exc:
            records.append(dict(base,status='pending_numerical_qualification',Me_Nmm=None,lambda_cr=None,reason=str(exc)));continue
        if parallel:
            from .roof_biaxial import annotate_projection
            calc=annotate_projection(calc,acts)
        records.append(dict(base,**calc))
    count=sum(r.get('numerically_converged') is True and r.get('Me_Nmm') is not None for r in records)
    ev.update(status='elastic_critical_component' if count else 'pending_model_scope',reason='',
        records=records,computed_cases=count,pending_cases=len(records)-count,
        torsion_assessment_separate=True,
        length_scope='Vão inteiro do esquema; comprimentos efetivos manuais não entram nesta componente.')
    return _save(out,ev)
