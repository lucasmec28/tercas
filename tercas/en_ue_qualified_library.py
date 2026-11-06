"""Explicit, pinned qualification of the nominal-Ue normal section library.

The candidate v1 is never mutated or retrospectively approved. Fresh builds
rederive it, require its COMPLETE audited hash, then create a separately pinned
qualified schema. Saved reads validate static inventory and source snapshots;
they never regenerate a section. This does not activate any app consumer.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'EN_Ue_Pierin_normal_section_library_qualified_v1'
LIBRARY_REVISION = 'EN_Ue_section_library_20261106_r1'
CANDIDATE_SCHEMA = 'EN_Ue_Pierin_nominal_normal_operators_candidate_v1'
CANDIDATE_REVISION = 'uniform_axial_and_integral_pure_moments_20261106'
INVENTORY_SCHEMA = 'EN_Ue_qualified_operator_inventory_v1'
ACTION_CONVENTION = 'N tension positive, Mx=integral(y*sigma)dA, My=-integral(x*sigma)dA'
INVENTORY_SHA256 = '51e7bac78b21e58f2adb2cc5bd25b1a65469fe0334e921e31bc351522c0e1f53'
INVENTORY_PATH = Path(__file__).parent/'data/en_ue_qualified_operator_inventory_20261106.json'
ACTIONS = ('N_tension','N_compression','Mx_positive','Mx_negative','My_positive','My_negative')
BINDING_KEYS = ('catalog_index','catalog_id','profile_id','nodes_sha256','nominal_identity',
                'nominal_identity_sha256','thickness_mm','material','method_revision')
FALSE_FLAGS = ('runtime_release_approved','whole_member_approved','global_stability_qualified',
               'physical_geometry_verified','complete_EN_design_qualified',
               'pierin_criticals_transferred','NBR_capacities_used','AISI_capacities_used',
               'legacy_certificates_changed')
INTEGRATION_CONDITIONS = {
    'app_activation': 'Separate integration release required; this library alone changes no app consumer.',
    'scope': 'Pure normal local/distortional section operators only, per eligible signed branch.',
    'My_positive': 'Inherited bounded EN13 Eq5.10b interpretation for mixed flanges with wholly compressed physical As; no additional universal translating-junction eigenmode requirement or qualification.',
    'curling_shear_lag': 'Applicability must be qualified for the actual profile and moment diagram; the seven legacy Ue100 proofs are not transferred.',
    'EN6_1_6': 'Use the same coherent gross contour for B and shear/torsional terms; this normal library does not qualify the combined check.',
    'EN6_27': 'Requires separately qualified EN shear capacities and concurrent signed action fields; no NBR/AISI substitution.',
    'centroid_transport': 'Apply axial transport once and do not credit favourable centroid shifts determined at fy.',
}


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _sealed_hash(value):
    if not isinstance(value,dict):raise ValueError('A certificate object is required')
    payload=copy.deepcopy(value);digest=payload.pop('content_sha256',None)
    if type(digest) is not str or digest!=_sha(payload):
        raise ValueError('Certificate content hash is invalid')
    return digest


def _binding(value):
    return dict({key:copy.deepcopy(value[key]) for key in BINDING_KEYS},
                action_convention=value['stress_convention'])


def _eligible(value):
    return {key:value['components'][key]['eligible'] for key in ACTIONS}


def _reference_id(index):
    return f'{LIBRARY_REVISION}:catalog_index:{index}'


@lru_cache(maxsize=1)
def _inventory():
    """Trusted immutable release asset, not a runtime enrollment database."""
    result=json.loads(INVENTORY_PATH.read_text(encoding='utf-8'))
    digest=_sealed_hash(result)
    if (digest!=INVENTORY_SHA256 or result.get('schema')!=INVENTORY_SCHEMA
            or result.get('library_revision')!=LIBRARY_REVISION
            or result.get('qualified_schema')!=SCHEMA
            or result.get('candidate_schema')!=CANDIDATE_SCHEMA
            or result.get('candidate_method_revision')!=CANDIDATE_REVISION):
        raise ValueError('Qualified EN inventory is outside the trusted release')
    return result


def qualified_reference(index):
    """Return a copy of one static reference; never derive or enroll a hash."""
    if type(index) is not int:raise ValueError('Integer catalogue index required')
    record=_inventory()['entries'].get(str(index))
    if record is None:raise ValueError('Catalogue row is not in the qualified EN inventory')
    return copy.deepcopy(record)


def _check_candidate(candidate,reference):
    digest=_sealed_hash(candidate)
    if (candidate.get('schema')!=CANDIDATE_SCHEMA
            or candidate.get('method_revision')!=CANDIDATE_REVISION
            or digest!=reference['candidate_content_sha256']
            or candidate.get('stress_convention')!=ACTION_CONVENTION
            or _binding(candidate)!=reference['source_binding']
            or _eligible(candidate)!=reference['eligible_by_action']
            or candidate['signed_capacity_floor']!=reference['signed_capacity_floor']):
        raise ValueError('Candidate complete hash/source is not exactly qualified; keep pending')
    if (candidate.get('review_status')!='candidate_pending_independent_review'
            or any(candidate.get(key) is not False for key in FALSE_FLAGS)):
        raise ValueError('The original candidate status/false flags must be preserved')


def _qualified_payload(candidate,reference_id):
    """Pure schema transformation, NOT admission. Validator pins its result.

    Used by the explicit offline audit when preparing a proposed inventory.
    Calling this private helper alone cannot admit its output at runtime.
    """
    result=copy.deepcopy(candidate);result.pop('content_sha256')
    result.update(schema=SCHEMA,library_revision=LIBRARY_REVISION,
        review_status='qualified_normal_section_library_not_app_activation',
        normal_component_runtime_approved=any(c['eligible'] for c in result['components'].values()),
        qualification=dict(reference_id=reference_id,inventory_revision=LIBRARY_REVISION,
            source_candidate_schema=candidate['schema'],
            source_candidate_method_revision=candidate['method_revision'],
            source_candidate_content_sha256=candidate['content_sha256'],
            source_candidate_review_status=candidate['review_status'],
            source_candidate_runtime_release_approved=candidate['runtime_release_approved'],
            integration_conditions=copy.deepcopy(INTEGRATION_CONDITIONS)))
    for component in result['components'].values():
        component['normal_component_runtime_approved']=component['eligible']
    # The app-release flag and all global/physical flags remain FALSE.
    result['content_sha256']=_sha(result)
    return result


def _restore_candidate_snapshot(certificate):
    """Undo metadata overlay only. No geometry, formula or section builder."""
    result=copy.deepcopy(certificate);qualification=result.pop('qualification')
    result.pop('content_sha256');result.pop('library_revision');result.pop('normal_component_runtime_approved')
    result['schema']=qualification['source_candidate_schema']
    result['review_status']=qualification['source_candidate_review_status']
    for component in result['components'].values():component.pop('normal_component_runtime_approved')
    result['content_sha256']=qualification['source_candidate_content_sha256']
    return result


def verify_qualified_component_sections(certificate):
    """Internal authenticity/integrity only; use validate_saved for binding.

    A different, entirely known certificate is valid in isolation, but cannot
    replace the original source snapshot in a saved calculation.
    """
    try:
        digest=_sealed_hash(certificate)
        if (certificate.get('schema')!=SCHEMA or certificate.get('library_revision')!=LIBRARY_REVISION
                or certificate.get('review_status')!='qualified_normal_section_library_not_app_activation'):
            raise ValueError('Qualified EN library schema/revision required')
        reference=qualified_reference(certificate['catalog_index'])
        if digest!=reference['qualified_content_sha256']:
            raise ValueError('Complete qualified certificate hash is unknown; keep pending')
        qualification=certificate['qualification']
        if (qualification['reference_id']!=reference['reference_id']
                or qualification['inventory_revision']!=LIBRARY_REVISION
                or qualification['source_candidate_content_sha256']!=reference['candidate_content_sha256']
                or qualification['source_candidate_method_revision']!=CANDIDATE_REVISION
                or qualification['source_candidate_runtime_release_approved'] is not False
                or qualification['integration_conditions']!=INTEGRATION_CONDITIONS
                or _binding(certificate)!=reference['source_binding']
                or _eligible(certificate)!=reference['eligible_by_action']
                or certificate['signed_capacity_floor']!=reference['signed_capacity_floor']
                or certificate['normal_component_runtime_approved'] is not any(reference['eligible_by_action'].values())
                or any(certificate.get(key) is not False for key in FALSE_FLAGS)):
            raise ValueError('Qualified EN source/conditions do not match the same reference')
        for name in ACTIONS:
            component=certificate['components'][name]
            eligible=reference['eligible_by_action'][name]
            if (component['normal_component_runtime_approved'] is not eligible
                    or component['first_yield_capacity_floor']!=reference['signed_capacity_floor'][name]):
                raise ValueError('Signed branch approval/floor differs from the inventory')
            if not eligible and (component['sigma_coefficients_c0_cx_cy'] is not None
                    or component['effective_properties'] is not None
                    or component['first_yield_capacity_floor'] is not None):
                raise ValueError('An absent branch cannot acquire gross/effective fallback data')
        restored=_restore_candidate_snapshot(certificate)
        _check_candidate(restored,reference)
    except (KeyError,TypeError,OverflowError) as error:
        raise ValueError('Malformed qualified EN certificate or source snapshot') from error


def qualify_audited_candidate(candidate,*,expected_catalog_index):
    """Explicit transition of a COMPLETE already-audited candidate snapshot.

    This does not regenerate the input. Fresh calculations must use the builder
    below, which rederives the candidate first. Unknown hashes stay pending.
    """
    reference=qualified_reference(expected_catalog_index)
    try:
        _check_candidate(candidate,reference)
    except (KeyError,TypeError,OverflowError) as error:
        raise ValueError('Malformed candidate/source snapshot') from error
    result=_qualified_payload(candidate,reference['reference_id'])
    verify_qualified_component_sections(result)
    return result


def build_qualified_component_sections(index,**material):
    """Fresh calculation rederives before applying the exact release inventory."""
    from .en_ue_catalog_operators import build_catalog_component_sections
    candidate=build_catalog_component_sections(index,**material)
    return qualify_audited_candidate(candidate,expected_catalog_index=index)


def _source_binding_unchecked(certificate):
    return dict(schema='EN_Ue_qualified_normal_source_binding_v1',
        library_revision=LIBRARY_REVISION,qualified_schema=SCHEMA,
        qualified_content_sha256=certificate['content_sha256'],
        candidate_content_sha256=certificate['qualification']['source_candidate_content_sha256'],
        reference_id=certificate['qualification']['reference_id'],
        **_binding(certificate))


def source_binding(certificate):
    """Compact original-reference snapshot for the consumer's saved source.

    The consumer must retain this alongside its own demand/case source binding,
    and check that nominal identity/material/contour match that actual source.
    Do not recreate this binding from a replacement certificate during reading.
    """
    verify_qualified_component_sections(certificate)
    return _source_binding_unchecked(certificate)


def validate_saved(certificate,expected_source_binding):
    """Read-only validation of saved payload + its ORIGINAL source snapshot."""
    verify_qualified_component_sections(certificate)
    if not isinstance(expected_source_binding,dict) or expected_source_binding!=_source_binding_unchecked(certificate):
        raise ValueError('Qualified EN certificate does not belong to the same original source snapshot')


def require_component(certificate,axis,value,*,expected_source_binding):
    """Only exact zero dispenses a signed branch; binding is always validated."""
    validate_saved(certificate,expected_source_binding)
    if axis not in ('N','Mx','My') or type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Finite N, Mx or My signed action required')
    if value==0.:return None
    name=('N_tension' if value>0 else 'N_compression') if axis=='N' else axis+('_positive' if value>0 else '_negative')
    component=certificate['components'][name]
    if not component['normal_component_runtime_approved']:
        raise ValueError(name+' remains pending: '+json.dumps(component['blocking_reasons']))
    return copy.deepcopy(component)


def normal_capacity_reference(index,qualified_certificate_sha256):
    """NORMAL-only frozen provider for a separately qualified composition.

    No shear keys are supplied. This schema alone cannot satisfy an EN6.27
    combined-capacity consumer. Neither candidates nor unknown hashes qualify.
    """
    reference=qualified_reference(index)
    if type(qualified_certificate_sha256) is not str or qualified_certificate_sha256!=reference['qualified_content_sha256']:
        raise ValueError('Complete normal library hash is not qualified for this exact index')
    binding=reference['source_binding']
    return dict(schema='EN_Ue_catalog_normal_capacity_reference_v1',
        qualification_status='independently_qualified_frozen_reference',family='Ue',
        reference_id=reference['reference_id'],catalog_index=index,catalog_id=binding['catalog_id'],
        profile_id=binding['profile_id'],action_convention=binding['action_convention'],
        component_sections_sha256=qualified_certificate_sha256,
        source_candidate_sha256=reference['candidate_content_sha256'],
        nominal_identity_sha256=binding['nominal_identity_sha256'],nodes_sha256=binding['nodes_sha256'],
        inventory_sha256=INVENTORY_SHA256,material=copy.deepcopy(binding['material']),
        eligible_components=copy.deepcopy(reference['eligible_by_action']),
        signed_capacity_floor=copy.deepcopy(reference['signed_capacity_floor']),
        normal_integration_conditions=copy.deepcopy(INTEGRATION_CONDITIONS),
        normal_component_runtime_approved=any(reference['eligible_by_action'].values()),
        torsional_interaction_qualified=False,
        **{key:False for key in FALSE_FLAGS})
