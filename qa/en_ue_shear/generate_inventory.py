"""Explicit offline qualification preparation; not called by runtime."""
import hashlib,json,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tercas import en_ue_shear as s
from tercas.catalogs import entries
from tercas.weak_pierin import reference_for_index
note=ROOT/'docs/EN_UE_SHEAR_QUALIFICATION_20261106.txt'
evidence=s._seal(dict(schema='EN_Ue_shear_sources_v1',revision=s.REVISION,
    qualification_note_path=str(note.relative_to(ROOT)),
    qualification_note_file_sha256=hashlib.sha256(note.read_bytes()).hexdigest(),
    sources=[dict(url='https://www.phd.eng.br/wp-content/uploads/2015/12/en.1993.1.3.2006.pdf',
        pdf_sha256='fd37edf92be58e1dc48745c29ed5a14265797b4f5a8e16f0e6f3f5f6f899d163',
        verified_printed_pages=[16,17,18,19,20,21,45,46,55],visual_tables=[5.1,6.1]),
        dict(url='https://help.scia.net/download/17.0/en/SteelCodeCheck_Theory_enu.pdf',
        pdf_sha256='efa8d1b8e91a5e6bb9125eb96d79b1017117d4d1b8f1d6c638e76110b504b80b',
        visually_verified_printed_pages=[80])],
    basis='EN13 6.8 and 6.10a, Table6.1 no support stiffening; hw exact, sw<=hw; one original web and two rotated flange webs; no plastic/lip/extra-corner credit',
    geometry_source_commit='740a63e60498f29250b234c8b00f4fbd02093dec',
    baseline_commit='89785b61c2b01a7d5ec350b00c10fc5e9bc8e90d'))
s.SOURCE_SHA256=evidence['content_sha256']
ids=[i for i,e in enumerate(entries()) if e['family']=='Ue'
    and reference_for_index(i)['status']=='tabulated_adopted_reference']
assert len(ids)==83
records={str(i):s._derive(i) for i in ids}
inventory=s._seal(dict(schema=s.INVENTORY_SCHEMA,revision=s.REVISION,method=s.METHOD,
    source_sha256=s.SOURCE_SHA256,entries=records))
for path,data in ((s.SOURCE_PATH,evidence),(s.INVENTORY_PATH,inventory)):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
module=ROOT/'tercas/en_ue_shear.py'
text=module.read_text()
import re
text=re.sub(r"INVENTORY_SHA256 = '[^']+'",f"INVENTORY_SHA256 = '{inventory['content_sha256']}'",text)
text=re.sub(r"SOURCE_SHA256 = '[^']+'",f"SOURCE_SHA256 = '{s.SOURCE_SHA256}'",text)
module.write_text(text)
summary=dict(count=len(ids),indices=ids,material=s.MATERIAL,inventory_sha256=inventory['content_sha256'],
    source_sha256=s.SOURCE_SHA256,all_geometric_guards_passed=all(r['applicability']['satisfied'] for r in records.values()),
    scalar_environment=dict(python=platform.python_version(),platform=platform.platform(),BLAS_used=False),
    ranges={})
for key in ('external_b_over_t','external_c_over_t','external_h_over_t','external_c_over_b'):
    values=[r['applicability'][key] for r in records.values()]
    summary['ranges'][key]=[min(values),max(values)]
for axis in ('strong','weak'):
    values=[r['shear_capacity_lower_N'][axis] for r in records.values()]
    lambdas=[r['shear_capacity_geometry'][axis]['lambda_upper'] for r in records.values()]
    summary['ranges'][axis+'_N']=[min(values),max(values)]
    summary['ranges'][axis+'_lambda']=[min(lambdas),max(lambdas)]
    summary[axis+'_branch_counts']={branch:sum(r['shear_capacity_geometry'][axis]['table61_branch']==branch for r in records.values())
        for branch in ('lambda_le_0.83','0.83_lt_lambda_lt_1.4','lambda_ge_1.4')}
(ROOT/'qa/en_ue_shear/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
