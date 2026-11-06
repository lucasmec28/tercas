"""Synthetic pinned section only; no member, mesh, network or user project."""
import copy
from decimal import Decimal, localcontext
import json

import pytest

from tercas import ue_catalog_nbr_weak_mle as mle
from tercas import ue_catalog_nbr_bending as base
from tercas import ue_catalog_reference as own
from tercas.model_domain import VERSION


@pytest.fixture
def data():
    marker = dict(copy.deepcopy(base.PIN), material=copy.deepcopy(base.MATERIAL),
                  geometric_properties=copy.deepcopy(base.GEOMETRY),
                  superseded_section_inputs={'synthetic_legacy': True},
                  old_criticals_inactive=True, whole_member_approved=False)
    return dict(catalog_index=26, load_mode='area', model_domain=VERSION,
                properties=dict(base.GEOMETRY, **base.MATERIAL),
                ue_catalog_reference=marker, Ml_Nmm=123., Mdist_Nmm=456.,
                weak_axis={'positive': {'Ml_Nmm': 789.}}, legacy_note='keep')


def decimal_reference():
    """Independent Decimal fixed-point iteration, not production bisection."""
    with localcontext() as ctx:
        ctx.prec = 55
        D = Decimal
        a, x, iy = map(D, ('491.6953270111933', '15.116450045292856', '170444.94310055477'))
        first, second = a*x, iy+a*x*x
        width = D(117)
        for _ in range(160):
            area = a-D(2)*(117-width)
            center = first/area
            stress = D(300)*(center+1)/(49-center)
            lam = D(117)/2/D('.95')*(stress/D(800000)).sqrt()
            width = D(117)*(1-D('.22')/lam)/lam
        area = a-2*(117-width)
        center = first/area
        inertia = second-first*first/area
        w = inertia/(49-center)
        return tuple(float(z) for z in (width, area, center, inertia, w, w*300/D('1.1')))


def test_local_independent_decimal_and_signed_sides(data):
    cert = mle.qualify(data)
    pos, neg = [cert['local_by_sign'][s] for s in mle.SIGNS]
    sec = pos['section']
    actual = (sec['web_effective_width_mm'], sec['Aef_mm2'],
              sec['centroid_effective_xy_mm'][0], sec['Iyef_mm4'],
              sec['Wfirst_mm3'], pos['MRd_local_Nmm'])
    assert actual == pytest.approx(decimal_reference(), rel=3e-14)
    assert pos['compression_side'] == 'web' and neg['compression_side'] == 'lips'
    assert pos['proof']['first_yield_side'] == 'tension_lips'
    assert neg['MRd_local_Nmm'] == pytest.approx(1371904.1996516583, rel=2e-14)
    assert sec['Wc_web_mm3'] > sec['Wfirst_mm3']
    assert neg['section']['Wc_lips_mm3'] == neg['section']['Wfirst_mm3']


def test_geometry_removal_is_only_central_flat_web(data):
    sec = mle.qualify(data)['local_by_sign']['positive']['section']
    lo, hi = sec['effective_web_y_intervals_mm']
    w = sec['web_effective_width_mm']
    assert lo == [3., 3.+w/2] and hi == [120.-w/2, 120.]
    assert lo[1] < hi[0]
    removed_area = 2*(hi[0]-lo[1])
    assert mle.A-removed_area == pytest.approx(sec['Aef_mm2'])
    assert sec['Aef_mm2']*sec['centroid_effective_xy_mm'][0] == pytest.approx(mle.S)
    assert sec['corners_preserved'] and sec['centroid_effective_xy_mm'][1] == 61.5
    assert sec['Ixyef_mm4'] == 0


def test_other_elements_uniform_majorant_and_bracket(data):
    c = mle.qualify(data)
    p = c['other_elements_proof']
    assert p['Is_mm4'] == pytest.approx(366.166666666667)
    assert p['Is_mm4'] > p['Ia_upper_mm4']
    assert p['flange_lambda'] < .673 and p['lip_lambda'] < .673
    proof = c['local_by_sign']['positive']['proof']
    assert proof['initial_bracket_mm'] == pytest.approx([80.01415360249672,117])
    assert 0 < proof['contraction_upper_bound'] < .306
    assert abs(proof['residual_mm']) < 1e-10
    assert proof['final_bracket_mm'][1]-proof['final_bracket_mm'][0] < 1e-10


def test_saved_replay_no_sources_and_preserves_every_input(data, monkeypatch):
    before = copy.deepcopy(data)
    def fail(*a, **k):
        raise AssertionError('No source/catalogue/geometry/member solve permitted')
    monkeypatch.setattr(own, '_source', fail)
    monkeypatch.setattr(own, 'source_binding', fail)
    cert = mle.qualify(data)
    replay = mle.validate_saved(json.loads(json.dumps(cert)), data)
    assert replay == cert and replay is not cert
    assert data == before
    assert 'MRd_Nmm' not in cert['local_by_sign']['positive']
    assert all(cert[k] is False for k in ('Me_qualified', 'distortional_qualified',
        'complete_bending_capacity_qualified', 'interaction_9_9_qualified',
        'ELS_qualified', 'global_properties_modified', 'whole_member_approved'))


@pytest.mark.parametrize('attack', ['capacity', 'CG', 'bracket', 'sign', 'D', 'bool_number', 'unknown'])
def test_rehashed_tampering_rejected(data, attack):
    c = mle.qualify(data)
    p = c['local_by_sign']['positive']
    if attack == 'capacity': p['MRd_local_Nmm'] *= 1.1
    elif attack == 'CG': p['section']['centroid_effective_xy_mm'][0] += .1
    elif attack == 'bracket': p['proof']['initial_bracket_mm'][0] = 1.
    elif attack == 'sign': p['compression_side'] = 'lips'
    elif attack == 'D': c['distortional_qualified'] = True
    elif attack == 'bool_number': c['whole_member_approved'] = 0
    else: c['MRd_Nmm'] = 1e99
    c.pop('snapshot_sha256')
    c['snapshot_sha256'] = own.digest(c)
    with pytest.raises(ValueError): mle.validate_saved(c, data)


@pytest.mark.parametrize('attack', ['fy', 'G', 'index', 'nodes', 'Iy', 'domain', 'family'])
def test_input_domain_is_pinned(data, attack):
    if attack in ('fy', 'G'): data['properties'][attack+'_MPa'] += 1
    elif attack == 'index': data['catalog_index'] = 25
    elif attack == 'nodes': data[own.FIELD]['nodes_sha256'] = 'a'*64
    elif attack == 'Iy': data['properties']['Iy_cm4'] += 1
    elif attack == 'domain': data['model_domain'] = 'other'
    else: data['member_application'] = 'girt'
    with pytest.raises(ValueError): mle.qualify(data)


def test_unmarked_input_not_implicitly_adopted(data):
    del data[own.FIELD]
    assert mle.qualify(data) is None


@pytest.mark.parametrize('chi', [.05, .2, .5, 1.])
def test_flt_helper_recalculates_section_at_chi_fy(data, chi):
    before = copy.deepcopy(data)
    pos = mle.flt_effective_section(data, 'positive', chi)
    neg = mle.flt_effective_section(data, 'negative', chi)
    assert pos['stress_MPa'] == 300*chi
    lam = 117/2/.95*(300*chi/800000)**.5
    rho = 1 if lam <= .673 else (1-.22/lam)/lam
    assert pos['section']['web_effective_width_mm'] == pytest.approx(117*rho)
    assert neg['section']['web_effective_width_mm'] == 117
    assert neg['Wcef_mm3'] == pytest.approx(5030.315398722746)
    assert not pos['Me_qualified'] and not pos['FLT_resistance_qualified']
    assert pos['local_first_yield_cap_required']
    assert data == before


def test_flt_trial_cannot_replace_tension_first_yield_cap(data):
    local = mle.qualify(data)['local_by_sign']['positive']
    trial = mle.flt_effective_section(data, 'positive', 1.)
    assert trial['section']['web_effective_width_mm'] < local['section']['web_effective_width_mm']
    assert trial['Wcef_mm3']*300/1.1 > local['MRd_local_Nmm']
    assert trial['local_first_yield_cap_required']
    assert 'MRd_Nmm' not in trial and 'MRd_FLT_Nmm' not in trial


@pytest.mark.parametrize('chi', [True, False, 0., -1., 1.0001, float('nan'), float('inf'), '1'])
def test_bad_chi_rejected(data, chi):
    with pytest.raises(ValueError): mle.flt_effective_section(data, 'positive', chi)


@pytest.mark.parametrize('sign', [None, 'web', '', 1])
def test_explicit_sign_required(data, sign):
    with pytest.raises(ValueError): mle.flt_effective_section(data, sign, .5)
