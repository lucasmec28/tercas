"""Opt-in consumer integration, two real solves shared by this module."""
import copy
import json
from unittest.mock import patch
import pytest
from tercas import isolated_service_component as c
from tercas import ue_family_reference as family, roof_top_load as roof
from tercas.application import fingerprint
from tercas.batch import area_bundle
from tercas.torsion_study import section_for,automatic_roof_choice
from tercas.torsion_vlasov.adapter import attach_torsion_evidence,load_lines_from_cg,summarize_torsion_evidence


def choice(criterion='nbr_A1_pair'):
    v=c.blank_choice();v.update(point_xy_from_CG_mm=[0.,0.],projection_xy=[0.,-1.],point_label='CG',
        direction_label='Normal local à cobertura',reference_declared=True,criterion=criterion,limit_mm=20.,
        criterion_origin='Synthetic comparison for full case load, no camber',model_origin='Synthetic isolated member',
        nominal_intact_section_declared=True)
    return v


def source():
    d=family.load_reference(3.35,3000.,0.);d['roof_top_load']=roof.choice();d[c.CHOICE]=choice()
    d['area_inputs'].update(permanent_kgf_m2=.1,live_kgf_m2=.2,wind_up_kgf_m2=.3,wind_down_kgf_m2=.3)
    d['selected_types']=['ELS rara']
    from tercas.ue_catalog_reference import activate
    d=activate(d);bundle=area_bundle(d)
    # Explicit synthetic source inventory of one ordinary service case.
    bundle['combinations']=[next(r for r in bundle['combinations'] if not r['coefficients'].get('V_Cima') and not r.get('P_N'))]
    r=dict(schema='tercas_batch_results_v1',input_data=d,input_fingerprint=fingerprint(d),load_bundle=bundle,
           cases=[{'combination':copy.deepcopy(v)} for v in bundle['combinations']])
    s=section_for(d);lines=load_lines_from_cg(s,automatic_roof_choice(d)['load_lines'])
    supports={side:dict(twist='fixed',warping='free_assumed',origin='Synthetic ideal fork') for side in ('left','right')}
    return r,s,lines,supports


@pytest.fixture(scope='module')
def current():
    raw,s,lines,supports=source()
    dense=attach_torsion_evidence(raw,section=s,load_lines=lines,supports=supports)
    snapshot=copy.deepcopy(dense)
    out=c.attach_dense(dense,s)
    assert dense==snapshot
    out['torsion_evidence']=summarize_torsion_evidence(out['torsion_evidence'])
    return c.finalize(out)


def test_consumer_solves_note_f_separately_without_touching_source_inventory(current):
    ev=c.saved(current);assert ev['computed_cases']==2 and not ev['pending_cases']
    assert len(current['torsion_evidence']['records'])==1
    up=next(r for r in ev['records'] if r['kind']=='supplementary_suction')
    a=up['supplementary_summary']['analysis']
    assert [r['name'] for r in a['loads']]==['V_Cima']
    assert a['loads'][0]['q_xy_N_mm']==[0.,-current['load_bundle']['case_vectors_N_mm']['V_Cima']['normal']]
    assert all(r['comparison']['index_upper'] is not None for r in ev['records'])
    assert not ev['combined_ELS_approved'] and not ev['source_matrix_changed']


def test_saved_json_ui_word_no_member_or_mechanics_replay(current):
    from docx import Document
    from tercas.isolated_service_ui import rows,report
    out=json.loads(json.dumps(current,allow_nan=False));doc=Document();c.saved(out)
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')), \
         patch('tercas.isolated_service_mechanics.calculate',side_effect=AssertionError('no mechanics')):
        ev=c.saved(out);assert len(rows(ev))==2;report(doc,out)
    assert any('SERVICE_A1_F' in p.text for p in doc.paragraphs)


@pytest.mark.parametrize('kind',['record','inventory','source','point','approval','index','screen','criterion_status','scope'])
def test_saved_tampering_fails_closed_even_with_rehash(current,kind):
    r=copy.deepcopy(current);e=r[c.FIELD];row=e['records'][0];check=row['comparison']
    if kind=='record':e['records'].pop()
    if kind=='inventory':e['inventory'].pop()
    if kind=='source':r['torsion_evidence']['records'][0]['analysis']['max_abs_phi']['phi_rad']+=1
    if kind=='point':check['source_point_xy_from_CG_mm'][0]+=1
    if kind=='approval':check['combined_ELS_approved']=True
    if kind=='index':check['index_upper']=0
    if kind=='screen':check['gross_screen']['walls'].pop()
    if kind=='criterion_status':check['criterion_status']='approved'
    if kind=='scope':e['scope']='All done'
    e['snapshot_sha256']=c.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):c.saved(r)


def test_missing_choice_retains_history_and_absent_fields(current):
    old=copy.deepcopy(current);old.pop(c.FIELD);old['input_data'].pop(c.CHOICE)
    old['input_fingerprint']=fingerprint(old['input_data'])
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')):
        assert c.saved(old) is None and c.finalize(old)==old


def test_incomplete_choice_never_solves_and_keeps_pending_inventory():
    r,s,_,_=source();r['input_data'][c.CHOICE]['point_xy_from_CG_mm']=[None,None]
    r['input_fingerprint']=fingerprint(r['input_data'])
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')):
        out=c.finalize(c.attach_dense(r,s))
    ev=c.saved(out);assert ev['computed_cases']==0 and ev['missing']
    assert len(ev['records'])==len(ev['inventory'])==2


@pytest.mark.parametrize('t',[1.2,1.5,3.35])
def test_new_choice_does_not_invalidate_old_own_geometry_but_malformed_choice_rejected(t):
    from tercas import ue_reference as single
    d=single.load_reference() if t==1.2 else family.load_reference(t,3000.,0.)
    d[c.CHOICE]=choice('declared_limit')
    state=single.assess(d) if t==1.2 else family.assess(d)
    assert state['calculable']
    assert section_for(d)['thickness_mm']==t
    d[c.CHOICE]['unexpected']=True
    with pytest.raises(ValueError):c.configuration(d)


def rehash(r):
    e=r[c.FIELD];e['snapshot_sha256']=c.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})


def test_rehashed_coherent_zero_displacement_rejected_by_arithmetic_replay(current):
    r=copy.deepcopy(current);e=r[c.FIELD];check=e['records'][0]['comparison']
    check['envelope']['abs_displacement_lower_mm']=check['envelope']['abs_displacement_upper_mm']=0.
    for k in ('index_lower','index_upper','diagnostic_ratio_lower','diagnostic_ratio_upper'):check[k]=0.
    check['criterion_status']='within_declared_linear_model'
    rehash(r)
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')):
        with pytest.raises(ValueError,match='aritmética'):c.saved(r)


def test_rehashed_coherent_zero_stress_rejected_by_arithmetic_replay(current):
    r=copy.deepcopy(current);check=r[c.FIELD]['records'][0]['comparison'];screen=check['gross_screen']
    for wall in screen['walls']:wall['compression_upper_MPa']=0.;wall['sufficient']=True
    screen['von_mises_upper_MPa']=0.;screen['gross_local_normal_sufficient']=True
    rehash(r)
    with pytest.raises(ValueError,match='aritmética'):c.saved(r)


def test_rehashed_dense_coefficients_rejected_by_compact_source(current):
    r=copy.deepcopy(current);row=r[c.FIELD]['records'][0]
    row['source_dense']['elements'][10]['coefficients']['phi_rad'][0]+=.01
    row['source_dense_sha256']=c.digest(row['source_dense']);rehash(r)
    with pytest.raises(ValueError,match='recovered polynomials'):c.saved(r)


def test_reopen_replays_arithmetic_without_member_solve(current):
    c._REPLAY_CACHE.clear()
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')):
        assert c.saved(json.loads(json.dumps(current)) )['computed_cases']==2


def test_model_and_criterion_origin_text_are_not_normative_gates():
    config=choice();config.update(model_origin='',criterion_origin='')
    assert c.missing_configuration(config)==[]


@pytest.mark.parametrize('kind',['wall_girt','three_girt'])
def test_outside_isolated_purlin_choice_stays_inactive(kind):
    r,s,_,_=source()
    if kind=='wall_girt':r['input_data']['member_application']='wall_girt'
    else:r['input_data']['three_girt_model']={'enabled':True}
    assert c.attach_dense(r,s)==r and c.finalize(r)==r
    assert c.saved(r) is None
