"""Candidate arithmetic/source domains. No external solver is used."""
import copy
import math
import json
from pathlib import Path
import pytest
from tercas import nbr_ue_weak_rp23 as r
from tercas.nbr_ue_family_expansion import OutsideMethod

P=dict(h=200.,bf=75.,lip=20.,t=2.,ri_mm=2.)
G=dict(centroid_xy_mm=[25.,99.],Iy_weak_mm4=700000.)
M=dict(r.prior.DEFAULT_MATERIAL)


def test_source_example_coefficients_and_stress_not_erroneous_moment_line():
    k=r.coefficients(3.747,.407)
    assert k['k1']==pytest.approx(8.673,abs=.005)
    assert k['k2']==pytest.approx(1.623,abs=.001)
    stress=k['k']*math.pi**2*29500/(12*(1-.3**2))*(.0346/1.340)**2
    assert stress==pytest.approx(182.9,rel=.001)
    # Printed example's last 186.1*.093=46.6 is internally inconsistent.
    # Never import that line: Eq11, Fcrl*S_c, is the governing dimensional identity.
    assert stress*.093==pytest.approx(17.01,abs=.03)


@pytest.mark.parametrize('eta',[2.5,2.75,2.75000001,6.,6.00000001,11.1])
def test_piecewise_formula(eta):
    out=r.coefficients(eta,.4)
    expected=.4*max(0.,min(13.,4*eta-11))
    assert out['k2']==pytest.approx(expected)


@pytest.mark.parametrize('eta,psi',[(2.4999,.4),(11.10001,.4),(4.,.069999),(4.,.770001)])
def test_domain_no_clipping(eta,psi):
    with pytest.raises(OutsideMethod):r.coefficients(eta,psi)


@pytest.mark.parametrize('sign',['positive','web','negative ',None])
def test_only_lip_compression(sign):
    with pytest.raises(OutsideMethod):r.critical(P,G,M,sign=sign)


def test_material_and_exterior_modulus_scaling():
    a=r.critical(P,G,M,sign='negative')
    b=r.critical(P,G,dict(M,E_MPa=210000,fy_MPa=350),sign='negative')
    c=r.critical(P,G,dict(M,G_MPa=80000,fy_MPa=250),sign='negative')
    assert b['Ml_Nmm']/a['Ml_Nmm']==pytest.approx(1.05)
    assert a['Ml_Nmm']==c['Ml_Nmm']
    assert a['Wc_mm3']==G['Iy_weak_mm4']/(P['bf']-P['t']/2-G['centroid_xy_mm'][0])
    assert a['Ml_Nmm']==a['Wc_mm3']*a['Fcrl_MPa']
    assert not a['guaranteed_lower_bound'] and not a['sample']['reported_fit_statistics_transferred']
    assert a['sample']['ri_over_t']==1
    local,flt=r.capacity(a,M,2e6)
    assert 0<local['MRd_Nmm']<=a['Wc_mm3']*M['fy_MPa']/M['gamma']
    assert 0<flt['MRd_Nmm']<=local['MRd_Nmm']


def test_stocky_lips_are_explicitly_excluded():
    p=dict(P,lip=9.)
    with pytest.raises(OutsideMethod,match='d/t<4.4'):r.critical(p,G,M,sign='negative')


def test_invalid_numeric_values():
    for v in (True,float('nan'),float('inf'),0,-1):
        with pytest.raises(ValueError):r.critical(dict(P,t=v),G,M,sign='negative')
        with pytest.raises(ValueError):r.critical(P,G,dict(M,E_MPa=v),sign='negative')


def test_candidate_binding_and_previous_branches_unchanged():
    # One catalogue call per route; exercises public integration, not a heavy solve.
    a=r.prior.assess(53,L_mm=6000.)
    b=r.assess(53,L_mm=6000.)
    assert a['strong']==b['strong'] and a['weak']['positive']==b['weak']['positive']
    assert a['weak']['negative']['distortional']==b['weak']['negative']['distortional']
    assert b['weak']['negative']['local']['eligible']
    assert not b['physical_section_verified'] and not b['whole_member_approved']
    assert b['method_status']=='integrated_approximate_reference'
    assert not b['pierin_criticals_transferred']
    bad=copy.deepcopy(b);bad['weak']['negative']['local']['Ml_Nmm']*=2
    bad['snapshot_sha256']=r.prior.digest({k:v for k,v in bad.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):r.validate_saved(bad,index=53,L_mm=6000.)


@pytest.mark.parametrize('mode',['direct','area'])
def test_versioned_consumer_replay_ui_word_and_negative_fallback(mode,monkeypatch):
    from tercas import nbr_ue_family as current
    from tercas import nbr_ue_family_application as app, nbr_ue_family_application_v2 as app2
    from tercas import nbr_ue_family_ui as ui
    from test_nbr_ue_family_application import source
    from docx import Document
    old=source(53,mode=mode,py=-100.)
    historic=app2.attach(old)
    fresh=app.attach(old)
    ev=fresh[app.FIELD]
    assert ev['schema']==app.SCHEMA
    assert app.preserved(json.loads(json.dumps(fresh)))==ev
    assert app.preserved(json.loads(json.dumps(historic)))==historic[app.FIELD]
    assert not historic[app.FIELD]['sources']['own_rounded_contour']['weak']['negative']['local']['eligible']
    assert ev['sources']['own_rounded_contour']['weak']['negative']['local']['eligible']
    assert all(x['approximate'] for row in ev['records'] for x in row['components']
               if x['method']=='weak_negative_local')
    assert all(not row['whole_member_approved'] for row in ev['records'])
    assert any(row['Aproximação'] for row in ui.rows(ev) if row['Método']=='weak_negative_local')
    doc=Document();ui.report(doc,fresh)
    assert any('RP23-01' in p.text for p in doc.paragraphs)
    assert any('Referência aproximada' in c.text for table in doc.tables for row in table.rows for c in row.cells)
    # Replay routes remain historical even if fresh generation becomes unavailable.
    monkeypatch.setattr(current,'assess',lambda *a,**kw:pytest.fail('v2 replay invoked v3'))
    assert app.preserved(historic)==historic[app.FIELD]


def test_v2_scalar_snapshot_stays_identical(monkeypatch):
    from tercas import nbr_ue_family as current
    a=r.prior.assess(53,L_mm=6000.)
    monkeypatch.setattr(current,'assess',lambda *a,**kw:pytest.fail('v2 scalar replay invoked v3'))
    assert current.validate_saved(a,index=53,L_mm=6000.)==a


def test_general_NBR_geometric_limit_not_bypassed():
    with pytest.raises(OutsideMethod,match='Table4'):
        r.critical(dict(P,h=500.),G,M,sign='negative')


def test_unrelated_prior_failure_is_not_replaced(monkeypatch):
    old=r.prior.assess(53,L_mm=6000.)
    old['weak']['negative']['local']['reason']='unresolved general applicability'
    monkeypatch.setattr(r.prior,'assess',lambda *a,**kw:copy.deepcopy(old))
    out=r.assess(53,L_mm=6000.)
    assert out['rp23_negative_local_candidate']['eligible']
    assert not out['weak']['negative']['local']['eligible']
    assert not out['weak']['negative']['complete_reference_components']


def test_elastic_material_binding_not_mixed():
    el=r.critical(P,G,M,sign='negative')
    with pytest.raises(ValueError,match='match material'):
        r.capacity(el,dict(M,fy_MPa=250),2e6)
