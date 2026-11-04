"""One-time extraction of elastic-only inputs. Never imports a resistance app."""
from pathlib import Path
import copy,hashlib,json,shutil
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
REG=ROOT/'outputs/tercas_ue100_family_critical_20261103'
STRONG=ROOT/'outputs/tercas_torsion_simple_aisi_20261104'
CAND=ROOT/'outputs/tercas_aisi_app_integration_20261104/candidate'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
for name in ['inputs','modes','vendor','source_review','certificates']: (OUT/name).mkdir(exist_ok=True)
pins=[]
def keep(src,dest):
 target=OUT/dest;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(src,target)
 pins.append(dict(source=str(src.relative_to(ROOT)) if src.is_relative_to(ROOT) else str(src),copy=dest,sha256=sha(src)))
 return dest
rows=json.loads((REG/'FAMILY_ELASTIC_REGISTRY.json').read_text())['profiles']
crows=json.loads((CAND/'tercas/data/ue_family/elastic_registry.json').read_text())['profiles']
assert rows==crows
actual=[]
for r in rows:
 t=r['thickness_mm'];k=f't{t:.2f}'
 # Deliberately exclude every previous-code resistance or analytic local prescription.
 row={key:copy.deepcopy(r[key]) for key in ['profile_id','thickness_mm','dimensions_external_mm','nodes_sha256','material','properties','property_convention','exterior_moduli']}
 row['modal_criticals']={}
 keep(STRONG/f'inputs/ue100x50x17_{k}.json',f'inputs/ue100x50x17_{k}.json')
 for mode in ['web_local','lips_local','lips_distortional']:
  m=copy.deepcopy(r['modal_criticals'][mode]);src=ROOT/m['source']['path'];assert sha(src)==m['source']['sha256']
  m['bundle_file']=keep(src,f'modes/{k}_{mode}.npz');row['modal_criticals'][mode]=m
 b=copy.deepcopy(r['weak_web_distortional']);src=ROOT/b['bound_source']['path'];assert sha(src)==b['bound_source']['sha256']
 b['bundle_certificate']=keep(src,f'certificates/{k}.json');row['web_all_spectrum_bound']=b
 actual.append(row)
for name in ['fsm_core.py','__init__.py']:keep(STRONG/'vendor'/name,'vendor/'+name)
keep(REG/'modal_review/MANUAL_CLASSIFICATION.json','source_review/PRIOR_MODAL_REVIEW.json')
keep(REG/'analytic_review/web_floor_review/REVIEW.json','source_review/PRIOR_WEB_BOUND_REVIEW.json')
keep(STRONG/'MATERIAL_SCALING.json','source_review/PRIOR_STRONG_SCALING.json')
keep(STRONG/'check_material_scaling.py','source_review/PRIOR_STRONG_SCALING.py')
keep(REG/'FINAL_RECEIPT.json','source_review/PRIOR_ELASTIC_RECEIPT.json')
keep(REG/'modal_review/REFINEMENT253_INDEX.json','source_review/PRIOR_MESH_REFINEMENT.json')
keep(REG/'modal_review/PROTOCOL_RESULTS.json','source_review/PRIOR_MODAL_PROTOCOL.json')
keep(ROOT/'outputs/tercas_ue_priority_20261103/web_lower_bound/interval_proof.py','source_review/PRIOR_INTERVAL_COEFFICIENT_KERNEL.py')
for r in rows:
 for side in ['web','lips']:
  t=r['thickness_mm'];keep(REG/f'modal_review/t{t:.2f}/{side}/REVIEW.json',f'source_review/t{t:.2f}_{side}_NUMERICAL_REVIEW.json')
write(OUT/'source_review/PRIMARY_SOURCE.json',dict(url='https://sdi.org/wp-content/uploads/2025/01/ANSI-SDI-AISI-S100-2024-SDI-AISI-S100-2024-C.pdf',sha256=sha(Path('/tmp/torsion_sources/aisi_s100_2024.pdf')),title='ANSI/SDI AISI S100-2024 and Commentary',accessed='2026-11-04',visual_pdf_pages=[95,97,99,100,213],redistributed_full_source=False))
write(OUT/'inputs/elastic_inputs.json',dict(schema='AISI_weak_elastic_only_v1',profiles=actual,NBR_capacities_used=False,original_registry_sha256=sha(REG/'FAMILY_ELASTIC_REGISTRY.json')))
pins.append(dict(source='Derived elastic-only selection from pinned registry',copy='inputs/elastic_inputs.json',sha256=sha(OUT/'inputs/elastic_inputs.json')))
f4review=ROOT/'outputs/tercas_weak_web_f4_independent_review_20261104'
assert sha(f4review/'MANIFEST.json')=='5d48a42b3a9b9bc7717a53574b5409ab22c81902154b9075ad3f787aa08ef248'
for src in sorted(f4review.rglob('*')):
 if src.is_file() and '__pycache__' not in src.parts:keep(src,'f4_applicability/independent/'+str(src.relative_to(f4review)))
keep(ROOT/'outputs/tercas_weak_web_distortional_qualification_20261104/F4_APPLICABILITY_PROPOSAL.json','f4_applicability/PROPOSAL.json')
write(OUT/'SOURCE_PINS.json',pins)
write(OUT/'SOURCE_PRESERVATION.json',dict(sources={str(p):sha(p) for p in [REG/'FAMILY_ELASTIC_REGISTRY.json',CAND/'tercas/data/ue_family/elastic_registry.json',CAND/'tercas/ue_family_reference.py']},candidate_elastic_rows_identical=True,candidate_resistance_code_imported=False))
print('Six elastic-only records; 18 weak modes; no prior resistance imported.')
