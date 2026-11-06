"""Read-only support demands from saved isolated or current 7DOF analyses.

Forces act ON the member. Isolated reactions(q,P) use the resisting-load
convention and are negated; 7DOF forces are rotated R01 y=-global Z. No contact,
compression face, stiffener, weld, effective restraint or capacity is inferred.
"""
import copy
import math
from ..three_girt_warping.application import fingerprint

SCHEMA = 'support_web_saved_sources_v1'
LEVELS = ('upper', 'middle', 'lower')
DOFS = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz', 'psi')


def _number(value, name):
    try:valid=type(value) in (int,float) and math.isfinite(value)
    except (ValueError,OverflowError):valid=False
    if not valid:
        raise ValueError('Número finito requerido: '+name)
    return float(value)


def _add(*vectors):
    return [math.fsum(v[i] for v in vectors) for i in range(len(vectors[0]))]


def _cross(a,b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _action(force, connection):
    return [*force, *_cross(connection['arm_mm'],force), -force[0]*connection['omega_mm2']]


def _end_action(s,left):
    sign=-1. if left else 1.
    return [sign*s['N_N'],-sign*s['Vy_N'],-sign*s['Vz_N'],
            sign*s['T_equilibrium_CG_Nmm'],sign*s['My_strong_Nmm'],
            sign*s['Mz_weak_Nmm'],-sign*s['B_equilibrium_Nmm2']]


def _section(data, selected=None):
    p=data['properties']
    family=selected['family'] if selected else 'Ue'
    if family not in ('U','Ue'):
        raise ValueError('Seção fora das famílias U/Ue desta extração')
    section=dict(family=family,H=p.get('h'),t=p.get('t'),ri=p.get('ri_mm'),fy=p.get('fy_MPa'))
    # Missing radius/material is retained as missing, not inferred; mechanics
    # can still process the web-connection exception without Annex D geometry.
    for key,value in section.items():
        if key!='family' and value is not None:_number(value,key)
    if selected:
        from ..core.selecao import select
        nominal=select(data['catalog_index'])
        if family!=nominal['family']:
            raise ValueError('Família salva difere da seção selecionada na entrada')
        for key in ('h','bf','lip','t'):
            if selected['fields'][key]['value']!=p[key] or p[key]!=nominal['fields'][key]['value']:
                raise ValueError('Geometria salva difere da seção selecionada: '+key)
        for a,b in (('H','h'),('t','t'),('ri','ri_mm'),('fy','fy_MPa')):
            if selected['fields'][b]['value']!=section[a]:
                raise ValueError('Geometria/material salvos diferem da entrada: '+b)
    return section


def _legacy(result, containers, L):
    """Only an explicitly saved web route bound to this isolated input/span."""
    d=result['input_data']; origin=d.get('support_origin'); details={}
    for side in ('left','right'):
        if not isinstance(origin,str) or not origin.strip():continue
        if d.get(side+'_web') is not True:continue
        records=[e.get('NBR_branches',{}).get('supports',{}).get(side,{}) for e in containers]
        if not records or not all(r.get('status')=='stiffener_exception_9_5_1'
                and r.get('provenance')==origin and r.get('connection_design_checked') is False
                and r.get('support_contact_assumed') is False for r in records):continue
        if result['schema']=='NBR14762_one_span_v1':
            spec=result['input_snapshot']; route=spec.get('introduction',{}).get(side,{})
            if spec.get('L_mm')!=L or route!={'route':'web_connection','origin':origin}:continue
        details[side]=dict(route='web_connection',origin=origin,
            binding=dict(source_input_fingerprint=result['input_fingerprint'],L_mm=L,
                         support_id=side,member_application=d.get('member_application','purlin'),
                         declaration_source='saved_left_right_web_route'),
            scope='Declaração legada de alma ligada neste vão; não informa ausência de contato pela mesa nem dimensiona a ligação.',
            connection_design_checked=False)
    # The opt-in contact contract independently declares BOTH end reactions
    # through connected webs, without flange contact. Its binding to this span,
    # section and current case remains valid even when external P equals zero.
    # Only its end-web declaration is reused, never its point capacity or c.
    from ..point_contact import configuration, basis_matches
    try:cfg=configuration(d)
    except (ValueError,TypeError,KeyError):cfg=None
    if (cfg is not None and cfg['enabled'] is True and basis_matches(d,cfg)
            and cfg['origin'].strip()
            and cfg['declarations']['end_reactions_through_webs'] is True
            and cfg['declarations']['no_end_flange_contact'] is True):
        for side in ('left','right'):
            details[side]=dict(route='web_connection',origin=cfg['origin'],
                binding=dict(source_input_fingerprint=result['input_fingerprint'],L_mm=L,
                    support_id=side,member_application=d.get('member_application','purlin'),
                    declaration_source='point_contact',contract_schema=cfg['schema'],
                    contract_fingerprint=fingerprint(cfg),basis=copy.deepcopy(cfg['basis'])),
                scope='Somente declaração vinculada das reações de extremidade pelas almas, sem contato nas mesas; capacidade de P e comprimento c não reutilizados.',
                connection_design_checked=False)
    return details


def _isolated(result):
    from ..application import fingerprint as input_digest
    from ..core.anexo_d import reactions
    from ..batch import area_bundle
    from ..three_girt_application import enabled
    d=result['input_data']; L=_number(d['L_mm'],'L')
    if L<=0 or result.get('input_fingerprint')!=input_digest(d):
        raise ValueError('Entrada isolada ausente, alterada ou sem vínculo de fingerprint')
    if enabled(d):raise ValueError('Não converter sistema 3D em vão isolado')
    batch=result['schema']=='tercas_batch_results_v1'
    selected=result['common_input_snapshot' if batch else 'input_snapshot']['selected_section']
    section=_section(d,selected)
    if batch:
        bundle=area_bundle(d)
        if result.get('load_bundle')!=bundle:
            raise ValueError('Lote salvo difere das combinações reconstruídas das entradas')
        cases=result.get('cases')
        if not isinstance(cases,list) or [c.get('combination') for c in cases]!=bundle['combinations']:
            raise ValueError('Cobertura/identidade das combinações isoladas alterada')
        cases=[(c['combination'],c['evidence'],c['evidence'].get('inclination',{}))
               for c in cases if c['combination']['limit_state']=='ELU']
    else:
        spec=result['input_snapshot']
        from ..direct_self_weight import calculation_inputs
        d=calculation_inputs(d)
        expected=dict(q_Nmm=d['q_uls'],P_N=d['P_uls'],x_mm=d['x_uls'],origin=d['actions_origin'])
        if d.get('load_mode')!='direct' or spec.get('L_mm')!=L or spec.get('ULS')!=expected:
            raise ValueError('Ações ou vão do resultado direto diferem da entrada salva')
        c=dict(id='DIRECT_ELU',limit_state='ELU',x_mm=d['x_uls'],
               q_vector=dict(normal=d['q_uls'],parallel=d.get('q_parallel_uls',0.)),
               P_vector=dict(normal=d['P_uls'],parallel=d.get('P_parallel_uls',0.)),
               origin=d['actions_origin'])
        cases=[(c,result,result.get('inclination_evidence',{}).get('ELU',{}))]
    supports=[]
    for c,e,ev in cases:
        q=c['q_vector']; p=c['P_vector']; x=_number(c['x_mm'],'posição P')
        for axis in ('normal','parallel'):
            _number(q[axis],'q '+axis);_number(p[axis],'P '+axis)
        if ev.get('q_vector')!=q or ev.get('P_vector')!=p:
            raise ValueError('Vetores da evidência isolada diferem da combinação salva')
        rn=reactions(L,q['normal'],p['normal'],x); rp=reactions(L,q['parallel'],p['parallel'],x)
        mathematical=c.get('point_position')=='support_limit'
        if mathematical and x!=0.:raise ValueError('Limite matemático exige x→0+; não ajustar posição')
        if not mathematical and not 0<x<L:raise ValueError('Posição finita deve estar dentro do vão')
        convention=('Força sobre a barra; +normal/+paralelo seguem os eixos das ações locais da interface. '
                    'normal_N e parallel_N são o negativo das reações escalares legadas. '+ev.get('convention',''))
        for i,side in enumerate(('left','right')):
            end=0. if i==0 else L
            states=[copy.deepcopy(s) for s in ev.get('states',[]) if s.get('x_mm')==end]
            if not states:raise ValueError('Estado de extremidade isolada ausente da evidência salva')
            for s in states:
                for axis,rr in (('normal',rn),('parallel',rp)):
                    for key,value in (('Rleft_N',rr[0]),('Rright_N',rr[1])):
                        if not math.isclose(_number(s[axis][key],key),value,rel_tol=2e-10,abs_tol=1e-7):
                            raise ValueError('Reação salva difere das ações isoladas: '+key)
            supports.append(dict(support_id=side,label='Apoio '+('esquerdo' if i==0 else 'direito'),
                combination_id=c['id'],limit_state='ELU',member='isolated',x_mm=end,
                normal_N=-rn[i],parallel_N=-rp[i],moment_strong_Nmm=0.,
                source_axis_convention=convention,
                trace=dict(combination=copy.deepcopy(c),L_mm=L,
                    q_vector=copy.deepcopy(q),P_vector=copy.deepcopy(p),external_P_zero=all(v==0 for v in p.values()),
                    reaction_load_convention_N=dict(normal=rn[i],parallel=rp[i]),
                    analytical_method='q L/2 + P participation; exact prescribed a→0+ retained, not finite contact' if mathematical else 'q L/2 + P participation, saved finite position',
                    mathematical_point_limit=mathematical,finite_contact_position_inferred=False,
                    concomitant_states=states,source_input_fingerprint=result['input_fingerprint'])))
    return dict(source_kind='isolated_batch' if batch else 'isolated_direct',section=section,supports=supports,
                legacy_details=_legacy(result,[e for _,e,_ in cases],L),intermediate_stations=[],
                ELS_combinations_excluded=sum(c['combination']['limit_state']=='ELS' for c in result.get('cases',[])))


def _network(result):
    from ..three_girt_axial.application import _validate, reference_configuration
    from ..three_girt_warping.application import recover_exported_state
    from ..three_girt_frame import topology
    _validate(result,reference_configuration(result))
    if result['configuration']['section_orientation']!='mouth_down_Y_minus_x_Z_minus_y':
        raise ValueError('Orientação atual 7DOF não reconhecida')
    out=dict(source_kind='current_7DOF',section=_section(result['input_data']),
             supports=[],legacy_details={},intermediate_stations=[],
             ELS_combinations_excluded=sum(c['combination']['limit_state']=='ELS' for c in result['cases']))
    for case in result['cases']:
        if case['combination']['limit_state']!='ELU':continue
        m=case['model']; inp=m['inputs']; L=inp['L_mm']; xs=[0.,*inp['attachment_x_mm'],L]; cols=len(xs)
        nodes=m['nodes']; fixed={(v['node'],v['dof']) for v in m['fixed_dofs']}
        expected={(r*cols+c,d) for r in range(3) for c in (0,cols-1) for d in ('ux','uy','uz','rx')}
        if inp['warping_end_condition']=='restrained_assumed':
            expected|={(r*cols+c,'psi') for r in range(3) for c in (0,cols-1)}
        if fixed!=expected or len(nodes)!=3*cols or m['dofs']!=21*cols:
            raise ValueError('Vínculos/nós não correspondem aos seis apoios da demanda')
        contributions={i:[] for i in range(len(nodes))}; bars={b['id']:b for b in m['bars']}
        links=topology(cols-2,inp['include_green'])
        if set(bars)!={b[0] for b in links}:raise ValueError('Barras salvas diferem da topologia')
        for name,a,b,color in links:
            bar=bars[name]; ca,cb=bar['connections']
            delta=[nodes[b]['xyz_CG_mm'][i]+cb['arm_mm'][i]-nodes[a]['xyz_CG_mm'][i]-ca['arm_mm'][i] for i in range(3)]
            length=math.sqrt(math.fsum(v*v for v in delta))
            if not length>0:raise ValueError('Comprimento de ligação inválido')
            for end,node,con in ((0,a,ca),(1,b,cb)):
                force=[(1 if end==0 else -1)*bar['axial_tension_N']*v/length for v in delta]
                weight=[0.,-bar['self_weight_N']/2,0.]
                contributions[node].append(dict(bar_id=name,end=end,connection=copy.deepcopy(con),
                    axial_tension_N=bar['axial_tension_N'],force_on_girt_global_N=force,
                    self_weight_half_global_N=weight,generalized_action=_add(_action(force,con),_action(weight,con))))
        records=[]; errors=[]; free_residuals=[]; force_scale=1.
        for index,node in enumerate(nodes):
            r,c=divmod(index,cols); member=LEVELS[r]; x=xs[c]; y=(inp['upper_gap_mm'],0.,-inp['lower_gap_mm'])[r]
            if node['id']!=index or node['xyz_CG_mm']!=[x,y,0.]:raise ValueError('Identidade/coordenada nodal inconsistente')
            raw=node['support_reactions']
            if len(raw)!=7:raise ValueError('Sete componentes de reação requeridas')
            for v in raw:_number(v,'reação nodal')
            reaction=[v if (index,d) in fixed else 0. for d,v in zip(DOFS,raw)]
            free_residuals.append([abs(v-reaction[j]) for j,v in enumerate(raw)])
            net=_add(reaction,*[a['generalized_action'] for a in contributions[index]])
            states=[]; ends=[]
            for beam in m['beams']:
                if beam['girt']!=member or x not in (beam['x_start_mm'],beam['x_end_mm']):continue
                state=recover_exported_state(m,beam,x)
                states.append(state);ends.append(_end_action(state,x==beam['x_start_mm']))
            if len(states)!=(1 if c in (0,cols-1) else 2):raise ValueError('Lados concomitantes não cobrem o nó')
            beam_action=_add(*ends)
            force_scale=max(force_scale,*map(abs,beam_action[:3]),*map(abs,net[:3]))
            errors.append([abs(a-b) for a,b in zip(beam_action,net)])
            trace=dict(source_demand_content_sha256=m['demand_content_sha256'],node_id=index,
                source_input_fingerprint=result['input_fingerprint'],L_mm=L,
                combination=copy.deepcopy(case['combination']),external_P_zero=not any(case['combination'].get('P_vector',{}).values()),
                external_support_reaction_global_generalized=reaction,nodal_residual_raw=copy.deepcopy(raw),
                attached_bar_end_actions=contributions[index],net_joint_action_global_generalized=net,
                own_girt_end_action_global_generalized=beam_action,concomitant_states=states,
                force_used='own_girt_end_action; support and bar contributions are balance trace only, never added twice',
                no_physical_contact_inferred=True)
            record=dict(member=member,x_mm=x,combination_id=case['combination']['id'],limit_state='ELU',
                normal_N=-beam_action[2],parallel_N=-beam_action[1],
                moment_strong_Nmm=-states[0]['My_strong_Nmm'],
                source_axis_convention='Força sobre a travessa: +normal = +y_R01 = −Z_global; +paralelo = +x_R01 = −Y_global. normal_N=−Fz da extremidade da própria travessa.',trace=trace)
            if c in (0,cols-1):
                side='left' if c==0 else 'right';record.update(support_id=member+'_'+side,label=member+' / '+side)
                records.append(record)
            else:
                record.update(station_id=member+'_attachment_'+str(c),is_external_support=False)
                out['intermediate_stations'].append(record)
        scaled=max(e/s for err in errors+free_residuals for e,s in zip(err,[force_scale]*3+[force_scale*L]*3+[force_scale*L*L]))
        if scaled>1e-8:raise ValueError('Equilíbrio apoio/barras/travessa salvo inconsistente; sem solver de correção')
        for record in records:record['trace']['nodal_balance_max_scaled']=scaled
        out['supports'].extend(records)
    return out


def extract(result):
    """Return validated, signed ELU support demands; never mutate/re-solve input.

    Stable IDs: left/right or {upper,middle,lower}_{left,right}. Missing physical
    geometry remains absent. legacy_details are only existing isolated web-route
    declarations, not automatically transferable to any 7DOF support.
    """
    if not isinstance(result,dict):raise ValueError('Resultado salvo requerido')
    schema=result.get('schema')
    if schema=='three_girt_current_vlasov_demand_v1':
        out=_network(result)  # Validate the ENTIRE mechanical network before selecting criteria.
        from ..three_girt_scope import central, NOTICE
        if central(result):
            out['supports']=[r for r in out['supports'] if r['member']=='middle']
            out['verification_scope']=copy.deepcopy(result['verification_scope'])
            out['verification_scope_notice']=NOTICE
    elif schema in ('NBR14762_one_span_v1','tercas_batch_results_v1'):out=_isolated(result)
    else:raise ValueError('Fonte de reações não suportada; sem conversão automática')
    out.update(schema=SCHEMA,source_input_fingerprint=result['input_fingerprint'],
               no_network_solve=True,physical_conditions_verified=False,connection_design_checked=False,
               scope='Demanda local normal nos apoios ELU, com sinal e ações concomitantes; sem inferir contato, transmitir declaração isolada ao 3D ou aprovar ligações. Estações intermediárias são rastreio separado, não apoios externos.')
    if out.get('verification_scope_notice'):out['scope']+=' '+out['verification_scope_notice']
    out['source_fingerprint']=fingerprint(out)
    return out
