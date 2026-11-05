"""Declared scalar direct-load envelope; no guessed self-weight or torque.

Moving unknown nonnegative CG self-weight into the top load increases the
height quadratic form by h*q_PP*phi². The first positive load factor cannot
increase, independent of the sign of the combined load. This is an ordering
of the declared Vlasov models, not a certified lower numerical eigenvalue or
a bound on primary torsion, hidden biaxial forces, or physical resistance.
"""
import copy
import math
from .ltb_load_height import finite
from .core.flt_vrd import flt_mse,weff_ratio

SCHEMA='roof_top_load_evidence_v2'
BASIS='direct_total_top_envelope'
ASSUMPTIONS=dict(
    inputs='Totais já combinados nos eixos locais, incluindo PP. Nenhum PP é estimado, somado ou separado.',
    self_weight='A parcela normal de PP no CG é descendente ou nula na combinação; sua quantidade permanece desconhecida.',
    other_loads='Demais ações normais na linha superior selecionada, conservando posições longitudinais.',
    scalar_model='Idealização uniaxial forte, sem componentes paralelas individuais ocultas/canceladas ou seus efeitos geométricos.',
    physical_applicability='Estas são premissas do modelo, não verificação da terça física. Inclinação não gira novamente cargas diretas.',
    torsion='A substituição de altura não envolve torque, bimomento, giros ou interação. A decomposição continua necessária para esses efeitos.')
SCOPE=('Envoltória de altura para FLT forte do modelo uniaxial declarado: q/P totais '
       'já combinados e com PP incluído são usados no topo apenas no operador de Me. '
       'A contribuição normal desconhecida de PP no CG deve ser descendente ou nula; '
       'demais ações na linha superior. Vale sob gravidade, sucção ou sinais mistos. '
       'Não estima PP, não fornece torque real e não cobre parcelas paralelas ocultas '
       'que se cancelem. Não é aprovação física/global nem limite numérico inferior certificado.')


def combinations(data):
    out=[]
    for state,suffix in (('ELU','uls'),('ELS','sls')):
        q=finite(data['q_'+suffix],'q '+state);p=finite(data['P_'+suffix],'P '+state)
        qp=finite(data.get('q_parallel_'+suffix,0.),'q paralelo '+state)
        pp=finite(data.get('P_parallel_'+suffix,0.),'P paralelo '+state)
        out.append(dict(id='DIRECT_'+state,limit_state=state,type=state+' direto — total combinado',
            q_N_mm=q,P_N=p,x_mm=finite(data['x_'+suffix],'posição P '+state),
            q_vector=dict(normal=q,parallel=qp),P_vector=dict(normal=p,parallel=pp),
            load_basis=BASIS,source='Entradas diretas preservadas; sem nova combinação/rotação ou PP automático.'))
    return out


def actions(combo,geometry):
    out=[];h=geometry['height_above_SC_mm'];parallel=[]
    if combo['q_vector']['parallel']!=0:parallel.append('q total')
    if combo['P_vector']['parallel']!=0:parallel.append('P total')
    if combo['q_N_mm']!=0:
        out.append(dict(name='DIRECT_TOTAL_q',kind='uniform',q_down_N_mm=combo['q_N_mm'],
            height_above_SC_mm=h,x_from_SC_mm=None,load_line_source='Hipótese de altura conservadora do total; não representa a linha real de PP.',
            actual_primary_torque_known=False))
    if combo['P_N']!=0:
        out.append(dict(name='DIRECT_TOTAL_P',kind='point',P_down_N=combo['P_N'],s_mm=combo['x_mm'],
            height_above_SC_mm=h,x_from_SC_mm=None,load_line_source='Total direto na posição longitudinal informada; torque não qualificado.',
            actual_primary_torque_known=False))
    return out,parallel


def nbr_resistance_floor(Wc,Fy,Ml,Me):
    """Conservative floor of the EXISTING rounded curve over Me_real >= Me.

The original flt_mse function is unchanged. At lambda0=1.336 the rounded
expressions have one downward jump when Me increases. The local-resistance
stage is increasing in chi, so its evaluation at the capped chi gives a
floor. Capping Wef at gross W only lowers that floor. It need not equal the
exact infimum at coincident discontinuities. The result remains conditional
on the scalar model/numerical Me, not a bound on the physical B/T problem.
"""
    raw=flt_mse(Wc,Fy,Ml,Me);cap=copy.deepcopy(raw)
    chi_limit=1.11*(1-.278*1.336**2)
    adjusted=raw['lambda0']>=1.336 and raw['chi_flt']>chi_limit
    if adjusted:
        lamp=math.sqrt(chi_limit*Wc*Fy/Ml);rho,local=weff_ratio(lamp)
        cap.update(chi_flt=chi_limit,flt_branch='lower_envelope_at_rounded_transition',
            lambda_p_reduced_stress=lamp,local_branch=local,Wceff_mm3=Wc*rho,
            MRd_flt_Nmm=chi_limit*Wc*rho*Fy/1.1)
    gross_cap=cap['Wceff_mm3']>Wc
    if gross_cap:
        cap.update(Wceff_mm3=Wc,MRd_flt_Nmm=cap['chi_flt']*Wc*Fy/1.1,
            local_branch='lower_envelope_gross_cap_at_rounded_transition')
    cap.update(scope='Envoltória inferior da curva NBR publicada para Me_real >= Me adotado; somente componente de flexão pura.',
        lower_envelope=dict(applied=True,transition_correction_applied=adjusted,
            local_rounding_gross_cap_applied=gross_cap,
            lambda_transition=1.336,chi_intermediate_limit=chi_limit,
            original_formula=raw,original_formula_unchanged=True,
            arithmetic_floor_only=True,physical_resistance_bound=False))
    return cap
