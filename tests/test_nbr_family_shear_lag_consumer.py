"""Actual family input-source guard; no new support or load path."""
import copy
import json
import pytest
from tercas import nbr_ue_family_application as app, ue_catalog_reference as own
from tercas.application import fingerprint
from tercas import nbr_family_panorama as p
from test_nbr_ue_family_application import source


def short(P=10.,Py=0.):
    r=source(26);d=r['input_data'];d.update(L_mm=1000.,x_uls=500.,x_sls=500.,P_uls=P,P_parallel_uls=Py)
    d['segments']=[dict(start_mm=0.,end_mm=1000.,Ly_effective_mm=1000.,Lz_effective_mm=1000.,Cb_mode='one',restraint_provenance='Synthetic physical span')]
    r['input_fingerprint']=fingerprint(d);return own.attach_source(r)


@pytest.mark.parametrize('P,Py,missing',[(10.,0.,['normal']),(0.,10.,['parallel']),(10.,10.,['normal','parallel'])])
def test_pending_axis_never_presents_qualified_bending_index(P,Py,missing):
    raw=short(P,Py);new=app.attach(raw);row=new[app.FIELD]['records'][0]
    for axis,g in row['shear_lag_applicability']['axes'].items():
        assert g['qualified'] is (axis not in missing)
    affected=[c for c in row['components'] if c['demand']['axis'] in missing and c['demand']['Msd_Nmm']>0]
    assert affected and all(c['index'] is None and c['status']=='pending_NBR_9_4_applicability' for c in affected)
    assert any(c['unqualified_diagnostic_index'] is not None for c in affected)
    assert row['member_interaction']['status']=='pending_actual_member_components'
    assert any('NBR_9_4' in v for v in row['member_interaction']['missing'])
    assert app.preserved(json.loads(json.dumps(new)))==new[app.FIELD]
    assert new['input_data']==raw['input_data']
    bad=copy.deepcopy(new);bad[app.FIELD]['records'][0]['shear_lag_applicability']['axes'][missing[0]]['qualified']=True
    bad[app.FIELD]['snapshot_sha256']=own.digest(bad[app.FIELD])
    with pytest.raises(ValueError):app.preserved(bad)


def test_short_uniform_only_qualifies_no_reaction_invented_as_P():
    row=app.attach(short(0.,0.))[app.FIELD]['records'][0]
    assert row['shear_lag_applicability']['qualified']
    assert not row['shear_lag_applicability']['support_reactions_invented']
    assert all(c['status']!='pending_NBR_9_4_applicability' for c in row['components'])


def test_panorama_is_pending_but_not_forced_failure():
    result=app.attach(short());result['model_domain_evidence']=dict(status='fixed_model_domain',conflict=False)
    checks,binding=p.apply(result,[])
    for name in ('local','FLT:family','biaxial'):
        assert next(r for r in checks if r['id']=='ELU:DIRECT_ELU:'+name)['status']=='pending'
    result['global_verification']={'checks':checks,p.BINDING:binding};p.validate_saved(result)
