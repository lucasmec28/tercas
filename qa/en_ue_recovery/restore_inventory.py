"""Reconstitute the lost inventory, accepting ONLY its two historical hashes.

This is recovery, not qualification or enrollment. The historical kernel-audit
hash comes verbatim from the independent review transcript. Current calculation
is recorded separately and is not represented as the historical audit run.
"""
import hashlib
import json
from pathlib import Path
from tercas import en_ue_catalog_operators as candidate
from tercas import en_ue_qualified_library as library

ROOT=Path(__file__).resolve().parents[2]
EXPECTED_CANONICAL='51e7bac78b21e58f2adb2cc5bd25b1a65469fe0334e921e31bc351522c0e1f53'
EXPECTED_FILE='455f8aa52886d620ec54255c332d39ccbac55212870bc046dd3ff4fbe1429353'
HISTORICAL_AUDIT='ce375847a8921f9c9c8355473770d7290f2b365035d5be8263376441a25f8abf'
rows={}
for index in candidate.available_indices():
    c=candidate.build_catalog_component_sections(index)
    reference_id=library._reference_id(index)
    q=library._qualified_payload(c,reference_id)
    record=dict(reference_id=reference_id,candidate_content_sha256=c['content_sha256'],
        qualified_content_sha256=q['content_sha256'],source_binding=library._binding(c),
        eligible_by_action=library._eligible(c),signed_capacity_floor=c['signed_capacity_floor'])
    library._check_candidate(c,record)
    assert library._restore_candidate_snapshot(q)==c
    rows[str(index)]=record
payload=dict(schema=library.INVENTORY_SCHEMA,library_revision=library.LIBRARY_REVISION,
    qualified_schema=library.SCHEMA,candidate_schema=library.CANDIDATE_SCHEMA,
    candidate_method_revision=library.CANDIDATE_REVISION,
    candidate_source_commit='2fd6a29e5b3194b215f62082836b63e1be6486b7',
    complete_kernel_audit_sha256=HISTORICAL_AUDIT,
    profile_count=len(rows),signed_branch_count=6*len(rows),
    eligible_signed_branch_count=sum(sum(r['eligible_by_action'].values()) for r in rows.values()),
    integration_conditions=library.INTEGRATION_CONDITIONS,entries=rows)
payload['content_sha256']=library._sha(payload)
blob=(json.dumps(payload,indent=2,ensure_ascii=False)+'\n').encode()
actual_file=hashlib.sha256(blob).hexdigest()
exact=payload['content_sha256']==EXPECTED_CANONICAL and actual_file==EXPECTED_FILE
report=dict(recovery_only=True,structural_solver_runs=0,historical_audit_sha256=HISTORICAL_AUDIT,
    historical_audit_source='Verbatim complete SHA256 recovered by independent reviewer from original tool output',
    canonical_sha256=payload['content_sha256'],expected_canonical_sha256=EXPECTED_CANONICAL,
    file_sha256=actual_file,expected_file_sha256=EXPECTED_FILE,byte_exact=exact,
    profile_count=len(rows),eligible_signed_branch_count=payload['eligible_signed_branch_count'],
    current_run_is_not_the_historical_kernel_audit=True)
(ROOT/'qa/en_ue_recovery/inventory_recovery_receipt.json').write_text(json.dumps(report,indent=2)+'\n')
if not exact:
    (ROOT/'qa/en_ue_recovery/inventory_unmatched.json').write_bytes(blob)
    raise SystemExit(json.dumps(report,indent=2)+'\nSTOP: original pins unchanged; runtime inventory NOT installed')
(ROOT/'tercas/data/en_ue_qualified_operator_inventory_20261106.json').write_bytes(blob)
print(json.dumps(report,indent=2))
