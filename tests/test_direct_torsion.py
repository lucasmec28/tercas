"""Direct PP/roof decomposition, independently checked torque and same-case H4."""
import copy
import json
import math
from io import BytesIO

import pytest
from docx import Document
from tercas import direct_torsion as direct
from tercas import direct_self_weight as pp, direct_roof_separated as split
from tercas import ue_family_reference as family, ue_reference as single
from tercas import roof_top_load as roof, aisi_roof_height as height, aisi_torsion_component as aisi
from tercas.application import calculate
from tercas.study_completion import complete_result
from tercas.aisi_torsion_ui import text_lines, report


def inputs(t=2., angle=0., q=.1, P=0., position=1700., line='web_midplane'):
    d=pp.activate(single.load_reference(angle=angle) if t==1.2 else family.load_reference(t,4000.,angle))
    d.update(load_mode='direct', q_uls=q, q_sls=.6*q, P_uls=P, P_sls=.6*P,
             x_uls=position, x_sls=position, roof_top_load=roof.choice(line))
    return d


def run(d):return complete_result(calculate(d))


@pytest.fixture(scope='module')
def current():return run(inputs(P=20.))


@pytest.mark.parametrize('t',[1.5,2.,2.25,2.65,3.,3.35])
@pytest.mark.parametrize('q,P',[(-.2,30.),(.1,-20.)])
def test_H4_one_ELU_with_unchanged_inputs_and_no_global_promotion(t,q,P):
    d=inputs(t,q=q,P=P);before=copy.deepcopy(d);r=run(d);e=aisi.preserved(r)
    assert d==before and r['input_data']==before
    assert r['torsion_evidence']['computed_cases']==2
    assert e['schema']==height.DIRECT_SCHEMA and e['H4_computed_cases']==1 and e['G81_computed_cases']==1
    assert len(e['records'])==1 and e['records'][0]['combination_id']=='DIRECT_ELU'
    c=e['records'][0];h=c['H4'];w=h['witness'];cap=c['roof_height']['strong_capacity']
    assert h['ratio']==pytest.approx(abs(w['Mx_physical_Nmm'])/cap['Ma_floor_Nmm']+abs(w['B_Nmm2'])/e['bimoment_capacity']['Ba_Nmm2'])
    assert c['roof_height']['primary_torque_preserved']
    assert c['AISI_analysis']['source_combination']==split.combinations(d)[0]
    assert e['NBR_capacities_used'] is False and not r['whole_member_approved']
    assert 'torsion_warping' in r['global_verification']['pending_ids']
    assert aisi.preserved(json.loads(json.dumps(r,allow_nan=False)))==e


@pytest.mark.parametrize('angle',[-12.,0.,12.])
@pytest.mark.parametrize('line',['web_midplane','flange_midwidth'])
def test_independent_torque_cross_product_PP_and_top_signed_actions(angle,line):
    d=inputs(angle=angle,q=-.12,P=17.,line=line)
    d.update(q_parallel_uls=.03,P_parallel_uls=-7.)
    r=run(d);rec=r['torsion_evidence']['records'][0];analysis=rec['analysis']
    cg=analysis['section']['properties']['centroid_xy_mm'];sc=analysis['section']['properties']['shear_center_xy_mm']
    p=d['properties'];top=[0. if line=='web_midplane' else (p['bf']-p['t'])/2,p['h']-p['t']/2]
    weight=1.25*p['mass_kg_m']*9.80665/1000.
    expected={'PP':([weight*math.sin(math.radians(angle)),-weight*math.cos(math.radians(angle))],cg),
              'EXTERNAL':([.03,.12],top),'P':([-7.,-17.],top)}
    for load in analysis['loads']:
        force,xy=expected[load['name']]
        key='force_xy_N' if load['kind']=='point' else 'q_xy_N_mm'
        torque_key='torque_SC_Nmm' if load['kind']=='point' else 'torque_SC_N'
        assert load[key]==pytest.approx(force) and load['application_xy_mm']==pytest.approx(xy)
        assert load[torque_key]==pytest.approx((xy[0]-sc[0])*force[1]-(xy[1]-sc[1])*force[0])
    ev=aisi.preserved(r)
    assert ev['G81_computed_cases']==1 and ev['H4_computed_cases']==0
    assert 'Flexão fraca real' in ' '.join(ev['records'][0]['missing'])


def test_independent_uniform_bimoment_closed_form():
    d=inputs(q=.1);r=run(d);ev=aisi.preserved(r);rec=ev['records'][0]
    s=ev['roof_height_source']['section']['properties'];cg=s['centroid_xy_mm'];sc=s['shear_center_xy_mm']
    w=1.25*d['properties']['mass_kg_m']*9.80665/1000.
    m=-(cg[0]-sc[0])*w-(0.-sc[0])*.1
    E=.9*203000.;G=.9*78000.;k=math.sqrt(G*s['J_mm4']/(E*s['Cw_mm6']))
    exact_B=m/k**2*(1.-1./math.cosh(k*d['L_mm']/2.))
    # Existing recovered FE field; this checks one ODE benchmark, not general physical validity.
    assert rec['G81']['B_Nmm2']==pytest.approx(exact_B,rel=2e-5)
    assert rec['G81']['x_mm']==pytest.approx(d['L_mm']/2.)


def test_cancelling_parallel_vectors_still_block_height_H4():
    d=inputs(angle=5.)
    e=pp.evidence(d)
    for suffix in ('uls','sls'):d['q_parallel_'+suffix]=-e['states'][suffix]['profile_PP_q_N_mm']['parallel']
    r=run(d);e=aisi.preserved(r)
    assert all(c['q_vector']['parallel']==0. for c in split.combinations(d))
    assert e['H4_computed_cases']==0 and e['G81_computed_cases']==1
    assert 'Flexão fraca real' in ' '.join(e['records'][0]['missing'])


def test_legacy_totals_and_nonselected_top_not_migrated():
    d=inputs();d.pop(pp.FIELD);r=run(d)
    assert r['torsion_evidence']['computed_cases']==0 and r[aisi.FIELD]['H4_computed_cases']==0
    d=inputs();d['roof_top_load']['enabled']=False;r=run(d)
    assert r.get('torsion_evidence',{}).get('computed_cases',0)==0 and r[aisi.FIELD]['H4_computed_cases']==0


def test_t120_retains_G81_and_specific_missing_flexural_source():
    r=run(inputs(1.2,position=1500.));ev=aisi.preserved(r)
    assert ev['G81_computed_cases']==1 and ev['H4_computed_cases']==0
    assert 'críticos fortes' in ' '.join(ev['records'][0]['missing'])


@pytest.mark.parametrize('position',[0.,4000.])
def test_exact_support_P_not_replaced_by_support_limit(position):
    with pytest.raises(ValueError,match='não no apoio'):
        run(inputs(P=50.,position=position))


def test_finite_P_near_support_is_pending_not_silently_moved():
    r=run(inputs(P=50.,position=1.));e=aisi.preserved(r)
    assert r['torsion_evidence']['pending_numerical_cases']==2 and e['H4_computed_cases']==0
    assert e['records'][0]['status']=='pending_demand'
    assert r['input_data']['x_uls']==1.


def reseal(r):
    e=r[aisi.FIELD];e['source_torsion_snapshot_sha256']=aisi.digest(r['torsion_evidence'])
    e['snapshot_sha256']=aisi.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})


@pytest.mark.parametrize('mutation',['schema','basis','PP','combo','load_line','torque','force','ratio','support_limit'])
def test_rehashed_corrupt_direct_evidence_rejected(current,mutation):
    r=copy.deepcopy(current);e=r[aisi.FIELD];src=e['roof_height_source'];rec=e['records'][0]
    if mutation=='schema':e['schema']=height.SCHEMA
    if mutation=='basis':src['direct_load_basis']='legacy'
    if mutation=='PP':src['direct_self_weight']['states']['uls']['factor']=1.
    if mutation=='combo':r['torsion_evidence']['source_combinations'][0]['profile_PP_factor']=1.
    if mutation=='load_line':rec['AISI_analysis']['actions'][0]['application_xy_mm'][1]=0.
    if mutation=='torque':rec['roof_height']['Mcre']['primary_torque_by_action'][0]['value']=0.
    if mutation=='force':rec['AISI_analysis']['actions'][0]['q_xy_N_mm'][0]=1.
    if mutation=='ratio':rec['H4']['ratio']=0.
    if mutation=='support_limit':rec['AISI_analysis']['support_limit_states_preserved']=True
    reseal(r)
    with pytest.raises(ValueError):aisi.preserved(r)


def test_saved_readers_do_not_solve_or_reopen_sources(current,monkeypatch):
    from tercas import torsion_study
    from tercas.aisi_research import adapter
    def fail(*args,**kwargs):raise AssertionError('No solve or source reopen when reading')
    monkeypatch.setattr(height,'refined',fail);monkeypatch.setattr(aisi,'_aisi_demand',fail)
    monkeypatch.setattr(direct,'solve_member',fail);monkeypatch.setattr(torsion_study,'section_for',fail)
    monkeypatch.setattr(roof,'geometry',fail);monkeypatch.setattr(adapter,'verify_bundle',fail)
    before=copy.deepcopy(current);ev=aisi.preserved(current)
    doc=Document();report(doc,current)
    text='\n'.join(text_lines(ev))
    assert '1,25 no ELU e 1,0 no ELS' in text and 'não são automaticamente' in text
    assert 'exatamente no apoio' in text and 'Cisalhamento' in text
    assert current==before
