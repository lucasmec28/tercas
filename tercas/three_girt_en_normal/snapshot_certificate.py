"""Replay bound coverage and physical finalists on the pinned seven Ue sections.
No network solve, extrema search or numerical envelope is allowed here.
"""
from . import application as engine
from .application import fingerprint as digest

def _verify_sign_pieces(component,demand):
    """Rebuild signed coverage/branch identities, not their numerical envelopes."""
    import math
    from . import shear_interaction as shear, bound_certificate as bc, witness_certificate as wc
    from ..three_girt_warping.application import recover_exported_state
    from ..torsion_study import section_for
    section=section_for(demand['input_data']);build_fields=shear.section_field_builder(section)
    sources={(case['combination']['id'],beam['id']):(case,beam) for case in demand['cases']
             if case['combination']['limit_state']=='ELU' for beam in case['model']['beams']}
    cert=component['component_sections'];fiber_count=4*(len(section['nodes_xy_mm'])-1)
    if cert['nodes_sha256']!=section['nodes_sha256'] or cert['thickness_mm']!=section['thickness_mm']:
        raise ValueError('Certified EN section differs from pinned demand geometry')
    if component.get('section_fibers_checked')!=fiber_count:
        raise ValueError('EN section face coverage changed')
    for row in component['rows']:
        case,beam=sources[(row['combination_id'],row['segment_id'])]
        torsion=engine.f.torsion_field(beam['torsion_state_parameters'])
        edge0=recover_exported_state(case['model'],beam,beam['x_start_mm'])
        edge1=recover_exported_state(case['model'],beam,beam['x_end_mm'])
        torque=[edge0['T_equilibrium_SC_Nmm'],edge1['T_equilibrium_SC_Nmm']-edge0['T_equilibrium_SC_Nmm']]
        fields_cache={}
        polys,transport=engine._transport_polynomials(row['normal_action_reference']['original_polynomials_R01'],cert)
        evaluate,_=engine._physical_witness_evaluator(case,beam,section,polys,torsion,cert,transport,
            component['normal_limit_MPa'],prune=False)
        intervals=engine._integral_sign_intervals(polys,cert)
        if len(row['pieces'])!=len(intervals):raise ValueError('EN signed-interval coverage changed')
        for piece,interval in zip(row['pieces'],intervals):
            keys={axis:engine._component_key(axis,sign) for axis,sign in interval['signs'].items()}
            required={axis:[engine._component_key(axis,sign) for sign in signs if sign]
                      for axis,signs in interval['required_signs'].items()}
            blocked={key:cert['components'][key]['blocking_reasons'] for values in required.values()
                     for key in values if not cert['components'][key]['eligible']}
            expected=dict(**interval,component_keys=keys,required_component_keys=required,blocking_components=blocked,
                complete=not blocked,branch_policy='union_of_required_signed_coefficients',
                bracket=[interval['left'],interval['right']],maximum_absolute_semantics='lower_witness_not_exact_maximum')
            if any(digest(piece.get(k))!=digest(v) for k,v in expected.items()):
                raise ValueError('EN signed interval or eligible-operator coverage changed')
            if blocked:
                if (piece.get('branch_count')!=0 or piece.get('maximum_absolute') is not None
                    or piece.get('shear_interaction') is not None
                    or digest(piece.get('normal'))!=digest(engine._normal_aggregate([],False))):
                    raise ValueError('Blocked EN interval acquired a stress result')
                continue
            branches=engine._coefficient_branches(interval,cert)
            if (piece.get('branch_count')!=len(branches)
                or [r['component_keys'] for r in piece.get('branches',[])]!=[keys for keys,_ in branches]
                or piece.get('section_fibers_checked')!=fiber_count):
                raise ValueError('EN signed branch/fiber inventory changed')
            for saved,(_,coefficients) in zip(piece['branches'],branches):
                operator=tuple((axis,tuple(coefficients[axis])) for axis in sorted(coefficients))
                if operator not in fields_cache:
                    fields_cache[operator]=build_fields(polys,coefficients,torsion,torque,beam['length_mm'])
                fields,tw=fields_cache[operator]
                proven=bc.verify(saved.get('bound_certificate'),fields,tw,torsion,
                    interval['left'],interval['right'],component['normal_limit_MPa'])
                for key,value in proven.items():
                    claimed=saved['index_upper_bounds'][key]
                    if type(claimed) not in (int,float) or not math.isfinite(claimed) or claimed<value:
                        raise ValueError('EN branch upper below authenticated interval certificate')
            wc.verify_piece(piece,evaluate,fields,tw,torsion,component['normal_limit_MPa'])
            si=piece.get('shear_interaction',{})
            if si.get('complete') is not True or si.get('checked_intervals')!=len(branches):
                raise ValueError('EN branch aggregation coverage changed')
            for key in ('normal','shear','interaction'):
                upper=[b['index_upper_bounds'][key] for b in piece['branches']]
                if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in upper):
                    raise ValueError('Invalid saved EN branch upper bound')
                if si[key]['index_upper_bound']!=max(upper):
                    raise ValueError('EN piece upper differs from saved branches')
                if key=='normal' and piece['normal']['index_upper_bound']!=max(upper):
                    raise ValueError('EN normal piece upper differs from saved branches')
            if (digest(piece['maximum_absolute'])!=digest(piece['normal']['witness'])
                or piece['normal_criterion']!=piece['normal']['criterion']):
                raise ValueError('EN piece witness/criterion alias changed')


def _verify_aggregates(component):
    """Reconcile every parent from its saved children, without new envelopes."""
    from . import shear_interaction as si
    for row in component['rows']:
        pieces=row['pieces'];complete=all(p['complete'] for p in pieces)
        normal=engine._normal_aggregate([p['normal'] for p in pieces if p['complete']],complete)
        winner=normal['witness']
        expected=dict(complete=complete,normal=normal,normal_criterion=normal['criterion'],
            shear_interaction=si.aggregate([p['shear_interaction'] for p in pieces],complete),
            complete_envelope_semantics='lower_witness_not_exact_maximum',
            complete_envelope=winner if complete else None,partial_maximum=winner if not complete else None,
            observed_normal_exceedance=bool(normal['index_lower_witness'] is not None and normal['index_lower_witness']>1),
            blocking_components=sorted({k for p in pieces for k in p['blocking_components']}))
        if any(digest(row.get(k))!=digest(v) for k,v in expected.items()):
            raise ValueError('EN row aggregate differs from saved sign pieces')
    for level,member in component['per_member'].items():
        rows=[r for r in component['rows'] if r['girt']==level];complete=all(r['complete'] for r in rows)
        normal=engine._normal_aggregate([p['normal'] for r in rows for p in r['pieces'] if p['complete']],complete)
        winner=normal['witness']
        expected=dict(ELU_segments=len(rows),complete_segments=sum(r['complete'] for r in rows),
            shear_interaction=si.aggregate([p['shear_interaction'] for r in rows for p in r['pieces']],complete),
            complete_sign_pieces=sum(p['complete'] for r in rows for p in r['pieces']),
            total_sign_pieces=sum(len(r['pieces']) for r in rows),complete=complete,normal=normal,
            complete_envelope_semantics='lower_witness_not_exact_maximum',
            complete_envelope=winner if complete else None,partial_maximum=winner if not complete else None,
            blocking_components=sorted({k for r in rows for k in r['blocking_components']}),
            observed_normal_exceedance=bool(normal['index_lower_witness'] is not None and normal['index_lower_witness']>1),
            normal_criterion=normal['criterion'])
        if digest(member)!=digest(expected):
            raise ValueError('EN member aggregate differs from saved rows/pieces')



def verify(component,demand):
    from . import centroid_policy as cp
    engine._validate_configuration(demand,component['configuration'])
    cert=component['component_sections']
    # Operator authority is mandatory even when the optional 6.27 is absent.
    from ..en_interaction_capacity_reference import qualified_reference
    qualified_reference(demand['input_data']['properties']['t'],cert['content_sha256'])
    if (component['normal_limit_MPa']!=cert['normal_yield_limit_MPa']
        or component['normal_limit_MPa']!=250.
        or component['source_geometry']!=demand['source_geometry']
        or component['demand_material_E_MPa']!=demand['input_data']['properties']['E_MPa']
        or component['resistance_material_E_MPa']!=cert['material']['E_MPa']
        or component['ELU_combinations']!=sum(c['combination']['limit_state']=='ELU' for c in demand['cases'])
        or component['ELS_combinations_excluded']!=sum(c['combination']['limit_state']=='ELS' for c in demand['cases'])):
        raise ValueError('Certified EN material, source or combination count changed')
    if any(cp.FIELD not in row for row in component['rows']):
        raise ValueError('Certified EN centroid policy coverage missing')
    _verify_sign_pieces(component,demand)
    _verify_aggregates(component)
