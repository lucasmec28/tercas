"""Synthetic scalar coverage/timing, before R10 versus current method."""
import gzip
import json
import platform
from collections import Counter
from pathlib import Path
from time import perf_counter
from tercas.en_ue_family_kernel import build, ACTIONS, REVISION
from tercas.catalogs import STEELS
from tercas.pierin_ue_registry import new_study_indices


def report():
    baseline=json.load(gzip.open(Path(__file__).parent/'recovery_current/EN_UE_FAMILY_MATERIAL_COVERAGE.json.gz'))
    materials=[]
    for name,steel in STEELS.items():
        before=next(m for m in baseline['materials'] if m['name']==name)
        rows=[];times=[];counts=Counter()
        for index in new_study_indices():
            start=perf_counter();value=build(index,fyb_MPa=steel['fy_MPa']);times.append(perf_counter()-start)
            for c in value['components'].values():counts[c['section_status']]+=1
            rows.append(dict(catalog_index=index,catalog_id=value['catalog_id'],
                eligibility={a:value['components'][a]['eligible'] for a in ACTIONS},
                capacities=value['signed_capacity_floor'],
                methods={a:value['components'][a]['section_status'] for a in ACTIONS},
                reasons={a:value['components'][a]['blocking_reasons'] for a in ACTIONS},
                shear_eligible=value['shear']['eligible'],
                whole_member_approved=value['whole_member_approved']))
        materials.append(dict(name=name,fy_MPa=steel['fy_MPa'],
            before={a:before['branches'][a]['eligible'] for a in ACTIONS},
            after={a:sum(r['eligibility'][a] for r in rows) for a in ACTIONS},
            shear_before=before['shear_eligible'],shear_after=sum(r['shear_eligible'] for r in rows),
            methods=dict(counts),cold_build_seconds=dict(total=sum(times),mean=sum(times)/len(times),maximum=max(times)),rows=rows))
    return dict(method_revision=REVISION,baseline_revision=baseline['method_revision'],
        baseline_commit='39d1673b0f879112367d36abc2b10f0525072f87',profile_count=len(new_study_indices()),
        python=platform.python_version(),scope='Synthetic nominal sections only; monothread scalar builds, no member solver, no global approval',materials=materials)

if __name__=='__main__':
    print(json.dumps(report(),indent=2,ensure_ascii=False,allow_nan=False))
