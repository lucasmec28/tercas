"""Opt-in production consumer of dense isolated-purlin ELS fields.

Original combinations and compact torsion evidence are unchanged. The extra
Appendix A note-f suction calculation lives only in this separate component.
"""
import copy
import math
from .completion_requirements import digest
from .serviceability_plan import prepare, table_a1_limit, CRITERIA
from . import isolated_service_mechanics as mechanics

CHOICE='isolated_combined_service'
FIELD='isolated_combined_service_component'
CONFIG_SCHEMA='isolated_combined_service_choice_v1'
SCHEMA='isolated_combined_service_snapshot_v1'
FALSE_FLAGS=('whole_member_approved','combined_ELS_approved','physical_first_order_applicability_qualified')
SCOPE=('Comparação do deslocamento combinado no campo linear bruto do mesmo modelo, '
       'com crivo suficiente MLE nas cinco paredes e guarda elástica incluindo Mx/My/B/V/T. '
       'Não transforma giro linear grande em giro físico nem conclui estabilidade ou ELS físico integral.')


def blank_choice():
    return dict(schema=CONFIG_SCHEMA,enabled=True,point_xy_from_CG_mm=[None,None],projection_xy=[None,None],
        point_label='',direction_label='',reference='physical_end_chord_same_point',reference_declared=False,
        criterion=None,limit_mm=None,criterion_origin='Deslocamento total da combinação selecionada, sem contraflecha.',
        model_origin='Modelo isolado, contorno próprio e vínculos declarados na análise.',nominal_intact_section_declared=False)


def configuration(data):
    raw=data.get(CHOICE)
    if raw is None:return None
    if not isinstance(raw,dict) or set(raw)!=set(blank_choice()) or raw.get('schema')!=CONFIG_SCHEMA:
        raise ValueError('Escolha de serviço combinado desconhecida; entradas não convertidas.')
    if any(type(raw[k]) is not bool for k in ('enabled','nominal_intact_section_declared','reference_declared')):
        raise ValueError('Escolha de serviço exige booleanos explícitos.')
    if raw['reference']!='physical_end_chord_same_point' or raw['criterion'] not in (None,'nbr_A1_pair','declared_limit'):
        raise ValueError('Referência ou critério de serviço não suportado.')
    for key in ('point_xy_from_CG_mm','projection_xy'):
        if not isinstance(raw[key],list) or len(raw[key])!=2:raise ValueError('Duas componentes necessárias: '+key)
        for value in raw[key]:
            if value is not None:mechanics.number(value,key)
    if raw['limit_mm'] is not None:mechanics.number(raw['limit_mm'],'Limite',True)
    for key in ('point_label','direction_label','criterion_origin','model_origin'):
        if not isinstance(raw[key],str):raise ValueError('Texto necessário: '+key)
    return copy.deepcopy(raw)


def active_model(data,c):
    return bool(c and c['enabled'] and data.get('member_application','purlin')=='purlin'
                and not data.get('three_girt_model',{}).get('enabled'))


def missing_configuration(c):
    missing=[]
    if not c['reference_declared']:missing.append('Adoção explícita da corda dos extremos físicos do mesmo ponto.')
    if not c['nominal_intact_section_declared']:missing.append('Adoção explícita da seção nominal íntegra no modelo.')
    for key,label in [('point_label','Ponto de serviço'),('direction_label','Direção de serviço')]:
        if not c[key].strip():missing.append(label)
    if any(v is None for key in ('point_xy_from_CG_mm','projection_xy') for v in c[key]):missing.append('Coordenadas do ponto e vetor da direção.')
    elif not math.isclose(sum(v*v for v in c['projection_xy']),1.,rel_tol=1e-12,abs_tol=1e-12):missing.append('Vetor unitário de direção.')
    if c['criterion'] is None:missing.append('Seleção explícita do critério de comparação.')
    if c['criterion']=='declared_limit' and c['limit_mm'] is None:missing.append('Limite de deslocamento declarado.')
    return missing


def _inventory(result,c):
    if c['criterion'] is None:return []
    if result.get('schema')=='tercas_batch_results_v1':
        combos=result.get('load_bundle',{}).get('combinations',[])
    else:
        from .direct_torsion import active
        if active(result['input_data']):
            from .direct_roof_separated import combinations
            combos=combinations(result['input_data'])
        else:
            # An unsupported legacy total remains pending, without decomposition.
            combos=[dict(id='DIRECT_ELS',limit_state='ELS',source='saved direct ELS input',
                         source_input_fingerprint=result.get('input_fingerprint'))]
    els=[r for r in combos if r.get('limit_state')=='ELS']
    if c['criterion']=='declared_limit':
        return [dict(id=r['id'],source_combination=copy.deepcopy(r),kind='existing',limit_mm=c['limit_mm']) for r in els]
    if c['criterion']!='nbr_A1_pair':return []
    plan=prepare(result);by_id={r['id']:r for r in els}
    rows=[dict(id=cid,source_combination=copy.deepcopy(by_id[cid]),kind='existing',
               limit_mm=table_a1_limit(result['input_data']['L_mm'],CRITERIA[0])['limit_mm'])
          for cid in plan.get('same_direction_rare_case_ids',[]) if cid in by_id]
    if not rows:rows.append(dict(id='A1_E_RARE_COVERAGE',kind='pending',reason='Nenhuma combinação rara candidata de mesmo sentido selecionada; a matriz não foi alterada.',limit_mm=None))
    if plan.get('opposite_action_status')=='explicitly_zero_characteristic_wind':
        rows.append(dict(id='SERVICE_A1_F_CHARACTERISTIC_SUCTION',kind='zero_characteristic_wind',limit_mm=table_a1_limit(result['input_data']['L_mm'],CRITERIA[1])['limit_mm']))
    elif plan.get('prepared_cases'):
        case=plan['prepared_cases'][0]
        rows.append(dict(id=case['id'],kind='supplementary_suction',source_combination=copy.deepcopy(case),
                         limit_mm=table_a1_limit(result['input_data']['L_mm'],CRITERIA[1])['limit_mm']))
    else:rows.append(dict(id='A1_F_CHARACTERISTIC_SOURCE',kind='pending',reason='Ações características separadas de sucção não disponíveis; totais diretos não são decompostos.',limit_mm=None))
    return rows


def _dimensions(data):
    if 'ue_catalog_reference' in data:
        from .ue_catalog_reference import validate
        n=validate(data)['nominal_identity'];return dict(n['dimensions_mm'],ri_mm=n['inner_radius_mm'])
    # Frozen own-Ue family currently has ri=t by its independently pinned file,
    # not because a profile label happens to look like a catalogue section.
    from .torsion_study import PINS
    from pathlib import Path
    import hashlib,json
    t=data['properties']['t'];path=Path(__file__).with_name('data')/'torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINS[t]:raise ValueError('Fonte geométrica de serviço divergente.')
    d=json.loads(raw)['geometry_external_mm']
    return dict(h=d['h'],bf=d['b'],lip=d['lip'],t=d['t'],ri_mm=d['ri'])


def _base(result,c,missing=()):
    inventory=_inventory(result,c)
    return dict(schema=SCHEMA,configuration=copy.deepcopy(c),source_input_fingerprint=result.get('input_fingerprint'),
        source_load_bundle_sha256=digest(result.get('load_bundle')),scope=SCOPE,
        inventory=inventory,records=[dict(id=r['id'],kind=r['kind'],status='pending',reason='; '.join(missing) or 'Campo ainda não consumido.',
            comparison=None,source_dense_sha256=None,supplementary_summary=None) for r in inventory],missing=list(missing),
        source_matrix_changed=False,**{k:False for k in FALSE_FLAGS})


def _supplementary(result,item,section):
    """Exactly one new characteristic wind-only solve; PP/CP stay absent."""
    from .torsion_vlasov.vlasov import solve_member
    ev=result['torsion_evidence'];combo=item['source_combination'];vector=combo['q_vector']
    line=ev.get('load_lines',{}).get('V_Cima')
    if not isinstance(line,dict) or not isinstance(line.get('xy_mm'),list) or not line.get('origin'):
        raise ValueError('Linha/origem da sucção característica ausente; não substituída por CG.')
    data=result['input_data']
    analysis=solve_member(section=section,length_mm=data['L_mm'],E_MPa=data['properties']['E_MPa'],
        G_MPa=data['properties']['G_MPa'],actions=[dict(name='V_Cima',kind='uniform',
            q_xy_N_mm=[vector['parallel'],-vector['normal']],couple_N=0.,
            application_xy_mm=copy.deepcopy(line['xy_mm']),origin=line['origin'])],supports=ev['supports'],
        combination_id=item['id'],limit_state='ELS',member_id='PURLIN',elements_per_interval=32,
        action_accounting_origin='NBR14762 Tabela A.1 nota f: sucção característica isolada, sem PP/CP; matriz fornecida preservada')
    return analysis


def attach_dense(result,section):
    c=configuration(result['input_data'])
    if not active_model(result['input_data'],c):return result
    out=copy.deepcopy(result);missing=missing_configuration(c);ev=_base(out,c,missing);out[FIELD]=ev
    if missing:return out
    if result.get('torsion_evidence',{}).get('schema')!='purlin_torsion_batch_evidence_v1':
        ev['missing']=['Campo denso Vlasov ausente; resumo histórico não é recalculado.'];return out
    try:
        from .torsion_study import section_for
        if section!=section_for(result['input_data']):raise ValueError('Contorno integral de serviço não corresponde à referência própria selecionada.')
        dimensions=_dimensions(result['input_data'])
    except (ValueError,TypeError,KeyError,OSError) as exc:ev['missing']=[str(exc)];return out
    ev['dimensions']=dimensions
    source=result['torsion_evidence']['records'];ev['records']=[]
    for item in ev['inventory']:
        row=dict(id=item['id'],kind=item['kind'],status='pending',reason=None,comparison=None,
                 source_dense_sha256=None,supplementary_summary=None)
        ev['records'].append(row)
        if item['kind']=='pending':row['reason']=item['reason'];continue
        if item['kind']=='zero_characteristic_wind':
            row.update(status='not_applicable',reason='Vetor característico de sucção explicitamente nulo nas duas componentes. Dispensa somente este caso.');continue
        try:
            if item['kind']=='supplementary_suction':
                analysis=_supplementary(result,item,section)
                from .torsion_vlasov.adapter import summarize_torsion_evidence
                row['supplementary_summary']=summarize_torsion_evidence(dict(schema='purlin_torsion_batch_evidence_v1',
                    records=[dict(combination_id=item['id'],limit_state='ELS',analysis=analysis)]))['records'][0]
            else:
                matches=[r for r in source if (r['combination_id'],r['limit_state'])==(item['id'],'ELS')]
                if len(matches)!=1 or not isinstance(matches[0].get('analysis'),dict):raise ValueError('Uma demanda de serviço íntegra é necessária por combinação.')
                analysis=matches[0]['analysis']
            if analysis['section']!=section:raise ValueError('Seção de serviço e fonte torsional divergentes.')
            row['source_dense']=copy.deepcopy(analysis)
            row['source_dense_sha256']=digest(analysis)
            row['comparison']=mechanics.calculate(analysis,dimensions,result['input_data']['properties']['fy_MPa'],c,item['limit_mm'])
            row['status']='computed_linear_comparison'
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:row['reason']=str(exc)
    return out


def finalize(result):
    c=configuration(result['input_data'])
    if not active_model(result['input_data'],c):return result
    out=copy.deepcopy(result)
    if FIELD not in out:out[FIELD]=_base(out,c,missing_configuration(c) or ['Demanda densa de serviço indisponível neste modelo.'])
    ev=out[FIELD];ev['source_torsion_snapshot_sha256']=digest(out.get('torsion_evidence'))
    source=out.get('torsion_evidence',{}).get('records',[])
    for row in ev['records']:
        matches=[r for r in source if (r.get('combination_id'),r.get('limit_state'))==(row['id'],'ELS')]
        row['source_summary_sha256']=digest(matches[0]) if len(matches)==1 and row['kind']=='existing' else None
    ev['computed_cases']=sum(r['status']=='computed_linear_comparison' for r in ev['records'])
    ev['pending_cases']=sum(r['status']=='pending' for r in ev['records'])
    ev['all_requested_linear_comparisons_satisfied']=bool(ev['records']) and not ev['missing'] and not ev['pending_cases'] and any(
        r['status']=='computed_linear_comparison' for r in ev['records']) and all(
        r['status']=='not_applicable' or r['comparison']['criterion_status']=='within_declared_linear_model' for r in ev['records'])
    ev['snapshot_sha256']=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    return out


# Cache arithmetic certification, never solver output. Every material input,
# polynomial, comparison and compact source participates in the token.
_REPLAY_CACHE=set()


def _replay_saved(row,summary,dimensions,fy,c,limit):
    dense=row.get('source_dense')
    if not isinstance(dense,dict) or digest(dense)!=row.get('source_dense_sha256'):
        raise ValueError('Certificado de campo denso ausente ou alterado.')
    token=digest([dense,summary,dimensions,fy,c,limit,row['comparison']])
    if token in _REPLAY_CACHE:return
    from .en_ue125_300_source_replay import validate
    from .torsion_vlasov.adapter import summarize_torsion_evidence
    # Rebuild element polynomials and K*u-f from SAVED nodal values; no solve.
    validate(dense)
    import numpy as np
    L=dense['length_mm'];loads=dense['loads']
    q=np.array([math.fsum(a['q_xy_N_mm'][j] for a in loads if a['kind']=='uniform') for j in (0,1)])
    left=-q*L/2;right=-q*L/2
    for load in loads:
        if load['kind']=='point':
            force=np.array(load['force_xy_N']);left-=force*(L-load['s_mm'])/L;right-=force*load['s_mm']/L
    if left.tolist()!=dense['support_reactions']['left_force_xy_N'] or right.tolist()!=dense['support_reactions']['right_force_xy_N']:
        raise ValueError('Reações de flexão de serviço divergentes das ações salvas.')
    compact=summarize_torsion_evidence(dict(schema='purlin_torsion_batch_evidence_v1',
        records=[dict(analysis=dense)]))['records'][0]['analysis']
    if compact!=summary['analysis']:
        raise ValueError('Polinômios de serviço não reproduzem a fonte compacta salva.')
    expected=mechanics.calculate(dense,dimensions,fy,c,limit,schema=row['comparison']['schema'])
    if row['comparison']!=expected:
        raise ValueError('Crivo/envelope salvo não reproduz a aritmética do campo concomitante.')
    if len(_REPLAY_CACHE)>=128:_REPLAY_CACHE.clear()
    _REPLAY_CACHE.add(token)


def saved(result):
    ev=result.get(FIELD)
    if ev is None:return None
    c=configuration(result['input_data'])
    from .application import fingerprint
    if (not isinstance(ev,dict) or ev.get('schema')!=SCHEMA or c is None or not c['enabled']
        or not active_model(result['input_data'],c)
        or ev.get('configuration')!=c or ev.get('scope')!=SCOPE
        or ev.get('source_input_fingerprint')!=result.get('input_fingerprint')
        or fingerprint(result['input_data'])!=result.get('input_fingerprint')
        or ev.get('source_load_bundle_sha256')!=digest(result.get('load_bundle'))
        or ev.get('source_torsion_snapshot_sha256')!=digest(result.get('torsion_evidence'))
        or ev.get('snapshot_sha256')!=digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
        or ev.get('source_matrix_changed') is not False or any(ev.get(k) is not False for k in FALSE_FLAGS)):
        raise ValueError('Componente de serviço salva alterada ou de outra fonte; nenhum recálculo executado.')
    if ev['inventory']!=_inventory(result,c):raise ValueError('Inventário independente de serviço divergente.')
    if [r['id'] for r in ev['records']]!=[r['id'] for r in ev['inventory']]:raise ValueError('Casos de serviço ausentes/duplicados.')
    source=result.get('torsion_evidence',{}).get('records',[])
    if ev['computed_cases']:
        if missing_configuration(c):raise ValueError('Comparação exige escolha completa do modelo/ponto/critério.')
        props=result['input_data']['properties']
        if ev.get('dimensions')!=_dimensions(result['input_data']):
            raise ValueError('Dimensões do crivo não correspondem à seção salva.')
    for row,item in zip(ev['records'],ev['inventory']):
        if row['kind']!=item['kind'] or row['status'] not in ('pending','not_applicable','computed_linear_comparison'):raise ValueError('Estado de serviço desconhecido.')
        if row['status']=='not_applicable' and item['kind']!='zero_characteristic_wind':raise ValueError('Dispensa de serviço não demonstrada.')
        if item['kind']=='existing':
            matches=[r for r in source if (r.get('combination_id'),r.get('limit_state'))==(row['id'],'ELS')]
            expected=digest(matches[0]) if len(matches)==1 else None
            if row.get('source_summary_sha256')!=expected:raise ValueError('Campo compacto de serviço divergente.')
        check=row['comparison']
        if row['status']!='computed_linear_comparison':
            if check is not None:raise ValueError('Resultado não calculado não pode apresentar índice.')
            continue
        if not isinstance(check,dict) or any(check.get(k) is not False for k in FALSE_FLAGS):raise ValueError('Comparação linear não é aprovação física.')
        if (check.get('schema') not in mechanics.SCHEMAS or check.get('combination_id')!=row['id'] or check.get('limit_state')!='ELS'
            or check.get('limit_mm')!=item['limit_mm'] or check.get('source_point_xy_from_CG_mm')!=c['point_xy_from_CG_mm']
            or check.get('source_projection_xy')!=c['projection_xy']):raise ValueError('Critério ou ponto de serviço divergente.')
        summary=row['supplementary_summary'] if row['kind']=='supplementary_suction' else next((r for r in source if (r.get('combination_id'),r.get('limit_state'))==(row['id'],'ELS')),None)
        a=summary.get('analysis') if isinstance(summary,dict) else None
        if (not isinstance(a,dict) or a.get('combination_id')!=row['id'] or a.get('limit_state')!='ELS'
            or a.get('length_mm')!=result['input_data']['L_mm']
            or check.get('source_length_mm')!=a['length_mm']
            or check.get('source_section_sha256')!=a['section']['content_sha256']
            or check.get('stored_linear_twist_max_rad')!=abs(a['max_abs_phi']['phi_rad'])
            or check.get('rotation_screening_warning') is not a.get('small_rotation_warning')):
            raise ValueError('Comparação de serviço não corresponde à análise compacta salva.')
        if row['kind']=='supplementary_suction':
            line=result['torsion_evidence'].get('load_lines',{}).get('V_Cima',{})
            vector=item['source_combination']['q_vector'];loads=a.get('loads',[])
            if (len(loads)!=1 or loads[0].get('name')!='V_Cima' or loads[0].get('kind')!='uniform'
                or loads[0].get('q_xy_N_mm')!=[vector['parallel'],-vector['normal']]
                or loads[0].get('application_xy_mm')!=line.get('xy_mm')
                or loads[0].get('origin')!=line.get('origin') or loads[0].get('couple_N')!=0.
                or a.get('support_hypotheses')!=result['torsion_evidence'].get('supports')):
                raise ValueError('Sucção característica não pode incluir PP/CP nem outra linha/vínculo.')
        from .torsion_study import section_for
        if row.get('source_dense',{}).get('section')!=section_for(result['input_data']):
            raise ValueError('Contorno integral salvo não corresponde à referência própria selecionada.')
        _replay_saved(row,summary,ev['dimensions'],result['input_data']['properties']['fy_MPa'],c,item['limit_mm'])
        screen=check['gross_screen'];walls=screen['walls']
        props=result['input_data']['properties'];d=ev['dimensions']
        if (screen.get('E_MPa')!=a.get('E_MPa') or a.get('E_MPa')!=props['E_MPa']
            or a.get('G_MPa')!=props['G_MPa']
            or screen.get('fy_MPa')!=props['fy_MPa']):raise ValueError('Material/rigidez de serviço divergentes.')
        expected_names=('bottom_lip','bottom_flange','web','top_flange','top_lip')
        expected_widths=(d['lip']-d['ri_mm']-d['t'],d['bf']-2*d['ri_mm']-2*d['t'],
                         d['h']-2*d['ri_mm']-2*d['t'],d['bf']-2*d['ri_mm']-2*d['t'],d['lip']-d['ri_mm']-d['t'])
        from .torsion_vlasov.intervals import Interval as I
        for wall,name,width,k in zip(walls,expected_names,expected_widths,(.43,.43,4.,.43,.43)):
            lower=float(((I(.673)*.95).square()*k*screen['E_MPa']*(I(d['t'])/width).square()).lo)
            if wall.get('name')!=name or wall.get('width_mm')!=width or wall.get('k')!=k or wall.get('integral_limit_lower_MPa')!=lower:
                raise ValueError('Aritmética do crivo MLE salvo divergente.')
        if len(walls)!=5 or len({r['name'] for r in walls})!=5:raise ValueError('Crivo de cinco paredes incompleto.')
        for wall in walls:
            base=wall['compression_upper_MPa']<=wall['integral_limit_lower_MPa']
            if check['schema'] in (mechanics.STIFFENED_SCHEMA,mechanics.SCHEMA) and 'flange' in wall['name']:
                if wall.get('uniform_unstiffened_sufficient') is not base:
                    raise ValueError('Crivo AL de referência salvo inconsistente.')
                base=bool(base or wall['edge_stiffener']['sufficient'])
            if check['schema']==mechanics.SCHEMA and wall['name']=='web':
                if wall.get('uniform_k4_sufficient') is not base:
                    raise ValueError('Crivo AA uniforme de referência salvo inconsistente.')
                base=bool(base or wall['affine_web']['sufficient'])
            if wall['sufficient'] is not base:raise ValueError('Crivo local salvo inconsistente.')
        sufficient=bool(all(w['sufficient'] for w in walls) and screen['von_mises_upper_MPa']<=screen['fy_MPa'])
        if screen['gross_local_normal_sufficient'] is not sufficient:raise ValueError('Crivo conjunto salvo divergente.')
        env=check['envelope'];lo=env['abs_displacement_lower_mm'];hi=env['abs_displacement_upper_mm']
        if not 0<=lo<=hi or not all(math.isfinite(v) for v in (lo,hi)):raise ValueError('Limites do deslocamento inválidos.')
        expected_lo=mechanics._outward(mechanics.F(lo)/mechanics.F(check['limit_mm']),False)
        expected_hi=mechanics._outward(mechanics.F(hi)/mechanics.F(check['limit_mm']),True)
        if check['diagnostic_ratio_lower']!=expected_lo or check['diagnostic_ratio_upper']!=expected_hi:raise ValueError('Razão de serviço salva divergente.')
        if check['index_lower']!=(expected_lo if sufficient else None) or check['index_upper']!=(expected_hi if sufficient else None):raise ValueError('Índice salvo ignora crivo de rigidez.')
        status=('within_declared_linear_model' if expected_hi<=1 else 'above_declared_linear_model' if expected_lo>1 else 'numerical_boundary_inconclusive') if sufficient else 'gross_MLE_sufficient_condition_inconclusive'
        if check['criterion_status']!=status:raise ValueError('Conclusão de serviço altera o alcance do campo linear.')
    computed=sum(r['status']=='computed_linear_comparison' for r in ev['records']);pending=sum(r['status']=='pending' for r in ev['records'])
    satisfied=bool(ev['records']) and not ev['missing'] and not pending and computed>0 and all(
        r['status']=='not_applicable' or r['comparison']['criterion_status']=='within_declared_linear_model' for r in ev['records'])
    if ev['computed_cases']!=computed or ev['pending_cases']!=pending or ev['all_requested_linear_comparisons_satisfied'] is not satisfied:raise ValueError('Resumo de serviço incompleto.')
    return copy.deepcopy(ev)
