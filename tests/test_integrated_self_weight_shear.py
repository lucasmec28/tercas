"""Cross-component regression: the same physical loads give the same web checks."""
import copy
import json
from pathlib import Path

from tercas import direct_self_weight as pp, three_girt_shear as shear
from tercas.three_girt_warping import application as warping
from tercas.three_girt_axial import application as nbr
from tercas.three_girt_assessment.application import assess
from tercas.ue_family_reference import apply_geometry


def test_automatic_PP_and_equivalent_legacy_network_have_identical_web_checks():
    source = json.loads((Path(__file__).parent / 'data/three_girt_normal_QA_input.json').read_text())
    data = pp.activate(apply_geometry(source['input_data'], 3.35, 4000.))
    data.update(load_mode='direct', q_uls=.4, q_sls=.3,
                q_parallel_uls=.025, q_parallel_sls=-.01,
                P_uls=0., P_sls=0., P_parallel_uls=0., P_parallel_sls=0.)
    before = copy.deepcopy(data)
    configuration = copy.deepcopy(source['configuration']['three_girt'])
    configuration.update(direct_pp_uls_N_mm=999., direct_pp_sls_N_mm=999.,
                         direct_brace_factor_uls=1.25, direct_brace_factor_sls=1.)
    current = warping.attach_g81(warping.calculate(
        data, warping.current_configuration(data, configuration)))

    # Express exactly the same physical problem through the preserved old
    # contract: totals include PP, with the already-combined PP identified.
    old_data = pp.calculation_inputs(data)
    old_configuration = copy.deepcopy(configuration)
    for suffix, record in pp.evidence(data)['states'].items():
        old_configuration['direct_pp_' + suffix + '_N_mm'] = record['profile_PP_q_N_mm']['parallel']
    previous = warping.attach_g81(warping.calculate(
        old_data, warping.current_configuration(old_data, old_configuration)))
    for now, old in zip(current['cases'], previous['cases']):
        assert now['loads'] == old['loads']
        assert now['combined_girt_PP_N_mm'] == old['combined_girt_PP_N_mm']
        assert [b['states'] for b in now['model']['beams']] == [b['states'] for b in old['model']['beams']]

    now_result = nbr.attach(current, nbr.reference_configuration(current))
    old_result = nbr.attach(previous, nbr.reference_configuration(previous))
    now_web = shear.saved(nbr.saved_component(now_result))
    old_web = shear.saved(nbr.saved_component(old_result))
    assert now_web is not None and old_web is not None
    assert now_web['rows'] == old_web['rows']
    assert now_web['NBR_capacity'] == old_web['NBR_capacity']
    inventory = assess(now_result)
    checks = {r['id']: r for r in inventory['checks']}
    assert checks['member_stability_and_analysis']['status'] == 'pending'
    assert checks['transverse_shear_resistance']['status'] == 'pending'
    assert 'foi avaliada' in checks['transverse_shear_resistance']['reason']
    assert inventory['whole_member_approved'] is False
    assert data == before
