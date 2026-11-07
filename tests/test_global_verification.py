"""State-machine and typed-adapter controls, not structural design validation."""
import copy
import itertools
import json
import math

import unittest


def cases(names, values):
    """Standard-library parameterized cases, independent of pytest availability."""
    def decorate(function):
        function._case_names = [name.strip() for name in names.split(',')]
        function._case_values = values
        return function
    return decorate

from tercas.global_verification import (aggregate, check, build_global_verification,
    attach_global_verification, axial_interaction_record)


def numeric(key, value, state='ELU', **kw):
    return check(key, limit_state=state, source='Synthetic independent control',
                 qualified=True, index=value, **kw)


def pending(key, state='MODEL'):
    return check(key, limit_state=state, source='Explicit missing control', reason='Missing')


def na(key):
    return check(key, limit_state='ELU', source='Explicit domain control', qualified=True,
                 not_applicable=True, reason='Not applicable to this control')


def statuses(records):
    return {r['id']: r for r in records}


@cases('value', [None, float('nan'), float('inf'), -float('inf'), -1, True, False, '0', '0.5'])
def test_missing_invalid_not_zero(value):
    c = numeric('a', value)
    assert c['status'] == 'pending' and c['index'] is None
    r = aggregate(['a'], [c], inventory_qualified=True)
    assert r['status'] == 'inconclusivo'
    assert r['maximum_available_check'] is None


@cases('value, expected', [(0, 'meets'), (1, 'meets'),
    (math.nextafter(1, 0), 'meets'), (math.nextafter(1, math.inf), 'fails'), (1.01, 'fails')])
def test_exact_zero_and_boundary_no_rounded_comparison(value, expected):
    assert numeric('a', value)['status'] == expected


def test_no_source_no_qualification_and_no_assumed_exclusion():
    assert check('a', limit_state='ELU', source='', qualified=True, index=.5)['status'] == 'pending'
    assert check('a', limit_state='ELU', source='source', index=.5)['status'] == 'pending'
    assert check('a', limit_state='ELU', source='source', qualified=True,
                 not_applicable=True)['status'] == 'pending'
    assert check('a', limit_state='ELU', source='source', qualified=True,
                 not_applicable=True, reason='none', index=0)['status'] == 'pending'


def test_failure_precedes_pending_but_never_deletes_it():
    r = aggregate(['a', 'b'], [numeric('a', 1.2), pending('b')], inventory_qualified=True)
    assert r['status'] == 'reprovado' and not r['complete']
    assert r['failed_ids'] == ['a'] and r['pending_ids'] == ['b']


def test_known_failure_not_replaced_by_global_average_or_sum():
    r = aggregate(['a', 'b'], [numeric('a', 1.2), numeric('b', 0)], inventory_qualified=True)
    assert r['status'] == 'reprovado'
    r = aggregate(['a', 'b'], [numeric('a', .8), numeric('b', .8)], inventory_qualified=True)
    assert r['status'] == 'aprovado'
    assert r['maximum_available_check']['index'] == .8
    assert r['maximum_is_global_utilization'] is False


def test_missing_duplicate_and_unexpected_records_are_pending():
    assert aggregate(['a', 'b'], [numeric('a', .5)], inventory_qualified=True)['status'] == 'inconclusivo'
    r = aggregate(['a'], [numeric('a', .5), numeric('a', .6)], inventory_qualified=True)
    assert r['status'] == 'inconclusivo' and r['checks'][0]['index'] is None
    r = aggregate(['a'], [numeric('a', .5), numeric('b', .6)], inventory_qualified=True)
    assert r['status'] == 'inconclusivo' and 'unexpected:b' in r['pending_ids']


def test_empty_unqualified_all_excluded_inventory_not_approval():
    assert aggregate([], [], inventory_qualified=True)['status'] == 'inconclusivo'
    assert aggregate(['a'], [numeric('a', .5)])['status'] == 'inconclusivo'
    assert aggregate(['a'], [na('a')], inventory_qualified=True)['status'] == 'inconclusivo'
    with unittest.TestCase().assertRaises(ValueError): aggregate(['a', 'a'], [])


def test_missing_serialized_ratio_not_promoted_by_label():
    r = numeric('a', .5)
    r['index'] = None
    r['reason'] = 'An old valid ratio was removed'
    assert aggregate(['a'], [r], inventory_qualified=True)['status'] == 'inconclusivo'


def test_exhaustive_status_oracle_independent_boolean_truth_table():
    factory = {'pass': lambda k: numeric(k, .5), 'fail': lambda k: numeric(k, 1.1),
               'unknown': pending, 'excluded': na}
    for length in range(1, 6):
        for values in itertools.product(factory, repeat=length):
            keys = list(map(str, range(length)))
            records = [factory[v](k) for k, v in zip(keys, values)]
            r = aggregate(keys, records, inventory_qualified=True)
            expected = ('reprovado' if 'fail' in values else 'inconclusivo'
                        if 'unknown' in values or 'pass' not in values else 'aprovado')
            assert r['status'] == expected


def fixture(parallel=0, point=0, local_index=.2, els_index=.2):
    ev = dict(q_vector={'normal': .1, 'parallel': parallel},
              P_vector={'normal': point, 'parallel': 0},
              states=[dict(x_mm=0., side='right', normal={'V_N':150.}),
                      dict(x_mm=3000., side='left', normal={'V_N':-150.})])
    if parallel:
        ev['biaxial'] = dict(status='computed_fixed_position', missing=[],
            governing=dict(x_mm=1500., Mx_Nmm=112500., My_Nmm=10000., index=.3))
    return dict(schema='NBR14762_one_span_v1',
        model_domain_evidence={'status':'fixed_model_domain', 'conflict':None},
        input_data={'L_mm':3000., 'segments':[dict(start_mm=0., end_mm=3000.)]},
        NBR_branches={
            'local':dict(status='computed', index=local_index),
            'distortional':dict(status='computed', index=.3),
            'MV':dict(status='computed_fixed_load_position', result={'index_squared':.04, 'x_mm':1500.}),
            'point':dict(status='not_applicable') if point == 0 else dict(status='not_evaluated')},
        FLT_segments=[dict(status='computed_from_supplied_effective_lengths', index=.4)],
        section_checks={'shear':dict(status='computed_from_supplied_inputs', VRd_N=15000.)},
        ELS=dict(status='computed_bending_component', index=els_index,
                 criterion_status='meets' if els_index <= 1 else 'fails', x_mm=1500.),
        inclination_evidence={'ELU':copy.deepcopy(ev), 'ELS':copy.deepcopy(ev)},
        whole_member_approved=False)


def test_all_known_checks_meet_torsion_still_pending_no_input_mutation():
    r = fixture(); before = copy.deepcopy(r)
    g = build_global_verification(r)
    assert r == before
    assert g['status'] == 'inconclusivo'
    assert g['pending_ids'] == ['ELS:DIRECT_ELS:combined_ELS_scope', 'torsion_warping']
    assert not g['whole_member_approved'] and not g['current_adapter_can_approve']
    assert g['by_limit_state']['ELU']['status'] == 'inconclusivo'
    assert g['by_limit_state']['ELS']['status'] == 'inconclusivo'
    assert g['listed_checks_only']['ELU']['status'] == 'aprovado'
    assert g['listed_checks_only']['ELS']['status'] == 'inconclusivo'
    assert g['listed_checks_only_is_complete_limit_state_approval'] is False
    attached = attach_global_verification(r)
    assert attached['global_verification'] == g and 'global_verification' not in r


def test_qualified_failure_preserved_with_torsion_pending():
    g = build_global_verification(fixture(local_index=1.1))
    assert g['status'] == 'reprovado'
    assert g['counts']['fails'] == 1 and 'torsion_warping' in g['pending_ids']
    assert g['whole_member_approved'] is False
    assert 'Reprovado nos critérios calculados' in g['display_summary']


def test_invalid_or_provisional_number_never_becomes_failure():
    r = fixture(parallel=.1)
    r['inclination_evidence']['ELU']['biaxial']['governing']['index'] = 1.3
    r['inclination_evidence']['ELU']['provisional_hypothesis'] = True
    g = build_global_verification(r)
    c = statuses(g['checks'])['ELU:DIRECT_ELU:biaxial']
    assert c['status'] == 'pending' and c['diagnostic_index'] == 1.3
    assert g['status'] == 'inconclusivo'


def test_missing_secondary_component_not_inferred_zero():
    r = fixture()
    r['inclination_evidence']['ELU']['P_vector'].pop('parallel')
    g = build_global_verification(r)
    assert 'ELU:DIRECT_ELU:secondary_shear_scope' in g['pending_ids']
    assert 'ELU:DIRECT_ELU:point_introduction_scope' in g['pending_ids']


def test_secondary_component_and_els_diagnostic_are_internal_pending():
    r = fixture(parallel=.1)
    r['ELS'].update(status='not_evaluated', criterion_status='pending_combined_stiffness', diagnostic_only=True)
    g = build_global_verification(r)
    assert 'ELS:DIRECT_ELS:combined_ELS_scope' in g['pending_ids']
    assert 'ELS:DIRECT_ELS:deflection' in g['pending_ids']
    assert statuses(g['checks'])['ELS:DIRECT_ELS:deflection']['index'] is None


def test_local_point_only_when_present_and_support_not_zero():
    assert statuses(build_global_verification(fixture())['checks'])['ELU:DIRECT_ELU:point_introduction_scope']['status'] == 'not_applicable'
    r = fixture(point=1000.)
    r['NBR_branches']['point'].update(position='support_limit', force_N=1000.)
    g = build_global_verification(r)
    assert 'ELU:DIRECT_ELU:point_introduction_scope' in g['pending_ids']
    assert statuses(g['checks'])['ELU:DIRECT_ELU:point_introduction_scope']['trace']['P_normal_N'] == 1000.


@cases('segments', [[], [dict(start_mm=1., end_mm=3000.)],
    [dict(start_mm=0., end_mm=1500.), dict(start_mm=1501., end_mm=3000.)],
    [dict(start_mm=0., end_mm=1600.), dict(start_mm=1500., end_mm=3000.)]])
def test_flt_coverage_missing_and_overlap_pending(segments):
    r = fixture(); r['input_data']['segments'] = segments
    assert 'ELU:DIRECT_ELU:FLT_coverage' in build_global_verification(r)['pending_ids']


def batch_fixture():
    r = fixture()
    out = {k:copy.deepcopy(r[k]) for k in ['input_data', 'model_domain_evidence']}
    out.update(schema='tercas_batch_results_v1', cases=[], load_bundle={'combinations':[]})
    for state in ('ELU', 'ELS'):
        combo = {'id':'CASE_'+state, 'limit_state':state}
        ev = copy.deepcopy(r)
        ev['inclination'] = r['inclination_evidence'][state]
        out['load_bundle']['combinations'].append(combo)
        out['cases'].append({'combination':copy.deepcopy(combo), 'evidence':ev, 'rows':[]})
    return out


@cases('mutation', ['missing', 'duplicate', 'unexpected', 'empty', 'wrong_limit_state'])
def test_batch_inventory_does_not_drop_missing_cases(mutation):
    r = batch_fixture()
    if mutation == 'missing':r['cases'].pop()
    elif mutation == 'duplicate':r['cases'].append(copy.deepcopy(r['cases'][0]))
    elif mutation == 'unexpected':
        c = copy.deepcopy(r['cases'][0]); c['combination']['id'] = 'ALIEN'; r['cases'].append(c)
    elif mutation == 'empty':r['load_bundle']['combinations'] = []
    else:r['cases'][0]['combination']['limit_state'] = 'ELS'
    g = build_global_verification(r)
    assert g['status'] == 'inconclusivo' and len(g['pending_ids']) > 1


def test_filtering_out_els_never_means_els_approved():
    r = batch_fixture()
    r['cases'].pop();r['load_bundle']['combinations'].pop()
    g = build_global_verification(r)
    assert 'missing_limit_state:ELS' in g['pending_ids']


def test_presentation_tampering_does_not_change_aggregation():
    r = batch_fixture(); expected = build_global_verification(r)
    r['summary'] = [{'Índice':0, 'Situação':'Aprovado'}]
    r['cases'][0]['rows'] = [{'Verificação':'Flexão local', 'Índice':999., 'Situação':'Falhou'}]
    assert build_global_verification(r) == expected


def axial_fixture():
    state = dict(x_mm=600., side='interior', N_tension_positive_N=-20.,
                 Mstrong_Nmm=30., Mweak_Nmm=-40., numeric_index=.9)
    return dict(combination_id='C1', section_id='S1', stability_member_id='whole_span',
        region_id='R1', segment_id='seg1', origin='Independent simultaneous state fixture',
        status='concomitant_arithmetic_only', maximum=copy.deepcopy(state), states=[state],
        missing_capacity_keys=[], member_issues=[], analysis_8_1_qualified=False)


def axial(raw):
    return axial_interaction_record(raw, expected_combination_id='C1', expected_section_id='S1',
        expected_stability_member_id='whole_span', expected_region_id='R1', expected_segment_id='seg1')


def test_axial_keeps_same_combination_section_region_side():
    r = axial(axial_fixture())
    assert r['status'] == 'meets' and r['index'] == .9
    assert r['trace']['concomitant_state']['N_tension_positive_N'] == -20.
    assert r['trace']['analysis_8_1_qualified'] is False
    g = aggregate([r['id'], 'analysis', 'torsion'], [r, pending('analysis'), pending('torsion')], inventory_qualified=True)
    assert g['status'] == 'inconclusivo'


@cases('key', ['combination_id','section_id','stability_member_id','region_id','segment_id'])
def test_axial_different_binding_not_reused(key):
    raw = axial_fixture();raw[key] = 'OTHER'
    assert axial(raw)['status'] == 'pending'


def test_axial_missing_denominator_or_partial_capacity_not_zero():
    raw = axial_fixture();raw['missing_capacity_keys'] = ['Nt']
    assert axial(raw)['status'] == 'pending' and axial(raw)['index'] is None
    raw = axial_fixture();raw['maximum'] = None
    assert axial(raw)['status'] == 'pending'
    raw = axial_fixture();raw['member_issues'] = ['Slenderness outside supported domain']
    assert axial(raw)['status'] == 'pending'


def test_axial_extrema_cannot_be_spliced_or_falsely_select_nonmaximum():
    raw = axial_fixture();raw['maximum']['Mstrong_Nmm'] = 999.
    assert axial(raw)['status'] == 'pending'
    raw = axial_fixture();other = copy.deepcopy(raw['states'][0]);other['numeric_index'] = 1.2
    raw['states'].append(other)
    assert axial(raw)['status'] == 'pending'


def test_three_girt_never_falls_back_to_pure_bending():
    r = fixture(local_index=100.)
    r.update(schema='tercas_three_girt_results_v1', cases=[
        dict(combination={'id':'C1','limit_state':'ELU'},model={}),
        dict(combination={'id':'C2','limit_state':'ELS'},model={})])
    g = build_global_verification(r)
    assert g['status'] == 'inconclusivo' and g['counts']['fails'] == 0
    assert 'ELU:C1:axial_bending' in g['pending_ids']
    assert not g['rod_connection_design_included']
    assert not g['whole_member_approved']


def test_unknown_historical_schema_not_requalified():
    g = build_global_verification({'schema':'unknown','whole_member_approved':True})
    assert g['status'] == 'inconclusivo' and g['whole_member_approved'] is False
    assert 'unsupported_result_schema' in g['pending_ids']


def test_json_output_finite_even_if_input_index_nonfinite():
    r = fixture();r['NBR_branches']['local']['index'] = float('nan')
    json.dumps(build_global_verification(r), allow_nan=False)


def test_explicit_missing_mv_and_biaxial_indices_never_fall_back():
    r = fixture(parallel=.1)
    r['NBR_branches']['MV'].update(index=.2, result={})
    r['inclination_evidence']['ELU']['biaxial'].update(index=1.3, governing={})
    g = build_global_verification(r); c = statuses(g['checks'])
    assert c['ELU:DIRECT_ELU:MV']['status'] == 'pending'
    assert c['ELU:DIRECT_ELU:biaxial']['status'] == 'pending'
    assert g['status'] == 'inconclusivo'


def test_nonfinite_concomitant_trace_is_marked_and_json_safe():
    r = fixture();r['NBR_branches']['MV']['result']['index_squared'] = float('nan')
    g = build_global_verification(r); c = statuses(g['checks'])['ELU:DIRECT_ELU:MV']
    assert c['status'] == 'pending' and c['index'] is None
    assert c['trace']['concomitant_state']['index_squared'] is None
    assert c['invalid_trace_paths']
    json.dumps(g, allow_nan=False)


def test_axial_every_state_needs_actions_coordinate_and_side():
    r = axial_fixture()
    r['states'].append({'numeric_index':.1,'N_tension_positive_N':float('nan')})
    assert axial(r)['status'] == 'pending'
    json.dumps(axial(r), allow_nan=False)


def test_frame_requested_case_missing_is_explicit():
    r = dict(schema='tercas_three_girt_results_v1',
        model_domain_evidence={'status':'fixed_model_domain'}, input_data={'load_mode':'area'},
        load_bundle={'combinations':[{'id':'C1','limit_state':'ELU'}, {'id':'C2','limit_state':'ELU'},
                                     {'id':'C3','limit_state':'ELS'}]},
        cases=[{'combination':{'id':'C1','limit_state':'ELU'},'model':{}},
               {'combination':{'id':'C3','limit_state':'ELS'},'model':{}}])
    g = build_global_verification(r)
    assert 'ELU:C2:frame_case_missing_or_duplicate' in g['pending_ids']


def test_contradictory_flt_segment_identity_is_not_ignored():
    r = fixture()
    r['input_data']['segments'] = [dict(start_mm=0.,end_mm=1500.),dict(start_mm=1500.,end_mm=3000.)]
    r['FLT_segments'] = [dict(status='computed_from_supplied_effective_lengths', index=.2,segment_id='same_wrong')]*2
    g = build_global_verification(r)
    assert 'ELU:DIRECT_ELU:FLT:1' in g['pending_ids'] and 'ELU:DIRECT_ELU:FLT:2' in g['pending_ids']


def test_flt_snapshot_interval_mismatch_pending():
    r = fixture()
    r['input_snapshot'] = {'segments':[dict(start_mm=0.,end_mm=2000.)]}
    assert 'ELU:DIRECT_ELU:FLT:1' in build_global_verification(r)['pending_ids']


def test_flt_equal_indices_are_not_artificially_called_duplicate():
    r = fixture()
    r['input_data']['segments'] = [dict(start_mm=0.,end_mm=1500.),dict(start_mm=1500.,end_mm=3000.)]
    r['FLT_segments'] = [dict(status='computed_from_supplied_effective_lengths', index=.2)]*2
    g = build_global_verification(r); records = statuses(g['checks'])
    assert records['ELU:DIRECT_ELU:FLT:1']['status'] == records['ELU:DIRECT_ELU:FLT:2']['status'] == 'meets'
    assert records['ELU:DIRECT_ELU:FLT:1']['trace']['binding_basis'] == 'producer_order_v1'
    assert records['ELU:DIRECT_ELU:FLT:1']['trace']['binding_is_independent_identity'] is False


def test_axial_member_names_are_part_of_unique_key():
    a = axial_fixture();b = copy.deepcopy(a);b['stability_member_id'] = 'other_span'
    ra = axial(a)
    rb = axial_interaction_record(b,expected_combination_id='C1',expected_section_id='S1',
        expected_stability_member_id='other_span',expected_region_id='R1',expected_segment_id='seg1')
    assert ra['id'] != rb['id']


def test_distortional_exemption_needs_its_recorded_basis():
    r = fixture(); r['NBR_branches']['distortional'] = {'status':'exempt_Table14'}
    assert statuses(build_global_verification(r)['checks'])['ELU:DIRECT_ELU:distortional']['status'] == 'pending'
    r['NBR_branches']['distortional']['table'] = {'exempt':True}
    assert statuses(build_global_verification(r)['checks'])['ELU:DIRECT_ELU:distortional']['status'] == 'not_applicable'


def test_zero_parallel_top_load_does_not_exclude_torsional_service():
    # Exact scalar counterexample: a downward load at the web top is eccentric
    # from a channel's shear centre. No beam/matrix solve is needed.
    r = fixture(parallel=0)
    qx, qy = 0., -.1
    load_xy, shear_center_xy = [0., 99.4], [-18., 49.4]
    torque = (load_xy[0]-shear_center_xy[0])*qy - (load_xy[1]-shear_center_xy[1])*qx
    assert torque == -1.8 and qx == 0
    r['torsion_evidence'] = {'records': [{'combination_id': 'DIRECT_ELS',
        'limit_state': 'ELS', 'analysis': {'loads': [{'torque_SC_N': torque}]}}]}
    g = build_global_verification(r)
    record = next(v for v in g['checks'] if v['id'] == 'ELS:DIRECT_ELS:combined_ELS_scope')
    assert record['status'] == 'pending' and record['index'] is None
    assert record['trace']['torsional_displacement_excluded'] is False
    assert g['combined_ELS_approved'] is False


def test_missing_torsional_service_evidence_is_not_zero():
    for label in ('large_linear_rotation', 'zero_rotation', 'missing_rotation'):
        r = fixture(parallel=0)
        r['untrusted_service_label'] = label
        g = build_global_verification(r)
        assert 'ELS:DIRECT_ELS:combined_ELS_scope' in g['pending_ids']
        assert g['counts']['fails'] == 0


class TestGlobalVerification(unittest.TestCase):
    pass


for _name, _function in list(globals().items()):
    if not (_name.startswith('test_') and callable(_function)):
        continue
    _rows = getattr(_function, '_case_values', [None])
    for _i, _row in enumerate(_rows):
        def _run(self, fn=_function, row=_row):
            names = getattr(fn, '_case_names', [])
            if not names:
                fn()
            else:
                values = [row] if len(names) == 1 else row
                fn(**dict(zip(names, values)))
        setattr(TestGlobalVerification, _name+('_'+str(_i) if hasattr(_function, '_case_values') else ''), _run)
    del globals()[_name]

del _name, _function, _rows, _i, _row, _run


if __name__ == '__main__':
    unittest.main(verbosity=2)
