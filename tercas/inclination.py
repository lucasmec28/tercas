"""Independent prototype: geometry/actions and restricted NBR14762 weak bending.
Not wired to production. No roof-sheet restraint and no inferred weak resistance.
Sources: NBR14762:2010 9.8.2.2, 9.9 and Annex E pp48,53,82.
"""
import math


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise ValueError(f'{name}: finite numeric value required')
    if positive and value <= 0:
        raise ValueError(f'{name}: must be positive')
    return float(value)


def angle(value, unit='degrees'):
    value=number(value,'inclination')
    if unit=='percent': theta=math.atan(value/100)
    elif unit=='degrees': theta=math.radians(value)
    else: raise ValueError('unit must be degrees or percent')
    if abs(theta)>=math.pi/2: raise ValueError('roof angle must be between -90 and 90 degrees')
    return {'radians':theta,'degrees':math.degrees(theta),'percent':100*math.tan(theta)}


def tributary_width(spacing, theta, spacing_basis='roof', load_area_basis='roof'):
    spacing=number(spacing,'spacing',True); theta=number(theta,'theta')
    if abs(theta)>=math.pi/2: raise ValueError('invalid roof angle')
    if spacing_basis not in ('roof','horizontal') or load_area_basis not in ('roof','horizontal'):
        raise ValueError('area and spacing basis must be explicit roof or horizontal')
    roof=spacing if spacing_basis=='roof' else spacing/math.cos(theta)
    return roof if load_area_basis=='roof' else roof*math.cos(theta)


def decompose(vertical, normal_wind, theta):
    """Signed downward gravity and inward normal wind. Same force/length unit.
    Local normal toward roof; local parallel downslope for positive theta.
    Web is assumed perpendicular to roof, member parallel to eaves.
    """
    vertical=number(vertical,'vertical'); normal_wind=number(normal_wind,'normal_wind');theta=number(theta,'theta')
    if abs(theta)>=math.pi/2: raise ValueError('invalid roof angle')
    return {'normal':vertical*math.cos(theta)+normal_wind,'parallel':vertical*math.sin(theta)}


def area_actions(pressure_kgfm2, spacing_m, theta, *, direction, spacing_basis, load_area_basis):
    q=number(pressure_kgfm2,'pressure')*tributary_width(spacing_m,theta,spacing_basis,load_area_basis)*9.80665/1000
    if direction=='vertical': return decompose(q,0,theta)
    if direction=='normal': return decompose(0,q,theta)
    raise ValueError('direction must be vertical or normal')


def self_weight(mass_kgm,theta):
    return decompose(number(mass_kgm,'mass_kgm',True)*9.80665/1000,0,theta)


def combine(cases,factors):
    """Superpose signed characteristic actions, not ratios/resistances."""
    out={'normal':0.,'parallel':0.}
    for key,factor in factors.items():
        if key not in cases: raise ValueError(f'missing case {key}')
        f=number(factor,'factor')
        for axis in out: out[axis]+=f*number(cases[key][axis],axis)
    return out


def annex_e_critical(*, Nex_N, Nez_N, r0_mm, j_mm, Cs, Cm, provenance):
    """Annex E.2 elastic critical. Caller must supply section convention/sign.
    Cs=+1 compression on negative-x/shear-centre side; -1 opposite.
    j is signed section parameter, not torsional J. No automatic Cb substitution.
    """
    if not isinstance(provenance,str) or not provenance.strip(): raise ValueError('critical input provenance required')
    nx=number(Nex_N,'Nex',True); nz=number(Nez_N,'Nez',True); r=number(r0_mm,'r0',True)
    j=number(j_mm,'j'); cm=number(Cm,'Cm',True)
    if not .2<=cm<=1.: raise ValueError('Annex E Cm must be in [0.2, 1.0]')
    if isinstance(Cs,bool) or Cs not in (-1,1):raise ValueError('Cs must be +1 or -1 per Annex E')
    a=r*r*nz/nx; root=math.sqrt(j*j+a)
    # (sqrt(j²+a)+Cs*j), evaluated without destructive cancellation.
    term=root+Cs*j
    if Cs*j<0: term=a/(root-Cs*j)
    me=nx/cm*term
    return {'Me_Nmm':me,'source':'NBR14762:2010 Annex E.2 p82','provenance':provenance,'resistance_evaluated':False}


def weak_resistance(*, W_mm3, Wc_mm3, fy_MPa, Me_Nmm, Ml_Nmm=None, Mdist_Nmm=None,
                    distortional_not_applicable=False, family=None, provenance='', gamma=1.1):
    """MSE subset; supplied elastic criticals must be for weak axis AND sense.
    W is the modulus of the first-yield fibre; Wc is the compression-fibre
    modulus used ONLY for FLT. No strong-axis Table12/14 reuse. Ue requires Mdist. A documented plain-U
    nonapplicability can omit it; user must not infer that from roof restraint.
    """
    if not isinstance(provenance,str) or not provenance.strip(): return {'status':'not_evaluated','missing':['weak-axis/sense property and critical provenance']}
    W=number(W_mm3,'W',True);Wc=number(Wc_mm3,'Wc',True)
    if W>Wc: raise ValueError('W for first-yield fibre cannot exceed Wc')
    fy=number(fy_MPa,'fy',True);me=number(Me_Nmm,'Me',True);g=number(gamma,'gamma',True)
    missing=[]
    if distortional_not_applicable and family!='U':
        raise ValueError('only documented plain-U nonapplicability accepted; no Table14 weak-axis exemption')
    if Ml_Nmm is None:missing.append('weak-axis/sense Ml or qualified effective-section route')
    if Mdist_Nmm is None and not distortional_not_applicable:missing.append('weak-axis/sense Mdist or documented nonapplicability')
    if missing:return {'status':'not_evaluated','missing':missing,'Me_Nmm':me}
    ml=number(Ml_Nmm,'Ml',True);wy=W*fy;wcy=Wc*fy
    lam=math.sqrt(wcy/me)
    chi=1. if lam<=.6 else 1.11*(1-.278*lam*lam) if lam<1.336 else 1/(lam*lam)
    ratio=lambda x:1. if x<=.673 else (1-.22/x)/x
    local=wy*ratio(math.sqrt(wy/ml))/g
    flt=chi*wcy*ratio(math.sqrt(chi*wcy/ml))/g
    caps={'local':local,'FLT':flt}
    if Mdist_Nmm is not None:caps['distortional']=wy*ratio(math.sqrt(wy/number(Mdist_Nmm,'Mdist',True)))/g
    return {'status':'computed_restricted','MRd_Nmm':min(caps.values()),'capacities_Nmm':caps,
            'source':'NBR14762:2010 9.8.2.1–3','provenance':provenance,'whole_member_approved':False}


def biaxial_interaction(Mx_Nmm,My_Nmm,MxRd_Nmm,MyRd_Nmm):
    """Section-coincident moments, same combination. N=0 subset of 9.9."""
    mx=number(Mx_Nmm,'Mx');my=number(My_Nmm,'My')
    if MxRd_Nmm is None or (my!=0 and MyRd_Nmm is None):
        return {'status':'not_evaluated','reason':'missing applicable resistance per axis/sense'}
    ix=abs(mx)/number(MxRd_Nmm,'MxRd',True)
    iy=0. if my==0 else abs(my)/number(MyRd_Nmm,'MyRd',True)
    return {'status':'computed','index':ix+iy,'meets':ix+iy<=1.,'source':'NBR14762:2010 9.9, N=0','whole_member_approved':False}


def weak_shear_status(Vparallel_N):
    v=number(Vparallel_N,'Vparallel')
    return {'status':'not_demanded' if v==0 else 'not_evaluated','Vparallel_N':v,
            'reason':'9.8.3 web VRd is not reused for shear parallel to flanges'}


def simply_supported_state(L_mm,x_mm,q_Nmm,P_N=0.,a_mm=None,side='right'):
    """Coincident two-axis M,V and reactions. One span, no lateral support
    inferred from effective FLT lengths; point force at same a in both axes.
    Supply P as a decomposed vector for vertical gravity on an inclined roof.
    A scalar P is a LOCAL NORMAL force, never implicitly vertical.
    N/mm equals kN/m numerically. Reactions in N and moments in N mm.
    """
    L=number(L_mm,'L',True);x=number(x_mm,'x');a=L/2 if a_mm is None else number(a_mm,'a')
    if not 0<=x<=L or not 0<=a<=L:raise ValueError('x and a must be within span')
    if side not in ('left','right'):raise ValueError('side must be left or right')
    out={}
    pvec=P_N if isinstance(P_N,dict) else {'normal':P_N,'parallel':0.}
    for axis in ('normal','parallel'):
        q=number(q_Nmm[axis],axis+' q');p=number(pvec[axis],axis+' P')
        ra=q*L/2+p*(L-a)/L;rb=q*L/2+p*a/L
        jump=p if x>a or (x==a and side=='right') else 0.
        out[axis]={'M_Nmm':ra*x-q*x*x/2-p*max(0.,x-a),'V_N':ra-q*x-jump,
                   'Rleft_N':ra,'Rright_N':rb}
    return out
