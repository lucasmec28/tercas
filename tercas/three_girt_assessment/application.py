"""Global inventory for the current 7DOF snapshot, with separate method scopes.

No solver, section source lookup or resistance formula is called. EN section
checks may close their own stress criteria, not member stability or physical
service applicability. NBR reference/G8.1/isolated deflection stay auxiliary.
"""
import copy
import importlib
import math
from ..three_girt_warping.application import fingerprint,SCHEMA as DEMAND_SCHEMA,LEVELS
from ..global_verification import check,aggregate,axial_interaction_record

SCHEMA='three_girt_global_inventory_v1'
CENTRAL_SCHEMA='three_girt_middle_inventory_v2'
from ..three_girt_scope import members, central, NOTICE, local_guard
SOURCE='Inventário do modelo Vlasov atual; componentes e normas mantidos separados'
EXCLUSIONS=['Resistência/dimensionamento dos cordões de solda, parafusos, tirantes, cantoneiras e ancoragens.',
    'Certificação de condições de campo; o cálculo usa hipóteses e dados declarados.',
    'A alternativa de vigas isoladas não substitui a resposta nem o ELS da rede.']


def _finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def _text(x):return isinstance(x,str) and bool(x.strip())


def item(key,state='MODEL',*,source=SOURCE,reason='',index=None,qualified=False,excluded=False,trace=None,verdict=None):
    return check(key,limit_state=state,source=source,reason=reason,index=index,
        qualified=qualified,not_applicable=excluded,trace=trace,verdict=verdict)


def _group(key,title,records,scope):
    result=aggregate(list(dict.fromkeys(r['id'] for r in records)),records,inventory_qualified=bool(records))
    return dict(id=key,title=title,scope=scope,**{k:result[k] for k in
        ('status','counts','checks','complete','failed_ids','pending_ids','maximum_available_check')},
        whole_member_approved=False,maximum_is_global_utilization=False)



def _load_binding(d,case):
    """Check saved load bookkeeping, not generate combinations or solve them."""
    data=d['input_data'];g=d['configuration']['three_girt'];c=case['combination'];bundle=d.get('load_bundle')
    vector=c['q_vector'];normal=vector['normal'];parallel=vector['parallel']
    if not all(_finite(v) for v in (normal,parallel)):raise ValueError('Invalid saved load vector')
    if data.get('load_mode')=='area':
        coeff=c['coefficients'];vectors=bundle['case_vectors_N_mm']
        for axis in ('normal','parallel'):
            value=sum(v*vectors[k][axis] for k,v in coeff.items())
            if not math.isclose(value,vector[axis],rel_tol=2e-13,abs_tol=1e-13):raise ValueError('Saved combination coefficients/vector differ')
        factor=coeff.get('PP',0.);pp=factor*vectors['PP']['parallel']
    elif data.get('load_mode')=='direct':
        state={'ELU':'uls','ELS':'sls'}[c['limit_state']]
        from ..direct_self_weight import calculation_inputs,evidence as pp_evidence
        pp_trace=pp_evidence(data);effective=calculation_inputs(data)
        if normal!=effective['q_'+state] or parallel!=effective.get('q_parallel_'+state,0.):raise ValueError('Saved direct actions differ')
        pp=pp_trace['states'][state]['profile_PP_q_N_mm']['parallel'] if pp_trace else g['direct_pp_'+state+'_N_mm'];factor=g['direct_brace_factor_'+state] if g['brace_self_weight'] else 0.
    else:raise ValueError('Unknown saved loading mode')
    if case['combined_girt_PP_N_mm']!=pp or case['brace_weight_factor']!=factor or case['model']['inputs']['brace_weight_factor']!=factor:
        raise ValueError('Saved self-weight bookkeeping differs')
    from ..load_application_policy import active as ct_active
    ct=ct_active(data);section=case['model']['inputs']['section']
    ey=section['sc_y_mm'] if ct else g['load_y_from_CG_mm'];ez=section['sc_z_mm'] if ct else g['load_z_from_CG_mm']
    expected=[]
    for weight in (.5,1.,.5):
        y=-weight*(parallel-pp);z=-weight*normal
        expected.append(dict(q_y_N_mm=y-pp,q_z_N_mm=z,load_y_from_CG_mm=0.,load_z_from_CG_mm=0.,
            distributed_torque_CG_N=ey*z-ez*(y-pp) if ct else ey*z-ez*y,
            components=[dict(id='external',q_y_N_mm=y,q_z_N_mm=z,y_from_CG_mm=ey,z_from_CG_mm=ez),
                dict(id='girt_PP',q_y_N_mm=-pp,q_z_N_mm=0.,y_from_CG_mm=ey if ct else 0.,z_from_CG_mm=ez if ct else 0.)]))
    if case['loads']!=expected:raise ValueError('Saved combination differs from resolved girt loads')


def validate_demand(d):
    """Saved hashes, inventories and analytical fields, not fresh mechanics."""
    if not isinstance(d,dict):raise ValueError('Resultado deve ser um objeto.')
    members(d)
    if d.get('schema')!=DEMAND_SCHEMA or d.get('status')!='conditional_elastic_vlasov_demand':raise ValueError('Current solved 7DOF snapshot required')
    if d.get('input_fingerprint')!=fingerprint(dict(data=d['input_data'],config=d['configuration'])):raise ValueError('Demand inputs/configuration changed')
    if d.get('coverage_complete') is not True or not d.get('cases'):raise ValueError('Demand coverage incomplete')
    if any(d.get(k) is not False for k in ('physical_conditions_verified','resistance_qualified','ELS_qualified','whole_member_approved')):raise ValueError('Original demand scope was promoted')
    cfg=d['configuration'];g=cfg['three_girt'];L=d['input_data']['L_mm']
    from ..load_application_policy import active as ct_active
    required=('geometry_declared','axial_bars_declared','connections_declared')+(() if ct_active(d['input_data']) else ('load_line_declared',))
    if cfg.get('enabled') is not True or any(g.get(k) is not True for k in required):raise ValueError('Current model declarations missing')
    if not _finite(L) or L<=0:raise ValueError('Invalid physical span')
    bundle=d.get('load_bundle')
    expected=bundle.get('combinations',[]) if isinstance(bundle,dict) else [dict(id='DIRETO_ELU',limit_state='ELU'),dict(id='DIRETO_ELS',limit_state='ELS')]
    keys=[(c.get('id'),c.get('limit_state')) for c in expected]
    actual=[(c['combination'].get('id'),c['combination'].get('limit_state')) for c in d['cases']]
    if not keys or len(set(keys))!=len(keys) or keys!=actual:raise ValueError('Current combination inventory differs')
    if isinstance(bundle,dict) and [r['combination'] for r in d['cases']]!=expected:raise ValueError('Current combination definition differs')
    for case in d['cases']:
        m=case['model'];saved=m.get('demand_content_sha256')
        if saved!=fingerprint({k:v for k,v in m.items() if k!='demand_content_sha256'}):raise ValueError('Saved model changed')
        if (m.get('source_input_fingerprint')!=d['input_fingerprint'] or m.get('first_order') is not True
            or m.get('bilateral_bars') is not True or m.get('diagnostics',{}).get('passed') is not True):raise ValueError('Current demand checks missing')
        inp=m['inputs'];s=inp['section']
        from ..load_application_policy import FIELD as CT_FIELD
        if inp.get(CT_FIELD)!=d['input_data'].get(CT_FIELD):raise ValueError('Saved applied-load model differs')
        _load_binding(d,case)
        stations=([L*j/(g['tie_count']+1) for j in range(1,g['tie_count']+1)] if g['position_mode']=='uniform' else g['positions_mm'])
        if inp['attachment_x_mm']!=stations or len(stations)!=g['tie_count']:raise ValueError('Saved physical stations/configuration differ')
        spacing=d['input_data']['area_inputs']['spacing_m']*1000
        if inp['upper_gap_mm']!=spacing or inp['lower_gap_mm']!=spacing:raise ValueError('Saved physical spacing differs')
        if inp['connections']!=cfg['connections'] or any(inp[k]!=cfg[k] for k in ('warping_end_condition','warping_condition_origin')):
            raise ValueError('Saved connections or boundary conditions differ')
        if any(inp[k]!=g[k] for k in ('blue','green','brace_self_weight')):raise ValueError('Saved axial bar inputs differ')
        if inp['L_mm']!=L or inp['loads']!=case['loads'] or len(case['loads'])!=3 or inp.get('nodal_loads')!=[]:raise ValueError('Saved model/load contract differs')
        if s['sectorial_section_id']!=d['source_geometry']['content_sha256']:raise ValueError('Saved section identity differs')
        if any(v!=0 for v in case['combination'].get('P_vector',{}).values()):raise ValueError('Concentrated action outside current adapter')
        ids=set()
        for level in LEVELS:
            beams=sorted((b for b in m['beams'] if b['girt']==level),key=lambda b:b['x_start_mm'])
            cuts=[0.]+inp['attachment_x_mm']+[L]
            if [(b['x_start_mm'],b['x_end_mm']) for b in beams]!=list(zip(cuts,cuts[1:])):raise ValueError('Physical segment coverage differs')
            for b in beams:
                if b['id'] in ids:raise ValueError('Duplicate physical segment')
                ids.add(b['id']);p=b['normal_action_polynomials']
                for name,degree in (('N_N',0),('My_strong_Nmm',2),('Mz_weak_Nmm',2)):
                    a=p[name]
                    if not isinstance(a,list) or not 1<=len(a)<=degree+1 or any(not _finite(v) for v in a):raise ValueError('Invalid analytical action field')
        if len(ids)!=len(m['beams']):raise ValueError('Unknown physical member')
        stations=[0.]+inp['attachment_x_mm']+[L]
        xyz=[[x,y,0.] for y in (inp['upper_gap_mm'],0.,-inp['lower_gap_mm']) for x in stations]
        if [n['id'] for n in m['nodes']]!=list(range(len(xyz))) or [n['xyz_CG_mm'] for n in m['nodes']]!=xyz:raise ValueError('Saved physical node inventory differs')
        fixed=[dict(node=i,dof=k) for i,n in enumerate(m['nodes']) if n['xyz_CG_mm'][0] in (0.,L)
            for k in ('ux','uy','uz','rx')+(('psi',) if inp['warping_end_condition']=='restrained_assumed' else ())]
        if m['fixed_dofs']!=fixed:raise ValueError('Saved end restraint inventory differs')
        for node in m['nodes']:
            if len(node['support_reactions'])!=7 or any(not _finite(v) for v in node['support_reactions']):raise ValueError('Invalid saved support reaction')
            if set(node['displacements'])!=set(('ux','uy','uz','rx','ry','rz','psi')) or any(not _finite(v) for v in node['displacements'].values()):raise ValueError('Invalid saved kinematics')
        if len(m['bars'])!=len(inp['connections']) or set(v['id'] for v in m['bars'])!=set(inp['connections']):raise ValueError('Saved bar inventory differs')
    return True


def _read(d,name,field):
    if field not in d:return None,None
    try:
        module=importlib.import_module('tercas.'+name+'.application')
        return module.saved_component(d),None
    except (ValueError,TypeError,KeyError,ArithmeticError,ImportError,AttributeError,IndexError) as exc:return None,str(exc)


def _beam_inventory(d,state):
    return [(c['combination']['id'],b['girt'],b['id'],b['x_start_mm'],b['x_end_mm'])
        for c in d['cases'] if c['combination']['limit_state']==state for b in c['model']['beams']]


def _en(d,c,error):
    source='EN1993-1-3:2006 6.1.6, componente seccional declarada'
    if c is None:return [item('EN:section_stresses','ELU',source=source,reason=error or 'Componente seccional EN não calculada; não se presume resistência N+M+B ou cisalhamento nula.')]
    from ..three_girt_en_normal.application import verification_members
    from ..three_girt_en_normal import centroid_policy as cp
    checked_members=verification_members(c,d)
    expected=[r for r in _beam_inventory(d,'ELU') if r[1] in checked_members]
    if not expected:return [item('EN:ELU_inventory','ELU',source=source,reason='Nenhum intervalo ELU avaliado.') ]
    actual=[(r['combination_id'],r['girt'],r['segment_id'],r['x_start_mm'],r['x_end_mm']) for r in c['rows']]
    if expected!=actual or set(c['per_member'])!=set(checked_members):raise ValueError('EN segment/member inventory differs from demand')
    if any(type(r.get('complete')) is not bool for r in c['rows']):raise ValueError('EN interval completeness is not boolean')
    out=[]
    for level,r in c['per_member'].items():
        if level not in members(d):continue
        count=sum(v[1]==level for v in expected)
        if r['ELU_segments']!=count or r['complete_segments']!=sum(v['complete'] for v in c['rows'] if v['girt']==level):raise ValueError('EN coverage count differs')
        complete=r['complete'] is True
        if complete is not (r['complete_segments']==count):raise ValueError('EN coverage conclusion differs')
        shear=r.get('shear_interaction');normal=r.get('normal') or (shear.get('normal') if shear else None)
        for key in ('normal','shear','interaction'):
            centroid=cp.qualification(c,level,key)
            bound=normal if key=='normal' else shear.get(key) if shear else None
            trace=dict(member_id=level,coverage_complete=complete,component_schema=c['schema'],
                source_component_sha256=c['content_sha256'],criterion_scope='declared_EN_section_model_only',
                centroid_shift_policy=centroid)
            if bound is not None:
                lo=bound.get('index_lower_witness');hi=bound.get('index_upper_bound')
                if (lo is not None and (not _finite(lo) or lo<0)) or (hi is not None and (not _finite(hi) or hi<0 or (lo is not None and hi<lo))):
                    raise ValueError('EN lower/upper bound contract differs')
                witness=bound.get('witness')
                if (lo is None)!=(witness is None):raise ValueError('EN lower witness missing')
                saved_lower=None if witness is None else (witness.get('index') if c['schema']=='three_girt_EN_normal_shear_interaction_integral_v2' else witness.get('index_lower_witness'))
                if witness is not None and (saved_lower!=lo or witness.get('girt')!=level or not _finite(witness.get('index')) or witness['index']<lo):
                    raise ValueError('EN concomitant lower witness differs')
                fail=lo is not None and lo>1
                passed=complete and shear is not None and shear.get('complete') is True and _finite(hi) and 0<=hi<=1 and centroid['qualified']
                qualified_upper=max(hi,centroid['original_index_upper_bound'] or 0.) if passed else None
                index=lo if fail else qualified_upper
                trace.update(index_lower_witness=lo,index_upper_bound=hi,
                    qualified_scenarios_index_upper_bound=qualified_upper,
                    partial_index_upper_bound=bound.get('partial_index_upper_bound'),witness=copy.deepcopy(bound.get('witness')),
                    numeric_measure='concomitant_lower_witness' if fail else
                        'full_interval_upper_bound_with_original_centroid_scenario' if passed and centroid['required_segments'] else
                        'full_interval_upper_bound' if passed else 'inconclusive_bound')
                out.append(item('EN:'+level+':'+key,'ELU',source=source,index=index,qualified=fail or passed,trace=trace,
                    reason='' if fail or passed else centroid['reason'] or 'Cobertura de seção ou limite numérico inconclusivo; máximo parcial não foi promovido.'))
            elif key=='normal':
                w=r.get('complete_envelope') or r.get('partial_maximum');index=w.get('normal_index') if w else None
                qualified=_finite(index) and index>=0 and ((complete and centroid['qualified']) or index>1)
                trace['witness']=copy.deepcopy(w)
                out.append(item('EN:'+level+':normal','ELU',source=source,index=index,qualified=qualified,trace=trace,
                    reason='' if qualified else centroid['reason'] or 'Envelope normal parcial ou ausente.'))
            else:out.append(item('EN:'+level+':'+key,'ELU',source=source,trace=trace,reason='Snapshot histórico sem este critério; não recalculado.'))
    return out


def _nbr(d,c,error):
    if c is None:return [item('NBR:reference','ELU',reason=error or 'Referência NBR não solicitada ou não calculada.')]
    expected=_beam_inventory(d,'ELU');actual=[(r['combination_id'],r['girt'],r['segment_id']) for r in c['rows']]
    if actual!=[x[:3] for x in expected] or c['source_geometry']!=d['source_geometry']:
        raise ValueError('NBR auxiliary interval/section inventory differs')
    if c['ELU_combinations']!=sum(x['combination']['limit_state']=='ELU' for x in d['cases']) or c['ELS_combinations_excluded']!=sum(x['combination']['limit_state']=='ELS' for x in d['cases']):
        raise ValueError('NBR auxiliary combination counts differ')
    rows=[]
    for r,(cid,level,segment,x0,x1) in zip(c['rows'],expected):
        if level not in members(d):continue
        if r['physical_member_length_mm']!=d['input_data']['L_mm'] or r['stability_lengths_mm']!=c['configuration']['effective_lengths_mm']:
            raise ValueError('NBR auxiliary physical/stability length differs')
        rows.append(axial_interaction_record(r,expected_combination_id=cid,expected_section_id=d['source_geometry']['profile_id'],
            expected_stability_member_id=level+'_full_physical_span',expected_region_id=segment,expected_segment_id=segment))
    return rows


def _service(d,c,error):
    if c is None:return [item('ELS:horizontal_model','ELS',source='NBR14762:2010 9.8.5; modelo horizontal declarado',reason=error or 'Componente horizontal Vlasov não calculada.')]
    out=[]
    for case in c['cases']:
        for level,r in case['members'].items():
            if level not in members(d):continue
            sufficient=(local_guard(case,level) if central(d) else case['network_local_normal_gross_sufficient'])
            out.append(item('ELS:'+case['combination']['id']+':'+level+':horizontal_model','ELS',
                source='NBR14762:2010 9.8.5; comparador local normal suficiente no modelo declarado',
                index=r['diagnostic_gross_ratio'],qualified=sufficient is True,
                reason=('Comparação da central condicionada à rigidez bruta declarada do entorno; não é prova física do ELS.' if central(d) else '') if sufficient else 'Crivo local da travessa avaliada inconclusivo; não é falha resistente nem flecha efetiva demonstrada.',
                trace=dict(member_id=level,combination_id=case['combination']['id'],witness=copy.deepcopy(r['witness']),
                    criterion_scope='horizontal_limit_in_declared_linear_model_only',source_component_sha256=c['content_sha256'])))
    return out


def _uniaxial(c,error,d=None):
    if c is None:return [] if not error else [item('uniaxial:reader','ELS',reason=error)]
    return [item('uniaxial:'+case['combination']['id']+':'+level,'ELS',source='NBR14762:2010 9.8.5, alternativa de vigas isoladas',
        index=r['isolated_component_index'],qualified=r['isolated_component_index'] is not None,
        reason='Modelo independente; não substitui a flecha da rede.',
        trace=dict(criterion_scope='isolated_uniaxial_alternative_only',source_component_sha256=c['content_sha256']))
        for case in c['cases'] for level,r in case['members'].items() if d is None or level in members(d)]


def _g81(d):
    out=[]
    for case in d['cases']:
        if case['combination']['limit_state']!='ELU':continue
        raw=case.get('G81_component',{});cap=raw.get('capacity',{});records=raw.get('records',[])
        numbers=('Fy_MPa','Cw_mm6','omega_max_mm2','Bn_Nmm2','By_Nmm2','phi_B','Ba_Nmm2')
        valid=(all(_finite(cap.get(k)) and cap[k]>0 for k in numbers)
            and cap.get('standard')=='AISI S100-2024' and cap.get('clause')=='G8.1-1/2, first-yield option'
            and cap.get('section_content_sha256')==d['source_geometry']['content_sha256']
            and cap.get('section_nodes_sha256')==d['source_geometry']['nodes_sha256']
            and cap.get('Fy_MPa')==d['input_data']['properties']['fy_MPa']
            and cap.get('Cw_mm6')==case['model']['inputs']['section']['Cw_mm6']
            and cap['phi_B']==.9 and cap['Bn_Nmm2']==cap['By_Nmm2']
            and cap['By_Nmm2']==cap['Fy_MPa']*cap['Cw_mm6']/cap['omega_max_mm2']
            and cap['Ba_Nmm2']==cap['phi_B']*cap['By_Nmm2']
            and cap.get('physical_product_verified') is False
            and {r.get('member') for r in records}==set(LEVELS) and len(records)==3)
        for level in members(d):
            found=[r for r in records if r.get('member')==level];r=found[0] if len(found)==1 else {}
            expected=case['model']['girt_envelopes'][level]['B_equilibrium_Nmm2']['max_abs']
            coherent=(valid and r.get('combination_id')==case['combination']['id'] and r.get('B_Nmm2')==expected['B_equilibrium_Nmm2']
                and r.get('ratio')==abs(expected['B_equilibrium_Nmm2'])/cap['Ba_Nmm2']
                and r.get('component_condition') is bool(r['ratio']<=1)
                and r.get('status')=='computed_conditional_component'
                and r.get('x_mm')==expected['x_mm'] and r.get('side')==expected['side']
                and all(r.get('concomitant_state',{}).get(k)==v for k,v in expected.items())
                and r.get('N_preserved') is True and r.get('H4_reduced_applied') is False
                and r.get('N_M_B_interaction_complete') is False and r.get('whole_member_approved') is False)
            out.append(item('G81:'+case['combination']['id']+':'+level,'ELU',source='AISI S100-2024 G8.1, componente independente',
                index=r.get('ratio'),qualified=coherent,reason='Comparação complementar de B; não soma nem substitui N+M+B EN/NBR.'))
    return out


def _zero_torsional_shear(beam,model):
    """Exact constant-twist proof, bound to saved geometry/loads/end nodes.

    Positive GJ/ECw, m=0 and equal end twists / zero end derivatives give
    constant phi, hence Tsv=Tw=0. Missing/unbound fields never imply zero.
    No sampling, tolerance, source files or new solve is used.
    """
    try:
        a=beam['torsion_state_parameters'];nodal=a['nodal_phi_psi']
        if (not isinstance(nodal,list) or len(nodal)!=4 or any(not _finite(v) for v in nodal)
            or any(not _finite(a.get(k)) or a[k]<=0. for k in ('L_mm','GJ_Nmm2','ECw_Nmm4'))
            or not _finite(a.get('m_SC_N'))):return False
        inp=model['inputs'];sec=inp['section'];level=LEVELS.index(beam['girt'])
        load=inp['loads'][level]
        if any(not _finite(sec[k]) or sec[k]<=0. for k in ('G_MPa','J_mm4','E_MPa','Cw_mm6')):return False
        if any(not _finite(sec[k]) for k in ('sc_y_mm','sc_z_mm')):return False
        if any(not _finite(load[k]) for k in ('distributed_torque_CG_N','q_z_N_mm','q_y_N_mm')):return False
        length=beam['x_end_mm']-beam['x_start_mm']
        torque=load['distributed_torque_CG_N']-sec['sc_y_mm']*load['q_z_N_mm']+sec['sc_z_mm']*load['q_y_N_mm']
        if (a['L_mm']!=length or beam['length_mm']!=length
            or a['GJ_Nmm2']!=sec['G_MPa']*sec['J_mm4']
            or a['ECw_Nmm4']!=sec['E_MPa']*sec['Cw_mm6'] or a['m_SC_N']!=torque):return False
        y=(inp['upper_gap_mm'],0.,-inp['lower_gap_mm'])[level];source=[]
        for x in (beam['x_start_mm'],beam['x_end_mm']):
            nodes=[n for n in model['nodes'] if n['xyz_CG_mm']==[x,y,0.]]
            if len(nodes)!=1:return False
            source.extend(nodes[0]['displacements'][key] for key in ('rx','psi'))
        if any(not _finite(v) for v in source) or source!=nodal:return False
        return a['m_SC_N']==0. and nodal[0]==nodal[2] and nodal[1]==nodal[3]==0.
    except (KeyError,TypeError,ValueError,IndexError,AttributeError):return False


def _applicability(d,nbr):
    elu=[b for c in d['cases'] if c['combination']['limit_state']=='ELU' for b in c['model']['beams'] if b['girt'] in members(d)]
    if not elu:return [item('ELU:coverage','ELU',reason='Nenhuma combinação ELU; filtro não é dispensa.')]
    # Exactly zero analytical coefficients, never sampled values or tolerances.
    zero_v=all(all(v==0 for v in b['normal_action_polynomials'][k][1:]) for b in elu for k in ('My_strong_Nmm','Mz_weak_Nmm'))
    zero_total_shear=zero_v and all(_zero_torsional_shear(b,c['model'])
        for c in d['cases'] if c['combination']['limit_state']=='ELU'
        for b in c['model']['beams'] if b['girt'] in members(d))
    tension=any(b['normal_action_polynomials']['N_N'][0]>0 for b in elu)
    reactions=[v for c in d['cases'] if c['combination']['limit_state']=='ELU' for n in c['model']['nodes']
        if (not central(d) or n['xyz_CG_mm'][1]==0.) and n['xyz_CG_mm'][0] in (0.,d['input_data']['L_mm']) for v in n['support_reactions'][:3]]
    zero_reactions=all(v==0 for v in reactions)
    no_interior=all(not c['model']['bars'] and not c['model']['inputs']['connections'] and not c['model']['inputs']['attachment_x_mm']
        and not c['model']['inputs']['nodal_loads'] for c in d['cases']) and d['configuration']['three_girt']['tie_count']==0
    out=[item('member_stability_and_analysis','MODEL',source='NBR14762:2010 8.1–8.2; modelo de primeira ordem declarado',
        reason='Estabilidade e aplicabilidade da análise de primeira ordem da rede nos ELU/ELS ainda não verificadas. Comprimentos NBR de referência e comparação horizontal local não são prova do conjunto. Nenhum certificado de campo, GJef/Cwef ou corte universal de giro foi imposto.'),
        item('transverse_shear_resistance','ELU',source='EN1993-1-3:2006 6.1.5',qualified=zero_v,excluded=zero_v,
            reason='Campo transversal V identicamente nulo em todos os polinômios ELU; Tsv/Tw e sigma–tau permanecem separados.' if zero_v else 'Resistência/flambagem por cortante transversal não demonstrada nesta rede; sigma–tau de 6.1.6 não a substitui.'),
        item('N_M_V_shear_reduction','ELU',source='EN1993-1-3:2006 6.1.10(1)',qualified=zero_total_shear,excluded=zero_total_shear,
            reason=('V transversal, Tsv e Tw identicamente nulos no campo salvo: sem redução adicional por cortante; critérios N/M/B permanecem.' if zero_total_shear else
                'Registro anterior sem componente EN6.27 nos dois eixos; este caso não foi coberto pelo subconjunto restrito salvo. A nova rota não exige torque nulo e mantém torção em 6.1.6.' if zero_v else
                'Registro anterior sem componente EN6.27 nos dois eixos. O limiar de 0,5 e a interação precisam de resistências EN próprias; não se impõe nulidade da torção nem interação adicional indiscriminada.')),
        item('support_force_introduction','ELU',source='NBR14762:2010 9.5.1 e Anexo D.1',qualified=zero_reactions,excluded=zero_reactions,
            reason='Todas as reações de força ELU salvas são exatamente nulas.' if zero_reactions else 'Reações de apoio existem. Classificar sua introdução local no perfil: compressão transversal da alma, exceção aplicável de alma ligada, ou outro mecanismo. P externa nula não dispensa esta avaliação; não é dimensionamento dos cordões.'),
        item('interior_force_introduction','ELU',source='NBR14762:2010 9.5.1/9.6, conforme mecanismo local',qualified=no_interior,excluded=no_interior,
            reason='Topologia interior vazia, sem barras, P ou ações nodais internas. Não dispensa as reações dos extremos.' if no_interior else 'Forças interiores exigem identificar o mecanismo local do perfil. Não se aplica Anexo D automaticamente a força axial soldada e não se exige dimensionar a solda neste escopo.')]
    if nbr is not None:
        from ..three_girt_local_stability import saved as saved_local_B1
        try:local=saved_local_B1(nbr,demand=d)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            local=None
            out[0]['reason']+=' Snapshot local B1 não utilizável: '+str(exc)
        if local is not None:
            out[0]['reason']='A amplificação flexional local B1 da central foi quantificada por plano, no vão integral. '
            out[0]['reason']+='N variável é admitido pela referência aproximada com N máximo; o complemento N/M incorpora B1 aos momentos, sem alterar a solução física. '
            out[0]['reason']+='Permanece inconclusiva a influência dos deslocamentos na redistribuição da rede. B1 próximo de 1 não é aprovação global; não se exige automaticamente outro solver.'
            out[0]['trace']['central_local_B1_component_sha256']=local['content_sha256']
    if nbr is not None and not zero_v:
        from ..three_girt_shear import saved as saved_web_shear
        try:web=saved_web_shear(nbr)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            web=None
            for r in out:
                if r['id'] in ('transverse_shear_resistance','N_M_V_shear_reduction'):
                    r['reason']+=' Snapshot adicional de alma não utilizável: '+str(exc)
        if web is not None:
            web_rows=[r for r in web['rows'] if r['girt'] in members(d)]
            en_rows=[r for r in web_rows if r['EN_web_shear'] is not None]
            en_note=('O piso resistente EN da alma também foi calculado separadamente. '
                if len(en_rows)==len(web_rows) else 'A capacidade EN da alma ainda não foi qualificada. ')
            weak_note=('O cortante fraco é identicamente nulo. ' if all(r['weak_shear_identically_zero'] for r in web_rows) else
                'A resistência do cortante fraco permanece pendente; VRd da alma não foi reutilizado. ')
            for r in out:
                if r['id']=='transverse_shear_resistance':
                    r['reason']='A componente forte da alma foi avaliada por NBR §9.8.3. '+en_note+weak_note+'A abrangência transversal completa da rede não foi aprovada por essas componentes.'
                    r['trace']['web_shear_component_sha256']=web['content_sha256']
                elif r['id']=='N_M_V_shear_reduction':
                    low=len(en_rows)==len(web_rows) and all(x['EN_no_web_shear_reduction']['status']=='meets' for x in en_rows)
                    r['reason']='M–V NBR da alma foi calculado na mesma seção por §9.8.4, sem omitir o N da rede. '+('O limiar EN de 0,5 atende no registro restrito da alma, que não contém a nova componente 6.27 dos dois eixos. ' if low else 'O registro restrito da alma não demonstra a redução/interação EN6.27 da seção. ')+weak_note+'N/M/B/T permanecem independentes.'
                    r['trace']['web_shear_component_sha256']=web['content_sha256']
    from ..three_girt_en_normal.application import saved_component as saved_en_mv_source
    try:en_mv_source=saved_en_mv_source(d)
    except (ValueError,TypeError,KeyError,ArithmeticError,AttributeError,IndexError) as exc:
        en_mv_source=None
        for r in out:
            if r['id'] in ('transverse_shear_resistance','N_M_V_shear_reduction') and r['status']=='pending':
                r['reason']+=' Fonte adicional EN6.27 não utilizável: '+str(exc)
    if en_mv_source and en_mv_source.get('EN_bending_shear_schema') is not None:
        selected=[r for r in en_mv_source['rows'] if r['girt'] in members(d)]
        mvs=[r['EN_bending_shear_component'] for r in selected if 'EN_bending_shear_component' in r]
        covered=bool(selected) and len(mvs)==len(selected)
        if covered:
            shear=max(r['result']['shear_ratio_upper'] for r in mvs)
            interaction=max(r['result']['index_upper'] for r in mvs)
            trace={'EN_normal_component_sha256':en_mv_source['content_sha256'],
                'EN_6_27_components_sha256':[r['content_sha256'] for r in mvs],
                'all_transverse_directions_included':True,'torsion_retained_in_separate_EN_6_1_6':True,
                'favorable_centroid_shift_not_credited':True}
            replacement={
                'transverse_shear_resistance':item('transverse_shear_resistance','ELU',
                    source='EN1993-1-3:2006 6.1.5; duas direções, capacidades por paredes',index=shear,
                    qualified=shear<=1.,trace=trace,
                    reason='Cortantes transversais forte e fraco cobertos por pisos EN distintos. Alma original no forte; duas mesas originais no fraco. Teto acima de 1 é inconclusivo, não falha demonstrada.'),
                'N_M_V_shear_reduction':item('N_M_V_shear_reduction','ELU',
                    source='EN1993-1-3:2006 6.1.10 Eq6.27, Mf=0; interpretação por dois eixos SCIA 17.0',
                    index=interaction,qualified=all(r['result']['component_qualified'] for r in mvs),trace=trace,
                    reason='Interação N/M e ambos os cortantes transversais avaliada com pisos EN e Mf=0. B/Tsv/Tw não precisam ser nulos: permanecem nas três desigualdades complementares de 6.1.6. O transporte do centroide de N é preservado uma vez, sem creditar cancelamento favorável dos momentos. Não encerra estabilidade nem aprovação global.')}
            out=[replacement.get(r['id'],r) for r in out]
        else:
            errors='; '.join(sorted({r.get('EN_bending_shear_error','Trecho sem registro') for r in selected if 'EN_bending_shear_component' not in r}))
            for r in out:
                if r['id'] in ('transverse_shear_resistance','N_M_V_shear_reduction') and r['status']=='pending':
                    r['reason']='Componente EN6.27 solicitada, com cobertura incompleta: '+errors
                    r['trace']['EN_normal_component_sha256']=en_mv_source['content_sha256']
    if not tension:out.append(item('tensile_section_scope','ELU',source='NBR14762:2010 9.6',qualified=True,excluded=True,reason='Nenhum intervalo ELU tem N de tração; não se exige Nt ou Ct sem demanda de tração.'))
    else:
        t=nbr.get('capacities',{}).get('tension',{}) if nbr else {};nt=t.get('Nt_Rd_N')
        ns=max(b['normal_action_polynomials']['N_N'][0] for b in elu)
        ok=_finite(nt) and nt>0
        out.append(item('tensile_section_scope','ELU',source='NBR14762:2010 9.6, componente axial de seção',index=ns/nt if ok else None,qualified=ok,
            reason='Seções líquidas/Ct necessários apenas nos intervalos tracionados. Hipótese U→Ue aprovada não é dimensionamento dos cordões nem certificado experimental.' if ok else 'Há tração e falta resistência de seção Nt aplicável. Conferir An0, An e Ct/detalhe; não substituir por Ag nem exigir dimensionamento das soldas neste inventário.',
            trace=dict(N_tension_max_N=ns,Nt_Rd_N=nt,scope='axial_tensile_section_only; no EN effective-area transfer')))
    return out


def _safe_records(key,state,fn):
    try:return fn()
    except (ValueError,TypeError,KeyError,ArithmeticError,AttributeError,IndexError) as exc:return [item(key,state,reason=str(exc))]


def assess(d):
    if not isinstance(d,dict):raise ValueError('Resultado deve ser um objeto.')
    from ..three_girt_en_normal import centroid_policy as cp
    original=None;records=[];groups=[]
    try:
        original=fingerprint(d)
        validate_demand(d)
        from ..support_scope import saved as saved_support_scope
        support_scope=saved_support_scope(d)
    except (ValueError,TypeError,KeyError,ArithmeticError,AttributeError,IndexError) as exc:
        records=[item('saved_demand_integrity',reason=str(exc))]
        result=aggregate([r['id'] for r in records],records,inventory_qualified=True)
        try:scoped=central(d)
        except (ValueError,TypeError,KeyError):scoped=False
        if scoped:result['verification_scope']=copy.deepcopy(d['verification_scope'])
        result.update(assessment_schema=CENTRAL_SCHEMA if scoped else SCHEMA,source_result_sha256=original,source_input_fingerprint=d.get('input_fingerprint'),
            groups=[],whole_member_approved=False,current_adapter_can_approve=False,numerical_results_changed=False,excluded_scope=EXCLUSIONS)
        from ..global_verification import display_summary
        result['display_summary']=display_summary(result)
        result[cp.ASSESSMENT_REVISION]=cp.SCHEMA
        result['content_sha256']=fingerprint(result)
        return result
    from ..model_domain import evidence as model_evidence
    try:domain=model_evidence(d['input_data'])
    except (ValueError,TypeError,KeyError) as exc:domain=dict(conflict=str(exc))
    records.append(item('declared_model_domain',qualified=not domain['conflict'],verdict='meets',
        reason='Domínio declarado sem crédito de rigidez da telha; não exige certificado de campo.' if not domain['conflict'] else domain['conflict']))
    records.append(item('saved_linear_demand',qualified=True,verdict='meets',reason='Hashes, combinações, cobertura e controles de equilíbrio da demanda linear salvos são coerentes. Não é prova de estabilidade.'))
    en,ee=_read(d,'three_girt_en_normal','EN_normal_N_M_B_component')
    nbr,ne=_read(d,'three_girt_axial','NBR_axial_bending_component')
    service,se=_read(d,'three_girt_service','horizontal_service_component')
    uni,ue=_read(d,'three_girt_uniaxial','isolated_uniaxial_service_component')
    try:er=_en(d,en,ee)
    except (ValueError,KeyError,TypeError,ArithmeticError,AttributeError,IndexError) as exc:er=[item('EN:inventory','ELU',reason=str(exc))]
    sr=_safe_records('ELS:horizontal_reader','ELS',lambda:_service(d,service,se))
    nr=_safe_records('NBR:reference_reader','ELU',lambda:_nbr(d,nbr,ne))
    gr=_safe_records('G81:reader','ELU',lambda:_g81(d))
    groups.extend([_group('EN_section','Tensões seccionais EN N/M/B, cisalhamento e interação',er,'Critérios seccionais no modelo EN declarado; não são projeto integral NBR/EN.'),
        _group('NBR_reference','Referência NBR N+M de vão inteiro',nr,'Referência separada; não é prova de estabilidade da rede nem denominador substituto da EN.'),
        _group('G81','Componente independente de bimomento G8.1',gr,'Comparação auxiliar, não critério global adicional em paralelo à EN.'),
        _group('horizontal_service','Deslocamento horizontal Vlasov',sr,'Comparação no modelo linear declarado; aplicabilidade física separada.')])
    ur=_safe_records('uniaxial:reader','ELS',lambda:_uniaxial(uni,ue,d))
    if ur:groups.append(_group('isolated_uniaxial','Alternativa uniaxial de vigas isoladas',ur,'Modelo independente, nunca utilizado para aprovar a rede.'))
    records+=er+sr+_safe_records('applicability_reader','MODEL',lambda:_applicability(d,nbr))
    for state in ('ELU','ELS'):
        if not any(c['combination']['limit_state']==state for c in d['cases']):records.append(item('missing_limit_state:'+state,state,reason='Nenhuma combinação '+state+' avaliada.'))
    from ..support_scope import apply_inventory as apply_support_scope
    records,support_scope=apply_support_scope(d,records)
    result=aggregate([r['id'] for r in records],records,inventory_qualified=True)
    result.update(assessment_schema=CENTRAL_SCHEMA if central(d) else SCHEMA,source_result_sha256=original,source_input_fingerprint=d['input_fingerprint'],
        groups=groups,whole_member_approved=False,current_adapter_can_approve=False,numerical_results_changed=False,
        combined_ELS_approved=False,physical_conditions_verified=False,historical_snapshots_requalified=False,
        auxiliary_groups_not_combined=['NBR_reference','G81','isolated_uniaxial'],excluded_scope=copy.deepcopy(EXCLUSIONS),
        interpretation='Estados calculados valem somente no modelo e critério identificados. Não se somam/misturam índices EN, NBR ou AISI; não há aprovação global automática.')
    from ..global_verification import display_summary
    result['display_summary']=display_summary(result)
    result[cp.ASSESSMENT_REVISION]=cp.SCHEMA
    if support_scope is not None:
        result['local_support_scope_exclusion']=support_scope
        result['excluded_scope'].append(support_scope['reason'])
    if central(d):
        for group in result['groups']:group['scope']='Somente travessa central. '+group['scope']
        result['verification_scope']=copy.deepcopy(d['verification_scope'])
        result['interpretation']=NOTICE+' '+result['interpretation']
    if fingerprint(d)!=original:raise AssertionError('Assessment mutated the saved demand')
    result['content_sha256']=fingerprint(result)
    return result


def saved_assessment(d,a):
    if not isinstance(a,dict) or a.get('assessment_schema') not in (SCHEMA,CENTRAL_SCHEMA):raise ValueError('Unknown global inventory schema')
    if a.get('content_sha256')!=fingerprint({k:v for k,v in a.items() if k!='content_sha256'}):raise ValueError('Saved inventory content changed')
    if a.get('source_result_sha256')!=fingerprint(d):raise ValueError('Saved inventory belongs to another result')
    if a.get('whole_member_approved') is not False or a.get('current_adapter_can_approve') is not False or a.get('numerical_results_changed') is not False:
        raise ValueError('Saved inventory exceeds qualified scope')
    from ..support_scope import validate_saved_inventory
    validate_saved_inventory(d,a)
    expected_schema=CENTRAL_SCHEMA if central(d) else SCHEMA
    if a['assessment_schema']!=expected_schema:raise ValueError('Saved inventory schema differs from demand scope')
    if a['assessment_schema']==CENTRAL_SCHEMA and a.get('verification_scope')!=d['verification_scope']:
        raise ValueError('Saved central inventory scope changed')
    if d.get('EN_normal_N_M_B_component') is not None:
        from ..three_girt_en_normal import centroid_policy as cp
        en,error=_read(d,'three_girt_en_normal','EN_normal_N_M_B_component')
        if en is not None:cp.verify_assessment(en,a,members(d))
        elif any(row['id'].startswith('EN:') and row['status']=='meets' for row in a['checks']):
            raise ValueError('Saved EN inventory source is no longer usable: '+str(error))
    return a
