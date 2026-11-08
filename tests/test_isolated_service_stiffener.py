"""Synthetic scalar/field tests for the existing §9.2.3 ELS extension."""
import copy
from decimal import localcontext
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from tercas import isolated_service_mechanics as m
from tercas.isolated_service_stiffener import flange_uniform_comparator
from tercas.biaxial_gross import gross_mle as old
from test_isolated_service_mechanics import synthetic,DIMS,CFG


@pytest.mark.parametrize('stress',[0,1,30,100,200,400,1000])
@pytest.mark.parametrize('policy',['linear','shifted_cubic'])
def test_scalar_extraction_matches_pinned_existing_law(stress,policy):
    D=old.D
    with localcontext() as ctx:
        ctx.prec=old.PRECISION
        g=SimpleNamespace(t=D(2),nominal_lip=D(17),E=D(200000),cg=(D(0),D(0)),
            nodes=((D(0),D(1)),(D(42),D(1))),
            walls=(('bottom_lip',0,1,D(13),(D(1),D(0))),))
        wall=('bottom_flange',0,1,D(42),(D(0),D(1)))
        # The old routine adds its outward pad. Feed that SAME majorant to
        # the extraction, so this compares arithmetic rather than field scopes.
        legacy=old.wall_result(g,wall,[(D(0),D(stress)/2)],policy)
        current=flange_uniform_comparator(D(42),g.t,g.nominal_lip,D(13),g.E,
            legacy['maximum_compression_upper_MPa'],stiffener_bound=policy)
        assert all(current[k]==legacy[k] for k in current)


def test_refinement_uses_concurrent_warping_and_retains_no_stiffener_fallback():
    demand=synthetic(q=.3,B=20000.)
    # A nonzero second bending axis and bimoment remain in the SAME field.
    demand['loads'][0]['q_xy_N_mm'][0]=.01
    demand['support_reactions']['left_force_xy_N'][0]=-.01*demand['length_mm']/2
    before=copy.deepcopy(demand)
    legacy=m.calculate(demand,DIMS,250.,CFG,20.,schema=m.LEGACY_SCHEMA)
    current=m.calculate(demand,DIMS,250.,CFG,20.)
    assert demand==before and not legacy['gross_screen']['gross_local_normal_sufficient']
    assert current['gross_screen']['gross_local_normal_sufficient']
    assert legacy['index_upper'] is None and current['index_upper'] is not None
    assert current['envelope']==legacy['envelope']
    assert current['stored_linear_twist_max_rad']==legacy['stored_linear_twist_max_rad']
    assert current['physical_first_order_applicability_qualified'] is False
    assert current['combined_ELS_approved'] is False
    flange=current['gross_screen']['walls'][3]
    assert not flange['uniform_unstiffened_sufficient'] and flange['edge_stiffener']['sufficient']
    assert flange['edge_stiffener']['adjacent_lip_full_under_common_majorant']


def test_lip_compression_and_elastic_guard_cannot_be_ignored():
    base=m.gross_screen(synthetic(q=.3),DIMS,250.,schema=m.LEGACY_SCHEMA)
    base['walls'][4]['compression_upper_MPa']=10000.
    base['walls'][4]['sufficient']=False
    m._refine_stiffened_flanges(base,DIMS)
    flange=base['walls'][3]
    assert flange['edge_stiffener']['common_compression_upper_MPa']==10000.
    assert not flange['edge_stiffener']['adjacent_lip_full_under_common_majorant']
    assert not flange['sufficient'] and not base['gross_local_normal_sufficient']
    high=m.calculate(synthetic(B=1e10),DIMS,250.,CFG,20.)
    assert high['index_lower'] is None and high['index_upper'] is None
    assert high['criterion_status']=='gross_MLE_sufficient_condition_inconclusive'
    elastic=m.gross_screen(synthetic(q=.3),DIMS,1.)
    assert not elastic['elastic_field_sufficient'] and not elastic['gross_local_normal_sufficient']


def test_source_dimensions_are_derived_before_binary_rounding():
    from decimal import Decimal as D
    dims=dict(DIMS,t=1.2,ri_mm=1.2,bf=50.1,lip=17.1)
    screen=m.gross_screen(synthetic(q=.01),DIMS,250.,schema=m.LEGACY_SCHEMA)
    m._refine_stiffened_flanges(screen,dims)
    proof=screen['walls'][3]['edge_stiffener']
    with localcontext() as ctx:
        ctx.prec=old.PRECISION
        t=D(dims['t']);ri=D(dims['ri_mm']);lip=D(dims['lip'])
        b=D(dims['bf'])-2*ri-2*t;d=lip-ri-t
        expected=flange_uniform_comparator(b,t,lip,d,D(screen['E_MPa']),D(proof['common_compression_upper_MPa']))
    assert proof['comparison']==old.unpack(expected)


def test_unknown_arithmetic_version_rejected():
    with pytest.raises(ValueError,match='version'):
        m.calculate(synthetic(),DIMS,250.,CFG,20.,schema='unknown')


def test_legacy_arithmetic_does_not_call_refined_law():
    with patch.object(m,'_refine_stiffened_flanges',side_effect=AssertionError('no upgrade')):
        result=m.calculate(synthetic(q=.3),DIMS,250.,CFG,20.,schema=m.LEGACY_SCHEMA)
    assert result['schema']==m.LEGACY_SCHEMA
    assert all('edge_stiffener' not in w for w in result['gross_screen']['walls'])
    assert result['index_upper'] is None


def test_short_lip_cannot_supply_required_inertia_even_if_local_lambda_passes():
    D=old.D
    with localcontext() as ctx:
        ctx.prec=old.PRECISION
        proof=flange_uniform_comparator(D(42),D(2),D(5),D(1),D(200000),D(100))
    assert proof['lambda_local']<old.LIMIT
    assert proof['Is_mm4']<proof['Ia_monotone_upper_mm4']
    assert proof['full_wall_sufficient'] is False


def test_flange_pass_alone_cannot_bypass_lip_under_common_majorant():
    # Deliberately scalar screen: the lip's own stress is zero, but the common
    # uniform majorant needed for the stiffened subsystem is 350 MPa.
    screen=m.gross_screen(synthetic(q=.3),DIMS,1000.,schema=m.LEGACY_SCHEMA)
    screen['walls'][3].update(compression_upper_MPa=350.,sufficient=False)
    screen['walls'][4].update(compression_upper_MPa=0.,sufficient=True)
    m._refine_stiffened_flanges(screen,dict(DIMS,t=2.,ri_mm=2.,bf=50.,lip=25.))
    wall=screen['walls'][3];proof=wall['edge_stiffener']
    assert proof['comparison']['full_wall_sufficient'] is True
    assert proof['adjacent_lip_full_under_common_majorant'] is False
    assert proof['sufficient'] is False and wall['sufficient'] is False


def test_controls_absent_choice_explains_available_method_without_mutating_inputs():
    from contextlib import nullcontext
    from tercas.isolated_service_ui import controls
    captions=[]
    ui=SimpleNamespace(expander=lambda *a,**k:nullcontext(),
        caption=captions.append,checkbox=lambda *a,**k:False)
    data={'member_application':'purlin','load_mode':'area','selected_types':['ELS frequente']}
    original=copy.deepcopy(data)
    controls(ui,data,'synthetic')
    assert data==original
    assert any('Método disponível, ainda não escolhido' in text for text in captions)


from tercas import pierin_ue_registry as registry


@pytest.mark.parametrize('index',registry.new_study_indices())
def test_all_complete_family_contours_use_scalar_dimensions_not_profile_names(index):
    from tercas.catalog_torsion_section import prepare
    packet=prepare(index,arc_segments=32)
    dims=dict(packet['nominal_identity']['dimensions_mm'],ri_mm=packet['nominal_identity']['inner_radius_mm'])
    demand=synthetic(q=.00001);demand['section']=packet['section']
    screen=m.gross_screen(demand,dims,250.)
    with localcontext() as ctx:
        ctx.prec=old.PRECISION
        t=old.D(dims['t']);ri=old.D(dims['ri_mm']);D=old.D(dims['lip'])
        b=old.D(dims['bf'])-2*ri-2*t;d=D-ri-t
        ratio=D/b;expected_Is=float(t*d**3/12)
    assert len(screen['walls'])==5
    for w in (screen['walls'][1],screen['walls'][3]):
        proof=w['edge_stiffener']
        if ratio<=old.D('.8'):
            assert proof['comparison']['Is_mm4']==expected_Is
            assert proof['comparison']['full_wall_sufficient']
            assert proof['adjacent_lip_full_under_common_majorant']
            assert proof['sufficient']
        else:
            assert proof['comparison'] is None and not proof['sufficient']
            assert 'D/b' in proof['reason']
            assert w['sufficient'] is w['uniform_unstiffened_sufficient']
    # Uniform extreme compression must stay inconclusive, independently of ID.
    extreme=copy.deepcopy(screen)
    for w in extreme['walls']:w.update(compression_upper_MPa=1e9,sufficient=False)
    m._refine_stiffened_flanges(extreme,dims)
    assert not extreme['gross_local_normal_sufficient']
    assert all(not extreme['walls'][i]['edge_stiffener']['sufficient'] for i in (1,3))


def test_stiffener_formula_domain_does_not_leak_acceptance():
    D=old.D
    with localcontext() as ctx:
        ctx.prec=old.PRECISION
        with pytest.raises(ValueError,match='D/b'):
            flange_uniform_comparator(D(20),D(2),D(17),D(13),D(200000),D(100))
