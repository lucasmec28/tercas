"""Source reporting changes invalidate only the active own-Ue result cache."""
import copy
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tercas import ue_reference as u


def test_r1_result_with_same_input_fingerprint_is_not_reused():
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    data=u.load_reference();data.update(load_mode='direct',q_uls=.2,q_sls=.1)
    result=u.calculate_reference(data)
    result['ue_reference_evidence']['reporting_version']='ue100_components_pending_els_20261103_r1'
    app.session_state['base']=copy.deepcopy(data)
    app.session_state['last_input']=copy.deepcopy(data)
    app.session_state['revision']=app.session_state['revision']+1
    app.session_state['result']=result
    app.run(timeout=30)
    assert not app.exception
    assert 'result' not in app.session_state
    assert app.session_state.last_input==data
    assert u.assess(app.session_state.last_input)['calculable']
