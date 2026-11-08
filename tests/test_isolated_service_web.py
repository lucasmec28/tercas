"""Synthetic full-contour and scalar controls. Never solve a member here."""
import copy
from decimal import localcontext
from fractions import Fraction as F
from unittest.mock import patch
import numpy as np
import pytest

from tercas import isolated_service_mechanics as m
from tercas.biaxial_gross import gross_mle as old
from tercas.isolated_service_web import affine_web_comparator,refine_web
from tercas.torsion_vlasov.intervals import Interval as I
from tercas.pierin_ue_registry import new_study_indices
from test_isolated_service_mechanics import synthetic,DIMS,CFG


def scalar_fixture(left=0.,right=100.):
    section={'nodes_xy_mm':[[0.,0.],[0.,50.],[0.,100.]]}
    dimensions=dict(h=108.,ri_mm=2.,t=2.)
    a=np.empty((1,2,3,3))
    for i in range(2):
        for j in range(3):a[0,i,:,j]=left+(right-left)*(i/2+j/4)
    return section,dimensions,[0,1],[I(a),I(a)]


def prove(args):
    section,dims,ids,fields=args
    return affine_web_comparator(section,dims,200000.,ids,fields)


@pytest.mark.parametrize('edges',[(0.,0.),(100.,100.),(0.,100.),(100.,0.),(30.,100.),(-80.,100.),(-80.,-10.)])
def test_matches_existing_web_index_in_cases_a_b_only(edges):
    args=scalar_fixture(*edges);result=prove(args)
    assert result['dominance_verified'] and result['residual_after_upper_MPa']<=0
    assert 0<=result['psi']<=1 and 4<=result['k']<=8
    assert not result['tensile_edge_credit']
    with localcontext() as ctx:
        ctx.prec=old.PRECISION
        lam,psi,k=old.web_index(list(map(old.D,result['corrected_endpoint_upper_MPa'])),
            old.D(result['comparison_width_upper_mm']),old.D(2),old.D(200000))
    assert result['lambda_local_diagnostic']==float(lam)
    assert result['psi']==float(psi) and result['k']==float(k)


def test_endpoint_maxima_need_not_be_simultaneous_and_uniform_case_stays_k4():
    args=list(scalar_fixture());values=args[-1][0].lo.copy()
    # Opposite spatial gradients at opposite span coefficients. No actual
    # station need simultaneously carry the two endpoint upper bounds.
    values[:,:,0,:]=100-values[:,:,0,:]
    args[-1]=[I(values),I(values)]
    result=prove(args)
    assert result['endpoint_compression_upper_MPa']==[100.,100.]
    assert result['psi']==1 and result['k']==4
    assert result['endpoint_maxima_are_a_comparator_not_a_concomitant_state']


@pytest.mark.parametrize('face',[0,1])
@pytest.mark.parametrize('coefficient',[(0,0,1,1),(0,1,1,0),(0,1,2,1)])
def test_all_interior_segment_and_span_coefficients_receive_residual_correction(face,coefficient):
    args=list(scalar_fixture());values=args[-1][face].lo.copy()
    values[coefficient]=1000.;args[-1][face]=I(values)
    result=prove(args)
    assert result['dominance_verified'] and result['residual_after_upper_MPa']<=0
    assert result['residual_correction_upper_MPa']>=900
    assert result['checked_bernstein_coefficient_count']==36
    assert not result['sufficient']
    # Independently certify coefficientwise dominance with EXACT fractions,
    # not the interval calculations used by the implementation.
    left,right=map(F,result['corrected_endpoint_upper_MPa'])
    for field in args[-1]:
        for i in range(2):
            for j in range(3):
                u=F(i,2)+F(j,4);bound=(1-u)*left+u*right
                assert all(F(float(value))<=bound for value in field.hi[0,i,:,j])


@pytest.mark.parametrize('change',['nonstraight','reordered','missing_segment','missing_face'])
def test_extra_route_fails_closed_outside_exact_geometry_or_complete_field(change):
    args=list(scalar_fixture())
    if change=='nonstraight':args[0]['nodes_xy_mm'][1][0]=1e-14
    elif change=='reordered':args[0]['nodes_xy_mm'][1][1]=101.
    elif change=='missing_segment':args[2]=[0,2]
    else:args[-1]=args[-1][:1]
    result=prove(args)
    assert not result['sufficient'] and result['reason']


def test_extra_route_numeric_failure_cannot_remove_uniform_sufficiency():
    screen=m.gross_screen(synthetic(),DIMS,250.,schema=m.STIFFENED_SCHEMA)
    before=screen['gross_local_normal_sufficient']
    with patch('tercas.isolated_service_web.web_index',side_effect=FloatingPointError('synthetic overflow')):
        section,dims,ids,fields=scalar_fixture()
        refine_web(screen,section,dims,ids,fields)
    assert screen['walls'][2]['uniform_k4_sufficient']
    assert screen['gross_local_normal_sufficient'] is before
    assert screen['walls'][2]['affine_web']['reason']=='synthetic overflow'


def test_unrepresentable_diagnostic_stays_json_finite_and_inconclusive():
    import json
    args=list(scalar_fixture(1.,1.));args[1]['t']=5e-324
    result=prove(args)
    assert result['sufficient'] is False and 'finite JSON' in result['reason']
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize('factor',[1-1e-9,1.,1+1e-9])
def test_uniform_boundary_has_no_favourable_tolerance(factor):
    stress=(.673*.95)**2*4*200000*(2/100)**2*factor
    result=prove(scalar_fixture(stress,stress))
    assert result['sufficient'] is (factor<1)


def test_nominal_width_is_derived_before_rounding_and_serialized_outward():
    args=list(scalar_fixture());args[0]['nodes_xy_mm'][-1][1]=99.
    args[1]=dict(h=108.1,ri_mm=2.,t=2.)
    result=prove(args)
    exact=F(108.1)-8
    assert F(result['comparison_width_upper_mm'])>=exact


def test_refinement_preserves_complete_concurrent_field_and_displacement():
    demand=synthetic(q=.7,B=20000.,phi=.2)
    demand['loads'][0]['q_xy_N_mm'][0]=.001
    demand['support_reactions']['left_force_xy_N'][0]=-.001*demand['length_mm']/2
    original=copy.deepcopy(demand)
    previous=m.calculate(demand,DIMS,250.,CFG,20.,schema=m.STIFFENED_SCHEMA)
    current=m.calculate(demand,DIMS,250.,CFG,20.)
    assert demand==original
    web=current['gross_screen']['walls'][2]
    assert not web['uniform_k4_sufficient'] and web['affine_web']['sufficient']
    assert not previous['gross_screen']['gross_local_normal_sufficient']
    assert current['gross_screen']['gross_local_normal_sufficient']
    assert current['envelope']==previous['envelope']
    assert current['stored_linear_twist_max_rad']==previous['stored_linear_twist_max_rad']==.2
    assert current['rotation_screening_warning']
    assert not current['combined_ELS_approved'] and not current['physical_first_order_applicability_qualified']
    assert current['gross_screen']['von_mises_upper_MPa']==previous['gross_screen']['von_mises_upper_MPa']
    assert all(current['gross_screen']['walls'][i]==previous['gross_screen']['walls'][i] for i in (0,1,3,4))


@pytest.mark.parametrize('schema',[m.LEGACY_SCHEMA,m.STIFFENED_SCHEMA])
def test_historical_versions_never_call_affine_refinement(schema):
    with patch('tercas.isolated_service_web.refine_web',side_effect=AssertionError('no promotion')):
        result=m.calculate(synthetic(),DIMS,250.,CFG,20.,schema=schema)
    assert result['schema']==schema
    assert 'affine_web' not in result['gross_screen']['walls'][2]


@pytest.mark.parametrize('index',new_study_indices())
def test_all_66_complete_contours_use_data_not_profile_name(index):
    from tercas.catalog_torsion_section import prepare
    packet=prepare(index,arc_segments=32)
    d=dict(packet['nominal_identity']['dimensions_mm'],ri_mm=packet['nominal_identity']['inner_radius_mm'])
    demand=synthetic(q=.001,B=20000.)
    demand['section']=packet['section']
    demand['loads'][0]['q_xy_N_mm'][0]=.0001
    demand['support_reactions']['left_force_xy_N'][0]=-.0001*demand['length_mm']/2
    original=copy.deepcopy(demand)
    with patch('tercas.torsion_vlasov.vlasov.solve_member',side_effect=AssertionError('no solver')):
        screen=m.gross_screen(demand,d,250.)
    proof=screen['walls'][2]['affine_web'];groups,_=m._flat_ids(packet['section'],d)
    assert proof['dominance_verified'] and proof['residual_after_upper_MPa']<=0
    assert proof['web_segment_indices']==groups[2]
    assert proof['web_node_count']==len(groups[2])+1
    assert screen['source_section_segments']==len(packet['section']['nodes_xy_mm'])-1
    assert screen['all_five_walls_and_all_bends_elastic_checked'] and len(screen['walls'])==5
    assert demand==original
