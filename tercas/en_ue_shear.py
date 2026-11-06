"""Pinned EN13 Table 6.1 transverse shear floors for 83 exact nominal Ue rows.

This independent qualification is not inherited from a normal-operator hash.
Only offline-reviewed records qualify. Saved reads do not reconstruct geometry
or calculate resistance. No app, historical record, or plain-U route changes.
"""
from __future__ import annotations

import copy
from decimal import Decimal, localcontext, ROUND_CEILING, ROUND_FLOOR
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'EN_Ue_Pierin_transverse_shear_qualified_v1'
REVISION = 'EN_Ue_shear_floors_20261106_r1'
METHOD = 'EN13_Table6.1_unstiffened_web_and_two_rotated_flange_webs_v1'
INVENTORY_SCHEMA = 'EN_Ue_shear_inventory_v1'
INVENTORY_SHA256 = '8beba399c4afc056eb6ae6d9a7b4f25beef7fd246089e34c1c17c13a5deba28f'
SOURCE_SHA256 = 'b5615b766a30aec50b19a29d18c9cf4e805e8721e8dd0822976172e187c6e47e'
DATA = Path(__file__).parent/'data'
INVENTORY_PATH = DATA/'en_ue_shear_inventory_20261106.json'
SOURCE_PATH = DATA/'en_ue_shear_sources_20261106.json'
MATERIAL = {'E_MPa':210000., 'nu':.3, 'fyb_MPa':250., 'fya_MPa':250., 'gamma_M0':1.}
BINDING_KEYS = ('catalog_index', 'catalog_id', 'profile_id', 'nodes_sha256',
    'nominal_identity', 'nominal_identity_sha256', 'thickness_mm', 'material')
FALSE_FLAGS = ('runtime_release_approved', 'normal_operators_qualified',
    'whole_member_approved', 'global_stability_qualified', 'physical_geometry_verified',
    'complete_EN_design_qualified', 'pierin_criticals_transferred',
    'NBR_capacities_used', 'AISI_capacities_used')


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _seal(payload):
    result=copy.deepcopy(payload);result['content_sha256']=_sha(result)
    return result


def _verify_seal(record):
    if not isinstance(record,dict): raise ValueError('Shear record must be an object')
    payload=copy.deepcopy(record);digest=payload.pop('content_sha256',None)
    if type(digest) is not str or digest != _sha(payload):
        raise ValueError('Shear content hash is invalid')
    return digest


def table61_unstiffened_fbv(lambda_w):
    """Scalar equation only, MPa at fixed fyb=250; never admits a profile.

    Endpoints are literal Table 6.1: <=0.83, (0.83,1.4), >=1.4.
    Rounded coefficients cause small downward jumps; do not interpolate them.
    """
    if type(lambda_w) not in (int,float) or not math.isfinite(lambda_w) or lambda_w<0:
        raise ValueError('Finite nonnegative web slenderness required')
    if lambda_w <= .83: return 145.
    if lambda_w < 1.4: return 120./lambda_w
    # Sequential division remains finite for very large finite lambda.
    return 167.5/lambda_w/lambda_w


def _wall_floor(hw_mm, t_mm, walls):
    """Directed Decimal evaluation of the conservative geometric bound.

    Input catalogue decimals represent declared exact nominal dimensions, not
    measurements. Upper sqrt/ratio produces an upper lambda. Decreasing fbv is
    rounded down. The final integer-N floor is computed before float reporting.
    Decimal.sqrt is correctly rounded nearest; next_plus encloses it above.
    """
    with localcontext() as ctx:
        ctx.prec=60;ctx.rounding=ROUND_CEILING
        h,t=Decimal(str(hw_mm)),Decimal(str(t_mm))
        root=(Decimal(250)/Decimal(210000)).sqrt().next_plus()
        lam=Decimal('0.346')*(h/t)*root
        ctx.rounding=ROUND_FLOOR
        if lam <= Decimal('.83'):
            strength=Decimal(145);branch='lambda_le_0.83'
        elif lam < Decimal('1.4'):
            strength=Decimal(120)/lam;branch='0.83_lt_lambda_lt_1.4'
        else:
            strength=Decimal('167.5')/lam/lam;branch='lambda_ge_1.4'
        capacity=Decimal(walls)*h*t*strength
        floor=int(capacity.to_integral_value(rounding=ROUND_FLOOR))
        # Reported bounds also point outward after conversion to binary64.
        lu=float(lam)
        if Decimal.from_float(lu)<lam: lu=math.nextafter(lu, math.inf)
        fl=float(strength)
        if Decimal.from_float(fl)>strength: fl=math.nextafter(fl, -math.inf)
    return dict(walls=walls, hw_mm=float(h), sw_upper_mm=float(h),
        lambda_upper=lu, fbv_lower_MPa=fl, table61_branch=branch,
        capacity_floor_N=float(floor), rounding='directed_decimal_60_digits_then_integer_N_floor')


def _derive(index):
    """Offline/fresh producer; alone it grants no qualification."""
    from .catalogs import catalog_entry
    from .catalog_torsion_section import CONVENTION, nominal_channel_nodes
    from .weak_pierin import reference_for_index
    entry=catalog_entry(index);reference=reference_for_index(index)
    if entry['family']!='Ue' or reference['status']!='tabulated_adopted_reference':
        raise ValueError('An exact nominal Pierin Ue row is required; no plain U or interpolation')
    d=entry['dimensions_mm'];t=float(d['t']);ri=entry['published_properties']['ri_mm']
    identity=dict(catalog_id=entry['id'], dimensions_mm=d, inner_radius_mm=ri,
                  arc_segments=32, convention=CONVENTION)
    nominal_hash=_sha(identity)
    nodes=nominal_channel_nodes(h_mm=d['h'],bf_mm=d['bf'],lip_mm=d['lip'],t_mm=t,
        ri_mm=ri,arc_segments=32)
    if len(nodes)!=134: raise ValueError('The qualified 32-chord Ue topology changed')
    # Opposite corner midpoints lie on the same normal coordinate. Their
    # separation, not the developed arc length, is the EN Figure 5.1 sw.
    sw_strong=abs(nodes[83][1]-nodes[50][1])
    sw_weak=[abs(nodes[17][0]-nodes[50][0]),abs(nodes[116][0]-nodes[83][0])]
    # Exact decimal subtraction avoids converting binary cancellation error
    # into a nominal dimension; both are bound to the same declared contour.
    hw_h=Decimal(str(d['h']))-Decimal(str(d['t']))
    hw_b=Decimal(str(d['bf']))-Decimal(str(d['t']))
    guard=dict(external_b_over_t=d['bf']/t, external_c_over_t=d['lip']/t,
        external_h_over_t=d['h']/t, external_c_over_b=d['lip']/d['bf'],
        inner_radius_mm=ri, radius_limit_mm=.04*t*MATERIAL['E_MPa']/MATERIAL['fyb_MPa'],
        core_design_thickness_assumed_mm=t, recommended_core_range_mm=[.45,15.],
        phi_degrees=90., sw_from_corner_midpoints_mm={'strong':sw_strong,'weak':sw_weak},
        source='EN13 3.2.4, 5.1(6), 5.2/Table5.1/Eq5.2a, 6.1.5/Fig5.1',
        external_dimensions_used_as_conservative_ratio_bounds=True)
    guard['satisfied']=(guard['external_b_over_t']<=60. and guard['external_c_over_t']<=50.
        and guard['external_h_over_t']<=500. and .2<=guard['external_c_over_b']<=.6
        and ri<=guard['radius_limit_mm'] and .45<=t<=15.
        and 0<sw_strong<=float(hw_h) and all(0<s<=float(hw_b) for s in sw_weak))
    if not guard['satisfied']: raise ValueError('Nominal Ue is outside the reviewed EN geometric scope')
    geometry={'strong':_wall_floor(hw_h,t,1),'weak':_wall_floor(hw_b,t,2)}
    binding=dict(catalog_index=index,catalog_id=entry['id'],
        profile_id='OWN_PIERIN_NOMINAL_'+entry['id']+'_'+nominal_hash[:16],
        nodes_sha256=_sha(nodes),nominal_identity=identity,nominal_identity_sha256=nominal_hash,
        thickness_mm=t,material=copy.deepcopy(MATERIAL),method_revision=REVISION)
    return _seal(dict(schema='EN_Ue_shear_reference_payload_v1',method=METHOD,
        source_binding=binding,pierin_nominal_row_id=reference['id'],
        source_sha256=SOURCE_SHA256,shear_capacity_geometry=geometry,
        shear_capacity_lower_N={axis:wall['capacity_floor_N'] for axis,wall in geometry.items()},
        applicability=guard,
        integration_conditions=[
            'Use the same nominal identity, nodes, design thickness and fixed material.',
            'Actual product, coating/tolerance-adjusted core thickness and material are not certified.',
            'Separate EN6.1.6 concurrent normal/shear/torsion stress checks remain required.',
            'Separate EN6.1.10 interaction, 6.1.7/6.1.11 where applicable, and member stability remain required.',
            'No holes, cutouts, added web stiffeners or arbitrary contour variants are admitted by this nominal identity.',
            'No support-stiffener, plastic, cold-work, lip or extra corner resistance is credited.',
            'Normal-operator qualification neither grants nor follows from this shear qualification.']))


@lru_cache(maxsize=1)
def _inventory():
    inventory=json.loads(INVENTORY_PATH.read_text(encoding='utf-8'))
    sources=json.loads(SOURCE_PATH.read_text(encoding='utf-8'))
    if (_verify_seal(sources)!=SOURCE_SHA256 or _verify_seal(inventory)!=INVENTORY_SHA256
            or inventory.get('schema')!=INVENTORY_SCHEMA or inventory.get('revision')!=REVISION
            or inventory.get('method')!=METHOD or inventory.get('source_sha256')!=SOURCE_SHA256
            or len(inventory.get('entries',{}))!=83):
        raise ValueError('Shear evidence/inventory is outside the pinned release')
    return inventory


def available_indices():
    return sorted(int(k) for k in _inventory()['entries'])


def qualified_reference(index):
    """Read trusted frozen data only; no catalog, geometry or normal rebuild."""
    if type(index) is not int:raise ValueError('Integer catalogue index required')
    payload=copy.deepcopy(_inventory()['entries'].get(str(index)))
    if payload is None:raise ValueError('No separately qualified shear reference for this row')
    _verify_seal(payload)
    binding=payload['source_binding'];payload_hash=payload.pop('content_sha256')
    result=dict(schema=SCHEMA,revision=REVISION,reference_payload_sha256=payload_hash,**{
        k:v for k,v in payload.items() if k!='schema'})
    result['shear_capacity_qualification']=dict(status='independently_qualified_frozen_reference',
        method=METHOD,walls={'strong':1,'weak':2},source_sha256=SOURCE_SHA256,
        inventory_sha256=INVENTORY_SHA256,nominal_identity_sha256=binding['nominal_identity_sha256'],
        nodes_sha256=binding['nodes_sha256'],material=copy.deepcopy(binding['material']),
        support_stiffener_credit=False,lip_or_corner_resistance_credit=False)
    result.update({key:False for key in FALSE_FLAGS})
    return _seal(result)


def build_catalog_shear_capacity(index, **material):
    """Fresh calculation must reproduce the entire independently frozen payload."""
    for key,value in material.items():
        if key not in MATERIAL or type(value) not in (int,float) or value!=MATERIAL[key]:
            raise ValueError('Shear material outside fixed qualified scope')
    candidate=_derive(index)
    record=_inventory()['entries'].get(str(index))
    if candidate!=record or candidate['content_sha256']!=record['content_sha256']:
        raise ValueError('Fresh shear result does not reproduce its qualified reference')
    return qualified_reference(index)


def verify_shear_capacity(certificate):
    """Reject forged/resealed evidence even when its arithmetic looks plausible."""
    try:
        _verify_seal(certificate)
        index=certificate['source_binding']['catalog_index']
        expected=qualified_reference(index)
        if certificate!=expected or certificate['content_sha256']!=expected['content_sha256']:
            raise ValueError('Unqualified shear certificate')
    except (KeyError,TypeError,OverflowError) as exc:
        raise ValueError('Malformed shear certificate') from exc
    return True


def validate_saved(certificate, source_snapshot):
    """Bind to the calculation's saved geometry/material, without reconstructing.

    source_snapshot may be a normal certificate or its source_binding. Its own
    upstream authenticity must also be checked by that component's validator.
    It must not be replaced by this shear certificate's own source_binding.
    """
    verify_shear_capacity(certificate)
    try:
        expected=certificate['source_binding']
        actual=source_snapshot.get('source_binding',source_snapshot)
        for key in BINDING_KEYS:
            if key not in actual or _sha(actual[key])!=_sha(expected[key]):
                raise ValueError('Shear/source binding mismatch: '+key)
        if 'nodes_xy_mm' in source_snapshot and _sha(source_snapshot['nodes_xy_mm'])!=expected['nodes_sha256']:
            raise ValueError('Saved shear source nodes mismatch')
    except (AttributeError,TypeError,KeyError) as exc:
        raise ValueError('Explicit original source snapshot required') from exc
    return True
