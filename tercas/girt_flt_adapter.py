"""Authenticate isolated-girt actions for existing scalar strong-axis FLT methods.

This is not roof geometry, a new support model, or a Ritz qualification.
"""
import copy
import math

SCHEMA='isolated_girt_flt_action_binding_v1'


def is_girt(data):
    return data.get('member_application')=='wall_girt'


def qualify(data,actions):
    from . import wall_girt_isolated as girt, ue_catalog_reference as own
    out=dict(schema=SCHEMA,eligible=False,reason=None,member_application='wall_girt',
        roof_geometry_used=False,physical_restraints_verified=False,
        physical_supports_created=False,whole_member_approved=False)
    if not girt.active(data):
        return dict(out,reason='Contorno próprio e identidade de travessa isolada não adotados.')
    out['source_binding']=own.source_binding(data)
    if not girt.height_model_adopted(data):
        return dict(out,reason='Modelo isolado/linhas locais da travessa não adotados explicitamente; esquema de cobertura não transferido.')
    if data.get('load_mode')=='area':
        from .batch import area_bundle
        bundle=area_bundle(data);combos=bundle['combinations']
    else:
        from .direct_roof_separated import combinations
        bundle=None;combos=combinations(data)
    matches=[c['id'] for c in combos if c['limit_state']=='ELU' and girt.height_actions(data,bundle,c)==actions]
    if not matches:
        return dict(out,reason='Ações/linhas locais não correspondem a uma combinação ELU autenticada da travessa.')
    out.update(combination_ids=matches,actions=copy.deepcopy(actions),
        declared_operator='Explicit R01 fork/free-warping isolated-girt choice; effective lengths remain separate resistance assumptions')
    if any(type(a.get(k)) not in (int,float) or not math.isfinite(a[k])
           for a in actions for k in ('height_above_SC_mm','x_from_SC_mm')):
        return dict(out,reason='Uma ou mais linhas locais da travessa permanecem indeterminadas.')
    return dict(out,eligible=True,reason='Ações locais, linhas por ação e contorno/material próprios autenticados; sem geometria de cobertura.')
