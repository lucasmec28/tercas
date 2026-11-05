"""Explicit U-to-Ue flange-weld hypothesis, never an automatic norm extension."""
import copy,json,math
from io import BytesIO
import pytest
from docx import Document
from tercas.three_girt_axial import tension_detail as td
from tercas.three_girt_axial import application as app
from tercas.three_girt_axial.tension_detail_ui import append_report
from test_three_girt_tension_detail import PAR,manual


def detail(length=100.,x=50.):
    d=td.blank_detail(td.WELD_U_MODE)
    d.update(origin='Synthetic QA: two longitudinal welds at the same flange',
        reference_scope_confirmed=True,outside_mode='confirmed_unperforated',outside_unperforated_confirmed=True)
    d['geometry'].update(length_mm=length,eccentricity_mm=x,
        two_equal_continuous_longitudinal_welds_confirmed=True,
        no_holes_or_losses_confirmed=True,extrapolation_accepted=True)
    return d


def solve(d):return td.capacity(d,manual(),**PAR)


@pytest.mark.parametrize('length,x,expected',[(100.,50.,.82),(200.,50.,.9),(10.,0.,.9),(36.,50.,.5)])
def test_formula_boundaries_and_no_area_factor(length,x,expected):
    r=solve(detail(length,x));d=r['connection_detail']['derived']
    assert d['raw_Ct']==pytest.approx(1-.36*x/length)
    assert d['Ct']==pytest.approx(expected)
    assert d['An_mm2']==PAR['A_mm2'] and d['weld_count']==2
    assert r['branches']['connection_net_rupture_N']==pytest.approx(expected*440*400/1.65)
    assert r['Nt_Rd_N']==pytest.approx(min(440*250/1.1,440*400/1.35,expected*440*400/1.65))
    assert d['extrapolated_hypothesis'] and not d['normative_applicability_demonstrated']
    assert not d['applied_force_eccentricity_removed'] and not r['connection_strength_verified']


@pytest.mark.parametrize('length',[35.999999,20.,1.])
def test_below_half_never_raised_or_released(length):
    r=solve(detail(length));d=r['connection_detail']['derived']
    assert d['raw_Ct']<.5 and d['Ct'] is None and not d['Ct_admissible']
    assert r['Nt_Rd_N'] is None and r['status']=='partial'
    assert r['connection_detail']['inputs']['Ct'] is None
    assert 'connection_net_rupture_N' not in r['branches']
    assert any('inadmissível' in s for s in r['missing'])
    json.dumps(r,allow_nan=False)
    doc=Document();append_report(doc,r);text='\n'.join(p.text for p in doc.paragraphs)
    assert 'inadmissível' in text and 'nunca elevado a 0,5' in text


def test_each_length_is_used_once_not_sum_of_two():
    d=solve(detail(50.,50.))['connection_detail']['derived']
    assert d['Ct']==pytest.approx(.64) and d['Ct']!=pytest.approx(.82)


def test_extreme_finite_dimensions_cannot_create_nonfinite_trace():
    with pytest.raises(ValueError,match='finite arithmetic'):
        solve(detail(1e-300,1e300))


@pytest.mark.parametrize('key',['two_equal_continuous_longitudinal_welds_confirmed','no_holes_or_losses_confirmed','extrapolation_accepted'])
def test_geometry_declarations_required(key):
    d=detail();d['geometry'][key]=False;r=solve(d)
    assert r['Nt_Rd_N'] is None and r['connection_detail']['inputs']['An_mm2'] is None
    d['geometry'][key]=1
    with pytest.raises(ValueError):solve(d)


@pytest.mark.parametrize('key',['length_mm','eccentricity_mm'])
def test_missing_dimensions_never_inferred(key):
    d=detail();d['geometry'][key]=None;r=solve(d)
    assert r['Nt_Rd_N'] is None and r['connection_detail']['derived'] is None


@pytest.mark.parametrize('key,value',[
    ('length_mm',0.),('length_mm',-1.),('length_mm',float('nan')),
    ('length_mm',float('inf')),('length_mm',True),('eccentricity_mm',-1.),
    ('eccentricity_mm',float('nan')),('eccentricity_mm',float('inf')),('eccentricity_mm',True)])
def test_invalid_dimensions_rejected(key,value):
    d=detail();d['geometry'][key]=value
    with pytest.raises(ValueError):solve(d)


def test_no_manual_Ct_or_area_mixed_into_hypothesis():
    for key in ('Ct','An_mm2'):
        d=detail();d['geometry'][key]=.8
        with pytest.raises(ValueError):solve(d)
        m=manual();m[key]=.8
        with pytest.raises(ValueError):td.capacity(detail(),m,**PAR)


def test_outside_area_remains_independent_and_requires_origin():
    d=detail();d.update(outside_mode='manual',outside_unperforated_confirmed=False)
    m=manual();m['An0_mm2']=10.
    assert td.capacity(d,m,**PAR)['Nt_Rd_N']==pytest.approx(10*400/1.35)
    m['outside_area_origin']=''
    assert td.capacity(d,m,**PAR)['Nt_Rd_N'] is None
    d=detail();d['outside_unperforated_confirmed']=False
    assert solve(d)['Nt_Rd_N'] is None


def test_end_to_end_saved_report_and_inadmissible_interaction(monkeypatch):
    from test_three_girt_en_normal_application import demand_for
    from tercas.three_girt_warping import report,network
    demand=demand_for();before=copy.deepcopy(demand)
    config=app.reference_configuration(demand);config['tension_connection']=detail();config['tension']=manual()
    saved=app.attach(demand,config);r=app.saved_component(saved)
    assert demand==before and r['capacities']['tension']['Nt_Rd_N']>0
    assert not r['whole_member_approved'] and not r['N_M_B_qualified']
    assert 'Nt' not in r['per_member']['middle']['missing_capacity_keys']
    config['tension_connection']=detail(20.)
    rejected=app.attach(demand,config);bad=app.saved_component(rejected)
    assert bad['capacities']['tension']['Nt_Rd_N'] is None
    assert 'Nt' in bad['per_member']['middle']['missing_capacity_keys']
    def forbidden(*args,**kwargs):raise AssertionError('Saved export must not recalculate')
    monkeypatch.setattr(network,'solve',forbidden);monkeypatch.setattr(app,'calculate',forbidden)
    for record in (saved,rejected):
        doc=Document(BytesIO(report.word(record)));text='\n'.join(p.text for p in doc.paragraphs)
        assert 'Hipótese extrapolada' in text and 'não a soma' in text
        assert 'incluindo lábios e dobras' in text and 'An=A' in text
        assert 'nunca elevado a 0,5' in text
    saved[app.FIELD]['configuration']['tension_connection']['geometry']['length_mm']=200.
    with pytest.raises(ValueError):app.saved_component(saved)
