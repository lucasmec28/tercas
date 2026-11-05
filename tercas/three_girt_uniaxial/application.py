"""Three independent full-span MSE bending components from current girt loads.

This deliberately changes the model. It does not scale the Vlasov solution,
reuse tie reactions, add gross twist, or claim a bound on the coupled network.
"""
import copy
import math
import warnings
from scipy.integrate import IntegrationWarning
from ..core import protocolo_ief as scalar
from ..three_girt_warping.application import fingerprint

FIELD='isolated_uniaxial_service_component'
REQUEST='isolated_uniaxial_service_requested_configuration'
ERROR='isolated_uniaxial_service_error'
SCHEMA='three_girt_isolated_uniaxial_MSE_v1'
CONFIG_SCHEMA='three_girt_isolated_uniaxial_choice_v1'
LEVELS=('upper','middle','lower')
FALSE_FLAGS=('ELS_qualified','global_stability_qualified','physical_ELS_approved','combined_ELS_approved','whole_member_approved',
    'coupled_network_response','network_reactions_reused','network_rigidities_modified',
    'torsional_displacement_included','tie_restraint_credit','bound_on_Vlasov_displacement',
    'effective_section_stress_qualified')
DOWNSTREAM=('horizontal_service_component','EN_normal_N_M_B_component','NBR_axial_bending_component')
EXCLUDED=(FIELD,REQUEST,ERROR,*DOWNSTREAM,'horizontal_service_requested_configuration','horizontal_service_error',
    'EN_normal_N_M_B_requested_configuration','EN_normal_N_M_B_error',
    'NBR_axial_bending_requested_configuration','NBR_axial_bending_error')
SCOPE=('Três vigas isoladas simplesmente apoiadas, cada uma no vão físico inteiro, sob sua carga horizontal distribuída atual. '
       'Ix efetivo variável pelo MSE uniaxial. Não é a resposta da rede Vlasov nem um limite conservador dela. '
       'N, flexão fraca, torção, empenamento, redistribuição e ações dos tirantes ficam fora apenas desta alternativa; '
       'as entradas e os resultados completos da rede são preservados.')


def source(demand):return {k:v for k,v in demand.items() if k not in EXCLUDED}


def number(value,name,positive=False):
    if type(value) not in (int,float) or not math.isfinite(value) or (positive and value<=0):
        raise ValueError(name+' must be a finite '+('positive ' if positive else '')+'number')
    return float(value)


def configuration(demand):
    return dict(schema=CONFIG_SCHEMA,enabled=True,demand_input_fingerprint=demand['input_fingerprint'],
        independent_members_declared=False,model_origin='',
        model='three_independent_full_span_simply_supported_uniaxial_members',
        direction='horizontal_Z_strong_bending_only',method='NBR14762_2010_9_8_5_MSE_variable_Ief')


def validate_configuration(demand,config):
    expected=configuration(demand)
    if not isinstance(config,dict) or set(config)!=set(expected):raise ValueError('Exact uniaxial alternative configuration required')
    if any(config[k]!=expected[k] for k in expected if k not in ('independent_members_declared','model_origin')):
        raise ValueError('Stale or unsupported uniaxial configuration')
    if config['independent_members_declared'] is not True or not isinstance(config['model_origin'],str) or not config['model_origin'].strip():
        raise ValueError('Declare the independent uniaxial model and its origin')


def criterion(data):
    wall=data['wall_els'];ref=wall['normal_reference_mm']
    ref=number(data['L_mm'] if ref is None else ref,'horizontal reference',True)
    denom=number(wall['normal_denominator'],'horizontal denominator',True)
    if not isinstance(wall['origin'],str) or not wall['origin'].strip():raise ValueError('Horizontal criterion origin required')
    return dict(reference_mm=ref,denominator=denom,limit_mm=ref/denom,origin=wall['origin'],
        scope='isolated_horizontal_component_only; no shorter analysis span from criterion or tie stations')


def properties(data):
    p=data['properties']
    if not isinstance(data['critical_origin'],str) or not data['critical_origin'].strip():raise ValueError('Own strong local critical provenance required')
    return dict(L_mm=number(data['L_mm'],'L',True),E_MPa=number(p['E_MPa'],'E',True),
        Ig_mm4=number(p['Ix_cm4'],'Ix',True)*1e4,Wg_mm3=number(p['Wx_cm3'],'Wx',True)*1e3,
        Ml_Nmm=number(data['Ml_Nmm'],'Ml',True),fy_MPa=number(p['fy_MPa'],'fy',True),
        critical_origin=data['critical_origin'],property_origin=data['property_origin'])


def beam_response(p,q,limit):
    """Same validated scalar law/integrator as the existing isolated app route."""
    q=number(q,'horizontal q');L=p['L_mm'];E=p['E_MPa'];Ig=p['Ig_mm4'];Ml=p['Ml_Nmm']
    m=abs(q)*L*L/8;imin=scalar.ief(Ig,m,Ml);gross=5*q*L**4/(384*E*Ig)
    sigma=m/p['Wg_mm3'];elastic=sigma<=p['fy_MPa']
    out=dict(q_Z_N_mm=q,max_abs_M_Nmm=m,x_max_abs_M_mm=L/2 if q else 0.,
        Ief_min_mm4=imin,Ief_min_over_Ig=imin/Ig,gross_uniaxial_deflection_mm=gross,
        constant_Ief_min_deflection_mm=5*q*L**4/(384*E*imin),
        sigma_gross_max_MPa=sigma,gross_elastic_guard=elastic,
        effective_section_stress_qualified=False,deflection_mm=None,x_mm=None,
        diagnostic_uniaxial_ratio=None,isolated_component_index=None,
        isolated_limit_satisfied=False,comparison='numerical_result_unavailable',numerical_warnings=[])
    try:
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always',IntegrationWarning)
            args=scalar.model(L,E,Ig,Ml,q,0.,L/2);x,d=scalar.peak(args)
        notes=[str(w.message) for w in seen if issubclass(w.category,IntegrationWarning)]
        if notes:
            out['numerical_warnings']=notes;return out
        number(x,'computed x');number(d,'computed displacement')
        tol=1e-8+1e-9*abs(d)
        if abs(d)<abs(gross)-tol or abs(d)>abs(out['constant_Ief_min_deflection_mm'])+tol:
            raise ArithmeticError('Variable-Ief response outside same-model integral bounds')
        ratio=abs(d)/limit
        out.update(deflection_mm=d,x_mm=x,diagnostic_uniaxial_ratio=ratio,
            isolated_component_index=ratio if elastic else None,
            isolated_limit_satisfied=bool(elastic and ratio<=1),
            comparison=('within_isolated_uniaxial_limit' if ratio<=1 else 'above_isolated_uniaxial_limit')
                if elastic else 'gross_elastic_model_exceeded')
    except (ValueError,ArithmeticError) as exc:out['numerical_warnings']=[str(exc)]
    return out


def calculate(demand,config):
    validate_configuration(demand,config)
    # Verify pinned geometry, local critical, original load allocation and
    # immutable solved-demand contract; do not solve or import capacities.
    from ..three_girt_axial.application import _validate,reference_configuration
    original,_=_validate(demand,reference_configuration(demand))
    data=demand['input_data'];p=properties(data);crit=criterion(data);cases=[]
    for case in demand['cases']:
        if case['combination']['limit_state']!='ELS':continue
        members={}
        for name,load in zip(LEVELS,case['loads']):
            r=beam_response(p,load['q_z_N_mm'],crit['limit_mm'])
            r['original_distributed_load']=copy.deepcopy(load)
            members[name]=r
        cases.append(dict(combination=copy.deepcopy(case['combination']),members=members))
    if not cases:raise ValueError('No current service combination')
    out=dict(schema=SCHEMA,configuration=copy.deepcopy(config),source_input_fingerprint=demand['input_fingerprint'],
        source_demand_sha256=fingerprint(source(demand)),source_geometry=copy.deepcopy(demand['source_geometry']),
        source_reference_id=original['reference_id'],properties=p,criterion=crit,cases=cases,
        ELS_combinations=len(cases),ELU_combinations_excluded=sum(c['combination']['limit_state']=='ELU' for c in demand['cases']),
        scope=SCOPE,formula='Ief=min(Ig,Ig*(1-0.22/lambda)/lambda) for lambda>0.673; otherwise Ig; lambda=sqrt(abs(M)/Ml)',
        displacement_method='Integral M(x)*unit_load_moment(x)/(E*Ief(x)), split at load and Ief transition points; full physical span',
        source='ABNT NBR14762:2010 9.8.5 MSE; Ml from the same own section and 9.8.2. No new load combination or resistance criterion.',
        gross_elastic_guard_scope='If even gross elastic bending stress exceeds fy, only mathematical displacement is retained. Passing this necessary guard does not certify effective-section stresses or physical ELS.',
        original_demand_unchanged=True,**{k:False for k in FALSE_FLAGS})
    out['content_sha256']=fingerprint(out);return out


def attach(demand,config):
    if any(k in demand for k in DOWNSTREAM):raise ValueError('Attach independent uniaxial alternative before service, EN and NBR')
    out=copy.deepcopy(demand);out.pop(FIELD,None);out[FIELD]=calculate(out,config);return out


def saved_component(demand):
    c=demand.get(FIELD)
    if c is None:return None
    if not isinstance(c,dict) or c.get('schema')!=SCHEMA:raise ValueError('Unknown saved uniaxial alternative')
    if c.get('content_sha256')!=fingerprint({k:v for k,v in c.items() if k!='content_sha256'}):raise ValueError('Saved uniaxial content changed')
    if c.get('source_demand_sha256')!=fingerprint(source(demand)) or c.get('source_input_fingerprint')!=demand.get('input_fingerprint'):
        raise ValueError('Saved uniaxial source changed')
    validate_configuration(demand,c['configuration'])
    if any(c.get(k) is not False for k in FALSE_FLAGS) or c.get('original_demand_unchanged') is not True:
        raise ValueError('Saved uniaxial scope was promoted')
    data=demand['input_data'];p=properties(data);crit=criterion(data)
    token=data.get('ue_family_reference',data.get('ue_reference',{}))
    if c['source_reference_id']!=token.get('reference_id') or c['scope']!=SCOPE:
        raise ValueError('Saved reference identity or model scope changed')
    if c['properties']!=p or c['criterion']!=crit or c['source_geometry']!=demand['source_geometry']:raise ValueError('Saved uniaxial geometry/criterion changed')
    original=[v for v in demand['cases'] if v['combination']['limit_state']=='ELS']
    if (len(original)!=c['ELS_combinations'] or [v['combination'] for v in c['cases']]!=[v['combination'] for v in original]
        or c['ELU_combinations_excluded']!=len(demand['cases'])-len(original)):raise ValueError('Saved uniaxial combination inventory changed')
    for case,old in zip(c['cases'],original):
        if set(case['members'])!=set(LEVELS):raise ValueError('Saved uniaxial member inventory changed')
        for name,load in zip(LEVELS,old['loads']):
            r=case['members'][name];q=load['q_z_N_mm'];L=p['L_mm'];m=abs(q)*L*L/8
            if r['original_distributed_load']!=load or r['q_Z_N_mm']!=q or r['max_abs_M_Nmm']!=m:
                raise ValueError('Saved uniaxial actions changed')
            if r['sigma_gross_max_MPa']!=m/p['Wg_mm3'] or r['gross_elastic_guard'] is not (r['sigma_gross_max_MPa']<=p['fy_MPa']):
                raise ValueError('Saved gross elastic guard changed')
            if r['effective_section_stress_qualified'] is not False:raise ValueError('Effective stress not qualified by scalar inertia')
            if r['numerical_warnings']:
                if any(r[k] is not None for k in ('deflection_mm','x_mm','diagnostic_uniaxial_ratio','isolated_component_index')) or r['comparison']!='numerical_result_unavailable' or r['isolated_limit_satisfied'] is not False:
                    raise ValueError('Numerical failure promoted to a result')
                continue
            d=number(r['deflection_mm'],'saved displacement');x=number(r['x_mm'],'saved position')
            if not math.isclose(x,L/2 if q else 0.,abs_tol=1e-7) or d*q<0:raise ValueError('Saved uniform-load displacement sign/position changed')
            if (r['Ief_min_mm4']!=scalar.ief(p['Ig_mm4'],m,p['Ml_Nmm'])
                or r['Ief_min_over_Ig']!=r['Ief_min_mm4']/p['Ig_mm4']
                or r['gross_uniaxial_deflection_mm']!=5*q*L**4/(384*p['E_MPa']*p['Ig_mm4'])
                or r['constant_Ief_min_deflection_mm']!=5*q*L**4/(384*p['E_MPa']*r['Ief_min_mm4'])):
                raise ValueError('Saved effective inertia invalid')
            tol=1e-8+1e-9*abs(d)
            if abs(d)<abs(r['gross_uniaxial_deflection_mm'])-tol or abs(d)>abs(r['constant_Ief_min_deflection_mm'])+tol:
                raise ValueError('Saved displacement outside the isolated integral bounds')
            ratio=abs(d)/crit['limit_mm'];elastic=r['gross_elastic_guard']
            expected=('within_isolated_uniaxial_limit' if ratio<=1 else 'above_isolated_uniaxial_limit') if elastic else 'gross_elastic_model_exceeded'
            if (r['diagnostic_uniaxial_ratio']!=ratio or r['isolated_component_index']!=(ratio if elastic else None)
                or r['comparison']!=expected or r['isolated_limit_satisfied'] is not bool(elastic and ratio<=1)):
                raise ValueError('Saved isolated criterion changed')
    return c
