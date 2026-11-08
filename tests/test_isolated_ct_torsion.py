"""Saved synthetic demand: no Vlasov/FLT/resistance solve in these tests."""
import copy
import json
from pathlib import Path

import pytest

from tercas import isolated_ct_torsion as ct
from tercas import isolated_en_panorama as en
from tercas.global_verification import build_global_verification
from tercas.application import fingerprint


def source(name='roof'):
    return json.loads((Path(__file__).parent/'fixtures'/('ct_zero_'+name+'.json')).read_text())


def torsion(summary):
    return next(r for r in summary['checks'] if r['id'] == 'torsion_warping')


@pytest.fixture(autouse=True)
def no_member_solves(monkeypatch):
    from tercas.torsion_vlasov import vlasov, adapter
    from tercas import direct_torsion, ltb_load_height
    def forbidden(*a, **kw):pytest.fail('Applicability reader must not solve the member')
    for module, name in ((vlasov,'solve_member'), (adapter,'solve_member'),
                         (direct_torsion,'solve_member'), (ltb_load_height,'refined')):
        monkeypatch.setattr(module, name, forbidden)


@pytest.mark.parametrize('name', ['roof','girt'])
def test_ct_model_zero_is_applicability_not_strength_or_global_approval(name):
    r=source(name);before=copy.deepcopy(r)
    p=ct.proof(r)
    assert p['ELU_cases']==1 and len(p['case_bindings'])==2
    assert p['normative_exemption'] is False and p['zero_test']=='exact_zero_no_tolerance'
    summary=build_global_verification(r);record=torsion(summary)
    assert record['status']=='not_applicable' and record['index'] is None
    assert record['reason']=='Sem solicitação torsional neste modelo.'
    assert 'torsion_warping' not in summary['pending_ids']
    assert 'incluindo torção/empenamento' not in summary['display_summary']
    assert summary[ct.FIELD]==ct.POLICY
    for k in ('whole_member_approved','approved_within_declared_checklist',
              'current_adapter_can_approve','torsion_warping_qualified','combined_ELS_approved'):
        assert summary[k] is False
    assert r==before
    # CG moments are not torques about SC and must never be zeroed.
    a=r['torsion_evidence']['records'][0]['analysis']
    assert any(x['torque_CG_N' if x['kind']=='uniform' else 'torque_CG_Nmm'] != 0 for x in a['loads'])
    assert a['field_envelopes']['T_CG_Nmm']['maximum_absolute']['value'] != 0
    r['global_verification']=summary
    en.validate_saved(json.loads(json.dumps(r)), None)


def mutate(r, name):
    ev=r['torsion_evidence'];a=ev['records'][0]['analysis'];data=r['input_data']
    if name=='empty':ev['records']=[];ev['computed_cases']=0
    elif name=='missing_record':ev['records'].pop()
    elif name=='duplicate':ev['records'].append(copy.deepcopy(ev['records'][0]));ev['computed_cases']+=1
    elif name=='no_elu':ev['records']=ev['records'][1:];ev['computed_cases']=1
    elif name=='other_id':ev['records'][0]['combination_id']='OTHER'
    elif name=='missing_analysis':ev['records'][0]['analysis']=None
    elif name=='pending':ev['records'][0]['status']='pending_numerical_qualification'
    elif name=='pending_els':ev['records'][1]['status']='pending_numerical_qualification'
    elif name=='unknown_method':a['method']='other'
    elif name=='network':data['three_girt_model']={'enabled':True}
    elif name=='network_schema':r['schema']='tercas_three_girt_results_v1'
    elif name=='legacy':data.pop('load_application_policy')
    elif name=='marker_only':ev.pop('load_application_policy')
    elif name=='missing_lines':ev['load_lines'].pop('PP')
    elif name=='line':a['loads'][0]['application_xy_mm'][0]+=1.
    elif name=='couple':a['loads'][0]['couple_N']=1e-300
    elif name=='sc_torque':a['loads'][0]['torque_SC_N']=1e-300
    elif name=='force':a['loads'][0]['q_xy_N_mm'][0]+=1.
    elif name=='point_position':next(x for x in a['loads'] if x['kind']=='point')['s_mm']+=1.
    elif name=='drop_action':a['loads'].pop()
    elif name=='duplicate_action':a['loads'].append(copy.deepcopy(a['loads'][0]))
    elif name=='source_combo':ev['source_combinations'][0]['q_vector']['normal']+=1.
    elif name=='local_vector':r['inclination_evidence']['ELU']['q_vector']['normal']+=1.
    elif name=='self_weight':r['direct_self_weight_evidence']['states']['uls']['factor']=1.
    elif name=='section_sc':a['section']['properties']['shear_center_xy_mm'][0]+=1.
    elif name=='section_digest':a['section']['nodes_sha256']='0'*64
    elif name=='section_J':a['section']['properties']['J_mm4']*=2.
    elif name=='G':a['G_MPa']*=2.
    elif name=='zero_G':a['G_MPa']=0.
    elif name=='support':a['support_hypotheses']['left']['twist']='free'
    elif name=='imposed_support':a['support_hypotheses']['left']['phi_rad']=.001
    elif name=='second_order':a['analysis_domain']['order']=2
    elif name=='coupled_operator':a['analysis_domain']['bending_torsion_coupled']=True
    elif name=='contact':a['analysis_domain']['sheet_contact']=True
    elif name=='qualification':a['numerics']['qualification_passed']=False
    elif name=='coverage':a['demand_coverage_complete_for_declared_model']=False
    elif name=='no_elements':a['element_count']=0
    elif name=='no_states':a['state_count']=0
    elif name=='no_witnesses':a['witnesses']=[]
    elif name=='witness':a['witnesses'][0]['B_Nmm2']=1e-300
    elif name=='witness_other_case':a['witnesses'][0]['combination_id']='OTHER'
    elif name=='witness_index':a['field_envelopes']['B_Nmm2']['minimum']['witness_index']=-1
    elif name=='missing_envelope':a['field_envelopes'].pop('Tw_Nmm')
    elif name=='missing_extreme':a['field_envelopes']['T_Nmm'].pop('minimum')
    elif name=='boolean_zero':a['field_envelopes']['B_Nmm2']['minimum']['value']=False
    elif name=='tiny_nonzero':a['field_envelopes']['B_Nmm2']['minimum']['value']=1e-300
    elif name=='nan':a['field_envelopes']['B_Nmm2']['minimum']['value']=float('nan')
    elif name=='reaction':a['support_reactions']['left_generalized_warping_Nmm2']=1e-300
    elif name=='energy':a['numerics']['energy_Nmm']=1e-300
    elif name=='max_phi':a['max_abs_phi']['phi_rad']=1e-300
    elif name=='domain_input':data['u_panel_condition']={'condition':'top_panel_other_free'}
    else:raise AssertionError(name)
    # Self-hashes are not authority. Even coherent hash refreshes must not help.
    if name in ('network','legacy','domain_input'):
        r['input_fingerprint']=fingerprint(data)
        ev['source_input_fingerprint']=r['input_fingerprint']
        for row in ev['records']:row['source_input_fingerprint']=r['input_fingerprint']
    ev['self_hash']='refreshed_untrusted_hash'


MUTATIONS=['empty','missing_record','duplicate','no_elu','other_id','missing_analysis','pending','pending_els',
    'unknown_method','network','network_schema','legacy','marker_only','missing_lines','line','couple','sc_torque',
    'force','point_position','drop_action','duplicate_action','source_combo','local_vector','self_weight','section_sc',
    'section_digest','section_J','G','zero_G','support','imposed_support','second_order','coupled_operator','contact',
    'qualification','coverage','no_elements','no_states','no_witnesses','witness','witness_other_case','witness_index',
    'missing_envelope','missing_extreme','boolean_zero','tiny_nonzero','nan','reaction','energy','max_phi','domain_input']


@pytest.mark.parametrize('name', MUTATIONS)
def test_no_missing_or_tampered_proof_promotes_pending(name):
    r=source();mutate(r,name)
    assert ct.record(r) is None
    assert en.torsion_record(None,en.DEFAULT_TORSION_REASON,ct_result=r)['status']=='pending'


@pytest.mark.parametrize('name', [n for n in MUTATIONS if n not in ('nan',)])
def test_saved_applicability_rejects_semantic_mutation_even_after_rehash(name):
    r=source();r['global_verification']=build_global_verification(r)
    mutate(r,name)
    g=r['global_verification'];g['source_input_fingerprint']=r['input_fingerprint']
    g['self_hash']=ct.digest({k:v for k,v in g.items() if k!='self_hash'})
    with pytest.raises(ValueError):en.validate_saved(r,None)


def test_old_ct_panorama_and_old_non_ct_pending_are_not_requalified():
    for legacy in (False,True):
        r=source()
        if legacy:r['input_data'].pop('load_application_policy')
        r['global_verification']={'checks':[{'id':'torsion_warping','status':'pending'}]}
        before=copy.deepcopy(r);en.validate_saved(r,None)
        assert r==before


@pytest.mark.parametrize('change',['remove_ct_policy','unknown_ct_policy','remove_en_policy','approve','reason','trace'])
def test_saved_policy_and_scope_cannot_be_relabelled(change):
    r=source();r['global_verification']=build_global_verification(r);g=r['global_verification']
    if change=='remove_ct_policy':g.pop(ct.FIELD)
    elif change=='unknown_ct_policy':g[ct.FIELD]='unknown'
    elif change=='remove_en_policy':g.pop('sectional_conditions_policy')
    elif change=='approve':g['whole_member_approved']=True
    elif change=='reason':torsion(g)['reason']='Dispensa normativa de torção'
    else:torsion(g)['trace']['normative_exemption']=True
    g['self_hash']=ct.digest(g)
    with pytest.raises(ValueError):en.validate_saved(r,None)


def test_coherently_shifted_SC_and_all_load_lines_still_rejected_after_rehash():
    r=source();r['global_verification']=build_global_verification(r)
    ev=r['torsion_evidence'];offset=1.
    for row in ev['records']:
        a=row['analysis'];a['section']['properties']['shear_center_xy_mm'][0]+=offset
        for load in a['loads']:load['application_xy_mm'][0]+=offset
        a['section']['content_sha256']=ct.digest(a['section'])
    for line in ev['load_lines'].values():
        line['xy_mm'][0]+=offset;line['xy_from_CG_mm'][0]+=offset
    for line in ev['choice_snapshot']['load_lines'].values():line['xy_from_CG_mm'][0]+=offset
    g=r['global_verification'];trace=torsion(g)['trace']
    trace['source_torsion_snapshot_sha256']=ct.digest(ev)
    trace['source_section_content_sha256']=ev['records'][0]['analysis']['section']['content_sha256']
    for binding,row in zip(trace['case_bindings'],ev['records']):
        binding['source_summary_record_sha256']=ct.digest(row)
    g['self_hash']=ct.digest(g)
    assert ct.record(r) is None
    with pytest.raises(ValueError):en.validate_saved(r,None)


def test_foreign_coherent_force_field_is_not_authorized_by_zero_torsion():
    r=source();r['global_verification']=build_global_verification(r)
    ev=r['torsion_evidence'];row=ev['records'][0];a=row['analysis']
    # A different balanced force field could also have exactly zero torque.
    # Its apparent zero torsion does not bind it to these requested actions.
    load=a['loads'][0];load['q_xy_N_mm'][0]+=1.
    cg=a['section']['properties']['centroid_xy_mm'];sc=a['section']['properties']['shear_center_xy_mm']
    load['torque_CG_N']=(sc[0]-cg[0])*load['q_xy_N_mm'][1]-(sc[1]-cg[1])*load['q_xy_N_mm'][0]
    for side in ('left','right'):a['support_reactions'][side+'_force_xy_N'][0]-=a['length_mm']/2
    ev['source_combinations'][0]['q_vector']['parallel']+=1.
    ev['source_combinations'][0]['external_q_vector']['parallel']+=1.
    r['inclination_evidence']['ELU']['q_vector']['parallel']+=1.
    trace=torsion(r['global_verification'])['trace'];trace['source_torsion_snapshot_sha256']=ct.digest(ev)
    trace['case_bindings'][0]['source_summary_record_sha256']=ct.digest(row)
    trace['case_bindings'][0]['source_combination_sha256']=ct.digest(ev['source_combinations'][0])
    assert ct.record(r) is None
    with pytest.raises(ValueError):en.validate_saved(r,None)
