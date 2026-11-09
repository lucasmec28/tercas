"""Read-only inventory, scope separation and exact applicability tests."""
import copy,json
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from tercas.three_girt_assessment import application as a
from tercas.three_girt_warping import application as w,network
from tercas.three_girt_en_normal import application as en
from tercas.three_girt_axial import application as nbr
from tercas.three_girt_service import application as svc
from tercas.ue_family_reference import apply_geometry
from tercas.global_verification import build_global_verification,attach_global_verification

@pytest.fixture(scope='module')
def demand():
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    data=apply_geometry(src['input_data'],3.35,4000.)
    return w.attach_g81(w.calculate(data,w.current_configuration(data,src['configuration']['three_girt'])))

@pytest.fixture(scope='module')
def complete(demand):
    sc=svc.configuration(demand);sc.update(nominal_intact_section_declared=True,model_origin='Synthetic QA, not a real design')
    d=svc.attach(demand,sc)
    ec=en.reference_configuration(d);ec.update(intact_section_model_declared=True,section_model_origin='Synthetic QA')
    d=en.attach(d,ec);return nbr.attach(d,nbr.reference_configuration(d))

def byid(rows):return {r['id']:r for r in rows}
def rehash(m):m['demand_content_sha256']=w.fingerprint({k:v for k,v in m.items() if k!='demand_content_sha256'})

def test_current_dispatch_inventory_and_hash_chain(complete):
    before=w.fingerprint(complete);result=build_global_verification(complete)
    assert result['assessment_schema']==a.SCHEMA
    assert len(byid(result['groups'])['EN_section']['checks'])==9
    assert len(byid(result['groups'])['NBR_reference']['checks'])==108
    assert result['source_result_sha256']==before and w.fingerprint(complete)==before
    assert 'service_model_applicability' not in result['pending_ids']
    assert 'torsion_warping' not in result['pending_ids'] and 'unsupported_result_schema' not in result['pending_ids']
    assert len(byid(result['checks']))==len(result['checks'])
    assert not result['whole_member_approved'] and not result['current_adapter_can_approve']
    assert not result['maximum_is_global_utilization'] and not result['combined_ELS_approved']
    assert svc.saved_component(complete) and en.saved_component(complete) and nbr.saved_component(complete)
    assert a.saved_assessment(complete,result)==result
    with pytest.raises(ValueError,match='cadeia de hashes'):attach_global_verification(complete)


def test_assessment_and_word_never_recalculate(complete,monkeypatch):
    from tercas.three_girt_warping.report import word
    def forbidden(*args,**kwargs):raise AssertionError('No fresh mechanics or source query')
    for module,name in ((network,'solve'),(w,'calculate'),(en,'calculate'),(en,'_profile_and_section'),(svc,'calculate'),(nbr,'_capacities')):
        monkeypatch.setattr(module,name,forbidden)
    result=a.assess(complete);payload=word(complete,assessment=result)
    text='\n'.join(p.text for p in Document(BytesIO(payload)).paragraphs)
    assert 'Panorama do modelo e critérios salvos' in text and 'não há aprovação global automática' in text
    assert word(complete)!=b''
    d=copy.deepcopy(complete);d['input_data']['project']='Changed'
    with pytest.raises(ValueError,match='another result'):word(d,assessment=result)

@pytest.mark.parametrize('mutation',[
    lambda d:d['input_data'].update(L_mm=3900.),lambda d:d['cases'].reverse(),lambda d:d['cases'].pop(),
    lambda d:d.update(coverage_complete=False),lambda d:d.update(whole_member_approved=True),
    lambda d:d['cases'][0]['model']['beams'].pop(),lambda d:d['cases'][0]['model']['fixed_dofs'].pop(),
    lambda d:d['cases'][0]['model']['nodes'][0]['support_reactions'].__setitem__(0,float('nan'))])
def test_changed_saved_demand_fails_closed(demand,mutation):
    d=copy.deepcopy(demand);mutation(d);r=a.assess(d)
    assert r['pending_ids']==['saved_demand_integrity'] and not r['whole_member_approved']
    assert r['display_summary'] and not r['groups']

@pytest.mark.parametrize('mutation',[
    lambda m:m['fixed_dofs'].pop(),lambda m:m['nodes'].pop(),lambda m:m['nodes'][0].update(id=99),
    lambda m:m['beams'][0]['normal_action_polynomials'].update(N_N=[0.,1.]),
    lambda m:m['beams'][0].update(girt='fourth'),lambda m:m['bars'].pop()])
def test_rehashed_malformed_structural_inventory_is_not_accepted(demand,mutation):
    d=copy.deepcopy(demand);m=d['cases'][0]['model'];mutation(m);rehash(m)
    assert a.assess(d)['pending_ids']==['saved_demand_integrity']


def test_optional_component_failure_does_not_erase_other_groups(complete):
    d=copy.deepcopy(complete);member=d[en.FIELD]['per_member']['upper']
    original=member['complete'];assert type(original) is bool
    member['complete']=not original
    assert member['complete']!=complete[en.FIELD]['per_member']['upper']['complete']
    r=a.assess(d);groups=byid(r['groups'])
    assert groups['EN_section']['status']=='inconclusivo'
    assert groups['horizontal_service']['counts']['meets']>0
    assert not r['whole_member_approved']


def test_auxiliary_indices_never_promote_or_fail_network(demand,monkeypatch):
    monkeypatch.setattr(a,'_nbr',lambda *x:[a.item('NBR:aux','ELU',index=99.,qualified=True)])
    monkeypatch.setattr(a,'_g81',lambda *x:[a.item('G81:aux','ELU',index=99.,qualified=True)])
    r=a.assess(demand);g=byid(r['groups'])
    assert g['NBR_reference']['status']==g['G81']['status']=='reprovado'
    assert r['status']=='inconclusivo'
    assert all(not x.startswith(('G81:','NBR:')) for x in r['failed_ids'])
    assert set(r['auxiliary_groups_not_combined'])=={'NBR_reference','G81','isolated_uniaxial'}


def fake_en(d,lo=.2,hi=.4,complete=True):
    rows=[dict(combination_id=c,girt=g,segment_id=s,x_start_mm=x,x_end_mm=y,complete=complete)
        for c,g,s,x,y in a._beam_inventory(d,'ELU')]
    members={}
    for g in a.LEVELS:
        bound=dict(index_lower_witness=lo,index_upper_bound=hi,witness=dict(girt=g,index=lo,index_lower_witness=lo))
        members[g]=dict(ELU_segments=sum(r['girt']==g for r in rows),complete_segments=sum(r['girt']==g and r['complete'] for r in rows),
            complete=complete,shear_interaction=dict(complete=complete,normal=copy.deepcopy(bound),shear=copy.deepcopy(bound),interaction=copy.deepcopy(bound)))
    # Unit-only stand-in for an already authenticated reader result.
    return dict(schema='three_girt_EN_normal_shear_certified_v6',content_sha256='fixture',rows=rows,per_member=members,
        component_sections=dict(components=dict(N_compression=dict(centroid_shift_from_gross_mm=[0.,0.]))))

@pytest.mark.parametrize('lo,hi,complete,status',[(.2,.4,True,'meets'),(.2,.4,False,'pending'),(.9,1.1,True,'pending'),(1.1,1.3,True,'fails'),(1.1,None,False,'fails')])
def test_bound_verdict_does_not_use_upper_bound_as_failure(demand,lo,hi,complete,status):
    rows=a._en(demand,fake_en(demand,lo,hi,complete),None)
    assert len(rows)==9 and {r['status'] for r in rows}=={status}
    if status=='fails':assert all(r['index']==lo for r in rows)
    if status=='pending':assert all(r['index'] is None for r in rows)

@pytest.mark.parametrize('mutation',[
    lambda c:c['rows'].pop(),lambda c:c['per_member']['upper'].update(complete_segments=0),
    lambda c:c['per_member']['upper']['shear_interaction']['normal'].update(index_upper_bound=.1),
    lambda c:c['per_member']['upper']['shear_interaction']['normal']['witness'].update(index_lower_witness=.1)])
def test_inconsistent_EN_inventory_or_bound_rejected(demand,mutation):
    c=fake_en(demand);mutation(c)
    with pytest.raises(ValueError):a._en(demand,c,None)


def test_no_extra_traceability_or_tie_strength_obligation(demand):
    r=a.assess(demand);ids={x['id'] for x in r['checks']}
    assert not ids & {'weld_design','tie_strength','field_certificate','effective_GJ_certificate','rotation_threshold'}
    assert not r['physical_conditions_verified']


def test_exact_zero_V_tension_and_empty_interior_exclusions(demand):
    d=copy.deepcopy(demand);d['configuration']['three_girt']['tie_count']=0
    for c in d['cases']:
        m=c['model'];m['bars']=[];m['inputs'].update(connections={},attachment_x_mm=[],nodal_loads=[])
        for b in m['beams']:
            b['normal_action_polynomials'].update(N_N=[0.],My_strong_Nmm=[1.,0.,0.],Mz_weak_Nmm=[2.,0.,0.])
            b['torsion_state_parameters'].update(m_SC_N=0.,nodal_phi_psi=[0.,0.,0.,0.])
        for load in m['inputs']['loads']:
            load.update(distributed_torque_CG_N=0.,q_z_N_mm=0.,q_y_N_mm=0.)
        for n in m['nodes']:
            n['support_reactions']=[0.]*7
            n['displacements'].update(rx=0.,psi=0.)
    rows=byid(a._applicability(d,None))
    for key in ('transverse_shear_resistance','N_M_V_shear_reduction','support_force_introduction','interior_force_introduction','tensile_section_scope'):
        assert rows[key]['status']=='not_applicable'
    assert rows['member_stability_and_analysis']['status']=='pending'
    d['cases'][0]['model']['nodes'][1]['support_reactions'][0]=1e-20
    assert byid(a._applicability(d,None))['support_force_introduction']['status']=='not_applicable'
    d['cases'][0]['model']['nodes'][0]['support_reactions'][0]=1e-20
    assert byid(a._applicability(d,None))['support_force_introduction']['status']=='pending'
    d['cases'][0]['model']['beams'][0]['normal_action_polynomials']['My_strong_Nmm'][1]=1e-30
    assert byid(a._applicability(d,None))['transverse_shear_resistance']['status']=='pending'
    d['cases'][0]['model']['beams'][0]['normal_action_polynomials']['N_N'][0]=1e-30
    assert byid(a._applicability(d,None))['tensile_section_scope']['status']=='pending'


def test_zero_external_P_does_not_exclude_support_introduction(demand):
    assert all(not any(c['combination']['P_vector'].values()) for c in demand['cases'])
    assert byid(a.assess(demand)['checks'])['support_force_introduction']['status']=='pending'

@pytest.mark.parametrize('change',[
    lambda r:r.update(whole_member_approved=True),lambda r:r.update(source_result_sha256='different'),lambda r:r['pending_ids'].clear()])
def test_sidecar_tampering_rejected(demand,change):
    r=a.assess(demand);change(r)
    with pytest.raises(ValueError):a.saved_assessment(demand,r)


def test_invalid_input_type():
    with pytest.raises(ValueError):a.assess([])


@pytest.mark.parametrize('mutation',[
    lambda d:d['load_bundle'].update(combinations=[1]),
    lambda d:d['cases'][0].update(model=[]),
    lambda d:d['cases'][0].update(G81_component=[]),
    lambda d:d['cases'][0]['G81_component'].update(capacity=None)])
def test_malformed_nested_object_is_pending_not_exception(demand,mutation):
    d=copy.deepcopy(demand);mutation(d);r=a.assess(d)
    assert not r['whole_member_approved']
    if r['groups']:assert byid(r['groups'])['G81']['status']=='inconclusivo'
    else:assert r['pending_ids']==['saved_demand_integrity']


def test_G81_capacity_scalars_and_concomitant_binding(demand):
    r=a.assess(demand);g=byid(r['groups'])['G81']
    assert g['counts']['meets']+g['counts']['fails']==36
    d=copy.deepcopy(demand);raw=d['cases'][0]['G81_component'];raw['capacity']['Ba_Nmm2']*=1000
    for row in raw['records']:row['ratio']/=1000
    assert sum(x['status']=='pending' for x in a._g81(d))==3
    d=copy.deepcopy(demand);d['cases'][0]['G81_component']['records'][0]['concomitant_state']['N_N']+=1
    assert a._g81(d)[0]['status']=='pending'


@pytest.mark.parametrize('axis',['normal','parallel'])
def test_jointly_changed_combination_and_bundle_cannot_match_unchanged_model(demand,axis):
    d=copy.deepcopy(demand)
    d['cases'][0]['combination']['q_vector'][axis]*=1e6
    d['load_bundle']['combinations'][0]['q_vector'][axis]*=1e6
    assert a.assess(d)['pending_ids']==['saved_demand_integrity']


def test_forged_combination_even_with_recomposed_vector_is_bound_to_loads(demand):
    d=copy.deepcopy(demand)
    for c in (d['cases'][0]['combination'],d['load_bundle']['combinations'][0]):
        c['coefficients']={k:v*2 for k,v in c['coefficients'].items()}
        c['q_vector']={k:v*2 for k,v in c['q_vector'].items()}
    assert a.assess(d)['pending_ids']==['saved_demand_integrity']

@pytest.mark.parametrize('restrained',[False,True])
@pytest.mark.parametrize('q',[0.,.02])
def test_direct_model_without_interior_bars_and_saved_load_binding(restrained,q):
    src=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    data=apply_geometry(src['input_data'],3.35,4000.)
    data.update(load_mode='direct',q_uls=q,q_sls=q,q_parallel_uls=0.,q_parallel_sls=0.,P_uls=0.,P_sls=0.,P_parallel_uls=0.,P_parallel_sls=0.)
    cfg=copy.deepcopy(src['configuration']['three_girt'])
    cfg.update(tie_count=0,connection_mode='concentric',connection_offsets={},brace_self_weight=False,direct_pp_uls_N_mm=0.,direct_pp_sls_N_mm=0.)
    cfg=w.current_configuration(data,cfg)
    if restrained:cfg['warping_end_condition']='restrained_assumed'
    d=w.attach_g81(w.calculate(data,cfg));r=a.assess(d);checks=byid(r['checks'])
    assert checks['saved_linear_demand']['status']=='meets'
    assert checks['interior_force_introduction']['status']=='not_applicable'
    assert checks['tensile_section_scope']['status']=='not_applicable'
    assert checks['transverse_shear_resistance']['status']==('not_applicable' if q==0 else 'pending')
    assert checks['support_force_introduction']['status']==('not_applicable' if q==0 else 'pending')


def test_human_display_labels_keep_raw_ids_only_in_saved_data():
    from tercas.three_girt_assessment.presentation import label,STATES
    assert label(dict(id='EN:middle:interaction'))=='Interação de tensões EN da travessa central'
    assert label(dict(id='ELS:ELSR_00004:upper:horizontal_model'))=='Flecha horizontal da travessa superior | ELSR_00004'
    assert STATES['fails']=='Não atendido' and STATES['pending']=='Pendente'


@pytest.mark.parametrize('mutation',[
    lambda c:c['rows'].pop(),lambda c:c['rows'].__setitem__(0,copy.deepcopy(c['rows'][1])),
    lambda c:c.update(ELU_combinations=99),lambda c:c['source_geometry'].update(profile_id='wrong')])
def test_NBR_auxiliary_inventory_is_bound_to_original_demand(complete,mutation):
    d=copy.deepcopy(complete);c=d['NBR_axial_bending_component'];mutation(c)
    c['content_sha256']=w.fingerprint({k:v for k,v in c.items() if k!='content_sha256'})
    r=a.assess(d);g=byid(r['groups'])['NBR_reference']
    assert g['pending_ids']==['NBR:reference_reader']
    assert not any(x.startswith('NBR:') for x in r['failed_ids'])


def test_duplicate_auxiliary_checks_fail_closed_instead_of_throwing():
    r=a.item('same','ELU',index=.2,qualified=True);g=a._group('test','Test',[r,r],'Synthetic')
    assert g['pending_ids']==['same'] and g['status']=='inconclusivo'


def test_zero_transverse_force_does_not_waive_existing_torsional_shear(demand):
    d=copy.deepcopy(demand)
    for case in d['cases']:
        for beam in case['model']['beams']:
            beam['normal_action_polynomials'].update(My_strong_Nmm=[0.],Mz_weak_Nmm=[0.])
    assert any(abs(state['T_SV_Nmm'])>0. or abs(state['T_w_Nmm'])>0.
        for case in d['cases'] if case['combination']['limit_state']=='ELU'
        for beam in case['model']['beams'] for state in beam['states'])
    before=copy.deepcopy(d);checks=byid(a._applicability(d,None))
    assert checks['transverse_shear_resistance']['status']=='not_applicable'
    assert checks['N_M_V_shear_reduction']['status']=='pending'
    assert 'Registro anterior' in checks['N_M_V_shear_reduction']['reason']
    assert 'nova rota não exige torque nulo' in checks['N_M_V_shear_reduction']['reason']
    assert d==before


@pytest.mark.parametrize('change',[
    lambda b:b['torsion_state_parameters'].update(m_SC_N=1e-30),
    lambda b:b['torsion_state_parameters'].update(nodal_phi_psi=[0.,1e-30,0.,0.]),
    lambda b:b['torsion_state_parameters'].update(nodal_phi_psi=[0.,0.,1e-30,0.]),
    lambda b:b.pop('torsion_state_parameters'),
    lambda b:b.update(torsion_state_parameters=None),
    lambda b:b['torsion_state_parameters'].update(nodal_phi_psi=[0.,False,0.,0.]),
    lambda b:b['torsion_state_parameters'].update(GJ_Nmm2=0.)])
def test_zero_torsional_shear_proof_requires_complete_exact_field(change):
    beam=dict(length_mm=1000.,torsion_state_parameters=dict(L_mm=1000.,GJ_Nmm2=10.,ECw_Nmm4=100.,
        m_SC_N=0.,nodal_phi_psi=[0.,0.,0.,0.]))
    beam.update(girt='middle',x_start_mm=0.,x_end_mm=1000.)
    model=dict(inputs=dict(upper_gap_mm=100.,lower_gap_mm=100.,
        section=dict(G_MPa=2.,J_mm4=5.,E_MPa=2.,Cw_mm6=50.,sc_y_mm=0.,sc_z_mm=0.),
        loads=[dict(distributed_torque_CG_N=0.,q_z_N_mm=0.,q_y_N_mm=0.) for _ in range(3)]),
        nodes=[dict(xyz_CG_mm=[x,0.,0.],displacements=dict(rx=0.,psi=0.)) for x in (0.,1000.)])
    assert a._zero_torsional_shear(beam,model)
    constant=copy.deepcopy(beam);constant['torsion_state_parameters']['nodal_phi_psi']=[.1,0.,.1,0.]
    assert not a._zero_torsional_shear(constant,model)
    constant_model=copy.deepcopy(model)
    for n in constant_model['nodes']:n['displacements']['rx']=.1
    assert a._zero_torsional_shear(constant,constant_model)
    change(beam);assert not a._zero_torsional_shear(beam,model)


def test_saved_panorama_is_not_reclassified_by_new_zero_shear_guard(demand,monkeypatch):
    saved=a.assess(demand);before=copy.deepcopy(saved)
    def fail(*args):raise AssertionError('No new applicability assessment on saved read')
    monkeypatch.setattr(a,'_applicability',fail)
    assert a.saved_assessment(demand,saved)==before


def test_rehashed_fake_zero_torsion_is_not_bound_to_real_nodes_and_loads(demand):
    d=copy.deepcopy(demand)
    for case in d['cases']:
        for beam in case['model']['beams']:
            beam['normal_action_polynomials'].update(My_strong_Nmm=[0.],Mz_weak_Nmm=[0.])
            beam['torsion_state_parameters'].update(m_SC_N=0.,nodal_phi_psi=[0.,0.,0.,0.])
        rehash(case['model'])
    checks=byid(a._applicability(d,None))
    assert checks['transverse_shear_resistance']['status']=='not_applicable'
    assert checks['N_M_V_shear_reduction']['status']=='pending'


@pytest.mark.parametrize('field',['L_mm','GJ_Nmm2','ECw_Nmm4'])
def test_zero_torsion_proof_rejects_different_saved_stiffness_or_length(demand,field):
    model=demand['cases'][0]['model'];beam=copy.deepcopy(model['beams'][0])
    beam['torsion_state_parameters'][field]*=1.01
    assert not a._zero_torsional_shear(beam,model)
