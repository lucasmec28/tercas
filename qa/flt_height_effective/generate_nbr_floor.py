"""Synthetic 66 x 4 sufficient resistance checks; no eigen/member solver."""
import json
import math
from pathlib import Path
from collections import Counter
from qa.flt_height_effective.generate import synthetic
from tercas import pierin_ue_registry as registry, roof_top_load as roof
from tercas import direct_roof_separated as direct, resistance_effective_lengths as lengths
from tercas import ue_catalog_reference as own
from tercas import flt_height_nbr_floor as bridge


def run():
    rows=[];counts=Counter();methods=Counter()
    for fy in (250.,300.,345.,350.):
        for index in registry.new_study_indices():
            d=synthetic(index);d['properties']['fy_MPa']=fy;d=own.activate(d)
            angle=math.radians(5.71)
            d.update(P_uls=150.*math.cos(angle),P_parallel_uls=150.*math.sin(angle),x_uls=1410.)
            d=lengths.declare(d,Lx_mm=2050.,Ly_mm=2050.,Lz_mm=2733.,
                origin='Synthetic declared Euler energy bounds; physical realization not verified')
            combo=next(c for c in direct.combinations(d) if c['limit_state']=='ELU')
            actions=direct.actions(combo,roof.geometry(d),include_parallel=True)[0]
            result=bridge.qualify_family(d,actions)
            assert result['resistance_floor_eligible']
            assert bridge.validate_saved(json.loads(json.dumps(result)),d,actions)==result
            counts[result['status']]+=1;cap=result['resistance_floor'];methods[cap['method']]+=1
            row=dict(catalog_index=index,fy_MPa=fy,status=result['status'],
                component_sufficient=result['component_sufficient'],failure_proven=False,
                Me_floor_Nmm=result['energy_floor']['Me_lower_bound_Nmm'],
                MRd_floor_Nmm=result['MRd_lower_bound_Nmm'],demand_fraction=result['demand_exact_fraction'],
                utilization_upper_bound=result['utilization_upper_bound'],method=cap['method'],
                chi_envelope=cap['chi_envelope'],snapshot_sha256=result['snapshot_sha256'])
            if index in (79,80,81,82):
                row['uniform_MLE_proof']=cap['resistance_proof']
            rows.append(row)
    return dict(schema='flt_height_nbr_energy_floor_family_qa_v1',synthetic_inputs_only=True,
        section_count=66,material_count=4,case_count=len(rows),eligible_floors=len(rows),
        status_counts=dict(counts),method_counts=dict(methods),physical_span_mm=4100.,
        Ly_mm=2050.,Lz_mm=2733.,point_station_mm=1410.,inclination_deg=5.71,
        original_external_uniform_N_mm=.5,original_external_point_N=150.,
        self_weight='Own-contour mass at CG, separate from roof actions',
        physical_energy_inequalities_verified=False,physical_supports_created=False,
        physical_resistance_lower_bound_claimed=False,whole_member_approved=False,
        no_member_eigen_solver_run=True,all_saved_certificates_replayed=True,rows=rows)


if __name__=='__main__':
    result=run();path=Path(__file__).with_name('FAMILY66_NBR_ENERGY_FLOOR_RESULTS.json')
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
