"""Saved action extraction only: no capacity, invented contact or solver call."""
import copy
import json
from pathlib import Path
import pytest
from tercas.support_web import sources as s
from tercas.application import example, build_spec, fingerprint
from tercas.inclination_adapter import direct_evidence
from tercas.core.introducao_um_vao import support
from tercas.batch import area_bundle, case_inputs


def isolated(q=1.2,p=0.,web=True):
    d=example();d.update(q_uls=q,P_uls=p,q_parallel_uls=.3,P_parallel_uls=0.,
        left_web=web,right_web=web,support_origin='Synthetic saved web route for both ends')
    return dict(schema='NBR14762_one_span_v1',input_data=d,input_fingerprint=fingerprint(d),
        input_snapshot=build_spec(d),inclination_evidence=direct_evidence(d),
        NBR_branches=dict(supports={k:support('web_connection' if web else None,d['support_origin']) for k in ('left','right')}))


def batch():
    d=isolated()['input_data'];d.update(load_mode='area',selected_types=['ELU normal'])
    d['area_inputs'].update(permanent_kgf_m2=10.,live_kgf_m2=20.,wind_up_kgf_m2=30.,wind_down_kgf_m2=25.)
    bundle=area_bundle(d);cases=[]
    for combo in bundle['combinations']:
        current=case_inputs(d,combo);ev=direct_evidence(current)['ELU']
        if combo.get('point_position')=='support_limit':
            for st in ev['states']:
                for axis in ('normal','parallel'):st[axis]['Rleft_N']+=combo['P_vector'][axis]
            ev['P_vector']=copy.deepcopy(combo['P_vector'])
        cases.append(dict(combination=combo,evidence=dict(inclination=ev,
            NBR_branches=dict(supports={k:support('web_connection',d['support_origin']) for k in ('left','right')}))))
    return dict(schema='tercas_batch_results_v1',input_data=d,input_fingerprint=fingerprint(d),
        common_input_snapshot=dict(selected_section=build_spec(case_inputs(d,bundle['combinations'][0]))['selected_section']),
        load_bundle=bundle,cases=cases)


@pytest.fixture(scope='module')
def network():
    # Two small exact cases create the fixture once. Extraction itself is tested
    # with all solvers and resistance evaluators disabled below.
    from tercas.three_girt_warping.application import calculate,current_configuration
    original=json.loads((Path(__file__).parent/'data/three_girt_normal_QA_input.json').read_text())
    d=original['input_data'];d.update(load_mode='direct',q_uls=1.,q_sls=.5,
        P_uls=0.,P_sls=0.,q_parallel_uls=.2,q_parallel_sls=.1,P_parallel_uls=0.,P_parallel_sls=0.)
    cfg=current_configuration(d,original['configuration']['three_girt'])
    cfg['three_girt'].update(direct_pp_uls_N_mm=.02,direct_pp_sls_N_mm=.02,
        direct_brace_factor_uls=1.25,direct_brace_factor_sls=1.)
    return calculate(d,cfg)


def test_isolated_no_external_P_still_has_two_signed_reactions():
    r=isolated();before=copy.deepcopy(r);out=s.extract(r)
    assert r==before and len(out['supports'])==2
    assert [a['normal_N'] for a in out['supports']]==[-1800.,-1800.]
    assert [a['parallel_N'] for a in out['supports']]==[-450.,-450.]
    assert all(a['trace']['external_P_zero'] for a in out['supports'])
    assert all(a['trace']['reaction_load_convention_N']['normal']==1800. for a in out['supports'])
    assert set(out['legacy_details'])=={'left','right'}
    assert 'source_fingerprint' in out and out['section']['family']=='U'


def test_force_signs_retained_without_inferred_compression():
    out=s.extract(isolated(q=-1.2))
    assert all(a['normal_N']==1800. for a in out['supports'])
    assert all('compression_sign' not in a and 'loaded_flange' not in a for a in out['supports'])


@pytest.mark.parametrize('mutation',[
    lambda r:r['input_data'].update(L_mm=4000.),
    lambda r:r['input_snapshot'].update(L_mm=4000.),
    lambda r:r['input_snapshot']['ULS'].update(q_Nmm=2.),
    lambda r:r['inclination_evidence']['ELU']['P_vector'].update(normal=1.),
    lambda r:r['inclination_evidence']['ELU']['states'][0]['normal'].update(Rleft_N=999.),
    lambda r:r['input_snapshot']['selected_section']['fields']['t'].update(value=99.),
    lambda r:r['input_snapshot']['selected_section'].update(family='Ue'),
])
def test_inconsistent_saved_isolated_demands_rejected(mutation):
    r=isolated();mutation(r)
    with pytest.raises(ValueError):s.extract(r)


def test_legacy_detail_requires_record_origin_and_this_span():
    r=isolated();r['NBR_branches']['supports']['left']['provenance']='Another detail'
    assert set(s.extract(r)['legacy_details'])=={'right'}
    r['input_snapshot']['introduction']['right']['origin']='Another span'
    assert not s.extract(r)['legacy_details']
    assert not s.extract(isolated(web=False))['legacy_details']


def with_contact_contract():
    from tercas.point_contact import blank_choice,reference_basis
    r=isolated(web=False);d=r['input_data'];cfg=blank_choice()
    cfg.update(enabled=True,origin='Saved contract declares web-only end reactions',basis=reference_basis(d))
    cfg['declarations'].update(end_reactions_through_webs=True,no_end_flange_contact=True)
    d['point_contact']=cfg;r['input_fingerprint']=fingerprint(d)
    return r


def test_point_contact_end_web_declaration_reused_even_without_P_or_c():
    r=with_contact_contract();out=s.extract(r)
    assert r['input_data']['P_uls']==0 and r['input_data']['point_contact']['c_mm'] is None
    assert set(out['legacy_details'])=={'left','right'}
    for detail in out['legacy_details'].values():
        assert detail['binding']['declaration_source']=='point_contact'
        assert detail['binding']['contract_fingerprint']==s.fingerprint(r['input_data']['point_contact'])
        assert detail['route']=='web_connection' and detail['connection_design_checked'] is False


@pytest.mark.parametrize('mutation',[
    lambda cfg:cfg.update(enabled=False),
    lambda cfg:cfg.update(origin=''),
    lambda cfg:cfg['basis'].update(L_mm=999.),
    lambda cfg:cfg['declarations'].update(end_reactions_through_webs=False),
    lambda cfg:cfg['declarations'].update(no_end_flange_contact=False),
    lambda cfg:cfg.update(schema='unknown'),
])
def test_missing_or_stale_point_contract_does_not_block_demands_or_create_web_route(mutation):
    r=with_contact_contract();mutation(r['input_data']['point_contact']);r['input_fingerprint']=fingerprint(r['input_data'])
    out=s.extract(r)
    assert len(out['supports'])==2 and not out['legacy_details']


def test_batch_reconstructs_combinations_and_keeps_point_limit():
    r=batch();before=copy.deepcopy(r);out=s.extract(r)
    assert r==before and len(out['supports'])==2*len(r['cases'])
    limits=[a for a in out['supports'] if a['trace']['mathematical_point_limit']]
    assert limits
    for a in limits:
        q=a['trace']['q_vector']['normal'];p=a['trace']['P_vector']['normal'];L=a['trace']['L_mm']
        assert a['normal_N']==pytest.approx(-(q*L/2+(p if a['support_id']=='left' else 0.)))
        assert a['trace']['finite_contact_position_inferred'] is False


@pytest.mark.parametrize('mutation',[
    lambda r:r['cases'].reverse(),
    lambda r:r['cases'][0]['combination'].update(id='OTHER'),
    lambda r:r['load_bundle']['combinations'].pop(),
])
def test_batch_missing_or_reassigned_loads_rejected(mutation):
    r=batch();mutation(r)
    with pytest.raises(ValueError):s.extract(r)


def test_network_own_end_action_not_external_joint_reaction(network,monkeypatch):
    from tercas.three_girt_warping import network as solver
    from tercas.three_girt_axial import application as axial
    def forbidden(*args,**kwargs):raise AssertionError('No solving/capacity during extraction')
    monkeypatch.setattr(solver,'solve',forbidden);monkeypatch.setattr(axial,'_capacities',forbidden)
    before=copy.deepcopy(network);out=s.extract(network)
    assert network==before and len(out['supports'])==6
    assert len(out['intermediate_stations'])==6 and out['ELS_combinations_excluded']==1
    assert not out['legacy_details']
    assert {r['support_id'] for r in out['supports']}=={m+'_'+e for m in ('upper','middle','lower') for e in ('left','right')}
    upper=next(r for r in out['supports'] if r['support_id']=='upper_left');t=upper['trace']
    assert abs(t['external_support_reaction_global_generalized'][0])>1
    assert abs(t['own_girt_end_action_global_generalized'][0])<1e-6
    assert upper['normal_N']==-t['own_girt_end_action_global_generalized'][2]
    assert all(a['trace']['external_P_zero'] for a in out['supports'])
    assert all(len(a['trace']['concomitant_states'])==2 for a in out['intermediate_stations'])
    assert all(not a['is_external_support'] for a in out['intermediate_stations'])


@pytest.mark.parametrize('mutation,rehash',[
    (lambda r:r['cases'][0]['model']['nodes'][0]['support_reactions'].__setitem__(2,123456.),False),
    (lambda r:r['cases'][0]['model']['nodes'][0]['support_reactions'].__setitem__(2,123456.),True),
    (lambda r:r['cases'][0]['model']['nodes'][1]['support_reactions'].__setitem__(2,123456.),True),
    (lambda r:r['cases'][0]['model']['fixed_dofs'].append(dict(node=1,dof='uz')),True),
    (lambda r:r['cases'][0]['model']['bars'][0].update(axial_tension_N=123456.),True),
])
def test_network_saved_demand_tampering_rejected(network,mutation,rehash):
    r=copy.deepcopy(network);mutation(r)
    if rehash:
        model=r['cases'][0]['model'];model['demand_content_sha256']=s.fingerprint({k:v for k,v in model.items() if k!='demand_content_sha256'})
    with pytest.raises(ValueError):s.extract(r)


def test_source_fingerprint_excludes_attached_component(network):
    a=s.extract(network)['source_fingerprint'];r=copy.deepcopy(network)
    r['support_web_component']={'placeholder':'not a source'}
    assert s.extract(r)['source_fingerprint']==a


@pytest.mark.parametrize('source',[{},dict(schema='tercas_three_girt_results_v1'),dict(schema='invented')])
def test_unsupported_source_is_not_silently_migrated(source):
    with pytest.raises(ValueError):s.extract(source)
