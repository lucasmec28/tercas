"""Scalar/source-field tests only. Synthetic polynomial fields, no member solve."""
import copy
import math
from pathlib import Path
from fractions import Fraction as F
import pytest
from tercas import isolated_service_mechanics as m
from tercas.torsion_vlasov.section import load_profile


def synthetic(q=.002,phi=0.,B=0.):
    section=load_profile(Path(__file__).parents[1]/'tercas/data/torsion_profiles/ue100x50x17_t1.50.json')
    L=3000.
    return dict(schema='single_vlasov_member_demand_v1',limit_state='ELS',combination_id='SYNTHETIC_FIELD',
        section=section,length_mm=L,E_MPa=200000.,G_MPa=200000/2.6,
        loads=[dict(name='test',kind='uniform',q_xy_N_mm=[0.,-q],couple_N=0.,
                    application_xy_mm=section['properties']['shear_center_xy_mm'],origin='synthetic algebra only')],
        support_reactions={'left_force_xy_N':[0.,q*L/2]},
        elements=[dict(a_mm=0.,b_mm=L,element_id='only',coefficients={
            'phi_rad':[0.,4*phi,-4*phi,0.],'B_Nmm2':[0.,4*B,-4*B,0.],
            'Tsv_Nmm':[0.,0.,0.],'Tw_Nmm':[0.,0.,0.]})],
        numerics={'qualification_passed':True},analysis_domain={'order':1,'axial_force_in_this_model_N':0.,
            'intermediate_braces':False,'sheet_restraint':False},
        max_abs_phi={'phi_rad':phi},small_rotation_warning=abs(phi)>.05)


DIMS={'h':100.,'bf':50.,'lip':17.,'t':1.5,'ri_mm':1.5}
CFG={'point_xy_from_CG_mm':[0.,0.],'projection_xy':[0.,-1.]}


def test_exact_bernstein_bounds_interior_peak_and_nonnegative():
    # t(1-t) has exact peak .25, unlike max at endpoints = 0.
    env=m.envelope([dict(a=F(0),b=F(10),coefficients=[F(0),F(1),F(-1)])])
    assert env['abs_displacement_lower_mm']==.25
    assert .25<=env['abs_displacement_upper_mm']<=.2500001
    assert env['witness']['station_mm']==5.


def test_zero_and_multiple_piece_inventory_not_all_empty_approval():
    with pytest.raises(ValueError):m.envelope([])
    env=m.envelope([dict(a=F(0),b=F(10),coefficients=[F(0)]),
                    dict(a=F(10),b=F(20),coefficients=[F(3)])])
    assert env['abs_displacement_lower_mm']==env['abs_displacement_upper_mm']==3


def test_gross_screen_checks_five_flats_and_all_normal_warping():
    r=synthetic();s=m.gross_screen(r,DIMS,250.)
    assert len(s['walls'])==5 and s['gross_local_normal_sufficient']
    assert s['all_five_walls_and_all_bends_elastic_checked']
    high=m.gross_screen(synthetic(B=1e10),DIMS,250.)
    assert not high['gross_local_normal_sufficient'] and not high['failed_sufficient_screen_is_physical_failure']


def test_uniform_tensor_flexure_matches_closed_form():
    r=synthetic();field=m.displacement_field(r,[0.,0.],[0.,-1.]);env=m.envelope(field)
    I=r['section']['properties']['Ix_strong_mm4'];expected=5*.002*3000**4/(384*200000*I)
    assert env['abs_displacement_lower_mm']<=expected<=env['abs_displacement_upper_mm']
    assert math.isclose(env['abs_displacement_lower_mm'],expected,rel_tol=1e-12)


def test_point_shift_uses_shear_center_arm_and_same_phi_before_envelope():
    r=synthetic(q=0.,phi=.01);sec=r['section']['properties'];dx=12.;dy=30.
    field=m.displacement_field(r,[dx,dy],[0.,-1.]);env=m.envelope(field)
    rx=sec['centroid_xy_mm'][0]-sec['shear_center_xy_mm'][0]+dx
    expected=abs(rx*.01)
    assert math.isclose(env['abs_displacement_lower_mm'],expected,rel_tol=1e-13)
    assert env['abs_displacement_lower_mm']<=expected<=env['abs_displacement_upper_mm']


def test_full_model_comparison_has_index_only_with_sufficient_screen():
    r=synthetic(phi=.00001);before=copy.deepcopy(r);out=m.calculate(r,DIMS,250.,CFG,20.)
    assert r==before and out['index_upper'] is not None
    assert out['criterion_status']=='within_declared_linear_model'
    assert not out['combined_ELS_approved'] and not out['physical_first_order_applicability_qualified']
    failed=m.calculate(synthetic(B=1e10),DIMS,250.,CFG,20.)
    assert failed['index_upper'] is None and failed['criterion_status']=='gross_MLE_sufficient_condition_inconclusive'


def test_large_linear_phi_does_not_create_normative_limit():
    out=m.calculate(synthetic(q=0.,phi=3.),DIMS,250.,CFG,.001)
    assert out['criterion_status']=='above_declared_linear_model'
    assert out['index_lower']>1 and not out['combined_ELS_approved']
    assert out['rotation_screening_warning'] is True


@pytest.mark.parametrize('change',['coverage','ELS','stiffness','width','vector'])
def test_incompatible_source_fails_closed(change):
    r=synthetic();d=copy.deepcopy(DIMS);cfg=copy.deepcopy(CFG)
    if change=='coverage':r['elements'][0]['a_mm']=1.
    if change=='ELS':r['limit_state']='ELU'
    if change=='stiffness':r['section']['properties']['Ix_strong_mm4']*=2
    if change=='width':d['bf']+=1
    if change=='vector':cfg['projection_xy']=[1.,1.]
    with pytest.raises(ValueError):m.calculate(r,d,250.,cfg,20.)


@pytest.mark.parametrize('index',range(83))
def test_catalogue_geometry_is_source_bound_not_old_seven_profile_pins(index):
    from tercas.catalog_torsion_section import prepare
    packet=prepare(index,arc_segments=32);d=dict(packet['nominal_identity']['dimensions_mm'],ri_mm=packet['nominal_identity']['inner_radius_mm'])
    groups,widths=m._flat_ids(packet['section'],d)
    assert len(groups)==len(widths)==5 and all(groups) and min(widths)>0
