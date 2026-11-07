import copy
import math
import pytest
from tercas.serviceability_plan import prepare, table_a1_limit, point_displacement, CRITERIA


def fixture():
    return dict(schema='tercas_batch_results_v1',input_data={'L_mm':3000.,'load_mode':'area'},
        load_bundle={'case_vectors_N_mm':{'V_Cima':{'normal':-.2,'parallel':.05}},
        'combinations':[
            {'id':'down','limit_state':'ELS','type':'ELS rara','coefficients':{'PP':1.,'CP':1.,'SC':1.}},
            {'id':'net_up','limit_state':'ELS','type':'ELS rara','coefficients':{'PP':1.,'CP':1.,'V_Cima':1.}},
            {'id':'freq','limit_state':'ELS','type':'ELS frequente','coefficients':{'PP':1.,'CP':1.,'SC':.4}},
        ]})


def state(s, **kw):
    d=dict(combination_id='SLS1',member_id='span',section_id='same_section',analysis_id='one_model',
           stiffness_id='one_stiffness',coordinate_system='xy_right_handed',reference_line_id='SC',
           limit_state='ELS',station_mm=s,ux_mm=0.,uy_mm=0.,phi_rad=0.)
    d.update(kw);return d


def test_verified_a1_limits_have_distinct_action_rules():
    a,b=[table_a1_limit(3600.,c) for c in CRITERIA]
    assert a['limit_mm']==20 and b['limit_mm']==30
    assert 'raras' in a['action_rule'] and 'sem PP/CP' in b['action_rule']
    assert a['source_pdf_pages']==[75,76,77] and a['service_approved'] is False


@pytest.mark.parametrize('L',[None,True,0,-1,float('inf'),float('nan')])
def test_invalid_length_not_default_limit(L):
    with pytest.raises(ValueError):table_a1_limit(L,CRITERIA[0])


def test_prepare_separate_uplift_without_cancelling_with_permanents():
    r=fixture();before=copy.deepcopy(r);p=prepare(r)
    assert r==before and p['source_matrix_changed'] is False
    assert p['same_direction_rare_case_ids']==['down'] and p['opposite_only_case_ids']==[]
    c=p['prepared_cases'][0]
    assert c['coefficients']=={'V_Cima':1.} and c['q_vector']=={'normal':-.2,'parallel':.05}
    assert c['P_vector']=={'normal':0.,'parallel':0.}
    assert c['displacement_mm'] is None and c['index'] is None
    assert not c['self_weight_added'] and not c['permanent_loads_included']


def test_exact_zero_is_distinct_from_missing_characteristic_wind():
    r=fixture();r['load_bundle']['case_vectors_N_mm']['V_Cima']={'normal':0.,'parallel':0.}
    p=prepare(r);assert p['opposite_action_status']=='explicitly_zero_characteristic_wind'
    assert not p['prepared_cases'] and not p['combined_ELS_approved']
    del r['load_bundle']['case_vectors_N_mm']['V_Cima']
    assert prepare(r)['opposite_action_status']=='missing_characteristic_source'


def test_filtered_rare_cases_remain_missing():
    r=fixture();r['load_bundle']['combinations']=r['load_bundle']['combinations'][2:]
    assert not prepare(r)['same_direction_rare_case_ids']
    assert any('rara candidata' in s for s in prepare(r)['missing'])


def test_direct_combined_loads_not_decomposed():
    r=fixture();r['schema']='NBR14762_one_span_v1';r['input_data']['load_mode']='direct'
    p=prepare(r);assert not p['prepared_cases']
    assert any('diretas combinadas' in s for s in p['missing'])


def test_atomic_linear_point_displacement_sign_and_chord():
    # uP=(2-50*.02,-3+20*.02)=(1,-2.6); the end chord is (.2,.6).
    r=point_displacement(state(5,ux_mm=2.,uy_mm=-3.,phi_rad=.02),
        offset_xy_mm=[20.,50.],projection_xy=[0.,-1.],
        left=state(0,ux_mm=.2,uy_mm=.6),right=state(10,ux_mm=.2,uy_mm=.6),limit_mm=2.)
    assert r['point_displacement_xy_mm']==[1.,-2.6]
    assert r['relative_displacement_xy_mm']==[.8,-3.2]
    assert r['projected_relative_mm']==3.2 and r['diagnostic_ratio']==1.6
    for key in ('physical_rotation_qualified','combined_ELS_approved','effective_stiffness_qualified',
                'first_order_applicability_qualified','continuous_envelope_qualified','whole_member_approved'):
        assert r[key] is False


def test_torsional_motion_of_same_point_at_moving_ends_is_subtracted():
    r=point_displacement(state(5,phi_rad=.1),offset_xy_mm=[10.,20.],projection_xy=[1.,0.],
        left=state(0,phi_rad=.1),right=state(10,phi_rad=.1))
    assert r['relative_displacement_xy_mm']==[0.,0.] and r['diagnostic_ratio'] is None


@pytest.mark.parametrize('key',['combination_id','member_id','section_id','analysis_id',
                                  'stiffness_id','coordinate_system','reference_line_id'])
def test_mixed_fields_rejected(key):
    right=state(10);right[key]='other'
    with pytest.raises(ValueError):
        point_displacement(state(5),offset_xy_mm=[0,0],projection_xy=[1,0],left=state(0),right=right)


@pytest.mark.parametrize('change',[{'phi_rad':None},{'ux_mm':float('nan')},{'limit_state':'ELU'},
                                     {'station_mm':20},{'uy_mm':True}])
def test_invalid_unknown_or_outside_state_not_zero(change):
    with pytest.raises(ValueError):
        point_displacement(state(5,**change) if 'station_mm' not in change else state(20),
            offset_xy_mm=[0,0],projection_xy=[1,0],left=state(0),right=state(10))


def test_large_phi_has_no_normative_failure_or_nonlinear_rotation_conversion():
    r=point_displacement(state(5,phi_rad=3.),offset_xy_mm=[10,20],projection_xy=[1,0],
                         left=state(0),right=state(10),limit_mm=1.)
    assert r['point_displacement_xy_mm']==[-60.,30.] and r['diagnostic_ratio']==60.
    assert not r['physical_rotation_qualified'] and 'status' not in r and not r['combined_ELS_approved']


def test_offset_zero_and_arbitrary_projection_are_not_resultant_maxima():
    r=point_displacement(state(5,ux_mm=3.,uy_mm=4.,phi_rad=10.),offset_xy_mm=[0.,0.],
                         projection_xy=[.6,.8],left=state(0),right=state(10))
    assert r['projected_relative_mm']==5. and not r['continuous_envelope_qualified']
    with pytest.raises(ValueError):
        point_displacement(state(5),offset_xy_mm=[0,0],projection_xy=[1,1],left=state(0),right=state(10))


def test_missing_central_binding_has_contract_error_not_keyerror():
    middle=state(5);del middle['stiffness_id']
    with pytest.raises(ValueError):
        point_displacement(middle,offset_xy_mm=[0,0],projection_xy=[1,0],left=state(0),right=state(10))
