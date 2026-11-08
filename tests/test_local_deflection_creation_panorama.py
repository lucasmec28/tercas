"""Local objective adoption never silently requalifies a historical snapshot."""
import copy
import json
import pytest
from tercas.application import calculate, rows
from tercas.deflection_scope import MODE, FIELD, activate
from tercas.new_study_policy import for_new_study
from tercas.global_verification import build_global_verification
from tercas.completion_requirements import attach, saved, _preparation_messages
from tercas.report import word
from test_uniaxial_deflection_scope import direct, text


def scope_row(result):
    return next(r for r in result['global_verification']['checks'] if r['id'].endswith(':combined_ELS_scope'))


def completed(data):
    result=calculate(data)
    result['global_verification']=build_global_verification(result)
    return attach(result)


def test_local_objective_excludes_optional_combined_check_without_approving_member():
    result=completed(activate(direct()))
    row=scope_row(result)
    assert row['status']=='not_applicable'
    assert row['id'] not in result['global_verification']['pending_ids']
    assert row['trace']['physical_ELS_approval'] is False
    assert result['global_verification']['current_adapter_can_approve'] is False
    record=saved(result)
    item=next(r for r in record['records'] if r['id']=='service_displacement')
    assert item['requirement_state']=='outside_requested_local_deflection_objective'
    assert any('Somente se for solicitada' in m for m in _preparation_messages(record))
    before=json.dumps(result,sort_keys=True,ensure_ascii=False)
    rendered=text(word(result))
    assert 'ELS combinado adicional — fora do objetivo solicitado' in rendered
    assert 'ELS combinado é uma análise adicional opcional' in rendered
    rows(result);saved(json.loads(before))
    assert json.dumps(result,sort_keys=True,ensure_ascii=False)==before


def test_historical_pending_inventory_and_word_remain_read_only():
    result=completed(direct())
    assert scope_row(result)['status']=='pending'
    before=json.dumps(result,sort_keys=True,ensure_ascii=False)
    rows(result);word(result);saved(result)
    assert json.dumps(result,sort_keys=True,ensure_ascii=False)==before
    assert 'fora do objetivo solicitado' not in text(word(result))


def test_input_token_alone_cannot_exclude_historical_combined_scope():
    result=calculate(direct());result['input_data'][FIELD]=MODE
    result['global_verification']=build_global_verification(result)
    assert scope_row(result)['status']=='pending'


def test_explicit_additional_combined_request_retains_its_own_coverage():
    result=calculate(activate(direct()))
    result['input_data']['isolated_combined_service']={'enabled':True}
    # Exercise inventory selection only: full service validation is covered by
    # its independent tests, and an input flag cannot manufacture a result.
    result['global_verification']=build_global_verification(result)
    assert scope_row(result)['status']=='pending'


@pytest.mark.parametrize('value',[None,[],True,{'enabled':'true'},{'enabled':1}])
def test_malformed_combined_choice_never_excludes_check(value):
    result=calculate(activate(direct()))
    result['input_data']['isolated_combined_service']=value
    result['global_verification']=build_global_verification(result)
    assert scope_row(result)['status']=='pending'


@pytest.mark.parametrize('target',['local','summary'])
@pytest.mark.parametrize('value',[None,[],{'schema':MODE}])
def test_incomplete_record_never_excludes_check(target,value):
    result=calculate(activate(direct()))
    if target=='local':result['ELS']['local_uniaxial_component']=copy.deepcopy(value)
    else:result['deflection_scope_evidence']=copy.deepcopy(value)
    result['global_verification']=build_global_verification(result)
    assert scope_row(result)['status']=='pending'


def test_minimal_schema_tokens_cannot_create_historical_scope_evidence():
    result=calculate(direct())
    result['ELS']['local_uniaxial_component']={'schema':MODE}
    result['deflection_scope_evidence']={'schema':MODE}
    result['global_verification']=build_global_verification(result)
    assert scope_row(result)['status']=='pending'


def test_batch_local_objective_keeps_every_service_combination():
    from tercas.batch import calculate_batch
    from tercas.ue_reference import load_reference
    result=calculate_batch(activate(load_reference(angle=5.)))
    summary=build_global_verification(result)
    rows=[r for r in summary['checks'] if r['id'].endswith(':combined_ELS_scope')]
    count=sum(c['combination']['limit_state']=='ELS' for c in result['cases'])
    assert len(rows)==count==18
    assert all(r['status']=='not_applicable' for r in rows)
    assert summary['whole_member_approved'] is False
