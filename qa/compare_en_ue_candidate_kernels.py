"""Audit complete candidate bytes in native and already-supported Haswell.

Use only on a host known to support the requested OpenBLAS kernel. Does not
install a kernel, auto-register a hash, or modify runtime reference files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'qa/en_ue_operators'


def collect(destination):
    import numpy as np
    from tercas.en_ue_catalog_operators import available_indices,build_catalog_component_sections
    runtime={}
    try:
        from threadpoolctl import threadpool_info
        runtime['threadpool_info']=threadpool_info()
    except ImportError:runtime['threadpool_info']='threadpoolctl unavailable'
    runtime.update(python=platform.python_version(),numpy=np.__version__,machine=platform.machine(),
        requested_OPENBLAS_CORETYPE=os.environ.get('OPENBLAS_CORETYPE'),
        OPENBLAS_NUM_THREADS=os.environ.get('OPENBLAS_NUM_THREADS'))
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i in available_indices():
        c=build_catalog_component_sections(i)
        blob=json.dumps(c,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
        (destination/f'{i}.json').write_bytes(blob)
        rows.append(dict(catalog_index=i,catalog_id=c['catalog_id'],candidate_content_sha256=c['content_sha256'],
            complete_serialized_sha256=hashlib.sha256(blob).hexdigest(),byte_count=len(blob),
            nodes_sha256=c['nodes_sha256'],nominal_identity_sha256=c['nominal_identity_sha256'],
            eligible={k:v['eligible'] for k,v in c['components'].items()},signed_capacity_floor=c['signed_capacity_floor']))
    (destination/'index.json').write_text(json.dumps(dict(runtime=runtime,rows=rows),indent=2)+'\n')


def compare():
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='en-ue-native-haswell-') as temp:
        base=Path(temp);indexes={}
        for kernel in ('native','Haswell'):
            env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1'
            if kernel=='native':env.pop('OPENBLAS_CORETYPE',None)
            else:env['OPENBLAS_CORETYPE']='Haswell'
            subprocess.run([sys.executable,__file__,'--collect',str(base/kernel)],env=env,cwd=ROOT,check=True)
            indexes[kernel]=json.loads((base/kernel/'index.json').read_text())
        if [r['catalog_index'] for r in indexes['native']['rows']] != [r['catalog_index'] for r in indexes['Haswell']['rows']]:
            raise RuntimeError('Kernel coverage differs')
        rows=[]
        for a,b in zip(indexes['native']['rows'],indexes['Haswell']['rows']):
            i=a['catalog_index'];identical=(base/'native'/f'{i}.json').read_bytes()==(base/'Haswell'/f'{i}.json').read_bytes()
            rows.append(dict(**a,haswell_candidate_content_sha256=b['candidate_content_sha256'],
                haswell_complete_serialized_sha256=b['complete_serialized_sha256'],
                complete_serialization_byte_identical=identical))
        result=dict(schema='EN_Ue_complete_candidate_kernel_audit_v1',candidate_source_commit='2fd6a29e5b3194b215f62082836b63e1be6486b7',
            compared_profile_count=len(rows),all_complete_certificates_identical=all(r['complete_serialization_byte_identical'] for r in rows),
            native_runtime=indexes['native']['runtime'],haswell_runtime=indexes['Haswell']['runtime'],rows=rows,
            hash_registration_performed=False,structural_solver_runs=0)
        (OUT/'complete_kernel_comparison.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
        if not result['all_complete_certificates_identical']:raise SystemExit('STOP: complete certificates differ')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--collect');args=parser.parse_args()
    collect(args.collect) if args.collect else compare()
