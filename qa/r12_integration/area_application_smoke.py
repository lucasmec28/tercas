"""Fresh 40-ELU synthetic application and saved-reader/Word smoke.

No private project, external upload or global approval. The original point
load inventory and support-limit cases are retained without filtering.
"""
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

from docx import Document
from test_en_concurrent_r12_application import data
from en_ue_test_helpers import run
from tercas import isolated_en_ue_family_application as en
from tercas import isolated_en_ue_family as original
from tercas import isolated_en_ue_family_ui as ui
from tercas import direct_torsion
from tercas.torsion_vlasov import vlasov


def main():
    out=Path(__file__).parent
    d=data();d.update(load_mode='area',selected_types=['ELU normal'])
    d['area_inputs'].update(permanent_kgf_m2=1.,live_kgf_m2=1.,wind_up_kgf_m2=1.,wind_down_kgf_m2=1.)
    start=time.perf_counter();result=run(d);calculation_seconds=time.perf_counter()-start
    ev=en.preserved(result)
    ids=[r['combination_id'] for r in ev['records']]
    assert len(ids)==len(set(ids))==ev['ELU_cases']==40
    assert ev['pending_demand_cases']==0 and all(row.get('check') for row in ev['records'])
    assert ev['shear_computed_cases']==40
    assert not result['whole_member_approved']
    support=[r for r in ev['records'] if r['check']['source_demand'].get('support_limit_states')]
    assert len(support)==4
    for row in support:
        assert any(p['source_piece']['kind']=='support_limit' for p in row['check']['pieces'])
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
    if os.environ.get('SAVE_SYNTHETIC_RESULTS_TO'):
        folder=Path(os.environ['SAVE_SYNTHETIC_RESULTS_TO']);folder.mkdir(parents=True,exist_ok=True)
        (folder/'area40.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    cloned=json.loads(raw);before=copy.deepcopy(cloned)
    def forbidden(*a,**kw):raise AssertionError('Saved field replay must not solve a member')
    direct_torsion.solve_member=forbidden;vlasov.solve_member=forbidden
    en._VALIDATED_RESULTS.clear();original._VERIFIED_READS.clear()
    start=time.perf_counter();read=en.preserved(cloned)
    en.global_context(cloned,sectional=True)
    doc=Document();ui.report(doc,cloned)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'EN família salvo inválido' not in text
    pending=[r for r in read['records'] if r['check']['component_status']['stress']=='pending']
    assert len(pending)==4
    for row in pending:
        message=ui._concurrent_pending_reason(row['check'])
        assert message and message in text and 'sem inferência de reprovação física' in message
    assert cloned==before
    receipt=dict(kind='SYNTHETIC_40_ELU_APPLICATION_NOT_USER_PROJECT',
        calculation_seconds=calculation_seconds,saved_replay_and_word_seconds=time.perf_counter()-start,
        input_sha256=hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        full_result_sha256=hashlib.sha256(raw).hexdigest(),
        counts={k:read[k] for k in ('ELU_cases','stress_computed_cases','shear_computed_cases','mv_computed_cases','partial_cases','pending_demand_cases')},
        support_limit_cases=[r['combination_id'] for r in support],
        pending_cases=[dict(id=r['combination_id'],reasons=r['check']['concurrent_shear_lag_supplement']['blocking_reasons']) for r in pending],
        member_solvers_blocked_during_saved_replay=True,whole_member_approved=False)
    (out/'area_application_smoke.json').write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
