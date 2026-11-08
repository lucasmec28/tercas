"""Policy adoption belongs to a new UI solve, never an opening or saved reader."""
import copy
import json

import pytest

from tercas import load_application_policy as loads, support_scope as supports
from tercas.current_calculation_inputs import prepare, preserve_policy_choices, begin_calculation
from tercas.pierin_ue_registry_ui import HISTORY, DURABLE_KEYS


def data():
    # No mechanics are claimed by this synthetic boundary-only payload.
    return dict(ue_catalog_reference={},project='saved study',
        roof_top_load={'enabled':True,'load_line':'web_midplane'},
        torsion_model={'load_lines':{'CP':{'xy_from_CG_mm':[12.,34.]}}},
        three_girt_model={'enabled':False,'load_y_from_CG_mm':25.,'load_line_declared':False})


def test_prepared_controls_preserve_import_and_legacy_fields():
    original=data();before=copy.deepcopy(original)
    view=prepare(original)
    assert loads.active(view) and supports.enabled(view)
    assert original==before
    assert preserve_policy_choices(view,original)==original
    for key in ('roof_top_load','torsion_model','three_girt_model'):
        assert view[key]==original[key] and view[key] is not original[key]
    view['project']='edited current project'
    restored=preserve_policy_choices(view,original)
    assert restored==dict(original,project='edited current project')


def test_click_archives_prior_result_and_commits_idempotent_deep_copies():
    original=data()
    historical={'input_data':copy.deepcopy(original),'legacy_numeric_values':[4.7,9.2]}
    state=dict(base=copy.deepcopy(original),last_input=copy.deepcopy(original),result=historical,
        catalog_scan_state={'rows':[{'historical':True}]},three_girt_warping_result={'old':True},
        revision=3,widget_draft='untouched')
    before=copy.deepcopy(state)
    current=begin_calculation(state,original)
    assert loads.active(current) and supports.enabled(current)
    assert state['base']==state['last_input']==current
    assert state['base'] is not state['last_input'] and state['last_input'] is not current
    assert state['result']==historical==before['result']
    assert state[HISTORY]==[{k:v for k,v in before.items() if k in DURABLE_KEYS}]
    assert state['widget_draft']=='untouched' and state['revision']==3
    current['project']='scratch only'
    assert state['last_input']['project']=='saved study'
    snapshot=copy.deepcopy(state[HISTORY])
    begin_calculation(state,state['last_input'])
    assert state[HISTORY]==snapshot
    assert json.loads(json.dumps(state[HISTORY][0]['result']))==historical


@pytest.mark.parametrize('field',[loads.FIELD,supports.FIELD])
def test_unknown_policies_do_not_mutate_any_state(field):
    original=data();original[field]='future unrecognized model'
    state={'base':copy.deepcopy(original),'last_input':copy.deepcopy(original),'result':{'saved':True}}
    before=copy.deepcopy(state)
    with pytest.raises(ValueError):begin_calculation(state,original)
    assert state==before
