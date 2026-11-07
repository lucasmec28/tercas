"""Synthetic member integration of the sufficient pure-Mx shear-lag envelope."""
import copy
import json
import pytest
from docx import Document
from tercas import isolated_en_ue_family as engine
from tercas import isolated_en_ue_family_application as app
from tercas import isolated_en_ue_family_ui as ui
from tercas import en_ue_family_provider as provider
from tercas import ue_catalog_reference as own
from en_ue_test_helpers import inputs,run
from test_en_ue_family_shear_lag import INDICES


def data(index=51,q=.03,P=0.,angle=0.):
    d=inputs(index,angle=angle);d['properties'].update(fy_MPa=300.,fu_MPa=450.)
    d.update(q_uls=q,P_uls=P,x_uls=2000.)
    return app.activate(own.activate(d),model_origin='Synthetic pure-Mx shear-lag QA')


@pytest.fixture(scope='module')
def six():return [run(data(i)) for i in INDICES]


def test_six_actual_flows_use_supplement_not_dispensation(six):
    for r in six:
        ev=app.preserved(r);assert ev['mv_computed_cases']==1
        check=ev['records'][0]['check'];proof=check['shear_lag_supplement']
        assert proof['eligible'] and check['schema']==engine.SCHEMA
        mx=check['applicability']['axes']['Mx']
        assert mx['shear_lag_qualified'] and not mx['shear_lag_dispensation_qualified']
        assert check['stress']['shear_lag_supplement_sha256']==proof['content_sha256']
        assert all(not c['observed_exceedance'] for c in check['stress']['criteria'].values())
        assert not check['whole_member_approved'] and not r['global_verification']['whole_member_approved']
        assert check['source_analysis_material']==dict(E_MPa=200000.,G_MPa=77000.)
        assert check['mv']['index_upper'] is not None
        assert check['source_demand']['section']['nodes_sha256']==ev['normal_snapshot']['nodes_sha256']
        assert any(any(e['coefficients'][key]) for e in check['source_demand']['elements'] for key in ('B_Nmm2','Tsv_Nmm','Tw_Nmm'))


def test_json_word_and_cold_reader_preserve_supplement_without_member_solver(six,monkeypatch):
    from tercas.torsion_vlasov import vlasov
    monkeypatch.setattr(vlasov,'solve_member',lambda *a,**k:pytest.fail('read must not solve a member'))
    engine._VERIFIED_READS.clear()
    r=json.loads(json.dumps(six[0]));ev=app.preserved(r)
    assert ev['records'][0]['check']['shear_lag_supplement']['eligible']
    doc=Document();ui.report(doc,r)
    text='\n'.join(p.text for p in doc.paragraphs)
    assert 'shear lag explícito' in text and 'perda espelhada' in text
    assert 'não há testemunha de excesso físico' in text


@pytest.mark.parametrize('field',['beta_global_lower','Ix_lower_mm4','moment_capacity_floor_Nmm','operator_intervals','source'])
def test_resealed_supplement_tampering_fails_warm_and_cold(six,field):
    r=copy.deepcopy(six[0]);ev=r[app.FIELD];check=ev['records'][0]['check'];p=check['shear_lag_supplement']
    if field=='operator_intervals':p[field]['Mx_positive'][2][1]*=.5
    elif field=='source':p['technical_source_sha256']='0'*64
    else:p[field]*=1.01
    p['content_sha256']=engine._sha({k:v for k,v in p.items() if k!='content_sha256'})
    check['content_sha256']=engine._sha({k:v for k,v in check.items() if k!='content_sha256'})
    ev['snapshot_sha256']=app.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):app.preserved(r)
    engine._VERIFIED_READS.clear()
    with pytest.raises(ValueError):app.preserved(r)


def test_v2_replay_stays_pending_instead_of_silent_upgrade(six):
    ev=six[0][app.FIELD];current=ev['records'][0]['check'];normal=ev['normal_snapshot'];d=current['source_demand'];origin=ev['configuration']['model_origin']
    old=engine._calculate(d,normal_snapshot=normal,model_origin=origin,shear_lag_extension=False)
    assert old['schema']==engine.PRE_SHEAR_LAG_SCHEMA
    assert 'shear_lag_supplement' not in old and old['mv']['index_upper'] is None
    saved=copy.deepcopy(old);engine._VERIFIED_READS.clear()
    assert engine.validate_saved(old,engine._compact_source(d),normal_snapshot=normal,source_sha256=engine._sha(d),model_origin=origin)
    assert old==saved


def test_inversion_and_point_jump_keep_exact_physical_zones(six):
    for q,P in ((-.30,0.),(.03,20.),(.03,-600.)):
        r=run(data(q=q,P=P));ev=app.preserved(r);check=ev['records'][0]['check'];p=check['shear_lag_supplement']
        assert p['eligible'] and check['mv']['index_upper'] is not None
        from tercas.en_ue_family_applicability import _zones
        zones=_zones(check['source_demand'],1)['zones']
        assert len(p['physical_zero_zones'])==len(zones)
        assert [z['Le_mm'] for z in p['physical_zero_zones']]==[float(b-a) for a,b in zones]
        if P==20.:assert len(zones)==1
        assert not check['whole_member_approved']


def test_inclined_biaxial_case_does_not_receive_pure_mx_proof():
    r=run(data(angle=5.71));ev=app.preserved(r);current=ev['records'][0]['check']
    check=engine.calculate(current['source_demand'],normal_snapshot=ev['normal_snapshot'],
        model_origin=ev['configuration']['model_origin'])
    p=check['shear_lag_supplement']
    assert 'shear_lag_supplement' not in current
    assert current['previous_shear_lag_attempt']==p
    assert current['concurrent_shear_lag_supplement']['eligible']
    assert not current['whole_member_approved']
    assert not p['eligible'] and 'N=My=0' in p['blocking_reasons'][0]['detail']
    assert check['mv']['index_upper'] is None and not check['whole_member_approved']
    assert check['component_status']['stress']=='pending'
    for key in ('normal','interaction'):
        c=check['stress']['criteria'][key]
        assert c['criterion']=='pending_bending_applicability' and c['index_upper_bound'] is None
        assert c['diagnostic_index_upper_bound'] is not None and not c['observed_exceedance']
    assert check['stress']['criteria']['shear']['index_upper_bound'] is not None
    assert check['shear']['index_upper'] is not None



def test_authentic_v2_engine_outputs_replay_without_requalification():
    import importlib.util
    from pathlib import Path
    from tercas._en_ue_family_r10 import en_ue_family_provider as r10
    spec=importlib.util.spec_from_file_location('tercas._historical_v2_engine_test',Path(__file__).parent/'fixtures/en_ue_family_engine_v2.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    r=run(data());ev=r[app.FIELD];new=ev['records'][0]['check'];d=new['source_demand'];origin=ev['configuration']['model_origin']
    for normal in (ev['normal_snapshot'],r10.section(51,fyb_MPa=300,
            material_declaration={k:ev['normal_snapshot']['material_declaration'].get(k) for k in ('name','fu_MPa','source')})):
        historical=old._calculate(d,normal_snapshot=normal,model_origin=origin)
        assert historical['schema']==engine.PRE_SHEAR_LAG_SCHEMA
        assert historical['mv']['index_upper'] is None and 'shear_lag_supplement' not in historical
        saved=copy.deepcopy(historical);engine._VERIFIED_READS.clear()
        assert engine.validate_saved(historical,engine._compact_source(d),normal_snapshot=normal,
            source_sha256=engine._sha(d),model_origin=origin)
        assert historical==saved
