import copy
import math
import pytest
from tercas import nbr_ue_family as family
from tercas import pierin_ue_registry as registry
from tercas import ue_catalog_nbr_distortional as legacy_d
from tercas import ue_catalog_nbr_weak_mle as legacy_w
from tercas import ue_catalog_nbr_weak_annex_e as legacy_e

def test_legacy_witness_and_no_pin_promotion():
    result=family.assess(26,L_mm=6000)
    d=result['strong']['distortional']['elastic']
    for key in ('Mdist_Nmm','Fcrd_MPa','Lcrd_mm'):
        assert d[key]==pytest.approx(legacy_d._elastic()[key],rel=2e-12)
    for sign in ('positive','negative'):
        weak=result['weak'][sign];old=legacy_w._certificate({})['local_by_sign'][sign]
        assert weak['local']['MRd_Nmm']==pytest.approx(old['MRd_local_Nmm'],rel=2e-12)
    for key in ('j_mm','r0_squared_mm2','integral_x3_mm5','integral_xy2_mm5'):
        assert result['section_constants'][key]==pytest.approx(legacy_e.section_constants()[key],rel=2e-12)
    assert not result['whole_member_approved']
    assert result['weak']['negative']['pure_weak_reference_MRd_Nmm'] is None

@pytest.mark.parametrize('index',registry.new_study_indices())
@pytest.mark.parametrize('fy',[250.,300.])
def test_every_complete_row_reports_each_branch(index,fy):
    result=family.assess(index,L_mm=6000,material=dict(family.DEFAULT_MATERIAL,fy_MPa=fy))
    assert result['catalog_index']==index
    assert result['pierin_criticals_transferred'] is False
    assert set(result['strong'])=={'local','distortional','FLT_reference'}
    assert set(result['weak'])=={'positive','negative'}
    for branch in result['strong'].values():
        if not branch['eligible']:assert branch['reason']
        if branch.get('MRd_Nmm') is not None:assert math.isfinite(branch['MRd_Nmm']) and branch['MRd_Nmm']>0
    assert not result['actual_load_capacity_qualified']
    assert not result['whole_member_approved']

def test_lengths_material_and_height_are_independent():
    a=family.assess(26,L_mm=6000)
    b=family.assess(26,L_mm=6000,lengths=dict(Lx_mm=3000,Ly_mm=4000,Lz_mm=5000,origin='test declaration'),load_position='destabilizing')
    assert a['strong']['local']==b['strong']['local']
    assert a['strong']['distortional']==b['strong']['distortional']
    assert a['strong']['FLT_reference']['Me_reference_Nmm']!=b['strong']['FLT_reference']['Me_reference_Nmm']
    assert not b['strong']['FLT_reference']['actual_position_supported']
    assert not b['strong']['FLT_reference']['height_effect_included']
    c=family.assess(26,L_mm=6000,material=dict(family.DEFAULT_MATERIAL,fy_MPa=250))
    assert a['strong']['distortional']['elastic']==c['strong']['distortional']['elastic']
    assert a['strong']['local']['Ml_Nmm']==c['strong']['local']['Ml_Nmm']
    assert a['strong']['local']['MRd_Nmm']!=c['strong']['local']['MRd_Nmm']

def test_short_member_and_invalid_inputs():
    a=family.assess(26,L_mm=10)
    assert a['strong']['local']['eligible']
    assert not a['strong']['distortional']['eligible']
    for value in (True,float('nan'),0,-1):
        with pytest.raises(ValueError):family.assess(26,L_mm=value)
    with pytest.raises(ValueError):family.assess(26,L_mm=6000,lengths={'Lx_mm':1})
    incomplete=registry.inventory()['incomplete'][0]['catalog_index']
    with pytest.raises(ValueError):family.assess(incomplete,L_mm=6000)

def test_saved_replay_rejects_rehashed_edit():
    a=family.assess(26,L_mm=6000)
    assert family.validate_saved(a,index=26,L_mm=6000)==a
    bad=copy.deepcopy(a);bad['strong']['local']['MRd_Nmm']*=2
    bad['snapshot_sha256']=family.digest({k:v for k,v in bad.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):family.validate_saved(bad,index=26,L_mm=6000)

def test_boundary_classes_and_input_rejection():
    from tercas.core.local_table12 import local_critical
    assert local_critical('Ue',100.,20.,1.,1000.,D_mm=10.)['Ml_Nmm']>0
    with pytest.raises(ValueError):local_critical('Ue',100.,19.99,1.,1000.,D_mm=10.)
    with pytest.raises(ValueError):family.material_values(dict(family.DEFAULT_MATERIAL,fy_MPa=True))
    with pytest.raises(ValueError):family.assess(True,L_mm=6000)
    p=dict(h=125,bf=50,lip=17,t=2,ri_mm=2)
    prepared=family.prepare(26)['section']
    with pytest.raises(family.OutsideMethod):family.weak_kernel(p,prepared['properties'],dict(family.DEFAULT_MATERIAL,fy_MPa=1500))

@pytest.mark.parametrize('index',registry.new_study_indices())
def test_tabulated_reference_all_complete_rows_without_table12_gate(index):
    out=family.tabulated_reference(index)
    assert out['strong']['local']['eligible']
    assert out['strong']['distortional']['eligible']
    assert out['local_distortional_reference_min_Nmm']>0
    assert not out['own_contour_used']
    assert not out['elastic_values_rescaled']
    assert not out['weak']['eligible']
    assert out['source_G_MPa'] is None
    assert out['source_nu'] is None
    assert not out['strong']['local']['identical_geometric_models_proven']

def test_tabulated_material_fy_does_not_rescale_elastic_and_E_change_blocks():
    a=family.tabulated_reference(26)
    b=family.tabulated_reference(26,material=dict(family.DEFAULT_MATERIAL,fy_MPa=250))
    assert a['published_criticals']==b['published_criticals']
    assert a['strong']['local']['MRd_Nmm']!=b['strong']['local']['MRd_Nmm']
    c=family.tabulated_reference(26,material=dict(family.DEFAULT_MATERIAL,E_MPa=210000))
    assert not c['strong']['local']['eligible']
    assert c['local_distortional_reference_min_Nmm'] is None

def test_explicit_fresh_attachment_preserves_legacy_and_separates_sources():
    row=registry.select_new_study(26,include_routes=False)
    data=dict(catalog_index=26,L_mm=6000,properties=dict(row['dimensions_mm'],E_MPa=200000.,G_MPa=77000.,fy_MPa=300.))
    result=dict(input_data=data,legacy={'MRd_Nmm':123.})
    assert family.attach(result) is result
    fresh=family.attach(result,fresh_calculation=True)
    assert family.FIELD not in result
    assert fresh['legacy']==result['legacy']
    assert fresh[family.FIELD]['routes_must_not_be_mixed']
    assert not fresh[family.FIELD]['roof_height_effect_qualified']
    wrong=copy.deepcopy(result);wrong['input_data']['properties']['t']=99
    with pytest.raises(ValueError):family.attach(wrong,fresh_calculation=True)
