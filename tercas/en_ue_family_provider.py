"""Content/version keyed local deterministic method, not imported-hash authority.

Cache stores immutable serialized values. Each caller receives an independent
object. Old frozen authorities and saved snapshots are never reclassified.
"""
from __future__ import annotations
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from . import en_ue_family_kernel as kernel
from .en_ue_catalog_operators import _sha

_SOURCE_ROOT = Path(__file__).parent
TECHNICAL_BINDING_REVISION = 'EN_Ue_family_technical_sources_v1'
# Explicit dependency closure of build(), including finite(), contour convention,
# panel/action constants, outward arithmetic and documentary selection inputs.
# UI, release labels and unrelated checks must not enter saved section identity.
TECHNICAL_SOURCES = (
    'en_ue_family_kernel.py',
    'en_ue_family_reductions.py',
    'en_ue_family_provider.py',
    'en_ue_catalog_operators.py',
    'catalog_torsion_section.py',
    'catalogs.py',
    'weak_pierin.py',
    'pierin_ue_registry.py',
    'three_girt_en_normal/en1993_normal_components.py',
    'torsion_vlasov/section.py',
    'torsion_vlasov/intervals.py',
    'core/catalogo_documentado.json',
    'data/pierin_2013_weak_reference.json',
)


def _technical_source_key():
    """Stable technical dependency identity, never a caller-declared hash."""
    return _sha(dict(binding_revision=TECHNICAL_BINDING_REVISION,
        sources={f:hashlib.sha256((_SOURCE_ROOT/f).read_bytes()).hexdigest()
                 for f in TECHNICAL_SOURCES}))


def _source_key():
    # Broad invalidation is intentionally transient, not persisted authority.
    root=_SOURCE_ROOT
    files=[str(p.relative_to(root)) for p in sorted(root.rglob('*')) if p.suffix in ('.py','.json')]
    return _sha({f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files})


@lru_cache(maxsize=512)
def _cached(index,fy,gamma,cache_source_key,technical_source_key,identity_key,declaration_json):
    result=kernel.build(index,fyb_MPa=fy,gamma_M0=gamma,material_declaration=json.loads(declaration_json))
    result.pop('content_sha256')
    result['provider_binding']=dict(source_content_sha256=technical_source_key,
                                    technical_binding_revision=TECHNICAL_BINDING_REVISION,
                                    nominal_input_sha256=identity_key,
                                    method_revision=kernel.REVISION,authority='local_deterministic_family_method')
    result['content_sha256']=_sha(result)
    return json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)


def section(index,*,fyb_MPa,gamma_M0=1.,material_declaration=None):
    from .pierin_ue_registry import select_new_study
    record=select_new_study(index,include_routes=False)
    values=kernel.material(fyb_MPa,gamma_M0)
    declaration=kernel._material_declaration(values,material_declaration)
    declaration_input={key:declaration.get(key) for key in ('name','fu_MPa','source')}
    declaration_json=json.dumps(declaration_input,sort_keys=True,allow_nan=False)
    identity_key=_sha(dict(catalog_index=index,catalog_id=record['catalog_id'],
                           dimensions_mm=record['dimensions_mm'],ri_mm=record['published_properties']['ri_mm'],
                           material=dict(values),material_declaration=declaration,method_revision=kernel.REVISION))
    return json.loads(_cached(index,values['fyb_MPa'],values['gamma_M0'],_source_key(),_technical_source_key(),identity_key,declaration_json))


def verify(certificate):
    """Compare all content against trusted local recomputation, not selfhash."""
    if not isinstance(certificate,dict):raise ValueError('Malformed family section')
    if certificate.get('method_revision') == 'explicit_material_integral_and_reduced_web_20261106_v1':
        from ._en_ue_family_r10.en_ue_family_provider import verify as verify_r10
        return verify_r10(certificate)
    try:
        expected=section(certificate['catalog_index'],fyb_MPa=certificate['material']['fyb_MPa'],
                         gamma_M0=certificate['material']['gamma_M0'],
                         material_declaration={key:certificate['material_declaration'].get(key)
                                               for key in ('name','fu_MPa','source')})
        if _sha(certificate)!=_sha(expected):
            raise ValueError('Family section differs from the local deterministic method')
    except (KeyError,TypeError,AttributeError,OverflowError) as exc:
        raise ValueError('Malformed family section') from exc
    return True


def require_component(certificate,axis,value):
    verify(certificate)
    if axis not in ('Mx','My') or type(value) not in (int,float):
        raise ValueError('Family normal scope is N=0 and signed Mx/My only')
    import math
    if not math.isfinite(value):raise ValueError('Finite signed action required')
    if value==0:return None
    name=axis+('_positive' if value>0 else '_negative')
    result=certificate['components'][name]
    if not result['eligible']:raise ValueError(name+': '+json.dumps(result['blocking_reasons']))
    import copy
    return copy.deepcopy(result)
