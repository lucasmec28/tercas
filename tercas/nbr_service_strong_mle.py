"""NBR 14762:2010 9.8.5(a): conventional local strong-axis service MLE.

Only the four complete Ue rows outside Table 12(b) are enabled. This is the
scalar flexural deflection component, not coupled bending/torsion or approval
of a member. No elastic critical is inferred from a resistance or stiffness.
Units: N, mm, MPa. Supplied actions already include their service combination.
"""
from functools import lru_cache
import math
from scipy.integrate import quad
from scipy.optimize import brentq
from . import nbr_ue_family as family
from .nbr_ue_family_expansion import strong_effective_modulus, OutsideMethod
from .core.protocolo_ief import moment, integration_points
from .bounded_polynomial import real_roots_open_unit_interval

INDICES = (79, 80, 81, 82)
SOURCE = dict(standard='ABNT NBR 14762:2010', clauses=['9.8.5(a)', '9.2.2.2', '9.2.3', 'Table 5'],
    pages_PDF_one_based=[33,34,35,57,58],
    sha256='c2a01615a3ce9e2b93aeb7fee757f7bf9dd932adaefbc242e848ce813dc82407')


def _law(index, material):
    if index not in INDICES:
        raise OutsideMethod('Service MLE route restricted to complete rows 79–82')
    p, props = family._geometry(index)
    m = family.material_values(family.DEFAULT_MATERIAL if material is None else material)
    fy = m['fy_MPa']; ig = props['Ix_strong_mm4']
    @lru_cache(maxsize=4096)
    def section(magnitude):
        if not math.isfinite(magnitude) or magnitude < 0:
            raise ValueError('Moment magnitude must be finite and nonnegative')
        if magnitude == 0:
            return dict(Ixef_mm4=ig, stress_MPa=0., residual_MPa=0., iterations=0,
                        Wc_mm3=ig/(p['h']/2), Aef_mm2=props['A_mm2'],
                        root_bracket_MPa=[0.,0.], root_method='zero_moment')
        # Widths depend on compression of the effective section, not gross stress.
        # A bracketed scalar iteration avoids an unverified fixed-point fallback.
        count = 0
        def residual(s):
            nonlocal count
            count += 1
            if s == 0: return -magnitude/(ig/(p['h']/2))
            sec = strong_effective_modulus(p, props, m, s)
            return s-magnitude/sec['Wc_mm3']
        lo=0.; hi=min(fy,magnitude/(ig/(p['h']/2)))
        boundary=fy
        # Grow only as far as the actual service demand requires. A reduced
        # web at fy must not disqualify a low-service full-web solution.
        for _ in range(160):
            try: value=residual(hi)
            except OutsideMethod:
                boundary=hi;hi=(lo+hi)/2
                if hi-lo<=1e-11*max(1.,hi):
                    raise OutsideMethod('Service root reaches an unimplemented effective-section domain')
                continue
            if value>=0: break
            lo=hi
            if lo>=fy:
                raise OutsideMethod('Service compression exceeds the elastic MLE stress domain')
            hi=min(boundary, max(hi*1.15,hi+1e-8))
        else:
            raise OutsideMethod('Service stress bracket did not converge')
        stress = hi if value==0 else brentq(residual, lo, hi, xtol=1e-10, rtol=1e-13)
        sec = strong_effective_modulus(p, props, m, stress)
        error = stress-magnitude/sec['Wc_mm3']
        if abs(error) > 1e-7*max(1., stress):
            raise OutsideMethod('Effective-width iteration did not reach service stress compatibility')
        if magnitude/sec['Wt_mm3'] > fy*(1+1e-10):
            raise OutsideMethod('Service tensile stress exceeds the elastic domain')
        # Floating cancellation on the gross branch cannot create extra rigidity.
        sec = dict(sec, Ixef_mm4=min(ig, sec['Ixef_mm4']), residual_MPa=error, iterations=count,
                   root_bracket_MPa=[lo,hi], root_method='brentq_service_stress_compatibility',
                   global_uniqueness_proof_claimed=False)
        return sec
    return section, m, props


def section_at_moment(index, moment_Nmm, *, material=None):
    if not math.isfinite(moment_Nmm): raise ValueError('Moment must be finite')
    law, _, _ = _law(index, material)
    return dict(law(abs(moment_Nmm)), moment_Nmm=moment_Nmm,
                source_service=SOURCE, sign_reflected_by_horizontal_symmetry=moment_Nmm<0,
                local_elastic_critical_inferred=False, whole_member_approved=False)


def peak_deflection(index, *, L_mm, q_Nmm=0., P_N=0., a_mm=None, material=None):
    """Signed uniform + one point action on the physical simply supported span.

    Integrates pointwise service MLE curvature and finds ALL stationary points.
    Moment-zero intervals make slope monotone, including opposite-sign actions.
    No load, self-weight, length reduction, limits or action factors are added.
    """
    L=float(L_mm); q=float(q_Nmm); P=float(P_N); a=L/2 if a_mm is None else float(a_mm)
    if not all(map(math.isfinite, (L,q,P,a))) or L<=0 or not 0<=a<=L:
        raise ValueError('Invalid span or signed service actions')
    law,m,props = _law(index, material); E=m['E_MPa']
    roots=[]; extrema=[0.,L,a]
    reaction=q*L/2+P*(L-a)/L
    for lo,hi,after in ((0.,a,False),(a,L,True)):
        length=hi-lo
        if length<=0: continue
        v=reaction-q*lo-(P if after else 0.)
        coeff=(moment(lo,L,q,P,a),v*length,-q*length*length/2)
        roots += [lo+t*length for t in real_roots_open_unit_interval(coeff)]
        if q and lo<=lo+v/q<=hi: extrema.append(lo+v/q)
    maxm=max(abs(moment(x,L,q,P,a)) for x in extrema)
    peak_section=law(maxm)  # Fail before integration if service stress is outside.
    def curvature(x):
        mm=moment(x,L,q,P,a)
        return mm/(E*law(abs(mm))['Ixef_mm4'])
    def integrate(z, derivative=False):
        def integrand(x):
            kernel=(-x/L if x<=z else (L-x)/L) if derivative else ((L-z)*x/L if x<=z else z*(L-x)/L)
            return curvature(x)*kernel
        points=integration_points(L,a,z,roots+extrema)
        results=[quad(integrand,lo,hi,epsabs=1e-9 if not derivative else 1e-12,
                      epsrel=1e-9,limit=150) for lo,hi in zip(points,points[1:]) if hi>lo]
        value=sum(r[0] for r in results); error=sum(r[1] for r in results)
        if error>max(1e-7 if not derivative else 1e-10,abs(value)*1e-6):
            raise OutsideMethod('Service MLE curvature quadrature did not meet its error bound')
        return value
    bounds=sorted(set([0.,L,a,*roots])); candidates=[(0.,0.),(L,0.)]
    for lo,hi in zip(bounds,bounds[1:]):
        sl,sh=integrate(lo,True),integrate(hi,True)
        if sl==0: candidates.append((lo,integrate(lo)))
        if sh==0: candidates.append((hi,integrate(hi)))
        if sl*sh<0:
            x=brentq(lambda z: integrate(z,True),lo,hi,xtol=1e-7)
            candidates.append((x,integrate(x)))
    x,delta=max(candidates,key=lambda item:abs(item[1]))
    return dict(status='computed_local_strong_service_MLE', method='NBR9.8.5(a)_pointwise_MLE',
        catalog_index=index, physical_span_mm=L, q_Nmm=q, P_N=P, a_mm=a,
        peak_x_mm=x, deflection_mm=delta, absolute_deflection_mm=abs(delta),
        max_abs_moment_Nmm=maxm, section_at_max_moment=peak_section,
        stationary_candidates=candidates, source=SOURCE,
        local_elastic_critical_inferred=False, self_weight_added=False,
        scope='Conventional local strong-axis flexural deflection only',
        whole_member_approved=False)
