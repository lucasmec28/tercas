"""Recover the original shear inventory without ever rewriting release pins.

Canonical hashes are required before output. Original saved Git-blob identity
from the r5 publication manifest is also compared and disclosed independently.
This is recovery tooling, not a new qualification or a runtime enrollment path.
"""
import hashlib
import json
import platform
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tercas import en_ue_shear as s
from tercas.catalogs import entries
from tercas.weak_pierin import reference_for_index

EXPECTED_INVENTORY='8beba399c4afc056eb6ae6d9a7b4f25beef7fd246089e34c1c17c13a5deba28f'
EXPECTED_SOURCE='b5615b766a30aec50b19a29d18c9cf4e805e8721e8dd0822976172e187c6e47e'
EXPECTED_NOTE='854d9d5a9f1603470c3b43dc9d1ce59cfef739e0d437ef0f8a681fa14d15afa0'
R5_MANIFEST_BLOB='6f6fe942efdd0b2117f4767a2f12d70ff6398ff8'
R5_MANIFEST_BYTES=360343
OUT=ROOT/'qa/en_ue_shear'
module=ROOT/'tercas/en_ue_shear.py'
module_before=module.read_bytes()
if s.INVENTORY_SHA256!=EXPECTED_INVENTORY or s.SOURCE_SHA256!=EXPECTED_SOURCE:
    raise SystemExit('Original runtime pins changed; no recovery output written')
source=json.loads(s.SOURCE_PATH.read_text(encoding='utf-8'))
if s._verify_seal(source)!=EXPECTED_SOURCE:
    raise SystemExit('Source manifest differs from original canonical pin; no output')
note=(ROOT/source['qualification_note_path']).read_bytes()
if hashlib.sha256(note).hexdigest()!=EXPECTED_NOTE:
    raise SystemExit('Original qualification note differs; no output')
ids=[i for i,e in enumerate(entries()) if e['family']=='Ue'
    and reference_for_index(i)['status']=='tabulated_adopted_reference']
if ids!=list(range(83)):
    raise SystemExit('Original 83 exact nominal Ue inventory changed; no output')
records={str(i):s._derive(i) for i in ids}
inventory=s._seal(dict(schema=s.INVENTORY_SCHEMA,revision=s.REVISION,method=s.METHOD,
    source_sha256=s.SOURCE_SHA256,entries=records))
if inventory['content_sha256']!=EXPECTED_INVENTORY:
    raise SystemExit('Regenerated canonical inventory differs from original: '+inventory['content_sha256'])
encoded=(json.dumps(inventory,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
blob=hashlib.sha1(b'blob '+str(len(encoded)).encode()+b'\0'+encoded).hexdigest()
if module.read_bytes()!=module_before:
    raise SystemExit('Module changed during recovery; no output')
s.INVENTORY_PATH.write_bytes(encoded)
receipt=dict(schema='EN_Ue_shear_recovery_receipt_v1',source_commit='77ed79065fb052f215fa8929d0e07196da761595',
    recovered_source_texts=True,regenerated_inventory=True,original_git_commit_restored=False,
    expected_inventory_content_sha256=EXPECTED_INVENTORY,actual_inventory_content_sha256=inventory['content_sha256'],
    expected_source_content_sha256=EXPECTED_SOURCE,actual_source_content_sha256=source['content_sha256'],
    qualification_note_sha256=EXPECTED_NOTE,count=len(ids),pins_unchanged=True,
    module_before_after_sha256=hashlib.sha256(module_before).hexdigest(),
    actual_inventory_file_sha256=hashlib.sha256(encoded).hexdigest(),actual_inventory_git_blob_sha1=blob,
    actual_inventory_bytes=len(encoded),r5_manifest_git_blob_sha1=R5_MANIFEST_BLOB,
    r5_manifest_bytes=R5_MANIFEST_BYTES,r5_manifest_blob_match=blob==R5_MANIFEST_BLOB,
    canonical_recovery_match=True,
    environment=dict(python=platform.python_version(),platform=platform.platform(),BLAS_used=False),
    new_tests_run_by_this_script=False)
(OUT/'inventory_recovery_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
