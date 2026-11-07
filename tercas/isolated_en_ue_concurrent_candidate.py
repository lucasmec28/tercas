"""Explicit opt-in candidate consumer; production v1/v2/v3 remain unchanged.

Reuses the original dense source and authenticated resistance authority. It
runs arithmetic/replay only, never a member solver. Already applicable v3
results are returned unchanged; only a currently pending bending applicability
may receive a fresh v4 candidate record. No UI or production caller imports it.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path

from .en_ue_catalog_operators import _sha
from . import isolated_en_ue_family as original
from . import isolated_en_ue_catalog_application as arithmetic
from . import en_ue_concurrent_shear_lag_candidate as method

SCHEMA='EN_Ue_family_concurrent_section_components_v4_candidate'
REVISION='simultaneous_uniform_reference_subyield_20261107_v1'


def source_binding():
    root=Path(__file__).parent
    names=('isolated_en_ue_concurrent_candidate.py','isolated_en_ue_family.py',
        'en_ue_family_field_controls.py','en_ue_family_provider.py',
        'en_ue_family_geometry.py','en_ue125_300_source_replay.py')
    return _sha(dict(method_sources=method._source_binding(),
        consumer_sources={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in names}))


def _applicability(old,proof):
    out=copy.deepcopy(old)
    for axis,row in out['axes'].items():
        if not row['active']:continue
        pure_curl=proof['curling_components']['axes'][axis]
        row.update(shear_lag_dispensation_qualified=row['shear_lag_qualified'],
            shear_lag_qualified=True,curling_qualified=pure_curl['qualified'],
            shear_lag_explicit_method=method.SCHEMA,qualified=pure_curl['qualified'],
            reason='' if pure_curl['qualified'] else 'Curling da componente pura não qualificado.')
    out['qualified']=all(row['qualified'] for row in out['axes'].values())
    out['curling_panels']={axis:copy.deepcopy(row['panels']) for axis,row in proof['curling_components']['axes'].items()}
    out['curling_model']=proof['curling_components']['scope']
    out['shear_lag_method']='Respective pure-axis area/moment enclosures, with simultaneous uniform local/D reference.'
    out['reason']='Shear lag das duas componentes e local/D simultâneo limitados; curling puro reavaliado.'
    out['concurrent_shear_lag_supplement_sha256']=proof['content_sha256']
    return out


def _extend(base,demand,*,normal_snapshot,model_origin):
    """Internal continuation after the closed original batch authenticates base."""
    if base['applicability']['qualified']:
        return base
    _,_,reaction_proof=arithmetic._equilibrium(demand)
    proof=method.audit(demand,normal_snapshot)
    ready=proof.get('construction_qualified') is True
    required={key for keys in proof.get('required_signed_branches',{}).values() for key in keys}
    if any(not normal_snapshot['components'][key]['eligible'] for key in required):
        ready=False
        proof['blocking_reasons'].append(dict(code='SOURCE_SIGNED_OPERATOR_NOT_QUALIFIED',normative_rejection_inferred=False))
    proof.update(source_authenticated=True,consumer_integrated=True,
        consumer_scope='Separate mathematical candidate consumer; not production app integration or publication',
        source_authentication=dict(normal_provider_verified=True,
            own_contour_CG_omega_Cw_verified=True,original_dense_field_replayed=True,
            bending_reaction_equilibrium=copy.deepcopy(reaction_proof),
            source_normal_sha256=normal_snapshot['content_sha256'],
            source_section_sha256=_sha(demand['section']),source_demand_sha256=_sha(demand)),
        eligible=ready,simultaneous_local_D_qualified=ready,
        status='qualified_simultaneous_subyield_shear_lag_reference' if ready else 'pending_simultaneous_reference_guards')
    proof['content_sha256']=_sha({k:v for k,v in proof.items() if k!='content_sha256'})
    out=copy.deepcopy(base)
    out.update(schema=SCHEMA,method_revision=REVISION,technical_source_sha256=source_binding(),
        previous_bending_applicability=copy.deepcopy(base['applicability']),
        concurrent_shear_lag_supplement=proof,historical_results_requalified=False)
    if 'shear_lag_supplement' in out:
        out['previous_shear_lag_attempt']=out.pop('shear_lag_supplement')
    if ready:
        app=_applicability(base['applicability'],proof)
        stress=original._stress(demand,normal_snapshot,model_origin,normal_witness=False,
            operator_intervals=proof['operator_intervals'])
        stress.update(applicability_qualified=app['qualified'],
            raw_bounds_sufficient=stress['section_stress_criteria_sufficiently_satisfied'],
            simultaneous_local_D_ceiling_proved=True,
            concurrent_shear_lag_supplement_sha256=proof['content_sha256'],
            stress_scope='Respective effective pure Mx/My interval enclosures with simultaneous local/D ceiling; unchanged gross B/V/Tsv/Tw, no physical exceedance witness')
        stress['section_stress_criteria_sufficiently_satisfied'] &= app['qualified']
        stress['content_sha256']=_sha({k:v for k,v in stress.items() if k!='content_sha256'})
        capacities=copy.deepcopy(proof['pure_My_construction']['signed_capacity_floor'])
        capacities.update(proof['pure_Mx_construction'].get('signed_capacity_floor',{}))
        shear,mv,pieces=original._interaction(demand,normal_snapshot,normal_snapshot['shear'],
            arithmetic._source_pieces(demand),app,capacity_overrides=capacities)
        out.update(stress=stress,shear=shear,mv=mv,pieces=pieces,applicability=app,
            component_status=dict(stress='computed',shear='computed',mv='computed'),
            scope='Candidate EN6.1.6 and EN6.27 section components with own shear-lag envelopes and simultaneous subyield local/D closure. N=0; no shared effective tensor, ELS, member stability or physical-project approval.')
    # A failed guard preserves the existing pending normal/interaction records:
    # no index is manufactured merely because a positive pure floor exists.
    out['content_sha256']=_sha({k:v for k,v in out.items() if k!='content_sha256'})
    return out


def validate_saved(check,summary,*,normal_snapshot,source_sha256,model_origin):
    """Arithmetic replay under the exact new schema; no legacy reinterpretation."""
    if check.get('schema')!=SCHEMA:
        return original.validate_saved(check,summary,normal_snapshot=normal_snapshot,
            source_sha256=source_sha256,model_origin=model_origin)
    for value in (check,summary,normal_snapshot,source_sha256,model_origin):original._json_native(value)
    demand=check['source_demand']
    if _sha(demand)!=source_sha256 or check['source_analysis_sha256']!=source_sha256:
        raise ValueError('Candidate source field identity changed')
    if _sha(original._compact_source(demand))!=_sha(summary):
        raise ValueError('Candidate dense and compact sources differ')
    expected=calculate(demand,normal_snapshot=normal_snapshot,model_origin=model_origin)
    if _sha(check)!=_sha(expected):
        raise ValueError('Candidate arithmetic, guards or technical source changed')
    return True


def calculate_many(demands,*,normal_snapshot,model_origin):
    """Authenticate the closed original batch once, then extend each own row."""
    if type(demands) is not list:raise ValueError('Native list of demands required')
    bases=original.calculate_many(demands,normal_snapshot=normal_snapshot,model_origin=model_origin)
    results=[]
    for demand,base in zip(demands,bases):
        if isinstance(base,Exception):results.append(base);continue
        try:results.append(_extend(base,demand,normal_snapshot=normal_snapshot,model_origin=model_origin))
        except (ValueError,KeyError,TypeError,ArithmeticError) as error:results.append(error)
    return results


def calculate(demand,*,normal_snapshot,model_origin):
    """New calculation only; never used to migrate historical records."""
    out=calculate_many([demand],normal_snapshot=normal_snapshot,model_origin=model_origin)[0]
    if isinstance(out,Exception):raise out
    return out


def validate_saved_many(requests,*,normal_snapshot,model_origin):
    """Dispatch ONLY by saved schema. No migration or v4 cache bypass."""
    if type(requests) is not list:raise ValueError('Native list of saved requests required')
    historical=[];current=[]
    for request in requests:
        if type(request) is not dict or set(request)!={'check','summary','source_sha256'}:
            raise ValueError('Explicit saved check, summary and original source hash required')
        original._json_native(request)
        if type(request['check']) is not dict:raise ValueError('Saved check must be a native dict')
        (current if request['check'].get('schema')==SCHEMA else historical).append(request)
    if historical:
        original.validate_saved_many(historical,normal_snapshot=normal_snapshot,model_origin=model_origin)
    for request in current:
        validate_saved(**request,normal_snapshot=normal_snapshot,model_origin=model_origin)
    return True
