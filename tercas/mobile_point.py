"""Load-position planning only: no normative factors and no resistance approval."""
import math

def _finite(*values):
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):
        raise ValueError('finite real inputs required')

def position_plan(L_mm, contact_mm=None):
    _finite(L_mm)
    if L_mm<=0:raise ValueError('positive span required')
    if contact_mm is None:
        return {'center_mm':L_mm/2,'left_mm':None,'right_mm':None,
                'shear_mode':'analytic_support_limits','contact_status':'not_informed',
                'note':'Support limits are global shear envelopes, not a physical point-load case at a support.'}
    _finite(contact_mm)
    if not 0<contact_mm<L_mm:raise ValueError('contact must be positive and smaller than span')
    return {'center_mm':L_mm/2,'left_mm':contact_mm/2,'right_mm':L_mm-contact_mm/2,
            'shear_mode':'physical_centroid_interval','contact_status':'provided',
            'note':'Contact footprint inside the span; this does not establish local resistance or interaction with support contact.'}

def static_response(L_mm,q_Nmm,P_N,a_mm,x_mm,side='left'):
    _finite(L_mm,q_Nmm,P_N,a_mm,x_mm)
    if L_mm<=0 or not 0<=a_mm<=L_mm or not 0<=x_mm<=L_mm:raise ValueError('outside span')
    if side not in ('left','right'):raise ValueError('unknown shear side')
    ra=q_Nmm*L_mm/2+P_N*(1-a_mm/L_mm)
    rb=q_Nmm*L_mm/2+P_N*a_mm/L_mm
    m=q_Nmm*x_mm*(L_mm-x_mm)/2+P_N*((L_mm-a_mm)*x_mm/L_mm if x_mm<=a_mm else a_mm*(L_mm-x_mm)/L_mm)
    v=ra-q_Nmm*x_mm-(P_N if x_mm>a_mm or (x_mm==a_mm and side=='right') else 0)
    return {'RA_N':ra,'RB_N':rb,'M_Nmm':m,'V_N':v,'a_mm':a_mm,'x_mm':x_mm,'shear_side':side}

def same_direction_global_envelope(L_mm,q_Nmm,P_N,contact_mm=None):
    """Exact M/V envelopes for UDL + mobile point load, same sign, simply supported.
    If no footprint is provided, V is a supremum as a approaches a support.
    M and V maxima are NOT a concomitant pair for an interaction check.
    """
    _finite(L_mm,q_Nmm,P_N)
    if q_Nmm*P_N<0:raise ValueError('opposed actions require independent signed envelope')
    p=position_plan(L_mm,contact_mm)
    q,P=abs(q_Nmm),abs(P_N)
    a=p['left_mm']
    M=q*L_mm**2/8+P*L_mm/4
    V=q*L_mm/2+P*(1-(a or 0)/L_mm)
    return {'M_abs_Nmm':M,'M_load_position_mm':L_mm/2,'M_section_mm':L_mm/2,
            'V_abs_N':V,'V_is_support_limit':a is None,
            'V_load_positions_mm':[a,p['right_mm']],
            'not_concomitant_pair':True,'position_plan':p}
