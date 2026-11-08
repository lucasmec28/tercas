"""Creation respects each own source contract; no FLT certificate transplant."""
import copy
import pytest
from tercas import ue_reference as ue, ue_family_reference as family
from tercas import homogeneous_reference as homogeneous, pierin_ue_registry as registry
from tercas import flt_height_effective as flt
from tercas.application import defaults, calculate
from tercas.new_study_policy import for_new_study, initialize_session
from tercas.deflection_scope import FIELD, MODE


CASES = [('ue', None)] + [('family', t) for t in family.THICKNESSES]


def own(kind, thickness):
    module = ue if kind == 'ue' else family
    data = module.load_reference() if kind == 'ue' else module.load_reference(thickness)
    data.update(load_mode='direct', q_uls=.3, q_sls=.1,
                q_parallel_uls=.025, q_parallel_sls=.05,
                P_parallel_uls=0., P_parallel_sls=0.)
    return module, data


@pytest.mark.parametrize('kind,thickness', CASES)
def test_seven_own_creations_remain_calculable(kind, thickness):
    module, seed = own(kind, thickness)
    before = copy.deepcopy(seed)
    created = for_new_study(seed)
    assert seed == before and flt.COMBINED_FIELD not in created
    assert created[FIELD] == MODE
    assert module.assess(created)['calculable']
    result = calculate(created)
    assert result['input_data'] == created
    assert not result.get('whole_member_approved', False)
    assert for_new_study(created) == created


@pytest.mark.parametrize('kind,thickness', CASES)
@pytest.mark.parametrize('marker', [flt.COMBINED_METHOD, flt.LEGACY_COMBINED_METHOD, 'unknown', None])
def test_existing_incompatible_marker_is_not_erased_or_requalified(kind, thickness, marker):
    module, data = own(kind, thickness)
    data[flt.COMBINED_FIELD] = marker
    before = copy.deepcopy(data)
    created = for_new_study(data)
    assert data == before and created[flt.COMBINED_FIELD] == marker
    assert not module.assess(created)['eligible']
    assert any(flt.COMBINED_FIELD in reason for reason in module.assess(created)['reasons'])
    with pytest.raises(ValueError):
        calculate(created)


@pytest.mark.parametrize('kind,thickness', CASES)
def test_existing_unmarked_inputs_and_history_are_not_migrated(kind, thickness):
    _, data = own(kind, thickness)
    state = {'last_input': data, 'result': {'historical': 'unchanged'}}
    before = copy.deepcopy(state)
    assert not initialize_session(state, lambda: pytest.fail('Not creation'))
    assert state == before | {'base': data}
    assert FIELD not in state['base'] and flt.COMBINED_FIELD not in state['base']


@pytest.mark.parametrize('ref', homogeneous.REFERENCES)
def test_plain_U_creation_retains_its_own_frozen_scalar_route(ref):
    data = for_new_study(homogeneous.load_reference(ref))
    assert FIELD not in data and flt.COMBINED_FIELD not in data
    assert homogeneous.assess(data)['calculable']
    assert homogeneous.calculate_reference(data)['homogeneous_reference_evidence']


@pytest.mark.parametrize('index', registry.new_study_indices())
def test_catalogue_creation_retains_its_own_flt_declaration(index):
    seed = defaults(index)
    before = copy.deepcopy(seed)
    created = for_new_study(seed)
    assert seed == before
    assert created[flt.COMBINED_FIELD] == flt.COMBINED_METHOD
    assert created[FIELD] == MODE
