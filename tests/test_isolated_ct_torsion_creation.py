"""Fresh synthetic calculation boundaries, separate from solver-free reader QA."""
import copy

import pytest

from test_isolated_ct_torsion import source, torsion
from tercas import isolated_ct_torsion as ct
from tercas import isolated_en_panorama as panorama
from tercas.application import calculate
from tercas.batch import calculate_batch
from tercas.study_completion import complete_result


@pytest.mark.parametrize('name', ['roof','girt'])
@pytest.mark.parametrize('mode', ['direct','area'])
def test_actual_current_calculation_then_panorama(name,mode):
    data=source(name)['input_data'];data['load_mode']=mode
    if mode=='area':data['selected_types']=['ELU normal','ELS quase permanente']
    result=complete_result(calculate(data) if mode=='direct' else calculate_batch(data))
    before=copy.deepcopy(result)
    proof=ct.proof(result)
    assert proof['ELU_cases']>0
    assert torsion(result['global_verification'])['status']=='not_applicable'
    panorama.validate_saved(result,None)
    assert result==before
    if mode=='area' and name=='roof':
        assert any(row['analysis']['support_limit_states'] for row in result['torsion_evidence']['records'])
        bad=copy.deepcopy(result)
        next(row['analysis'] for row in bad['torsion_evidence']['records']
            if row['analysis']['support_limit_states'])['support_limit_states']=[]
        assert ct.record(bad) is None
        with pytest.raises(ValueError):panorama.validate_saved(bad,None)
    if mode=='area':
        for location in ('load_bundle','cases','torsion_evidence'):
            bad=copy.deepcopy(result)
            if location=='load_bundle':bad[location]['combinations'].pop()
            elif location=='cases':bad[location].pop()
            else:bad[location]['records'].pop()
            assert ct.record(bad) is None


@pytest.mark.parametrize('thickness', [1.2,1.5,3.35])
def test_current_frozen_source_direct_CT(thickness):
    from tercas import ue_reference,ue_family_reference,direct_self_weight,load_application_policy
    data=ue_reference.load_reference() if thickness==1.2 else ue_family_reference.load_reference(thickness)
    data=load_application_policy.adopt(direct_self_weight.activate(data))
    data.update(load_mode='direct',q_uls=.2,q_sls=.1,P_uls=150.,P_sls=100.,x_uls=1500.,x_sls=1500.,
        q_parallel_uls=.02,q_parallel_sls=.01,P_parallel_uls=15.,P_parallel_sls=10.)
    result=complete_result(calculate(data))
    assert ct.proof(result)['ELU_cases']==1
    assert torsion(result['global_verification'])['status']=='not_applicable'
    panorama.validate_saved(result,None)
