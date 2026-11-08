"""Synthetic applied-load CT model, with old inputs retained as replay oracles."""
import copy
import json
import pytest
from tercas import load_application_policy as policy
from tercas import nbr_ue_family_application as nbr, ue_catalog_reference as own
from tercas import direct_roof_separated as separated, direct_torsion, direct_self_weight
from tercas.application import fingerprint
from tercas.pierin_ue_registry import new_study_indices
from test_nbr_family_height_integration import source as roof_source
from test_girt_nbr_family_66_scalar import scalar_source as girt_source


def marked(source):
    out=copy.deepcopy(source);out['input_data']=policy.adopt(out['input_data'])
    out['input_fingerprint']=fingerprint(out['input_data'])
    return own.attach_source(out)


def non_position_actions(actions):
    return [{k:v for k,v in a.items() if k not in ('height_above_SC_mm','x_from_SC_mm','load_line_source')}
            for a in actions]


def component(row,name):
    return next(p for p in row['components'] if p['route']=='own_rounded_contour' and p['method']==name)


@pytest.mark.parametrize('index',new_study_indices())
@pytest.mark.parametrize('source',[roof_source,girt_source],ids=['roof','girt'])
def test_all66_load_arms_and_nbr_me_without_height_solver(index,source,monkeypatch):
    from tercas import flt_height_effective,flt_height_nbr_floor,ltb_load_height
    def forbidden(*a,**kw):pytest.fail('Current CT actions must use existing NBR expressions, not height/Ritz/floors')
    monkeypatch.setattr(flt_height_effective,'qualify_family_fresh',forbidden)
    monkeypatch.setattr(flt_height_nbr_floor,'qualify_family',forbidden)
    monkeypatch.setattr(ltb_load_height,'refined',forbidden)
    old=source(index);before=copy.deepcopy(old);r=marked(old);out=nbr.attach(r);ev=out[nbr.FIELD]
    assert old==before and ev['schema'] in policy.NBR_SCHEMAS
    assert ev['resistance_lengths'] and ev['physical_span_mm']==r['input_data']['L_mm']
    for row in ev['records']:
        assert all(a['height_above_SC_mm']==a['x_from_SC_mm']==0. for a in row['actions'])
        assert all(p['classification']=='shear_center' for p in row['load_position_by_axis'].values())
        assert row['height_energy_floor'] is None and not row['height_source']['elastic_reference_eligible']
        assert component(row,'FLT_reference')['index'] is not None
        for sign in ('positive','negative'):
            p=component(row,'weak_'+sign+'_FLT_reference')
            if p['demand']['Msd_Nmm']>0:assert p['index'] is not None
    assert nbr.preserved(json.loads(json.dumps(out)))==ev


@pytest.mark.parametrize('source',[roof_source,girt_source])
def test_external_pp_and_eccentric_P_force_and_flexure_unchanged(source):
    old=source(26);d=old['input_data'];d.update(P_uls=173.,P_parallel_uls=-29.,x_uls=1537.)
    old['input_fingerprint']=fingerprint(d);old=own.attach_source(old)
    new=marked(old);nd=new['input_data']
    before=copy.deepcopy(old)
    from tercas import roof_top_load,wall_girt_isolated
    geo_old=wall_girt_isolated.geometry(d) if d.get('member_application')=='wall_girt' else roof_top_load.geometry(d)
    geo_new=policy.geometry(nd)
    oc=separated.combinations(d)[0];nc=separated.combinations(nd)[0]
    oa=direct_torsion.actions(oc,geo_old);na=direct_torsion.actions(nc,geo_new)
    assert len(oa)==len(na) and {'EXTERNAL','PP','P'}=={a['name'] for a in na}
    for a,b in zip(oa,na):
        assert {k:v for k,v in a.items() if k not in ('application_xy_mm','origin')}=={k:v for k,v in b.items() if k not in ('application_xy_mm','origin')}
        assert b['application_xy_mm']==geo_new['SC_xy_mm']
        f=b['q_xy_N_mm' if b['kind']=='uniform' else 'force_xy_N']
        arm=[b['application_xy_mm'][j]-geo_new['SC_xy_mm'][j] for j in (0,1)]
        assert arm[0]*f[1]-arm[1]*f[0]==0.
    assert direct_self_weight.evidence(d)['states']==direct_self_weight.evidence(nd)['states']
    assert [v['factor'] for v in direct_self_weight.evidence(nd)['states'].values()]==[1.25,1.]
    old_ev=nbr.attach(old)[nbr.FIELD];new_ev=nbr.attach(new)[nbr.FIELD]
    assert non_position_actions(old_ev['records'][0]['actions'])==non_position_actions(new_ev['records'][0]['actions'])
    old_demands={p['method']:p['demand'] for p in old_ev['records'][0]['components']}
    assert all(old_demands[p['method']]==p['demand'] for p in new_ev['records'][0]['components'])
    assert old==before


def test_lengths_change_capacity_not_actions_or_supports():
    a=nbr.attach(marked(roof_source(26,Leff=2050.)))[nbr.FIELD]
    b=nbr.attach(marked(roof_source(26,Leff=4100.)))[nbr.FIELD]
    ar=a['records'][0];br=b['records'][0]
    assert ar['actions']==br['actions'] and ar['combination']==br['combination']
    assert component(ar,'FLT_reference')['capacity_Nmm']>component(br,'FLT_reference')['capacity_Nmm']
    assert [p['demand'] for p in ar['components']]==[p['demand'] for p in br['components']]


def test_new_contour_does_not_require_inactive_top_choice():
    from tercas.application import defaults
    d=policy.adopt(direct_self_weight.activate(defaults(0)))
    d.pop('roof_top_load',None)
    assert own.validate(own.activate(d))


@pytest.mark.parametrize('factory',[lambda:__import__('tercas.ue_reference',fromlist=['load_reference']).load_reference()]+[
    lambda t=t:__import__('tercas.ue_family_reference',fromlist=['load_reference']).load_reference(t) for t in (1.5,2.,2.25,2.65,3.,3.35)])
def test_seven_frozen_sources_accept_new_load_model_without_changing_sources(factory):
    from tercas import ue_reference,ue_family_reference
    d=direct_self_weight.activate(factory());d['load_mode']='direct';new=policy.for_calculation(d)
    module=ue_family_reference if ue_family_reference.claims_reference(d) else ue_reference
    assert policy.active(new) and module.assess(new)['calculable']
    assert module.evidence(d)['global_criticals']==module.evidence(new)['global_criticals']
    c=separated.combinations(new)[0];a=direct_torsion.actions(c,policy.geometry(new))
    assert all(x['application_xy_mm']==policy.geometry(new)['SC_xy_mm'] for x in a)
    assert policy.FIELD not in d


def test_historical_application_and_unknown_marker_fail_closed(monkeypatch):
    from tercas import nbr_family_validation_cache as cache
    r=nbr.attach(roof_source(0));before=copy.deepcopy(r);cache.clear()
    assert nbr.preserved(json.loads(json.dumps(r)))==r[nbr.FIELD] and r==before
    assert r[nbr.FIELD]['schema']==nbr.SCHEMA and policy.FIELD not in r['input_data']
    bad=copy.deepcopy(r['input_data']);bad[policy.FIELD]='unknown'
    with pytest.raises(ValueError):policy.for_calculation(bad)


def test_network_forces_preserved_and_torque_recomputed_at_CT():
    from test_three_girt_system import ready
    from tercas.three_girt_application import configuration,load_cases,readiness
    old=ready();old['three_girt_model']['sc_z_mm']=8.
    new=policy.adopt(old);new['three_girt_model']['load_line_declared']=False
    c=configuration(new);a,_=load_cases(old,configuration(old));b,_=load_cases(new,c)
    assert not readiness(new,c)
    for old_case,new_case in zip(a,b):
        for oa,na in zip(old_case['loads'],new_case['loads']):
            assert (oa['q_y_N_mm'],oa['q_z_N_mm'])==(na['q_y_N_mm'],na['q_z_N_mm'])
            assert na['distributed_torque_CG_N']-c['sc_y_mm']*na['q_z_N_mm']+c['sc_z_mm']*na['q_y_N_mm']==pytest.approx(0.,abs=1e-15)
            assert all(x['y_from_CG_mm']==c['sc_y_mm'] and x['z_from_CG_mm']==c['sc_z_mm'] for x in na['components'])
    assert new['three_girt_model']['connection_offsets']==old['three_girt_model']['connection_offsets']
