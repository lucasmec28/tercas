"""Verification selection must never become a structural-model reduction."""
import copy
import json
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from tercas import three_girt_scope as scope
from tercas.three_girt_warping import application as w, network
from tercas.three_girt_assessment import application as assessment
from tercas.three_girt_en_normal import application as en
from tercas.three_girt_axial import application as nbr
from tercas.three_girt_service import application as service
from tercas.three_girt_uniaxial import application as uniaxial
from tercas.ue_family_reference import apply_geometry

@pytest.fixture(scope='module')
def pair():
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    data=apply_geometry(src['input_data'],3.35,4000.)
    cfg=w.current_configuration(data,src['configuration']['three_girt'])
    return (w.attach_g81(w.calculate(data,cfg)),
            w.attach_g81(w.calculate(data,cfg,verification_scope=scope.SCHEMA)))

@pytest.fixture(scope='module')
def complete(pair):
    d=pair[1]
    cfg=uniaxial.configuration(d);cfg.update(independent_members_declared=True,model_origin='Synthetic scope QA')
    d=uniaxial.attach(d,cfg)
    cfg=service.configuration(d);cfg.update(nominal_intact_section_declared=True,model_origin='Synthetic scope QA')
    d=service.attach(d,cfg)
    cfg=en.reference_configuration(d);cfg.update(intact_section_model_declared=True,section_model_origin='Synthetic scope QA')
    d=en.attach(d,cfg)
    return nbr.attach(d,nbr.reference_configuration(d))


def test_scope_does_not_change_any_mechanical_field(pair):
    old,new=pair
    assert new==dict(old,verification_scope=scope.record(old['input_fingerprint']))
    assert scope.members(old)==('upper','middle','lower')
    assert scope.members(new)==('middle',)
    assert len(new['cases'])==19
    for a,b in zip(old['cases'],new['cases']):
        assert a==b  # Full K diagnostic, all displacements, actions, reactions and equilibrium.
        assert {r['girt'] for r in b['model']['beams']}==set(scope.LEVELS)
        assert len(b['G81_component']['records'])==(3 if b['combination']['limit_state']=='ELU' else 0)


def test_new_inventory_has_only_central_criteria_and_full_integrity(complete):
    before=w.fingerprint(complete)
    a=assessment.assess(complete)
    assert a['assessment_schema']==assessment.CENTRAL_SCHEMA
    assert a['verification_scope']==complete['verification_scope']
    assert 'CENTRAL' in a['interpretation']
    assert not a['whole_member_approved'] and not a['combined_ELS_approved']
    assert 'member_stability_and_analysis' in a['pending_ids']
    groups={g['id']:g for g in a['groups']}
    assert len(groups['EN_section']['checks'])==3
    assert len(groups['NBR_reference']['checks'])==36
    assert len(groups['horizontal_service']['checks'])==7
    assert len(groups['isolated_uniaxial']['checks'])==7
    for group in a['groups']:
        for row in group['checks']:
            assert 'upper' not in row['id'] and 'lower' not in row['id']
    assert w.fingerprint(complete)==before
    assert assessment.saved_assessment(complete,a)==a
    bad=copy.deepcopy(complete);bad['cases'][0]['model']['beams'].pop(0)
    assert assessment.assess(bad)['pending_ids']==['saved_demand_integrity']


def test_display_and_word_select_only_central_resistance(complete,monkeypatch):
    from tercas.three_girt_warping.report import word
    from tercas.three_girt_warping.ui import result_rows
    from tercas.three_girt_shear import presentation_rows
    def forbidden(*a,**k):raise AssertionError('No recalculation during display')
    for module,name in [(w,'calculate'),(network,'solve'),(en,'calculate'),(nbr,'calculate'),(service,'calculate'),(uniaxial,'calculate')]:
        monkeypatch.setattr(module,name,forbidden)
    assert {r['Travessa'] for r in result_rows(complete)}=={'Central'}
    for module in (en,nbr,service,uniaxial):
        c=module.saved_component(complete)
        from importlib import import_module
        rows=import_module(module.__package__+'.ui').rows(scope.view(c,complete))
        assert rows and {r['Travessa'] for r in rows}=={'Central'}
    assert {r['Travessa'] for r in presentation_rows(nbr.saved_component(complete),demand=complete)}=={'Central'}
    a=assessment.assess(complete)
    doc=Document(BytesIO(word(complete,assessment=a)))
    text='\n'.join(p.text for p in doc.paragraphs)
    assert scope.NOTICE in text
    # One three-member table remains intentionally: mechanical demand context.
    outer_tables=[t for t in doc.tables if any(c.text in ('Superior','Inferior') for r in t.rows for c in r.cells)]
    assert len(outer_tables)==1
    assert 'N N' in [c.text for c in outer_tables[0].rows[0].cells]


def test_historical_json_and_inventory_are_not_requalified(pair,monkeypatch):
    old=json.loads(json.dumps(pair[0]));saved=assessment.assess(old)
    def forbidden(*a,**k):raise AssertionError('Historical read must not recalculate')
    monkeypatch.setattr(w,'calculate',forbidden);monkeypatch.setattr(network,'solve',forbidden)
    assert scope.FIELD not in old
    assert scope.view({'per_member':dict.fromkeys(scope.LEVELS)},old)['per_member'].keys()==dict.fromkeys(scope.LEVELS).keys()
    assert assessment.saved_assessment(old,json.loads(json.dumps(saved)))==saved
    assert saved['assessment_schema']==assessment.SCHEMA
    assert all('middle' not in g.get('scope','') for g in saved['groups'])
    assert scope.FIELD not in old


def test_central_service_guard_is_separate_from_environment(pair):
    d=pair[1]
    c=dict(content_sha256='synthetic',cases=[dict(combination=dict(id='QA'),
        network_local_normal_gross_sufficient=False,
        segments=[dict(girt=m,section=dict(local_normal_gross_sufficient=m=='middle')) for m in scope.LEVELS],
        members={m:dict(diagnostic_gross_ratio=.5 if m=='middle' else 10.,witness={}) for m in scope.LEVELS})])
    rows=assessment._service(d,c,None)
    assert len(rows)==1 and rows[0]['status']=='meets'
    assert 'rigidez bruta declarada do entorno' in rows[0]['reason']
    assert all(r['status']=='pending' for r in assessment._service(pair[0],c,None))
    c['cases'][0]['segments'][1]['section']['local_normal_gross_sufficient']=False
    assert assessment._service(d,c,None)[0]['status']=='pending'
    c['cases'][0]['segments']=[r for r in c['cases'][0]['segments'] if r['girt']!='middle']
    assert assessment._service(d,c,None)[0]['status']=='pending'
    assert scope.local_guard(c['cases'][0],'middle') is False


def test_scope_does_not_reuse_components_from_unscoped_demand(complete):
    d=copy.deepcopy(complete);d.pop(scope.FIELD)
    for module in (en,nbr,service,uniaxial):
        with pytest.raises(ValueError):module.saved_component(d)


def test_support_details_only_central_but_full_balance_retained(pair,monkeypatch):
    from tercas.support_web import sources, application as supports
    old,new=pair
    extracted=sources.extract(new)
    assert {r['support_id'] for r in extracted['supports']}=={'middle_left','middle_right'}
    assert {r['member'] for r in extracted['intermediate_stations']}==set(scope.LEVELS)
    assert len(sources.extract(old)['supports'])==3*len(extracted['supports'])
    a=supports.calculate(new,supports.reference_configuration(new))
    assert a['summary']['records']==24
    monkeypatch.setattr(sources,'extract',lambda *a: (_ for _ in ()).throw(AssertionError('No extraction during read')))
    assert supports.saved_assessment(new,a)==a


def test_unknown_scope_fails_closed(pair):
    d=copy.deepcopy(pair[1]);d[scope.FIELD]['verified_members']=['upper']
    with pytest.raises(ValueError):scope.members(d)
    assert assessment.assess(d)['pending_ids']==['saved_demand_integrity']


@pytest.mark.parametrize('source_index,target_schema',[(0,assessment.CENTRAL_SCHEMA),(1,assessment.SCHEMA)])
def test_inventory_cannot_upgrade_or_downgrade_scope_even_when_rehashed(pair,source_index,target_schema):
    d=pair[source_index]
    a=assessment.assess(d)
    assert assessment.saved_assessment(d,a)==a
    a['assessment_schema']=target_schema
    if target_schema==assessment.CENTRAL_SCHEMA:
        a['verification_scope']=scope.record(d['input_fingerprint'])
    else:a.pop('verification_scope',None)
    a['content_sha256']=w.fingerprint({k:v for k,v in a.items() if k!='content_sha256'})
    with pytest.raises(ValueError,match='schema differs from demand scope'):
        assessment.saved_assessment(d,a)


def test_invalid_central_mechanics_keep_scoped_pending_sidecar(pair):
    d=copy.deepcopy(pair[1]);d['cases'][0]['model']['beams'].pop()
    a=assessment.assess(d)
    assert a['assessment_schema']==assessment.CENTRAL_SCHEMA
    assert a['pending_ids']==['saved_demand_integrity']
    assert assessment.saved_assessment(d,a)==a
