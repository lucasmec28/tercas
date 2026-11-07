"""Fresh synthetic family workflows, with partial coverage reported honestly.

Run only after freezing the production source. No private project is used.
All statuses are results for this declared scenario, not universal approvals.
"""
import hashlib
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))
from en_ue_test_helpers import inputs,run
from tercas import pierin_ue_registry as registry,ue_catalog_reference as own
from tercas import isolated_en_ue_family_application as en
from tercas import nbr_ue_family_application as nbr
from tercas import isolated_service_component as service
from tercas.resistance_effective_lengths import declare


def main():
    root=Path(__file__).resolve().parents[2]
    output=Path(__file__).with_name('family_application_matrix_current.json')
    files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted((root/'tercas').rglob('*.py'))}
    out=dict(kind='synthetic_application_workflow_matrix',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        production_file_sha256=files,
        scope='66 documentary-complete own Ue, fy300, L4100, slope5.71, Ly=Lz2050, signed PP at CG, external q at top; one ELU and one ELS per profile. Not all load/material combinations.',
        family=registry.new_study_indices(),records=[],complete=False,whole_member_approved=False)
    def save():output.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    save()
    for index in out['family']:
        d=inputs(index,angle=5.71,L=4100.)
        d['properties'].update(fy_MPa=300.,fu_MPa=450.)
        d=own.activate(d)
        d=declare(d,Lx_mm=2050.,Ly_mm=2050.,Lz_mm=2050.,origin='Synthetic resistance lengths; no intermediate supports')
        d=en.activate(d,model_origin='Synthetic R11 complete-family application audit')
        c=service.blank_choice();c.update(point_xy_from_CG_mm=[0.,d['properties']['h']/2],projection_xy=[0.,-1.],
            point_label='Top-flange point at gross CG x',direction_label='Local normal downward',reference_declared=True,
            criterion='declared_limit',limit_mm=20.,criterion_origin='Synthetic comparison of total selected ELS, no camber',
            model_origin='Synthetic isolated linear member',nominal_intact_section_declared=True)
        d[service.CHOICE]=c
        t=time.perf_counter();r=run(d);ee=en.preserved(r);ne=nbr.preserved(r);se=service.saved(r)
        if os.environ.get('SAVE_SYNTHETIC_RESULTS_TO'):
            folder=Path(os.environ['SAVE_SYNTHETIC_RESULTS_TO']);folder.mkdir(parents=True,exist_ok=True)
            raw=json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
            (folder/(str(index)+'.json.gz')).write_bytes(gzip.compress(raw,mtime=0))
        assert ee['ELU_cases']==1 and len(ne['records'])==1
        assert not r['whole_member_approved'] and not r['global_verification']['whole_member_approved']
        assert len(r['torsion_evidence']['records'])==2
        nr=ne['records'][0];sr=se['records'][0]
        row=dict(index=index,fy_MPa=300.,elapsed_seconds=time.perf_counter()-t,
            EN={k:ee[k] for k in ('stress_computed_cases','shear_computed_cases','mv_computed_cases','partial_cases','pending_demand_cases')},
            EN_records=[dict(status=x['status'],reason=x['reason'],component_status=(x.get('check') or {}).get('component_status'),schema=(x.get('check') or {}).get('schema'),supplement_eligible=((x.get('check') or {}).get('concurrent_shear_lag_supplement') or {}).get('eligible')) for x in ee['records']],
            NBR={c['method']:dict(status=c['status'],index=c['index'],diagnostic_index=c.get('unqualified_diagnostic_index'),reason=c['reason'])
                 for c in nr['components'] if c['route']=='own_rounded_contour'},
            NBR_biaxial=dict(status=nr['member_interaction']['status'],criterion_status=nr['member_interaction']['criterion_status'],missing=nr['member_interaction']['missing']),
            NBR_MV=dict(status=nr['strong_web_MV']['status'],criterion_status=nr['strong_web_MV']['criterion_status'],missing=nr['strong_web_MV']['missing']),
            NBR_shear_lag={a:v['status'] for a,v in nr['shear_lag_applicability']['axes'].items()},
            service=dict(computed_cases=se['computed_cases'],pending_cases=se['pending_cases'],status=sr['status'],reason=sr['reason'],
                criterion_status=(sr['comparison'] or {}).get('criterion_status'),index_upper=(sr['comparison'] or {}).get('index_upper')),
            listed_checks=[dict(id=x['id'],status=x['status'],index=x['index'],reason=x['reason']) for x in r['global_verification']['checks']],
            global_approved=False)
        out['records'].append(row);save()
        print(json.dumps({k:row[k] for k in ('index','elapsed_seconds','EN','NBR_biaxial','service')},ensure_ascii=False),flush=True)
    assert len(out['records'])==66 and len({r['index'] for r in out['records']})==66
    assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==sha for name,sha in files.items())
    out['complete']=True
    out['counts']=dict(profiles=66,
        EN_stress=sum(r['EN']['stress_computed_cases']==1 for r in out['records']),
        EN_shear=sum(r['EN']['shear_computed_cases']==1 for r in out['records']),
        EN_new_concurrent=sum(r['EN_records'][0]['schema']=='EN_Ue_family_concurrent_section_components_v4_candidate' for r in out['records']),
        EN_preserved_v3=sum(r['EN_records'][0]['schema']=='EN_Ue_family_concurrent_section_components_v3' for r in out['records']),
        EN_MV=sum(r['EN']['mv_computed_cases']==1 for r in out['records']),
        NBR_biaxial_computed=sum(r['NBR_biaxial']['status']=='component_computed' for r in out['records']),
        service_with_index=sum(r['service']['index_upper'] is not None for r in out['records']))
    save();print(json.dumps(out['counts']),flush=True)


if __name__=='__main__':main()
