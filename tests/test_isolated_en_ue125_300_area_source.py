"""One authentic synthetic area support-limit case, not a truncated batch result."""
import copy
import json
import time
from tercas.batch import area_bundle
from tercas import en_ue125_300_authority as authority
from tercas import isolated_en_ue125_300 as core
from tercas import isolated_en_ue125_300_application as app
from tercas.roof_top_load import geometry
from tercas.torsion_vlasov.vlasov import solve_member
from tercas.torsion_vlasov.adapter import (actions_for_combination,load_lines_from_cg,
    support_limit_before_point,summarize_torsion_evidence)
from test_isolated_en_ue125_300_application import data


def test_single_original_area_support_limit_case():
    d=data();d.update(load_mode='area',selected_types=['ELU normal'])
    d['area_inputs'].update(permanent_kgf_m2=1.,live_kgf_m2=1.,wind_up_kgf_m2=1.,wind_down_kgf_m2=1.)
    bundle=area_bundle(d)
    combo=next(c for c in bundle['combinations'] if c.get('point_position')=='support_limit')
    section=core.section_reference();geo=geometry(d)
    lines=load_lines_from_cg(section,{role:dict(declared=True,
        xy_from_CG_mm=[geo['x_from_CG_mm'],geo['y_from_CG_mm']],origin='Synthetic declared roof load line')
        for role in ('CP','SC','V_Cima','V_Baixo','P')})
    actions,missing=actions_for_combination(bundle,combo,section,lines);assert not missing
    demand=solve_member(section=section,length_mm=d['L_mm'],E_MPa=200000.,G_MPa=77000.,
        actions=actions,supports={side:dict(twist='fixed',warping='free_assumed',origin='Synthetic fork') for side in ('left','right')},
        combination_id=combo['id'],limit_state='ELU',member_id='PURLIN',elements_per_interval=32,
        action_accounting_origin='Original synthetic area combination, one support-limit case')
    demand['support_limit_states']=[support_limit_before_point(demand)]
    demand['critical_states']=demand['support_limit_states']+demand['critical_states']
    demand['analysis_domain']['point_position_scope']='Prescribed a->0+ left-support limit, not an all-position envelope'
    # This inventory is used only to replay input load arithmetic, not emitted as results.
    inventory=dict(schema='tercas_batch_results_v1',input_data=d,load_bundle=bundle,
        cases=[dict(combination=copy.deepcopy(c)) for c in bundle['combinations']])
    app._validate_case(demand,app._load_inventory(inventory)[combo['id']],d)
    normal=authority.read();check=core.calculate(demand,normal_snapshot=normal,model_origin='Synthetic nominal intact QA')
    summary=summarize_torsion_evidence(dict(schema='purlin_torsion_batch_evidence_v1',records=[dict(analysis=demand)]))['records'][0]['analysis']
    start=time.perf_counter()
    assert core.validate_saved(check,summary,normal_snapshot=normal,source_sha256=app.digest(demand),model_origin='Synthetic nominal intact QA')
    print('EN300 synthetic one-area-case: check_bytes='+str(len(json.dumps(check).encode()))+'; reader_seconds='+str(round(time.perf_counter()-start,4)))
    assert check['pieces'][-1]['source_piece']['kind']=='support_limit'
    assert check['source_demand']['support_limit_states'][0]['position_limit'].startswith('a->0+')
    assert summary['support_limit_states'] and check['full_member_field_covered']
