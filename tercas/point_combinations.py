"""Additional maintenance-point combinations; independent of the original 48 rows.

P=1 kN accompanying permanents only: NBR 6120:2019 §6.4.
Point ELU factor 1.5: NBR 14762:2010 (source checked by coordinating agent).
Permanent factors are the declared Lucas matrix, not a general factor generator.
No resistance, local bearing or stiffness validation is supplied by this module.
"""
import math
try:
    from .mobile_point import position_plan, same_direction_global_envelope
except ImportError:
    from mobile_point import position_plan, same_direction_global_envelope

FAMILIES = ('ELU normal', 'ELS rara', 'ELS frequente', 'ELS quase permanente')
DEFAULT_PERMANENT_FACTORS = ((1.25, 1.4), (1.25, 1.0), (1.0, 1.4), (1.0, 1.0))

def _nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value<0:
        raise ValueError(f'{name}: informe número finito não negativo.')
    return float(value)

def point_combinations(*, L_mm, case_q_N_mm, selected_types=None,
                       contact_mm=None, permanent_factors=DEFAULT_PERMANENT_FACTORS):
    """Only additive P records, no mutation, no P in wind/area-live rows.

    Reactions/shear use analytic support limits if contact is unknown. The
    independent Mmax/Vmax pair must NEVER enter an interaction check. For such
    checks use envelope_mv.py with its applicable fixed capacities, or evaluate
    all actual position-dependent resistance models separately.
    """
    types = list(FAMILIES) if selected_types is None else selected_types
    if not isinstance(types,(list,tuple)) or any(t not in FAMILIES for t in types) or len(set(types))!=len(types):
        raise ValueError('Famílias de combinação inválidas ou repetidas.')
    plan = position_plan(L_mm,contact_mm)
    if not isinstance(case_q_N_mm,dict):raise ValueError('Ações características ausentes.')
    pp=_nonnegative(case_q_N_mm.get('PP'),'PP')
    cp=_nonnegative(case_q_N_mm.get('CP'),'CP')
    pairs=[]
    for pair in permanent_factors:
        if not isinstance(pair,(tuple,list)) or len(pair)!=2:raise ValueError('Fatores permanentes inválidos.')
        gpp,gcp=(_nonnegative(pair[0],'γPP'),_nonnegative(pair[1],'γCP'))
        if min(gpp,gcp)<=0:raise ValueError('Fatores permanentes devem ser positivos.')
        if (gpp,gcp) not in pairs:pairs.append((gpp,gcp))
    if not pairs:raise ValueError('Fatores permanentes ausentes.')
    specs=[]
    if 'ELU normal' in types:
        specs += [('ELU normal','ELU',a,b,1.5) for a,b in pairs]
    if 'ELS rara' in types:specs.append(('ELS rara','ELS',1.,1.,1.))
    result=[]
    state_counts={'ELU':0,'ELS':0}
    for family,state,gpp,gcp,gp in specs:
        state_counts[state]+=1
        i=state_counts[state]
        q=gpp*pp+gcp*cp;P=1000.*gp
        if not math.isfinite(q):raise ValueError('A combinação excedeu o intervalo numérico.')
        expression=f'{gpp:g} PP + {gcp:g} CP + {gp:g} P'
        result.append({'id':f'P_{state}_{i:02d}','type':family,'limit_state':state,
            'coefficients':{'PP':gpp,'CP':gcp,'P':gp},'q_N_mm':q,'q_kN_m':q,
            'P_N':P,'P_characteristic_N':1000.,'expression':expression,
            'origin':'Caso adicional P isolado das demais ações variáveis; fatores permanentes da matriz Lucas',
            'position_plan':dict(plan),'x_mm':L_mm/2,
            'global_envelope':same_direction_global_envelope(L_mm,q,P,contact_mm),
            'local_contact_status':'pendente: comprimento de contato não informado' if contact_mm is None else 'informado: verificar domínio local',
            'mobile_resistance_status':'requer avaliação por rota; máximos M/V separados não constituem interação',
            'ELS_position_status':'posição central candidata; avaliar flecha com rigidez efetiva da combinação' if state=='ELS' else None})
    return result
