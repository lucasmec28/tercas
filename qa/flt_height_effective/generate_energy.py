"""Synthetic q+P coverage for the conditional energy floor, not MRd."""
import json
import math
from pathlib import Path
from qa.flt_height_effective.generate import synthetic
from tercas import pierin_ue_registry as registry, roof_top_load as roof
from tercas import direct_roof_separated as direct, resistance_effective_lengths as lengths
from tercas import flt_height_energy_floor as floor


def run():
    rows=[]
    for index in registry.new_study_indices():
        d=synthetic(index);angle=math.radians(5.71)
        d.update(P_uls=150.*math.cos(angle),P_parallel_uls=150.*math.sin(angle),x_uls=1410.)
        d=lengths.declare(d,Lx_mm=2050.,Ly_mm=2050.,Lz_mm=2733.,
            origin='Synthetic declared Euler energy bounds; physical realization not verified')
        combo=next(c for c in direct.combinations(d) if c['limit_state']=='ELU')
        actions=direct.actions(combo,roof.geometry(d),include_parallel=True)[0]
        result=floor.qualify_family(d,actions)
        assert result['elastic_reference_eligible']
        assert floor.validate_saved(json.loads(json.dumps(result)),d,actions)==result
        keep=('schema','status','physical_span_mm','Ly_used_mm','Lz_used_mm',
            'maximum_reference_moment_Nmm','Ny_assumed_lower_N','T_assumed_lower_Nmm2',
            'B_upper_Nmm','D_upper_Nmm2','lambda_lower_bound','Me_lower_bound_Nmm',
            'determinant_relative_residual','primary_torque_by_action','source_binding',
            'snapshot_sha256')
        rows.append(dict(catalog_index=index,combination=combo,actions=actions,
                         certificate_summary={k:result[k] for k in keep}))
    return dict(schema='flt_height_declared_energy_family_qa_v1',synthetic_inputs_only=True,
        sections=len(rows),computed_conditional_energy_floors=len(rows),
        physical_span_mm=4100.,Ly_mm=2050.,Lz_mm=2733.,point_station_mm=1410.,
        original_external_uniform_N_mm=.5,original_external_point_N=150.,inclination_deg=5.71,
        self_weight='Own-contour mass at CG, separate from roof actions',
        method='Energy/Cauchy/Poincare with declared Euler lower stiffness assumptions',
        physical_energy_inequalities_verified=False,physical_supports_created=False,
        historical_fork_solver_lower_bound_claimed=False,NBR_capacity_floor_qualified=False,
        whole_member_approved=False,no_member_eigen_solver_run=True,rows=rows)


if __name__=='__main__':
    result=run();path=Path(__file__).with_name('FAMILY66_ENERGY_FLOOR_RESULTS.json')
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
