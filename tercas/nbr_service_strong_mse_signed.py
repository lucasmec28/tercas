"""Local one-axis service MSE, including opposing uniform and point actions.

NBR 14762:2010 9.8.5(b), with the existing disclosed Ief <= Ig clamp.
A pure optional route: no change to the legacy single-maximum protocol, no
critical-moment inference, no load factors, limits, torsion or ELU checks.
Units are N, mm and MPa; Ml must be supplied from the qualified local method.
"""
import math
from scipy.integrate import quad
from scipy.optimize import brentq
from .bounded_polynomial import real_roots_open_unit_interval
from .core.protocolo_ief import ief, moment, positive, integration_points, max_moment


def peak_deflection(*, L_mm, E_MPa, Ig_mm4, Ml_Nmm, q_Nmm=0., P_N=0., a_mm=None):
    """Return the largest absolute signed deflection on a simply supported span.

    v(z) = integral(M(x) m_unit(x,z) / (E Ief(x))) dx. Since
    v'' = -M/(E Ief), slope is monotone between moment zeros and the
    point action. Every isolated stationary point is bracketed separately.
    Zero-curvature intervals are affine, so their endpoints suffice even
    when the entire interval is stationary. Quadrature also splits at both
    signed crossings of the clamped stiffness transition. No abs(q)/abs(P).
    """
    L,E,Ig,Ml,q,P = map(float,(L_mm,E_MPa,Ig_mm4,Ml_Nmm,q_Nmm,P_N))
    a=L/2 if a_mm is None else float(a_mm)
    positive(L,E,Ig,Ml)
    if not all(math.isfinite(v) for v in (q,P,a)) or not 0<=a<=L:
        raise ValueError('Invalid signed service actions or point position')
    threshold=((1+math.sqrt(1-4*.22))/2)**2*Ml
    reaction=q*L/2+P*(L-a)/L
    zeros=[]; transitions=[]; flat=[]
    for lo,hi,after in ((0.,a,False),(a,L,True)):
        length=hi-lo
        if length<=0: continue
        m0=moment(lo,L,q,P,a)
        v0=reaction-q*lo-(P if after else 0.)
        linear=v0*length; quadratic=-q*length*length/2
        if m0==linear==quadratic==0: flat.append((lo,hi))
        for target,destination in ((0.,zeros),(threshold,transitions),(-threshold,transitions)):
            destination.extend(lo+t*length for t in
                real_roots_open_unit_interval((m0-target,linear,quadratic)))
    maxm=max_moment((L,E,Ig,Ml,q,P,a))
    imin=ief(Ig,maxm,Ml)
    extra=[*zeros,*transitions]

    def integral(z, derivative=False):
        if not derivative and z in (0.,L): return 0.
        def integrand(x):
            mm=moment(x,L,q,P,a)
            kernel=(-x/L if x<=z else (L-x)/L) if derivative else (
                (L-z)*x/L if x<=z else z*(L-x)/L)
            return mm*kernel/(E*ief(Ig,mm,Ml))
        points=integration_points(L,a,z,extra)
        values=[quad(integrand,lo,hi,epsabs=1e-12 if derivative else 1e-9,
                     epsrel=1e-10,limit=200)
                for lo,hi in zip(points,points[1:]) if hi>lo]
        result=math.fsum(value for value,error in values)
        error=math.fsum(error for value,error in values)
        if error>max(1e-10 if derivative else 1e-7,abs(result)*1e-6):
            raise ArithmeticError('Signed service MSE quadrature error bound exceeded')
        return result

    # Keep physical candidates; only quadrature coalesces ULP-sized intervals.
    bounds=sorted(set([0.,L,a,*zeros]))
    candidates={z:integral(z) for z in bounds}
    stationary=[]
    slopes={z:integral(z,True) for z in bounds}
    for lo,hi in zip(bounds,bounds[1:]):
        sl,sh=slopes[lo],slopes[hi]
        if sl==0: stationary.append(lo)
        if sh==0: stationary.append(hi)
        if (sl<0<sh) or (sh<0<sl):
            x=brentq(lambda z:integral(z,True),lo,hi,
                     xtol=max(math.ulp(L),1e-12*L),rtol=4*math.ulp(1.))
            candidates[x]=integral(x)
            stationary.append(x)
    x=max(candidates,key=lambda z:abs(candidates[z]))
    delta=candidates[x]
    return dict(status='computed_local_strong_service_MSE',
        method='NBR9.8.5(b)_pointwise_MSE_signed', physical_span_mm=L,
        q_Nmm=q,P_N=P,a_mm=a,E_MPa=E,Ig_mm4=Ig,Ml_Nmm=Ml,
        peak_x_mm=x,deflection_mm=delta,absolute_deflection_mm=abs(delta),
        max_abs_moment_Nmm=maxm,min_Ief_mm4=imin,
        stiffness_clamp='min(Ig, Ief_literal)',
        moment_zero_points_mm=sorted(set(zeros)),
        stiffness_transition_points_mm=sorted(set(transitions)),
        stiffness_transition_abs_moment_Nmm=threshold,
        zero_curvature_intervals_mm=flat,
        stationary_points_mm=sorted(set(stationary)),
        peak_candidates=sorted(candidates.items()),
        local_elastic_critical_inferred=False,self_weight_added=False,
        scope='Conventional local strong-axis flexural deflection only',
        whole_member_approved=False)
