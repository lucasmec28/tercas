"""Horizontal service response plus a sufficient LOCAL NORMAL MLE comparator.

No network is re-solved and no rigidity/reaction is scaled. This closes a useful
model comparison, not complete ELS, distortion, stability or torsional strength.
"""
import copy
import math
import numpy as np
from numpy.polynomial import polynomial as poly
from ..three_girt_en_normal import field_envelope as f
from ..three_girt_warping.application import fingerprint
from ..three_girt_warping.element import shape_physical
from ..three_girt_warping import exact_torsion as exact

FIELD='horizontal_service_component'
REQUEST='horizontal_service_requested_configuration'
ERROR='horizontal_service_error'
SCHEMA='three_girt_horizontal_service_local_gross_v1'
CONFIG_SCHEMA='three_girt_horizontal_service_choice_v1'
FALSE_FLAGS=('whole_member_approved','ELS_qualified','physical_ELS_approved',
    'global_stability_qualified','distortion_qualified','torsional_effective_stiffness_qualified',
    'shear_normal_interaction_qualified')
EXCLUDED=(FIELD,REQUEST,ERROR,'NBR_axial_bending_component','NBR_axial_bending_error',
    'NBR_axial_bending_requested_configuration','EN_normal_N_M_B_component',
    'EN_normal_N_M_B_error','EN_normal_N_M_B_requested_configuration')
LEVELS=('upper','middle','lower')


def source(demand):
    return {k:v for k,v in demand.items() if k not in EXCLUDED}


def configuration(demand):
    return dict(schema=CONFIG_SCHEMA,enabled=True,demand_input_fingerprint=demand['input_fingerprint'],
        nominal_intact_section_declared=False,model_origin='',
        displacement_definition='horizontal_Z_at_gross_centroid_relative_to_end_chord',
        method='NBR14762_2010_9_8_5_local_normal_sufficient_comparison_and_saved_linear_Vlasov')


def _number(value,name,positive=False):
    if type(value) not in (float,int) or not math.isfinite(value) or (positive and value<=0):
        raise ValueError(name+' must be a finite '+('positive ' if positive else '')+'number')
    return float(value)


def plate_limits(profile,E):
    """Uniform compression dominance without credit for flange edge stiffeners."""
    E=_number(E,'E',True);d=profile['geometry_external_mm'];t=_number(d['t'],'t',True)
    if d!={'h':100.,'b':50.,'lip':17.,'t':t,'ri':t}:raise ValueError('Only the pinned Ue100x50x17 ri=t topology')
    widths=(17-2*t,50-4*t,100-4*t,50-4*t,17-2*t)
    ns=profile['geometry_identity']['flat_segment_counts'];arcs=profile['geometry_identity']['arc_segment_counts']
    rows=[];start=0
    for i,(name,b,k) in enumerate(zip(('bottom_lip','bottom_flange','web','top_flange','top_lip'),widths,(.43,.43,4.,.43,.43))):
        if b<=0:raise ValueError('Invalid flat plate width')
        sigma=(.673*.95)**2*k*E*(t/b)**2
        # Downward rounding protects the acceptance boundary of this scalar
        # floating-point comparator; not a formal interval proof of mechanics.
        rows.append(dict(name=name,b_mm=b,k=k,sigma_integral_MPa=math.nextafter(sigma,-math.inf),
            start_segment=start,end_segment=start+ns[i]-1))
        start+=ns[i]+(arcs[i] if i<len(arcs) else 0)
    return rows


def _fiber_subset(fibers,ids):
    return [fibers['xy_mm'][i] for i in ids],[fibers['omega_over_Cw'][i] for i in ids]


def section_check(beam,section,profile,E,fy):
    """Same station/fiber N/M/B envelope; tension positive, compression=-min."""
    p=beam['normal_action_polynomials'];s=section['properties']
    fields={'N':p['N_N'],'Mx':[-v for v in p['My_strong_Nmm']],'My':[-v for v in p['Mz_weak_Nmm']]}
    coeff={'N':[1/s['A_mm2'],0,0],'Mx':[0,0,1/s['Ix_strong_mm4']],'My':[0,-1/s['Iy_weak_mm4'],0]}
    torsion=f.torsion_field(beam['torsion_state_parameters']);fibers=f.exterior_fibers(section)
    all_field=f.envelope(fields,coeff,fibers['xy_mm'],fibers['omega_over_Cw'],torsion)
    rows=[]
    for wall in plate_limits(profile,E):
        # N/M/omega are affine along each straight wall. Four outer vertices
        # bound the whole rectangular flat, not a sampling grid.
        ids=[i for i,v in enumerate(fibers['identities']) if
             (v['segment_index']==wall['start_segment'] and v['endpoint']==0) or
             (v['segment_index']==wall['end_segment'] and v['endpoint']==1)]
        xy,omega=_fiber_subset(fibers,ids);env=f.envelope(fields,coeff,xy,omega,torsion)
        compression=max(0.,-env['minimum']['sigma_MPa'])
        rows.append(dict(wall,compression_upper_MPa=compression,
            sufficient_integral=compression<=wall['sigma_integral_MPa'],
            governing=env['minimum']))
    elastic=abs(all_field['maximum_absolute']['sigma_MPa'])<=fy
    return dict(walls=rows,normal_elastic_sufficient=elastic,
        max_abs_normal_MPa=abs(all_field['maximum_absolute']['sigma_MPa']),
        normal_witness=all_field['maximum_absolute'],
        local_normal_gross_sufficient=bool(elastic and all(v['sufficient_integral'] for v in rows)),
        E_MPa=E,fy_MPa=fy,all_exterior_fibers_checked=all_field['section_fibers_checked'],
        scope='Local normal MLE sufficient comparator only; bends retained by declared MLE convention and included in normal-elastic guard. No distortion, shear or torsional-rigidity proof.')


def horizontal_field(model,beam):
    """Recover SC quartic and CG rotation from SAVED nodal kinematics."""
    sec=model['inputs']['section'];name=beam['girt'];level=LEVELS.index(name)
    y=(model['inputs']['upper_gap_mm'],0.,-model['inputs']['lower_gap_mm'])[level]
    nodes=[]
    for x in (beam['x_start_mm'],beam['x_end_mm']):
        matches=[r for r in model['nodes'] if r['xyz_CG_mm']==[x,y,0.]]
        if len(matches)!=1:raise ValueError('Unique physical endpoint node required')
        nodes.append(matches[0]['displacements'])
    a,b=nodes;L=beam['length_mm'];sy=_number(sec['sc_y_mm'],'sc_y')
    w=shape_physical(a['uz']+sy*a['rx'],-a['ry'],b['uz']+sy*b['rx'],-b['ry'],
        L,model['inputs']['loads'][level]['q_z_N_mm'],sec['E_MPa']*sec['I_strong_mm4'])
    # Convert polynomial from local x to normalized t in [0,1].
    coefficients=[float(v*L**i) for i,v in enumerate(w)]
    params=copy.deepcopy(beam['torsion_state_parameters'])
    if params['nodal_phi_psi']!=[a['rx'],a['psi'],b['rx'],b['psi']]:
        raise ValueError('Saved nodal torsion/interval mismatch')
    return dict(polynomial_SC_mm=coefficients,phi_factor_mm=-sy,torsion=params,
        x_start_mm=beam['x_start_mm'],length_mm=L,
        observation='horizontal Z at gross centroid; both member end translations and twists fixed, so end chord is zero')


def displacement_function(field):
    p=field['polynomial_SC_mm'];q=_number(field['phi_factor_mm'],'phi factor')
    if len(p)!=5:raise ValueError('Quartic SC displacement required')
    p=[_number(v,'coefficient') for v in p];a=field['torsion']
    L,S,D,m=(a[k] for k in ('L_mm','GJ_Nmm2','ECw_Nmm4','m_SC_N'))
    c=exact.constants(L,S,D,m,a['nodal_phi_psi'])
    def value(t,derivative=0):
        t=_number(t,'t')
        if not 0<=t<=1:raise ValueError('Normalized station outside physical interval')
        normal=float(poly.polyval(t,poly.polyder(p,derivative)))
        phi=float(exact.basis(t,L,S,D,derivative)@c+exact.particular(t,L,S,D,m,derivative))*L**derivative
        result=normal+q*phi
        if not math.isfinite(result):raise ArithmeticError('Nonfinite displacement derivative')
        return result
    return value


def horizontal_extrema(field):
    """All stationary points: D5 is a hyperbolic pair, then Rolle D4..D1.

    For k=0 the fifth derivative is identically zero and D4 is constant;
    the same monotone recursion gives the quartic's cubic stationary roots.
    """
    value=displacement_function(field)
    knots=[0.,1.]
    for order in (5,4,3,2,1):
        roots=f._monotone_roots(lambda t:value(t,order),knots)
        knots=f._distinct([0.,1.]+roots)
    rows=[dict(t=t,x_mm=field['x_start_mm']+field['length_mm']*t,
               horizontal_CG_mm=value(t),SC_flexural_mm=float(poly.polyval(t,field['polynomial_SC_mm']))) for t in knots]
    for r in rows:r['rotation_contribution_mm']=r['horizontal_CG_mm']-r['SC_flexural_mm']
    return dict(maximum_absolute=max(rows,key=lambda r:abs(r['horizontal_CG_mm'])),
        stationary_candidates=rows,method='Analytical derivative Rolle partition D5 to D1; no station grid or added extrema of separate fields')


def calculate(demand,config):
    expected=configuration(demand)
    if not isinstance(config,dict) or set(config)!=set(expected):raise ValueError('Exact service configuration required')
    for k in expected:
        if k not in ('nominal_intact_section_declared','model_origin') and config[k]!=expected[k]:raise ValueError('Stale or unsupported service configuration')
    if config['nominal_intact_section_declared'] is not True or not isinstance(config['model_origin'],str) or not config['model_origin'].strip():
        raise ValueError('Declare intact nominal section and origin for the service model')
    from ..three_girt_axial.application import _validate,reference_configuration
    _validate(demand,reference_configuration(demand))
    from ..three_girt_en_normal.application import _profile_and_section
    profile,section=_profile_and_section(demand);data=demand['input_data'];E=_number(data['properties']['E_MPa'],'E',True)
    fy=_number(data['properties']['fy_MPa'],'fy',True)
    if E!=200000.:raise ValueError('MLE service comparator scope requires E=200000 MPa')
    wall=data['wall_els'];reference=wall['normal_reference_mm']
    reference=_number(data['L_mm'] if reference is None else reference,'horizontal reference length',True)
    denominator=_number(wall['normal_denominator'],'horizontal denominator',True)
    if not isinstance(wall.get('origin'),str) or not wall['origin'].strip():raise ValueError('Horizontal criterion origin required')
    limit=reference/denominator;cases=[]
    for case in demand['cases']:
        if case['combination']['limit_state']!='ELS':continue
        records=[]
        for beam in case['model']['beams']:
            check=section_check(beam,section,profile,E,fy)
            field=horizontal_field(case['model'],beam);env=horizontal_extrema(field)
            records.append(dict(girt=beam['girt'],segment_id=beam['id'],
                x_start_mm=beam['x_start_mm'],x_end_mm=beam['x_end_mm'],section=check,
                horizontal_field=field,horizontal_envelope=env))
        # One failed plate anywhere invalidates the gross-compatible response
        # of this entire connected network, not only its own member segment.
        sufficient=all(r['section']['local_normal_gross_sufficient'] for r in records)
        members={}
        for name in LEVELS:
            rows=[r for r in records if r['girt']==name]
            winner=max((r['horizontal_envelope']['maximum_absolute']|{'segment_id':r['segment_id']} for r in rows),key=lambda r:abs(r['horizontal_CG_mm']))
            ratio=abs(winner['horizontal_CG_mm'])/limit
            members[name]=dict(witness=winner,diagnostic_gross_ratio=ratio,
                comparison=('within_declared_limit_in_gross_linear_model' if ratio<=1 else 'above_declared_limit_in_gross_linear_model') if sufficient else 'local_normal_gross_proof_inconclusive',
                horizontal_limit_satisfied_in_declared_model=bool(sufficient and ratio<=1),
                qualified_complete_ELS_index=None)
        cases.append(dict(combination=copy.deepcopy(case['combination']),segments=records,
            network_local_normal_gross_sufficient=sufficient,members=members))
    if not cases:raise ValueError('No service combinations in the current demand')
    out=dict(schema=SCHEMA,source_input_fingerprint=demand['input_fingerprint'],
        source_demand_sha256=fingerprint(source(demand)),configuration=copy.deepcopy(config),
        criterion=dict(horizontal_limit_mm=limit,reference_mm=reference,denominator=denominator,origin=wall['origin'],
            geometry_scope='Entire member; tie stations do not shorten the physical analysis span or create a fixed reference chord'),
        source_geometry=copy.deepcopy(demand['source_geometry']),cases=cases,
        ELS_combinations=len(cases),ELU_combinations_excluded=sum(c['combination']['limit_state']=='ELU' for c in demand['cases']),
        sufficient_combinations=sum(c['network_local_normal_gross_sufficient'] for c in cases),
        original_reactions_and_rigidities_unchanged=True,**{k:False for k in FALSE_FLAGS})
    out['content_sha256']=fingerprint(out);return out


def attach(demand,config):
    if 'NBR_axial_bending_component' in demand or 'EN_normal_N_M_B_component' in demand:
        raise ValueError('Attach service snapshot before EN and NBR to preserve their source hashes')
    out=copy.deepcopy(demand);out.pop(FIELD,None);out[FIELD]=calculate(out,config);return out


def saved_component(demand):
    c=demand.get(FIELD)
    if c is None:return None
    if not isinstance(c,dict) or c.get('schema')!=SCHEMA:raise ValueError('Unknown saved service schema')
    if c.get('content_sha256')!=fingerprint({k:v for k,v in c.items() if k!='content_sha256'}):raise ValueError('Saved service component changed')
    if c.get('source_demand_sha256')!=fingerprint(source(demand)) or c.get('source_input_fingerprint')!=demand.get('input_fingerprint'):
        raise ValueError('Service component source changed; calculate again')
    if any(c.get(k) is not False for k in FALSE_FLAGS):raise ValueError('Service component exceeds qualified scope')
    config=c.get('configuration');expected_config=configuration(demand)
    if not isinstance(config,dict) or set(config)!=set(expected_config) or any(config[k]!=expected_config[k] for k in expected_config if k not in ('nominal_intact_section_declared','model_origin')):
        raise ValueError('Saved service configuration changed')
    if config['nominal_intact_section_declared'] is not True or not isinstance(config['model_origin'],str) or not config['model_origin'].strip():
        raise ValueError('Saved model declaration missing')
    wall=demand['input_data']['wall_els'];reference=wall['normal_reference_mm']
    reference=demand['input_data']['L_mm'] if reference is None else reference
    if (c['criterion']['reference_mm']!=reference or c['criterion']['denominator']!=wall['normal_denominator']
        or c['criterion']['origin']!=wall['origin'] or c['source_geometry']!=demand['source_geometry']):
        raise ValueError('Saved criterion or source geometry changed')
    source_cases=[case for case in demand['cases'] if case['combination']['limit_state']=='ELS']
    if [case['combination'] for case in c['cases']]!=[case['combination'] for case in source_cases] or c['ELU_combinations_excluded']!=len(demand['cases'])-len(source_cases):
        raise ValueError('Saved service source combination inventory changed')
    for case,source_case in zip(c['cases'],source_cases):
        if [(r['segment_id'],r['girt'],r['x_start_mm'],r['x_end_mm']) for r in case['segments']]!=[(r['id'],r['girt'],r['x_start_mm'],r['x_end_mm']) for r in source_case['model']['beams']]:
            raise ValueError('Saved service source interval inventory changed')
    limit=_number(c['criterion']['horizontal_limit_mm'],'saved horizontal limit',True)
    if limit!=c['criterion']['reference_mm']/c['criterion']['denominator']:
        raise ValueError('Saved horizontal limit identity changed')
    if c['ELS_combinations']!=len(c['cases']) or not c['cases']:
        raise ValueError('Saved service combination inventory changed')
    sufficient_count=0
    for case in c['cases']:
        if case['combination']['limit_state']!='ELS' or not case['segments']:
            raise ValueError('Saved service limit state changed')
        for record in case['segments']:
            section=record['section']
            if len(section['walls'])!=5:raise ValueError('Saved five-wall proof incomplete')
            for wall in section['walls']:
                expected=wall['compression_upper_MPa']<=wall['sigma_integral_MPa']
                if wall['sufficient_integral'] is not expected:
                    raise ValueError('Saved local comparison changed')
            elastic=section['max_abs_normal_MPa']<=section['fy_MPa']
            if section['normal_elastic_sufficient'] is not elastic or section['local_normal_gross_sufficient'] is not bool(elastic and all(w['sufficient_integral'] for w in section['walls'])):
                raise ValueError('Saved normal-elastic/local conclusion changed')
        sufficient=all(r['section']['local_normal_gross_sufficient'] for r in case['segments'])
        if case['network_local_normal_gross_sufficient'] is not sufficient or set(case['members'])!=set(LEVELS):
            raise ValueError('Saved network coverage changed')
        sufficient_count+=sufficient
        for name,member in case['members'].items():
            expected=max((r['horizontal_envelope']['maximum_absolute']|{'segment_id':r['segment_id']} for r in case['segments'] if r['girt']==name),key=lambda r:abs(r['horizontal_CG_mm']))
            ratio=abs(expected['horizontal_CG_mm'])/limit
            comparison=('within_declared_limit_in_gross_linear_model' if ratio<=1 else 'above_declared_limit_in_gross_linear_model') if sufficient else 'local_normal_gross_proof_inconclusive'
            if (member['witness']!=expected or member['diagnostic_gross_ratio']!=ratio or member['comparison']!=comparison
                or member['horizontal_limit_satisfied_in_declared_model'] is not bool(sufficient and ratio<=1)
                or member['qualified_complete_ELS_index'] is not None):
                raise ValueError('Saved horizontal comparison changed')
    if sufficient_count!=c['sufficient_combinations']:
        raise ValueError('Saved sufficient combination count changed')
    return c
