"""Synthetic local adapter tests, no member solver or private project data."""
import copy
import json
import pytest
from tercas.point_web import application as a,sources
from tercas.application import defaults,build_spec,fingerprint
from tercas.catalogs import entries
from tercas.load_combinations import COMBINATION_TYPES
from tercas.inclination_adapter import direct_evidence


def fixture(p=1000.,parallel=200.,x=1500.):
    idx=next(i for i,e in enumerate(entries()) if e['family']=='Ue')
    d=defaults(idx);d['properties'].update(ri_mm=d['properties']['t'],fy_MPa=250.)
    d.update(P_uls=p,P_parallel_uls=parallel,q_uls=.3,x_uls=x)
    return dict(schema='NBR14762_one_span_v1',input_data=d,input_fingerprint=fingerprint(d),
        input_snapshot=build_spec(d),inclination_evidence=direct_evidence(d),NBR_branches={})


def config(r):
    cfg=a.reference_configuration(r)
    for d in cfg['details'].values():
        d.update(origin='Synthetic centered contact, no physical verification',c_mm=40.,physical_ends_match_span=True,
                 connected=False,no_opposite_force=True,normal_compressive_sign=1,loaded_flange_orientation='Mesa superior declarada')
    return cfg


def test_finite_mixed_actions_only_normal_and_source_immutable():
    r=fixture();cfg=config(r);old=copy.deepcopy((r,cfg));out=a.calculate(r,cfg)
    assert (r,cfg)==old
    local=out['rows'][0]['local']
    assert local['status']=='computed' and local['actions']['parallel_N']==200.
    assert 'sinais não invertidos' in out['rows'][0]['source_record']['source_axis_convention']
    assert 'negativo das reações' not in out['rows'][0]['source_record']['source_axis_convention']
    assert local['actions']['moment_strong_Nmm']!=0.
    assert all(out[k] is False and local[k] is False for k in a.FLAGS)
    assert local['domain']['table_location']=='internal'
    assert len(out['source_inventory']['support_reactions'])==2
    assert a.saved_assessment(r,json.loads(json.dumps(out)))==out


def test_read_is_saved_only(monkeypatch):
    r=fixture();out=a.calculate(r,config(r))
    def forbidden(*args,**kwargs):raise AssertionError('No extraction or capacity on read')
    monkeypatch.setattr(sources,'extract',forbidden)
    assert a.saved_assessment(r,out)==out

@pytest.mark.parametrize('change',[lambda d:d.update(origin=''),lambda d:d.update(c_mm=None),
    lambda d:d.update(physical_ends_match_span=False),lambda d:d.update(normal_compressive_sign=-1),
    lambda d:d.update(no_opposite_force=False),lambda d:d.update(c_mm=19.)])
def test_missing_domain_pending(change):
    r=fixture();cfg=config(r);change(cfg['details']['DIRECT_ELU'])
    local=a.calculate(r,cfg)['rows'][0]['local']
    assert local['status']=='not_evaluated' and 'index' not in local


def test_end_contact_and_two_flange_classification():
    r=fixture(x=60.);cfg=config(r);d=cfg['details']['DIRECT_ELU']
    d.update(no_opposite_force=False,opposite_clear_distance_mm=0.)
    local=a.calculate(r,cfg)['rows'][0]['local']
    assert local['status']=='computed'
    assert local['domain']['loaded_flange_count']==2 and local['domain']['table_location']=='end'
    d['c_mm']=130.
    assert a.calculate(r,cfg)['rows'][0]['local']['reason_code']=='patch_outside_member'


def test_limit_not_a_finite_contact_or_support_waiver():
    r=fixture();point=sources.extract(r)['points'][0];point.update(mathematical_point_limit=True,x_mm=0.)
    local=a.evaluate(sources.extract(r)['section'],point,config(r)['details']['DIRECT_ELU'])
    assert local['reason_code']=='mathematical_support_limit' and not local['support_reactions_checked']


def test_zero_normal_preserves_parallel_and_supports():
    r=fixture(p=0.);out=a.calculate(r,a.reference_configuration(r))
    assert out['rows'][0]['local']['status']=='not_applicable'
    assert out['rows'][0]['local']['actions']['parallel_N']==200.
    assert len(out['source_inventory']['support_reactions'])==2

@pytest.mark.parametrize('field',['source','point','missing','section','domain','index','approval','local_flag','capacity','scope','local_source'])
def test_saved_tamper_rejected_after_rehash(field):
    r=fixture();out=a.calculate(r,config(r))
    if field=='source':r['input_data']['P_uls']=999.
    elif field=='point':out['source_inventory']['points'][0]['normal_N']=999.
    elif field=='missing':out['source_inventory']['points']=[];out['rows']=[];out['configuration']['details']={}
    elif field=='section':out['source_inventory']['section']['t']=999.
    elif field=='domain':out['rows'][0]['local']['domain']['c_mm']=999.
    elif field=='index':out['rows'][0]['local']['index']=0.
    elif field=='approval':out['global_approval']=True
    elif field=='capacity':
        local=out['rows'][0]['local'];local['FRd_N']*=100.;local['index']=local['force_N']/local['FRd_N'];local['criterion_status']='meets'
    elif field=='scope':out['scope']='Altered scope'
    elif field=='local_source':out['rows'][0]['local']['source']='Other standard'
    else:out['rows'][0]['local']['local_criterion_only']=False
    out['content_sha256']=a.fingerprint({k:v for k,v in out.items() if k!='content_sha256'})
    with pytest.raises(ValueError):a.saved_assessment(r,out)


def test_family_and_application_scope():
    from test_support_web_sources import isolated
    with pytest.raises(ValueError,match='restrita a Ue'):sources.extract(isolated())
    r=fixture();r['input_data']['member_application']='wall_girt'
    with pytest.raises(ValueError,match='terça isolada'):sources.extract(r)


def test_batch_complete_inventory_with_prescribed_support_limit():
    from tercas.batch import area_bundle,case_inputs
    r=fixture();d=r['input_data'];d.update(load_mode='area',selected_types=list(COMBINATION_TYPES))
    d['area_inputs'].update(permanent_kgf_m2=10.,live_kgf_m2=20.)
    bundle=area_bundle(d);cases=[]
    for c in bundle['combinations']:
        current=case_inputs(d,c);ev=direct_evidence(current)['ELU']
        if c.get('point_position')=='support_limit':
            for st in ev['states']:
                for axis in ('normal','parallel'):st[axis]['Rleft_N']+=c['P_vector'][axis]
            ev['P_vector']=copy.deepcopy(c['P_vector'])
        cases.append(dict(combination=c,evidence=dict(inclination=ev,NBR_branches={})))
    r=dict(schema='tercas_batch_results_v1',input_data=d,input_fingerprint=fingerprint(d),
        common_input_snapshot=dict(selected_section=build_spec(case_inputs(d,bundle['combinations'][0]))['selected_section']),load_bundle=bundle,cases=cases)
    out=a.calculate(r,config(r));assert a.saved_assessment(r,out)==out
    elu=[c for c in cases if c['combination']['limit_state']=='ELU']
    assert len(out['rows'])==len(elu) and len(out['source_inventory']['support_reactions'])==2*len(elu)
    limits=[row for row in out['rows'] if row['source_record']['mathematical_point_limit']]
    assert limits and all(row['local']['status']=='not_evaluated' for row in limits)


def test_independent_decimal_golden_internal_ue():
    # Independent D.2 scalar review, not obtained by calling the production frd.
    section=dict(family='Ue',H=154.,t=2.,ri=2.,fy=250.)
    point=dict(normal_N=1000.,parallel_N=200.,moment_strong_Nmm=500000.,
               mathematical_point_limit=False,x_mm=1020.,L_mm=3000.)
    detail=dict(origin='Synthetic independent scalar case',c_mm=40.,physical_ends_match_span=True,
                connected=False,no_opposite_force=True,opposite_clear_distance_mm=None,
                normal_compressive_sign=1,loaded_flange_orientation='Mesa superior declarada')
    local=a.evaluate(section,point,detail)
    assert local['FRd_N']==pytest.approx(13402.111302327401,rel=1e-13)
    assert local['index']==pytest.approx(.07461510932433017,rel=1e-13)
