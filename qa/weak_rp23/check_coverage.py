import json, time
from tercas import nbr_ue_weak_rp23 as candidate
from tercas import nbr_ue_family as old
start=time.monotonic();rows=[]
for fy in (250.,300.,345.,350.):
    subset=[]
    for i in old.registry.new_study_indices():
        o=candidate.assess(i,L_mm=6000.,material=dict(old.DEFAULT_MATERIAL,fy_MPa=fy))
        n=o['weak']['negative'];el=o['rp23_negative_local_candidate']
        subset.append(dict(index=i,id=o['catalog_id'],RP23=el['eligible'],reason=el.get('reason'),
            local=n['local']['eligible'],reference=n['complete_reference_components'],
            fallback=n['local'].get('method')=='RP23_01_Eq28_30_lips_compressed',
            MRd=n['pure_weak_reference_MRd_Nmm'],positive=o['weak']['positive']['complete_reference_components'],
            coefficients=el.get('coefficients'),eta=el.get('eta'),psi=el.get('psi'),d_t=el.get('d_over_t'),
            previous_MLE_gap=n['local'].get('previous_MLE_gap'),NBR_Table4_flat_ratios=el.get('NBR_Table4_flat_ratios'),
            Ml=el.get('Ml_Nmm'),ri_t=el.get('sample',{}).get('ri_over_t')))
    rows.append(dict(fy=fy,total=len(subset),counts={k:sum(x[k] for x in subset) for k in ('RP23','local','reference','fallback','positive')},rows=subset))
report=dict(elapsed_seconds=time.monotonic()-start,rows=rows)
open('qa/weak_rp23/coverage.json','w').write(json.dumps(report,indent=2))
print(json.dumps({str(x['fy']):x['counts'] for x in rows},indent=2));print('Seconds',report['elapsed_seconds'])
