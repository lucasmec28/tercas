"""Scalar extraction of the existing uniform §9.2.3 flange comparator.

The pinned historical biaxial comparator is left byte-for-byte unchanged.
Only scalar arithmetic is reused here; its bending-only field is not reused.
"""
from .biaxial_gross.gross_mle import D, GUARD, LIMIT


def flange_uniform_comparator(width, t, nominal_lip, lip_width, E, sigma, *,
                              stiffener_bound='shifted_cubic'):
    """Scalar §9.2.3 sufficient comparator shared with the combined ELS route.

    Decimal arguments describe an orthogonal lip and a nonnegative uniform
    compression MAJORANT, not an isolated bending moment. The caller proves the
    stress bound, full lip effectiveness, geometry and elastic field separately.
    Use PRECISION-digit localcontext; no member/section reduction is performed.
    """
    if (any(not isinstance(v, D) or not v.is_finite()
            for v in (width, t, nominal_lip, lip_width, E, sigma))
            or min(width, t, nominal_lip, lip_width, E) <= 0 or sigma < 0):
        raise ValueError('Positive Decimal dimensions/material and nonnegative compression required.')
    if stiffener_bound not in ('shifted_cubic', 'linear'):
        raise ValueError('Unknown stiffener upper-bound policy.')
    lambda0 = width/t/D('.623')*(sigma/E).sqrt()
    threshold = LIMIT*(1-GUARD)
    Is = t*lip_width**3/12  # Orthogonal lip. Bends excluded.
    ratio = nominal_lip/width
    if not 0 < ratio <= D('.8'):
        raise ValueError('Flange D/b outside the supplied 9.2.3 formula domain.')
    full_k = min(D(4), D('3.57')+D('.43') if ratio <= D('.25')
                 else D('4.82')-5*ratio+D('.43'))
    full_lam = width/t/D('.95')*(sigma/(E*full_k)).sqrt()
    if lambda0:
        low_limit = (threshold/lambda0)**2
        linear_limit = max(D(0), (Is/(t**4*(1+GUARD))-5)/56)
        cubic_limit = LIMIT+(Is/(399*t**4*(1+GUARD)))**(D(1)/3)/D('.487')
        stiffener_lambda0_limit = (linear_limit if stiffener_bound == 'linear'
                                  else max(linear_limit, cubic_limit))
        high_limit = min((threshold/full_lam)**2, (stiffener_lambda0_limit/lambda0)**2)
        scale_limit = max(low_limit, high_limit)
    else:
        scale_limit = None
    k, Ia, Ia_upper = D('.43'), None, None
    if lambda0 <= threshold:
        lam = lambda0
        full = True
        route = '9.2.3 low-slenderness branch: edge stiffener not needed'
    else:
        # Both bounds are monotone above LIMIT and dominate the literal Ia.
        Ia = min(399*t**4*(D('.487')*lambda0-D('.328'))**3,
                 t**4*(56*lambda0+5))
        linear_upper = t**4*(56*lambda0+5)
        shifted_cube = 399*t**4*(D('.487')*max(D(0), lambda0-LIMIT))**3
        Ia_upper = linear_upper if stiffener_bound == 'linear' else min(shifted_cube, linear_upper)
        adequate = Is >= Ia_upper*(1+GUARD)
        k, lam = full_k, full_lam
        full = adequate and lam <= threshold
        route = 'Uniform flange comparator; full stiffener via Is>=monotone '+stiffener_bound+' upper bound on Ia'
    return dict(k=k, lambda_p0=lambda0, lambda_local=lam, Is_mm4=Is,
        Ia_literal_diagnostic_mm4=Ia, Ia_monotone_upper_mm4=Ia_upper,
        stiffener_upper_bound_method=stiffener_bound, full_wall_sufficient=full,
        route=route, uniform_action_scale_sufficient_limit=scale_limit)
