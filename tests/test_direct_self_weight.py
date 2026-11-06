"""External direct actions plus profile PP; legacy snapshots never migrate."""
import copy,json,math
from io import BytesIO
import pytest
from docx import Document
from tercas import direct_self_weight as pp
from tercas.application import example,calculate,build_spec,rows,fingerprint
from tercas.batch import area_bundle,case_inputs,calculate_batch
from tercas.new_study_policy import for_new_study,initialize_session
from tercas import ue_reference as single,ue_family_reference as family
from tercas.roof_top_load import choice,preserved,combination_inventory
from tercas.study_completion import complete_result
from tercas.catalog_scan import inputs_for_section

@pytest.mark.parametrize('angle',[-30.,0.,30.])
@pytest.mark.parametrize('q',[-.7,0.,.7])
def test_PP_factors_and_signed_projection_do_not_rotate_external_actions(angle,q):
    d=pp.activate(example());d.update(q_uls=q,q_sls=q,q_parallel_uls=.02,q_parallel_sls=-.04,
        inclination=dict(value=angle,unit='degrees'))
    frozen=copy.deepcopy(d);e=pp.evidence(d);effective=pp.calculation_inputs(d)
    w=d['properties']['mass_kg_m']*9.80665/1000
    for suffix,factor in pp.FACTORS.items():
        assert effective['q_'+suffix]==pytest.approx(q+factor*w*math.cos(math.radians(angle)))
        assert effective['q_parallel_'+suffix]==pytest.approx(d['q_parallel_'+suffix]+factor*w*math.sin(math.radians(angle)))
        assert effective['P_'+suffix]==d['P_'+suffix]
        assert e['states'][suffix]['external_q_N_mm']['normal']==q
    assert d==frozen and pp.calculation_inputs(effective)==effective
    result=calculate(d)
    assert result['input_data']==d and result['input_fingerprint']==fingerprint(d)
    assert result['input_snapshot']['ULS']['q_Nmm']==effective['q_uls']
    assert result['inclination_evidence']['ELS']['q_vector']==e['states']['sls']['total_q_N_mm']


def test_legacy_and_area_inputs_unchanged():
    old=example();frozen=copy.deepcopy(old);r=calculate(old)
    assert pp.evidence(old) is None and pp.calculation_inputs(old)==old
    assert 'direct_self_weight_evidence' not in r and old==frozen
    assert r['input_snapshot']['ULS']['q_Nmm']==old['q_uls']
    d=pp.activate(old);d['load_mode']='area'
    b=area_bundle(d);c=case_inputs(d,b['combinations'][0])
    assert pp.FIELD not in c
    assert build_spec(c)['ULS']['q_Nmm']==b['combinations'][0]['q_N_mm']
    d0=copy.deepcopy(d);d0.pop(pp.FIELD)
    assert area_bundle(d)==area_bundle(d0)
    a,z=calculate_batch(d),calculate_batch(d0)
    assert a['cases']==z['cases']


def test_mass_changes_recompute_PP_and_import_preserves_legacy():
    d=pp.activate(example());d.update(q_uls=.2,q_sls=.1)
    other=inputs_for_section(d,(d['catalog_index']+1)%209)
    assert other['q_uls']==d['q_uls'] and other[pp.FIELD]==pp.MODE
    assert pp.evidence(other)['profile_characteristic_weight_N_mm']==other['properties']['mass_kg_m']*9.80665/1000
    raw=json.dumps(d);assert json.loads(raw)==d
    old=example();state={'last_input':old}
    assert not initialize_session(state,lambda:pytest.fail('no fresh factory'))
    assert state['base']==old and pp.FIELD not in state['base']
    assert pp.FIELD in for_new_study(old) and pp.FIELD not in old


@pytest.mark.parametrize('bad',[None,True,1,'unknown',{},[]])
def test_unknown_contract_is_rejected_without_mutating(bad):
    d=example();d[pp.FIELD]=bad;before=copy.deepcopy(d)
    with pytest.raises(ValueError):calculate(d)
    assert d==before


@pytest.mark.parametrize('mass',[None,0.,-1.,float('nan'),float('inf'),True])
def test_missing_or_invalid_mass_cannot_mean_zero(mass):
    d=pp.activate(example());d['properties']['mass_kg_m']=mass
    with pytest.raises(ValueError):calculate(d)


@pytest.mark.parametrize('factory',[single.load_reference,lambda:family.load_reference(1.5)])
def test_reference_contract_survives_span_changes_and_nonzero_PP_parallel(factory):
    d=pp.activate(factory());d.update(load_mode='direct',q_sls=.1,q_parallel_sls=0.)
    d['inclination']['value']=5.
    result=calculate(d)
    assert result['inclination_evidence']['ELS']['parallel_demand']
    assert result['ELS'].get('index') is None
    assert result['input_data']==d


def test_direct_separated_Me_keeps_PP_at_CG_and_actual_external_top_torque():
    d=pp.activate(single.load_reference());d.update(load_mode='direct',q_uls=.12,q_sls=.08,roof_top_load=choice())
    r=complete_result(calculate(d));ev=preserved(r)
    assert ev['schema']=='roof_top_load_evidence_v3' and ev['self_weight_added']
    assert ev['computed_cases']==2
    for combo,record in zip(combination_inventory(r),ev['records']):
        acts={x['name']:x for x in record['actions']}
        assert acts['PP']['height_above_SC_mm']==0.
        assert acts['EXTERNAL']['height_above_SC_mm']==pytest.approx(50.)
        assert acts['PP']['q_down_N_mm']==combo['profile_PP_q_vector']['normal']
        assert acts['EXTERNAL']['q_down_N_mm']==combo['external_q_vector']['normal']
        assert all(t['value'] is not None for t in record['primary_torque_by_action'])
        assert record['maximum_reference_moment_Nmm']==pytest.approx(combo['q_N_mm']*d['L_mm']**2/8)
    assert not r['whole_member_approved']
    altered=copy.deepcopy(r);altered['input_data']['q_uls']+=.1
    with pytest.raises(ValueError):preserved(altered)
    from tercas.report import word
    doc=Document(BytesIO(word(r)))
    assert any('Peso próprio no modo direto' in x.text for x in doc.paragraphs)


def test_cancelled_parallel_components_do_not_silently_enable_uniaxial_height():
    d=pp.activate(single.load_reference());d.update(load_mode='direct',roof_top_load=choice())
    d['inclination']['value']=5.
    e=pp.evidence(d)
    for suffix in pp.FACTORS:d['q_parallel_'+suffix]=-e['states'][suffix]['profile_PP_q_N_mm']['parallel']
    r=complete_result(calculate(d));ev=preserved(r)
    assert ev['computed_cases']==0
    assert all(x['status']=='pending_biaxial_model' for x in ev['records'])


def test_wall_PP_is_vertical_without_spurious_horizontal_roundoff():
    d=pp.activate(example());d.update(member_application='wall_girt',q_uls=.2,q_sls=.1,q_parallel_uls=0.,q_parallel_sls=0.)
    e=pp.evidence(d);r=calculate(d)
    assert e['states']['uls']['profile_PP_q_N_mm']['normal']==0.
    assert r['input_snapshot']['ULS']['q_Nmm']==.2
    assert r['inclination_evidence']['ELS']['q_vector']['parallel']==pytest.approx(d['properties']['mass_kg_m']*9.80665/1000)
    assert r['elastic_vertical']['status']!='not_applicable'


def test_three_girts_external_actions_half_but_profile_PP_full():
    from tests.test_three_girt_system import ready
    from tercas.three_girt_application import configuration,load_cases,readiness
    d=pp.activate(ready());c=configuration(d)
    c['direct_pp_uls_N_mm']=None;c['direct_pp_sls_N_mm']=None
    assert not readiness(d,c)
    cases,_=load_cases(d,c)
    e=pp.evidence(d)
    for suffix,case in zip(('uls','sls'),cases):
        weight=e['states'][suffix]['profile_PP_q_N_mm']['parallel']
        assert case['combined_girt_PP_N_mm']==weight
        for factor,load in zip((.5,1.,.5),case['loads']):
            assert load['q_y_N_mm']==pytest.approx(-factor*d['q_parallel_'+suffix]-weight)
            assert load['components'][1]['q_y_N_mm']==-weight
            assert load['distributed_torque_CG_N']==pytest.approx(c['load_y_from_CG_mm']*(-factor*d['q_'+suffix])-c['load_z_from_CG_mm']*(-factor*d['q_parallel_'+suffix]))


def test_current_7DOF_profile_PP_is_vertical_full_and_saved_binding_validates():
    from pathlib import Path
    from tercas.three_girt_warping import application as w
    from tercas.three_girt_assessment.application import _load_binding
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    d=pp.activate(src['input_data']);d.update(load_mode='direct',q_uls=0.,q_sls=0.,q_parallel_uls=0.,q_parallel_sls=0.,
        P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.)
    cfg=w.current_configuration(d,src['configuration']['three_girt']);cfg['three_girt']['brace_self_weight']=False
    cfg['three_girt'].update(direct_pp_uls_N_mm=999.,direct_pp_sls_N_mm=999.)
    r=w.calculate(d,cfg)
    assert r['status']=='conditional_elastic_vlasov_demand'
    for case in r['cases']:
        _load_binding(r,case)
        for load in case['loads']:
            assert load['q_z_N_mm']==0.
            assert load['q_y_N_mm']==-case['combined_girt_PP_N_mm']
            assert load['distributed_torque_CG_N']==0.
    bad=copy.deepcopy(d);bad['member_application']='purlin'
    with pytest.raises(ValueError,match='wall_girt'):w.calculate(bad,cfg)
