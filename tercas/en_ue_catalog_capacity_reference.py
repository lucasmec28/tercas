"""Compose two independently pinned authorities for the same nominal Ue.

No candidate, caller JSON, or arithmetic-only certificate is an authority.
Normal and transverse-shear inventories are admitted by their own providers.
This adapter only checks their common source identity and joins their records;
it does not build sections, solve a member, or activate an application route.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

SCHEMA = 'EN_Ue_catalog_signed_capacity_reference_v1'
REVISION = 'EN_Ue_normal_and_shear_composition_20261106_r1'
NORMAL_SCHEMA = 'EN_Ue_catalog_normal_capacity_reference_v1'
SHEAR_SCHEMA = 'EN_Ue_Pierin_transverse_shear_qualified_v1'
STATUS = 'independently_qualified_frozen_reference'
CONVENTION = 'N tension positive, Mx=integral(y*sigma)dA, My=-integral(x*sigma)dA'
SHEAR_METHOD = 'EN13_Table6.1_unstiffened_web_and_two_rotated_flange_webs_v1'
MATERIAL = dict(E_MPa=210000., nu=.3, fyb_MPa=250., fya_MPa=250., gamma_M0=1.)
BRANCHES = ('N_tension', 'N_compression', 'Mx_positive', 'Mx_negative',
            'My_positive', 'My_negative')
COMMON = ('catalog_index', 'catalog_id', 'profile_id', 'nominal_identity_sha256',
          'nodes_sha256', 'material')
FALSE_FLAGS = ('whole_member_approved', 'complete_EN_design_qualified',
    'global_stability_qualified', 'torsional_interaction_qualified',
    'NBR_capacities_used', 'AISI_capacities_used', 'runtime_release_approved',
    'physical_geometry_verified', 'pierin_criticals_transferred',
    'legacy_certificates_changed')


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _digest(value):
    return (type(value) is str and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


def _normal_reference(index, certificate_sha256):
    try:
        from .en_ue_qualified_library import normal_capacity_reference
    except ImportError as exc:
        raise ValueError('Qualified normal Ue inventory is not installed') from exc
    return normal_capacity_reference(index, certificate_sha256)


def _shear_reference(index):
    try:
        from .en_ue_shear import qualified_reference as read_shear
    except ImportError as exc:
        raise ValueError('Separately qualified Ue shear inventory is not installed') from exc
    return read_shear(index)


def _normal_conditions():
    from .en_ue_qualified_library import INTEGRATION_CONDITIONS
    return copy.deepcopy(INTEGRATION_CONDITIONS)


def qualified_reference(index, component_sections_sha256):
    """Read the exact normal hash and the independently pinned same-row shear.

    The normal inventory SHA keeps its original meaning. The separate shear
    inventory and source SHAs remain explicit in shear_capacity_qualification.
    The final content hash is a consistency seal, never admission authority.
    """
    if type(index) is not int or index < 0 or not _digest(component_sections_sha256):
        raise ValueError('Exact catalogue index and qualified normal hash required')
    normal = copy.deepcopy(_normal_reference(index, component_sections_sha256))
    shear = copy.deepcopy(_shear_reference(index))
    if not isinstance(normal, dict) or not isinstance(shear, dict):
        raise ValueError('Both qualified capacity authorities are required')
    if (normal.get('schema') != NORMAL_SCHEMA or normal.get('qualification_status') != STATUS
            or type(normal.get('catalog_index')) is not int or normal['catalog_index'] != index
            or normal.get('component_sections_sha256') != component_sections_sha256
            or normal.get('family') != 'Ue' or normal.get('action_convention') != CONVENTION
            or _sha(normal.get('material')) != _sha(MATERIAL)
            or any(normal.get(k) is not False for k in FALSE_FLAGS)):
        raise ValueError('Normal authority outside the qualified Ue source/domain')
    for key in ('nominal_identity_sha256', 'nodes_sha256', 'inventory_sha256',
                'source_candidate_sha256'):
        if not _digest(normal.get(key)):
            raise ValueError('Normal authority has no complete identity: '+key)
    eligible, floors = normal.get('eligible_components'), normal.get('signed_capacity_floor')
    if (not isinstance(eligible, dict) or set(eligible) != set(BRANCHES)
            or not isinstance(floors, dict) or set(floors) != set(BRANCHES)):
        raise ValueError('All six normal branches must be accounted for')
    for key in BRANCHES:
        if type(eligible[key]) is not bool:
            raise ValueError('Normal eligibility must be boolean')
        if eligible[key]:
            if type(floors[key]) is not int or floors[key] <= 0:
                raise ValueError('Eligible normal branch requires a positive integer floor')
        elif floors[key] is not None:
            raise ValueError('Absent normal branch cannot acquire a floor')
    if normal.get('normal_component_runtime_approved') is not any(eligible.values()):
        raise ValueError('Normal library approval contradicts its signed branches')
    if normal.get('normal_integration_conditions') != _normal_conditions():
        raise ValueError('Normal integration conditions are missing or changed')
    source = shear.get('source_binding')
    if (shear.get('schema') != SHEAR_SCHEMA or not isinstance(source, dict)
            or any(_sha(source.get(key)) != _sha(normal.get(key)) for key in COMMON)
            or any(shear.get(key) is not False for key in (
                'normal_operators_qualified', 'runtime_release_approved', 'whole_member_approved',
                'global_stability_qualified', 'physical_geometry_verified',
                'complete_EN_design_qualified', 'pierin_criticals_transferred',
                'NBR_capacities_used', 'AISI_capacities_used'))):
        raise ValueError('Shear authority is not for the exact same nominal source/material')
    digest = shear.get('content_sha256')
    if not _digest(digest) or digest != _sha({k:v for k,v in shear.items() if k != 'content_sha256'}):
        raise ValueError('Shear authority consistency seal is invalid')
    proof = shear.get('shear_capacity_qualification')
    if (not isinstance(proof, dict) or proof.get('status') != STATUS
            or proof.get('method') != SHEAR_METHOD or shear.get('method') != SHEAR_METHOD
            or proof.get('walls') != {'strong':1, 'weak':2}
            or proof.get('nodes_sha256') != normal['nodes_sha256']
            or proof.get('nominal_identity_sha256') != normal['nominal_identity_sha256']
            or _sha(proof.get('material')) != _sha(MATERIAL)
            or proof.get('support_stiffener_credit') is not False
            or proof.get('lip_or_corner_resistance_credit') is not False
            or any(not _digest(proof.get(k)) for k in ('source_sha256','inventory_sha256'))):
        raise ValueError('Separate shear qualification is missing or contradictory')
    capacity = shear.get('shear_capacity_lower_N')
    if (not isinstance(capacity, dict) or set(capacity) != {'strong','weak'}
            or any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0
                   for v in capacity.values())):
        raise ValueError('Both qualified transverse shear floors are required')
    result = normal
    result.update(schema=SCHEMA, composition_revision=REVISION,
        normal_authority_schema=NORMAL_SCHEMA, shear_authority_schema=SHEAR_SCHEMA,
        shear_authority_sha256=digest,
        shear_capacity_lower_N=capacity, shear_capacity_qualification=proof,
        shear_capacity_geometry=copy.deepcopy(shear['shear_capacity_geometry']),
        shear_integration_conditions=copy.deepcopy(shear['integration_conditions']),
        shear_applicability=copy.deepcopy(shear['applicability']))
    result['content_sha256'] = _sha(result)
    return result
