"""Non-mutating adapter of an ALREADY calculated own-reference purlin batch.

Does not create combinations, recompute masses, rotate actions again or add PP.
The application's existing [parallel,normal] vector maps to section [x,-y].
Unknown external lines remain pending. PP alone is assigned to its known CG.
"""
import copy
import hashlib
import json
import math

import numpy as np

from .section import finite,verify_section
from .vlasov import solve_member,evaluate,METHOD,NumericalQualificationError


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def active_action_roles(result):
    """Roles with nonzero existing factored demand; PP is reported but fixed."""
    bundle=result['load_bundle'];roles=set()
    for c in bundle['combinations']:
        for key,factor in c['coefficients'].items():
            if key=='P':
                if np.any(_vec(c['P_vector'],'P')):roles.add(key)
            elif finite(factor,key+' factor')!=0 and np.any(_vec(bundle['case_vectors_N_mm'][key],key)):
                roles.add(key)
    return [k for k in ('PP','CP','SC','V_Cima','V_Baixo','P') if k in roles]


def load_lines_from_cg(section, records):
    """UI conversion only, explicit offsets in the SAME unrotated R01 axes.

records[role]={declared:bool,xy_from_CG_mm:[dx,dy],origin:str}.
No default line for nonzero external action; PP is always [0,0] from CG.
The roof angle has already rotated action vectors, not these section axes.
"""
    verify_section(section)
    if not isinstance(records,dict) or set(records)-set(('PP','CP','SC','V_Cima','V_Baixo','P')):
        raise ValueError('Unknown load-line role')
    cg=section['properties']['centroid_xy_mm'];out={}
    for key,r in records.items():
        if not isinstance(r,dict) or type(r.get('declared')) is not bool:
            raise ValueError('Explicit declared flag required for load line '+key)
        if not r['declared']:continue
        offset=r.get('xy_from_CG_mm')
        if not isinstance(offset,(tuple,list)) or len(offset)!=2:
            raise ValueError('Two offsets from centroid required')
        offset=[finite(x,key+' offset') for x in offset]
        if key=='PP' and offset!=[0.,0.]:raise ValueError('Self-weight cannot be moved from centroid')
        if not isinstance(r.get('origin'),str) or not r['origin'].strip():
            raise ValueError('Load-line origin/idealization required')
        out[key]={'xy_mm':[cg[i]+offset[i] for i in (0,1)],'origin':r['origin'],
                  'xy_from_CG_mm':offset,'coordinate_source':'Explicit conversion from frozen centroid; x toward lips, y upward'}
    return out


def _vec(raw, name):
    if not isinstance(raw,dict) or set(raw)!=set(('normal','parallel')):
        raise ValueError(name+': explicit normal/parallel vector required')
    return np.array([finite(raw['parallel'],name),-finite(raw['normal'],name)])


def _line(lines,name,section):
    if name=='PP':
        xy=section['properties']['centroid_xy_mm']
        if name in lines and not np.allclose(lines[name].get('xy_mm'),xy,rtol=0,atol=1e-12):
            raise ValueError('Profile self-weight remains at its own centroid')
        return list(xy),'Profile self-weight at centroid; same frozen section geometry'
    rec=lines.get(name)
    if not isinstance(rec,dict) or not isinstance(rec.get('origin'),str) or not rec['origin'].strip():
        return None,'Missing application line/origin for '+name
    v=rec.get('xy_mm')
    if not isinstance(v,(list,tuple)) or len(v)!=2:return None,'Missing application line coordinates for '+name
    return [finite(x,name+' application') for x in v],rec['origin']


def _check_snapshot(result,section):
    verify_section(section)
    if result.get('schema')!='tercas_batch_results_v1':
        raise ValueError('This adapter requires an already calculated area batch; no direct-load decomposition inferred')
    data=result['input_data']
    if data.get('member_application','purlin')!='purlin':
        raise ValueError('Do not substitute a single purlin for the three-girt system')
    if fingerprint(data)!=result.get('input_fingerprint'):
        raise ValueError('Stale result/input fingerprint')
    if data.get('model_domain')!='cladding_actions_only_20261103_r1':
        raise ValueError('No-contact, no-restraint cladding model must be explicit')
    if 'ue_family_sources' in data:
        identity=data['ue_family_sources']
        if (identity.get('reference_id')!=section['profile_id'] or
                identity.get('nodes_sha256')!=section['nodes_sha256'] or
                data.get('ue_family_reference',{}).get('reference_id')!=section['profile_id']):
            raise ValueError('Batch and torsion geometry identities differ')
    elif data.get('ue_model',{}).get('reference_id')=='Ue100x50x17x1.20_rounded_R01_209nodes_nu0p3':
        # Legacy reference has no node digest field. This is an explicit, bounded
        # identity mapping, in addition to scalar checks and the app's own gate.
        if (section['profile_id']!='R01_Ue100x50x17x1.20_rounded_faceted_209_frozen' or
                section['nodes_sha256']!='004c9cee5033877e4cf1c619627c968c02413aea26fe67a0a5422218ec003f7d' or
                data.get('active_numeric_reference',{}).get('reference_id')!=data['ue_model']['reference_id']):
            raise ValueError('Legacy R01 1.20 identity differs')
    else:
        raise ValueError('Own Ue100 geometry identity required; scalar catalogue coincidence is insufficient')
    p=data['properties'];s=section['properties']
    for k,v in [('A_mm2',p['A_cm2']*100),('Ix_strong_mm4',p['Ix_cm4']*10000),
                ('Iy_weak_mm4',p['Iy_cm4']*10000),('J_mm4',p['J_mm4']),('Cw_mm6',p['Cw_mm6'])]:
        if not math.isclose(s[k],v,rel_tol=2e-12,abs_tol=1e-9):
            raise ValueError('Batch and torsion section differ: '+k)
    if p['t']!=section['thickness_mm']:raise ValueError('Thickness identity differs')
    L=finite(data['L_mm'],'length',True)
    if not 3000<=L<=6000:raise ValueError('Frozen purlin application scope is 3000 to 6000 mm')
    bundle=result['load_bundle'];cases=result['cases']
    if finite(bundle.get('L_mm'),'bundle length',True)!=L:
        raise ValueError('Batch load bundle and input span differ')
    cmap={c['id']:c for c in bundle['combinations']}
    if len(cmap)!=len(bundle['combinations']) or len(cases)!=len(cmap):
        raise ValueError('Duplicate or missing source combination')
    if len({c['combination']['id'] for c in cases})!=len(cases):raise ValueError('Duplicate case')
    for c in cases:
        if c['combination']!=cmap.get(c['combination']['id']):
            raise ValueError('Case does not match the preserved combination bundle')
    # Consistency check only; no mass replacement, automatic density or new PP.
    pp=_vec(bundle['case_vectors_N_mm']['PP'],'PP')
    expected=finite(p['mass_kg_m'],'mass',True)*9.80665/1000
    if not math.isclose(float(np.linalg.norm(pp)),expected,rel_tol=2e-12,abs_tol=1e-12):
        raise ValueError('Existing PP vector differs from existing linear mass')
    return data,bundle


def actions_for_combination(bundle,combo,section,lines):
    known=set(('PP','CP','SC','V_Cima','V_Baixo','P'))
    if not isinstance(lines,dict) or set(lines)-known:raise ValueError('Unknown action-line role')
    if set(combo['coefficients'])-known:raise ValueError('Unmapped action in existing combination')
    acts=[];missing=[];summed=np.zeros(2)
    for name,f0 in combo['coefficients'].items():
        if name=='P':continue
        factor=finite(f0,name+' existing factor')
        q=factor*_vec(bundle['case_vectors_N_mm'][name],name);summed+=q
        if not np.any(q):continue
        xy,origin=_line(lines,name,section)
        if xy is None:missing.append(origin);continue
        acts.append(dict(name=name,kind='uniform',q_xy_N_mm=q.tolist(),couple_N=0.,
            application_xy_mm=xy,origin=origin,existing_combination_factor=factor))
    if not np.allclose(summed,_vec(combo['q_vector'],'combined q'),rtol=2e-12,atol=1e-12):
        raise ValueError('Component sum does not equal already combined q; do not repair or duplicate PP')
    P=_vec(combo['P_vector'],'combined P')
    pp=_vec(bundle['case_vectors_N_mm']['PP'],'existing PP direction')
    ppnorm=float(np.linalg.norm(pp))
    if ppnorm<=0:raise ValueError('Existing PP direction unavailable')
    expectedP=finite(combo['coefficients'].get('P',0.),'existing P factor')*1000*pp/ppnorm
    if not np.allclose(P,expectedP,rtol=2e-12,atol=1e-9):
        raise ValueError('Point vector differs from existing P factor/direction')
    if not math.isclose(finite(combo['q_N_mm'],'existing scalar q'),-summed[1],rel_tol=2e-12,abs_tol=1e-12):
        raise ValueError('Scalar and vector normal q differ')
    if not math.isclose(finite(combo['P_N'],'existing scalar P'),-P[1],rel_tol=2e-12,abs_tol=1e-9):
        raise ValueError('Scalar and vector normal P differ')
    if np.any(P):
        if 'P' not in combo['coefficients']:raise ValueError('Point force missing its source coefficient')
        xy,origin=_line(lines,'P',section)
        if xy is None:missing.append(origin)
        else:acts.append(dict(name='P',kind='point',force_xy_N=P.tolist(),couple_Nmm=0.,
            s_mm=finite(combo['x_mm'],'existing P position'),application_xy_mm=xy,origin=origin,
            existing_point_position=combo.get('point_position','fixed')))
    if not acts and not missing:
        acts=[dict(name='zero_combination',kind='uniform',q_xy_N_mm=[0.,0.],couple_N=0.,
                   application_xy_mm=section['properties']['centroid_xy_mm'],origin='Exact zero existing action combination')]
    return acts,missing


def support_limit_before_point(result):
    """Analytical a->0+ layer, not an exactly supported point treated as internal.

There is no longitudinal point force or applied bimoment. Thus phi,psi,B are
continuous in the limit, while V_after-V_before=-P and T_after-T_before=-Tp.
The local load-introduction resistance stays pending.
"""
    points=[a for a in result['loads'] if a['kind']=='point']
    if len(points)!=1 or points[0]['s_mm']!=0:
        raise ValueError('One existing left-support-limit point required')
    p=points[0];state=evaluate(result,0,0.)
    state.update(element_id=result['member_id']+':support_limit_before_P',element_index=None,
        position_limit='a->0+, s->0+, before P; analytical vanishing layer, not a finite FE element',
        side='right',demand_scope='concomitant support-limit action state; local force transfer not checked')
    state['Vx_N']+=p['force_xy_N'][0];state['Vy_N']+=p['force_xy_N'][1]
    state['T_Nmm']+=p['torque_SC_Nmm'];state['Tw_Nmm']+=p['torque_SC_Nmm']
    # The FE constitutive field does not represent this vanished interval.
    state['B_constitutive_Nmm2']=None;state['T_constitutive_Nmm']=None
    sc=result['section']['properties']['shear_center_xy_mm'];cg=result['section']['properties']['centroid_xy_mm']
    state['T_CG_Nmm']=state['T_Nmm']-(cg[0]-sc[0])*state['Vy_N']+(cg[1]-sc[1])*state['Vx_N']
    state['source']['support_limit_derivation']='V/T jumps and continuity of phi,psi,B for no concentrated axial-sectorial action'
    return state


def attach_torsion_evidence(result, *, section, load_lines, supports, elements_per_interval=32):
    """Add a separate evidence record without altering any existing result.

Missing load-line data yield an explicit pending case. No common line is
inferred and no case is quietly dropped. P_APOIO preserves its limit layer.
"""
    data,bundle=_check_snapshot(result,section)
    out=copy.deepcopy(result);records=[]
    for c in result['cases']:
        combo=c['combination'];acts,missing=actions_for_combination(bundle,combo,section,load_lines)
        base=dict(combination_id=combo['id'],limit_state=combo['limit_state'],method=METHOD,
            coverage_complete=False,resistance_qualified=False,whole_member_approved=False,
            source_input_fingerprint=result['input_fingerprint'])
        if missing:
            records.append(dict(base,status='pending_model_data',missing=missing,analysis=None));continue
        if combo.get('point_position') not in (None,'center','support_limit','fixed'):
            records.append(dict(base,status='pending_model_data',missing=['Unsupported point-position semantics'],analysis=None));continue
        try:
            r=solve_member(section=section,length_mm=data['L_mm'],E_MPa=data['properties']['E_MPa'],
                G_MPa=data['properties']['G_MPa'],actions=acts,supports=supports,
                combination_id=combo['id'],limit_state=combo['limit_state'],member_id='PURLIN',
                action_accounting_origin='Existing batch components and factors; PP counted once; no new combination',
                elements_per_interval=elements_per_interval)
        except NumericalQualificationError as exc:
            records.append(dict(base,status='pending_numerical_qualification',missing=[str(exc)],analysis=None,
                numerical_diagnostics=copy.deepcopy(exc.diagnostics)))
            continue
        if combo.get('point_position')=='support_limit' and any(a['kind']=='point' for a in acts):
            r['support_limit_states']=[support_limit_before_point(r)]
            r['critical_states']=r['support_limit_states']+r['critical_states']
            r['analysis_domain']['point_position_scope']='Prescribed a->0+ left-support limit, not an all-position envelope'
        elif any(a['kind']=='point' for a in acts):
            r['analysis_domain']['point_position_scope']='Existing prescribed point position only, not an all-position envelope'
        # No old strength, ELS status or snapshot is relabelled by this calculation.
        records.append(dict(base,status='elastic_demand_computed',missing=r['missing'],analysis=r))
    out['torsion_evidence']={'schema':'purlin_torsion_batch_evidence_v1','method':METHOD,
        'source_input_fingerprint':result['input_fingerprint'],'load_lines':copy.deepcopy(load_lines),
        'supports':copy.deepcopy(supports),'records':records,
        'computed_cases':sum(r['status']=='elastic_demand_computed' for r in records),
        'pending_model_cases':sum(r['status']=='pending_model_data' for r in records),
        'pending_numerical_cases':sum(r['status']=='pending_numerical_qualification' for r in records),
        'scope':'Independent elastic demand addition; original pure-bending strength checks are not requalified under torsion',
        'coverage_complete':False,'whole_member_approved':False,'resistance_qualified':False,
        'source_preserved':True,'app_axis_mapping':'physical q=[parallel,-normal]; Mforte_R01=-Mx_physical; Mfraco_R01=-My_physical'}
    return out


def summarize_torsion_evidence(evidence):
    """Losslessly keep selected witness numbers, without a new solve or rounding.

Individual extrema are selected from the exact-field critical states, not
combined across positions. This is NOT an interaction/stress envelope proof.
Dense nodal/element arrays and 209-node geometry are omitted from this compact
view only. The source evidence is untouched and can be exported separately.
"""
    if evidence.get('schema')!='purlin_torsion_batch_evidence_v1':
        raise ValueError('Expected complete torsion batch evidence')
    out={k:copy.deepcopy(v) for k,v in evidence.items() if k!='records'}
    out['schema']='purlin_torsion_batch_summary_v1';out['records']=[]
    out['dense_data_omitted']=True
    fields=('N_N','Mx_physical_Nmm','My_physical_Nmm','Mforte_R01_Nmm','Mfraco_R01_Nmm',
            'Vx_N','Vy_N','T_Nmm','T_CG_Nmm','Tsv_Nmm','Tw_Nmm','B_Nmm2','phi_rad','psi_per_mm',
            'B_constitutive_Nmm2','T_constitutive_Nmm')
    keep_state=('combination_id','limit_state','member_id','element_id','element_index','x_mm','s_mm','u','side',
                'position_limit','demand_scope','sign_convention')+fields
    def compact_state(s):return {k:copy.deepcopy(s[k]) for k in keep_state if k in s}
    for record in evidence['records']:
        rec={k:copy.deepcopy(v) for k,v in record.items() if k!='analysis'};a=record.get('analysis')
        if a is None:rec['analysis']=None;out['records'].append(rec);continue
        states=a['critical_states'];witnesses=[];lookup={};env={}
        def witness(s):
            # Exact station/side identity. No nearby positions are merged.
            key=(s['element_id'],s['x_mm'],s['u'],s['side'],s.get('position_limit'))
            if key not in lookup:
                lookup[key]=len(witnesses);witnesses.append(compact_state(s))
            return lookup[key]
        for field in fields:
            available=[s for s in states if s.get(field) is not None]
            if not available:env[field]=None;continue
            low=min(available,key=lambda s:s[field]);high=max(available,key=lambda s:s[field]);absolute=max(available,key=lambda s:abs(s[field]))
            env[field]={label:{'value':s[field],'witness_index':witness(s)} for label,s in
                        [('minimum',low),('maximum',high),('maximum_absolute',absolute)]}
        summary={k:copy.deepcopy(a[k]) for k in ('method','length_mm','E_MPa','G_MPa','loads','support_hypotheses',
            'combination_id','limit_state','member_id','action_accounting_origin','support_reactions','numerics',
            'analysis_domain','demand_coverage_complete_for_declared_model','coverage_complete','missing',
            'physical_design_approved','resistance_qualified','whole_member_approved','small_rotation_warning','critical_state_scope')}
        summary.update(schema='single_vlasov_member_summary_v1',section={k:copy.deepcopy(a['section'][k]) for k in
            ('profile_id','nodes_sha256','content_sha256','properties','thickness_mm','normalization','stress_scope','physical_geometry_verified')},
            element_count=len(a['elements']),state_count=len(states),witnesses=witnesses,field_envelopes=env,
            max_abs_phi=compact_state(a['max_abs_phi']),support_limit_states=[compact_state(s) for s in a.get('support_limit_states',[])],
            summary_scope='Individual-field extrema with same-state concomitants; not the maximum combined stress/resistance interaction',
            dense_fields_available_in_original_evidence=True)
        rec['analysis']=summary;out['records'].append(rec)
    return out
