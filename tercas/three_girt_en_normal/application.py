"""Conditional EN normal/shear/interaction section criteria on current 7DOF demand.

Only demonstrated pure effective sections at ULS are admitted. Reduced axial
sections carry an explicit centroid shift and require moment transport. The borrowed
NBR adapter validates the immutable current demand/source contract ONLY; no
NBR denominator or AISI capacity participates in this calculation. The input
load combinations and existing structural E remain unchanged and are labelled.
"""
import copy
import hashlib
import json
import math
import itertools
from fractions import Fraction
from pathlib import Path
from . import field_envelope as f
from . import shear_interaction as si
from .en1993_normal_components import build_component_sections,verify_component_sections

FIELD='EN_normal_N_M_B_component'
LEGACY_SCHEMA='three_girt_EN_normal_N_M_B_integral_v1'
LEGACY_SHEAR_SCHEMA='three_girt_EN_normal_shear_interaction_integral_v2'
LEGACY_EFFECTIVE_SCHEMA='three_girt_EN_normal_shear_effective_sections_v3'
SCHEMA='three_girt_EN_normal_shear_signed_union_v4'
CONFIG_SCHEMA='three_girt_EN_normal_N_M_B_choice_v1'
REQUEST='EN_normal_N_M_B_requested_configuration'
ERROR='EN_normal_N_M_B_error'
LEVELS=('upper','middle','lower')
FALSE_FLAGS=('whole_member_approved','physical_geometry_verified','physical_analysis_qualified',
    'complete_EN_6_1_6_verified','shear_normal_interaction_qualified','global_stability_qualified',
    'net_section_fracture_qualified','ELS_qualified','NBR_full_member_qualified')
EXCLUDED=(FIELD,REQUEST,ERROR,'NBR_axial_bending_component','NBR_axial_bending_error',
          'NBR_axial_bending_requested_configuration')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        allow_nan=False,separators=(',',':')).encode()).hexdigest()


def mechanical_source(demand):
    return {k:v for k,v in demand.items() if k not in EXCLUDED}


def reference_configuration(demand):
    return dict(schema=CONFIG_SCHEMA,enabled=True,
        demand_input_fingerprint=demand['input_fingerprint'],
        section_model='current_nominal_intact_faceted_thin_wall',
        intact_section_model_declared=False,section_model_origin='',
        reference_basis='EN1993-1-3:2006 6.1.6 normal component; fixed gammaM0=1; not full EN design')


def _validate_configuration(demand,config):
    expected=reference_configuration(demand)
    if not isinstance(config,dict) or set(config)!=set(expected):raise ValueError('Exact separate EN normal configuration required')
    for k in ('schema','enabled','demand_input_fingerprint','section_model','reference_basis'):
        if config[k]!=expected[k]:raise ValueError('Unsupported or stale EN normal configuration: '+k)
    if config['intact_section_model_declared'] is not True:
        raise ValueError('Declare the intact nominal section model; holes/cut-outs cannot default to gross geometry')
    if not isinstance(config['section_model_origin'],str) or not config['section_model_origin'].strip():
        raise ValueError('The intact-section model needs an explicit origin/assumption')


def _component_key(axis,sign):
    if sign==0:return None
    return ('N_tension' if sign>0 else 'N_compression') if axis=='N' else axis+('_positive' if sign>0 else '_negative')



def _transport_polynomials(original,certificate):
    """Transport the original actions once from gross CG to axial effective CG.

    EN13 6.1.3/6.1.9 with tension-positive N: Mx_corr=Mx-N*ey,
    My_corr=My+N*ex. The pure axial coefficient stays uniform 1/Aeff.
    This model admits constant N on each beam; hence d(N*e)/dx=0 and the
    transverse shear from moment derivatives is unchanged. A blocked N never
    receives a fabricated centroid or a stress evaluation.
    """
    if set(original)!={'N','Mx','My'} or len(original['N'])!=1:
        raise ValueError('Centroid transport requires exactly constant N on each current beam')
    for axis,values in original.items():
        if not isinstance(values,(list,tuple)) or not 1<=len(values)<=(1 if axis=='N' else 3):
            raise ValueError('Unexpected degree for centroid transport')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
            raise ValueError('Finite original action coefficients required')
    n=original['N'][0]
    if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n):
        raise ValueError('Finite signed constant axial action required')
    corrected={axis:list(values) for axis,values in original.items()};key=_component_key('N',n)
    record=None if key is None else certificate['components'][key]
    if record is not None and not record['eligible']:
        return corrected,dict(available=False,status='blocked_axial_section_no_transport_or_stress',
            axial_component=key,centroid_shift_from_gross_mm=None,
            original_polynomials_R01=copy.deepcopy(original),corrected_polynomials_R01=None,
            additional_Mx_Nmm=None,additional_My_Nmm=None)
    shift=[0.,0.] if record is None else record['centroid_shift_from_gross_mm']
    if len(shift)!=2 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in shift):
        raise ValueError('Finite effective axial centroid required')
    ex,ey=shift;dx=-n*ey;dy=n*ex
    corrected['Mx'][0]=math.fsum([corrected['Mx'][0],dx])
    corrected['My'][0]=math.fsum([corrected['My'][0],dy])
    if not all(math.isfinite(v) for a in corrected.values() for v in a):
        raise ValueError('Centroid transport exceeds finite arithmetic')
    return corrected,dict(available=True,status='transported_from_gross_to_axial_effective_centroid',
        axial_component=key,centroid_shift_from_gross_mm=list(shift),
        original_polynomials_R01=copy.deepcopy(original),corrected_polynomials_R01=copy.deepcopy(corrected),
        additional_Mx_Nmm=dx,additional_My_Nmm=dy,
        convention='R01, N tension positive; Mx_corr=Mx-N*ey; My_corr=My+N*ex',
        axial_stress='Uniform N/Aeff,N; centroid moments are included ONLY in the corrected bending actions',
        shear_derivatives_unchanged=True,original_network_actions_and_rigidities_unchanged=True)


def _normal_action_state(state,transport):
    if not transport['available']:raise ValueError('No stress witness for a blocked axial section')
    original=dict(N=state['N_N'],Mx=-state['My_strong_Nmm'],My=-state['Mz_weak_Nmm'])
    expected=transport['original_polynomials_R01']['N'][0]
    if not math.isclose(original['N'],expected,rel_tol=2e-10,abs_tol=1e-6):
        raise ValueError('Recovered axial action differs from its constant beam field')
    ex,ey=transport['centroid_shift_from_gross_mm']
    additional=dict(Mx=-original['N']*ey,My=original['N']*ex)
    corrected=dict(N=original['N'],Mx=math.fsum([original['Mx'],additional['Mx']]),
        My=math.fsum([original['My'],additional['My']]))
    return corrected,dict(axial_component=transport['axial_component'],
        centroid_shift_from_gross_mm=[ex,ey],original_actions_R01=original,
        additional_moments_R01=additional,corrected_actions_R01=corrected,
        convention=transport['convention'])

def _integral_sign_intervals(polynomials,certificate):
    """Join adjacent pieces only when every possible eligible operator is equal.

    Required signs are retained exactly, including sub-ulp pockets. A blocked
    section never coalesces with an eligible one or acquires a gross fallback.
    Distinct My operators keep their bracket; unrelated identical Mx operators
    do not force extra full-section passes.
    """
    intervals=f.sign_intervals(polynomials)
    def signature(row):
        result=[]
        for axis in ('N','Mx','My'):
            operators=[]
            for sign in row['required_signs'][axis]:
                key=_component_key(axis,sign)
                if key is None:operator=('zero',)
                else:
                    record=certificate['components'][key]
                    operator=('eligible',*record['sigma_coefficients_c0_cx_cy']) if record['eligible'] else ('blocked',key)
                if operator not in operators:operators.append(operator)
            result.append(tuple(sorted(operators)))
        return tuple(result)
    merged=[];last_signature=None
    for row in intervals:
        sig=signature(row)
        if merged and sig==last_signature and merged[-1]['right']==row['left']:
            previous=merged[-1];previous['right']=row['right']
            previous['required_signs']={axis:sorted(set(previous['required_signs'][axis]+row['required_signs'][axis]))
                                        for axis in ('N','Mx','My')}
            previous['sign_root_neighborhood']|=row['sign_root_neighborhood']
            previous['coalesced_exact_sign_intervals']=previous.get('coalesced_exact_sign_intervals',1)+1
            previous['coalescence_proof']='Identical sets of eligible signed stress operators; all exact required signs retained'
        else:merged.append(copy.deepcopy(row));last_signature=sig
    return merged


def _profile_and_section(demand):
    from ..torsion_study import section_for,PINS
    section=section_for(demand['input_data']);t=demand['input_data']['properties']['t']
    path=Path(__file__).resolve().parents[1]/'data'/'torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINS[t]:raise ValueError('Current own section bytes changed')
    return json.loads(raw),section


def _witness(result,case,beam,polys,coefficients,torsion,fibers,limit,transport):
    from ..three_girt_warping.application import recover_exported_state
    witness=copy.deepcopy(result)
    t=witness['t'];x=beam['x_start_mm']+(beam['x_end_mm']-beam['x_start_mm'])*t
    state=recover_exported_state(case['model'],beam,x)
    actual,reference=_normal_action_state(state,transport)
    pos=fibers['xy_mm'][witness['section_fiber_index']];omega=fibers['omega_over_Cw'][witness['section_fiber_index']]
    terms={}
    for axis in ('N','Mx','My'):
        value=sum(a*t**i for i,a in enumerate(polys[axis]))
        if not math.isclose(value,actual[axis],rel_tol=2e-10,abs_tol=1e-6):raise ValueError('Normal witness differs from current signed actions')
        coef=coefficients.get(axis)
        terms[axis]=0. if coef is None else actual[axis]*(coef[0]+coef[1]*pos[0]+coef[2]*pos[1])
    terms['B']=state['B_equilibrium_Nmm2']*omega
    total=math.fsum(terms.values())
    if not math.isclose(total,witness['sigma_MPa'],rel_tol=2e-10,abs_tol=2e-7):raise ArithmeticError('Concomitant witness stress mismatch')
    witness.update(x_mm=x,side='right' if x==beam['x_start_mm'] else 'left' if x==beam['x_end_mm'] else 'interior',
        combination_id=case['combination']['id'],girt=beam['girt'],segment_id=beam['id'],
        section_fiber=copy.deepcopy(fibers['identities'][witness['section_fiber_index']]),
        stress_contributions_MPa=terms,concomitant_7DOF_state=state,normal_action_reference=reference,
        normal_contribution_convention='Uniform axial term plus corrected signed bending actions, with centroid moments included exactly once',
        normal_index=abs(total)/limit,normal_limit_MPa=limit,
        witness_scope='Exterior vertex of a faceted thin-wall rectangle; omega constant through thickness')
    return witness


def _shear_witness(witness,case,beam,section,coefficients,transport):
    from ..three_girt_warping.application import recover_exported_state
    import numpy as np
    w=copy.deepcopy(witness);x=beam['x_start_mm']+beam['length_mm']*w['t']
    state=recover_exported_state(case['model'],beam,x)
    pos=np.asarray(w['xy_relative_to_gross_CG_mm']);u=w['u'];i=w['segment_index']
    props=section['properties'];th=section['thickness_mm']
    static=np.asarray(section['segment_static_coefficients'][i])@np.array([1.,u,u*u])
    omega=(1-u)*section['omega_nodes_mm2'][i]+u*section['omega_nodes_mm2'][i+1]
    physical,reference=_normal_action_state(state,transport)
    normal={axis:0. if coefficients.get(axis) is None else
        physical[axis]*(coefficients[axis][0]+np.asarray(coefficients[axis][1:])@pos)
        for axis in physical}
    normal['B']=state['B_equilibrium_Nmm2']*omega/props['Cw_mm6']
    shear=dict(Vx=-state['Vy_N']*static[0]/props['Iy_weak_mm4']/th,
        Vy=-state['Vz_N']*static[1]/props['Ix_strong_mm4']/th,
        warping=-state['T_w_Nmm']*static[2]/props['Cw_mm6']/th,
        Saint_Venant=-w['thickness_face_sign']*state['T_SV_Nmm']*th/props['J_mm4'])
    if not math.isclose(math.fsum(normal.values()),w['sigma_MPa'],rel_tol=3e-10,abs_tol=2e-7):
        raise ArithmeticError('Concomitant exterior normal/shear witness mismatch')
    if not math.isclose(math.fsum(shear.values()),w['tau_MPa'],rel_tol=3e-10,abs_tol=2e-7):
        raise ArithmeticError('Concomitant shear witness mismatch')
    w.update(x_mm=x,combination_id=case['combination']['id'],girt=beam['girt'],segment_id=beam['id'],
        side=state['side'],concomitant_7DOF_state=state,normal_contributions_MPa=normal,normal_action_reference=reference,
        shear_contributions_MPa=shear,omega_mm2=omega,
        witness_scope='Same longitudinal station, contour coordinate and signed wall face')
    return w



def _exact_actions(polynomials,t):
    """Canonical binary64 polynomials evaluated over rationals, never isclose signs."""
    q=Fraction(float(t))
    return {axis:sum((Fraction(float(v))*q**i for i,v in enumerate(values)),Fraction(0))
            for axis,values in polynomials.items()}


def _coefficient_branches(interval,certificate):
    choices=[]
    for axis in ('N','Mx','My'):
        keys=[_component_key(axis,s) for s in interval['required_signs'][axis] if s]
        unique=[]
        for key in keys:
            row=certificate['components'][key]
            if not row['eligible']:raise ValueError('Cannot extend an ineligible signed section')
            coefficient=row['sigma_coefficients_c0_cx_cy']
            if not all(math.isfinite(v) for v in coefficient):raise ValueError('Nonfinite signed coefficient')
            if not any(c==coefficient for _,c in unique):unique.append((key,coefficient))
        choices.append(unique or [(None,None)])
    return [(dict(zip(('N','Mx','My'),(v[0] for v in branch))),
             {axis:value[1] for axis,value in zip(('N','Mx','My'),branch) if value[1] is not None})
            for branch in itertools.product(*choices)]


def _physical_witness_evaluator(case,beam,section,polys,torsion,certificate,transport,limit,*,proposal_only=False,prune=True,fiber_data=None):
    """Rebuild candidates with their REAL signed sections and same recovered state.

    Recovery disagreement in sign rejects the candidate, even if isclose would
    accept its magnitude. Rejection never discards the interval upper bound.
    Cached recovery is shared across all facets and artificially extended branches.
    """
    from ..three_girt_warping.application import recover_exported_state
    import numpy as np
    cache={};exact_cache={};weight_cache={};discarded={};best_sample=[-1.,-1.,-1.];props=section['properties'];th=section['thickness_mm']
    # calculate already builds these immutable section identities once. Reuse
    # them only inside that calculation; each persisted witness still copies
    # its identity and is recovered/validated independently.
    if fiber_data is None:fiber_data=f.exterior_fibers(section)
    def reject(reason):
        discarded[reason]=discarded.get(reason,0)+1
        return None
    def evaluate(candidate):
        w=candidate.copy();t=w['t'];x=beam['x_start_mm']+beam['length_mm']*t
        # Candidate pruning only weakens L; it never changes U or claims an
        # exact maximum. Avoid expensive network recovery for inferior points.
        if t not in exact_cache:
            exact=_exact_actions(polys,t)
            signs={axis:(value>0)-(value<0) for axis,value in exact.items()}
            exact_cache[t]=(exact,signs,{axis:float(value) for axis,value in exact.items()})
        exact,signs,exact_float=exact_cache[t]
        keys={axis:_component_key(axis,sign) for axis,sign in signs.items()}
        pos=w['xy_relative_to_gross_CG_mm'];u=w['u'];i=w['segment_index']
        omega=(1-u)*section['omega_nodes_mm2'][i]+u*section['omega_nodes_mm2'][i+1]
        canonical={};proposal_scale=0.
        for axis,key in keys.items():
            if key is None:canonical[axis]=0.;continue
            record=certificate['components'][key]
            if not record['eligible']:return reject('physical_signed_component_not_eligible')
            cache_key=(key,i,u,w['thickness_face_sign'])
            if cache_key not in weight_cache:
                c=record['sigma_coefficients_c0_cx_cy']
                weight_cache[cache_key]=(math.fsum((c[0],c[1]*pos[0],c[2]*pos[1])),
                    sum(abs(v) for v in polys[axis])*(abs(c[0])+abs(c[1]*pos[0])+abs(c[2]*pos[1])))
            weight,scale=weight_cache[cache_key]
            canonical[axis]=exact_float[axis]*weight;proposal_scale+=scale
        canonical['B']=f.bimoment(torsion,t)*omega/props['Cw_mm6']
        cs=math.fsum(canonical.values());ct=w['tau_MPa']
        scores=[abs(cs)/limit if u in (0.,1.) else -1.,abs(ct)*math.sqrt(3)/limit,
                math.hypot(cs,math.sqrt(3)*ct)/(1.1*limit)]
        if prune and all(value<=best for value,best in zip(scores,best_sample)):return None
        if proposal_only:
            # This is a physical CANONICAL polynomial point, not a recovered
            # network witness. It may guide refinement, but is never persisted
            # as an accepted witness until final recovery below succeeds.
            h=torsion['h'];bc=.5 if h==0 else 2*(math.sinh(h/2)/h)**2;bd=1. if h==0 else math.sinh(h)/h
            proposal_scale+=abs(omega/props['Cw_mm6'])*(abs(torsion['B0'])+abs(torsion['U'])*bc+abs(torsion['V'])*bd)
            w.update(sigma_MPa=cs,equivalent_MPa=math.hypot(cs,math.sqrt(3)*ct),
                witness_error_MPa=dict(sigma=128*np.finfo(float).eps*max(1.,proposal_scale),tau=0.),
                selected_component_keys=keys,canonical_action_signs=signs,
                canonical_signed_actions_R01=exact_float)
            for j,value in enumerate(scores):best_sample[j]=max(best_sample[j],value)
            return w
        if t not in cache:
            state=recover_exported_state(case['model'],beam,x)
            actual,reference=_normal_action_state(state,transport)
            error=None
            for axis,value in actual.items():
                if not math.isfinite(value):raise ValueError('Nonfinite recovered action')
                if ((value>0)-(value<0))!=signs[axis]:error='recovered_and_exact_polynomial_sign_disagree'
                elif not math.isclose(value,float(exact[axis]),rel_tol=2e-10,abs_tol=1e-6):
                    error='recovered_and_exact_polynomial_magnitude_disagree'
            cache[t]=(state,actual,reference,exact,signs,error)
        state,actual,reference,exact,signs,error=cache[t]
        if error:return reject(error)
        keys={axis:_component_key(axis,sign) for axis,sign in signs.items()}
        pos=w['xy_relative_to_gross_CG_mm'];u=w['u'];i=w['segment_index']
        omega=(1-u)*section['omega_nodes_mm2'][i]+u*section['omega_nodes_mm2'][i+1]
        normal={};canonical={};scale=0.
        for axis,key in keys.items():
            if key is None:normal[axis]=canonical[axis]=0.;continue
            record=certificate['components'][key]
            if not record['eligible']:return reject('physical_signed_component_not_eligible')
            c=record['sigma_coefficients_c0_cx_cy'];weight=math.fsum((c[0],c[1]*pos[0],c[2]*pos[1]))
            normal[axis]=actual[axis]*weight;canonical[axis]=float(exact[axis])*weight
            scale+=max(abs(actual[axis]),sum(abs(v) for v in polys[axis]))*(abs(c[0])+abs(c[1]*pos[0])+abs(c[2]*pos[1]))
        normal['B']=state['B_equilibrium_Nmm2']*omega/props['Cw_mm6']
        canonical['B']=f.bimoment(torsion,t)*omega/props['Cw_mm6']
        static=np.asarray(section['segment_static_coefficients'][i])@np.array([1.,u,u*u])
        shear=dict(Vx=-state['Vy_N']*static[0]/props['Iy_weak_mm4']/th,
            Vy=-state['Vz_N']*static[1]/props['Ix_strong_mm4']/th,
            warping=-state['T_w_Nmm']*static[2]/props['Cw_mm6']/th,
            Saint_Venant=-w['thickness_face_sign']*state['T_SV_Nmm']*th/props['J_mm4'])
        sigma=math.fsum(normal.values());tau=math.fsum(shear.values())
        h=torsion['h'];bc=.5 if h==0 else 2*(math.sinh(h/2)/h)**2;bd=1. if h==0 else math.sinh(h)/h
        scale+=abs(omega/props['Cw_mm6'])*(abs(torsion['B0'])+abs(torsion['U'])*bc+abs(torsion['V'])*bd)
        eps=128*np.finfo(float).eps
        se=abs(sigma-math.fsum(canonical.values()))+eps*max(1.,scale)
        te=abs(tau-w['tau_MPa'])+eps*max(1.,sum(abs(v) for v in shear.values()))
        if not all(math.isfinite(v) for v in (sigma,tau,se,te)):raise ValueError('Nonfinite physical witness')
        w.update(sigma_MPa=sigma,tau_MPa=tau,equivalent_MPa=math.hypot(sigma,math.sqrt(3)*tau),
            sigma_error_MPa=se,tau_error_MPa=te,witness_error_MPa=dict(sigma=se,tau=te),x_mm=x,combination_id=case['combination']['id'],
            girt=beam['girt'],segment_id=beam['id'],side=state['side'],
            concomitant_7DOF_state=state,normal_contributions_MPa=normal,stress_contributions_MPa=normal,
            shear_contributions_MPa=shear,normal_action_reference=reference,selected_component_keys=keys,
            canonical_signed_actions_R01={k:float(v) for k,v in exact.items()},canonical_action_signs=signs,
            omega_mm2=omega,normal_index=abs(sigma)/limit,normal_limit_MPa=limit,
            section_fiber=(copy.deepcopy(fiber_data['identities'][i*4+int(u)*2+int(w['thickness_face_sign']==1)]) if u in (0.,1.) else
                dict(segment_index=i,u=u,thickness_face_sign=w['thickness_face_sign'],fiber_xy_relative_to_gross_CG_mm=pos)),
            section_fiber_index=i*4+int(u)*2+int(w['thickness_face_sign']==1) if u in (0.,1.) else None,
            witness_scope='Physical signed section; same recovered station, contour coordinate and wall face',
            witness_error_method='Magnitude-scaled binary64 pad and recovered/canonical discrepancy; not formal intervals')
        for j,value in enumerate(scores):best_sample[j]=max(best_sample[j],value)
        return w
    return evaluate,discarded



def _recover_branch_witnesses(bound,evaluate,limit):
    """Only recovered, same-sign final candidates enter persisted criteria.

    A failed candidate is discarded; its branch U remains valid. Canonical
    early exits therefore can only yield a weaker/inconclusive final result,
    never a fictitious observed exceedance or a false full-bound pass.
    """
    limits=dict(normal=limit,shear=limit/math.sqrt(3),interaction=1.1*limit)
    for key in limits:
        record=bound[key];proposal=record['witness']
        physical=None if proposal is None else evaluate(proposal)
        low=None
        if physical is not None:
            e=physical['witness_error_MPa'];pe=proposal['witness_error_MPa']
            es=max(e['sigma'],pe['sigma']);et=max(e['tau'],pe['tau'])
            physical['witness_error_MPa']=dict(sigma=es,tau=et)
            value=abs(physical['sigma_MPa']) if key=='normal' else abs(physical['tau_MPa']) if key=='shear' else physical['equivalent_MPa']
            error=es if key=='normal' else et if key=='shear' else math.hypot(es,math.sqrt(3)*et)
            low=max(0.,math.nextafter((value-error)/limits[key],-math.inf))
            point_upper=math.nextafter((value+error)/limits[key],math.inf)
            if not all(math.isfinite(v) for v in (value,error,low,point_upper)):
                raise ArithmeticError('Nonfinite recovered witness bound')
            physical.update(index=value/limits[key],index_lower_witness=low,index_upper_witness=point_upper)
            if point_upper>record['index_upper_bound']:
                record['physical_witness_upper_adjustment']+=point_upper-record['index_upper_bound']
                record['index_upper_bound']=point_upper
        upper=record['index_upper_bound']
        if not math.isfinite(upper) or (low is not None and upper<low):raise ArithmeticError('Invalid recovered witness bounds')
        record.update(witness=physical,index_lower_witness=low,bound_gap=None if low is None else upper-low,
            criterion='above_1_at_concomitant_state' if low is not None and low>1 else
                'within_1_by_full_interval_upper_bound' if upper<=1 else 'unresolved_numerical_bound')
    return bound

def _normal_aggregate(records,complete):
    records=[r for r in records if r is not None]
    for r in records:
        low=r['index_lower_witness'];upper=r['index_upper_bound']
        if upper is None or not math.isfinite(upper) or upper<0:
            raise ArithmeticError('Invalid normal upper bound')
        if (low is None)!=(r['witness'] is None):raise ValueError('Normal witness/lower mismatch')
        if low is not None and (not math.isfinite(low) or low<0 or upper<low):
            raise ArithmeticError('Invalid normal upper/lower bounds')
    valid=[r for r in records if r['witness'] is not None]
    winner=max(valid,key=lambda r:r['index_lower_witness']) if valid else None
    low=None if winner is None else winner['index_lower_witness']
    upper=max((r['index_upper_bound'] for r in records),default=None)
    if upper is not None and (not math.isfinite(upper) or (low is not None and upper<low)):
        raise ArithmeticError('Invalid normal upper/lower bounds')
    covered=bool(complete and records)
    criterion=('above_1_at_concomitant_state' if low is not None and low>1 else
        'within_1_by_full_interval_upper_bound' if covered and upper<=1 else
        'unresolved_numerical_bound' if covered else 'incomplete_section_branch_coverage')
    if not covered and low is not None and low>1:criterion='above_1_at_checked_state_full_envelope_incomplete'
    return dict(witness=None if winner is None else winner['witness'],index_lower_witness=low,
        index_upper_bound=upper if covered else None,partial_index_upper_bound=None if covered else upper,
        bound_gap=None if low is None or upper is None else upper-low,criterion=criterion,
        upper_bound_method='Union of signed-section Bernstein/hyperbolic bounds with magnitude-scaled binary64 padding; not formal interval arithmetic',
        bound_is_not_a_concomitant_state=True,complete=covered)

def calculate(demand,config):
    _validate_configuration(demand,config)
    # This call checks source bytes, case/bundle/model binding, action fields,
    # complete physical spans and signed model hashes. It does NOT compute
    # NBR capacities (_capacities), interaction or any new network solution.
    from ..three_girt_axial.application import _validate,reference_configuration as nbr_config,_polynomials
    _validate(demand,nbr_config(demand))
    if demand['input_data']['properties']['fy_MPa']!=250.:
        raise ValueError('EN normal implementation currently qualified only for fyb=fya=250 MPa')
    profile,section=_profile_and_section(demand)
    certificate=build_component_sections(profile)
    if certificate['nodes_sha256']!=section['nodes_sha256']:
        raise ValueError('EN pure sections and Vlasov omega have different geometry')
    fibers=f.exterior_fibers(section);limit=certificate['normal_yield_limit_MPa'];rows=[]
    from ..three_girt_warping.application import recover_exported_state
    for case in demand['cases']:
        if case['combination']['limit_state']!='ELU':continue
        for beam in case['model']['beams']:
            raw=_polynomials(beam)
            original=dict(N=raw['N_N'],Mx=[-v for v in raw['My_strong_Nmm']],My=[-v for v in raw['Mz_weak_Nmm']])
            polys,transport=_transport_polynomials(original,certificate)
            pieces=[];prepared_fields_cache={};torsion=f.torsion_field(beam['torsion_state_parameters'])
            edge0=recover_exported_state(case['model'],beam,beam['x_start_mm'])
            edge1=recover_exported_state(case['model'],beam,beam['x_end_mm'])
            total_torque=[edge0['T_equilibrium_SC_Nmm'],edge1['T_equilibrium_SC_Nmm']-edge0['T_equilibrium_SC_Nmm']]
            for interval in _integral_sign_intervals(polys,certificate):
                keys={axis:_component_key(axis,sign) for axis,sign in interval['signs'].items()}
                required={axis:[_component_key(axis,sign) for sign in signs if sign]
                          for axis,signs in interval['required_signs'].items()}
                blocked={key:copy.deepcopy(certificate['components'][key]['blocking_reasons'])
                    for values in required.values() for key in values if not certificate['components'][key]['eligible']}
                piece=dict(**interval,component_keys=keys,required_component_keys=required,blocking_components=blocked,
                    complete=not blocked,maximum_absolute=None,normal_criterion=None,shear_interaction=None)
                piece['branch_policy']='union_of_required_signed_coefficients'
                piece['bracket']=[interval['left'],interval['right']]
                piece['branch_count']=0;piece['normal']=_normal_aggregate([],False)
                piece['maximum_absolute_semantics']='lower_witness_not_exact_maximum'
                if not blocked:
                    branches=_coefficient_branches(interval,certificate)
                    evaluate,discarded=_physical_witness_evaluator(case,beam,section,polys,torsion,certificate,transport,limit,prune=False,fiber_data=fibers)
                    propose,_=_physical_witness_evaluator(case,beam,section,polys,torsion,certificate,transport,limit,proposal_only=True,fiber_data=fibers)
                    branch_results=[];details=[]
                    for selected,coefficients in branches:
                        operator_key=tuple((axis,tuple(coefficients[axis])) for axis in sorted(coefficients))
                        if operator_key not in prepared_fields_cache:
                            prepared_fields_cache[operator_key]=si.section_fields(section,polys,coefficients,torsion,total_torque,beam['length_mm'])
                        # A single deduplicated operator is already physical
                        # throughout this interval (zero actions contribute zero).
                        # Exact signs and recovered states are still checked on
                        # every persisted finalist below.
                        bound=si.envelope(section,polys,coefficients,torsion,total_torque,beam['length_mm'],
                            left=interval['left'],right=interval['right'],normal_limit_MPa=limit,
                            witness_evaluator=propose if len(branches)>1 else None,bounds_only_tiny=True,
                            prepared_fields=prepared_fields_cache[operator_key])
                        _recover_branch_witnesses(bound,evaluate,limit)
                        branch_results.append(bound)
                        details.append(dict(component_keys=selected,
                            index_upper_bounds={k:bound[k]['index_upper_bound'] for k in ('normal','shear','interaction')}))
                    normal=_normal_aggregate([r['normal'] for r in branch_results],True)
                    piece.update(normal=normal,maximum_absolute=normal['witness'],normal_criterion=normal['criterion'],
                        shear_interaction=si.aggregate(branch_results,True),branch_count=len(branches),branches=details,
                        discarded_witnesses=dict(discarded),section_fibers_checked=len(fibers['xy_mm']),
                        analytical_candidates_checked=None)
                pieces.append(piece)
            complete=all(p['complete'] for p in pieces)
            normal=_normal_aggregate([p['normal'] for p in pieces if p['complete']],complete)
            winner=normal['witness']
            rows.append(dict(combination_id=case['combination']['id'],girt=beam['girt'],segment_id=beam['id'],
                x_start_mm=beam['x_start_mm'],x_end_mm=beam['x_end_mm'],pieces=pieces,normal_action_reference=transport,
                shear_interaction=si.aggregate([p['shear_interaction'] for p in pieces],complete),
                complete=complete,normal=normal,normal_criterion=normal['criterion'],
                complete_envelope_semantics='lower_witness_not_exact_maximum',complete_envelope=winner if complete else None,
                partial_maximum=winner if not complete else None,
                observed_normal_exceedance=bool(normal['index_lower_witness'] is not None and normal['index_lower_witness']>1),
                blocking_components=sorted({k for p in pieces for k in p['blocking_components']})))
    if not rows:raise ValueError('No ELU combination for the normal component')
    members={}
    for level in LEVELS:
        rr=[r for r in rows if r['girt']==level];complete=all(r['complete'] for r in rr)
        normal=_normal_aggregate([p['normal'] for r in rr for p in r['pieces'] if p['complete']],complete)
        winner=normal['witness']
        members[level]=dict(ELU_segments=len(rr),complete_segments=sum(r['complete'] for r in rr),
            shear_interaction=si.aggregate([p['shear_interaction'] for r in rr for p in r['pieces']],complete),
            complete_sign_pieces=sum(p['complete'] for r in rr for p in r['pieces']),
            total_sign_pieces=sum(len(r['pieces']) for r in rr),complete=complete,normal=normal,
            complete_envelope_semantics='lower_witness_not_exact_maximum',
            complete_envelope=winner if complete else None,partial_maximum=winner if not complete else None,
            blocking_components=sorted({k for r in rr for k in r['blocking_components']}),
            observed_normal_exceedance=bool(normal['index_lower_witness'] is not None and normal['index_lower_witness']>1),
            normal_criterion=normal['criterion'])
    result=dict(schema=SCHEMA,status='computed_conditional_EN_normal_shear_interaction',
        branch_policy='union_of_required_signed_coefficients',
        normal_envelope_semantics='Physical lower witness and separate numerical upper bound; compatibility maximum aliases are not exact maxima',
        configuration=copy.deepcopy(config),source_input_fingerprint=demand['input_fingerprint'],
        source_demand_sha256=fingerprint(mechanical_source(demand)),source_geometry=copy.deepcopy(demand['source_geometry']),
        component_sections=certificate,normal_limit_MPa=limit,section_fiber_model=fibers['scope'],
        section_fibers_checked=len(fibers['xy_mm']),rows=rows,per_member=members,
        ELU_combinations=sum(c['combination']['limit_state']=='ELU' for c in demand['cases']),
        ELS_combinations_excluded=sum(c['combination']['limit_state']=='ELS' for c in demand['cases']),
        demand_material_E_MPa=demand['input_data']['properties']['E_MPa'],
        resistance_material_E_MPa=certificate['material']['E_MPa'],
        actions_basis='Existing NBR load combinations and first-order 7DOF demand retained; not renamed as EN load combinations or integral EN analysis',
        limits=['EN1993-1-3:2006 6.1.6(3)-(5) normal, shear and interaction section criteria; same pure-section method for N/M, coherent gross B/shear properties.',
            'Demonstrated pure effective sections at ULS only: integral branches and explicitly qualified uniform-compression local/distortional reductions at t1.20/1.50 and web reductions at t2.00/2.25. Axial centroid moments transported exactly once before bending-sign selection. No missing-branch or NBR/AISI fallback.',
            'Both exterior faces of every faceted wall segment; omega constant through thickness. Not an exact curved solid stress solution.',
            'EN6.1.6(4) shear and sigma-tau interaction use concomitant face stresses and full-interval numerical upper bounds in eligible sign intervals; incomplete section coverage never passes.',
            'EN6.1.5 shear resistance/buckling and EN6.1.10 N-M-V interaction are not replaced. Global stability, second-order/small-rotation applicability, net fracture, shear lag, flange curling, local force introduction, connections and ELS remain separate.',
            'Fixed EN section proof E210000/nu0.3/fyb=fya250/gammaM0=1. Existing demand E and NBR combinations preserved; material and geometry are declared assumptions, not certified.',
            'Physical lower witnesses exclude blocked intervals; aliases named maximum or envelope are lower witnesses, never exact maxima. Only complete upper bounds can establish a within-limit criterion.',
            'Signed-section unions cover root brackets conservatively. Artificial branch states are never accepted as witnesses. Bounds use magnitude-scaled binary64 padding, not formal interval arithmetic; unresolved gaps remain inconclusive.'],
        **{key:False for key in FALSE_FLAGS})
    result['content_sha256']=fingerprint(result)
    return result


def attach(demand,config):
    if 'NBR_axial_bending_component' in demand:
        raise ValueError('Attach EN normal before the NBR snapshot so both independent source hashes remain intact')
    source=copy.deepcopy(demand);source.pop(FIELD,None)
    component=calculate(source,config);source[FIELD]=component
    return source



def _verify_saved_action_references(component,demand):
    """Validate saved transport arithmetic, never resolve or rebuild a section."""
    from ..three_girt_axial.application import _polynomials
    beams={(case['combination']['id'],beam['id']):beam for case in demand['cases']
           if case['combination']['limit_state']=='ELU' for beam in case['model']['beams']}
    seen=set();references={}
    def witness_reference(w,expected):
        if w is None:return
        _,reference=_normal_action_state(w['concomitant_7DOF_state'],expected)
        if w.get('normal_action_reference')!=reference:
            raise ValueError('Saved concomitant centroid transport changed')
        if component['schema']==SCHEMA:
            exact=_exact_actions(expected['corrected_polynomials_R01'],w['t'])
            signs={axis:(value>0)-(value<0) for axis,value in exact.items()}
            selected={axis:_component_key(axis,sign) for axis,sign in signs.items()}
            actual=reference['corrected_actions_R01']
            if (w.get('selected_component_keys')!=selected or w.get('canonical_action_signs')!=signs or
                any(((actual[axis]>0)-(actual[axis]<0))!=sign for axis,sign in signs.items())):
                raise ValueError('Saved physical witness signed section changed')
        for axis,polynomial in expected['original_polynomials_R01'].items():
            value=math.fsum(coefficient*w['t']**i for i,coefficient in enumerate(polynomial))
            if not math.isclose(value,reference['original_actions_R01'][axis],rel_tol=2e-10,abs_tol=1e-6):
                raise ValueError('Saved normal reference differs from the original signed beam action')
    for row in component['rows']:
        key=(row['combination_id'],row['segment_id'])
        if key not in beams or key in seen:raise ValueError('Saved transported beam coverage changed')
        seen.add(key);raw=_polynomials(beams[key])
        original=dict(N=raw['N_N'],Mx=[-v for v in raw['My_strong_Nmm']],My=[-v for v in raw['Mz_weak_Nmm']])
        _,expected=_transport_polynomials(original,component['component_sections']);references[key]=expected
        if row.get('normal_action_reference')!=expected:raise ValueError('Saved beam centroid transport changed')
        if component['schema']==SCHEMA:
            _validate_saved_bound(row['normal'],row['complete'])
            witness_reference(row['normal']['witness'],expected)
        for name in ('complete_envelope','partial_maximum'):
            witness_reference(row[name],expected)
        for criterion in ('shear','interaction'):
            aggregate=row['shear_interaction'][criterion]
            if aggregate:witness_reference(aggregate['witness'],expected)
        for piece in row['pieces']:
            if component['schema']==SCHEMA:
                _validate_saved_bound(piece['normal'],piece['complete'])
                witness_reference(piece['normal']['witness'],expected)
            witness_reference(piece['maximum_absolute'],expected)
            if piece['shear_interaction']:
                for criterion in ('shear','interaction'):
                    witness_reference(piece['shear_interaction'][criterion]['witness'],expected)
    if seen!=set(beams):raise ValueError('Saved transported beam coverage incomplete')
    for member in component['per_member'].values():
        if component['schema']==SCHEMA:
            _validate_saved_bound(member['normal'],member['complete'])
            w=member['normal']['witness']
            if w:witness_reference(w,references[(w['combination_id'],w['segment_id'])])
        for name in ('complete_envelope','partial_maximum'):
            w=member[name]
            if w:witness_reference(w,references[(w['combination_id'],w['segment_id'])])
        for criterion in ('shear','interaction'):
            value=member['shear_interaction'][criterion]
            if value:
                w=value['witness']
                if w:witness_reference(w,references[(w['combination_id'],w['segment_id'])])


def _validate_saved_bound(bound,complete):
    low=bound['index_lower_witness'];hi=bound['index_upper_bound'];partial=bound['partial_index_upper_bound']
    if (low is None)!=(bound['witness'] is None):raise ValueError('Saved lower witness missing')
    for value in (low,hi,partial):
        if value is not None and (not math.isfinite(value) or value<0):raise ValueError('Invalid saved bound')
    upper=hi if complete else partial
    if complete and (hi is None or partial is not None):raise ValueError('Saved full upper bound missing')
    if not complete and hi is not None:raise ValueError('Incomplete coverage has a full upper bound')
    if low is not None and (upper is None or upper<low):raise ValueError('Saved upper below lower')
    expected=('above_1_at_concomitant_state' if low is not None and low>1 else
        'within_1_by_full_interval_upper_bound' if complete and hi<=1 else
        'unresolved_numerical_bound' if complete else 'incomplete_section_branch_coverage')
    if not complete and low is not None and low>1:expected='above_1_at_checked_state_full_envelope_incomplete'
    if bound['criterion']!=expected:raise ValueError('Saved bound criterion changed')

def saved_component(demand):
    component=demand.get(FIELD)
    if component is None:return None
    if not isinstance(component,dict) or component.get('schema') not in (LEGACY_SCHEMA,LEGACY_SHEAR_SCHEMA,LEGACY_EFFECTIVE_SCHEMA,SCHEMA):raise ValueError('Unknown saved EN normal component')
    if component.get('content_sha256')!=fingerprint({k:v for k,v in component.items() if k!='content_sha256'}):
        raise ValueError('Saved EN normal component content changed')
    if (component.get('source_demand_sha256')!=fingerprint(mechanical_source(demand)) or
        component.get('source_input_fingerprint')!=demand.get('input_fingerprint') or
        any(component.get(k) is not False for k in FALSE_FLAGS)):
        raise ValueError('Saved EN normal source/scope changed')
    verify_component_sections(component['component_sections'])
    if component['schema'] in (LEGACY_EFFECTIVE_SCHEMA,SCHEMA):_verify_saved_action_references(component,demand)
    return component


def summary(result):
    return dict(schema=result['schema'],ELU_combinations=result['ELU_combinations'],
        ELS_combinations_excluded=result['ELS_combinations_excluded'],normal_limit_MPa=result['normal_limit_MPa'],
        members={name:{k:copy.deepcopy(v) for k,v in row.items() if k not in ('complete_envelope','partial_maximum')}
            | {'complete_normal_index':None if row['complete_envelope'] is None else row['complete_envelope']['normal_index'],
               'partial_normal_index':None if row['partial_maximum'] is None else row['partial_maximum']['normal_index']}
            for name,row in result['per_member'].items()},**{k:False for k in FALSE_FLAGS})
