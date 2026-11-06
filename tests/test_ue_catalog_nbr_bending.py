"""Synthetic section-only checks. No private project input or actions are used."""
import copy
from decimal import Decimal, localcontext
import json

import pytest

from tercas.application import defaults, build_spec
from tercas import direct_self_weight as pp, roof_top_load as roof
from tercas import ue_catalog_reference as own
from tercas import ue_catalog_nbr_bending as nbr
from tercas.strong_critical_guard import qualify_strong_criticals


@pytest.fixture(scope='module')
def section_input():
    data = pp.activate(defaults(26))
    data['roof_top_load'] = roof.choice()
    data['properties'].update(E_MPa=200000., G_MPa=77000., fy_MPa=300., fu_MPa=400.)
    # Synthetic actions intentionally unrelated to any project.
    data.update(L_mm=5000., q_uls=.2, q_sls=.1, P_uls=0., P_sls=0.)
    return own.activate(data)


def test_table12_independent_decimal_polynomial_and_plateau(section_input):
    before = copy.deepcopy(section_input)
    cert = nbr.qualify(section_input)
    local = cert['strong']['local']
    with localcontext() as ctx:
        ctx.prec = 45
        D = Decimal
        eta = D(50) / D(125)
        k = sum(D(c) * eta**i for i, c in enumerate(
            (81, -730, 4261, -12304, 17919, -12796, 3574)))
        w = D('118.12876899091285') * 10000 / D('62.5')
        pi = D('3.141592653589793238462643383279502884197169399')
        ml = k * pi**2 * 200000 / (12 * (1-D('.3')**2)) * (D(2)/125)**2 * w
        lam = (w*300/ml).sqrt()
        assert k == D('25.638464')
        assert lam < D('.673')
    assert local['kl'] == pytest.approx(float(k), rel=1e-13)
    assert local['Ml_Nmm'] == pytest.approx(float(ml), rel=1e-13)
    assert local['lambda_local'] == pytest.approx(float(lam), rel=1e-13)
    assert local['MRd_Nmm'] == pytest.approx(float(w*300/D('1.1')), rel=1e-13)
    assert local['rho_local'] == 1.
    assert local['Wc_mm3'] == local['W_mm3'] == local['Wef_mm3']
    assert local['signs'] == ['positive', 'negative']
    assert local['modal_critical_computed'] is False
    assert section_input == before


def test_table14_independent_interpolation_is_not_exemption(section_input):
    cert = nbr.qualify(section_input)
    dist = cert['strong']['distortional']
    # At bf/bw=.4, table endpoints are (.25 at50) and (.12 at100).
    expected = .25 + (62.5-50)/(100-50)*(.12-.25)
    assert dist['table14']['required_D_bw'] == pytest.approx(expected)
    assert expected == pytest.approx(.2175)
    assert dist['table14']['D_bw'] == pytest.approx(.136)
    assert dist['table14']['required_D_mm'] == pytest.approx(27.1875)
    assert dist['table14']['exempt'] is False and dist['exemption'] is False
    assert dist['Mdist_Nmm'] == pytest.approx(13999871.753852382)
    assert dist['MRd_Nmm'] == pytest.approx(5154709.919603469)
    assert cert['strong_bending_complete'] is True
    assert cert['biaxial_qualified'] is False
    assert cert['complete_bending_capacity_qualified'] is False
    assert all(x['MRd_Nmm'] is None for x in cert['weak'].values())
    assert cert['whole_member_approved'] is False


def test_new_Ml_and_approximate_D_ignore_changed_legacy_criticals(section_input):
    data = copy.deepcopy(section_input)
    data.update(Ml_Nmm=1e12, Mdist_Nmm=2e12, critical_origin='independent claimed text')
    effective, audit = qualify_strong_criticals(data)
    assert effective['Ml']['value'] == pytest.approx(22424085.04996672)
    assert effective['Mdist']['value'] == pytest.approx(13999871.753852382)
    assert audit['fields']['Ml']['inherited_tabulated'] is False
    assert audit['fields']['Ml']['input_value_Nmm'] == 1e12
    assert audit['fields']['Mdist']['input_value_Nmm'] == 2e12
    assert audit[nbr.FIELD]['inherited_criticals_used'] is False
    spec = build_spec(data)
    assert spec['Ml']['value'] == effective['Ml']['value']
    assert spec['Mdist']['value'] == effective['Mdist']['value']


def test_nu_is_explicit_and_original_G_not_changed(section_input):
    cert = nbr.qualify(section_input)
    assert cert['model']['G_MPa'] == 77000.
    assert cert['strong']['local']['formula_nu'] == .3
    assert .3 != section_input['properties']['E_MPa']/(2*77000.)-1
    assert section_input['properties']['G_MPa'] == 77000.


def test_new_Ml_feeds_existing_scalar_Ief_without_claiming_combined_ELS(section_input):
    from tercas.core.protocolo_ief import ief
    spec = build_spec(section_input)
    ml = spec['Ml']['value']
    ig = section_input['properties']['Ix_cm4'] * 1e4
    assert ief(ig, 0., ml) == ig
    assert ief(ig, .25*ml, ml) == ig
    assert ief(ig, 4.*ml, ml) == pytest.approx(.445*ig)
    assert nbr.qualify(section_input)['combined_stress_qualified'] is False


def test_no_certificate_for_different_current_material(section_input):
    data = copy.deepcopy(section_input)
    data['properties']['fy_MPa'] = 250.
    data = own.activate(data)
    assert nbr.qualify(data) is None
    effective, audit = qualify_strong_criticals(data)
    assert effective['Ml']['value'] is None and effective['Mdist']['value'] is None
    assert nbr.FIELD not in audit


def test_no_certificate_for_legacy_or_neighboring_contour(section_input):
    assert nbr.qualify(defaults(26)) is None
    data = pp.activate(defaults(25))
    data['roof_top_load'] = roof.choice()
    data['properties'].update(nbr.MATERIAL)
    assert nbr.qualify(own.activate(data)) is None


@pytest.mark.parametrize('key', ['h', 'bf', 'lip', 't', 'ri_mm', 'Ix_cm4', 'E_MPa', 'G_MPa', 'fy_MPa'])
def test_edit_without_explicit_readoption_rejected(section_input, key):
    data = copy.deepcopy(section_input)
    data['properties'][key] *= 1.01
    with pytest.raises(ValueError):
        nbr.qualify(data)


def test_saved_reader_does_not_reopen_geometry_or_requalify(section_input, monkeypatch):
    cert = nbr.qualify(section_input)
    def fail(*args, **kwargs):
        raise AssertionError('saved reader must not reopen sources or calculate geometry')
    monkeypatch.setattr(own, '_source', fail)
    monkeypatch.setattr(own, 'source_binding', fail)
    monkeypatch.setattr(nbr, 'qualify', fail)
    saved = json.loads(json.dumps(cert, allow_nan=False))
    assert nbr.validate_saved(saved, section_input) == cert


@pytest.mark.parametrize('mutation', ['local', 'dist', 'exemption', 'weak', 'complete', 'approved', 'nu'])
def test_rehashed_capacity_promotion_rejected(section_input, mutation):
    cert = nbr.qualify(section_input)
    if mutation == 'local':
        cert['strong']['local']['MRd_Nmm'] *= 1.1
    elif mutation == 'dist':
        cert['strong']['distortional'].update(status='computed', Mdist_Nmm=1e12, MRd_Nmm=1e12)
    elif mutation == 'exemption':
        cert['strong']['distortional']['table14']['exempt'] = True
    elif mutation == 'weak':
        cert['weak']['web']['MRd_Nmm'] = 1e12
    elif mutation == 'complete':
        cert['complete_bending_capacity_qualified'] = True
    elif mutation == 'approved':
        cert['whole_member_approved'] = True
    elif mutation == 'nu':
        cert['strong']['local']['formula_nu'] = .2987012987012987
    cert['snapshot_sha256'] = own.digest({k: v for k, v in cert.items() if k != 'snapshot_sha256'})
    with pytest.raises(ValueError, match='Evidência NBR'):
        nbr.validate_saved(cert, section_input)


def test_rehashed_geometry_marker_cannot_grant_same_certificate(section_input):
    cert = nbr.qualify(section_input)
    data = copy.deepcopy(section_input)
    marker = data[own.FIELD]
    marker['geometric_properties']['Ix_cm4'] *= 1.001
    data['properties']['Ix_cm4'] = marker['geometric_properties']['Ix_cm4']
    marker['properties_sha256'] = own.digest(marker['geometric_properties'])
    with pytest.raises(ValueError):
        nbr.validate_saved(cert, data)


@pytest.mark.parametrize('mutation', ['girt', 'network', 'malformed_network', 'domain', 'old_reference'])
def test_saved_reader_rechecks_semantic_scope_without_geometry(section_input, mutation, monkeypatch):
    cert = nbr.qualify(section_input)
    data = copy.deepcopy(section_input)
    if mutation == 'girt':
        data['member_application'] = 'wall_girt'
    elif mutation == 'network':
        data['three_girt_model'] = {'enabled': True}
    elif mutation == 'malformed_network':
        data['three_girt_model'] = []
    elif mutation == 'domain':
        data['model_domain'] = 'changed'
    elif mutation == 'old_reference':
        data['ue_reference'] = {}
    # The certificate's hash remains valid. Rehashing an outer result cannot
    # qualify these semantically incompatible declarations either.
    cert['snapshot_sha256'] = own.digest({k: v for k, v in cert.items() if k != 'snapshot_sha256'})
    def fail(*args, **kwargs):
        raise AssertionError('saved reader must not reopen geometry')
    monkeypatch.setattr(own, '_source', fail)
    with pytest.raises(ValueError):
        nbr.validate_saved(cert, data)


@pytest.mark.parametrize('mutation', ['extra', 'missing_audit', 'malformed_audit'])
def test_saved_marker_shape_stays_exact(section_input, mutation):
    cert = nbr.qualify(section_input)
    data = copy.deepcopy(section_input)
    marker = data[own.FIELD]
    if mutation == 'extra':
        marker['unknown_scope_extension'] = True
    elif mutation == 'missing_audit':
        marker.pop('superseded_section_inputs')
    else:
        marker['superseded_section_inputs'] = []
    with pytest.raises(ValueError, match='malformado'):
        nbr.validate_saved(cert, data)
