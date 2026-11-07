"""Synthetic endpoint search; controls stay nonphysical and bounds unchanged."""
import copy
import pytest
from tercas import isolated_en_ue125_300 as en
from tercas import en_ue125_300_normal_witness as w
from tercas.en_ue125_300_authority import read
from tercas.torsion_vlasov.vlasov import solve_member
from test_isolated_en_ue125_300 import summary


def make():
    s=en.section_reference();sc=s['properties']['shear_center_xy_mm']
    return solve_member(section=s,length_mm=4000.,E_MPa=200000.,G_MPa=77000.,
        actions=[dict(name='q',kind='uniform',q_xy_N_mm=[0.,-10.],couple_N=0.,application_xy_mm=sc,origin='synthetic endpoint search'),
            dict(name='P',kind='point',force_xy_N=[0.,1000.],couple_Nmm=0.,application_xy_mm=sc,s_mm=1700.,origin='synthetic endpoint search')],
        supports={side:dict(twist='fixed',warping='free_assumed',origin='synthetic') for side in ('left','right')},
        combination_id='SYNTHETIC_ENDPOINTS',limit_state='ELU',member_id='QA',action_accounting_origin='synthetic',elements_per_interval=2)


@pytest.fixture(scope='module')
def source():return make()


@pytest.fixture(scope='module')
def result(source):return en.calculate(source,normal_snapshot=read(),model_origin='Synthetic endpoints')


def test_real_interior_control_finds_separate_physical_endpoint(source,result):
    n=result['stress']['criteria']['normal'];c=n['bound_control']
    assert c['longitudinal_control'] in (1,2)
    assert c['is_physical_state'] is False and w.observe(source,read(),c) is None
    assert n['observed_exceedance'] is True
    p=n['physical_witness'];assert p['absolute_sigma_lower_MPa']>300
    assert p['location']['longitudinal_parameter'] in (0.,1.)
    assert p['wall_parameter'] in (0.,1.) and p['physical_maximum_claimed'] is False
    assert p['candidate_search']['candidate_is_re_evaluated_endpoint'] is True
    assert p['candidate_search']['governing_control_is_physical_state'] is False
    assert p['location']['element_id']==c['source_piece']['element_id'] and p['wall_segment']==c['wall_segment']
    old=en._calculate(source,normal_snapshot=read(),model_origin='Synthetic endpoints',normal_witness=False)
    assert all(old['stress']['criteria'][k]['index_upper_bound']==result['stress']['criteria'][k]['index_upper_bound'] for k in ('normal','shear','interaction'))
    assert old['shear']==result['shear'] and old['mv']==result['mv']
    with en._READ_LOCK:en._VERIFIED_READS.clear()
    assert en.validate_saved(result,summary(source),normal_snapshot=read(),source_sha256=en._sha(source),model_origin='Synthetic endpoints')


def test_operator_hull_excess_without_endpoint_excess_stays_inconclusive(source):
    # Independent polynomial-operator fixture only, deliberately not passed to
    # the qualified member calculator. Endpoints have |sigma|<=250; Bernstein
    # hull can exceed300. An interior hull coefficient must not become a point.
    d=copy.deepcopy(source);d['loads']=[];d['support_reactions']['left_force_xy_N']=[0.,0.];d['support_reactions']['right_force_xy_N']=[0.,0.]
    omega=max(abs(x) for x in d['section']['omega_nodes_mm2']);base=250*d['section']['properties']['Cw_mm6']/omega
    for e in d['elements']:
        e['coefficients']['B_Nmm2']=[base,2*base,-2*base]
        e['coefficients']['Tsv_Nmm']=[0.];e['coefficients']['Tw_Nmm']=[0.]
    z=en._stress(d,read(),'Synthetic polynomial basis',normal_witness=True)['criteria']['normal']
    assert z['index_upper_bound']>1 and z['bound_control']['longitudinal_control'] in (1,2)
    assert z['observed_exceedance'] is False and z['criterion']=='inconclusive_upper_bound'
    assert w.search_endpoints(d,read(),z['bound_control']) is None


@pytest.mark.parametrize('mutation',['location','provenance','sigma','sign','flag'])
def test_endpoint_proof_rehash_corruption_rejected(source,result,mutation):
    r=copy.deepcopy(result);n=r['stress']['criteria']['normal'];p=n['physical_witness']
    if mutation=='location':p['location']['longitudinal_parameter']=.5
    elif mutation=='provenance':p['candidate_search']['governing_longitudinal_control']=0
    elif mutation=='sigma':p['sigma_interval_MPa'][0]*=.5
    elif mutation=='sign':p['selected_operators']['Mx']='Mx_positive'
    else:n['observed_exceedance']=False
    p['content_sha256']=en._sha({k:v for k,v in p.items() if k!='content_sha256'})
    r['stress']['content_sha256']=en._sha({k:v for k,v in r['stress'].items() if k!='content_sha256'})
    r['content_sha256']=en._sha({k:v for k,v in r.items() if k!='content_sha256'})
    with pytest.raises(ValueError):en.validate_saved(r,summary(source),normal_snapshot=read(),source_sha256=en._sha(source),model_origin='Synthetic endpoints')


def test_ambiguous_real_sign_never_selects_union_branch(source,result,monkeypatch):
    original=w._member_polynomials
    def ambiguous(d):
        p,ids=original(d);p['Mx']=en.I(p['Mx'].lo*0-1.,p['Mx'].hi*0+1.)
        return p,ids
    monkeypatch.setattr(w,'_member_polynomials',ambiguous)
    assert w.search_endpoints(source,read(),result['stress']['criteria']['normal']['bound_control']) is None


def test_already_physical_candidate_preserved(source,result):
    p=result['stress']['criteria']['normal']['physical_witness']
    c=copy.deepcopy(result['stress']['criteria']['normal']['bound_control'])
    c.update(longitudinal_control=0 if p['location']['longitudinal_parameter']==0 else 3,
        wall_control=0 if p['wall_parameter']==0 else 2,face=p['face'])
    assert w.search_endpoints(source,read(),c)==w.observe(source,read(),c)
