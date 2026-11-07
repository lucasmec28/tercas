"""Pure panorama routing/bounds tests; no member solve, UI or live source.

The comparator source is mocked only for contract projection tests. Actual
consumer authentication is covered by test_isolated_service_component and is
also exercised here on a genuinely pending, solver-free component.
"""
import copy
from unittest.mock import patch
import pytest
from tercas import isolated_service_panorama as p,isolated_service_component as c
from tercas.global_verification import check,aggregate,display_summary


def packet(lo=.4,hi=.5,*,sufficient=True,kind='existing',criterion='declared_limit'):
    cid='DIRECT_ELS' if kind=='existing' else 'SERVICE_A1_F_CHARACTERISTIC_SUCTION'
    cfg=c.blank_choice();cfg.update(criterion=criterion,point_xy_from_CG_mm=[-12.,50.],projection_xy=[0.,-1.],
        point_label='Ponto do topo',direction_label='Normal local',reference_declared=True,limit_mm=20.,nominal_intact_section_declared=True)
    state=('within_declared_linear_model' if hi<=1 else 'above_declared_linear_model' if lo>1 else 'numerical_boundary_inconclusive') if sufficient else 'gross_MLE_sufficient_condition_inconclusive'
    result=dict(schema='NBR14762_one_span_v1',input_fingerprint='SYNTHETIC_INPUT',whole_member_approved=False,
        model_domain_evidence=dict(status='fixed_model_domain',conflict=False))
    calc=dict(index_lower=lo if sufficient else None,index_upper=hi if sufficient else None,limit_mm=20.,
        envelope=dict(abs_displacement_lower_mm=lo*20,abs_displacement_upper_mm=hi*20),
        criterion_status=state,gross_screen=dict(gross_local_normal_sufficient=sufficient),
        stored_linear_twist_max_rad=.03,rotation_screening_warning=False,physical_first_order_applicability_qualified=False)
    source=dict(id=cid,kind=kind,source_combination=dict(id=cid,limit_state='ELS',source='synthetic exact source'))
    if kind=='supplementary_suction':source['source_combination'].update(q_vector=dict(normal=-.3,parallel=0.),source_cases=['V_Cima'])
    row=dict(id=cid,kind=kind,status='computed_linear_comparison',comparison=calc,source_dense_sha256='dense source digest',
        source_summary_sha256='summary source digest',supplementary_summary=None)
    ev=dict(schema=c.SCHEMA,configuration=cfg,source_input_fingerprint='SYNTHETIC_INPUT',
        source_torsion_snapshot_sha256='TORSION_SOURCE',records=[row],inventory=[source],missing=[])
    result[c.FIELD]=ev
    return result


def old():
    return [check('model_domain',limit_state='MODEL',source='existing model source',reason='Existing declared model',qualified=True,verdict='meets'),
        check('ELS:DIRECT_ELS:combined_ELS_scope',limit_state='ELS',source='existing scope source',reason='Original physical ELS pending.'),
        check('ELS:DIRECT_ELS:deflection',limit_state='ELS',source='original uniaxial source',index=.2,qualified=True)]


def trusted(monkeypatch,result):
    monkeypatch.setattr(c,'saved',lambda r:copy.deepcopy(r[c.FIELD]))
    return result


def build(result,records=None):
    added,binding=p.apply(result,old() if records is None else records)
    result=copy.deepcopy(result);summary=aggregate([r['id'] for r in added],added,inventory_qualified=True)
    summary.update({k:False for k in p.FALSE_FLAGS});summary[p.BINDING]=binding
    summary['display_summary']=display_summary(summary)
    result['global_verification']=summary
    return result


def test_saved_banner_cannot_be_promoted_without_changing_criteria(monkeypatch):
    r=build(trusted(monkeypatch,packet()))
    r['global_verification']['display_summary']='Aprovado integralmente'
    with pytest.raises(ValueError,match='Texto do panorama'):p.validate_saved(r)


@pytest.mark.parametrize('lo,hi,status,bound,index',[
    (0.,0.,'meets','upper',0.),(.5,.8,'meets','upper',.8),(.9,1.,'meets','upper',1.),
    (1.,1.,'meets','upper',1.),(1.01,1.4,'fails','lower',1.01),
    (.99,1.01,'pending','diagnostic_upper_only',None),(1.,1.01,'pending','diagnostic_upper_only',None)])
def test_bounds_are_conditional_and_never_upper_bound_false_failure(monkeypatch,lo,hi,status,bound,index):
    r=build(trusted(monkeypatch,packet(lo,hi)));p.validate_saved(r)
    item=next(x for x in r['global_verification']['checks'] if x['id'].endswith(':'+p.SUFFIX))
    assert item['status']==status and item['index']==index
    assert item['trace']['selected_index_bound']==bound and item['trace']['physical_ELS_approval'] is False
    assert item['trace']['source_configuration']['point_xy_from_CG_mm']==[-12.,50.]
    assert item['trace']['source_configuration']['reference']=='physical_end_chord_same_point'
    assert not r['whole_member_approved'] and not r['global_verification']['combined_ELS_approved']
    physical=next(x for x in r['global_verification']['checks'] if x['id'].endswith(':combined_ELS_scope'))
    assert physical['status']=='meets' and physical['index'] is None and 'Cálculo combinado completo' in physical['reason']
    assert physical['trace']['coverage_is_numerical_acceptance'] is False
    assert [x for x in r['global_verification']['checks'] if x['limit_state']=='MODEL']==old()[:1]


def test_failed_sufficient_MLE_screen_does_not_become_failure(monkeypatch):
    r=build(trusted(monkeypatch,packet(3.,4.,sufficient=False)));p.validate_saved(r)
    item=next(x for x in r['global_verification']['checks'] if x['id'].endswith(':'+p.SUFFIX))
    assert item['status']=='pending' and item['index'] is None and item['diagnostic_index'] is None
    assert 'inconclusiva' in item['reason']


def test_note_f_keeps_its_own_id_vector_and_source_not_nearest_case(monkeypatch):
    r=trusted(monkeypatch,packet(.5,.7,kind='supplementary_suction',criterion='nbr_A1_pair'))
    before=copy.deepcopy(r);built=build(r);p.validate_saved(built);assert r==before
    item=built['global_verification']['checks'][-1]
    assert item['id']=='ELS:SERVICE_A1_F_CHARACTERISTIC_SUCTION:'+p.SUFFIX
    assert item['trace']['source_case_kind']=='supplementary_suction'
    assert item['trace']['stored_linear_twist_max_rad']==.03
    assert item['trace']['rotation_screening_warning'] is False
    assert item['trace']['rotation_warning_is_normative_limit'] is False
    assert item['trace']['source_combination']['source_cases']==['V_Cima']
    assert item['trace']['source_combination']['q_vector']==dict(normal=-.3,parallel=0.)
    coverage=built['global_verification']['checks'][1]
    assert coverage['status']=='pending' and 'Nenhum campo combinado' in coverage['reason']


@pytest.mark.parametrize('state',['pending','not_applicable'])
def test_inventory_cases_do_not_disappear(monkeypatch,state):
    r=packet(kind='supplementary_suction');ev=r[c.FIELD];row=ev['records'][0]
    row.update(status=state,comparison=None,reason='Explicit missing source' if state=='pending' else 'Explicitly zero characteristic wind')
    if state=='not_applicable':row['kind']=ev['inventory'][0]['kind']='zero_characteristic_wind'
    built=build(trusted(monkeypatch,r));p.validate_saved(built)
    assert built['global_verification']['checks'][-1]['status']==state
    assert built['global_verification']['checks'][-1]['index'] is None


def test_empty_selection_is_pending_not_all_empty_approval(monkeypatch):
    r=packet();r[c.FIELD].update(records=[],inventory=[],missing=['Criterion not selected'])
    built=build(trusted(monkeypatch,r));p.validate_saved(built)
    row=built['global_verification']['checks'][-1]
    assert row['id']=='ELS:SERVICE_SELECTION:'+p.SUFFIX and row['status']=='pending'


@pytest.mark.parametrize('change',['conflict','absent'])
def test_model_conflict_retains_unqualified_numeric_diagnostic(monkeypatch,change):
    r=packet()
    if change=='conflict':r['model_domain_evidence']['conflict']='incompatible source'
    else:r.pop('model_domain_evidence')
    built=build(trusted(monkeypatch,r));p.validate_saved(built)
    item=built['global_verification']['checks'][-1]
    assert item['status']=='pending' and item['index'] is None and item['diagnostic_index']==.5


@pytest.mark.parametrize('change',['remove','duplicate','index','bound','point','criterion','source_case','binding','binding_removed','scope_approval','scope_missing','scope_annotation','global_approval','field_removed','new_unbound'])
def test_saved_changes_fail_closed(monkeypatch,change):
    r=build(trusted(monkeypatch,packet()));g=r['global_verification'];row=g['checks'][-1]
    if change=='remove':g['checks'].pop()
    elif change=='duplicate':g['checks'].append(copy.deepcopy(row))
    elif change=='index':row['index']=0.
    elif change=='bound':row['trace']['index_upper']=.1
    elif change=='point':row['trace']['source_configuration']['point_xy_from_CG_mm'][0]=0.
    elif change=='criterion':row['trace']['source_configuration']['limit_mm']=30.
    elif change=='source_case':r[c.FIELD]['inventory'][0]['source_combination']['source']='different source'
    elif change=='binding':g[p.BINDING]['source_packet_sha256']='forged'
    elif change=='binding_removed':g.pop(p.BINDING)
    elif change=='scope_approval':g['checks'][1].update(status='meets',index=.1)
    elif change=='scope_missing':g['checks'].pop(1)
    elif change=='scope_annotation':g['checks'][1]['reason']='All service done'
    elif change=='global_approval':g['combined_ELS_approved']=True
    elif change=='field_removed':r.pop(c.FIELD)
    elif change=='new_unbound':row['id']='ELS:forged:'+p.SUFFIX
    with pytest.raises(ValueError):p.validate_saved(r)


def test_reader_and_apply_do_not_call_member_solver(monkeypatch):
    r=trusted(monkeypatch,packet())
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no member solve')):
        built=build(r);p.validate_saved(built)


def test_authentication_failure_is_not_suppressed(monkeypatch):
    r=packet()
    def fail(r):raise ValueError('invalid dense certificate')
    monkeypatch.setattr(c,'saved',fail)
    with pytest.raises(ValueError,match='invalid dense certificate'):p.apply(r,old())


def test_old_history_unchanged_even_if_component_predates_panorama(monkeypatch):
    baseline=old();before=copy.deepcopy(baseline)
    with patch.object(c,'saved',side_effect=AssertionError('no historical upgrade')):
        assert p.apply({},baseline)==(baseline,None)
        p.validate_saved({'global_verification':dict(checks=baseline)})
        p.validate_saved({c.FIELD:packet()[c.FIELD],'global_verification':dict(checks=baseline)})
    assert baseline==before


def test_apply_no_mutation_or_duplicate_overlay(monkeypatch):
    r=trusted(monkeypatch,packet());base=old();before=copy.deepcopy((r,base))
    records,_=p.apply(r,base);assert (r,base)==before
    with pytest.raises(ValueError,match='já aplicado'):p.apply(r,records)


@pytest.mark.parametrize('change',['missing','duplicate','already_approved'])
def test_physical_scope_is_never_silently_removed_or_approved(monkeypatch,change):
    r=trusted(monkeypatch,packet());base=old()
    if change=='missing':base.pop(1)
    elif change=='duplicate':base.append(copy.deepcopy(base[1]))
    else:base[1].update(status='meets',index=.2)
    with pytest.raises(ValueError):p.apply(r,base)


def test_real_pending_component_authentication_without_solver():
    from test_isolated_service_component import source
    from tercas.application import fingerprint
    result,section,_,_=source();cfg=result['input_data'][c.CHOICE]
    cfg['point_xy_from_CG_mm']=[None,None];result['input_fingerprint']=fingerprint(result['input_data'])
    result['model_domain_evidence']=dict(status='fixed_model_domain',conflict=False)
    result['whole_member_approved']=False
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')):
        result=c.finalize(c.attach_dense(result,section))
        cid=result['cases'][0]['combination']['id']
        marker=check('ELS:'+cid+':combined_ELS_scope',limit_state='ELS',source='existing marker',reason='No combined field yet')
        built=build(result,[marker]);p.validate_saved(built)
    assert len(built['global_verification']['checks'])==3
    assert all(r['status']=='pending' for r in built['global_verification']['checks'])
    built[c.FIELD]['configuration']['point_label']='altered even if panorama binding changed'
    with pytest.raises(ValueError):p.validate_saved(built)


def test_orphan_annotation_on_uncalculated_case_is_rejected(monkeypatch):
    r=build(trusted(monkeypatch,packet()))
    r['global_verification']['checks'][2]['trace'][p.ANNOTATION]=copy.deepcopy(r['global_verification']['checks'][1]['trace'][p.ANNOTATION])
    with pytest.raises(ValueError,match='órfã'):p.validate_saved(r)


@pytest.mark.parametrize('key',['status','complete','counts','pending_ids','failed_ids','by_limit_state','maximum_available_check'])
def test_derived_summary_cannot_disagree_with_saved_criteria(monkeypatch,key):
    r=build(trusted(monkeypatch,packet(1.1,1.3)))
    r['global_verification'][key]='forged summary'
    with pytest.raises(ValueError,match='Resumo global divergente'):p.validate_saved(r)


@pytest.mark.parametrize('phi,warning',[(.02,False),(.0536,True),(.1755,True),(1.1,True),(3.,True)])
def test_rotation_warning_and_fixed_physical_flag_do_not_block_calculation_coverage(monkeypatch,phi,warning):
    r=packet();calc=r[c.FIELD]['records'][0]['comparison']
    calc.update(stored_linear_twist_max_rad=phi,rotation_screening_warning=warning,physical_first_order_applicability_qualified=False)
    built=build(trusted(monkeypatch,r));p.validate_saved(built)
    coverage=built['global_verification']['checks'][1];annotation=coverage['trace'][p.ANNOTATION]
    assert coverage['status']=='meets' and annotation['stored_linear_twist_max_rad']==phi
    assert annotation['rotation_screening_warning'] is warning
    assert annotation['rotation_warning_is_normative_limit'] is False
    assert annotation['physical_first_order_flag_is_coverage_gate'] is False
    assert not built['whole_member_approved'] and not built['global_verification']['combined_ELS_approved']


def test_MLE_inconclusive_keeps_concrete_coverage_pending(monkeypatch):
    built=build(trusted(monkeypatch,packet(2.,3.,sufficient=False)));p.validate_saved(built)
    coverage=built['global_verification']['checks'][1]
    assert coverage['status']=='pending' and 'MLE inconclusivo' in coverage['reason']
    assert coverage['trace'][p.ANNOTATION]['missing']


@pytest.mark.parametrize('missing',['field','point','direction','chord','criterion','limit'])
def test_actual_missing_calculation_data_remains_concretely_pending(monkeypatch,missing):
    r=packet();ev=r[c.FIELD];cfg=ev['configuration'];row=ev['records'][0]
    row.update(status='pending',comparison=None,reason='Campo combinado ausente.')
    if missing=='point':cfg['point_xy_from_CG_mm']=[None,None]
    elif missing=='direction':cfg['projection_xy']=[None,None]
    elif missing=='chord':cfg['reference_declared']=False
    elif missing=='criterion':cfg['criterion']=None
    elif missing=='limit':cfg['limit_mm']=None
    built=build(trusted(monkeypatch,r));p.validate_saved(built)
    coverage=built['global_verification']['checks'][1]
    assert coverage['status']=='pending' and coverage['trace'][p.ANNOTATION]['missing']
    assert 'Cobertura do cálculo pendente' in coverage['reason']


def test_empty_origin_text_is_not_a_new_certificate_requirement(monkeypatch):
    r=packet();r[c.FIELD]['configuration'].update(model_origin='',criterion_origin='')
    built=build(trusted(monkeypatch,r));p.validate_saved(built)
    coverage=built['global_verification']['checks'][1]
    assert coverage['status']=='meets'
    assert coverage['trace'][p.ANNOTATION]['calculation_portion']=='total_selected_combination_without_camber_relative_to_same_point_end_chord'


@pytest.mark.parametrize('criterion',['declared_limit','nbr_A1_pair'])
def test_ponding_is_separate_system_requirement_not_case_gate_or_exemption(monkeypatch,criterion):
    r=packet(criterion=criterion);built=build(trusted(monkeypatch,r));p.validate_saved(built)
    scope=built['global_verification'][p.BINDING]['system_scope']
    assert scope['ponding']['status']=='outside_point_displacement_calculation'
    assert 'nota g' in scope['ponding']['requirement']
    assert 'sem reprovação nem dispensa' in scope['ponding']['reason']
    assert not any('ponding' in row['id'] for row in built['global_verification']['checks'])
    assert built['global_verification']['checks'][1]['status']=='meets'


def test_cases_outside_selected_A1_pair_are_not_exempted_from_general_ELS(monkeypatch):
    r=packet(criterion='nbr_A1_pair');r['schema']='tercas_batch_results_v1'
    selected=dict(id='DIRECT_ELS',limit_state='ELS',type='ELS rara',coefficients={'PP':1.,'CP':1.,'SC':1.})
    frequent=dict(id='FREQ',limit_state='ELS',type='ELS frequente',coefficients={'PP':1.,'CP':1.,'SC':.4})
    ascent=dict(id='UP_WITH_PP',limit_state='ELS',type='ELS rara',coefficients={'PP':1.,'CP':1.,'V_Cima':1.})
    r['load_bundle']={'combinations':[selected,frequent,ascent]}
    r['cases']=[{'combination':copy.deepcopy(x)} for x in r['load_bundle']['combinations']]
    r[c.FIELD]['inventory'][0]['source_combination']=selected
    base=old()+[check('ELS:'+x['id']+':combined_ELS_scope',limit_state='ELS',source='old generic',reason='Combined ELS not covered') for x in (frequent,ascent)]
    built=build(trusted(monkeypatch,r),base);p.validate_saved(built)
    for cid in ('FREQ','UP_WITH_PP'):
        row=next(v for v in built['global_verification']['checks'] if v['id']=='ELS:'+cid+':combined_ELS_scope')
        ann=row['trace'][p.ANNOTATION]
        assert row['status']=='not_applicable' and ann['outside_selected_A1_pair_only'] is True
        assert ann['general_ELS_exemption'] is False and ann['criterion_id'] is None
        assert ann['source_combination']['id']==cid
        assert 'não é dispensa geral' in row['reason']


def test_coverage_tampering_cannot_be_hidden_by_reaggregating_summary(monkeypatch):
    r=build(trusted(monkeypatch,packet()));g=r['global_verification']
    g['checks'][1]['trace'][p.ANNOTATION]['calculation_portion']='all construction stages and ponding'
    derived=aggregate([x['id'] for x in g['checks']],g['checks'],inventory_qualified=True)
    for key in ('status','complete','counts','failed_ids','pending_ids','maximum_available_check','maximum_is_global_utilization','by_limit_state','listed_checks_only','listed_checks_only_is_complete_limit_state_approval'):
        g[key]=derived[key]
    g['display_summary']=display_summary(g)
    with pytest.raises(ValueError,match='Cobertura do cálculo ELS'):p.validate_saved(r)


def default_pending_source():
    r=packet();r['input_data']={'load_mode':'direct','ELS_limit_mm':None,'ELS_origin':''}
    r['input_snapshot']={'ELS_limit_mm':{'value':None,'origin':''},'SLS':{'origin':'synthetic'}}
    r['ELS']={'status':'not_evaluated','missing':['Ml with origin']}
    base=old();base[2]=check('ELS:DIRECT_ELS:deflection',limit_state='ELS',source='MSE default',reason='Ml with origin')
    return r,base


def test_only_unavailable_automatic_default_without_effective_criterion_is_retired(monkeypatch):
    r,base=default_pending_source();before=copy.deepcopy((r,base))
    built=build(trusted(monkeypatch,r),base);p.validate_saved(built)
    assert (r,base)==before
    row=built['global_verification']['checks'][2];ann=row['trace'][p.ANNOTATION]
    assert row['status']=='not_applicable' and row['index'] is None
    assert ann['old_MSE_or_Ml_calculated'] is False
    assert ann['physical_equivalence_or_dominance_claimed'] is False
    assert ann['general_service_stiffness_exemption'] is False
    assert 'objetivo de deslocamento no ponto explicitamente escolhido' in row['reason']
    assert built['ELS']==r['ELS'] and built['input_snapshot']==r['input_snapshot']


@pytest.mark.parametrize('change',['positive_root_limit','root_origin','positive_effective_limit','effective_origin',
    'no_effective_snapshot','no_effective_limit_field','opt_in','computed_old','failed_old','missing_extra',
    'new_MLE_inconclusive','new_field_pending','batch'])
def test_any_real_or_ambiguous_legacy_criterion_and_optin_is_preserved(monkeypatch,change):
    r,base=default_pending_source()
    if change=='positive_root_limit':r['input_data']['ELS_limit_mm']=15.
    elif change=='root_origin':r['input_data']['ELS_origin']='Selected L/180'
    elif change=='positive_effective_limit':r['input_snapshot']['ELS_limit_mm']['value']=15.
    elif change=='effective_origin':r['input_snapshot']['ELS_limit_mm']['origin']='Injected L/180'
    elif change=='no_effective_snapshot':r.pop('input_snapshot')
    elif change=='no_effective_limit_field':r['input_snapshot'].pop('ELS_limit_mm')
    elif change=='opt_in':r['input_data']['deflection_model']='local_uniaxial_component_v1'
    elif change=='computed_old':r['ELS']={'status':'computed_bending_component','index':.4,'criterion_status':'meets'};base[2]=old()[2]
    elif change=='failed_old':r['ELS']={'status':'computed_bending_component','index':1.4,'criterion_status':'fails'};base[2]=check('ELS:DIRECT_ELS:deflection',limit_state='ELS',source='old criterion',index=1.4,qualified=True)
    elif change=='missing_extra':r['ELS']['missing'].append('SLS actions with origin')
    elif change=='new_MLE_inconclusive':
        cmp=r[c.FIELD]['records'][0]['comparison'];cmp.update(index_lower=None,index_upper=None,criterion_status='gross_MLE_sufficient_condition_inconclusive');cmp['gross_screen']['gross_local_normal_sufficient']=False
    elif change=='new_field_pending':r[c.FIELD]['records'][0].update(status='pending',comparison=None,reason='Missing dense source')
    elif change=='batch':
        r['schema']='tercas_batch_results_v1';r['load_bundle']={'combinations':[{'id':'DIRECT_ELS','limit_state':'ELS'}]};r['cases']=[{'combination':{'id':'DIRECT_ELS','limit_state':'ELS'}}]
    expected=copy.deepcopy(base[2]);built=build(trusted(monkeypatch,r),base);p.validate_saved(built)
    assert built['global_verification']['checks'][2]==expected


def test_saved_default_replacement_is_bound_to_effective_case_input(monkeypatch):
    r,base=default_pending_source();built=build(trusted(monkeypatch,r),base)
    built['input_snapshot']['ELS_limit_mm'].update(value=15.,origin='Real case criterion')
    with pytest.raises(ValueError):p.validate_saved(built)
