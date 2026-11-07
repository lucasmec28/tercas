"""Synthetic coverage audit; output hashes never admit external authorities."""
import json
from collections import Counter
from tercas.en_ue_family_kernel import build,ACTIONS,REVISION
from tercas.catalogs import STEELS
from tercas.pierin_ue_registry import new_study_indices


def report():
    materials=[]
    for name,steel in STEELS.items():
        rows=[build(index,fyb_MPa=steel['fy_MPa']) for index in new_study_indices()]
        branches={}
        for action in ACTIONS:
            counts=Counter(); occurrences=Counter()
            for row in rows:
                row_keys=set()
                for reason in row['components'][action]['blocking_reasons']:
                    key=(reason['category'],reason['code'],reason.get('detail',''))
                    occurrences[key]+=1;row_keys.add(key)
                counts.update(row_keys)
            branches[action]=dict(eligible=sum(row['components'][action]['eligible'] for row in rows),
                blocked=sum(not row['components'][action]['eligible'] for row in rows),
                reason_counts=[dict(category=k[0],code=k[1],detail=k[2],count=n,occurrences=occurrences[k])
                               for k,n in sorted(counts.items())])
        materials.append(dict(name=name,**steel,branches=branches,
            shear_eligible=sum(row['shear']['eligible'] for row in rows),
            rows=[dict(catalog_index=row['catalog_index'],catalog_id=row['catalog_id'],
                       eligible_by_action={a:row['components'][a]['eligible'] for a in ACTIONS},
                       capacity_floor=row['signed_capacity_floor'],
                       blocking_reasons={a:row['components'][a]['blocking_reasons'] for a in ACTIONS},
                       shear=row['shear']['shear_capacity_lower_N']) for row in rows]))
    return dict(method_revision=REVISION,profile_count=len(new_study_indices()),materials=materials,
                note='Complete documentary rows only. Section-method eligibility is not material conformity or whole-member approval.')

if __name__=='__main__':print(json.dumps(report(),indent=2,ensure_ascii=False))
