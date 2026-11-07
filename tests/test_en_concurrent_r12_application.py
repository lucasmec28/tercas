"""New application dispatch and frozen historical schemas, synthetic inputs only."""
import copy
import json
import pytest
from docx import Document
from tercas import isolated_en_ue_family_application as app
from tercas import isolated_en_ue_family as original
from tercas import isolated_en_ue_concurrent_candidate as extension
from tercas import isolated_en_ue_family_ui as ui
from tercas import ue_catalog_reference as own
from en_ue_test_helpers import inputs,run


def data(index=40):
    d=inputs(index,angle=5.71,L=4100.)
    d['properties'].update(fy_MPa=300.,fu_MPa=450.)
    d=own.activate(d)
    return app.activate(d,model_origin='Synthetic R12 simultaneous shear-lag integration')


@pytest.fixture(scope='module')
def current():return run(data())


def test_new_dispatch_is_consumed_and_global_stays_separate(current):
    ev=app.preserved(current);c=ev['records'][0]['check']
    assert c['schema']==extension.SCHEMA
    assert c['concurrent_shear_lag_supplement']['eligible'] is True
    assert ev['stress_computed_cases']==ev['mv_computed_cases']==1
    assert all(ev[k] is False for k in app.FLAGS)
    assert current['whole_member_approved'] is False
    assert current['global_verification']['whole_member_approved'] is False
    assert current['input_data']==data()


def test_word_uses_actual_new_floors_and_reports_the_condition(current):
    ev=app.preserved(current);proof=ev['records'][0]['check']['concurrent_shear_lag_supplement']
    floors={}
    for axis in ('Mx','My'):floors.update(proof['pure_'+axis+'_construction']['signed_capacity_floor'])
    doc=Document();ui.report(doc,current)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'pisos próprios consumidos em EN6.27 [N·mm] '+str(floors) in text
    assert 'Sem crédito por cancelamento' in text
    assert 'Não é uma seção efetiva comum' in text
    assert 'Os operadores-base abaixo permanecem identificados como fonte' in text


def test_json_cold_replay_never_runs_member_solver(current,monkeypatch):
    from tercas import direct_torsion
    from tercas.torsion_vlasov import vlasov
    def forbidden(*args,**kwargs):raise AssertionError('Saved read must not solve a member')
    monkeypatch.setattr(direct_torsion,'solve_member',forbidden)
    monkeypatch.setattr(vlasov,'solve_member',forbidden)
    app._VALIDATED_RESULTS.clear();original._VERIFIED_READS.clear()
    r=json.loads(json.dumps(current));before=copy.deepcopy(r)
    assert app.preserved(r)['records'][0]['check']['schema']==extension.SCHEMA
    app.global_context(r,sectional=True)
    assert r==before


def test_v3_pending_is_not_promoted_on_read(monkeypatch):
    with monkeypatch.context() as legacy:
        legacy.setattr(extension,'calculate_many',original.calculate_many)
        result=run(data())
    ev=result[app.FIELD];assert ev['records'][0]['check']['schema']==original.SCHEMA
    assert ev['stress_computed_cases']==0 and ev['mv_computed_cases']==0
    before=copy.deepcopy(result)
    def forbidden(*args,**kwargs):raise AssertionError('Historical v3 must not invoke v4 generation')
    monkeypatch.setattr(extension,'calculate',forbidden)
    monkeypatch.setattr(extension,'calculate_many',forbidden)
    app._VALIDATED_RESULTS.clear();original._VERIFIED_READS.clear()
    assert app.preserved(result)==ev
    assert result==before


def test_v3_already_qualified_remains_original():
    result=run(data(0));ev=app.preserved(result);c=ev['records'][0]['check']
    assert c['schema']==original.SCHEMA
    assert c['applicability']['qualified'] is True
    expected=original.calculate(c['source_demand'],normal_snapshot=ev['normal_snapshot'],
        model_origin=ev['configuration']['model_origin'])
    assert c==expected


def test_resealed_new_floor_is_not_accepted(current):
    r=copy.deepcopy(current);ev=r[app.FIELD];c=ev['records'][0]['check']
    p=c['concurrent_shear_lag_supplement']
    p['pure_My_construction']['signed_capacity_floor']['My_negative']*=2
    p['content_sha256']=app.digest({k:v for k,v in p.items() if k!='content_sha256'})
    c['content_sha256']=app.digest({k:v for k,v in c.items() if k!='content_sha256'})
    ev['snapshot_sha256']=app.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):app.preserved(r)
