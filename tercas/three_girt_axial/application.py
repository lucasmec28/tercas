"""Practical, explicit NBR 14762:2010 N/M arithmetic for the 7DOF network.

This is a separate component, never an approval of N+M+B, H4, the physical
network or ELS. Current own-Ue scalar denominators are a full-span K=Cb=Cm=1
REFERENCE. No tie station is converted to a buckling support. Pure-compression
Table11 evidence is not reused as a bending or combined-stress exemption.
"""
import copy
import hashlib
import json
import math
from numpy.polynomial import Polynomial
from . import backend as a

SCHEMA = 'three_girt_current_NBR_axial_bending_v1'
CONFIG_SCHEMA = 'three_girt_NBR_full_span_reference_v1'
LEVELS = ('upper', 'middle', 'lower')
SIGN_MAP = ('N_N positive=tension. NBR strong=My_frame; NBR weak=Mz_frame. '
            'Mz_frame>0 compresses the web (x_R01<0), <0 the lips. '
            'R01 physical moments are their negatives; do not invert twice.')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def _check_digest(record, key):
    if not isinstance(record, dict) or not isinstance(record.get(key), str):
        raise ValueError('Missing current snapshot digest: '+key)
    if fingerprint({k:v for k,v in record.items() if k != key}) != record[key]:
        raise ValueError('Current snapshot content changed: '+key)


def reference_configuration(demand):
    """Return a reviewable full-span reference, not physical restraint approval.

    Callers must save/choose this explicit component independently of the
    warping solve. Missing net areas/Ct remain None, never gross-area defaults.
    """
    L = a._number(demand['input_data']['L_mm'], 'L', positive=True)
    return dict(schema=CONFIG_SCHEMA, enabled=True,
        demand_input_fingerprint=demand['input_fingerprint'],
        reference_mode='own_Ue_full_span_K_Cb_Cm_1_no_tie_credit',
        effective_lengths_mm=dict(symmetry=L, orthogonal=L, torsion=L),
        reference_origin='Referência analítica explícita: vão físico inteiro, K=Cb=Cm=1, sem crédito de nós/tirantes ou telha. Não comprova os vínculos reais nem estabilidade do conjunto com torção.',
        tension=dict(An0_mm2=None, An_mm2=None, Ct=None,
            origin='Sem inventário de seções líquidas/Ct; tração completa permanece pendente.',
            outside_area_origin=None, connection_origin=None))


def _validate(demand, config):
    from ..three_girt_warping.application import SCHEMA as DEMAND_SCHEMA
    if not isinstance(demand, dict) or demand.get('schema') != DEMAND_SCHEMA:
        raise ValueError('A current 7DOF demand snapshot is required')
    if demand.get('coverage_complete') is not True or not demand.get('cases'):
        raise ValueError('Current demand combination coverage is incomplete')
    expected=fingerprint(dict(data=demand['input_data'],config=demand['configuration']))
    if demand.get('input_fingerprint') != expected:
        raise ValueError('Demand source inputs/configuration changed after solving')
    template=reference_configuration(demand)
    allowed=set(template) | ({'tension_connection'} if isinstance(config,dict) and 'tension_connection' in config else set())
    if not isinstance(config,dict) or set(config) != allowed:
        raise ValueError('Exact separate axial/bending configuration required')
    for k in ('schema','enabled','demand_input_fingerprint','reference_mode','effective_lengths_mm'):
        if config[k] != template[k]:
            raise ValueError('Unsupported or stale axial/bending reference configuration: '+k)
    a._origin(config['reference_origin'])
    if not isinstance(config['tension'],dict) or set(config['tension']) != set(template['tension']):
        raise ValueError('Explicit axial tensile input fields required')
    # The source is verified through its own pinned source gate. Its N=0 token
    # qualifies the scalar source only, never the N/M/B network.
    from .. import ue_family_reference as family, ue_reference as single
    data=demand['input_data']
    if family.claims_reference(data):
        source=family.evidence(data);ref=family.reference(data['properties']['t'],data['L_mm'])
    elif single.claims_reference(data):
        source=single.evidence(data);ref=single.reference(data['L_mm'])
        pp=ref['properties']
        pp['centroid_xy_mm']=[pp['centroid_x_mm'],pp['centroid_y_mm']]
        pp['shear_center_xy_mm']=[pp['shear_center_x_mm'],pp['shear_center_y_mm']]
    else:raise ValueError('A verified current own-Ue scalar source is required')
    if source['reference_id'] != ref['id']:
        raise ValueError('Own-Ue source identity differs from scalar reference')
    # Rebuild only the cheap input/load contract, not the frame solution.
    # Equal edited case+bundle labels cannot silently reassign a solved model.
    from ..torsion_study import section_for
    from ..three_girt_warping.application import frame_section, _connections
    from ..three_girt_application import configuration, load_cases, readiness
    section=section_for(data);expected_section=frame_section(data,section)
    raw=copy.deepcopy(demand['configuration']['three_girt']);raw['enabled']=True
    raw.update(sc_y_mm=expected_section['sc_y_mm'],sc_z_mm=expected_section['sc_z_mm'],sc_origin=expected_section['origin'])
    adapted=copy.deepcopy(data);adapted['three_girt_model']=raw;c=configuration(adapted)
    if readiness(adapted,c):raise ValueError('Current physical model declaration is incomplete')
    expected_rows,expected_bundle=load_cases(adapted,c)
    if demand.get('load_bundle') != expected_bundle or 'load_bundle' not in demand:
        raise ValueError('Demand bundle differs from reconstructed current loads')
    if len(demand['cases'])!=len(expected_rows) or any(
        {k:row.get(k) for k in expected_row} != expected_row
        for row,expected_row in zip(demand['cases'],expected_rows)):
        raise ValueError('Demand cases differ from reconstructed current loads/combinations')
    expected_connections=_connections(demand['configuration']['connections'],section,c)
    spacing=data['area_inputs']['spacing_m']*1000
    seen=set()
    for case in demand['cases']:
        combination=case['combination'];cid=combination['id'];model=case['model']
        if cid in seen:raise ValueError('Duplicate demand combination id')
        seen.add(cid)
        if combination['limit_state'] not in ('ELU','ELS'):
            raise ValueError('Unrecognized limit state')
        _check_digest(model,'demand_content_sha256')
        expected_inputs=dict(L_mm=data['L_mm'],upper_gap_mm=spacing,lower_gap_mm=spacing,
            attachment_x_mm=c['resolved_positions_mm'],section=expected_section,blue=c['blue'],green=c['green'],
            loads=case['loads'],connections=expected_connections,
            warping_end_condition=demand['configuration']['warping_end_condition'],
            warping_condition_origin=demand['configuration']['warping_condition_origin'],
            include_green=True,brace_self_weight=c['brace_self_weight'],brace_weight_factor=case['brace_weight_factor'],nodal_loads=[])
        if model['inputs']!=expected_inputs:
            raise ValueError('Solved model inputs differ from current case/configuration')
        g81=model.get('G81_demand_inputs')
        if (not isinstance(g81,list) or len(g81)!=3 or {r.get('member') for r in g81}!=set(LEVELS)
            or any(r.get('combination_id')!=cid or r.get('limit_state')!=combination['limit_state'] for r in g81)):
            raise ValueError('Signed model combination identity differs from enclosing case')
        if (model.get('first_order') is not True or model.get('bilateral_bars') is not True
            or model.get('source_input_fingerprint') != expected
            or model.get('diagnostics',{}).get('passed') is not True):
            raise ValueError('Demand must retain the checked bilateral first-order model')
        sect=model['inputs']['section'];p=ref['properties'];mat=demand['input_data']['properties']
        fields=dict(A_mm2=p['A_mm2'],I_strong_mm4=p['Ix_mm4'],I_weak_mm4=p['Iy_mm4'],
                    J_mm4=p['J_mm4'],Cw_mm6=p['Cw_mm6'],E_MPa=mat['E_MPa'],G_MPa=mat['G_MPa'])
        if sect['sectorial_section_id'] != demand['source_geometry']['content_sha256']:
            raise ValueError('Current sectorial section identity mismatch')
        for key,value in fields.items():
            if not math.isclose(a._number(sect[key],key,positive=True),value,rel_tol=2e-12,abs_tol=1e-9):
                raise ValueError('Demand section differs from current source: '+key)
        if (not math.isclose(sect['sc_y_mm'],p['centroid_xy_mm'][0]-p['shear_center_xy_mm'][0],rel_tol=2e-12,abs_tol=1e-9)
            or not math.isclose(sect['sc_z_mm'],0.,abs_tol=1e-9)):
            raise ValueError('Only the declared mouth-down monosymmetric current section is supported')
        L=demand['input_data']['L_mm']
        if model['inputs']['L_mm'] != L:raise ValueError('Demand physical span mismatch')
        ids=set()
        for level in LEVELS:
            beams=sorted((b for b in model['beams'] if b['girt']==level),key=lambda b:b['x_start_mm'])
            if not beams or beams[0]['x_start_mm']!=0. or beams[-1]['x_end_mm']!=L:
                raise ValueError('Missing physical member span')
            for index,b in enumerate(beams):
                if b['id'] in ids:raise ValueError('Duplicate physical segment id')
                ids.add(b['id'])
                if b['x_end_mm']<=b['x_start_mm'] or (index and b['x_start_mm']!=beams[index-1]['x_end_mm']):
                    raise ValueError('Physical segment gap or overlap')
                _polynomials(b)
        if len(ids)!=len(model['beams']):raise ValueError('Unknown member in demand model')
    return source,ref


def _polynomials(beam):
    """Require exact uniform-load fields; states do not constitute an envelope."""
    p=beam.get('normal_action_polynomials')
    if not isinstance(p,dict):raise ValueError('Missing exact N/My/Mz polynomial fields; do not infer the interaction maximum from component extrema')
    keys=('N_N','My_strong_Nmm','Mz_weak_Nmm')
    fields={k:a._poly(p[k],k,0 if k=='N_N' else 2) for k in keys}
    start=beam['x_start_mm'];length=beam['x_end_mm']-start
    for state in beam['states']:
        u=(state['x_mm']-start)/length
        if not 0.<=u<=1.:raise ValueError('State outside its physical segment')
        for k,poly in fields.items():
            if not math.isclose(float(poly(u)),state[k],rel_tol=2e-10,abs_tol=1e-7):
                raise ValueError('Exact normal field differs from saved state: '+k)
    return {k:[float(x) for x in poly.coef] for k,poly in fields.items()}


def _capacities(demand,config,source,ref):
    p=demand['input_data']['properties'];s=demand['cases'][0]['model']['inputs']['section']
    o=config['reference_origin'];ll=config['effective_lengths_mm']
    elastic=a.monossymmetric_elastic_compression(A_mm2=s['A_mm2'],I_sym_mm4=s['I_strong_mm4'],
        I_orth_mm4=s['I_weak_mm4'],J_mm4=s['J_mm4'],Cw_mm6=s['Cw_mm6'],x0_mm=s['sc_y_mm'],
        E_MPa=s['E_MPa'],G_MPa=s['G_MPa'],fy_MPa=p['fy_MPa'],
        effective_L_sym_mm=ll['symmetry'],effective_L_orth_mm=ll['orthogonal'],
        effective_L_torsion_mm=ll['torsion'],origin=p.get('property_origin',demand['input_data']['property_origin']),
        effective_lengths_origin=o)
    geom=dict(family='Ue',h_mm=p['h'],bf_mm=p['bf'],t_mm=p['t'],ri_mm=p['ri_mm'],lip_mm=p['lip'])
    local=a.fully_effective_U_Ue(**geom,A_mm2=s['A_mm2'],E_MPa=s['E_MPa'],
        stress_MPa=elastic['sigma_effective_MPa'],origin=o)
    dist=a.centered_compression_distortion(**{k:v for k,v in geom.items() if k!='ri_mm'},origin=o)
    widths=a.section_width_limits(local=local,t_mm=p['t'],bending_present=True,origin=o)
    compression=a.compression_capacity(elastic=elastic,local=local,distortion=dist,geometry_limits=widths,origin=o)
    if config.get('tension_connection') is None:
        tension=a.tension_capacity(Ag_mm2=s['A_mm2'],fy_MPa=p['fy_MPa'],fu_MPa=p['fu_MPa'],**config['tension'])
    else:
        from .tension_detail import capacity as detail_capacity
        tension=detail_capacity(config['tension_connection'],config['tension'],
            A_mm2=s['A_mm2'],t_mm=p['t'],h_mm=p['h'],ri_mm=p['ri_mm'],
            fy_MPa=p['fy_MPa'],fu_MPa=p['fu_MPa'])
    return dict(compression=dict(elastic=elastic,local=local,distortion=dist,width_limits=widths,capacity=compression),
        tension=tension,bending_scalar_source=copy.deepcopy(source),
        bending=copy.deepcopy(ref['resistances_exterior_primary']),
        scope='Full-span scalar reference denominators only. The isolated-source approval is not inherited by the 3D network.',
        actual_stability_model_qualified=False,N_M_B_qualified=False)


def calculate(demand,config):
    """Compute the full concomitant §9.9 arithmetic, not N+M+B acceptance."""
    source,ref=_validate(demand,config);caps=_capacities(demand,config,source,ref)
    source_hash=fingerprint(demand);records=[];L=demand['input_data']['L_mm']
    bending_map={'Mstrong_pos':'strong_positive','Mstrong_neg':'strong_negative',
                 'Mweak_pos':'weak_web_compressed','Mweak_neg':'weak_lips_compressed'}
    try:
        from ..three_girt_warping.application import recover_exported_state
    except ImportError:
        recover_exported_state=None
    for case in demand['cases']:
        if case['combination']['limit_state']!='ELU':continue
        for beam in case['model']['beams']:
            poly=_polynomials(beam);member=beam['girt']+'_full_physical_span'
            binding=dict(section_id=ref['id'],stability_member_id=member,region_id=beam['id'])
            den={}
            values=dict(Nc=caps['compression']['capacity']['Nc_Rd_N'],Nt=caps['tension']['Nt_Rd_N'])
            values.update({k:caps['bending'][v]['MRd_Nmm'] for k,v in bending_map.items()})
            for key,value in values.items():
                den[key]=a.denominator(key=key,value=value,**binding,
                    origin=config['reference_origin']+(' '+config['tension']['origin'] if key=='Nt' else ''),
                    member_issues=caps['compression']['capacity']['member_issues'] if key=='Nc' else ())
            row=a.interaction_segment(N_coeff=poly['N_N'],Mstrong_coeff=poly['My_strong_Nmm'],
                Mweak_coeff=poly['Mz_weak_Nmm'],capacities=den,
                combination_id=case['combination']['id'],**binding,segment_id=beam['id'],
                x_start_mm=beam['x_start_mm'],length_mm=beam['x_end_mm']-beam['x_start_mm'],
                origin='Current checked 7DOF fields; exact polynomial roots of the NBR signed-capacity sum; '+SIGN_MAP)
            for state in row['states']:
                # Retain every physical field at the SAME new interaction station.
                saved=next((s for s in beam['states'] if s['x_mm']==state['x_mm']),None)
                actual=(recover_exported_state(case['model'],beam,state['x_mm'])
                        if recover_exported_state is not None else saved)
                if actual is not None:
                    for key,expected in [('N_N',state['N_tension_positive_N']),('My_strong_Nmm',state['Mstrong_Nmm']),('Mz_weak_Nmm',state['Mweak_Nmm'])]:
                        if not math.isclose(actual[key],expected,rel_tol=2e-10,abs_tol=1e-7):
                            raise ValueError('Recovered interaction witness differs from exact normal field')
                    state['concomitant_7DOF_state']=copy.deepcopy(actual)
                else:
                    state['concomitant_7DOF_state']=None
                    state['torsion_recovery_note']='Exact normal witness available; B/T at this new position unavailable, never replaced by zero.'
                state['contributions']=None if state['numeric_index'] is None else {
                    label:(abs(state[field])/den[key]['value'] if key else 0.)
                    for label,field,key in zip(('axial','strong','weak'),
                        ('N_tension_positive_N','Mstrong_Nmm','Mweak_Nmm'),state['capacity_keys'])}
            row.update(girt=beam['girt'],physical_member_length_mm=L,
                stability_lengths_mm=copy.deepcopy(config['effective_lengths_mm']),denominators=den,
                N_M_B_qualified=False,H4_used_to_close_N_M_B=False,
                scalar_reference_criterion=None if row['maximum'] is None else
                    ('above_1' if row['maximum']['numeric_index']>1. else 'within_1'),
                actual_member_criterion=None,
                reference_member_limits_satisfied=not row['member_issues'])
            records.append(row)
    if not records:raise ValueError('No ELU combination for axial/bending resistance arithmetic')
    per_member={}
    for level in LEVELS:
        rows=[r for r in records if r['girt']==level];complete=[r for r in rows if r['maximum'] is not None]
        winner=max(complete,key=lambda r:r['maximum']['numeric_index']) if complete else None
        witness=None if winner is None else dict(combination_id=winner['combination_id'],segment_id=winner['segment_id'],state=winner['maximum'])
        per_member[level]=dict(ELU_segments=len(rows),arithmetic_complete_segments=len(complete),
            complete_reference_envelope=witness if len(complete)==len(rows) else None,
            partial_reference_maximum=witness if len(complete)!=len(rows) else None,
            missing_capacity_keys=sorted({k for r in rows for k in r['missing_capacity_keys']}),
            member_issues=sorted({k for r in rows for k in r['member_issues']}),whole_member_approved=False)
    out=dict(schema=SCHEMA,status='computed_reference_component',
        source_demand_sha256=source_hash,source_input_fingerprint=demand['input_fingerprint'],
        configuration=copy.deepcopy(config),source_geometry=copy.deepcopy(demand['source_geometry']),
        capacities=caps,rows=records,per_member=per_member,
        ELU_combinations=len({r['combination_id'] for r in records}),
        ELS_combinations_excluded=sum(c['combination']['limit_state']=='ELS' for c in demand['cases']),
        sign_mapping=SIGN_MAP,first_order=True,bilateral_bars=True,
        maximum_observed_abs_twist_at_exported_stations_rad=max(abs(state['phi_rad'])
            for case in demand['cases'] for beam in case['model']['beams'] for state in beam['states']),
        small_rotation_applicability_qualified=False,
        tie_strength_checked=False,analysis_8_1_qualified=False,
        physical_restraints_qualified=False,N_M_B_qualified=False,
        torsion_warping_shear_interaction_qualified=False,ELS_qualified=False,whole_member_approved=False,
        notes=['§9.9 uses same-section N and moments; separate combinations and joint sides are retained.',
            'Compression uses the full physical span. Force-introduction regions do not shorten effective buckling lengths.',
            'Compression KL/r<=200 is a member limit under §9.7.4 in the supplied 2010 edition; the distinct tensile L/r<=300 provision is a recommendation.',
            'N=0 requires no axial denominator. A nonzero tensile force, however small, requires Nt.',
            'Scalar §9.8.2 denominators are reused as explicit full-span reference values, not physical 3D stability approval.',
            'An index within 1 is arithmetic of the declared reference, not acceptance with T/B, second-order effects or actual connections.',
            'G8.1 and H4 remain separate. H4 alone is not used to certify N+M+B.'])
    from ..three_girt_shear import calculate_validated as calculate_web_shear
    try:out['web_shear_component']=calculate_web_shear(demand,ref)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:out['web_shear_error']=str(exc)
    from ..three_girt_scope import central
    if central(demand):
        from ..three_girt_local_stability import calculate_validated as calculate_local_B1, FIELD as B1_FIELD
        try:out[B1_FIELD]=calculate_local_B1(demand,out)
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:out['central_local_B1_error']=str(exc)
    out['content_sha256']=fingerprint(out)
    if fingerprint(demand)!=source_hash:raise AssertionError('Input demand was mutated')
    return out


def summary(result):
    return dict(schema=result['schema'],ELU_combinations=result['ELU_combinations'],
        ELS_combinations_excluded=result['ELS_combinations_excluded'],
        Nc_Rd_reference_N=result['capacities']['compression']['capacity']['Nc_Rd_N'],
        compression_KL_over_r=result['capacities']['compression']['elastic']['compression_slenderness'],
        Nt_Rd_N=result['capacities']['tension']['Nt_Rd_N'],
        maximum_observed_abs_twist_at_exported_stations_rad=result['maximum_observed_abs_twist_at_exported_stations_rad'],
        small_rotation_applicability_qualified=False,
        members={level:{k:copy.deepcopy(v) for k,v in record.items() if k not in ('complete_reference_envelope','partial_reference_maximum')}
            | {'complete_reference_index':None if record['complete_reference_envelope'] is None else record['complete_reference_envelope']['state']['numeric_index'],
               'partial_reference_index':None if record['partial_reference_maximum'] is None else record['partial_reference_maximum']['state']['numeric_index']}
            for level,record in result['per_member'].items()},
        N_M_B_qualified=False,whole_member_approved=False)


FIELD='NBR_axial_bending_component'


def attach(demand,config):
    """Attach a new explicit component without altering the original demand."""
    source=copy.deepcopy(demand);source.pop(FIELD,None)
    result=calculate(source,config)
    out=copy.deepcopy(source);out[FIELD]=result
    return out


def saved_component(demand):
    """Validate saved linkage only. No source lookup, solver or recomputation."""
    component=demand.get(FIELD)
    if component is None:return None
    if not isinstance(component,dict) or component.get('schema')!=SCHEMA:
        raise ValueError('Invalid saved NBR component schema')
    _check_digest(component,'content_sha256')
    source={k:v for k,v in demand.items() if k!=FIELD}
    if (component.get('source_demand_sha256')!=fingerprint(source)
        or component.get('source_input_fingerprint')!=demand.get('input_fingerprint')
        or any(component.get(k) is not False for k in ('N_M_B_qualified','whole_member_approved',
            'analysis_8_1_qualified','physical_restraints_qualified','torsion_warping_shear_interaction_qualified','ELS_qualified'))):
        raise ValueError('Saved NBR component differs from its current demand or exceeds its scope')
    return component
