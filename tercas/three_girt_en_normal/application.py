"""Separate, conditional EN normal N+Mx+My+B component on current 7DOF demand.

Only pure sections demonstrated integral at ULS are admitted. The borrowed
NBR adapter validates the immutable current demand/source contract ONLY; no
NBR denominator or AISI capacity participates in this calculation. The input
load combinations and existing structural E remain unchanged and are labelled.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
from . import field_envelope as f
from .en1993_normal_components import build_component_sections,verify_component_sections

FIELD='EN_normal_N_M_B_component'
SCHEMA='three_girt_EN_normal_N_M_B_integral_v1'
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


def _profile_and_section(demand):
    from ..torsion_study import section_for,PINS
    section=section_for(demand['input_data']);t=demand['input_data']['properties']['t']
    path=Path(__file__).resolve().parents[1]/'data'/'torsion_profiles'/f'ue100x50x17_t{t:.2f}.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PINS[t]:raise ValueError('Current own section bytes changed')
    return json.loads(raw),section


def _witness(result,case,beam,polys,coefficients,torsion,fibers,limit):
    from ..three_girt_warping.application import recover_exported_state
    witness=copy.deepcopy(result)
    t=witness['t'];x=beam['x_start_mm']+(beam['x_end_mm']-beam['x_start_mm'])*t
    state=recover_exported_state(case['model'],beam,x)
    actual={'N':state['N_N'],'Mx':-state['My_strong_Nmm'],'My':-state['Mz_weak_Nmm']}
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
        stress_contributions_MPa=terms,concomitant_7DOF_state=state,
        normal_index=abs(total)/limit,normal_limit_MPa=limit,
        witness_scope='Exterior vertex of a faceted thin-wall rectangle; omega constant through thickness')
    return witness


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
    for case in demand['cases']:
        if case['combination']['limit_state']!='ELU':continue
        for beam in case['model']['beams']:
            raw=_polynomials(beam)
            polys=dict(N=raw['N_N'],Mx=[-v for v in raw['My_strong_Nmm']],My=[-v for v in raw['Mz_weak_Nmm']])
            pieces=[];torsion=f.torsion_field(beam['torsion_state_parameters'])
            for interval in f.sign_intervals(polys):
                keys={axis:_component_key(axis,sign) for axis,sign in interval['signs'].items()}
                required={axis:[_component_key(axis,sign) for sign in signs if sign]
                          for axis,signs in interval['required_signs'].items()}
                blocked={key:copy.deepcopy(certificate['components'][key]['blocking_reasons'])
                    for values in required.values() for key in values if not certificate['components'][key]['eligible']}
                piece=dict(**interval,component_keys=keys,required_component_keys=required,blocking_components=blocked,
                    complete=not blocked,maximum_absolute=None,normal_criterion=None)
                if not blocked:
                    coefficients={axis:certificate['components'][key]['sigma_coefficients_c0_cx_cy']
                                  for axis,key in keys.items() if key is not None}
                    # A root bracket may require both signs. They must have
                    # identical demonstrated integral coefficients; no future
                    # reduced-section branch can silently reuse this shortcut.
                    for axis,values in required.items():
                        if any(certificate['components'][key]['sigma_coefficients_c0_cx_cy']!=coefficients[axis] for key in values):
                            raise ValueError('Opposite effective sections differ in a root neighborhood')
                    env=f.envelope(polys,coefficients,fibers['xy_mm'],fibers['omega_over_Cw'],torsion,
                        interval['left'],interval['right'])
                    winner=_witness(env['maximum_absolute'],case,beam,polys,coefficients,torsion,fibers,limit)
                    piece.update(maximum_absolute=winner,
                        normal_criterion='within_1_in_declared_section_model' if winner['normal_index']<=1 else 'above_1_in_declared_section_model',
                        section_fibers_checked=env['section_fibers_checked'],analytical_candidates_checked=env['analytical_candidates_checked'])
                pieces.append(piece)
            valid=[p['maximum_absolute'] for p in pieces if p['complete']]
            winner=max(valid,key=lambda v:v['normal_index']) if valid else None
            complete=all(p['complete'] for p in pieces)
            rows.append(dict(combination_id=case['combination']['id'],girt=beam['girt'],segment_id=beam['id'],
                x_start_mm=beam['x_start_mm'],x_end_mm=beam['x_end_mm'],pieces=pieces,
                complete=complete,complete_envelope=winner if complete else None,
                partial_maximum=winner if not complete else None,
                observed_normal_exceedance=bool(winner is not None and winner['normal_index']>1),
                blocking_components=sorted({k for p in pieces for k in p['blocking_components']})))
    if not rows:raise ValueError('No ELU combination for the normal component')
    members={}
    for level in LEVELS:
        rr=[r for r in rows if r['girt']==level];complete=all(r['complete'] for r in rr)
        valid=[r['complete_envelope'] or r['partial_maximum'] for r in rr]
        valid=[r for r in valid if r is not None];winner=max(valid,key=lambda v:v['normal_index']) if valid else None
        members[level]=dict(ELU_segments=len(rr),complete_segments=sum(r['complete'] for r in rr),
            complete_sign_pieces=sum(p['complete'] for r in rr for p in r['pieces']),
            total_sign_pieces=sum(len(r['pieces']) for r in rr),complete=complete,
            complete_envelope=winner if complete else None,partial_maximum=winner if not complete else None,
            blocking_components=sorted({k for r in rr for k in r['blocking_components']}),
            observed_normal_exceedance=bool(winner is not None and winner['normal_index']>1),
            normal_criterion=('above_1_at_checked_state_full_envelope_incomplete' if winner is not None and winner['normal_index']>1 else None)
                if not complete else ('within_1_in_declared_section_model' if winner['normal_index']<=1 else 'above_1_in_declared_section_model'))
    result=dict(schema=SCHEMA,status='computed_conditional_EN_normal_component',
        configuration=copy.deepcopy(config),source_input_fingerprint=demand['input_fingerprint'],
        source_demand_sha256=fingerprint(mechanical_source(demand)),source_geometry=copy.deepcopy(demand['source_geometry']),
        component_sections=certificate,normal_limit_MPa=limit,section_fiber_model=fibers['scope'],
        section_fibers_checked=len(fibers['xy_mm']),rows=rows,per_member=members,
        ELU_combinations=sum(c['combination']['limit_state']=='ELU' for c in demand['cases']),
        ELS_combinations_excluded=sum(c['combination']['limit_state']=='ELS' for c in demand['cases']),
        demand_material_E_MPa=demand['input_data']['properties']['E_MPa'],
        resistance_material_E_MPa=certificate['material']['E_MPa'],
        actions_basis='Existing NBR load combinations and first-order 7DOF demand retained; not renamed as EN load combinations or integral EN analysis',
        limits=['EN1993-1-3:2006 6.1.6 normal-stress component only; same pure-section method for N and M, gross omega/Cw for B.',
            'Only pure sections demonstrated integral at ULS. No reduced-section, opposite-sign or NBR/AISI capacity fallback.',
            'Both exterior faces of every faceted wall segment; omega constant through thickness. Not an exact curved solid stress solution.',
            'Normal-stress criterion does not complete 6.1.6(4): shear and sigma-tau interaction remain unverified.',
            'Global stability, second-order/small-rotation applicability, net fracture, shear lag, flange curling, local force introduction, connections and ELS remain separate.',
            'Fixed EN section proof E210000/nu0.3/fyb=fya250/gammaM0=1. Existing demand E and NBR combinations preserved; material and geometry are declared assumptions, not certified.',
            'Partial maxima exclude blocked sign intervals and are never promoted to a full member envelope.'],
        **{key:False for key in FALSE_FLAGS})
    result['content_sha256']=fingerprint(result)
    return result


def attach(demand,config):
    if 'NBR_axial_bending_component' in demand:
        raise ValueError('Attach EN normal before the NBR snapshot so both independent source hashes remain intact')
    source=copy.deepcopy(demand);source.pop(FIELD,None)
    component=calculate(source,config);source[FIELD]=component
    return source


def saved_component(demand):
    component=demand.get(FIELD)
    if component is None:return None
    if not isinstance(component,dict) or component.get('schema')!=SCHEMA:raise ValueError('Unknown saved EN normal component')
    if component.get('content_sha256')!=fingerprint({k:v for k,v in component.items() if k!='content_sha256'}):
        raise ValueError('Saved EN normal component content changed')
    if (component.get('source_demand_sha256')!=fingerprint(mechanical_source(demand)) or
        component.get('source_input_fingerprint')!=demand.get('input_fingerprint') or
        any(component.get(k) is not False for k in FALSE_FLAGS)):
        raise ValueError('Saved EN normal source/scope changed')
    verify_component_sections(component['component_sections'])
    return component


def summary(result):
    return dict(schema=result['schema'],ELU_combinations=result['ELU_combinations'],
        ELS_combinations_excluded=result['ELS_combinations_excluded'],normal_limit_MPa=result['normal_limit_MPa'],
        members={name:{k:copy.deepcopy(v) for k,v in row.items() if k not in ('complete_envelope','partial_maximum')}
            | {'complete_normal_index':None if row['complete_envelope'] is None else row['complete_envelope']['normal_index'],
               'partial_normal_index':None if row['partial_maximum'] is None else row['partial_maximum']['normal_index']}
            for name,row in result['per_member'].items()},**{k:False for k in FALSE_FLAGS})
