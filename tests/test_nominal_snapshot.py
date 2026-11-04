"""Corrupt optional records must not alter mechanics or break a report."""
import copy
from contextlib import nullcontext
from decimal import Decimal
from io import BytesIO
import json
import math

from docx import Document
import pytest

from tercas.torsion_material import FIELD, preserved_details, deepen
from tercas import torsion_material_ui as ui
from tercas.nominal_snapshot import validate_envelope
from test_torsion_nominal_integration import base, detailed
from test_torsion_nominal_envelope import member, envelope


def packet(result):
    return next(iter(result[FIELD]['records'].values()))


MUTATIONS = [
    'null', 'wrong_root_type', 'records_type', 'missing_fy', 'wrong_fy', 'bool_fy',
    'missing_bounds', 'nan', 'infinite', 'inverted', 'negative_vm', 'bool_bound',
    'wrong_gap', 'wrong_converged', 'int_converged', 'wrong_all_converged',
    'wrong_warning', 'int_warning', 'wrong_phi', 'missing_witness', 'bad_position',
    'bad_face', 'bad_segment', 'wrong_witness_case', 'wrong_witness_state',
    'missing_witness_interval', 'inverted_witness_interval', 'wrong_factor',
    'missing_factor', 'wrong_factor_kind', 'wrong_material_state', 'wrong_scaled_phi',
    'wrong_section', 'wrong_method', 'wrong_actions', 'wrong_lines', 'wrong_supports',
    'wrong_domain', 'wrong_numerics', 'top_approval', 'packet_approval', 'env_approval',
    'resistance_factor', 'missing_hash', 'wrong_status', 'pending_without_reason',
    'wrong_source_fingerprint', 'wrong_source_choice', 'duplicate_source',
    'false_limit', 'bad_section_u', 'huge_segment', 'bad_polynomial_u',
    'tolerance_outside_producer', 'zero_witness', 'wrong_joint_vm',
]


def mutate(result, name):
    if name == 'null': result[FIELD] = None; return
    if name == 'wrong_root_type': result[FIELD] = []; return
    if name == 'records_type': result[FIELD]['records'] = []; return
    p = packet(result); e = p['material_envelope']; v = e['stress_envelopes']['von_mises']; w = v['witness']
    if name == 'missing_fy': del e['fy_MPa']
    elif name == 'wrong_fy': e['fy_MPa'] += 1
    elif name == 'bool_fy': e['fy_MPa'] = True
    elif name == 'missing_bounds': del v['lower_MPa']
    elif name == 'nan': v['upper_MPa'] = math.nan
    elif name == 'infinite': v['upper_MPa'] = math.inf
    elif name == 'inverted': v['upper_MPa'] = v['lower_MPa'] - 1
    elif name == 'negative_vm': v['lower_MPa'] = -1
    elif name == 'bool_bound': v['lower_MPa'] = False
    elif name == 'wrong_gap': v['absolute_gap_MPa'] += 1
    elif name == 'wrong_converged': v['converged'] = not v['converged']
    elif name == 'int_converged': v['converged'] = 1
    elif name == 'wrong_all_converged': e['all_requested_field_bounds_converged'] = False
    elif name == 'wrong_warning': e['source_small_rotation_warning'] = not e['source_small_rotation_warning']
    elif name == 'int_warning': e['source_small_rotation_warning'] = 1
    elif name == 'wrong_phi': e['source_max_abs_phi_rad'] += .1
    elif name == 'missing_witness': del v['witness']
    elif name == 'bad_position': w['longitudinal_state']['x_mm'] = -1
    elif name == 'bad_face': w['saint_venant_face_sign'] = 0
    elif name == 'bad_segment': w['section_segment_index'] = True
    elif name == 'wrong_witness_case': w['longitudinal_state']['combination_id'] = 'wrong'
    elif name == 'wrong_witness_state': w['longitudinal_state']['limit_state'] = 'wrong'
    elif name == 'missing_witness_interval': del w['sigma_midline_MPa_interval']
    elif name == 'inverted_witness_interval': w['sigma_midline_MPa_interval'] = [1., -1.]
    elif name == 'wrong_factor': e['proportional_load_to_nominal_material_yield']['lower'] += .1
    elif name == 'missing_factor': del e['proportional_load_to_nominal_material_yield']
    elif name == 'wrong_factor_kind': e['proportional_load_to_nominal_material_yield']['kind'] = 'exact_zero_field'
    elif name == 'wrong_material_state': e['nominal_material_state'] = 'zero_source_field'
    elif name == 'wrong_scaled_phi': e['algebraic_max_abs_phi_at_nominal_yield_rad']['lower'] += .1
    elif name == 'wrong_section': e['section_content_sha256'] = 'a' * 64
    elif name == 'wrong_method': e['source_method'] = 'other'
    elif name == 'wrong_actions': p['source_actions'][0]['q_xy_N_mm'][0] += .1
    elif name == 'wrong_lines': p['load_lines']['CP']['xy_mm'][0] += .1
    elif name == 'wrong_supports': p['supports']['left']['warping'] = 'fixed'
    elif name == 'wrong_domain': p['source_analysis_domain']['sheet_contact'] = True
    elif name == 'wrong_numerics': p['source_numerics']['qualification_passed'] = False
    elif name == 'top_approval': result[FIELD]['whole_member_approved'] = True
    elif name == 'packet_approval': p['physical_design_approved'] = True
    elif name == 'env_approval': e['physical_design_approved'] = True
    elif name == 'resistance_factor': e['resistance_factor_applied'] = True
    elif name == 'missing_hash': del p['case_model_sha256']
    elif name == 'wrong_status': p['status'] = 'approved'
    elif name == 'pending_without_reason': p.update(material_envelope=None, status='pending_numerical_qualification', missing=[])
    elif name == 'wrong_source_fingerprint': result['torsion_evidence']['source_input_fingerprint'] = 'wrong'
    elif name == 'wrong_source_choice': result['torsion_evidence']['choice_snapshot']['support_hypothesis'] = 'wrong'
    elif name == 'duplicate_source': result['torsion_evidence']['records'].append(copy.deepcopy(result['torsion_evidence']['records'][0]))
    elif name == 'false_limit': w['longitudinal_state']['position_limit'] = 'before P; fake limit'
    elif name == 'bad_section_u': w['section_u'] = 2.
    elif name == 'huge_segment': w['section_segment_index'] = 10000
    elif name == 'bad_polynomial_u': w['polynomial_u'] = -1.
    elif name == 'tolerance_outside_producer': v['requested_relative_tolerance'] = 2.
    elif name == 'zero_witness':
        for key in ('sigma_midline_MPa_interval', 'tau_face_MPa_interval', 'von_mises_MPa_interval'): w[key] = [0., 0.]
    elif name == 'wrong_joint_vm': w['von_mises_MPa_interval'][1] += 1.
    else: raise AssertionError(name)


class Display:
    def __init__(self): self.errors = []; self.captions = []
    def expander(self, *args, **kwargs): return nullcontext()
    def warning(self, *args, **kwargs): pass
    def caption(self, value): self.captions.append(value)
    def error(self, value): self.errors.append(value)
    def markdown(self, value): self.captions.append(value)


def forbid(*args, **kwargs): raise AssertionError('Saved record reading must not recalculate anything')


@pytest.mark.parametrize('name', MUTATIONS)
def test_corrupt_optional_detail_is_visibly_refused_without_mutation_or_solver(detailed, name, monkeypatch):
    bad = copy.deepcopy(detailed); mutate(bad, name)
    before = json.dumps(bad, sort_keys=True)
    monkeypatch.setattr(ui, 'available_cases', lambda result: [])
    monkeypatch.setattr(ui, 'deepen', forbid)
    with pytest.raises((ValueError, TypeError, KeyError, ArithmeticError)):
        preserved_details(bad)
    display = Display()
    assert ui.render(display, bad) is bad
    assert any('anexo nominal salvo é inválido' in text for text in display.errors)
    assert not any('Equivalente nominal de von Mises:' in text for text in display.captions)
    doc = Document(); doc.add_paragraph('Existing base report')
    ui.report(doc, bad)
    assert doc.paragraphs[0].text == 'Existing base report'
    assert any('registro nominal inválido' in p.text for p in doc.paragraphs)
    assert any('nenhum cálculo foi refeito' in p.text for p in doc.paragraphs)
    assert json.dumps(bad, sort_keys=True) == before


def test_invalid_annex_does_not_break_complete_word(detailed, monkeypatch):
    from tercas.report import batch_word
    bad = copy.deepcopy(detailed); mutate(bad, 'missing_fy')
    monkeypatch.setattr(ui, 'deepen', forbid)
    doc = Document(BytesIO(batch_word(bad)))
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert 'registro nominal inválido' in text and 'Identificação das entradas' in text
    assert bad['global_verification'] == detailed['global_verification']


def test_empty_details_and_absent_details_stay_empty_without_output(detailed, base):
    assert preserved_details(base) == {}
    empty = copy.deepcopy(detailed); empty[FIELD]['records'] = {}
    assert preserved_details(empty) == {}
    doc = Document(); doc.add_paragraph('Existing')
    ui.report(doc, empty)
    assert [p.text for p in doc.paragraphs] == ['Existing']


def test_pending_numerical_detail_is_preserved_not_promoted(detailed):
    pending = copy.deepcopy(detailed)
    p = packet(pending)
    p.update(status='pending_numerical_qualification', material_envelope=None,
             missing=['Explicit synthetic failed refinement'])
    before = copy.deepcopy(pending)
    assert preserved_details(pending)
    assert any('Detalhe pendente:' in line for line in ui.text_lines(p))
    assert pending == before


@pytest.mark.parametrize('kind', ['uniform', 'mixed', 'zero', 'endpoint', 'limit'])
def test_valid_envelope_branches_remain_valid(kind):
    analysis = member(kind)
    env = envelope(analysis, max_subdivisions=0, relative_tolerance=1e-12, absolute_tolerance_MPa=1e-12)
    combo = dict(id=analysis['combination_id'], limit_state=analysis['limit_state'], expression='Synthetic branch probe')
    p = dict(combination_id=combo['id'], source_combination=combo, material_envelope=env,
             status='computed_partial_material_envelope' if env['all_requested_field_bounds_converged'] else 'bounded_material_field_not_converged')
    validate_envelope(env, p, analysis, {'input_data': {'properties': {'fy_MPa': 250.}}})
    lines = ui.text_lines(p)
    assert lines
    if kind == 'zero':
        assert env['proportional_load_to_nominal_material_yield']['kind'] == 'exact_zero_field'
    if kind == 'endpoint':
        assert env['proportional_load_to_nominal_material_yield']['upper'] is None
    if kind == 'limit':
        assert env['stress_envelopes']['von_mises']['witness']['longitudinal_state']['element_index'] is None


@pytest.mark.parametrize('value', [0., 1e-309, -1e-309, 1e30, -1e30, 1e308, -1e308])
def test_finite_large_or_subnormal_bounds_round_outwards_without_decimal_failure(value):
    lo = Decimal(ui.bound(value).replace(',', '.'))
    hi = Decimal(ui.bound(value, True).replace(',', '.'))
    assert lo <= Decimal.from_float(value) <= hi


def test_failed_new_request_does_not_repair_invalid_old_details(detailed):
    bad = copy.deepcopy(detailed); mutate(bad, 'missing_fy')
    before = copy.deepcopy(bad)
    with pytest.raises((ValueError, KeyError)):
        deepen(bad, next(iter(bad[FIELD]['records'])))
    assert bad == before


def test_saved_geometry_segment_counts_are_exact_pinned_counts():
    from pathlib import Path
    from tercas.nominal_snapshot import SEGMENT_COUNTS
    from tercas.torsion_vlasov.section import load_profile
    directory = Path(__file__).resolve().parents[1] / 'tercas/data/torsion_profiles'
    actual = {}
    for path in directory.glob('ue*.json'):
        section = load_profile(path)
        actual[section['nodes_sha256']] = len(section['nodes_xy_mm']) - 1
    assert actual == SEGMENT_COUNTS


def test_removed_limit_label_is_refused_while_legitimate_interior_is_allowed():
    from tercas.nominal_snapshot import validate_witness_position
    from tercas.torsion_vlasov.vlasov import evaluate
    analysis = member('limit')
    env = envelope(analysis)
    witness = copy.deepcopy(env['stress_envelopes']['von_mises']['witness'])
    assert witness['longitudinal_state']['element_index'] is None
    validate_witness_position(witness, analysis)
    del witness['longitudinal_state']['position_limit']
    with pytest.raises(ValueError, match='camada limite'):
        validate_witness_position(witness, analysis)
    actual = evaluate(analysis, 0, .5)
    assert actual['side'] == 'interior'
    interior = dict(longitudinal_state=actual, source_piece=0, section_u=.5, polynomial_u=.5)
    validate_witness_position(interior, analysis)
