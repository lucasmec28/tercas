"""Prepare an OFFLINE proposed inventory after full-certificate kernel audit.

Writes only a QA proposal, not the trusted runtime inventory or code pin.
Review and explicit installation are separate. No runtime auto-enrollment API.
"""
import hashlib
import json
from pathlib import Path

from tercas import en_ue_qualified_library as library
from tercas.en_ue_catalog_operators import available_indices,build_catalog_component_sections

ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'qa/en_ue_operators'
comparison_path=QA/'complete_kernel_comparison.json'
comparison=json.loads(comparison_path.read_text())
if comparison['all_complete_certificates_identical'] is not True or comparison['compared_profile_count']!=83:
    raise SystemExit('Complete native/Haswell candidate audit is absent or not successful')
rows={row['catalog_index']:row for row in comparison['rows']}
entries={}
for index in available_indices():
    candidate=build_catalog_component_sections(index)
    blob=json.dumps(candidate,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    audit=rows[index]
    if (candidate['content_sha256']!=audit['candidate_content_sha256']
            or candidate['content_sha256']!=audit['haswell_candidate_content_sha256']
            or hashlib.sha256(blob).hexdigest()!=audit['complete_serialized_sha256']
            or audit['complete_serialization_byte_identical'] is not True):
        raise SystemExit(f'STOP: candidate {index} differs from the complete audited output')
    reference_id=library._reference_id(index)
    qualified=library._qualified_payload(candidate,reference_id)
    record=dict(reference_id=reference_id,candidate_content_sha256=candidate['content_sha256'],
        qualified_content_sha256=qualified['content_sha256'],source_binding=library._binding(candidate),
        eligible_by_action=library._eligible(candidate),signed_capacity_floor=candidate['signed_capacity_floor'])
    library._check_candidate(candidate,record)
    if library._restore_candidate_snapshot(qualified)!=candidate:raise SystemExit('Candidate overlay is not reversible')
    entries[str(index)]=record
payload=dict(schema=library.INVENTORY_SCHEMA,library_revision=library.LIBRARY_REVISION,
    qualified_schema=library.SCHEMA,candidate_schema=library.CANDIDATE_SCHEMA,
    candidate_method_revision=library.CANDIDATE_REVISION,
    candidate_source_commit='2fd6a29e5b3194b215f62082836b63e1be6486b7',
    complete_kernel_audit_sha256=hashlib.sha256(comparison_path.read_bytes()).hexdigest(),
    profile_count=len(entries),signed_branch_count=6*len(entries),
    eligible_signed_branch_count=sum(sum(r['eligible_by_action'].values()) for r in entries.values()),
    integration_conditions=library.INTEGRATION_CONDITIONS,entries=entries)
payload['content_sha256']=library._sha(payload)
path=QA/'proposed_qualified_inventory.json';path.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(proposal_path=str(path),inventory_sha256=payload['content_sha256'],
    profile_count=payload['profile_count'],eligible_signed_branches=payload['eligible_signed_branch_count'],
    runtime_inventory_installed=False),indent=2))
