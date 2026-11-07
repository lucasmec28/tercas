"""Read-only Ue study registry derived from existing documentary sources.

Completeness is a selection policy, never resistance qualification. Historical
readers do not call this module. No geometry, resistance or member is generated.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'pierin_ue_documentary_registry_v1'
COMPLETENESS_POLICY = 'exact_nominal_row_dimensions_published_properties_five_criticals_v1'
DIMENSIONS = ('h', 'bf', 'lip', 't')
PROPERTIES = ('mass_kg_m', 'A_cm2', 'Ix_cm4', 'Wx_cm3', 'Iy_cm4',
              'J_mm4', 'Cw_mm6', 'ri_mm')
CRITICALS = ('Nl_N', 'Ndist_N', 'Ml_Nmm', 'Mdist_Nmm', 'Mly_Nmm')
DATA = Path(__file__).parent


def _read(relative):
    raw = (DATA / relative).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _completeness(entry, matches):
    missing = []
    for group, keys in (('dimensions_mm', DIMENSIONS),
                        ('published_properties', PROPERTIES), ('critical_values', CRITICALS)):
        for key in keys:
            if not _positive(entry.get(group, {}).get(key)):
                missing.append(group + '.' + key)
    for key in ('id', 'source_url', 'critical_source'):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            missing.append(key)
    if len(matches) != 1:
        missing.append('exact_unique_Pierin_nominal_row')
    elif not _positive(matches[0].get('Mly_Nmm')):
        missing.append('Pierin_reference.Mly_Nmm')
    conflicts = []
    if len(matches) == 1 and entry.get('critical_values', {}).get('Mly_Nmm') != matches[0].get('Mly_Nmm'):
        conflicts.append('Workbook and adopted Pierin Mly differ; both preserved.')
    return dict(policy=COMPLETENESS_POLICY, complete=not missing and not conflicts,
                missing_or_invalid_fields=missing, conflicts=conflicts,
                scope='Documentary values only; source G/nu/sign and physical product remain unverified.')


def _bound(entry, index, binding):
    """Nominal row link only; retain full contour/material key for consumers."""
    identity = binding.get('nominal_identity', {})
    return (type(binding.get('catalog_index')) is int
            and binding['catalog_index'] == index
            and binding.get('catalog_id') == entry['id']
            and identity.get('catalog_id') == entry['id']
            and identity.get('dimensions_mm') == entry['dimensions_mm']
            and identity.get('inner_radius_mm') == entry['published_properties']['ri_mm'])


def _route(provider, entry, index, binding, branches, digest, **extra):
    matched = _bound(entry, index, binding)
    return dict(provider=provider,
                status='frozen_section_reference_available' if matched else 'source_binding_mismatch',
                reason=('Read the original authority and recheck exact contour, material, sign and application domain.'
                        if matched else 'Authority and documentary nominal identity differ; not selectable as authority.'),
                source_binding=copy.deepcopy(binding), signed_branches=copy.deepcopy(branches),
                authority_sha256=digest, application_qualified=False,
                whole_member_approved=False, **extra)


def _routes(entry, index):
    # Existing readers authenticate their inventories; no generation or solver.
    from . import en_ue_qualified_library as normal
    from . import en_ue_shear as shear
    from . import en_ue125_300_authority as normal300
    from . import en_ue125_shear300 as shear300
    routes = {}
    try:
        ref = normal.qualified_reference(index)
        routes['EN250_normal'] = _route('tercas.en_ue_qualified_library', entry, index,
            ref['source_binding'], ref['eligible_by_action'], ref['qualified_content_sha256'],
            pending_branch_reason='Ineligible branches require their original certificate blocking reasons; no gross fallback.')
    except (ValueError, OSError) as exc:
        routes['EN250_normal'] = dict(status='unavailable', reason=str(exc), application_qualified=False)
    for name, provider in (('EN250_shear', shear), ('EN300_shear', shear300)):
        try:
            ref = provider.qualified_reference(index)
            routes[name] = _route(provider.__name__, entry, index, ref['source_binding'],
                {'strong': True, 'weak': True}, ref['content_sha256'])
        except (ValueError, OSError) as exc:
            routes[name] = dict(status='unavailable', reason=str(exc), application_qualified=False)
    try:
        ref = normal300.read()
        binding = {key: copy.deepcopy(ref[key]) for key in
            ('catalog_index', 'catalog_id', 'profile_id', 'nominal_identity',
             'nominal_identity_sha256', 'nodes_sha256', 'material', 'thickness_mm')}
        binding['action_convention'] = ref['stress_convention']
        if not _bound(entry, index, binding):
            raise ValueError('No frozen fy300 normal authority for this nominal row; the parameterized family route is listed separately.')
        routes['EN300_normal'] = _route(normal300.__name__, entry, index, binding,
            {key: item['eligible'] for key, item in ref['components'].items()}, ref['content_sha256'], axial_scope='N=0')
    except (ValueError, OSError) as exc:
        routes['EN300_normal'] = dict(status='unavailable', reason=str(exc), application_qualified=False)
    routes['NBR_own_contour'] = dict(status='not_assessed_for_current_study',
        reason='Existing own-contour NBR certificates require their exact geometry/material/sign and explicit study scope; documentary completeness does not activate them.',
        providers=['tercas.ue_catalog_nbr_bending', 'tercas.ue_catalog_nbr_distortional',
                   'tercas.ue_catalog_nbr_weak_mle', 'tercas.ue_catalog_nbr_weak_annex_e'],
        application_qualified=False)
    # These are method descriptors, not certificates. Browsing the catalogue
    # must not generate sections, solve fields or silently adopt a material.
    routes['EN_parameterized_family'] = dict(
        status='method_available_for_new_calculation',
        provider='tercas.en_ue_family_provider',
        application='tercas.isolated_en_ue_family_application',
        material_parameter='declared fyb; gamma_M0=1 in this implementation',
        reason='Each signed normal branch and both transverse shear branches are assessed from geometry and material during an explicitly selected family calculation. Missing normal branches do not suppress independently qualified shear.',
        requires_complete_documentary_row=True, requires_explicit_model_selection=True,
        application_qualified=False, whole_member_approved=False)
    routes['NBR_parameterized_family'] = dict(
        status='method_available_for_new_calculation',
        provider='tercas.nbr_ue_family', application='tercas.nbr_ue_family_application',
        material_parameter='declared E, G, fy and resistance factors',
        reason='Published nominal local/distortional references and own-contour methods are separate. Actual load position, signed demands and effective lengths are checked during calculation; tabulated completeness alone does not qualify resistance.',
        requires_complete_documentary_row=True, application_qualified=False,
        whole_member_approved=False)
    return routes


def table(*, include_routes=True):
    """All Ue rows, including incomplete rows, freshly derived without caching."""
    catalogue, catalogue_sha = _read('core/catalogo_documentado.json')
    pierin, pierin_sha = _read('data/pierin_2013_weak_reference.json')
    records = []
    for index, entry in enumerate(catalogue['entries']):
        if entry['family'] != 'Ue':
            continue
        matches = [r for r in pierin['entries'] if r['family'] == 'Ue'
                   and r['dimensions_mm'] == entry['dimensions_mm']]
        complete = _completeness(entry, matches)
        records.append(dict(schema=SCHEMA, catalog_index=index, catalog_id=entry['id'],
            name=entry['name'], family='Ue', dimensions_mm=copy.deepcopy(entry['dimensions_mm']),
            published_properties=copy.deepcopy(entry['published_properties']),
            workbook_critical_values=copy.deepcopy(entry['critical_values']),
            raw_source_values=copy.deepcopy(entry['raw_source_values']),
            source=dict(workbook=catalogue['source_file'], sheet=catalogue['sheet'],
                workbook_row=entry['source_workbook_row'], workbook_sha256=catalogue['source_sha256'],
                catalogue_asset_sha256=catalogue_sha, properties_url=entry['source_url'],
                criticals_url=entry['critical_source'], pierin_reference_asset_sha256=pierin_sha,
                pierin_pdf_sha256=pierin['source_pdf_sha256']),
            pierin_reference=dict(matching_rows=copy.deepcopy(matches), E_MPa=pierin['E_MPa'],
                G_MPa=pierin['G_MPa'], nu=pierin['nu'], source_sign=pierin['source_sign'],
                corners=pierin['corners'], boundary=pierin['boundary'],
                source_geometry_to_mean_line=pierin['source_geometry_to_mean_line']),
            completeness=complete, selectable_for_new_study=complete['complete'],
            geometry_separation=dict(published_property_convention_unresolved=entry.get('source_geometry_convention_unresolved', True),
                rounded_contour_provider='tercas.catalog_torsion_section.prepare',
                rounded_contour_generated=False, pierin_criticals_transferred=False),
            routes=_routes(entry, index) if include_routes else {'status': 'not_requested'},
            resistance_qualified_by_registry=False, whole_member_approved=False))
    return records


def inventory(*, include_routes=False):
    records = table(include_routes=include_routes)
    return dict(schema=SCHEMA, completeness_policy=COMPLETENESS_POLICY,
                total=len(records), complete=sum(r['selectable_for_new_study'] for r in records),
                incomplete=[dict(catalog_index=r['catalog_index'], name=r['name'],
                                 **r['completeness']) for r in records if not r['selectable_for_new_study']],
                records=records)


def new_study_indices():
    """Only documentary-complete Ue rows, never a replacement for legacy reads."""
    return [r['catalog_index'] for r in table(include_routes=False) if r['selectable_for_new_study']]


def select_new_study(index, *, include_routes=True):
    """Return a descriptor, not project inputs, a certificate or approval."""
    if type(index) is not int:
        raise ValueError('A catalogue integer index is required; generic dimensions are future work.')
    record = next((r for r in table(include_routes=False) if r['catalog_index'] == index), None)
    if record is None:
        raise ValueError('Only existing Ue catalogue rows are supported for new studies.')
    if not record['selectable_for_new_study']:
        raise ValueError('Incomplete Pierin documentary row: ' + json.dumps(record['completeness'], ensure_ascii=False))
    if include_routes:
        from .catalogs import catalog_entry
        record['routes'] = _routes(catalog_entry(index), index)
    return record
