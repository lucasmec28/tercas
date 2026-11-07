"""Synthetic family integration; no project/private data."""
import copy,json
import pytest
from docx import Document
from tercas import isolated_en_ue_family_application as app
from tercas import isolated_en_ue_family as engine
from tercas import isolated_en_ue_family_ui as ui
from tercas import en_ue_family_provider as provider
from tercas import ue_catalog_reference as own
from en_ue_test_helpers import inputs,run


def data(index=26,fy=300.,gamma=1.):
    d=inputs(index);d['properties'].update(fy_MPa=fy,fu_MPa=450.)
    d=own.activate(d)
    return app.activate(d,model_origin='Synthetic nominal intact QA',gamma_M0=gamma)


@pytest.fixture(scope='module')
def result():return run(data())


def test_roundtrip_word_and_no_solver(result,monkeypatch):
    from tercas.torsion_vlasov import vlasov
    monkeypatch.setattr(vlasov,'solve_member',lambda *a,**k:pytest.fail('read must not solve'))
    engine._VERIFIED_READS.clear()
    r=json.loads(json.dumps(result));ev=app.preserved(r)
    assert ev['computed_cases']==1 and ev['ELS_cases_excluded']==1
    assert all(ev[k] is False for k in app.FLAGS)
    assert ev['records'][0]['check']['material']['fyb_MPa']==300
    assert r['global_verification']['whole_member_approved'] is False
    doc=Document();ui.report(doc,r)
    assert '300 MPa' in '\n'.join(p.text for p in doc.paragraphs)
    from tercas.isolated_en_application import validate_saved_global
    validate_saved_global(r)


def test_dispatch_explicit_and_no_old_routes(result):
    assert not any(k in result for k in ('isolated_EN_Ue125_300_component','isolated_EN_Ue_catalog_component'))
    d=data();d.pop(app.CHOICE)
    assert app.configuration(d) is None
    before=copy.deepcopy(d);d['isolated_en_ue125_300_model']={'enabled':True}
    activated=app.activate(d,model_origin='Explicit family update')
    assert 'isolated_en_ue125_300_model' not in activated
    activated.pop(app.CHOICE);assert activated==before


@pytest.mark.parametrize('field',['fy','gamma','normal','omega','count','proof'])
def test_saved_rejects_mutations(result,field):
    r=copy.deepcopy(result);ev=r[app.FIELD]
    if field=='fy':r['input_data']['properties']['fy_MPa']=345.
    elif field=='gamma':r['input_data'][app.CHOICE]['gamma_M0']=1.1
    elif field=='normal':ev['normal_snapshot']['material']['fyb_MPa']=250.
    elif field=='omega':ev['records'][0]['check']['source_demand']['section']['omega_nodes_mm2'][0]+=.01
    elif field=='count':ev['computed_cases']=0
    else:ev['records'][0]['check']['stress']['criteria']['normal']['index_upper_bound']=0
    with pytest.raises(ValueError):app.preserved(r)


def test_material_gamma_and_declared_stiffness():
    d=data(fy=345.,gamma=1.);d['properties'].update(E_MPa=205000.,G_MPa=78000.)
    d=own.activate(d);d=app.activate(d,model_origin='Synthetic alternate stiffness',gamma_M0=1.)
    r=run(d);ev=app.preserved(r)
    assert ev['computed_cases']==1
    c=ev['records'][0]['check']
    assert c['stress']['normal_limit_MPa']==345.
    assert c['source_analysis_material']==dict(E_MPa=205000.,G_MPa=78000.)
    assert all(p['stress_upper_MPa']==345. for p in c['applicability']['curling_panels'].values())


def test_direct_field_regression_and_unchanged_source():
    from test_isolated_en_ue125_300 import make,calc
    d=make();before=copy.deepcopy(d);old=calc(d)
    n=provider.section(26,fyb_MPa=300.)
    new=engine.calculate(d,normal_snapshot=n,model_origin='Synthetic nominal intact')
    assert d==before and new['mv']['index_upper']==old['mv']['index_upper']
    for k in ('normal','shear','interaction'):
        assert new['stress']['criteria'][k]['index_upper_bound']<=old['stress']['criteria'][k]['index_upper_bound']


def test_geometry_resealed_forgery_rejected():
    from test_isolated_en_ue125_300 import make
    d=make();n=provider.section(26,fyb_MPa=300.)
    d['section']['omega_nodes_mm2'][0]+=.1
    d['section']['content_sha256']=engine._sha({k:v for k,v in d['section'].items() if k!='content_sha256'})
    with pytest.raises(ValueError,match='Geometria integral'):engine.calculate(d,normal_snapshot=n,model_origin='synthetic')


def test_zero_needs_no_unavailable_signed_branch():
    from test_isolated_en_ue125_300 import make
    from tercas.en_ue_family_field_controls import _field_controls
    d=make(0.);n=provider.section(26,fyb_MPa=300.)
    for c in n['components'].values():c['eligible']=False;c['sigma_coefficients_c0_cx_cy']=None
    assert len(list(_field_controls(d,n)))==2


def test_required_sign_reports_pending_not_wrong_operator():
    from test_isolated_en_ue125_300 import make
    from tercas.en_ue_family_field_controls import _field_controls
    d=make();n=provider.section(26,fyb_MPa=300.)
    for c in n['components'].values():c['eligible']=False
    with pytest.raises(ValueError,match='signed effective section unavailable'):list(_field_controls(d,n))


def test_batch_authentication_once(result,monkeypatch):
    ev=result[app.FIELD];c=ev['records'][0]['check'];d=c['source_demand'];n=ev['normal_snapshot']
    calls=[];original=provider.verify
    def verify(value):calls.append(1);return original(value)
    monkeypatch.setattr(provider,'verify',verify)
    checks=engine.calculate_many([d,d],normal_snapshot=n,model_origin='Synthetic batch')
    assert len(calls)==1 and all(isinstance(c,dict) for c in checks)


def test_nonunit_gamma_is_explicit_pending():
    r=run(data(gamma=1.1));ev=app.preserved(r)
    assert ev['computed_cases']==0 and 'gamma_M0=1' in ev['records'][0]['reason']


def test_shear_preserved_when_normal_branch_missing(monkeypatch):
    from tercas._en_ue_family_r10 import en_ue_family_provider as legacy
    monkeypatch.setattr(provider,"section",legacy.section)
    r=run(data(index=19));ev=app.preserved(r)
    assert ev['shear_computed_cases']==1 and ev['stress_computed_cases']==0
    assert ev['mv_computed_cases']==0 and ev['partial_cases']==1
    check=ev['records'][0]['check']
    assert check['component_status']==dict(stress='pending',shear='computed',mv='pending')
    assert check['shear']['index_upper'] is not None
    assert all(c['index_upper_bound'] is None for c in check['stress']['criteria'].values())
    assert check['stress']['section_stress_criteria_sufficiently_satisfied'] is False
    assert check['mv']['index_upper'] is None and 'Operadores EN' in check['mv']['reason']
    assert 'unavailable' in ev['records'][0]['reason']
    assert not r['global_verification']['whole_member_approved']
    doc=Document();ui.report(doc,r)
    assert 'tensões calculadas: 0' in '\n'.join(p.text for p in doc.paragraphs)


def test_resealed_proof_does_not_pass_warm_cache(result):
    r=copy.deepcopy(result);ev=r[app.FIELD];c=ev['records'][0]['check']
    c['shear']['strong_ratio_upper']+=0.125
    c['content_sha256']=engine._sha({k:v for k,v in c.items() if k!='content_sha256'})
    ev['snapshot_sha256']=app.digest({k:v for k,v in ev.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError,match='arithmetic or authority'):app.preserved(r)


def test_ineligible_profile_directly_preserves_all_pending_reasons(monkeypatch):
    from tercas._en_ue_family_r10 import en_ue_family_provider as legacy
    monkeypatch.setattr(provider,"section",legacy.section)
    r=run(data(index=82));ev=app.preserved(r)
    assert ev['shear_computed_cases']==1
    assert ev['stress_computed_cases']==0 and ev['mv_computed_cases']==0
    assert ev['records'][0]['reason'] and ev['records'][0]['check']['shear']['index_upper'] is not None
