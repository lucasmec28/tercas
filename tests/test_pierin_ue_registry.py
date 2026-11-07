"""Documentary/reader checks only: no geometry or member solver."""
import copy
import importlib
import json
import sys

import pytest

from tercas import pierin_ue_registry as registry


def test_complete_inventory_preserves_every_row_and_explains_exclusions():
    out = registry.inventory()
    assert out['total'] == 83
    assert out['complete'] == 66
    assert len(out['incomplete']) == 17
    missing = [f for row in out['incomplete'] for f in row['missing_or_invalid_fields']]
    assert missing.count('critical_values.Ml_Nmm') == 7
    assert missing.count('critical_values.Ndist_N') == 10
    assert len(missing) == 17
    assert all(not r['resistance_qualified_by_registry'] for r in out['records'])
    assert all(not r['whole_member_approved'] for r in out['records'])


def test_unresolved_convention_not_missing_data_and_no_criticals_transferred():
    r = registry.select_new_study(26, include_routes=False)
    assert r['selectable_for_new_study']
    assert r['pierin_reference']['corners'] == 'retos'
    assert r['pierin_reference']['G_MPa'] is None
    assert r['pierin_reference']['nu'] is None
    assert r['geometry_separation']['published_property_convention_unresolved']
    assert not r['geometry_separation']['pierin_criticals_transferred']
    assert not r['geometry_separation']['rounded_contour_generated']


def test_selector_is_explicit_and_does_not_gate_legacy_catalogue():
    from tercas.catalogs import catalog_entry
    indices = registry.new_study_indices()
    assert len(indices) == 66 and 26 in indices and 4 not in indices
    original = copy.deepcopy(catalog_entry(4))
    with pytest.raises(ValueError, match='Incomplete'):
        registry.select_new_study(4)
    assert catalog_entry(4) == original
    assert catalog_entry(4)['critical_values']['Ml_Nmm'] is None
    for index in (True, 26., None, {'h': 125}, -1, 100000):
        with pytest.raises(ValueError):
            registry.select_new_study(index)


def test_records_are_detached_and_json_serializable():
    a = registry.select_new_study(26, include_routes=False)
    a['dimensions_mm']['h'] = 999
    a['raw_source_values'].clear()
    b = registry.select_new_study(26, include_routes=False)
    assert b['dimensions_mm']['h'] == 125
    assert b['raw_source_values']
    json.dumps(b, allow_nan=False)


def test_missing_fields_conflicts_and_duplicate_source_are_visible():
    from tercas.catalogs import catalog_entry
    e = catalog_entry(26)
    r = registry.select_new_study(26, include_routes=False)['pierin_reference']['matching_rows']
    assert registry._completeness(e, r)['complete']
    for value in (None, True, float('nan'), 0, -1):
        changed = copy.deepcopy(e)
        changed['critical_values']['Ndist_N'] = value
        assert 'critical_values.Ndist_N' in registry._completeness(changed, r)['missing_or_invalid_fields']
    assert not registry._completeness(e, r + r)['complete']
    changed = copy.deepcopy(r)
    changed[0]['Mly_Nmm'] += 1
    assert registry._completeness(e, changed)['conflicts']


def test_authorities_remain_bound_to_material_contour_and_signed_branches(monkeypatch):
    # Any accidental derivation call must fail rather than solve during reads.
    for module, names in (
        ('tercas.en_ue_qualified_library', ['build_qualified_component_sections']),
        ('tercas.en_ue_shear', ['build_catalog_shear_capacity', '_derive']),
        ('tercas.en_ue125_shear300', ['build_catalog_shear_capacity', '_derive'])):
        mod = importlib.import_module(module)
        for name in names:
            monkeypatch.setattr(mod, name, lambda *a, **kw: pytest.fail('Unexpected generation'))
    r = registry.select_new_study(26)
    for name in ('EN250_normal', 'EN250_shear', 'EN300_normal', 'EN300_shear'):
        route = r['routes'][name]
        assert route['status'] == 'frozen_section_reference_available'
        b = route['source_binding']
        assert b['nominal_identity']['dimensions_mm'] == r['dimensions_mm']
        assert b['material']['fyb_MPa'] == (300 if '300' in name else 250)
        assert len(b['nodes_sha256']) == 64
        assert route['signed_branches']
        assert not route['application_qualified']
    other = registry.select_new_study(0)
    assert other['routes']['EN300_normal']['status'] == 'unavailable'
    assert other['routes']['EN300_shear']['status'] == 'unavailable'


def test_authority_binding_change_does_not_transfer_authority(monkeypatch):
    from tercas import en_ue_qualified_library as normal
    original = normal.qualified_reference
    def changed(index):
        value = original(index)
        value['source_binding']['nominal_identity']['dimensions_mm']['h'] += 1
        return value
    monkeypatch.setattr(normal, 'qualified_reference', changed)
    assert registry.select_new_study(26)['routes']['EN250_normal']['status'] == 'source_binding_mismatch'


def test_all_rows_still_inspectable_even_when_not_selectable():
    records = registry.table(include_routes=False)
    row = next(r for r in records if r['catalog_index'] == 4)
    assert row['workbook_critical_values']['Ml_Nmm'] is None
    assert not row['selectable_for_new_study']
    assert row['source']['workbook_row']
    assert row['raw_source_values']
    assert len(row['pierin_reference']['matching_rows']) == 1


def test_parameterized_routes_are_described_without_running_methods(monkeypatch):
    from tercas import en_ue_family_kernel, en_ue_family_provider, nbr_ue_family
    for module, name in ((en_ue_family_kernel, 'build'),
                         (en_ue_family_provider, 'section'), (nbr_ue_family, 'assess')):
        monkeypatch.setattr(module, name, lambda *a, **k: pytest.fail('Catalogue browsing computes a method'))
    for index in (0, 26):
        record = registry.select_new_study(index)
        for route in ('EN_parameterized_family', 'NBR_parameterized_family'):
            method = record['routes'][route]
            assert method['status'] == 'method_available_for_new_calculation'
            assert method['requires_complete_documentary_row']
            assert not method['application_qualified'] and not method['whole_member_approved']
