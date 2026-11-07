"""Replay final service presentation over authenticated synthetic aa1eef2 fields.

Pure arithmetic/field-envelope validation is allowed; member solvers are blocked.
This is not a new mechanical analysis or migration of user history. The
original archived results remain unchanged; only fresh copies are projected.
"""
import copy,gzip,hashlib,json,os,subprocess,time
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from tercas import global_verification as gv,completion_requirements as cr
from tercas import isolated_service_panorama as sp
from tercas import isolated_service_component as service
from tercas import isolated_en_ue_family_application as en
from tercas import nbr_ue_family_application as nbr


def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def sha(x):return hashlib.sha256(canonical(x)).hexdigest()
def main():
    folder=Path(os.environ['SYNTHETIC_RESULTS'])
    matrix=json.loads(Path(__file__).with_name('family_application_matrix_current.json').read_text())
    assert matrix['complete'] and len(matrix['family'])==66
    root=Path(__file__).resolve().parents[2]
    files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted((root/'tercas').rglob('*.py'))}
    output=Path(__file__).with_name('service_panorama_family_replay.json')
    receipt=dict(kind='new_presentation_replay_of_preserved_synthetic_fields',
        calculation_source_commit=matrix['source_commit'],
        presentation_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        production_file_sha256=files,complete=False,records=[],whole_member_approved=False)
    def save():output.write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    save()
    with ExitStack()as stack:
        for name in ('tercas.torsion_vlasov.vlasov.solve_member','tercas.direct_torsion.solve_member'):
            stack.enter_context(patch(name,side_effect=AssertionError('Replay must not run solver: '+name)))
        for index in matrix['family']:
            path=folder/(str(index)+'.json.gz');raw=path.read_bytes();old=json.loads(gzip.decompress(raw));t=time.perf_counter()
            assert old['input_data']['catalog_index']==index
            # Authenticate current calculation packets, then build a fresh view.
            es=en.preserved(old);ns=nbr.preserved(old);ss=service.saved(old)
            result=cr.attach(gv.attach_global_verification(old))
            sp.validate_saved(result);cr.saved(result)
            assert result['whole_member_approved'] is False
            assert result['global_verification']['whole_member_approved'] is False
            allowed={'global_verification','completion_requirements'}
            assert {k:v for k,v in old.items()if k not in allowed}=={k:v for k,v in result.items()if k not in allowed}
            assert sha(en.preserved(result))==sha(es) and sha(nbr.preserved(result))==sha(ns) and sha(service.saved(result))==sha(ss)
            checks=result['global_verification']['checks']
            ids=[c['id']for c in checks];assert len(ids)==len(set(ids))
            service_rows=[dict(id=c['id'],status=c['status'],index=c['index'],reason=c['reason'])for c in checks if c['limit_state']=='ELS']
            before=[c for c in old['global_verification']['checks']if c['limit_state']!='ELS']
            after=[c for c in checks if c['limit_state']!='ELS'];assert before==after
            receipt['records'].append(dict(index=index,source_file_sha256=hashlib.sha256(raw).hexdigest(),
                calculation_packets_unchanged=True,non_service_checks_unchanged=True,ELS=service_rows,
                projected_global_sha256=sha(result['global_verification']),elapsed_seconds=time.perf_counter()-t))
            save();print(json.dumps(receipt['records'][-1],ensure_ascii=False),flush=True)
    assert len(receipt['records'])==66
    assert all(hashlib.sha256((root/k).read_bytes()).hexdigest()==v for k,v in files.items())
    receipt['complete']=True;save();print('66 authenticated presentation replays completed without solvers',flush=True)
if __name__=='__main__':main()
