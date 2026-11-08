"""Explicit, opt-in reproduction of synthetic CT fixtures via current app code.

Run as a script, never imported by pytest. This intentionally solves the fresh
synthetic member. The regular test module blocks member solvers during replay.
"""
import json
from pathlib import Path


def main():
    from tercas.application import calculate
    from tercas.study_completion import complete_result
    from tercas.isolated_ct_torsion import proof
    directory=Path(__file__).parent/'fixtures'
    for name in ('roof','girt'):
        path=directory/('ct_zero_'+name+'.json')
        data=json.loads(path.read_text())['input_data']
        assert data['synthetic'] is True
        result=complete_result(calculate(data))
        assert proof(result)['ELU_cases']==1
        record=next(r for r in result['global_verification']['checks'] if r['id']=='torsion_warping')
        assert record['status']=='not_applicable'
        keep=('schema','input_data','input_fingerprint','inclination_evidence','model_domain_evidence',
              'direct_self_weight_evidence','ue_catalog_reference_evidence','torsion_evidence','synthetic')
        out={k:result[k] for k in keep if k in result}
        out['synthetic_fixture_scope']='Actual calculate then complete_result output from versioned CT code, synthetic inputs only. Selected original fields preserved unchanged; not project data or a structural design certificate.'
        path.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'))+'\n')
        print(name,record['status'])


if __name__=='__main__':main()
