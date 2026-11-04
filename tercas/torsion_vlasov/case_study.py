"""One explicit case study from a preserved own-reference batch.

No new action combination, PP, load direction, strength or global verdict.
A UI must pass the saved case's declared lines/supports, not silent defaults.
"""
import copy
import hashlib
import json

from .adapter import _check_snapshot,attach_torsion_evidence,load_lines_from_cg,summarize_torsion_evidence
from .yield_envelope import member_yield_envelope,FIELDS
from .vlasov import METHOD
from .section import finite


def _saved_model(result,section,load_lines,supports):
    data=result['input_data'];choice=data.get('torsion_model');ev=result.get('torsion_evidence')
    if (not isinstance(choice,dict) or set(choice)!=set(('schema','enabled','support_hypothesis','load_lines')) or choice.get('schema')!='purlin_vlasov_choice_v1' or
            choice.get('enabled') is not True or choice.get('support_hypothesis')!='R01_fork_free_warping'):
        raise ValueError('Enabled saved R01 torsion-model choice required; do not infer a new model')
    if (not isinstance(ev,dict) or ev.get('schema') not in ('purlin_torsion_batch_evidence_v1','purlin_torsion_batch_summary_v1') or
            ev.get('method')!=METHOD or ev.get('source_input_fingerprint')!=result['input_fingerprint'] or
            ev.get('choice_snapshot')!=choice):
        raise ValueError('Saved torsion evidence does not match its input/model snapshot')
    records=choice.get('load_lines')
    if not isinstance(records,dict) or set(records)-set(('CP','SC','V_Cima','V_Baixo','P')):raise ValueError('Saved known-role line declarations required')
    complete={}
    for role,r in records.items():
        if not isinstance(r,dict) or set(r)!=set(('declared','xy_from_CG_mm','origin')) or type(r.get('declared')) is not bool:raise ValueError('Malformed saved line declaration')
        xy=r.get('xy_from_CG_mm');origin=r.get('origin')
        if not isinstance(xy,list) or len(xy)!=2 or not isinstance(origin,str):raise ValueError('Malformed saved line coordinates/origin')
        for value in xy:
            if value is not None:finite(value,'saved line coordinate')
        if r['declared'] and origin.strip() and all(v is not None for v in xy):complete[role]=r
    expected=load_lines_from_cg(section,complete)
    if load_lines!=expected or ev.get('load_lines')!=expected:
        raise ValueError('Selected-case lines differ from the preserved model; recalculate the base first')
    if supports!=ev.get('supports') or set(supports)!=set(('left','right')):
        raise ValueError('Selected-case supports differ from the preserved model')
    for side in ('left','right'):
        r=supports[side]
        if (not isinstance(r,dict) or set(r)!=set(('twist','warping','origin')) or r.get('twist')!='fixed' or r.get('warping')!='free_assumed' or
                not isinstance(r.get('origin'),str) or not r['origin'].strip()):
            raise ValueError('Independent saved R01 fork/free-warping support hypothesis required')
    original_ids={c['combination']['id'] for c in result['cases']};rows=ev.get('records',[])
    if len(rows)!=len(original_ids) or {r.get('combination_id') for r in rows}!=original_ids:
        raise ValueError('Saved torsion evidence has missing or duplicate source combinations')
    if any(r.get('source_input_fingerprint')!=result['input_fingerprint'] for r in rows):
        raise ValueError('Saved case torsion evidence is stale')
    return ev


def study_selected_combination(result,combination_id,*,section,load_lines,supports,elements_per_interval=32,
                               relative_tolerance=1e-6,absolute_tolerance_MPa=1e-6,max_subdivisions=20000):
    """Return a compact supplementary record; the original snapshot is untouched."""
    data,bundle=_check_snapshot(result,section)
    chosen=next((c for c in result['cases'] if c['combination']['id']==combination_id),None)
    if chosen is None:raise ValueError('Selected combination does not exist in the preserved snapshot')
    saved=_saved_model(result,section,load_lines,supports)
    definition=dict(source_input_fingerprint=result['input_fingerprint'],combination=chosen['combination'],
        section_content_sha256=section['content_sha256'],load_lines=load_lines,supports=supports,
        elements_per_interval=elements_per_interval,relative_tolerance=relative_tolerance,
        absolute_tolerance_MPa=absolute_tolerance_MPa,max_subdivisions=max_subdivisions)
    digest=hashlib.sha256(json.dumps(definition,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    selected=dict(schema=result['schema'],input_data=copy.deepcopy(data),input_fingerprint=result['input_fingerprint'],
                  load_bundle=copy.deepcopy(bundle),cases=[copy.deepcopy(chosen)],whole_member_approved=False)
    selected['load_bundle']['combinations']=[copy.deepcopy(chosen['combination'])]
    ev=attach_torsion_evidence(selected,section=section,load_lines=load_lines,supports=supports,
        elements_per_interval=elements_per_interval)['torsion_evidence'];record=ev['records'][0]
    packet=dict(schema='purlin_selected_material_study_v1',combination_id=combination_id,
        source_input_fingerprint=result['input_fingerprint'],case_model_sha256=digest,
        source_combination=copy.deepcopy(chosen['combination']),load_lines=copy.deepcopy(load_lines),supports=copy.deepcopy(supports),
        source_snapshot_preserved=True,all_existing_strength_and_ELS_results_unchanged=True,
        coverage_complete=False,resistance_qualified=False,normative_resistance_qualified=False,
        physical_design_approved=False,whole_member_approved=False)
    if record['analysis'] is None:
        packet.update(status=record['status'],missing=record['missing'],material_envelope=None)
        if 'numerical_diagnostics' in record:packet['numerical_diagnostics']=copy.deepcopy(record['numerical_diagnostics'])
        return packet
    analysis=record['analysis']
    saved_record=next(r for r in saved['records'] if r['combination_id']==combination_id)
    previous=saved_record.get('analysis')
    if previous is None:
        raise ValueError('Saved case has no qualified dense-field provenance; recalculate the base first')
    old_count=previous.get('element_count',len(previous.get('elements',[])))
    if old_count!=len(analysis['elements']) or previous.get('section',{}).get('content_sha256')!=section['content_sha256']:
        raise ValueError('Selected reconstruction mesh/section differs from the saved field')
    if {k:v for k,v in saved_record.items() if k!='analysis'}!={k:v for k,v in record.items() if k!='analysis'}:
        raise ValueError('Saved case qualification/provenance differs from the reconstruction')
    if previous.get('schema')=='single_vlasov_member_summary_v1':
        rebuilt=summarize_torsion_evidence(ev)['records'][0]['analysis']
    elif previous.get('schema')=='single_vlasov_member_demand_v1':rebuilt=analysis
    else:raise ValueError('Unsupported saved analysis schema')
    if previous!=rebuilt:
        raise ValueError('Saved elastic field does not reproduce exactly; recalculate the base in the current environment first')
    env=member_yield_envelope(analysis,fy_MPa=data['properties']['fy_MPa'],
        material_origin='Nominal fy from the same preserved own-reference input; no resistance factor',
        relative_tolerance=relative_tolerance,absolute_tolerance_MPa=absolute_tolerance_MPa,max_subdivisions=max_subdivisions)
    packet.update(status='computed_partial_material_envelope' if env['all_requested_field_bounds_converged'] else 'bounded_material_field_not_converged',
        material_envelope=env,source_actions=copy.deepcopy(analysis['loads']),source_analysis_domain=copy.deepcopy(analysis['analysis_domain']),
        source_numerics=copy.deepcopy(analysis['numerics']),
        scope='Explicit selected-case nominal material study only; no normative torsional or member resistance release')
    return packet
