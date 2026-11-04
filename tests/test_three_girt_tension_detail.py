import copy,math
from io import BytesIO
import pytest
from docx import Document
from tercas.three_girt_axial import tension_detail as a
from tercas.three_girt_axial import application as app

PAR=dict(A_mm2=440.,t_mm=2.,h_mm=100.,ri_mm=2.,fy_MPa=250.,fu_MPa=400.)


def manual():return dict(An0_mm2=None,An_mm2=None,Ct=None,origin='QA',outside_area_origin='QA unperforated outside detail',connection_origin=None)

def bolted():
    d=a.blank_detail('web_bolt_single_transverse_row')
    d.update(origin='QA synthetic common row, not actual construction',reference_scope_confirmed=True,
             outside_mode='confirmed_unperforated',outside_unperforated_confirmed=True)
    d['geometry'].update(count=2,diameter_mm=12.7,pitch_mm=50.,single_row_in_flat_web_confirmed=True,no_other_losses_confirmed=True)
    return d


def welded(arrangement='transverse_only'):
    d=a.blank_detail('lower_flange_weld')
    d.update(origin='QA synthetic lower-flange connected area',reference_scope_confirmed=True,
             outside_mode='confirmed_unperforated',outside_unperforated_confirmed=True)
    d['geometry'].update(arrangement=arrangement,An_mm2=80.)
    return d


def solve(d,**kw):return a.capacity(d,manual(),**(PAR|kw))


def test_two_vertical_bolts_use_full_developed_edges_and_factor_once():
    r=solve(bolted());g=r['connection_detail']['derived']
    assert g['developed_width_mm']==220 and g['developed_edge_sum_mm']==170
    assert g['g_effective_mm']==170 and g['hole_diameter_mm']==14.7
    assert g['An_mm2']==pytest.approx(.9*(440-2*14.7*2))
    assert g['Ct']==pytest.approx(2.5*12.7/170)
    assert r['Nt_Rd_N']==pytest.approx(.9*(440-2*14.7*2)*(2.5*12.7/170)*400/1.65)
    assert r['branches']['outside_net_rupture_N']==pytest.approx(440*400/1.35)
    assert g['longitudinal_bolt_positions']==1 and not g['applied_force_eccentricity_removed']


def test_five_eighths_exact_conversion_and_clearance():
    d=bolted();d['geometry'].update(diameter_mm=15.875,pitch_mm=50.)
    g=solve(d)['connection_detail']['derived'];assert g['hole_diameter_mm']==17.875
    assert g['hole_classification']=='circular_enlarged_actual_d_plus_2_not_standard'


def test_single_bolt_uses_whole_developed_width_not_half_or_web():
    d=bolted();d['geometry'].update(count=1,pitch_mm=None)
    g=solve(d)['connection_detail']['derived'];assert g['g_effective_mm']==220
    assert g['Ct']==pytest.approx(2.5*12.7/220)


@pytest.mark.parametrize('key',['origin','reference_scope_confirmed','outside_unperforated_confirmed'])
def test_missing_common_confirmation_blocks_Nt(key):
    d=bolted();d[key]='' if key=='origin' else False
    assert solve(d)['Nt_Rd_N'] is None


@pytest.mark.parametrize('key',['single_row_in_flat_web_confirmed','no_other_losses_confirmed'])
def test_missing_geometry_confirmation_blocks_Nt(key):
    d=bolted();d['geometry'][key]=False;assert solve(d)['Nt_Rd_N'] is None


@pytest.mark.parametrize('key',['count','diameter_mm','pitch_mm'])
def test_incomplete_geometry_stays_partial(key):
    d=bolted();d['geometry'][key]=None;assert solve(d)['Nt_Rd_N'] is None


@pytest.mark.parametrize('key,value',[
    ('count',True),('count',2.5),('count',0),('diameter_mm',float('nan')),
    ('diameter_mm',12.),('pitch_mm',39.),('pitch_mm',100.),('clearance_mm',1.5),
    ('single_row_in_flat_web_confirmed',1),('no_other_losses_confirmed','yes')])
def test_invalid_bolt_inputs_rejected(key,value):
    d=bolted();d['geometry'][key]=value
    with pytest.raises(ValueError):solve(d)


def test_minimum_pitch_boundary_is_accepted_and_lower_rejected():
    d=bolted();d['geometry']['pitch_mm']=14.7+2*12.7;assert solve(d)['Nt_Rd_N']>0
    d['geometry']['pitch_mm']-=1e-6
    with pytest.raises(ValueError):solve(d)


def test_single_bolt_cannot_hide_pitch():
    d=bolted();d['geometry']['count']=1
    with pytest.raises(ValueError):solve(d)


def test_partial_soldada_selection_never_creates_Ct():
    d=welded('undefined');assert solve(d)['Nt_Rd_N'] is None


def test_transverse_only_uses_connected_part_area_not_A():
    r=solve(welded());assert r['Nt_Rd_N']==pytest.approx(80*400/1.65)
    assert r['connection_detail']['derived']['Ct']==1


@pytest.mark.parametrize('arr',['longitudinal','mixed'])
def test_longitudinal_and_mixed_lower_flange_do_not_infer_Ct(arr):
    d=welded(arr);d['geometry'].update(length_mm=100.,eccentricity_mm=49.)
    assert solve(d)['Nt_Rd_N'] is None
    d['geometry'].update(Ct=.6,ct_origin='QA independent applicability audit, no automatic U substitution')
    assert solve(d)['Nt_Rd_N']==pytest.approx(.6*80*400/1.65)
    d['geometry']['length_mm']=None;assert solve(d)['Nt_Rd_N'] is None


def test_transverse_manual_Ct_rejected():
    d=welded();d['geometry']['Ct']=1.
    with pytest.raises(ValueError):solve(d)


def test_manual_and_derived_values_cannot_mix():
    m=manual();m['An_mm2']=440
    with pytest.raises(ValueError):a.capacity(bolted(),m,**PAR)
    m=manual();m['An0_mm2']=440
    with pytest.raises(ValueError):a.capacity(bolted(),m,**PAR)


def test_outside_An0_is_separate_and_source_required():
    d=bolted();d.update(outside_mode='manual',outside_unperforated_confirmed=False)
    m=manual();m['An0_mm2']=10
    r=a.capacity(d,m,**PAR);assert r['Nt_Rd_N']==pytest.approx(10*400/1.35)
    m['outside_area_origin']='';assert a.capacity(d,m,**PAR)['Nt_Rd_N'] is None


@pytest.fixture(scope='module')
def demand():
    from test_three_girt_en_normal_application import demand_for
    return demand_for()


def test_default_configuration_and_manual_route_are_unchanged(demand):
    c=app.reference_configuration(demand);assert 'tension_connection' not in c
    c['tension'].update(An0_mm2=300.,An_mm2=250.,Ct=.8,
        outside_area_origin='QA',connection_origin='QA')
    r=app.calculate(demand,c)
    assert 'connection_detail' not in r['capacities']['tension']
    assert r['capacities']['tension']['Nt_Rd_N']==pytest.approx(250*.8*400/1.65)


def test_bolt_detail_end_to_end_saved_report_and_hash(demand,monkeypatch):
    c=app.reference_configuration(demand);c['tension_connection']=bolted();c['tension']=manual()
    before=copy.deepcopy(demand);saved=app.attach(demand,c);r=app.saved_component(saved)
    assert demand==before and not r['whole_member_approved'] and not r['N_M_B_qualified']
    assert r['capacities']['tension']['Nt_Rd_N']>0
    assert 'Nt' not in r['per_member']['middle']['missing_capacity_keys']
    from tercas.three_girt_warping import report,network
    def forbidden(*a,**k):raise AssertionError('Saved display/export must not recalculate')
    monkeypatch.setattr(network,'solve',forbidden);monkeypatch.setattr(app,'calculate',forbidden)
    doc=Document(BytesIO(report.word(saved)));text='\n'.join(p.text for p in doc.paragraphs)
    assert 'Detalhe simples da referência de tração' in text
    assert '14.700000' in text and 'Chapa equivalente' in text
    assert 'furo-padrão' in text and 'não atualizam' in text
    saved[app.FIELD]['configuration']['tension_connection']['geometry']['pitch_mm']=51
    with pytest.raises(ValueError):app.saved_component(saved)


def test_EN_computation_and_intact_source_are_not_modified_by_detail(demand):
    from tercas.three_girt_en_normal import application as en
    from test_three_girt_en_normal_application import config
    en_saved=en.attach(demand,config(demand));before=copy.deepcopy(en.saved_component(en_saved))
    c=app.reference_configuration(en_saved);c['tension_connection']=bolted();c['tension']=manual()
    saved=app.attach(en_saved,c);assert en.saved_component(saved)==before
    r=app.saved_component(saved)
    assert not r['capacities']['tension']['connection_detail']['holes_transferred_to_bending_or_EN']


def test_thick_profile_automatic_geometry_domain_is_not_extended():
    with pytest.raises(ValueError,match='4.75'):
        solve(bolted(),t_mm=5.)
