"""Explicit nominal Pierin Ue family N=0 section components.

Same original Vlasov field and conservative Bernstein machinery; no new solver,
no inherited fy250 authority, no global or first-order physical approval.
Saved readers authenticate providers and replay arithmetic only.
"""
import copy
from collections import OrderedDict
from threading import RLock
import json
import math
from pathlib import Path
from fractions import Fraction as F
import numpy as np
from .en_ue125_300_authority import _sha
from . import en_ue_family_provider as provider
from .isolated_en_stress import _support_limit_guard, stress_norm
from .en_ue_family_field_controls import _field_controls
from .torsion_vlasov.intervals import Interval as I
from .torsion_vlasov.section import verify_section
from . import isolated_en_ue_catalog_application as arithmetic
from . import en_signed_partial_interaction as core
from .en_ue_family_applicability import assess

LEGACY_SCHEMA='EN_Ue_family_concurrent_section_components_v1'
SCHEMA='EN_Ue_family_concurrent_section_components_v2'
_VERIFIED_READS=OrderedDict()
_READ_LOCK=RLock()
FALSE_FLAGS=('whole_member_approved','complete_EN_design_qualified','global_stability_qualified','combined_ELS_qualified',
    'first_order_analysis_qualified','physical_design_approved','historical_results_requalified',
    'original_mechanics_changed','NBR_capacities_used','AISI_capacities_used')


def _validate(demand, normal_snapshot, model_origin):
    normal=normal_snapshot
    shear=normal['shear']
    if not shear['eligible']:raise ValueError('Cortante fora do domínio: '+str(shear['blocking_reasons']))
    if type(model_origin) is not str or not model_origin.strip():raise ValueError('Explicit intact-section model origin required')
    verify_section(demand['section'])
    if demand['section']['nodes_sha256']!=normal['nodes_sha256']:raise ValueError('Normal/stress contour mismatch')
    if demand.get('schema')!='single_vlasov_member_demand_v1':raise ValueError('Original dense demand required')
    for element in demand['elements']:
        for key in ('B_Nmm2','Tsv_Nmm','Tw_Nmm'):
            values=element['coefficients'][key]
            if (not isinstance(values,list) or not 1<=len(values)<=4
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in values)):
                raise ValueError('Finite real torsion coefficients required; booleans are not actions')
    pieces=arithmetic._source_pieces(demand)
    if not pieces or len(pieces)*(len(normal['nodes_xy_mm'])-1)*2>100000:raise ValueError('Numerical resource budget exceeded')
    binding=dict(nodes_sha256=normal['nodes_sha256'],section_profile_id=demand['section']['profile_id'])
    arithmetic._validate_source(demand,pieces,binding,dict(E_MPa=demand['E_MPa'],G_MPa=demand['G_MPa']))
    arithmetic._equilibrium(demand)
    from .en_ue125_300_source_replay import validate as validate_source_field
    validate_source_field(demand)
    _support_limit_guard(demand)
    return normal,shear,pieces


def _stress(demand, certificate, model_origin, *, normal_witness=False):
    """Upper<=1 is sufficient for these three section criteria only.

    No branch sum is interpreted as a concurrent physical maximum. An upper
    bound >1 is inconclusive unless a separate physical-point interval proves
    a strict normal exceedance in the recovered linear field. Existing NBR
    combinations/material stiffness are retained and explicitly labelled.
    """
    normal_limit = certificate['normal_yield_limit_MPa']
    limit_intervals = dict(normal=I(normal_limit),
        shear=I(normal_limit) / I(3.).sqrt(), interaction=I(normal_limit) * I(1.1))
    bounds = dict(normal=0., shear=0., interaction=0.)
    controls = {}; count = 0
    for selected, face, sigma, tau, identities in _field_controls(demand, certificate):
        values = dict(normal=sigma.abs(), shear=tau.abs(),
            interaction=stress_norm(sigma, tau))
        for key, values_at_controls in values.items():
            ratios = values_at_controls / limit_intervals[key]
            index = np.unravel_index(np.argmax(ratios.hi), ratios.hi.shape)
            upper = float(ratios.hi[index])
            if upper >= bounds[key]:
                bounds[key] = upper
                controls[key] = dict(source_piece=identities[index[0]], wall_segment=int(index[1]),
                    face=face, longitudinal_control=int(index[2]), wall_control=int(index[3]),
                    signed_operator_superset=selected,
                    sigma_interval_MPa=[float(sigma.lo[index]),float(sigma.hi[index])],
                    tau_interval_MPa=[float(tau.lo[index]),float(tau.hi[index])],
                    is_physical_state=False, semantics='Bernstein bound control, not a stress witness')
        count += sigma.lo.shape[0] * sigma.lo.shape[1]
    # Exact zero follows from source coefficients/equilibrium, never tolerance.
    exact_zero=all(not any(v for values in arithmetic._fields(demand,piece).values() for v in values)
        for piece in arithmetic._source_pieces(demand))
    exact_zero &= all(not any(e['coefficients'][key]) for e in demand['elements']
        for key in ('B_Nmm2','Tsv_Nmm','Tw_Nmm'))
    exact_zero &= all(not any(s[key] for key in ('B_Nmm2','Tsv_Nmm','Tw_Nmm'))
        for s in demand.get('support_limit_states',[]))
    if exact_zero:
        bounds={key:0. for key in bounds}
        for control in controls.values():
            control['sigma_interval_MPa']=[0.,0.];control['tau_interval_MPa']=[0.,0.]
            control['exact_zero_by_source_coefficients']=True
    criteria = {key:dict(index_upper_bound=value,
        criterion='within_limit' if value <= 1 else 'inconclusive_upper_bound',
        bound_control=controls[key], observed_exceedance=False) for key, value in bounds.items()}
    if normal_witness and bounds['normal']>1:
        from .en_ue_family_normal_witness import search_endpoints
        witness=search_endpoints(demand,certificate,controls['normal'])
        if witness is not None:
            criteria['normal'].update(criterion='observed_exceedance_under_linear_model',
                observed_exceedance=True,physical_witness=witness)
    output = dict(schema='EN_Ue_family_6_1_6_bounds_v2' if normal_witness else 'EN_Ue_family_6_1_6_bounds_v1', status='computed_sufficient_EN_section_stress_bounds',
        combination_id=demand['combination_id'], member_id=demand['member_id'],
        source_demand_sha256=_sha(demand), source_geometry_sha256=demand['section']['nodes_sha256'],
        component_sections_sha256=certificate['content_sha256'],
        material=certificate['material'], model_origin=model_origin,
        intact_section_model_declared=True, criteria=criteria,
        full_member_field_covered=True, section_stress_criteria_sufficiently_satisfied=all(v <= 1 for v in bounds.values()),
        normal_limit_MPa=normal_limit, shear_limit_MPa=normal_limit/math.sqrt(3.),
        interaction_limit_MPa=1.1*normal_limit, polynomial_patches_checked=count,
        source_analysis_material=dict(E_MPa=demand['E_MPa'], G_MPa=demand['G_MPa']),
        method='EN1993-1-3:2006 6.1.6(3)-(5); tensor Bernstein sufficient bounds; signed-section union',
        demand_basis='Original first-order isolated ELU demand retained, not recalculated as EN action combinations',
        stress_scope='Effective pure-section bending normal stresses at both exterior faces; gross B/V/Tsv/Tw; N=0',
        numerical_scope='Outward-rounded bounds of the recovered polynomial field only, not an FE-error certificate',
        NBR_capacities_used=False, AISI_capacities_used=False, whole_member_approved=False,
        complete_EN_design_qualified=False, global_stability_qualified=False,
        excluded=['EN6.1.5 shear buckling resistance and EN6.1.10 N-M-V interaction',
            'Global/member stability and applicability of first-order/small-rotation analysis',
            'Local force introduction, connections, holes/net-section rupture and actual restraint details',
            'Full serviceability and physical geometry/material verification'],
        integration_status='Separate EN section component; explicit caller opt-in; no global approval')
    output['content_sha256'] = _sha(output)
    return output

def _interaction(demand, normal, shear, pieces, applicability):
    floors={k:F(v['first_yield_capacity_floor']) for k,v in normal['components'].items() if v['eligible']}
    # Axial action is proved exactly zero; no fictitious axial floor is supplied.
    caps=shear['shear_capacity_lower_N'];rows=[];maxima=[];missing_branches=set()
    for piece in pieces:
        fields=arithmetic._fields(demand,piece)
        if any(fields['N']):raise ValueError('Only N=0 is qualified')
        controls={a:core._bernstein([(v,v) for v in values]) for a,values in fields.items()}
        checks=[]
        for i in range(3):
            values={a:controls[a][i] for a in core.ACTIONS}
            required={k for axis in ('Mx','My') for k in core._required(axis,values[axis])}
            missing=required-set(floors)
            missing_branches.update(missing)
            if missing:
                strong=max(abs(v) for v in values['Vstrong'])/F(caps['strong'])
                weak=max(abs(v) for v in values['Vweak'])/F(caps['weak'])
                exact=dict(strong_shear_ratio_upper=strong,weak_shear_ratio_upper=weak,
                    shear_ratio_upper=max(strong,weak),normal_ratio_upper=None,index_upper=None,
                    shear_penalty_upper=max(max(F(0),2*v-1)**2 for v in (strong,weak)))
            else:exact=core._objective(values,floors,caps)
            maxima.append(exact)
            checks.append(dict(control=i,is_physical_state=False,
                intervals={a:[core._outward(lo,-1),core._outward(hi,1)] for a,(lo,hi) in values.items()},
                **{k:None if v is None else core._outward(v,1) for k,v in exact.items()}))
        rows.append(dict(source_piece=copy.deepcopy(piece),controls=checks))
    strong=max(m['strong_shear_ratio_upper'] for m in maxima)
    weak=max(m['weak_shear_ratio_upper'] for m in maxima)
    index=None if missing_branches else max(m['index_upper'] for m in maxima)
    ready=applicability['qualified'] and not missing_branches
    missing_reason='Operadores EN por sentido pendentes: '+', '.join(sorted(missing_branches)) if missing_branches else None
    shear_result=dict(strong_ratio_upper=core._outward(strong,1),weak_ratio_upper=core._outward(weak,1),
        index_upper=core._outward(max(strong,weak),1),component_sufficient=max(strong,weak)<=1,
        status='sufficient' if max(strong,weak)<=1 else 'inconclusive_upper_bound',observed_failure=False)
    passed=ready and index<=1 and max(strong,weak)<=1
    mv=dict(index_upper=core._outward(index,1) if ready else None,component_sufficient=passed,
        status=('sufficient' if passed else 'inconclusive_upper_bound') if ready else 'pending',
        reason=('Condição suficiente seccional EN6.27; Mf=0, N=0; EN6.1.6 permanece separado.' if passed
            else 'Teto conservador excedido; não demonstra falha física.') if ready else missing_reason or applicability['reason'],
        observed_failure=False,flange_reserve_Mf=0,N_identically_zero=True,
        original_moments_equal_current=True,torsion_converted_to_shear=False)
    return shear_result,mv,rows


def _calculate(demand, *, normal_snapshot, model_origin, normal_witness=True):
    """Evaluate the existing dense field before its normal app compaction."""
    normal,shear,pieces=_validate(demand,normal_snapshot,model_origin)
    try:stress=_stress(demand,normal,model_origin,normal_witness=normal_witness)
    except ValueError as error:
        if not str(error).startswith('EN signed effective section unavailable:'):raise
        # No fabricated sigma/tau or combined-stress approval. Only V/capacity
        # can proceed independently under its own authenticated authority.
        stress=dict(schema='EN_Ue_family_6_1_6_pending_v1',status='pending_signed_normal_operator',
            reason=str(error),criteria={k:dict(index_upper_bound=None,criterion='pending',
                bound_control=None,observed_exceedance=False) for k in ('normal','shear','interaction')},
            section_stress_criteria_sufficiently_satisfied=False,normal_limit_MPa=normal['normal_yield_limit_MPa'],
            material=normal['material'],whole_member_approved=False)
    stress_computed=stress['status']!='pending_signed_normal_operator'
    applicability=assess(demand,normal_snapshot)
    stress['raw_bounds_sufficient']=stress['section_stress_criteria_sufficiently_satisfied']
    stress['section_stress_criteria_sufficiently_satisfied'] &= applicability['qualified']
    stress['applicability_qualified']=applicability['qualified']
    if stress_computed:stress['status']='computed_sufficient_EN_section_stress_bounds' if applicability['qualified'] else 'pending_bending_applicability'
    stress['content_sha256']=_sha({k:v for k,v in stress.items() if k!='content_sha256'})
    v,m,rows=_interaction(demand,normal,shear,pieces,applicability)
    out=dict(schema=SCHEMA if normal_witness else LEGACY_SCHEMA,normal_source_sha256=normal['content_sha256'],
        shear_source_snapshot=shear,source_analysis_sha256=_sha(demand),
        source_analysis_material=dict(E_MPa=demand['E_MPa'],G_MPa=demand['G_MPa']),
        material=copy.deepcopy(normal['material']),model_origin=model_origin,
        source_demand=copy.deepcopy(demand),stress=stress,shear=v,mv=m,pieces=rows,
        applicability=applicability,full_member_field_covered=True,
        component_status=dict(stress='computed' if stress_computed else 'pending',shear='computed',mv='computed' if m['index_upper'] is not None else 'pending'),
        scope='EN6.1.6 plus EN6.1.5/6.1.10 Eq6.27; família Ue Pierin, material declarado, N=0, no roof restraint or global approval',
        **{k:False for k in FALSE_FLAGS})
    out['content_sha256']=_sha(out)
    return out


def _compact_source(demand):
    from .torsion_vlasov.adapter import summarize_torsion_evidence
    return summarize_torsion_evidence(dict(schema='purlin_torsion_batch_evidence_v1',
        records=[dict(analysis=demand)]))['records'][0]['analysis']


def _read_token(check, summary, normal_snapshot, source_sha256, model_origin):
    for value in (check,summary,normal_snapshot,source_sha256,model_origin):_json_native(value)
    return (_sha(check),_sha(summary),_sha(normal_snapshot),source_sha256,model_origin)


def _remember_verified(token):
    with _READ_LOCK:
        _VERIFIED_READS[token]=True
        while len(_VERIFIED_READS)>128:_VERIFIED_READS.popitem(last=False)


def calculate_many(demands, *, normal_snapshot, model_origin):
    provider.verify(normal_snapshot)
    from .en_ue_family_geometry import section
    expected_section=section(normal_snapshot['catalog_index'])
    results=[]
    for d in demands:
        try:
            if _sha(d['section'])!=_sha(expected_section):raise ValueError('Geometria integral diverge da fonte nominal atual')
            out=_calculate(d,normal_snapshot=normal_snapshot,model_origin=model_origin)
            token=_read_token(out,_compact_source(d),normal_snapshot,out['source_analysis_sha256'],model_origin)
            _remember_verified(token)
            results.append(out)
        except (ValueError,KeyError,TypeError,ArithmeticError) as error:results.append(error)
    return results


def calculate(demand, *, normal_snapshot, model_origin):
    result=calculate_many([demand],normal_snapshot=normal_snapshot,model_origin=model_origin)[0]
    if isinstance(result,Exception):raise result
    return result


def _json_native(value):
    t=type(value)
    if t is dict:
        if any(type(k) is not str for k in value):raise ValueError('JSON string keys required')
        for v in value.values():_json_native(v)
    elif t is list:
        for v in value:_json_native(v)
    elif t not in (str,int,float,bool,type(None)) or t is float and not math.isfinite(value):
        raise ValueError('Only finite native JSON values may be replayed or cached')


def validate_saved_many(requests, *, normal_snapshot, model_origin):
    """Authenticate authorities once per call; replay every independent row.

    This is a closed batch operation, not a caller-provided trusted context.
    Every call reads the current authority files, including on warm hits. The
    only shared row work is content-identical, native-JSON shear certificates
    and the common normal authority. Complete per-row proof tokens and replay
    on any miss remain mandatory. No result/object-identity cache is used.
    """
    if type(requests) is not list:raise ValueError('Native list of saved EN family requests required')
    _json_native(normal_snapshot);_json_native(model_origin)
    provider.verify(normal_snapshot)
    from .en_ue_family_geometry import section
    expected_section=section(normal_snapshot['catalog_index'])
    normal_sha256=_sha(normal_snapshot)
    rows=[];verified_shear=set()
    for request in requests:
        if type(request) is not dict or set(request)!={'check','summary','source_sha256'}:
            raise ValueError('Explicit saved check, summary and original source hash required')
        check=request['check'];summary=request['summary'];source_sha256=request['source_sha256']
        for value in (check,summary,source_sha256):_json_native(value)
        if type(check) is not dict or check.get('schema') != SCHEMA:
            raise ValueError('EN family snapshot schema required')
        token=(_sha(check),_sha(summary),normal_sha256,source_sha256,model_origin)
        shear_key=_sha(check['shear_source_snapshot'])
        if shear_key not in verified_shear:
            if _sha(check['shear_source_snapshot'])!=_sha(normal_snapshot['shear']):
                raise ValueError('Cortante salvo diverge da fonte determinística atual')
            verified_shear.add(shear_key)
        rows.append((check,summary,source_sha256,token))
    for check,summary,source_sha256,token in rows:
        if _sha(check['source_demand']['section'])!=_sha(expected_section):raise ValueError('Geometria integral salva diverge da fonte nominal atual')
        with _READ_LOCK:
            if token in _VERIFIED_READS:
                _VERIFIED_READS.move_to_end(token)
                continue
        demand=check['source_demand']
        if _sha(demand)!=source_sha256 or check['source_analysis_sha256']!=source_sha256:
            raise ValueError('Original dense field identity changed')
        replay_summary=_compact_source(demand)
        if _sha(replay_summary)!=_sha(summary):raise ValueError('Original dense field and saved summary differ')
        expected=_calculate(demand,normal_snapshot=normal_snapshot,model_origin=model_origin,
            normal_witness=True)
        if _sha(check)!=_sha(expected):raise ValueError('EN family saved arithmetic or authority differs from original source')
        _remember_verified(token)
    return True


def validate_saved(check, summary, *, normal_snapshot, source_sha256, model_origin):
    """Unchanged single-check API with fresh authorities, even on a cache hit."""
    return validate_saved_many([dict(check=check,summary=summary,source_sha256=source_sha256)],
        normal_snapshot=normal_snapshot,model_origin=model_origin)
