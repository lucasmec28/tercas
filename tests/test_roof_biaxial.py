"""Separate-axis NBR 9.9 capacities; never a coupled LBA or global approval."""
import copy
import json
import pytest
from tercas import roof_biaxial as biaxial,roof_top_load as roof,roof_top_nbr as nbr
from tercas import direct_self_weight as pp,direct_roof_separated as separated
from tercas import ue_reference as single,ue_family_reference as family
from tercas.application import calculate,rows
from tercas.global_verification import build_global_verification
from tercas.roof_top_nbr_ui import presentation_rows,ROW,report


def action(parallel,x=30.,name='PP',height=0.):
    return dict(name=name,kind='uniform',q_down_N_mm=.1,q_parallel_N_mm=parallel,
                x_from_SC_mm=x,height_above_SC_mm=height)


@pytest.mark.parametrize('parallel,x,applicable',[(.1,30.,True),(-.1,30.,False),
    (-.1,-30.,True),(.1,-30.,False),(.1,0.,True),(-.1,0.,True),(0.,30.,False)])
def test_position_is_physical_force_dot_radius_not_angle(parallel,x,applicable):
    e=biaxial.classify([action(parallel,x)],{'coherent_torsion_section':True})
    assert e['applicable'] is applicable
    assert e['combined_buckling_eigenvalue'] is False
    assert e['primary_torsion_assessed'] is False
    assert e['weak_favorable_height_used'] is False


def test_individual_opposite_forces_cannot_cancel_the_guard():
    a=[action(.1,name='PP'),action(-.1,name='EXTERNAL',height=50.)]
    e=biaxial.classify(a,{'coherent_torsion_section':True})
    assert not e['applicable'] and 'EXTERNAL' in e['reason']
    assert len(e['actions'])==2
    assert not biaxial.classify([action(.1,None)],{'coherent_torsion_section':True})['applicable']
    assert not biaxial.classify([action(.1)],{'coherent_torsion_section':False})['applicable']


def inputs(t=2.,angle=5.):
    d=single.load_reference(angle=angle) if t==1.2 else family.load_reference(t,4000.,angle)
    d=pp.activate(d)
    d.update(load_mode='direct',q_uls=.1,q_sls=.06,P_uls=0.,P_sls=0.,
        q_parallel_uls=0.,q_parallel_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.,
        roof_top_load=roof.choice())
    return d


def run(d):
    return nbr.attach(roof.attach(calculate(d)))


@pytest.fixture(scope='module')
def positive():return run(inputs())


@pytest.mark.parametrize('t',[1.2,1.5,2.,2.25,2.65,3.,3.35])
def test_seven_sources_have_same_combination_capacities_and_concomitant_demands(t):
    r=run(inputs(t));e=nbr.preserved(r);m=roof.preserved(r)
    assert m['computed_cases']==2 and e['computed_cases']==1 and e['pending_cases']==0
    row=e['records'][0];b=row['biaxial'];c=roof.combination_inventory(r)[0]
    assert b['status']=='computed_fixed_position'
    assert b['strong_capacity_Nmm']==row['MRd_bending_component_Nmm']
    assert b['governing']['My_Nmm']>0
    assert b['governing']['index']==pytest.approx(
        abs(b['governing']['Mx_Nmm'])/row['MRd_bending_component_Nmm']+
        abs(b['governing']['My_Nmm'])/b['weak_axis_capacities']['positive']['MRd_Nmm'])
    assert b['governing']['x_mm']==pytest.approx(r['input_data']['L_mm']/2)
    assert c['profile_PP_factor']==1.25
    for record,combo in zip(m['records'],roof.combination_inventory(r)):
        acts={a['name']:a for a in record['actions']}
        assert acts['PP']['q_parallel_N_mm']==combo['profile_PP_q_vector']['parallel']
        assert acts['PP']['height_above_SC_mm']==0.
        assert acts['EXTERNAL']['height_above_SC_mm']==pytest.approx(50.,abs=1e-10)
        assert record['separate_axis_capacity_scope']['applicable']
        assert record['primary_torsion_resistance_included'] is False
    assert not r['whole_member_approved']


def test_negative_angle_and_cancelled_opposite_action_stay_pending():
    r=run(inputs(angle=-5.));e=nbr.preserved(r)
    assert e['computed_cases']==0 and 'desestabilizante' in e['records'][0]['reason']
    d=inputs();e=pp.evidence(d)
    for suffix in pp.FACTORS:d['q_parallel_'+suffix]=-e['states'][suffix]['profile_PP_q_N_mm']['parallel']
    r=run(d)
    assert roof.preserved(r)['computed_cases']==0
    assert all(x['status']=='pending_biaxial_model' for x in roof.preserved(r)['records'])


def test_zero_parallel_axis_keeps_existing_uniaxial_route():
    r=run(inputs(angle=0.));m=roof.preserved(r);e=nbr.preserved(r)
    assert m['computed_cases']==2 and e['computed_cases']==1
    assert all('separate_axis_capacity_scope' not in x for x in m['records'])
    assert 'biaxial' not in e['records'][0]
    assert all(x['status']=='not_applicable' for x in build_global_verification(r)['checks'] if x['id'].endswith(':biaxial'))


def test_actual_primary_torque_keeps_parallel_top_term_without_changing_kernel():
    d=inputs();d.update(q_parallel_uls=.025,P_parallel_uls=40.,P_uls=100.)
    r=run(d);m=roof.preserved(r)['records'][0]
    actual={x['name']:x['value'] for x in m['primary_torque_by_action']}
    normal={x['name']:x['value'] for x in m['normal_projection_primary_torque_by_action']}
    assert actual['EXTERNAL']==pytest.approx(normal['EXTERNAL']-50.*.025)
    assert actual['P']==pytest.approx(normal['P']-50.*40.)
    assert actual['PP']==normal['PP']
    assert m['primary_torque_report_includes_parallel_actions']


def test_global_and_display_replace_resolved_pending_only(positive):
    r=copy.deepcopy(positive);r['global_verification']=build_global_verification(r)
    nbr.validate_saved_global(r)
    g=r['global_verification'];checks={x['id'].rsplit(':',1)[-1]:x for x in g['checks']}
    assert checks['biaxial']['status']=='meets' and checks['FLT_height']['status']=='meets'
    assert 'torsion_warping' in g['pending_ids'] and not g['whole_member_approved']
    shown=presentation_rows(r,rows(r))
    assert sum(x['Verificação']=='Flexão biaxial' for x in shown)==1
    assert next(x for x in shown if x['Verificação']=='Flexão biaxial')['Índice']==r[nbr.FIELD]['records'][0]['biaxial']['governing']['index']
    assert sum(x['Verificação']==ROW for x in shown)==1
    assert r['NBR_branches']==positive['NBR_branches']


def test_readers_use_saved_values_without_source_or_solver(positive,monkeypatch):
    r=copy.deepcopy(positive);r['global_verification']=build_global_verification(r);before=copy.deepcopy(r)
    def fail(*a,**k):raise AssertionError('Unexpected recalculation/source reopening')
    monkeypatch.setattr(roof,'refined',fail);monkeypatch.setattr(biaxial,'interaction',fail)
    monkeypatch.setattr(family,'reference',fail);monkeypatch.setattr(single,'reference',fail)
    from tercas import weak_axis
    monkeypatch.setattr(weak_axis,'interaction_envelope',fail)
    nbr.preserved(r);nbr.validate_saved_global(r);presentation_rows(r,rows(r))
    from docx import Document
    doc=Document();report(doc,r)
    assert any('Interação §9.9: x=' in x.text for x in doc.paragraphs)
    assert r==before and nbr.preserved(json.loads(json.dumps(r)))


@pytest.mark.parametrize('mutation',['axis_force','biaxial_removed','weak_capacity','governing','projection_torque'])
def test_resigned_inconsistent_new_snapshot_rejected(positive,mutation):
    r=copy.deepcopy(positive)
    if mutation in ('axis_force','projection_torque'):
        e=r['roof_top_load_evidence'];row=e['records'][0]
        if mutation=='axis_force':row['actions'][1]['q_parallel_N_mm']*=-1
        else:row['primary_torque_by_action'][0]['value']+=1
        e['snapshot_sha256']=roof.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    else:
        e=r[nbr.FIELD];row=e['records'][0]
        if mutation=='biaxial_removed':del row['biaxial']
        elif mutation=='weak_capacity':row['biaxial']['weak_axis_capacities']['positive']['MRd_Nmm']*=2
        else:row['biaxial']['governing']['My_Nmm']=0.
        e['snapshot_sha256']=roof.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):nbr.preserved(r)


def test_new_fields_do_not_change_shared_AISI_action_adapter(positive):
    d=positive['input_data'];g=roof.geometry(d);combo=separated.combinations(d)[0]
    legacy,_=separated.actions(combo,g)
    extended,_=separated.actions(combo,g,include_parallel=True)
    projected=copy.deepcopy(extended)
    for a in projected:a.pop('q_parallel_N_mm',None);a.pop('P_parallel_N',None)
    assert legacy==projected
    assert all('q_parallel_N_mm' not in a and 'P_parallel_N' not in a for a in legacy)


def test_historical_pending_snapshot_not_requalified(positive,monkeypatch):
    r=copy.deepcopy(positive);r.pop(nbr.FIELD)
    e=r['roof_top_load_evidence'];e['computed_cases']=0;e['pending_cases']=len(e['records'])
    e['status']='pending_model_scope'
    e['records']=[dict(combination_id=x['combination_id'],limit_state=x['limit_state'],
        direct_envelope=False,physical_applicability_verified=False,
        actions=[{k:v for k,v in a.items() if k not in ('q_parallel_N_mm','P_parallel_N')} for a in x['actions']],
        status='pending_biaxial_model',Me_Nmm=None,lambda_cr=None,
        reason='Histórico: componentes paralelas não avaliadas.') for x in e['records']]
    e['snapshot_sha256']=roof.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    before=copy.deepcopy(r)
    monkeypatch.setattr(roof,'refined',lambda **kw:pytest.fail('Historical recalculation'))
    assert roof.preserved(r)==e and r==before
    assert nbr.preserved(r) is None


def test_pure_weak_interaction_does_not_require_nonzero_strong_demand(positive):
    own=positive['ue_family_reference_evidence']
    combo=dict(q_vector=dict(normal=0.,parallel=.01),P_vector=dict(normal=0.,parallel=0.),x_mm=2000.)
    b=biaxial.interaction(combo,4000.,1000000.,own)
    assert b['governing']['Mx_Nmm']==0 and b['governing']['My_Nmm']>0
    assert b['governing']['index']==pytest.approx(20000./b['weak_axis_capacities']['positive']['MRd_Nmm'])


def test_strong_net_cancellation_with_height_does_not_become_zero_demand_approval():
    d=inputs();e=pp.evidence(d)
    for suffix in pp.FACTORS:d['q_'+suffix]=-e['states'][suffix]['profile_PP_q_N_mm']['normal']
    r=run(d);m=roof.preserved(r)
    assert all(x['maximum_reference_moment_Nmm']==0 for x in m['records'])
    assert all(x.get('Me_Nmm') is None for x in m['records'])
    assert nbr.preserved(r)['computed_cases']==0


@pytest.mark.parametrize('mutation',['zero_witness','missing_polynomial','missing_vertex'])
def test_coherent_false_meets_cannot_replace_envelope_certificate(positive,mutation):
    r=copy.deepcopy(positive);e=r[nbr.FIELD];b=e['records'][0]['biaxial']
    if mutation=='zero_witness':
        b.update(governing=dict(x_mm=0.,Mx_Nmm=0.,My_Nmm=0.,index=0.),
            criterion_status='meets',weak_distortional_floor_can_govern=False)
    elif mutation=='missing_polynomial':b['envelope_certificate'].pop()
    else:
        row=next(c for c in b['envelope_certificate'] if len(c['candidate_x_mm'])==3)
        row['candidate_x_mm'].pop()
    e['snapshot_sha256']=roof.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):nbr.preserved(r)


@pytest.mark.parametrize('qx,px,qy,py,a',[(.1,0.,.01,0.,2000.),(-.1,200.,.03,-20.,1300.),
    (.1,-200.,-.02,150.,3000.),(0.,100.,.03,-50.,0.),(.1,-200.,.01,40.,4000.)])
def test_four_signed_polynomials_match_independent_existing_envelope(positive,qx,px,qy,py,a):
    from tercas.weak_axis import interaction_envelope
    own=positive['ue_family_reference_evidence'];rx=1000000.
    combo=dict(q_vector=dict(normal=qx,parallel=qy),P_vector=dict(normal=px,parallel=py),x_mm=a)
    new=biaxial.interaction(combo,4000.,rx,own)
    old=interaction_envelope(4000.,qx,px,qy,py,a,rx,new['weak_axis_capacities'])
    assert new['governing']['index']==pytest.approx(old['governing']['index'],rel=1e-13,abs=1e-14)
    biaxial.validate_saved(new,dict(combo,span_mm=4000.),rx,own)


@pytest.mark.parametrize('key',['source','scope'])
def test_resigned_source_or_scope_cannot_expand_claims(positive,key):
    r=copy.deepcopy(positive);e=r[nbr.FIELD]
    e['records'][0]['biaxial'][key]='Invented global approval'
    e['snapshot_sha256']=roof.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):nbr.preserved(r)


def test_inclination_detail_and_direct_rows_do_not_repeat_resolved_pending(positive):
    from tercas.roof_top_nbr_ui import presentation_inclination
    shown=presentation_inclination(positive,positive['inclination_evidence'])
    assert shown['ELU']['strong_capacity_Nmm']==positive[nbr.FIELD]['records'][0]['MRd_bending_component_Nmm']
    assert 'pendente' not in shown['ELU']['resistance_status'].lower()
    assert shown['ELS']==positive['inclination_evidence']['ELS']
    assert shown['ELU']['q_vector']==positive['inclination_evidence']['ELU']['q_vector']
    assert any(r['Verificação']==ROW for r in rows(positive))
    assert not any(r['Verificação'].startswith('FLT — trecho ') for r in rows(positive))
    assert next(r for r in rows(positive) if r['Verificação']=='Flexão biaxial')['Índice'] is not None


def test_area_cases_keep_P_support_limit_and_same_combination_binding():
    from tercas.batch import calculate_batch
    d=family.load_reference(2.,4000.,5.)
    d.update(roof_top_load=roof.choice(),selected_types=['ELU normal'])
    raw=calculate_batch(d);r=nbr.attach(roof.attach(raw));e=nbr.preserved(r)
    assert e['computed_cases']==40 and e['pending_cases']==0
    r['global_verification']=build_global_verification(r);nbr.validate_saved_global(r)
    assert all(r[k]==v for k,v in raw.items())
    cases={c['id']:c for c in roof.combination_inventory(r)}
    for row in e['records']:
        c=cases[row['combination_id']]
        assert row['source_combination_sha256']==roof.digest(c)
        biaxial.validate_saved(row['biaxial'],dict(c,span_mm=d['L_mm']),
            row['MRd_bending_component_Nmm'],r['ue_family_reference_evidence'])
    support=[c for c in r['cases'] if c['combination'].get('point_position')=='support_limit']
    assert support
    for case in support:
        shown=presentation_rows(r,case['rows'],case['combination']['id'])
        assert next(x for x in shown if x['Verificação']=='Flexão biaxial')['Índice'] is not None


def test_real_app_direct_inclined_case_replaces_legacy_pending(monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    d=inputs();payload=json.dumps(d).encode()
    monkeypatch.setattr(st,'file_uploader',lambda *a,**k:SimpleNamespace(size=len(payload),getvalue=lambda:payload))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    next(x for x in app.button if x.label=='Aplicar entradas do arquivo').click().run(timeout=30)
    next(x for x in app.button if x.label=='Calcular verificações disponíveis').click().run(timeout=60)
    assert not app.exception
    r=app.session_state.result
    assert r[nbr.FIELD]['records'][0]['biaxial']['criterion_status']=='meets'
    assert not r['global_verification']['whole_member_approved']
    assert not any('Interação §9.9 pendente: resistência completa do eixo forte' in w.value for w in app.warning)
    tables=[w.value for w in app.dataframe if 'Verificação' in w.value.columns]
    assert tables
    assert any('Flexão biaxial' in table['Verificação'].values for table in tables)
    assert all(not any(str(x).startswith('FLT — trecho ') for x in table['Verificação']) for table in tables)


def test_pending_strong_record_cannot_smuggle_active_biaxial_result(positive):
    r=copy.deepcopy(positive);e=r[nbr.FIELD];row=e['records'][0]
    row.update(status='pending',index=None,reason='Missing strong capacity')
    e.update(computed_cases=0,pending_cases=1)
    e['snapshot_sha256']=roof.digest({k:v for k,v in e.items() if k!='snapshot_sha256'})
    with pytest.raises(ValueError):nbr.preserved(r)


def test_nonzero_tiny_parallel_force_is_not_hidden_by_legacy_demand_tolerance():
    r=run(inputs(angle=1e-10))
    assert r['inclination_evidence']['ELU']['q_vector']['parallel']>0
    assert 'biaxial' in nbr.preserved(r)['records'][0]
    assert any(x['Verificação']=='Flexão biaxial' for x in rows(r))
