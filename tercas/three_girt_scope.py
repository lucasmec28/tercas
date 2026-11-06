"""Versioned verification selection. Never a structural-model projection."""
import copy

FIELD = 'verification_scope'
SCHEMA = 'three_girt_middle_verification_v1'
LEVELS = ('upper', 'middle', 'lower')
NOTICE = ('Verificações dirigidas somente à travessa CENTRAL. Superior e inferior são contexto do modelo: '
          'mantêm ações, rigidez, deslocamentos, forças e reações. Não há aprovação global, de estabilidade ou dos tirantes.')


def record(input_fingerprint):
    return dict(schema=SCHEMA, verified_members=['middle'], model_members=list(LEVELS),
                source_input_fingerprint=input_fingerprint, requires_fresh_calculation=True)


def members(demand):
    scope=demand.get(FIELD)
    if scope is None:return LEVELS  # Historical snapshots retain their original meaning.
    if scope != record(demand.get('input_fingerprint')):
        raise ValueError('Escopo de verificação desconhecido ou alterado; calcule novamente.')
    return ('middle',)


def central(demand):return members(demand)==('middle',)


def view(component, demand):
    """Presentation copy AFTER source validation; never pass it to a solver/reader."""
    if component is None or not central(demand):return component
    out=copy.deepcopy(component)
    if 'per_member' in out:out['per_member']={k:v for k,v in out['per_member'].items() if k=='middle'}
    for case in out.get('cases',[]):
        if 'members' in case:case['members']={k:v for k,v in case['members'].items() if k=='middle'}
    if 'sufficient_combinations' in out:
        for case in out['cases']:
            local=local_guard(case,'middle')
            case['central_local_normal_gross_sufficient']=local
            r=case['members']['middle'];ratio=r['diagnostic_gross_ratio']
            # View-only fields, never serialized as a recalculated component.
            r['comparison']=('within_declared_limit_in_gross_linear_model' if ratio<=1 else 'above_declared_limit_in_gross_linear_model') if local else 'local_normal_gross_proof_inconclusive'
            r['horizontal_limit_satisfied_in_declared_model']=bool(local and ratio<=1)
    return out


def axial_demand(demand, sign):
    """Exact constant N field in the selected ELU members, not a capacity check."""
    return any(sign*b['normal_action_polynomials']['N_N'][0]>0
               for case in demand.get('cases',[]) if case['combination']['limit_state']=='ELU'
               for b in case['model']['beams'] if b['girt'] in members(demand))


def local_guard(case, member):
    rows=[r for r in case['segments'] if r['girt']==member]
    return bool(rows) and all(r['section']['local_normal_gross_sufficient'] is True for r in rows)
