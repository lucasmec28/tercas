"""Synthetic direct workflow coverage, not profile/member approval."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from en_ue_test_helpers import inputs,run
from tercas.pierin_ue_registry import new_study_indices
from tercas import ue_catalog_reference as own,isolated_en_ue_family_application as a
rows=[]
for index in new_study_indices():
    d=inputs(index);d['properties'].update(fy_MPa=300.,fu_MPa=450.)
    d=own.activate(d);d=a.activate(d,model_origin='Synthetic complete family workflow matrix')
    r=run(d);ev=a.preserved(r)
    rows.append(dict(index=index,fy_MPa=300.,flow='direct original synthetic q=0.03, first-order roof load',
        computed=ev['computed_cases'],pending=ev['pending_demand_cases'],
        shear_computed=ev['shear_computed_cases'],stress_computed=ev['stress_computed_cases'],
        mv_computed=ev['mv_computed_cases'],partial=ev['partial_cases'],
        records=[dict(status=v['status'],reason=v['reason'],mv_status=(v['check'] or {}).get('mv',{}).get('status')) for v in ev['records']],
        global_approved=r['global_verification']['whole_member_approved']))
    print(index,rows[-1]['computed'],flush=True)
out=dict(profile_count=len(rows),computed_profiles=sum(r['computed']>0 for r in rows),
    pending_profiles=sum(r['pending']>0 for r in rows),
    shear_profiles=sum(r['shear_computed']>0 for r in rows),stress_profiles=sum(r['stress_computed']>0 for r in rows),
    mv_profiles=sum(r['mv_computed']>0 for r in rows),partial_profiles=sum(r['partial']>0 for r in rows),
    global_approved=any(r['global_approved'] for r in rows),records=rows)
Path('docs/EN_UE_FAMILY_APP_COVERAGE_20261106.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print({k:v for k,v in out.items() if k!='records'})
