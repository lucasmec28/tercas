"""Synthetic flows only. No private project inputs or approval."""
import json,time
from en_ue_test_helpers import inputs,run
from tercas import ue_catalog_reference as own
from tercas import isolated_en_ue_family_application as en
rows=[]
for i in (19,26,51,53,79,82):
 d=inputs(i,angle=5.71);d['properties'].update(fy_MPa=300.,fu_MPa=450.);d=own.activate(d)
 d=en.activate(d,model_origin='Synthetic R11 release family check')
 t=time.perf_counter();r=run(d);ev=en.preserved(r)
 row=dict(index=i,elapsed_seconds=time.perf_counter()-t,ELU_cases=ev['ELU_cases'],
  stress=ev['stress_computed_cases'],shear=ev['shear_computed_cases'],mv=ev['mv_computed_cases'],
  partial=ev['partial_cases'],reasons=[x.get('reason') for x in ev['records']],whole_member_approved=r['whole_member_approved'])
 rows.append(row);print(json.dumps(row),flush=True)
 assert ev['ELU_cases']==ev['stress_computed_cases']==ev['shear_computed_cases']==1
 assert not r['whole_member_approved']
json.dump(rows,open('qa/r11_integration/en_representative_results.json','w'),indent=2)
