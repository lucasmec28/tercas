"""Reproduce direct-load PP/top examples without changing UI or snapshots."""
import json
from pathlib import Path

from tercas import direct_self_weight as pp, direct_roof_separated as split
from tercas import ue_family_reference as family, ue_reference as single
from tercas import roof_top_load as roof, direct_torsion
from tercas.torsion_vlasov.vlasov import solve_member
from tercas.torsion_vlasov.section import from_frozen_profile
from tercas.isolated_en_stress import check_member

ROOT=Path(__file__).resolve().parents[1]
rows=[]
for t in (1.2,1.5,2.,2.25,2.65,3.,3.35):
    profile=json.loads((ROOT/f'tercas/data/torsion_profiles/ue100x50x17_t{t:.2f}.json').read_text())
    section=from_frozen_profile(profile)
    data=pp.activate(single.load_reference(angle=0.) if t==1.2 else family.load_reference(t,4000.,0.))
    data.update(load_mode='direct',q_uls=.1,q_sls=.06,P_uls=20.,P_sls=12.,
        x_uls=1700.,x_sls=1700.,roof_top_load=roof.choice('web_midplane'))
    combo=split.combinations(data)[0];geometry=roof.geometry(data)
    actions=direct_torsion.actions(combo,geometry)
    demand=solve_member(section=section,length_mm=data['L_mm'],E_MPa=data['properties']['E_MPa'],
        G_MPa=data['properties']['G_MPa'],actions=actions,
        supports={k:dict(twist='fixed',warping='free_assumed',origin='Declared R01 ideal forks') for k in ('left','right')},
        combination_id=combo['id'],limit_state=combo['limit_state'],member_id='PURLIN',
        action_accounting_origin='Same direct adapter: external actions plus PP once',elements_per_interval=32)
    result=check_member(demand,profile,intact_section_model_declared=True,model_origin='QA intact nominal Ue model')
    rows.append(dict(thickness_mm=t,length_mm=data['L_mm'],direct_combination=combo,
        load_roles=[a['name'] for a in actions],stress_checks=result))
output=dict(synthetic_examples=True,not_physical_design_approval=True,examples=rows)
path=ROOT/'docs/ISOLATED_EN_STRESS_QA_20261106.json'
path.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
for row in rows:
    print(row['thickness_mm'],row['length_mm'],{k:round(v['index_upper_bound'],6) for k,v in row['stress_checks']['criteria'].items()})
