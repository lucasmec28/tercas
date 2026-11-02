"""Regression for stale strong-axis tables after elastic property edits."""
import copy
import json
from io import BytesIO
from pathlib import Path
import pytest
from docx import Document
from tercas.application import build_spec, calculate, defaults, example, rows
from tercas.batch import calculate_batch
from tercas.catalog_scan import inputs_for_section, scan_catalog
from tercas.catalogs import entries
from tercas.report import word, batch_word
from tercas.strong_critical_guard import qualify_strong_criticals


def loaded():
    d = defaults(0)
    d.update(q_uls=.1, q_sls=.1, ELS_limit_mm=3000/180,
             ELS_origin='Teste L/180', route_domain=True)
    d['segments'] = [dict(start_mm=0., end_mm=3000., Ly_effective_mm=3000.,
                          Lz_effective_mm=3000., Cb_mode='one', restraint_provenance='Teste')]
    return d


def test_original_configuration_retained_without_source_poisson_invention():
    d = loaded();s = build_spec(d);q = s['strong_critical_qualification']
    assert q['source_E_MPa'] == 200000.
    assert q['source_G_MPa'] is None and q['source_nu'] is None
    assert q['app_original_G_MPa'] == 77000.
    assert not q['warnings']
    assert s['Ml']['value'] == 4510000. and s['Mdist']['value'] == 2810000.
    r = calculate(d)
    assert r['NBR_branches']['local']['status'] == 'computed'
    assert r['NBR_branches']['distortional']['status'] == 'computed'
    assert r['ELS']['status'] == 'computed_bending_component'


@pytest.mark.parametrize('field,value', [('E_MPa',100000.),('E_MPa',400000.),
 ('G_MPa',38500.),('G_MPa',154000.),('G_MPa',200000/2.6),('E_MPa',None),('G_MPa',None)])
def test_changed_elastic_inputs_remove_criticals_and_dependent_indices(field,value):
    d = loaded();d['properties'][field] = value;before = copy.deepcopy(d);r = calculate(d)
    assert d == before and r['input_data'] == before
    assert r['input_snapshot']['Ml']['value'] is None
    assert r['input_snapshot']['Mdist']['value'] is None
    for branch in ('local','distortional','MV'):
        assert r['NBR_branches'][branch]['status'] == 'not_evaluated'
    assert r['ELS']['status'] == 'not_evaluated'
    assert all('index' not in item for item in r['FLT_segments'])
    for row in rows(r):
        if row['Verificação'] in ('Flexão local','Distorcional','Flexão e cortante concomitantes','Flecha — flexão'):
            assert row['Índice'] is None
    assert len(r['strong_critical_qualification']['warnings']) == 2
    assert not r['whole_member_approved']


@pytest.mark.parametrize('field,value', [('E_MPa',100000.),('G_MPa',38500.)])
def test_legacy_json_and_all_tabulated_profiles_are_guarded(field,value):
    for index, entry in enumerate(entries()):
        d = json.loads(json.dumps(defaults(index)));d['properties'][field] = value;s = build_spec(d)
        for key,label in [('Ml_Nmm','Ml'),('Mdist_Nmm','Mdist')]:
            if entry['critical_values'][key] is not None:
                assert s[label]['value'] is None, (index,key)
                assert s['strong_critical_qualification']['fields'][label]['inherited_tabulated']


@pytest.mark.parametrize('edit', ['origin_only','value_only','one_critical_only'])
def test_no_free_text_or_one_field_escape_from_automatic_inheritance(edit):
    d = loaded();d['properties']['E_MPa'] = 100000.
    if edit == 'origin_only':d['critical_origin'] = 'Texto alterado sem nova análise demonstrada'
    elif edit == 'value_only':d['Ml_Nmm'] *= .5;d['Mdist_Nmm'] *= .5
    else:d['Ml_Nmm'] *= .5;d['critical_origin'] = 'Análise manual independente declarada pelo usuário'
    s = build_spec(d)
    assert s['Mdist']['value'] is None
    if edit != 'one_critical_only':assert s['Ml']['value'] is None
    else:assert s['Ml']['value'] == d['Ml_Nmm']


def test_independent_manual_inputs_unchanged_not_certified():
    d = loaded();d['properties']['E_MPa'] = 100000.
    d.update(Ml_Nmm=1234567.,Mdist_Nmm=2345678.,critical_origin='Análise independente declarada; E=100000 MPa')
    s = build_spec(d)
    assert s['Ml']['value'] == d['Ml_Nmm'] and s['Mdist']['value'] == d['Mdist_Nmm']
    assert not s['strong_critical_qualification']['warnings']
    assert not calculate(d)['whole_member_approved']


def test_restoring_original_configuration_restores_only_original_domain():
    d = loaded();d['properties']['E_MPa'] = 100000.
    assert build_spec(d)['Ml']['value'] is None
    d['properties']['E_MPa'] = 200000.
    assert build_spec(d)['Ml']['value'] == 4510000.
    d['properties']['fy_MPa'] = 300.
    assert build_spec(d)['Ml']['value'] == 4510000.


def test_didactic_synthetic_and_weak_axis_payload_are_not_rewritten():
    assert calculate(example())['NBR_branches']['local']['status'] == 'computed'
    d = loaded();d['weak_axis'] = {'positive':{'Ml_Nmm':123.,'provenance':'Teste independente'}}
    d['properties']['E_MPa'] = 100000.;before = copy.deepcopy(d['weak_axis'])
    qualify_strong_criticals(d)
    assert d['weak_axis'] == before


@pytest.mark.parametrize('field,value', [('E_MPa',100000.),('G_MPa',38500.)])
def test_catalogue_reselection_cannot_restore_incompatible_criticals(field,value):
    d = loaded();d['properties'][field] = value;out = inputs_for_section(d,0)
    assert out['properties'][field] == value and build_spec(out)['Ml']['value'] is None
    result = scan_catalog(d,indices=[0])
    assert result['complete'] and not result['rows'][0]['criteria_satisfied']
    assert any('tabulado do eixo forte' in p for p in result['rows'][0]['pending'])


def test_direct_word_explains_block_and_keeps_original_values():
    d = loaded();d['properties']['G_MPa'] = 38500.;r = calculate(d)
    text = '\n'.join(p.text for p in Document(BytesIO(word(r))).paragraphs)
    assert 'G e ν da fonte não foram explicitados' in text
    assert 'sem escala automática' in text
    assert r['input_data']['Ml_Nmm'] == 4510000.


def test_area_batch_and_word_preserve_pending_status():
    d = loaded();d.update(load_mode='area',selected_types=['ELS rara','ELU normal'])
    d['properties']['E_MPa'] = 100000.;r = calculate_batch(d)
    assert r['cases']
    for c in r['cases']:
        assert any('tabulado do eixo forte' in w for w in c['warnings'])
        for row in c['rows']:
            if row['Verificação'] in ('Flexão local','Distorcional','Flecha — flexão'):
                assert row['Índice'] is None
    text = '\n'.join(p.text for p in Document(BytesIO(batch_word(r))).paragraphs)
    assert 'tabulado do eixo forte' in text


def test_streamlit_imported_custom_E_shows_pending_without_crash():
    from streamlit.testing.v1 import AppTest
    d = loaded();d['steel_name'] = 'Personalizado';d['properties']['E_MPa'] = 100000.
    a = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'))
    a.session_state.base = d;a.run(timeout=30)
    next(b for b in a.button if b.label.startswith('Calcular')).click().run(timeout=30)
    assert not a.exception
    assert a.session_state.result['input_snapshot']['Ml']['value'] is None
    assert any('tabulado do eixo forte' in w.value for w in a.warning)


@pytest.mark.parametrize('E', [100000.,400000.,None])
def test_stale_direct_table12_fallback_blocks_without_rewriting_inputs(E):
    d = defaults(83);before_value = d['Ml_Nmm'];d['properties']['E_MPa'] = E
    original = copy.deepcopy(d);r = calculate(d)
    assert d == original and r['input_data'] == original
    assert before_value == pytest.approx(679828.32598158)
    assert r['input_snapshot']['Ml']['value'] is None
    assert r['NBR_branches']['local']['status'] == 'not_evaluated'
    assert r['ELS']['status'] == 'not_evaluated'
    q = r['strong_critical_qualification']['fields']['Ml']
    assert q['status'] == 'not_evaluated_stale_automatic_table12'
    assert q['formula_nu'] == .3
    assert 'não é ν atribuído a Pierin' in q['formula_nu_origin']
    assert any('Tabela 12' in w for w in r['critical_warnings'])


@pytest.mark.parametrize('index', [83,84,100])
def test_profile_change_recomputed_fallback_has_current_E_and_parameter_evidence(index):
    d = defaults(83);d['properties']['E_MPa'] = 100000.;before = copy.deepcopy(d)
    out = inputs_for_section(d,index);s = build_spec(out)
    assert d == before
    assert out['catalog_index'] == index
    assert s['Ml']['value'] == out['Ml_Nmm']
    q = s['strong_critical_qualification']['fields']['Ml']
    assert q['status'] == 'automatic_table12_recomputed_for_current_E'
    assert q['formula_E_MPa'] == 100000. and q['formula_nu'] == .3
    assert q['formula_parameters']['h'] == out['properties']['h']
    if index == 83:assert s['Ml']['value'] == pytest.approx(339914.16299079)
    assert out['properties']['E_MPa'] == 100000.


def test_manual_table12_critical_retained_with_independent_value_and_origin():
    d = defaults(83);d['properties']['E_MPa'] = 100000.
    d.update(Ml_Nmm=333333.,critical_origin='Recálculo independente informado pelo usuário')
    assert build_spec(d)['Ml']['value'] == 333333.
    d['Ml_Nmm'] = defaults(83)['Ml_Nmm']
    assert build_spec(d)['Ml']['value'] is None


def test_editing_only_auto_table12_value_does_not_requalify():
    d = defaults(83);d['properties']['E_MPa'] = 100000.;d['Ml_Nmm'] *= .5
    assert build_spec(d)['Ml']['value'] is None
    d['properties']['E_MPa'] = 200000.
    assert build_spec(defaults(83))['Ml']['value'] == defaults(83)['Ml_Nmm']


@pytest.mark.parametrize('E', [200000.,400000.])
def test_reediting_E_after_a_catalogue_recalculation_does_not_restore_stale_value(E):
    d = defaults(83);d['properties']['E_MPa'] = 100000.
    scanned = inputs_for_section(d,83)
    assert build_spec(scanned)['Ml']['value'] == pytest.approx(339914.16299079)
    scanned['properties']['E_MPa'] = E
    assert build_spec(scanned)['Ml']['value'] is None
    refreshed = inputs_for_section(scanned,83)
    assert build_spec(refreshed)['Ml']['value'] == refreshed['Ml_Nmm']


@pytest.mark.parametrize('index', [12,83])
@pytest.mark.parametrize('E', [100000.,200000.])
def test_imported_auto_criticals_from_another_profile_are_not_manual(index,E):
    foreign = defaults(0);d = defaults(index);d['properties']['E_MPa'] = E
    for key in ('Ml_Nmm','Mdist_Nmm','critical_origin'):d[key] = foreign[key]
    before = copy.deepcopy(d);r = calculate(d)
    assert d == before
    for key in ('Ml','Mdist'):
        assert r['input_snapshot'][key]['value'] is None
        assert r['strong_critical_qualification']['fields'][key]['status'] == 'not_evaluated_incompatible_catalogue_source'
    assert r['NBR_branches']['local']['status'] == 'not_evaluated'
    assert any('seção/linha' in text for text in r['critical_warnings'])


def test_unused_mdist_warning_does_not_fake_a_coverage_gap_or_block_strong_capacity():
    from tercas.weak_axis import strong_capacity
    d = loaded();fresh = defaults(12)
    for key in ('catalog_index','properties','Ml_Nmm','Mdist_Nmm','critical_origin'):d[key] = fresh[key]
    d['properties']['E_MPa'] = 100000.
    d.update(Ml_Nmm=1234567.,critical_origin='Análise independente declarada para Ml; Mdist não requerido')
    r = calculate(d)
    assert r['NBR_branches']['distortional']['status'] == 'exempt_Table14'
    assert r['NBR_branches']['local']['status'] == 'computed'
    assert r['critical_warnings'] and not r['coverage_warnings']
    assert strong_capacity(r) is not None
    assert r['input_snapshot']['Mdist']['value'] is None
    d['segments'][0]['end_mm'] = 2000.
    gapped = calculate(d)
    assert gapped['coverage_warnings'] and strong_capacity(gapped) is None
