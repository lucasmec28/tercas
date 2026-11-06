"""Independent scalar/source checks; public nominal geometry, no project data."""
import copy
import hashlib
from decimal import Decimal, localcontext
import json
import math
from pathlib import Path

import pytest

from tercas import ue_catalog_nbr_bending as bending
from tercas import ue_catalog_nbr_distortional as dist
from tercas import ue_catalog_reference as own
from test_ue_catalog_nbr_bending import section_input


def decimal_elastic():
    """Independent high-precision reassembly, expanded web term and H tensor."""
    with localcontext() as ctx:
        ctx.prec = 50
        D = Decimal
        b, d, t, h, E, G, nu = map(D, ('48', '16', '2', '125', '200000', '77000', '.3'))
        pi = D('3.1415926535897932384626433832795028841971693993751')
        area = t*(b+d)
        ix = t*(t*t*b*b+4*b*d**3+t*t*b*d+d**4)/(12*(b+d))
        iy = t*(b**4+4*d*b**3)/(12*(b+d))
        ixy = t*b*b*d*d/(4*(b+d))
        xo, xh, yo = b*b/(2*(b+d)), -(b*b+2*d*b)/(2*(b+d)), -d*d/(2*(b+d))
        H = b*b*(ix-ixy*ixy/iy)
        length = pi*h*(4*(1-nu*nu)*H/(t**3*h**3)+D(1)/720).sqrt().sqrt()
        z = pi/length
        u2 = (z*h)**2
        fe = E*H*z**4+G*((b+d)*t**3/3)*z*z
        we = E*t**3/(12*(1-nu*nu))*(3/h+D(2)/5*z*z*h+z**4*h**3/240)
        fg = z*z*(ix+iy+area*(xh*xh+yo*yo-2*yo*b*ixy/iy))
        wg = z*z*t*h**3/240*(300+8*u2+u2*u2)/(420+28*u2+u2*u2)
        stress = (fe+we)/(fg+wg)
        W = D('118.12876899091285')*10000/(h/2)
        return {k: float(v) for k, v in dict(Lcrd_mm=length, Ld_mm=length,
            k_phi_fe_N=fe, k_phi_we_N=we, k_phi_fg_mm2=fg, k_phi_wg_mm2=wg,
            Fcrd_MPa=stress, Mdist_Nmm=stress*W, Sfc_mm3=W).items()}


def test_external_historical_benchmark_separate_from_current_arithmetic():
    # RP07-2 pp.11.108-11.111, original kip/in units. This historical formula
    # is test-only. Its 0.5 kip spring is NEVER used in the production section.
    b, d, t, h, E, nu = 1.625-.0566, .5-.0566/2, .0566, 6., 29500., .3
    A, J = (b+d)*t, (b+d)*t**3/3
    Ix = t*(t*t*b*b+4*b*d**3+t*t*b*d+d**4)/(12*(b+d))
    Iy, Ixy = t*(b**4+4*d*b**3)/(12*(b+d)), t*b*b*d*d/(4*(b+d))
    xo, xh, yo = b*b/(2*(b+d)), -(b*b+2*d*b)/(2*(b+d)), -d*d/(2*(b+d))
    H = b*b*(Ix-Ixy*Ixy/Iy)
    L = math.pi*h*(4*(1-nu*nu)*H/(t**3*h**3)+1/720)**.25
    q, u = math.pi/L, math.pi/L*h
    fe = E*H*q**4+E/2.6*J*q*q
    fg_now = q*q*(Ix+Iy+A*(xh*xh+yo*yo-2*yo*b*Ixy/Iy))
    fg_old = fg_now+q*q*A*b*b*(Ixy/Iy)**2
    we_old = E*t**3/(12*(1-nu*nu))*(3/h+19/60*q*q*h+q**4*h**3/240)
    we_now = E*t**3/(12*(1-nu*nu))*(3/h+2/5*q*q*h+q**4*h**3/240)
    wg_old = q*q*t*h**3/240*(300+8*u*u+50/56*u**4)/(420+28*u*u+u**4)
    wg_now = q*q*t*h**3/240*(300+8*u*u+u**4)/(420+28*u*u+u**4)
    old = (fe+we_old+.5)/(fg_old+wg_old)
    now = (fe+we_now+.5)/(fg_now+wg_now)
    assert L == pytest.approx(13.639, abs=.0005)
    assert old == pytest.approx(115.803, abs=.0005)
    assert old*.953 == pytest.approx(110.361, abs=.0005)
    # This value is independent current-equation arithmetic, not a published
    # 2024 golden. It must not be claimed as an unchanged historical benchmark.
    assert now == pytest.approx(119.980585009, rel=2e-11)
    assert now != pytest.approx(old, rel=.001)


def test_current_elastic_terms_independent_decimal(section_input):
    result = dist.qualify(section_input)
    scalar = result['elastic']
    for key, value in decimal_elastic().items():
        assert scalar[key] == pytest.approx(value, rel=2e-14)
    assert scalar['Mdist_Nmm'] == pytest.approx(13999871.753852382, rel=2e-14)
    assert scalar['Lcrd_mm'] == pytest.approx(377.7364353270835, rel=2e-14)
    f = scalar['flange_lip']
    assert [f[k] for k in ('Af_mm2', 'Iyf_mm4', 'Ixyf_mm4', 'xof_mm', 'xhf_mm', 'yof_mm')] == [128., 32256., 4608., 18., -30., -2.]
    assert f['Ixf_mm4'] == pytest.approx(2250.6666666666665)
    assert f['corner_radius_included'] is False
    assert scalar['global_inner_radius_mm'] == 2.
    assert scalar['exterior_fibre_distance_mm'] == 62.5
    assert scalar['G_MPa'] == 77000. and scalar['formula_nu'] == .3
    assert scalar['preliminary_commentary_formula_used'] is False


def test_nbr_only_curve_no_exemption_and_no_combined_promotion(section_input):
    c = bending.qualify(section_input)
    d = c['strong']['distortional']
    r = d['analytical_evidence']['resistance']
    assert r['lambda_dist'] == pytest.approx(math.sqrt(18900.603038546056*300/13999871.753852382))
    assert r['lambda_dist'] < .673 and r['rho_dist'] == 1.
    assert r['MRd_dist_Nmm'] == pytest.approx(18900.603038546056*300/1.1)
    assert r['AISI_strength_factors_used'] is False
    assert d['table14']['exempt'] is False and d['exemption'] is False
    assert c['strong_bending_complete'] is True and c['biaxial_qualified'] is False
    assert c['complete_bending_capacity_qualified'] is False
    assert c['combined_stress_qualified'] is False and c['whole_member_approved'] is False
    assert all(v['MRd_Nmm'] is None for v in c['weak'].values())


def test_no_span_roof_or_moment_gradient_credit_and_inputs_unchanged(section_input):
    before = copy.deepcopy(section_input)
    a = dist.qualify(section_input)
    changed = copy.deepcopy(section_input)
    changed.update(L_mm=8000., q_uls=.7, q_parallel_uls=.2)
    # Section scalar reference is independent of actual superposed demand.
    assert dist.qualify(changed) == a
    assert section_input == before
    e = a['elastic']
    assert e['beta'] == 1. and e['k_phi_N'] == 0. and e['xi_web'] == 2.
    assert e['Lm_mm'] is None and e['Ld_mm'] == e['Lcrd_mm']
    assert e['panel_restraint_credit_used'] is False
    assert e['moment_gradient_credit_used'] is False
    assert all(a['assumptions'][k] is False for k in (
        'physical_holes_verified', 'physical_restraints_verified', 'physical_small_rotation_applicability_verified'))


def test_short_physical_member_keeps_local_but_no_distortional_candidate(section_input):
    full = bending.qualify(section_input)
    cut = full['strong']['distortional']['analytical_evidence']['elastic']['Lcrd_mm']
    data = copy.deepcopy(section_input)
    data['L_mm'] = math.nextafter(cut, -math.inf)
    # Effective lateral lengths must not be relabeled distortional restraints.
    data['Ly_top_mm'] = data['Ly_bottom_mm'] = data['Lz_mm'] = 9000.
    before = copy.deepcopy(data)
    assert dist.qualify(data) is None
    partial = bending.qualify(data)
    d = partial['strong']['distortional']
    assert partial['schema'] == bending.SCHEMA
    assert partial['status'] == 'partial_strong_local_only'
    assert partial['strong']['local'] == full['strong']['local']
    assert partial['strong_bending_complete'] is False
    assert d['status'] == 'not_evaluated'
    assert all(d[k] is None for k in ('Mdist_Nmm', 'MRd_Nmm', 'MRd_dist_Nmm'))
    assert 'analytical_evidence' not in d
    assert d['required_minimum_member_length_mm'] == cut
    assert d['length_scope'] == 'member_shorter_than_qualified_halfwave'
    assert bending.validate_saved(partial, data) == partial
    with pytest.raises(ValueError): bending.validate_saved(full, data)
    with pytest.raises(ValueError): dist.validate_saved(full['strong']['distortional']['analytical_evidence'], data)
    assert data == before
    data['L_mm'] = cut
    assert bending.qualify(data)['strong_bending_complete'] is True
    # The fixed historical v1 calculation has no D and needs no new D guard.
    old = bending._certificate_v1(bending._saved_binding(data))
    data['L_mm'] = 200.
    assert bending.validate_saved(old, data) == old


@pytest.mark.parametrize('invalid', [0., -1., True, float('nan'), float('inf'), None])
def test_invalid_physical_length_cannot_qualify_or_validate_D(section_input, invalid):
    full = dist.qualify(section_input)
    data = copy.deepcopy(section_input)
    data['L_mm'] = invalid
    with pytest.raises(ValueError): dist.qualify(data)
    with pytest.raises(ValueError): dist.validate_saved(full, data)


def test_correlation_receipt_is_public_same_contour_bounded_not_a_floor(section_input):
    c = dist.qualify(section_input)
    same = c['correlation']['same_contour']
    payload = (Path(__file__).resolve().parents[1]/same['receipt']).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == same['receipt_sha256']
    receipt = json.loads(payload)
    assert receipt['nodes_source_sha256'] == c['source_binding']['nodes_sha256']
    assert len(receipt['rows']) == same['finite_strip_solves'] == 6
    fine = next(r for r in receipt['rows'] if r['flats'] == 12 and r['halfwave_mm'] == c['elastic']['Lcrd_mm'])
    coarse = next(r for r in receipt['rows'] if r['flats'] == 4 and r['halfwave_mm'] == c['elastic']['Lcrd_mm'])
    assert fine['eigenvalues_kNm'][0]*1e6 == pytest.approx(same['central_refined_FSM_Mcr_Nmm'], rel=1e-15)
    assert same['central_mesh_relative_change'] == pytest.approx(coarse['eigenvalues_kNm'][0]/fine['eigenvalues_kNm'][0]-1.)
    assert same['analytical_matching_G_Mcr_Nmm'] == receipt['analytical_matching_E_nu']['Mcrd_Nmm']
    assert same['analytic_to_central_refined_FSM'] == receipt['analytical_to_central_refined_first_eigenvalue']
    assert c['guaranteed_lower_bound'] is False and c['exact_modal_eigenvalue'] is False
    assert same['continuous_minimum_proven'] is False
    assert c['correlation']['family']['prediction_to_FSM_standard_deviation'] == .096
    assert max(max(r['residuals']) for r in receipt['rows']) < 1e-6


@pytest.mark.parametrize('schema', ['v1', 'v2'])
def test_saved_bending_versions_are_immutable_without_solver_or_source(section_input, schema, monkeypatch):
    original = (bending._certificate_v1(bending._saved_binding(section_input)) if schema == 'v1'
                else bending.qualify(section_input))
    saved = json.loads(json.dumps(original))
    def forbidden(*a, **k):
        raise AssertionError('Saved reader reopened geometry/source or solver')
    monkeypatch.setattr(own, '_source', forbidden)
    monkeypatch.setattr(own, 'source_binding', forbidden)
    monkeypatch.setattr(bending, 'qualify', forbidden)
    monkeypatch.setattr(dist, 'qualify', forbidden)
    assert bending.validate_saved(saved, section_input) == original
    assert saved == original
    if schema == 'v1':
        assert saved['strong']['distortional']['Mdist_Nmm'] is None
        assert 'strong_bending_complete' not in saved


@pytest.mark.parametrize('mutation', ['Mdist', 'MRd', 'spring', 'beta', 'length', 'nu',
    'flange_radius', 'global_Ix', 'physical', 'floor', 'weak', 'source', 'correlation', 'schema'])
def test_rehashed_distortional_evidence_cannot_expand_scope(section_input, mutation):
    c = dist.qualify(section_input)
    if mutation == 'Mdist': c['elastic']['Mdist_Nmm'] *= 1.01
    elif mutation == 'MRd': c['resistance']['MRd_dist_Nmm'] *= 1.01
    elif mutation == 'spring': c['elastic']['k_phi_N'] = 1.
    elif mutation == 'beta': c['elastic']['beta'] = 1.2
    elif mutation == 'length': c['elastic']['Ld_mm'] = 5000.
    elif mutation == 'nu': c['elastic']['formula_nu'] = 200000/(2*77000)-1
    elif mutation == 'flange_radius': c['elastic']['flange_lip']['corner_radius_included'] = True
    elif mutation == 'global_Ix': c['elastic']['global_Ix_mm4'] *= 1.01
    elif mutation == 'physical': c['assumptions']['physical_small_rotation_applicability_verified'] = True
    elif mutation == 'floor': c['guaranteed_lower_bound'] = True
    elif mutation == 'weak': c['weak_axis_qualified'] = True
    elif mutation == 'source': c['source_documents'][1]['url'] = 'altered'
    elif mutation == 'correlation': c['correlation']['same_contour']['continuous_minimum_proven'] = True
    else: c['schema'] = 'ue_catalog_nbr_distortional_v999'
    c['snapshot_sha256'] = own.digest({k:v for k,v in c.items() if k != 'snapshot_sha256'})
    with pytest.raises(ValueError, match='Mdist'):
        dist.validate_saved(c, section_input)


@pytest.mark.parametrize('mutation', ['biaxial', 'strong', 'nested', 'schema', 'weak'])
def test_nested_rehash_does_not_promote_bending(section_input, mutation):
    c = bending.qualify(section_input)
    if mutation == 'biaxial': c['biaxial_qualified'] = True
    elif mutation == 'strong': c['strong_bending_complete'] = False
    elif mutation == 'schema': c['schema'] = bending.SCHEMA_V1
    elif mutation == 'weak': c['weak']['lips']['MRd_Nmm'] = 500000.
    else:
        nested = c['strong']['distortional']['analytical_evidence']
        nested['elastic']['Mdist_Nmm'] *= 1.01
        nested['snapshot_sha256'] = own.digest({k:v for k,v in nested.items() if k != 'snapshot_sha256'})
    c['snapshot_sha256'] = own.digest({k:v for k,v in c.items() if k != 'snapshot_sha256'})
    with pytest.raises(ValueError): bending.validate_saved(c, section_input)
