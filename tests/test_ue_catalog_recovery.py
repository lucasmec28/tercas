"""Fresh reconstruction QA, never a reuse of the lost candidate's receipt."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess

import pytest
from tercas import catalog_torsion_section as geo,ue_catalog_reference as own
from tercas import direct_self_weight as pp,roof_top_load as roof,direct_torsion
from tercas import aisi_torsion_component as aisi
from tercas.application import defaults,calculate,build_spec,fingerprint
from tercas.catalogs import entries
from tercas.study_completion import complete_result
from tercas.torsion_vlasov.section import from_polyline,load_profile,section_demands

UE=[i for i,e in enumerate(entries()) if e['family']=='Ue']


def inputs(index=0,**changes):
    d=pp.activate(defaults(index));d['roof_top_load']=roof.choice()
    d.update(q_uls=.1,q_sls=.06,**changes)
    return own.activate(d)


@pytest.mark.parametrize('index',UE)
def test_source_properties_and_material_are_coherent(index):
    original=pp.activate(defaults(index));original['roof_top_load']=roof.choice()
    d=own.activate(original);packet=geo.prepare(index);s=packet['section'];p=s['properties']
    assert d['properties']['A_cm2']*100==pytest.approx(p['A_mm2'])
    assert d['properties']['mass_kg_m']==pytest.approx(p['A_mm2']*7850e-6)
    assert d['properties']['Ix_cm4']*1e4==pytest.approx(p['Ix_strong_mm4'])
    assert d['properties']['Iy_cm4']*1e4==pytest.approx(p['Iy_weak_mm4'])
    assert d['properties']['J_mm4']==p['J_mm4'] and d['properties']['Cw_mm6']==p['Cw_mm6']
    assert own.material(d)==own.material(original)
    assert own.section_for(d)==s
    assert own.source_binding(d)['nodes_sha256']==s['nodes_sha256']
    assert d[own.FIELD]['superseded_section_inputs']['properties']==original['properties']
    assert own.activate(d)[own.FIELD]['superseded_section_inputs']==d[own.FIELD]['superseded_section_inputs']
    assert d['Ml_Nmm'] is None and d['Mdist_Nmm'] is None and d['weak_axis']=={}
    assert original['properties']==defaults(index)['properties']


@pytest.mark.parametrize('a,b,t',[(100.,50.,2.),(75.,30.,1.5),(250.,70.,4.)])
def test_independent_sharp_channel_integrals(a,b,t):
    s=from_polyline(nodes_xy_mm=[[b,0.],[0.,0.],[0.,a],[b,a]],thickness_mm=t,profile_id='analytic',source='Sharp midsurface U, independent closed form')
    p=s['properties'];A=t*(a+2*b);cg=b*b/(a+2*b);e=3*b*b/(a+6*b)
    assert p['A_mm2']==pytest.approx(A)
    assert p['centroid_xy_mm']==pytest.approx([cg,a/2])
    assert p['shear_center_xy_mm']==pytest.approx([-e,a/2])
    assert p['Ix_strong_mm4']==pytest.approx(t*a*a*(a+6*b)/12)
    assert p['Iy_weak_mm4']==pytest.approx(2*t*b**3/3-A*cg**2)
    assert p['J_mm4']==pytest.approx(t**3*(a+2*b)/3)
    assert p['Cw_mm6']==pytest.approx(t*b**3*a*a*(2*a+3*b)/(12*(a+6*b)))
    assert s['omega_nodes_mm2']==pytest.approx([a*(b-e)/2,-a*e/2,a*e/2,-a*(b-e)/2])


def test_seven_frozen_sections_bit_identical_to_published_base(tmp_path):
    path=tmp_path/'original_section.py'
    path.write_bytes(subprocess.check_output(['git','show','89785b61c2b01a7d5ec350b00c10fc5e9bc8e90d:tercas/torsion_vlasov/section.py']))
    spec=importlib.util.spec_from_file_location('tercas.torsion_vlasov.original_section',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    files=sorted((Path(__file__).parents[1]/'tercas/data/torsion_profiles').glob('*.json'))
    assert len(files)==7
    for file in files:assert load_profile(file)==module.load_profile(file)


@pytest.mark.parametrize('index',UE)
def test_resultants_recovered_from_same_contour(index):
    s=geo.prepare(index)['section'];v=dict(N_N=10.,Mx_Nmm=12000.,My_Nmm=-3000.,Vx_N=5.,Vy_N=-7.,Tsv_Nmm=40.,Tw_Nmm=30.,B_Nmm2=30000.)
    r=section_demands(s,**v)
    assert r['recovered_normal_N_Mx_My_B']==pytest.approx([10.,12000.,-3000.,30000.],rel=3e-11,abs=1e-7)
    assert r['recovered_flow_Vx_Vy_Tw']==pytest.approx([5.,-7.,30.],rel=3e-11,abs=1e-7)


@pytest.mark.parametrize('mutation',['mass','Ix','material','marker','catalog','old_reference','domain','network','girt'])
def test_no_stale_or_mixed_reference(mutation):
    d=inputs()
    if mutation=='mass':d['properties']['mass_kg_m']*=2
    elif mutation=='Ix':d['properties']['Ix_cm4']*=2
    elif mutation=='material':d['properties']['E_MPa']*=1.1
    elif mutation=='marker':d[own.FIELD]['nodes_sha256']='0'*64
    elif mutation=='catalog':d['catalog_index']=1
    elif mutation=='old_reference':d['ue_reference']={}
    elif mutation=='domain':d['model_domain']='other'
    elif mutation=='network':d['three_girt_model']=[]
    elif mutation=='girt':d['member_application']='wall_girt'
    with pytest.raises(ValueError):build_spec(d)


def test_no_legacy_migration_or_plain_U_activation():
    d=defaults(0);d['roof_top_load']=roof.choice()
    with pytest.raises(ValueError):own.activate(d)
    d=pp.activate(defaults(next(i for i,e in enumerate(entries()) if e['family']=='U')));d['roof_top_load']=roof.choice()
    with pytest.raises(ValueError,match='exclusiva'):own.activate(d)
    assert own.validate(defaults(0)) is None


def test_editing_critical_text_does_not_import_old_denominators():
    d=inputs();d.update(Ml_Nmm=1e12,Mdist_Nmm=1e12,critical_origin='independent')
    spec=build_spec(d)
    assert spec['Ml']['value'] is None and spec['Mdist']['value'] is None
    from tercas.weak_axis import capacities
    assert all(r['status']=='not_evaluated' for r in capacities(d,'Ue').values())


@pytest.mark.parametrize('index',UE)
def test_complete_direct_flow_all_Ue_and_independent_uniform_bimoment(index):
    d=inputs(index);before=copy.deepcopy(d);r=complete_result(calculate(d));e=aisi.preserved(r)
    assert d==before and r['input_data']==before
    assert r['torsion_evidence']['computed_cases']==2
    assert e['G81_computed_cases']==1 and e['H4_computed_cases']==0
    assert own.preserved(r)['source_binding']==own.source_binding(d)
    p=own.section_for(d)['properties'];cg=p['centroid_xy_mm'];sc=p['shear_center_xy_mm']
    w=1.25*d['properties']['mass_kg_m']*9.80665/1000
    torque=-(cg[0]-sc[0])*w-(0.-sc[0])*.1
    k=math.sqrt(.9*78000*p['J_mm4']/(.9*203000*p['Cw_mm6']))
    exact=torque/k**2*(1-1/math.cosh(k*d['L_mm']/2))
    assert e['records'][0]['G81']['B_Nmm2']==pytest.approx(exact,rel=3e-5,abs=1e-8)
    assert not r['whole_member_approved'] and not e['NBR_capacities_used']
    assert 'torsion_warping' in r['global_verification']['pending_ids']
    assert aisi.preserved(json.loads(json.dumps(r,allow_nan=False)))==e


@pytest.mark.parametrize('angle,line',[(-12.,'web_midplane'),(12.,'flange_midwidth')])
def test_PP_CG_external_top_signed_vectors_independent_cross_product(angle,line):
    from tercas.inclination_adapter import configuration
    d=inputs(40);d['roof_top_load']=roof.choice(line)
    # Use the app's versioned inclination rather than rotating external actions.
    from test_direct_torsion import inputs as legacy_inputs
    d['inclination']=legacy_inputs(angle=angle)['inclination']
    d.update(q_uls=-.12,P_uls=17.,q_parallel_uls=.03,P_parallel_uls=-7.)
    r=complete_result(calculate(d));a=r['torsion_evidence']['records'][0]['analysis'];s=a['section']['properties']
    cg=s['centroid_xy_mm'];sc=s['shear_center_xy_mm'];p=d['properties'];top=[0. if line=='web_midplane' else (p['bf']-p['t'])/2,p['h']-p['t']/2]
    weight=1.25*p['mass_kg_m']*9.80665/1000
    expected={'PP':([weight*math.sin(math.radians(angle)),-weight*math.cos(math.radians(angle))],cg),'EXTERNAL':([.03,.12],top),'P':([-7.,-17.],top)}
    for load in a['loads']:
        f,xy=expected[load['name']];key='force_xy_N' if load['kind']=='point' else 'q_xy_N_mm';tk='torque_SC_Nmm' if load['kind']=='point' else 'torque_SC_N'
        assert load[key]==pytest.approx(f) and load['application_xy_mm']==pytest.approx(xy)
        assert load[tk]==pytest.approx((xy[0]-sc[0])*f[1]-(xy[1]-sc[1])*f[0])


def test_saved_readers_do_not_reopen_sources_or_solve(monkeypatch):
    from tercas.report import word
    r=complete_result(calculate(inputs()));before=copy.deepcopy(r)
    def fail(*a,**k):raise AssertionError('historical read must not reopen or solve')
    monkeypatch.setattr(own,'_source',fail);monkeypatch.setattr(direct_torsion,'solve_member',fail)
    monkeypatch.setattr(aisi,'_aisi_demand',fail)
    assert own.preserved(r)
    assert aisi.preserved(r)
    assert word(r)
    assert r==before


def test_rehashed_H4_promotion_rejected():
    r=complete_result(calculate(inputs()));e=r[aisi.FIELD]
    e['H4_computed_cases']=1;e['snapshot_sha256']=aisi.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError,match='H4'):aisi.preserved(r)


def test_selected_geometry_does_not_convert_changed_action_basis_or_inactive_top():
    d=inputs();d.pop(pp.FIELD)
    r=complete_result(calculate(d))
    assert r.get('torsion_evidence',{}).get('computed_cases',0)==0
    assert not r.get('direct_self_weight_evidence')
    d=inputs();d['roof_top_load']['enabled']=False
    r=complete_result(calculate(d))
    assert r.get('torsion_evidence',{}).get('computed_cases',0)==0


def test_area_combinations_PP_and_support_limit_remain_separate():
    from tercas.batch import calculate_batch,area_bundle
    d=defaults(0);d.update(load_mode='area',roof_top_load=roof.choice(),selected_types=['ELU normal'])
    d['area_inputs'].update(permanent_kgf_m2=4.,live_kgf_m2=10.,wind_up_kgf_m2=20.,wind_down_kgf_m2=5.)
    d=own.activate(d);r=complete_result(calculate_batch(d));ev=r['torsion_evidence'];bundle=area_bundle(d)
    assert ev['computed_cases']==len(bundle['combinations'])
    assert [x['combination_id'] for x in ev['records']]==[x['id'] for x in bundle['combinations']]
    assert r['load_bundle']==bundle
    cg=own.section_for(d)['properties']['centroid_xy_mm']
    for record,combo in zip(ev['records'],bundle['combinations']):
        a=record['analysis'];pp_load=[x for x in a['loads'] if x['name']=='PP']
        assert len(pp_load)==1 and pp_load[0]['application_xy_mm']==cg
        if combo.get('point_position')=='support_limit':
            assert a['support_limit_states'][0]['element_index'] is None
    assert aisi.preserved(r)['H4_computed_cases']==0

@pytest.mark.parametrize('nodes',[
    [[True,0],[0,10],[10,10]],
    [[0,float('nan')],[0,10],[10,10]],
    [[0,0],[0,10],[0,0]],
    [[0,0],[0,10],[0,10],[10,10]],
    [[0,0],[10,10],[0,10],[10,0]],
    [[0,0],[0,10],[0,5],[10,5]],
    [['0',0],[0,10],[10,10]],
    [[0,0],[1,0],[2,0]],
])
def test_invalid_open_contours_are_rejected(nodes):
    with pytest.raises(ValueError):from_polyline(nodes_xy_mm=nodes,thickness_mm=1.,profile_id='bad',source='test')


def test_inactive_top_never_reactivates_old_manual_lines_in_area_mode():
    from tercas.torsion_study import blank_choice,attach
    d=defaults(0);d.update(load_mode='area',roof_top_load=roof.choice())
    d=own.activate(d)
    d['roof_top_load']['enabled']=False
    d['torsion_model']=blank_choice()
    d['torsion_model']['load_lines']={'CP':dict(declared=True,xy_from_CG_mm=[90.,90.],origin='stored old manual line')}
    r=attach(dict(input_data=d,input_fingerprint=fingerprint(d),schema='tercas_batch_results_v1',cases=[]))
    assert r['torsion_evidence']['computed_cases']==0
    assert 'Linhas manuais' in r['torsion_evidence']['reason']
    assert d['torsion_model']['load_lines']['CP']['xy_from_CG_mm']==[90.,90.]


def test_new_source_does_not_offer_unintegrated_nominal_detail_or_claim_flexural_capacities():
    from tercas import torsion_material
    from tercas.aisi_torsion_ui import text_lines
    r=complete_result(calculate(inputs()))
    assert torsion_material.available_cases(r)==[]
    assert 'ainda não está integrado' in torsion_material.pending_reason(r)
    text='\n'.join(text_lines(aisi.preserved(r)))
    assert 'Mcre e Ma,piso calculados' not in text
    assert 'capacidades flexionais e H4 pendentes' in text
    assert 'Mcre, Ma,piso e H4 permanecem pendentes' in text


def test_legacy_nominal_case_availability_is_unchanged():
    from tercas.torsion_material import available_cases,pending_reason
    r=dict(input_data={},cases=[dict(combination=dict(id='LEGACY'))],
        torsion_evidence=dict(records=[dict(combination_id='LEGACY',status='elastic_demand_computed',analysis={})]))
    assert available_cases(r)==['LEGACY'] and pending_reason(r) is None
