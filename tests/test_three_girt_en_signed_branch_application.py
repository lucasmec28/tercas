"""Light independent guards for signed union; no network solve or UI."""
import copy
import math
from fractions import Fraction
import pytest
from tercas.three_girt_en_normal import application as a
from tercas.three_girt_en_normal import field_envelope as f


def certificate():
    return {'components':{a._component_key(axis,sign):dict(eligible=True,
        sigma_coefficients_c0_cx_cy=[float((1 if sign>0 else 2)*(j+1)),0.,0.])
        for j,axis in enumerate(('N','Mx','My')) for sign in (-1,1)}}


def test_two_actions_enumerate_all_four_operators_and_preserve_subulp_pocket():
    c=certificate();p=dict(N=[0.],Mx=[-1.,3.],My=[-2.,6.])
    intervals=a._integral_sign_intervals(p,c)
    bracket=next(r for r in intervals if r['sign_root_neighborhood'])
    assert len(a._coefficient_branches(bracket,c))==4
    for t in [bracket['left'],bracket['right']]:
        signs={k:(v>0)-(v<0) for k,v in a._exact_actions(p,t).items()}
        assert all(sign==0 or sign in bracket['required_signs'][k] for k,sign in signs.items())
    hidden=f.sign_intervals(dict(N=[0.],Mx=[0.],My=[0.,-5e-324,1e308]))
    assert any(-1 in r['required_signs']['My'] for r in hidden)
    c['components']['My_negative']['eligible']=False
    with pytest.raises(ValueError,match='ineligible'):
        a._coefficient_branches(hidden[0],c)


def test_same_operator_axes_coalesce_without_erasing_distinct_my():
    c=certificate();c['components']['Mx_negative']=copy.deepcopy(c['components']['Mx_positive'])
    p=dict(N=[1.],Mx=[-1.,2.],My=[-1.,3.])
    rows=a._integral_sign_intervals(p,c)
    assert len(rows)==3
    assert rows[-1]['right']==1 and rows[-1]['required_signs']['Mx']==[-1,1]
    assert rows[1]['sign_root_neighborhood']
    assert len(a._coefficient_branches(rows[1],c))==2


def test_exact_sign_is_not_float_summation_sign():
    t=1/3
    assert -1.+3.*t==0.
    value=a._exact_actions(dict(N=[0.],Mx=[-1.,3.],My=[0.]),t)['Mx']
    assert value==Fraction(-1,2**54) and value<0


def test_normal_union_criterion_uses_upper_not_central_witness():
    def record(low,upper,w=True):
        return dict(witness={'normal_index':low} if w else None,
                    index_lower_witness=low if w else None,index_upper_bound=upper)
    r=a._normal_aggregate([record(.9999999999999999,1.0000000000000002)],True)
    assert r['criterion']=='unresolved_numerical_bound'
    r=a._normal_aggregate([record(0.,.8,False)],True)
    assert r['witness'] is None and r['criterion']=='within_1_by_full_interval_upper_bound'
    r=a._normal_aggregate([record(.7,.8)],False)
    assert r['index_upper_bound'] is None and r['partial_index_upper_bound']==.8
    assert r['criterion']=='incomplete_section_branch_coverage'
    with pytest.raises(ArithmeticError):a._normal_aggregate([record(2.,1.)],True)
    with pytest.raises((ValueError,ArithmeticError)):a._normal_aggregate([record(0.,math.nan)],True)


def _physical_fixture(monkeypatch,actual_mx):
    from tercas.three_girt_warping import application as wa
    state=dict(N_N=1.,My_strong_Nmm=-actual_mx,Mz_weak_Nmm=0.,B_equilibrium_Nmm2=0.,
               Vy_N=0.,Vz_N=0.,T_w_Nmm=0.,T_SV_Nmm=0.,side='interior')
    monkeypatch.setattr(wa,'recover_exported_state',lambda *args:state)
    section=dict(nodes_xy_mm=[[0.,0.],[1.,0.]],omega_nodes_mm2=[0.,0.],thickness_mm=1.,
        segment_static_coefficients=[[[0.,0.,0.]]*3],
        properties=dict(centroid_xy_mm=[0.,0.],Cw_mm6=1.,J_mm4=1.,Iy_weak_mm4=1.,Ix_strong_mm4=1.))
    p=dict(N=[1.],Mx=[-1.,3.],My=[0.])
    transport=dict(available=True,original_polynomials_R01=p,centroid_shift_from_gross_mm=[0.,0.],
                   axial_component='N_tension',convention='test')
    ev,discarded=a._physical_witness_evaluator({'model':{},'combination':{'id':'x'}},
        dict(x_start_mm=0.,length_mm=1.,id='b',girt='upper'),section,p,
        dict(h=0.,B0=0.,U=0.,V=0.),certificate(),transport,250.)
    candidate=dict(t=1/3,u=0.,segment_index=0,thickness_face_sign=1,
        xy_relative_to_gross_CG_mm=[0.,.5],normal_xy=[0.,1.],sigma_MPa=999.,tau_MPa=0.)
    return ev,discarded,candidate


def test_isclose_cannot_accept_recovered_wrong_sign(monkeypatch):
    ev,discarded,w=_physical_fixture(monkeypatch,0.)
    assert ev(w) is None
    assert discarded=={'recovered_and_exact_polynomial_sign_disagree':1}


def test_physical_callback_replaces_artificial_coefficient_and_retains_shape(monkeypatch):
    ev,discarded,w=_physical_fixture(monkeypatch,-2**-54)
    physical=ev(w)
    assert physical['selected_component_keys']['Mx']=='Mx_negative'
    assert physical['selected_component_keys']['My'] is None
    assert physical['stress_contributions_MPa']['Mx']==-4*2**-54
    assert physical['sigma_MPa']!=999.
    assert physical['section_fiber']['fiber_xy_relative_to_gross_CG_mm']==[0.,.5]
    assert physical['witness_error_MPa']['sigma']>0
    assert not discarded


@pytest.mark.parametrize('schema',[a.LEGACY_SCHEMA,a.LEGACY_SHEAR_SCHEMA,a.LEGACY_EFFECTIVE_SCHEMA])
def test_historical_schemas_are_read_without_recalculating(schema,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Historical snapshots must not be recomputed')
    monkeypatch.setattr(a,'calculate',forbidden)
    monkeypatch.setattr(a,'build_component_sections',forbidden)
    monkeypatch.setattr(a,'verify_component_sections',lambda certificate:None)
    demand=dict(cases=[],input_fingerprint='historical-source')
    component=dict(schema=schema,rows=[],per_member={},component_sections={},
        source_demand_sha256=a.fingerprint(demand),source_input_fingerprint=demand['input_fingerprint'],
        **{k:False for k in a.FALSE_FLAGS})
    component['content_sha256']=a.fingerprint(component)
    demand[a.FIELD]=component
    assert a.saved_component(demand) is component


def test_nonwinning_nan_lower_rejected():
    records=[dict(witness={'normal_index':.5},index_lower_witness=.5,index_upper_bound=.8),
             dict(witness={'normal_index':math.nan},index_lower_witness=math.nan,index_upper_bound=.8)]
    with pytest.raises(ArithmeticError):a._normal_aggregate(records,True)


def test_saved_v4_upper_cannot_be_relabelled_as_pass():
    bound=a._normal_aggregate([dict(witness={'normal_index':.99},
        index_lower_witness=.99,index_upper_bound=1.01)],True)
    a._validate_saved_bound(bound,True)
    bound['criterion']='within_1_by_full_interval_upper_bound'
    with pytest.raises(ValueError,match='criterion'):a._validate_saved_bound(bound,True)


def test_canonical_early_exit_is_not_a_recovered_exceedance():
    proposal=dict(t=.5,u=0.,segment_index=0,thickness_face_sign=1,
        sigma_MPa=300.,tau_MPa=100.,witness_error_MPa=dict(sigma=.01,tau=.01))
    bound={k:dict(witness=proposal.copy(),index_lower_witness=1.2,index_upper_bound=1.5,
        physical_witness_upper_adjustment=0.,criterion='above_1_at_concomitant_state')
        for k in ('normal','shear','interaction')}
    a._recover_branch_witnesses(bound,lambda w:None,250.)
    for r in bound.values():
        assert r['witness'] is None and r['index_lower_witness'] is None
        assert r['index_upper_bound']==1.5
        assert r['criterion']=='unresolved_numerical_bound'


def test_proposal_only_never_calls_network_recovery(monkeypatch):
    from tercas.three_girt_warping import application as wa
    ev,_,w=_physical_fixture(monkeypatch,-2**-54)
    # Intercept factory arguments by rebuilding the lightweight fixture's
    # closure as proposal mode through its available captured data.
    c=ev.__closure__;values=dict(zip(ev.__code__.co_freevars,(v.cell_contents for v in c)))
    propose,_=a._physical_witness_evaluator(values['case'],values['beam'],values['section'],
        values['polys'],values['torsion'],values['certificate'],values['transport'],values['limit'],proposal_only=True)
    def forbidden(*args):raise AssertionError('Proposal must not recover the network')
    # The factory imports recovery once; create again after patch.
    monkeypatch.setattr(wa,'recover_exported_state',forbidden)
    propose,_=a._physical_witness_evaluator(values['case'],values['beam'],values['section'],
        values['polys'],values['torsion'],values['certificate'],values['transport'],values['limit'],proposal_only=True)
    p=propose(w)
    assert p['selected_component_keys']['Mx']=='Mx_negative'
    assert 'concomitant_7DOF_state' not in p
