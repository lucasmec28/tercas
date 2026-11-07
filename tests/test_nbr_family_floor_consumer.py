"""A proven lower resistance is sufficient only; exceeding it is not failure."""
import copy
import json
import pytest
from tercas import nbr_family_member as member, nbr_family_panorama as panorama
from tercas import nbr_ue_family_application as app, ue_catalog_reference as own
from tercas.application import fingerprint
from tercas.resistance_effective_lengths import declare
from test_nbr_family_member import fixture,part
from test_nbr_family_panorama import old
from test_nbr_ue_family_application import source


def fixture_floor(capacity=70.,q=.01):
    row,sources=fixture(0.)
    row['combination']['q_vector']['normal']=q
    for name in ('FLT_reference','FLT_height_effective_reference'):
        part(row,name)['index']=None
    row['components'].append(dict(route='own_rounded_contour',method='FLT_height_energy_floor',
        capacity_Nmm=capacity,index=q*100/8/capacity,status='sufficient_bound_index',
        capacity_lower_bound_only=True,floor_source_sha256='synthetic',approximate=True))
    return row,sources


@pytest.mark.parametrize('q,expected',[(.01,'component_computed'),(100.,'inconclusive_resistance_floor')])
def test_floor_sufficient_or_inconclusive_not_failed(q,expected):
    row,sources=fixture_floor(q=q);result=member.build(row,sources,10.)
    assert result['status']==expected
    assert result['denominator_lower_bound_only']
    assert result['criterion_status']==('meets' if q<1 else None)
    assert result['selection']['Mx_positive']['denominator_lower_bound_only']


@pytest.mark.parametrize('floor',[100.,110.])
def test_exact_tie_or_lower_ordinary_component_keeps_real_minimum(floor):
    row,sources=fixture_floor(floor,q=100.);result=member.build(row,sources,10.)
    assert result['arithmetic']['capacities_Nmm']['Mx_positive']==100.
    assert not result['denominator_lower_bound_only']
    assert result['status']=='component_computed' and result['criterion_status']=='fails'


def test_pure_flt_floor_exceeded_stays_pending_even_if_local_failure_is_real(monkeypatch):
    row,sources=fixture_floor(q=100.);row['member_interaction']=member.build(row,sources,10.)
    # Independent ordinary local criterion may still fail. The floor cannot.
    part(row,'local')['index']=2.
    packet=dict(schema=app.SCHEMA,records=[row],sources=sources,
        resistance_lengths=dict(Lx_mm=10.,Ly_mm=10.,Lz_mm=10.),physical_span_mm=10.)
    result={app.FIELD:packet,'model_domain_evidence':dict(status='fixed_model_domain',conflict=False)}
    monkeypatch.setattr(app,'preserved',lambda r:packet)
    checks,_=panorama.apply(result,old());by={r['id']:r for r in checks}
    assert by['ELU:synthetic:FLT:family']['status']=='pending'
    assert by['ELU:synthetic:biaxial']['status']=='pending'
    assert by['ELU:synthetic:local']['status']=='fails'


@pytest.mark.parametrize('index',[19,26,79,82])
def test_actual_q_P_non_tabulated_lengths_floor_source_replay_and_no_new_support(index):
    result=source(index)
    result['input_data']=declare(result['input_data'],Lx_mm=3000.,Ly_mm=3500.,Lz_mm=4000.,origin='synthetic floor test')
    result['input_fingerprint']=fingerprint(result['input_data']);result=own.attach_source(result)
    before=copy.deepcopy(result);new=app.attach(result);row=new[app.FIELD]['records'][0]
    e=row['height_energy_floor'];assert e is not None and e['resistance_floor_eligible']
    assert e['physical_span_mm']==6000. and not e['physical_supports_created']
    p=part(row,'FLT_height_energy_floor')
    assert p['capacity_lower_bound_only'] and p['floor_source_sha256']==e['snapshot_sha256']
    assert p['capacity_Nmm']==e['MRd_lower_bound_Nmm']
    assert not p['failure_proven']
    assert app.preserved(json.loads(json.dumps(new)))==new[app.FIELD]
    assert result==before
    bad=copy.deepcopy(new);part(bad[app.FIELD]['records'][0],'FLT_height_energy_floor')['capacity_lower_bound_only']=False
    bad[app.FIELD]['snapshot_sha256']=own.digest(bad[app.FIELD])
    with pytest.raises(ValueError):app.preserved(bad)


def test_classical_qualified_position_does_not_gain_floor():
    result=source(q=-1.);result['input_data']['P_uls']=0.
    result['input_fingerprint']=fingerprint(result['input_data']);result=own.attach_source(result)
    row=app.attach(result)[app.FIELD]['records'][0]
    assert row['height_energy_floor'] is None
    assert not any(p['method']=='FLT_height_energy_floor' for p in row['components'])
