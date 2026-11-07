"""Reproduce six synthetic scalar shear-lag supplemental proofs; no member solve."""
import json
from time import perf_counter
from tercas.en_ue_family_kernel import build
from tercas.en_ue_family_shear_lag import build as lag,REVISION


def report():
    demand=dict(length_mm=4000.,loads=[dict(kind='uniform',q_xy_N_mm=[0.,.03])],
        elements=[dict(a_mm=0.,b_mm=4000.,element_id='synthetic:e1')],
        support_reactions=dict(left_force_xy_N=[0.,-60.],right_force_xy_N=[0.,-60.]))
    rows=[]
    for index in (51,52,58,59,60,67):
        n=build(index,fyb_MPa=300);start=perf_counter()
        p=lag(demand,n,{'axes':{'Mx':{'shear_lag_qualified':False}}})
        elapsed=perf_counter()-start
        rows.append(dict(index=index,old_local_only_Mx_floor_Nmm=n['signed_capacity_floor']['Mx_positive'],
            strict_shear_lag_dispensation=False,explicit_envelope_eligible=p['eligible'],
            beta_lower=p.get('beta_global_lower'),Ix_lower_mm4=p.get('Ix_lower_mm4'),
            new_Mx_floor_Nmm=p.get('moment_capacity_floor_Nmm'),
            supplemental_build_seconds=elapsed,proof=p))
    return dict(method_revision=REVISION,scope='Synthetic pure-Mx L4000/fy300 scalar proof; real member integration is covered separately by pytest receipts',
        count=len(rows),qualified=sum(r['explicit_envelope_eligible'] for r in rows),rows=rows,
        global_approval=False,biaxial_extension=False)

if __name__=='__main__':print(json.dumps(report(),indent=2,ensure_ascii=False,allow_nan=False))
