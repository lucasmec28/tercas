"""Reproduce the central B1 reference on repository synthetic QA inputs."""
import hashlib
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tercas.three_girt_warping import application as warping
from tercas.three_girt_axial import application as nbr
from tercas import three_girt_local_stability as b1,three_girt_scope
from tercas.ue_family_reference import apply_geometry


def main():
    source=json.loads((ROOT/'tests/data/three_girt_normal_QA_input.json').read_text())
    data=apply_geometry(source['input_data'],3.35,4000.)
    cfg=warping.current_configuration(data,source['configuration']['three_girt'])
    demand=warping.calculate(data,cfg,verification_scope=three_girt_scope.SCHEMA)
    result=nbr.attach(demand,nbr.reference_configuration(demand))
    component=b1.saved(nbr.saved_component(result),demand=demand)
    out=dict(base_commit='23dd0355e129c66d80b269fe18cd416c9fb0e9ad',
        input_scope='Synthetic repository QA, Ue100x50x17 t3.35, L4000; not Lucas project data',
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/'tercas/three_girt_local_stability.py',ROOT/'tercas/three_girt_axial/application.py')},
        component=component)
    path=ROOT/'qa/CENTRAL_LOCAL_B1_20261106.json.gz'
    payload=(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    path.write_bytes(gzip.compress(payload,compresslevel=9,mtime=0))
    local=component['local_NM_reference']
    print(json.dumps(dict(path=str(path),local_formula_cases=component['local_formula_cases'],
        blocked_cases=component['diagnostic_or_blocked_cases'],maximum_B1=component['maximum_B1_reference'],
        local_NM_reference_complete=local['complete'],local_NM_maximum=local['maximum_available'],
        local_NM_missing_capacity_keys=local['missing_capacity_keys'],
        network_qualified=component['network_stability_qualified']),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
