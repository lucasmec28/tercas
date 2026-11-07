"""Synthetic Ue125 plus family-size checks. No project data."""
import copy,json
import pytest
from en_ue_test_helpers import inputs
from tercas import ue_catalog_reference as own,nbr_ue_family_application as app
from tercas import nbr_family_panorama as panorama
from tercas.application import fingerprint
from tercas.resistance_effective_lengths import declare


def source(index=26,Leff=2050.):
    d=inputs(index,angle=5.71,L=4100.)
    d['properties'].update(fy_MPa=300.,fu_MPa=450.);d=own.activate(d)
    d.update(q_uls=.5,q_sls=.2,P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.)
    d=declare(d,Lx_mm=Leff,Ly_mm=Leff,Lz_mm=Leff,origin='Synthetic declared resistance lengths')
    return own.attach_source(dict(input_data=d,input_fingerprint=fingerprint(d),schema='NBR14762_one_span_v1',
        model_domain_evidence=dict(status='fixed_model_domain',conflict=False)))


@pytest.mark.parametrize('index',[0,19,26,53,79,82])
def test_current_height_and_biaxial_consumed_for_positive_weak_domain(index):
    r=app.attach(source(index));ev=app.preserved(json.loads(json.dumps(r)));row=ev['records'][0]
    assert row['height_source']['elastic_reference_eligible']
    h=next(c for c in row['components'] if c['method']=='FLT_height_effective_reference')
    assert h['index'] is not None and h['approximate']
    b=row['member_interaction'];assert b['status']=='component_computed'
    assert b['arithmetic']['active_signed_branches']['My_positive']
    assert not b['arithmetic']['active_signed_branches']['My_negative']
    checks,binding=panorama.apply(r,[])
    r['global_verification']=dict(checks=checks,**{panorama.BINDING:binding})
    panorama.validate_saved(r)
    assert not binding['whole_member_approved']


def test_declared_lengths_change_resistance_not_physical_actions():
    a=app.attach(source())[app.FIELD]['records'][0]
    b=app.attach(source(Leff=4100.))[app.FIELD]['records'][0]
    assert a['actions']==b['actions'] and a['combination']==b['combination']
    assert [p['demand'] for p in a['components']]==[p['demand'] for p in b['components']]
    assert a['height_source']['Me_Nmm']>b['height_source']['Me_Nmm']
    assert a['height_capacity']['MRd_Nmm']>b['height_capacity']['MRd_Nmm']
    assert a['height_source']['physical_span_mm']==b['height_source']['physical_span_mm']==4100.


@pytest.mark.parametrize('mutation',['height','capacity','maximum','selection','source'])
def test_new_source_and_interaction_replay_rejects_corruption(mutation):
    r=app.attach(source());row=r[app.FIELD]['records'][0]
    if mutation=='height':row['height_source']['Me_Nmm']*=100
    elif mutation=='capacity':row['height_capacity']['MRd_Nmm']*=100
    elif mutation=='maximum':row['member_interaction']['arithmetic']['governing']['index_upper']=0.
    elif mutation=='selection':row['member_interaction']['selection']['Mx_positive']['selected'].pop()
    else:row['member_interaction']['source_binding']['material']['fy_MPa']=350.
    with pytest.raises(ValueError):app.preserved(r)


def test_v1_height_and_pending_biaxial_are_not_promoted():
    from tercas import nbr_ue_family_application_v1 as v1
    r=v1.attach(source());before=copy.deepcopy(r)
    assert app.preserved(r)==r[app.FIELD]
    row=r[app.FIELD]['records'][0]
    assert row['height_source']['status']=='separate_existing_height_route'
    assert 'member_interaction' not in row and r==before
    assert panorama.apply(r,[])==([],None)


def test_height_resistance_method_gap_does_not_drop_other_components(monkeypatch):
    from tercas import nbr_ue_family as provider
    from tercas.nbr_ue_family_expansion import OutsideMethod
    def outside(*args,**kwargs):raise OutsideMethod('Synthetic unsupported effective section')
    monkeypatch.setattr(provider,'strong_capacity_at_me',outside)
    r=app.attach(source());row=r[app.FIELD]['records'][0]
    assert row['height_source']['elastic_reference_eligible']
    assert row['height_capacity']['status']=='outside_height_resistance_method'
    assert next(p for p in row['components'] if p['method']=='local' and p['route']=='own_rounded_contour')['index'] is not None
    assert row['member_interaction']['status']=='pending_actual_member_components'
