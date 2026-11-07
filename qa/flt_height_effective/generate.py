"""Synthetic family matrix. Run from repository root; scalar arithmetic only."""
import json
import math
from pathlib import Path
from tercas import pierin_ue_registry as registry, ue_catalog_reference as own
from tercas import roof_top_load as roof, direct_self_weight as pp
from tercas import direct_roof_separated as direct
from tercas import resistance_effective_lengths as lengths
from tercas import flt_height_effective as flt
from tercas.application import defaults


def synthetic(index):
    d=pp.activate(defaults(index))
    angle=math.radians(5.71)
    d.update(member_application='purlin',load_mode='direct',L_mm=4100.,
        q_uls=.5*math.cos(angle),q_parallel_uls=.5*math.sin(angle),
        P_uls=0.,P_parallel_uls=0.,x_uls=2050.,
        q_sls=.3*math.cos(angle),q_parallel_sls=.3*math.sin(angle),
        P_sls=0.,P_parallel_sls=0.,x_sls=2050.,
        roof_top_load=roof.choice('web_midplane'),inclination=dict(value=5.71,unit='degrees'))
    d['properties']['fy_MPa']=300.
    d['segments']=[dict(start_mm=0.,end_mm=4100.,Ly_effective_mm=2050.,
        Lz_effective_mm=2050.,Cb_mode='one',restraint_provenance='Synthetic declared resistance lengths; no added physical supports')]
    return own.activate(d)


def compact_row(row):
    """Keep auditable facts once per section, not four copies of source prose."""
    cases=row['cases']; first=cases[0]
    row.update(source_binding=first['source_binding'],section_properties=first['section_properties'],
               strong_symmetry=first['strong_symmetry'],actions=first['actions'],
               load_reduction=first['load_reduction'],
               primary_torque_by_action=first['primary_torque_by_action'])
    keys=('status','elastic_reference_eligible','physical_span_mm','Ly_used_mm','Lz_used_mm',
          'kz','kw','Me_Nmm','maximum_reference_moment_Nmm','lambda_reference','distribution',
          'C1','C2','coefficient_source','snapshot_sha256')
    row['cases']=[{k:c[k] for k in keys} for c in cases]
    return row


def run():
    rows=[]
    for index in registry.new_study_indices():
        d=synthetic(index)
        combo=next(c for c in direct.combinations(d) if c['limit_state']=='ELU')
        acts=direct.actions(combo,roof.geometry(d),include_parallel=True)[0]
        cases=[]
        for ly,lz in [(2050.,2050.),(2050.,4100.),(4100.,2050.),(4100.,4100.)]:
            inputs=lengths.declare(d,Lx_mm=2050.,Ly_mm=ly,Lz_mm=lz,
                origin='Synthetic independent lengths for analytical QA')
            evidence=flt.qualify_family(inputs,acts)
            assert evidence['elastic_reference_eligible']
            assert flt.validate_saved(json.loads(json.dumps(evidence)),inputs,acts)==evidence
            cases.append(evidence)
        assert len({c['maximum_reference_moment_Nmm'] for c in cases})==1
        rows.append(compact_row(dict(catalog_index=index,dimensions_mm={k:d['properties'][k] for k in ('h','bf','lip','t')},
            synthetic_input_fingerprint=own.digest(d),combination=combo,cases=cases)))
    return dict(schema='flt_height_effective_family_qa_v1',synthetic_only=True,
        no_private_project_inputs=True,physical_span_mm=4100.,inclination_deg=5.71,fy_MPa=300.,
        external_gravity_before_projection_N_mm=.5,self_weight='Own-contour mass; PP separately at CG through existing direct convention',
        total_sections=len(rows),cases_per_section=4,computed_elastic_references=sum(len(r['cases']) for r in rows),
        physical_demand_unchanged_in_all_length_variations=True,
        no_member_solver_run=True,normative_global_approval=False,
        limitations=['Documentary approximate elastic references, not certified lower bounds',
            'Only kz=.5/1 and kw .5..1; no interpolation',
            'q+P mixture and arbitrary point positions not qualified',
            'Primary torque is reported, not checked by this scalar Me',
            'NBR/EN resistance consumers must use their own compatible local/distortional kernels'],rows=rows)


if __name__=='__main__':
    target=Path(__file__).with_name('FAMILY66_RESULTS.json')
    result=run();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
