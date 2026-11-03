from fractions import Fraction
from pathlib import Path
import copy
import json
import math
import numpy as np
import pytest
from tercas import ue_family_reference as f


@pytest.fixture(scope='module')
def base():
    return f.load_reference(1.5,4000.,5.)


@pytest.mark.parametrize('t',[1.5,2.,2.25,2.65,3.,3.35])
def test_six_individual_references(t):
    d=f.load_reference(t,4750.,-5.);r=f.reference(t,4750.)
    assert f.assess(d)['calculable']
    assert d['properties']['t']==d['properties']['ri_mm']==t
    assert d['Mdist_Nmm']==r['source_record']['modal_criticals']['strong_distortional']['value_Nmm']
    assert d['weak_axis']['positive']['Mdist_Nmm']==r['source_record']['weak_web_distortional']['lower_bound_Nmm']
    assert r['resistances_exterior_primary']['weak_web_compressed']['Mdist_identified_Nmm'] is None
    assert r['resistance_release'] is False
    assert r['source_record']['strong_Table14_exemption'] is False


@pytest.mark.parametrize('t',[1.2,1.7,0,True,np.bool_(True),'1.5',None,float('nan'),float('inf')])
def test_unknown_thickness_not_coerced(t):
    with pytest.raises(ValueError):f.reference(t)


@pytest.mark.parametrize('L',[2999.999999,6000.000001,0,-1,True,np.bool_(True),'4000',None,float('nan'),float('inf'),
                              Fraction(3000)-Fraction(1,10**14),Fraction(6000)+Fraction(1,10**14)])
def test_span_domain_no_rounding_or_coercion(L):
    with pytest.raises(ValueError):f.reference(1.5,L)


@pytest.mark.parametrize('L',[3000.,3000.0001,4000.,4750.,5999.9999,6000.])
def test_current_span_criticals_are_recalculated(L):
    r=f.reference(2.25,L)
    assert r['model']['stability_lengths']==dict(Lx_mm=L,Ly_mm=L,Lz_mm=L)
    expected=math.pi**2*200000*r['properties']['Ix_mm4']/L**2
    assert r['global_criticals']['Nex_N']==expected


@pytest.mark.parametrize('mutate',[
    lambda d:d['properties'].update(t=2.),
    lambda d:d['properties'].update(fy_MPa=350.),
    lambda d:d['properties'].update(G_MPa=77000.),
    lambda d:d['properties'].update(ri_mm=1.2),
    lambda d:d['properties'].update(mass_kg_m=2.64),
    lambda d:d.update(Mdist_Nmm=None),
    lambda d:d.update(Mdist_Nmm=7330000.),
    lambda d:d['weak_axis']['positive'].update(Mdist_Nmm=850000.),
    lambda d:d['weak_axis']['positive'].update(plain_u_no_distortion=True),
    lambda d:d['weak_axis']['positive'].update(Cs=-1),
    lambda d:d['weak_axis']['negative'].update(Cs=1),
    lambda d:d['weak_axis']['positive'].update(Wc_mm3=d['weak_axis']['negative']['Wc_mm3']),
    lambda d:d['weak_axis']['positive'].update(provisional_hypothesis=True),
    lambda d:d['segments'][0].update(Lz_effective_mm=2000.),
    lambda d:d['segments'][0].update(Ly_top_effective_mm=2000.),
    lambda d:d['segments'][0].update(Cb_mode='quarter_formula'),
    lambda d:d['ue_family_model'].update(N_N=1.),
    lambda d:d['ue_family_model'].update(imposed_primary_torque_Nmm=1.),
    lambda d:d['ue_family_model'].update(supports='warping restrained'),
    lambda d:d['ue_family_sources'].update(registry_sha256='0'*64),
    lambda d:d['ue_family_sources']['web_bound_source'].update(sha256='0'*64),
    lambda d:d.update(member_application='wall_girt'),
    lambda d:d.update(model_domain='panel_restraint'),
    lambda d:d.update(route_domain=False),
    lambda d:d.update(L_mm=5000.),
    lambda d:d.update(synthetic=False),
    lambda d:d.update(whole_member_approved=True),
    lambda d:d.update(ue_model={}),
    lambda d:d.update(weak_catalog={}),
    lambda d:d['inclination'].update(permanent_basis='horizontal'),
    lambda d:d['properties'].update(unknown=1),
])
def test_protected_mutations_fail_closed_without_repair(base,mutate):
    d=copy.deepcopy(base);mutate(d);before=copy.deepcopy(d)
    s=f.assess(d)
    assert not s['eligible'] and not s['calculable'] and d==before
    with pytest.raises(ValueError):f.activate(d)


def test_token_not_qualification(base):
    d=copy.deepcopy(base);d['properties']['Ix_cm4']*=1.01
    assert d[f.FIELD]==base[f.FIELD]
    assert not f.assess(d)['calculable']


def test_unactivated_exact_source_requires_activation():
    d=f.source(3.,3000.);s=f.assess(d)
    assert s['eligible'] and not s['active'] and not s['calculable']
    with pytest.raises(ValueError):f.calculate_reference(d)


def test_missing_or_swapped_token(base):
    for token in ({'schema':f.VERSION,'reference_id':'other'},True,{},None):
        d=copy.deepcopy(base);d[f.FIELD]=token
        assert not f.assess(d)['calculable']


@pytest.mark.parametrize('value',[None,[],1,'unknown',True])
def test_malformed_properties_are_ineligible_not_unhandled_exception(base,value):
    d=copy.deepcopy(base);d['properties']=value
    state=f.assess(d)
    assert not state['eligible'] and not state['calculable']
    with pytest.raises(ValueError):f.calculate_reference(d)


@pytest.mark.parametrize('key,value',[
    ('spacing_m',0.),('permanent_kgf_m2',-1.),('live_kgf_m2',float('nan')),('wind_up_kgf_m2',True)])
def test_bad_area_action_blocks_but_does_not_repair_identity(base,key,value):
    d=copy.deepcopy(base);d['area_inputs'][key]=value
    assert not f.assess(d)['calculable']


def test_editable_actions_and_source_roundtrip(base):
    d=copy.deepcopy(base);d.update(project='Ensaio editado',actions_origin='Ações sintéticas editadas explicitamente')
    d['area_inputs']['permanent_kgf_m2']=17.;d['inclination']['value']=-15.
    assert f.assess(d)['calculable']
    assert f.assess(json.loads(json.dumps(d)))==f.assess(d)


def test_span_change_preserves_actions_and_updates_global_inputs(base):
    d=copy.deepcopy(base);d['area_inputs']['wind_down_kgf_m2']=77.
    z=f.apply_span(d,4750.)
    assert d['L_mm']==4000. and z['L_mm']==4750.
    assert z['area_inputs']==d['area_inputs']
    assert z['weak_axis']['positive']['Nex_N']!=d['weak_axis']['positive']['Nex_N']
    assert z['weak_axis']['positive']['Mdist_Nmm']==d['weak_axis']['positive']['Mdist_Nmm']
    assert f.assess(z)['calculable']


def test_direct_position_invalid_after_span_change_is_not_silently_clamped():
    d=f.load_reference(2.,6000.,0.)
    d.update(load_mode='direct',x_uls=5000.,x_sls=5000.)
    z=f.apply_span(d,3000.)
    assert z['x_uls']==5000. and z['x_sls']==5000.
    assert not f.assess(z)['calculable']


def test_web_floor_is_actual_governing_component_for_t150():
    a=f.reference(1.5,4000.)['resistances_exterior_primary']['weak_web_compressed']
    assert a['governing_branches']==['distortional']
    assert a['MRd_Nmm']==a['MRd_dist_Nmm']<a['MRd_local_Nmm']
    assert a['rho_dist']==pytest.approx(.9118249332589479)


@pytest.mark.parametrize('t',f.THICKNESSES)
def test_two_separate_floor_scalar_proofs(t):
    r=f.reference(t,4000.)['resistances_exterior_primary']['weak_web_compressed']
    p=f.floor_scalar_proof(r['W_mm3'],250.,r['Mdist_lower_bound_Nmm'])
    assert p['conservative_for_all_critical_at_least_floor'] is True
    assert p['literal_curve_globally_monotone_claimed'] is False
    assert p['Mdist_identified_Nmm'] is None
    assert p['proof_branch'].startswith('active' if t==1.5 else 'entire')


def test_literal_rounded_transition_is_not_silently_called_monotone():
    W,fy=4000.,250.
    lam=.67300001
    floor=W*fy/lam**2
    assert f._rho(lam)>1.
    with pytest.raises(ValueError,match='curva literal'):f.floor_scalar_proof(W,fy,floor)


def test_frozen_backend_remains_intact():
    assert len(f.gate())==6
