"""Regenerate the isolated 83-row candidate coverage, no structural solver."""
import csv
import hashlib
import json
import platform
from collections import Counter
from pathlib import Path

from tercas.en_ue_catalog_operators import available_indices, build_catalog_component_sections, PURE_ACTIONS

OUT=Path(__file__).parent/'en_ue_operators'
OUT.mkdir(exist_ok=True)
rows=[];eligibility=Counter();blockers=Counter()
for i in available_indices():
    cert=build_catalog_component_sections(i)
    row=dict(catalog_index=i,catalog_id=cert['catalog_id'],dimensions_mm=cert['nominal_identity']['dimensions_mm'],
        nodes_sha256=cert['nodes_sha256'],content_sha256=cert['content_sha256'],
        all_normal_components_eligible=cert['all_normal_components_eligible'],
        geometry_guard_satisfied=cert['geometry_guard']['satisfied'],components={})
    for name,c in cert['components'].items():
        row['components'][name]=dict(eligible=c['eligible'],section_status=c['section_status'],
            first_yield_capacity_floor=c['first_yield_capacity_floor'],blocking_reasons=c['blocking_reasons'])
        eligibility[name]+=c['eligible']
        for b in c['blocking_reasons']:blockers[b['code']+': '+b.get('detail','')]+=1
        if c['eligible'] and name=='N_compression':
            row['components'][name].update(Aeff_mm2=c['effective_properties']['A_mm2'],
                effective_centroid_relative_to_gross_mm=c['effective_centroid_relative_to_gross_mm'],
                rho_panels=[p['rho'] for p in c['local_panels']],chi_d=[s['chi_d'] for s in c['stiffeners']])
    rows.append(row)
summary=dict(schema='EN_Ue_candidate_coverage_audit_v1',profile_count=len(rows),
    total_signed_branches=6*len(rows),eligible_signed_branches=sum(eligibility.values()),
    eligible_by_action=dict(eligibility),fully_eligible_profile_count=sum(r['all_normal_components_eligible'] for r in rows),
    geometry_guard_satisfied_count=sum(r['geometry_guard_satisfied'] for r in rows),blocking_reason_counts=dict(blockers),
    solver_runs=0,python=platform.python_version(),runtime_release_approved=False,rows=rows)
(OUT/'inventory.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
with (OUT/'coverage.csv').open('w',newline='') as f:
    writer=csv.writer(f);writer.writerow(['index','catalog_id','h','bf','lip','t',*PURE_ACTIONS,'all_six'])
    for r in rows:
        writer.writerow([r['catalog_index'],r['catalog_id'],*(r['dimensions_mm'][k] for k in ('h','bf','lip','t')),
            *(r['components'][k]['first_yield_capacity_floor'] if r['components'][k]['eligible'] else 'BLOCKED' for k in PURE_ACTIONS),r['all_normal_components_eligible']])
protected=['tercas/three_girt_en_normal/en1993_normal_components.py','tercas/en_simplified_interaction.py',
    'tercas/en_interaction_capacity_reference.py','docs/EN627_OPENBLAS_COMPATIBILITY_20261106.md']
root=Path(__file__).resolve().parents[1]
(OUT/'legacy_source_hashes.json').write_text(json.dumps({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in protected},indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
