"""Typed exclusion of a mathematical load limit, never a physical exemption.

The finite-contact solver and the mechanical support-limit solver are unchanged.
Only newly emitted, fully matching records qualify for this scope distinction.
"""
import json
import math

SCHEMA = 'point_contact_mathematical_limit_v1'
SOURCE = 'Distinção de escopo do modelo; NBR14762:2010 §9.5.1 e Anexo D tratam o detalhe físico'
SCOPE = ('P_APOIO é somente o limite matemático a→0+ das ações, não um contato físico. '
         'Não aplicável aqui significa apenas que o critério de contato finito não é avaliado nessa coordenada limite, '
         'não dispensa normativa. A transferência local permanece uma exigência do detalhe real. '
         'P_CENTRO, quando calculado, cobre somente o contato central. '
         'Contato físico próximo à extremidade exige posição finita e detalhe próprios na opção v2, com as ações dessa posição. '
         'Não certifica outras posições, apoios, ligações ou o elemento completo.')


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _valid_combination(combination, L):
    if not isinstance(combination, dict):return False
    p=combination.get('P_vector', {})
    return (isinstance(p,dict) and combination.get('point_position')=='support_limit'
            and combination.get('limit_state') in ('ELU','ELS')
            and isinstance(combination.get('id'),str) and bool(combination['id'])
            and _finite(L) and L>0
            and _finite(combination.get('x_mm')) and combination['x_mm']==0
            and all(_finite(p.get(k)) for k in ('normal','parallel'))
            and _finite(combination.get('P_N')) and combination['P_N']>0
            and combination['P_N']==p['normal'])


def contact_exclusion(combination, L):
    """Record mathematical meaning without evaluating a resistance or geometry."""
    if not _valid_combination(combination,L):
        raise ValueError('Limite matemático de P sem combinação/forças/coordenada coerentes.')
    return dict(schema=SCHEMA,status='not_applicable',scope='mathematical_limit',
        combination_id=combination['id'],limit_state=combination['limit_state'],
        position='support_limit',a_limit='a→0+',L_mm=L,
        force_N=combination['P_vector']['normal'],parallel_force_N=combination['P_vector']['parallel'],
        source=SOURCE,reason=SCOPE,physical_contact_checked=False,
        physical_conditions_verified=False,connection_design_checked=False)


def saved_exclusion(raw, combination, L, point_vector):
    """Read-only identity/type check. A label alone never excludes a real case.

    No conversion of old not_evaluated records, no contact formula or solver.
    Exact serialized shape rejects extra resistance, index and geometry fields.
    """
    try:
        if not _valid_combination(combination,L) or not isinstance(raw,dict):return False
        if not isinstance(point_vector,dict):return False
        if not all(_finite(point_vector.get(k)) and point_vector[k]==combination['P_vector'][k]
                   for k in ('normal','parallel')):return False
        expected=contact_exclusion(combination,L)
        return json.dumps(raw,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False)
    except (ValueError,TypeError,OverflowError):
        return False
