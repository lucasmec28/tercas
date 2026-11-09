"""R21 external snapshots and new scalar guards; no Ritz/EN/Vlasov calls."""
import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from tercas import nbr_ue_family_application as app, load_application_policy as policy
from tercas import nbr_ue_shear_lag as legacy, nbr_ue_shear_lag_strong as current
from tercas import nbr_family_validation_cache as cache, nbr_family_panorama as panorama
from tercas import nbr_ue_family_ui as ui, ue_catalog_reference as own
from tercas.application import fingerprint
from tercas.resistance_effective_lengths import declare

QA=Path(__file__).resolve().parents[1]/'qa/nbr_shear_lag_strong_geometry'


def load(name):
    entry=json.loads((QA/'historical_manifest.json').read_text())[name]
    raw=(QA/entry['file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==entry['sha256']
    return json.loads(gzip.decompress(raw))


@pytest.fixture(autouse=True)
def no_solvers(monkeypatch, request):
    from tercas import ltb_load_height,flt_height_effective,flt_height_nbr_floor,direct_torsion
    from tercas.torsion_vlasov import vlasov
    def forbidden(*a,**kw):pytest.fail('Focused shear-lag guard test must not invoke an elastic/member solver')
    monkeypatch.setattr(ltb_load_height,'refined',forbidden)
    if 'pre_CT' not in request.node.name:
        monkeypatch.setattr(flt_height_effective,'qualify_family_fresh',forbidden)
        monkeypatch.setattr(flt_height_nbr_floor,'qualify_family',forbidden)
    monkeypatch.setattr(direct_torsion,'solve_member',forbidden)
    monkeypatch.setattr(vlasov,'solve_member',forbidden)


@pytest.mark.parametrize('name',['roof','girt'])
def test_real_r21_snapshot_cold_replay_and_new_explicit_recalculation(name):
    old=load(name);before=copy.deepcopy(old)
    # Cold validation is deliberate; an in-process cached boolean cannot pass.
    assert app._preserved_uncached(old)==old[app.FIELD]
    oldrow=old[app.FIELD]['records'][0]
    assert oldrow['shear_lag_applicability']['schema']==legacy.SCHEMA
    assert not oldrow['shear_lag_applicability']['axes']['normal']['qualified']
    assert app.preserved(json.loads(json.dumps(old)))==old[app.FIELD]
    assert old==before
    new=app.attach(old);packet=new[app.FIELD];row=packet['records'][0]
    assert packet['schema']==(policy.NBR_SCHEMA if name=='roof' else policy.NBR_GIRT_SCHEMA)
    assert packet['schema']!=old[app.FIELD]['schema']
    assert row['shear_lag_applicability']['schema']==current.SCHEMA
    assert row['shear_lag_applicability']['axes']['normal']['qualified']
    assert row['shear_lag_applicability']['axes']['parallel']==oldrow['shear_lag_applicability']['axes']['parallel']
    assert new['input_data']==old['input_data']
    assert row['actions']==oldrow['actions'] and row['combination']==oldrow['combination']
    assert packet['sources']==old[app.FIELD]['sources']
    assert [c['capacity_Nmm'] for c in row['components']]==[c['capacity_Nmm'] for c in oldrow['components']]
    assert [c['demand'] for c in row['components']]==[c['demand'] for c in oldrow['components']]
    assert any(c['index'] is not None for c in row['components'] if c['demand']['axis']=='normal' and c['demand']['Msd_Nmm']>0)
    assert row['strong_web_MV']['section94_qualified']
    assert app._preserved_uncached(json.loads(json.dumps(new)))==packet
    assert not packet['whole_member_approved']


@pytest.mark.parametrize('name',['roof','girt'])
def test_panorama_and_ui_preserve_old_pending_new_component_scope(name):
    old=load(name);oldchecks,_=panorama.apply(old,[])
    assert next(c for c in oldchecks if c['id'].endswith(':local'))['status']=='pending'
    new=app.attach(old);checks,_=panorama.apply(new,[])
    assert next(c for c in checks if c['id'].endswith(':local'))['status']!='pending'
    assert len(ui.rows(new[app.FIELD]))==len(ui.rows(old[app.FIELD]))


@pytest.mark.parametrize('change',[
    lambda r:r[app.FIELD]['records'][0]['shear_lag_applicability']['axes']['normal'].update(bf0_exact_mm='1'),
    lambda r:r[app.FIELD]['records'][0]['shear_lag_applicability'].update(inner_radius_mm=4.),
    lambda r:r[app.FIELD]['records'][0]['shear_lag_applicability']['source_documents'][0].update(sha256='0'*64),
    lambda r:r[app.FIELD]['records'][0]['shear_lag_applicability'].update(schema=legacy.SCHEMA),
])
def test_rehashed_width_source_radius_and_schema_forgery_rejected(change):
    new=app.attach(load('roof'));change(new)
    new[app.FIELD]['snapshot_sha256']=own.digest(new[app.FIELD])
    with pytest.raises(ValueError):app._preserved_uncached(new)


@pytest.mark.parametrize('sign',[1.,-1.])
def test_reflection_and_effective_lengths_do_not_move_physical_threshold(sign):
    r=load('roof');d=r['input_data'];d['P_uls']=sign*10.;d['q_uls']=sign*.01
    d=declare(d,Lx_mm=500.,Ly_mm=600.,Lz_mm=700.,origin='Synthetic lengths, no additional support')
    r['input_data']=d;r['input_fingerprint']=fingerprint(d);r=own.attach_source(r)
    ev=app.attach(r)[app.FIELD];gate=ev['records'][0]['shear_lag_applicability']
    assert gate['axes']['normal']['qualified'] and gate['physical_span_mm']==1980.
    assert gate['axes']['normal']['sufficient_span_exact_mm']=='1950'
    assert ev['resistance_lengths']['Ly_mm']==600.


@pytest.mark.parametrize('name',['roof_no_CT','girt_no_CT'])
def test_pre_CT_historical_schemas_keep_their_original_scalar_reader(name):
    old=load(name);before=copy.deepcopy(old)
    assert app._preserved_uncached(old)==old[app.FIELD]
    assert app.preserved(json.loads(json.dumps(old)))==old[app.FIELD]
    assert old[app.FIELD]['records'][0]['shear_lag_applicability']['schema']==legacy.SCHEMA
    assert 'bf0 forte =' not in ui.application_note(old[app.FIELD])
    assert old==before
