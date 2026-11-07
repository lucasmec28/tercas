"""Synthetic own-contour scalar matrix. No member solver or AppTest."""
import gzip
import json
from pathlib import Path
from tercas import nbr_ue_family as family


def main():
    result={str(fy):family.coverage(L_mm=6000.,material=dict(family.DEFAULT_MATERIAL,fy_MPa=fy),
        load_position='shear_center') for fy in (250.,300.,345.,350.)}
    path=Path(__file__).with_name('MATERIAL_SIGN_COVERAGE.json.gz')
    with gzip.open(path,'wt',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,sort_keys=True)
    print(json.dumps({k:v['counts'] for k,v in result.items()},ensure_ascii=False,indent=2))
    for row in result.values():
        assert row['total']==66
        for key in ('strong_local','strong_distortional','strong_FLT_reference',
                    'weak_positive_local','weak_positive_reference','weak_negative_distortional'):
            assert row['counts'][key]==66,(row['material'],key,row['counts'])
    return result

if __name__=='__main__':main()
