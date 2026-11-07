"""Synthetic-only generalization of the qualified Ue125/300 endpoint search."""
import copy
import pytest
from tercas import isolated_en_ue_family as engine
from tercas import en_ue_family_normal_witness as witness
from tercas import en_ue125_300_normal_witness as original
from tercas import en_ue_family_provider as provider
from tercas.en_ue125_300_authority import read
from test_en_ue125_300_endpoint_search import make


@pytest.fixture(scope='module')
def source():
    return make()


@pytest.fixture(scope='module')
def normal():
    return provider.section(26, fyb_MPa=300.)


@pytest.fixture(scope='module')
def stress(source, normal):
    return engine._stress(source, normal, 'Synthetic family endpoints', normal_witness=True)


def test_family_interior_control_has_separate_endpoint(source, normal, stress):
    n=stress['criteria']['normal'];c=n['bound_control']
    assert c['longitudinal_control'] in (1,2)
    assert witness.observe(source, normal, c) is None
    p=n['physical_witness']
    old=original.search_endpoints(source, read(), c)
    assert old is not None and n['observed_exceedance']
    for key in ('location','wall_segment','wall_parameter','face','selected_operators','candidate_search'):
        assert p[key]==old[key]
    assert p['sigma_interval_MPa']==pytest.approx(old['sigma_interval_MPa'], rel=1e-10, abs=1e-8)
    assert p['absolute_sigma_lower_MPa']>300 and not p['physical_maximum_claimed']
    without=engine._stress(source,normal,'Synthetic family endpoints',normal_witness=False)
    for k in ('normal','shear','interaction'):
        assert stress['criteria'][k]['index_upper_bound']==without['criteria'][k]['index_upper_bound']
    assert not without['criteria']['normal']['observed_exceedance']


def test_same_search_algorithm_with_parametric_limit(source, stress):
    # Exact same operator data isolates the search generalization from provider
    # precision differences. This is a helper fixture, not a saved certificate.
    n=read();n['normal_yield_limit_MPa']=300.
    c=stress['criteria']['normal']['bound_control']
    a=original.search_endpoints(source,n,c);b=witness.search_endpoints(source,n,c)
    for p in (a,b):
        p.pop('schema');p.pop('content_sha256')
    assert a==b
    n['normal_yield_limit_MPa']=1e12
    assert witness.search_endpoints(source,n,c) is None


def test_bound_excess_without_endpoint_excess(source,normal):
    # Algebraic operator fixture, deliberately not a qualified solved field.
    d=copy.deepcopy(source);d['loads']=[]
    for side in ('left','right'):d['support_reactions'][side+'_force_xy_N']=[0.,0.]
    base=250*d['section']['properties']['Cw_mm6']/max(abs(v) for v in d['section']['omega_nodes_mm2'])
    for e in d['elements']:
        e['coefficients'].update(B_Nmm2=[base,2*base,-2*base],Tsv_Nmm=[0.],Tw_Nmm=[0.])
    n=engine._stress(d,normal,'Synthetic operator only',normal_witness=True)['criteria']['normal']
    assert n['index_upper_bound']>1
    assert not n['observed_exceedance'] and n['criterion']=='inconclusive_upper_bound'
    assert witness.search_endpoints(d,normal,n['bound_control']) is None


@pytest.mark.parametrize('selector',['longitudinal_control','wall_control','face'])
def test_boolean_selector_rejected(source,normal,stress,selector):
    c=copy.deepcopy(stress['criteria']['normal']['bound_control']);c[selector]=True
    assert witness.search_endpoints(source,normal,c) is None


@pytest.mark.parametrize('scale',[100.,-100.])
def test_large_signed_load_and_rotation_never_approve_physics(normal,scale):
    from tercas import isolated_en_ue125_300 as legacy
    from tercas.torsion_vlasov.vlasov import solve_member
    section=legacy.section_reference()
    d=solve_member(section=section,length_mm=4000.,E_MPa=200000.,G_MPa=77000.,
        actions=[dict(name='P',kind='point',force_xy_N=[1000.*scale,-10000.*scale],
            couple_Nmm=100000.*scale,application_xy_mm=section['properties']['shear_center_xy_mm'],
            s_mm=2000.,origin='synthetic signed high-rotation witness')],
        supports={side:dict(twist='fixed',warping='free_assumed',origin='synthetic') for side in ('left','right')},
        combination_id='SYNTHETIC_HIGH_ROTATION',limit_state='ELU',member_id='QA',
        action_accounting_origin='synthetic',elements_per_interval=8)
    assert d['small_rotation_warning'] is True
    assert abs(d['max_abs_phi']['phi_rad'])>d['numerics']['rotation_warning_rad']
    before=copy.deepcopy(d)
    result=engine.calculate(d,normal_snapshot=normal,model_origin='Synthetic high rotation')
    old=legacy.calculate(d,normal_snapshot=read(),model_origin='Synthetic high rotation')
    assert d==before and result['source_demand']==before
    for r in (result,old):
        assert r['first_order_analysis_qualified'] is False
        assert r['whole_member_approved'] is False and r['global_stability_qualified'] is False
        assert r['source_demand']['small_rotation_warning'] is True
        n=r['stress']['criteria']['normal']
        assert n['observed_exceedance'] is True
        p=n['physical_witness']
        assert p['absolute_sigma_lower_MPa']>300
        assert not p['first_order_analysis_qualified'] and not p['whole_member_approved']
        assert not p['physical_maximum_claimed']
    # Compare the exact same physical point, not potentially different governing
    # union controls. Both helpers independently select the true moment signs.
    p=result['stress']['criteria']['normal']['physical_witness']
    c=copy.deepcopy(result['stress']['criteria']['normal']['bound_control'])
    c.update(longitudinal_control=0 if p['location']['longitudinal_parameter']==0 else 3,
        wall_control=0 if p['wall_parameter']==0 else 2,face=p['face'])
    same=original.observe(d,read(),c)
    assert same is not None
    assert p['selected_operators']==same['selected_operators']
    assert p['sigma_interval_MPa']==pytest.approx(same['sigma_interval_MPa'],rel=1e-10,abs=1e-7)
