"""Synthetic saved-reader controls: no mechanics, solver or private project data."""
import copy
import json
import math
from contextlib import nullcontext

import pytest
from docx import Document

from tercas.application import fingerprint
from tercas.aisi_torsion_component import _base, digest
from tercas.torsion_applicability import saved_notice


def saved_result(*, phi=.2, with_aisi=True):
    data = {'L_mm': 3600., 'synthetic': True}
    identity = fingerprint(data)
    r = dict(schema='tercas_batch_results_v1', input_data=data, input_fingerprint=identity)
    records = []
    for cid, state in [('SYNTHETIC_ULS', 'ELU'), ('SYNTHETIC_SLS', 'ELS')]:
        a = dict(schema='single_vlasov_member_summary_v1', combination_id=cid,
            limit_state=state, length_mm=3600.,
            analysis_domain={'order': 1, 'small_rotation_kinematics': True, 'intermediate_braces': False},
            numerics={'rotation_warning_rad': .05, 'rotation_warning_is_normative_limit': False},
            max_abs_phi={'phi_rad': phi, 'x_mm': 1800.}, small_rotation_warning=abs(phi) > .05)
        records.append(dict(combination_id=cid, limit_state=state, analysis=a,
            source_input_fingerprint=identity))
    r['torsion_evidence'] = dict(schema='purlin_torsion_batch_summary_v1',
        source_input_fingerprint=identity, records=records, computed_cases=2)
    if with_aisi:
        ev = _base(r)
        ev.update(records=[dict(combination_id='SYNTHETIC_ULS', limit_state='ELU',
            G81={'ratio': 1.3}, H4={'ratio': .8, 'witness': {'x_mm': 1200.}, 'whole_member_approved': False},
            whole_member_approved=False, missing=[], first_order_small_rotation_warning=abs(phi) > .05,
            AISI_analysis={'max_abs_phi_rad': abs(phi), 'numerics': copy.deepcopy(records[0]['analysis']['numerics'])})],
            G81_computed_cases=1, H4_computed_cases=1, pending_cases=0,
            source_torsion_snapshot_sha256=digest(r['torsion_evidence']))
        ev['snapshot_sha256'] = digest(ev)
        r['aisi_torsion_component'] = ev
    r['global_verification'] = dict(display_summary='Resumo histórico preservado', status='inconclusivo', checks=[])
    return r


@pytest.fixture(autouse=True)
def no_solver(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Reading a saved result must not solve or rebuild it')
    import tercas.torsion_vlasov.vlasov as vlasov
    import tercas.aisi_torsion_component as aisi
    import tercas.global_verification as global_verification
    for module, name in [(vlasov, 'solve_member'), (aisi, '_aisi_demand'),
                         (aisi, 'solve_member'), (global_verification, 'build_global_verification')]:
        monkeypatch.setattr(module, name, forbidden)


def test_warning_preserves_numbers_status_and_hashes():
    r = saved_result()
    before = copy.deepcopy(r)
    notice = saved_notice(r)
    text = '\n'.join(notice['lines'])
    assert notice['warning'] is True
    assert '2 de 2 combinações' in text and '0,2 rad' in text
    assert 'não previsão do giro físico' in text and 'não é limite normativo' in text
    assert '3600 mm, sem apoio intermediário' in text
    assert '1 de 1 casos ELU com |B|/Ba > 1' in text and 'máximo salvo = 1,3' in text
    assert 'não comprovação de ruptura física' in text and 'condição algébrica' in text
    assert r == before


@pytest.mark.parametrize('phi,warning', [(0., False), (.05, False), (-.05, False),
    (math.nextafter(.05, math.inf), True), (-.2, True)])
def test_existing_screen_exact_boundary_never_approves_first_order(phi, warning):
    r = saved_result(phi=phi)
    notice = saved_notice(r)
    assert notice['warning'] is warning
    assert 'primeira ordem não estabelecida' in notice['lines'][0]
    if not warning:
        assert 'isso não valida a primeira ordem' in notice['lines'][0]


@pytest.mark.parametrize('mutation', ['flag', 'int_flag', 'normative', 'limit', 'phi',
    'identity', 'fingerprint', 'duplicate', 'missing_records', 'computed_count', 'aisi_hash',
    'torsion_hash', 'aisi_flag', 'aisi_phi'])
def test_inconsistent_snapshot_has_no_plausible_quantitative_notice(mutation):
    r = saved_result()
    ev = r['torsion_evidence']; a = ev['records'][0]['analysis']
    if mutation == 'flag': a['small_rotation_warning'] = False
    elif mutation == 'int_flag': a['small_rotation_warning'] = 1
    elif mutation == 'normative': a['numerics']['rotation_warning_is_normative_limit'] = True
    elif mutation == 'limit': a['numerics']['rotation_warning_rad'] = 0
    elif mutation == 'phi': a['max_abs_phi']['phi_rad'] = float('nan')
    elif mutation == 'identity': a['combination_id'] = 'different'
    elif mutation == 'fingerprint': r['input_data']['L_mm'] += 1
    elif mutation == 'duplicate': ev['records'].append(copy.deepcopy(ev['records'][0]))
    elif mutation == 'missing_records': ev['records'] = []
    elif mutation == 'computed_count': ev['computed_cases'] = True
    elif mutation == 'aisi_hash': r['aisi_torsion_component']['records'][0]['G81']['ratio'] = .3
    elif mutation == 'torsion_hash': a['max_abs_phi']['phi_rad'] = .3
    elif mutation in ('aisi_flag', 'aisi_phi'):
        # Even a recomputed storage checksum is not a qualification of a
        # self-contradictory warning/rotation field.
        item = r['aisi_torsion_component']['records'][0]
        if mutation == 'aisi_flag': item['first_order_small_rotation_warning'] = False
        else: item['AISI_analysis']['max_abs_phi_rad'] = True
        ev = r['aisi_torsion_component']
        ev['snapshot_sha256'] = digest({k: v for k, v in ev.items() if k != 'snapshot_sha256'})
    before = copy.deepcopy(r)
    notice = saved_notice(r)
    text = '\n'.join(notice['lines'])
    assert notice['warning'] and 'registro salvo inconsistente' in text
    assert 'Máximo |φ linear|' not in text and 'máximo salvo =' not in text
    assert json.dumps(r, sort_keys=True) == json.dumps(before, sort_keys=True)


class Screen:
    def __init__(self): self.events = []
    def __getattr__(self, name):
        def emit(value, *args, **kwargs):
            self.events.append((name, str(value)))
            return nullcontext()
        return emit


def test_panorama_and_word_warning_precedes_saved_summary_without_rebuild():
    from tercas.study_completion import show_global, report_global
    r = saved_result(); before = copy.deepcopy(r)
    screen = Screen(); show_global(screen, r)
    assert screen.events[0][0] == 'error'
    assert 'Aplicabilidade da análise' in screen.events[0][1]
    assert next(i for i, e in enumerate(screen.events) if 'Resumo histórico' in e[1]) > 0
    doc = Document(); report_global(doc, r)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert text.index('Aplicabilidade da análise') < text.index('Resumo histórico')
    assert '|B|/Ba > 1' in text and r == before


def test_torsion_and_aisi_tables_preserve_diagnostic_indices():
    from tercas.torsion_study_ui import show_result, report, summary_rows
    from tercas.aisi_torsion_ui import show, rows
    r = saved_result(); before = copy.deepcopy(r)
    screen = Screen(); show_result(screen, r)
    assert next(i for i, e in enumerate(screen.events) if 'Aplicabilidade da análise' in e[1]) < next(i for i, e in enumerate(screen.events) if e[0] == 'dataframe')
    row = summary_rows(r['torsion_evidence'])[0]
    assert row['|giro| [rad]'] == .2 and 'Indisponível' in row['Interpretação física']
    ev = r['aisi_torsion_component']; row = rows(ev)[0]
    assert row['G8.1 |B|/Ba'] == 1.3 and row['H4 Mx/Max + My/May + B/Ba'] == .8
    assert 'Indisponível' in row['Interpretação física G8.1/H4']
    screen = Screen(); show(screen, r)
    assert any(kind == 'warning' and '1 de 1 casos ELU' in msg for kind, msg in screen.events)
    doc = Document(); report(doc, r)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert text.index('Aplicabilidade da análise') < text.index('Caso: SYNTHETIC_ULS')
    assert r == before


def test_legacy_without_torsion_is_unchanged_and_unhashed_torsion_still_warns():
    old = {'global_verification': {'display_summary': 'Historical only'}}
    before = copy.deepcopy(old)
    assert saved_notice(old) is None and old == before
    r = saved_result(with_aisi=False)
    before = copy.deepcopy(r)
    assert saved_notice(r)['warning'] is True and r == before
    r['torsion_evidence'] = dict(records=[], computed_cases=0, schema='purlin_torsion_pending_v1')
    assert saved_notice(r) is None


def test_app_panorama_is_called_once_before_component_rendering():
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).parents[1] / 'app.py').read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render_results')
    calls = [n.func.id for n in ast.walk(function) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert calls[0] == 'show_global' and calls.count('show_global') == 1


@pytest.mark.parametrize('malformed', ['analysis', 'numerics', 'overflow'])
def test_aisi_reader_reports_bad_rotation_shape_without_crashing(malformed):
    from tercas.aisi_torsion_ui import show, report
    r = saved_result(); ev = r['aisi_torsion_component']; row = ev['records'][0]
    if malformed == 'analysis': row['AISI_analysis'] = 1
    elif malformed == 'numerics': row['AISI_analysis']['numerics'] = []
    else: row['AISI_analysis']['max_abs_phi_rad'] = 10 ** 400
    ev['snapshot_sha256'] = digest({k: v for k, v in ev.items() if k != 'snapshot_sha256'})
    before = copy.deepcopy(r)
    screen = Screen(); show(screen, r)
    assert any(kind == 'error' and 'Registro do complemento AISI inválido' in msg for kind, msg in screen.events)
    assert not any(kind == 'dataframe' for kind, _ in screen.events)
    doc = Document(); report(doc, r)
    text = '\n'.join(p.text for p in doc.paragraphs)
    assert 'Nenhum índice AISI desse registro foi emitido' in text and r == before


def first_yield_result(*, ratio=1.3, axial=0.):
    """Synthetic complete inputs for the presentation-only H4 lower bound."""
    r = saved_result()
    ev = r['aisi_torsion_component']; row = ev['records'][0]
    ev['bimoment_capacity'] = dict(option='Bn=By; no inelastic Bp option',
        By_Nmm2=200., Bn_Nmm2=200., Ba_Nmm2=180., phi_B=.90,
        physical_product_verified=False)
    row['G81'].update(ratio=ratio, B_Nmm2=ratio*180., Ba_Nmm2=180.)
    row['H4'] = None
    row['AISI_analysis'].update(axial_force_N=axial, analysis_order=1)
    ev.update(H4_computed_cases=0, pending_cases=1)
    ev['snapshot_sha256'] = digest({k: v for k, v in ev.items() if k != 'snapshot_sha256'})
    return r


def test_first_yield_excess_explains_h4_obstruction_without_computing_or_promoting():
    from tercas.aisi_torsion_ui import report, show
    r = first_yield_result(); before = copy.deepcopy(r)
    text = '\n'.join(saved_notice(r)['lines'])
    assert 'Em 1 caso ELU com N=0' in text
    assert 'H4 ≥ |B|/Ba > 1' in text and 'Completar Max/May não elimina esse excesso' in text
    assert 'não é cálculo completo de H4' in text and 'não prova ruptura física' in text
    assert 'não descarta uma alternativa inelástica' in text
    screen = Screen(); show(screen, r)
    assert any(kind == 'warning' and 'H4 ≥ |B|/Ba > 1' in message
               for kind, message in screen.events)
    doc = Document(); report(doc, r)
    assert 'H4 ≥ |B|/Ba > 1' in '\n'.join(p.text for p in doc.paragraphs)
    assert r == before
    ev = r['aisi_torsion_component']
    assert ev['H4_computed_cases'] == 0 and ev['pending_cases'] == 1
    assert ev['records'][0]['H4'] is None and ev['whole_member_approved'] is False
    assert ev['physical_design_approved'] is False


@pytest.mark.parametrize('absence', ['not_exceeded', 'threshold', 'unknown_N', 'nonzero_N',
    'boolean_N', 'unknown_order', 'unknown_option', 'capacity', 'G81'])
def test_h4_obstruction_does_not_infer_missing_domain_or_capacity(absence):
    r = first_yield_result()
    ev = r['aisi_torsion_component']; row = ev['records'][0]
    if absence in ('not_exceeded', 'threshold'):
        ratio = .8 if absence == 'not_exceeded' else 1.
        row['G81'].update(ratio=ratio, B_Nmm2=ratio*180.)
    elif absence == 'unknown_N': row['AISI_analysis'].pop('axial_force_N')
    elif absence == 'nonzero_N': row['AISI_analysis']['axial_force_N'] = 1.
    elif absence == 'boolean_N': row['AISI_analysis']['axial_force_N'] = False
    elif absence == 'unknown_order': row['AISI_analysis'].pop('analysis_order')
    elif absence == 'unknown_option': ev['bimoment_capacity']['option'] = 'Other option'
    elif absence == 'capacity': ev.pop('bimoment_capacity')
    else: row['G81'] = None; ev['G81_computed_cases'] = 0
    ev['snapshot_sha256'] = digest({k: v for k, v in ev.items() if k != 'snapshot_sha256'})
    before = copy.deepcopy(r)
    assert 'H4 ≥ |B|/Ba > 1' not in '\n'.join(saved_notice(r)['lines'])
    assert r == before


@pytest.mark.parametrize('mutation', ['hash', 'Bn', 'Ba', 'B', 'record_Ba',
    'approval', 'physical_approval'])
def test_h4_obstruction_does_not_publish_from_adulterated_saved_evidence(mutation):
    from tercas.aisi_torsion_ui import show, report
    r = first_yield_result()
    ev = r['aisi_torsion_component']; row = ev['records'][0]
    if mutation == 'hash': row['G81']['ratio'] += .1
    elif mutation == 'Bn': ev['bimoment_capacity']['Bn_Nmm2'] += 1
    elif mutation == 'Ba': ev['bimoment_capacity']['Ba_Nmm2'] += 1
    elif mutation == 'B': row['G81']['B_Nmm2'] += 1
    elif mutation == 'record_Ba': row['G81']['Ba_Nmm2'] += 1
    elif mutation == 'approval': ev['whole_member_approved'] = True
    else: ev['physical_design_approved'] = True
    if mutation != 'hash':
        ev['snapshot_sha256'] = digest({k: v for k, v in ev.items() if k != 'snapshot_sha256'})
    before = copy.deepcopy(r)
    notice = saved_notice(r)
    assert 'registro salvo inconsistente' in '\n'.join(notice['lines'])
    assert 'H4 ≥ |B|/Ba > 1' not in '\n'.join(notice['lines'])
    screen = Screen(); show(screen, r)
    assert any(kind == 'error' for kind, _ in screen.events)
    assert not any(kind == 'dataframe' for kind, _ in screen.events)
    doc = Document(); report(doc, r)
    assert 'Nenhum índice AISI desse registro foi emitido' in '\n'.join(p.text for p in doc.paragraphs)
    assert r == before


@pytest.mark.parametrize('phi', [0., 1e-8, -.2, 2., 7.])
def test_prescribed_geometry_visible_in_screen_and_word_without_force_reader(phi, monkeypatch):
    from tercas.torsion_applicability import show, report
    from tercas import rotation_geometry_diagnostic as geometry
    from tercas.report_audit import technical_number
    def forbidden(*args, **kwargs):
        raise AssertionError('Presentation must not enter saved force reader')
    monkeypatch.setattr(geometry, 'saved_maximum_twist_load_lines', forbidden)
    r = saved_result(phi=phi); before = copy.deepcopy(r)
    expected = technical_number(geometry.normalized_rotation_difference(phi))+' vezes o raio'
    screen = Screen(); show(screen, r)
    messages = [msg for _, msg in screen.events if 'Distância geométrica' in msg]
    assert len(messages) == 1
    doc = Document(); report(doc, r)
    paragraphs = [p.text for p in doc.paragraphs if 'Distância geométrica' in p.text]
    assert paragraphs == messages and expected in messages[0]
    for text in ('rotação finita prescrita', 'campo linear salvo', 'não é erro estimado',
                 'nem limite de aceitação', 'Não corrige deslocamento, torque ou equilíbrio',
                 'não calcula flecha relativa à corda'):
        assert text in messages[0]
    assert 'força' not in messages[0] and r == before
    assert saved_notice(r)['warning'] == (abs(phi) > .05)


def test_geometry_is_omitted_for_invalid_or_missing_saved_evidence():
    assert saved_notice({}) is None
    r = saved_result()
    r['input_data']['L_mm'] += 1
    text = '\n'.join(saved_notice(r)['lines'])
    assert 'registro salvo inconsistente' in text and 'Distância geométrica' not in text
