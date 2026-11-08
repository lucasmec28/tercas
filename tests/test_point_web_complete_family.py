"""Every documentary-complete Ue: synthetic finite contact, no member solve."""
import copy,json
import pytest
from tercas.pierin_ue_registry import new_study_indices
from tercas.catalogs import catalog_entry
from tercas.application import defaults,build_spec,fingerprint
from tercas.inclination_adapter import direct_evidence
from tercas.point_web import application as a
INDICES=new_study_indices()
assert len(INDICES)==66

@pytest.mark.parametrize('index',INDICES)
@pytest.mark.parametrize('fy',[250.,300.])
def test_complete_family_exact_source_contact_and_saved_replay(index,fy):
    d=defaults(index);entry=catalog_entry(index)
    d['properties']['fy_MPa']=fy
    d.update(L_mm=6000.,x_uls=3000.,P_uls=1000.,P_parallel_uls=150.,q_uls=.1)
    r=dict(schema='NBR14762_one_span_v1',input_data=d,input_fingerprint=fingerprint(d),
        input_snapshot=build_spec(d),inclination_evidence=direct_evidence(d),NBR_branches={})
    cfg=a.reference_configuration(r)
    detail=cfg['details']['DIRECT_ELU']
    detail.update(origin='Synthetic centered finite contact for family coverage',c_mm=20.,
        physical_ends_match_span=True,connected=False,no_opposite_force=True,
        normal_compressive_sign=1,loaded_flange_orientation='Declared loaded flange')
    before=copy.deepcopy((r,cfg));out=a.calculate(r,cfg)
    assert (r,cfg)==before
    local=out['rows'][0]['local']
    assert local['status']=='computed'
    assert local['FRd_N']>0 and local['index']==1000./local['FRd_N']
    assert local['domain']['H_external_mm']==entry['dimensions_mm']['h']
    assert local['domain']['t_mm']==entry['dimensions_mm']['t']
    assert local['domain']['ri_mm']==entry['published_properties']['ri_mm']
    assert local['domain']['fy_MPa']==fy
    assert local['domain']['table_location']=='internal'
    assert local['actions']['parallel_N']==150.
    assert all(local[k] is False and out[k] is False for k in a.FLAGS)
    assert a.saved_assessment(r,json.loads(json.dumps(out)))==out
