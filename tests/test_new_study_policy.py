"""No timed fallback default; creation and all existing choices are preserved."""
import copy
import pytest
from tercas.direct_self_weight import activate as activate_PP
from tercas.new_study_policy import for_new_study, initialize_session
from tercas.deflection_scope import FIELD, MODE, activate
from tercas.application import defaults, example
from tercas import ue_reference as ue, ue_family_reference as family, homogeneous_reference as homogeneous


def test_explicit_new_study_is_only_a_nonmutating_scope_choice():
    seed=ue.load_reference();before=copy.deepcopy(seed)
    result=for_new_study(seed)
    assert seed==before and result==activate_PP(seed) and FIELD not in result
    assert result is not seed and result['properties'] is not seed['properties']
    assert for_new_study(result)==result


@pytest.mark.parametrize('value',[None,True,False,'future',{},[]])
def test_unknown_seed_choice_is_never_converted(value):
    data=defaults();data[FIELD]=value;before=copy.deepcopy(data)
    with pytest.raises(ValueError):for_new_study(data)
    assert data==before


def test_backend_factories_and_source_contracts_stay_unmarked():
    for data in [defaults(),example(),ue.source(),ue.load_reference(),family.source(1.5),
                 family.load_reference(1.5),homogeneous.source('U100'),homogeneous.load_reference('U100')]:
        assert FIELD not in data


def test_only_empty_session_is_new():
    state={};seed=defaults()
    assert initialize_session(state,lambda:seed)
    assert state=={'base':activate_PP(seed)} and FIELD not in seed
    before=copy.deepcopy(state)
    assert not initialize_session(state,lambda:pytest.fail('Existing base must not call factory'))
    assert state==before


@pytest.mark.parametrize('key',['revision','result','catalog_scan_state','manual_result_history',
                               'manual_catalog_history','calculation_cache_epoch','unrecognized_saved_key'])
def test_any_existing_key_prevents_default_even_when_base_is_missing(key):
    state={key:{'legacy':'unchanged'}};before=copy.deepcopy(state);seed=defaults()
    assert not initialize_session(state,lambda:copy.deepcopy(seed))
    assert state==before|{'base':seed} and FIELD not in state['base']


@pytest.mark.parametrize('marker',[None,MODE,'future'])
def test_partial_session_retains_last_input_without_conversion(marker):
    data=ue.load_reference()
    if marker is not None:data[FIELD]=marker
    state={'last_input':data,'result':{'old':'do not requalify'},'revision':7}
    before=copy.deepcopy(state)
    assert not initialize_session(state,lambda:pytest.fail('Preserved input must not call factory'))
    assert state==before|{'base':data}
    assert state['base'] is not state['last_input']
    assert state['last_input']==before['last_input']


@pytest.mark.parametrize('marker',[None,MODE,'future'])
def test_existing_base_keeps_choice_and_historical_result(marker):
    data=ue.load_reference()
    if marker is not None:data[FIELD]=marker
    state={'base':data,'last_input':copy.deepcopy(data),'result':{'old':'unchanged'}}
    before=copy.deepcopy(state)
    assert not initialize_session(state,lambda:pytest.fail('No new factory'))
    assert state==before
