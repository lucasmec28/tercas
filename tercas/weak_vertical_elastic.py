"""Conditional gross elastic beam study. N, mm; downward y/q/P positive.
No strength, effective inertia, restraint qualification, or approval is provided.
"""
from math import isfinite


def _solve(A, b):
    """Small dense system with partial pivoting; no external dependency."""
    a = [list(row) + [v] for row, v in zip(A, b)]
    n = len(b)
    for j in range(n):
        p = max(range(j, n), key=lambda i: abs(a[i][j]))
        if a[p][j] == 0:
            raise ArithmeticError('Singular compatibility matrix')
        a[j], a[p] = a[p], a[j]
        v = a[j][j]
        a[j] = [x/v for x in a[j]]
        for i in range(n):
            if i != j:
                v = a[i][j]
                a[i] = [x-v*y for x, y in zip(a[i], a[j])]
    return [row[-1] for row in a]


def _green(x, a, L, EI):
    # Simply supported unit downward point load; reciprocity explicit.
    u, v = min(x, a), max(x, a)
    return u*(L-v)*(L*L-u*u-(L-v)**2)/(6*L*EI)


def _value(c, x):
    ans = 0.
    for v in reversed(c):
        ans = ans*x+v
    return ans


def _roots(c, lo, hi):
    """All real roots on closed interval, derivative isolation + bisection."""
    c = list(c)
    while len(c) > 1 and c[-1] == 0:
        c.pop()
    scale = max(map(abs, c), default=0.)
    if len(c) == 1 or scale == 0:
        return []
    c = [v/scale for v in c]
    if len(c) == 2:
        r = -c[0]/c[1]
        return [min(hi, max(lo, r))] if lo-1e-13 <= r <= hi+1e-13 else []
    cuts = [lo]+_roots([i*c[i] for i in range(1, len(c))], lo, hi)+[hi]
    roots = [v for v in cuts if abs(_value(c, v)) < 2e-13]
    for left, right in zip(cuts, cuts[1:]):
        fl, fr = _value(c, left), _value(c, right)
        if fl*fr >= 0:
            continue
        for _ in range(60):
            mid = (left+right)/2
            fm = _value(c, mid)
            if fl*fm <= 0:
                right = mid
            else:
                left, fl = mid, fm
        roots.append((left+right)/2)
    return sorted(set(roots))


def _unilateral(A, d):
    # min .5 R^T A R-d^T R, R>=0; A=F+diag(1/k), SPD.
    n = len(d)
    R, free = [0.]*n, set()
    tol = 2e-12*max(max(map(abs, d), default=0.), 1e-12)
    for iteration in range(max(20, 20*n*n)):
        grad = [sum(A[i][j]*R[j] for j in range(n))-d[i] for i in range(n)]
        outside = [i for i in range(n) if i not in free and grad[i] < -tol]
        if not outside:
            return R, iteration
        free.add(min(outside, key=lambda i: grad[i]))
        while True:
            ids = sorted(free)
            z = [0.]*n
            for i, v in zip(ids, _solve([[A[i][j] for j in ids] for i in ids], [d[i] for i in ids])):
                z[i] = v
            bad = [i for i in ids if z[i] <= 0]
            if not bad:
                R = z
                break
            alpha = min(R[i]/(R[i]-z[i]) if R[i] != z[i] else 0. for i in bad)
            R = [r+alpha*(v-r) for r, v in zip(R, z)]
            removed = [i for i in bad if R[i] <= 1e-12*max(1., max(R))]
            if not removed:
                raise ArithmeticError('Active set stalled')
            for i in removed:
                R[i] = 0.
                free.remove(i)
    raise ArithmeticError('Active set did not converge; no result released')


def study_weak_vertical(*, L, E, Iy, q=0., P=0., a=None, springs=()):
    """Return gross elastic diagnostic, never a regulatory check.

    L,E,Iy >0 [mm,N/mm²,mm4]; q>=0 [N/mm], P>=0 [N];
    a [mm] required when P>0, fixed along member. Each spring is
    {'x': interior position mm, 'k': finite positive N/mm, 'origin': nonempty
    source/assumption description}. Anchors fixed; reaction upward only;
    no gap/prestress. End supports bilateral simple supports. Constant EI.
    """
    vals = (L, E, Iy, q, P)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v) for v in vals):
        raise ValueError('Finite real beam/load inputs required')
    if min(L, E, Iy) <= 0 or min(q, P) < 0:
        raise ValueError('Positive L,E,Iy and nonnegative downward q,P required')
    if a is None:
        if P:
            raise ValueError('Fixed point-load position a required')
        a = L/2
    if not isinstance(a, (int, float)) or isinstance(a, bool) or not isfinite(a) or not 0 <= a <= L:
        raise ValueError('a must lie on beam')
    springs = [dict(s) for s in springs]
    for s in springs:
        if not all(isinstance(s.get(key), (int, float)) and not isinstance(s[key], bool) and isfinite(s[key]) for key in ('x', 'k')):
            raise ValueError('Finite spring x,k required; no infinite default support')
        if not 0 < s['x'] < L or s['k'] <= 0 or not isinstance(s.get('origin'), str) or not s['origin'].strip():
            raise ValueError('Interior x, positive k and stated origin required')
    EI = E*Iy
    if not isfinite(EI) or EI == 0:
        raise ValueError('EI outside floating-point range')
    F = [[_green(s['x'], t['x'], L, EI) for t in springs] for s in springs]
    d = [q*s['x']*(L**3-2*L*s['x']**2+s['x']**3)/(24*EI)+P*_green(s['x'], a, L, EI) for s in springs]
    A = [[v+(1/springs[i]['k'] if i == j else 0.) for j, v in enumerate(row)] for i, row in enumerate(F)]
    R, iterations = _unilateral(A, d)
    points = [(a, P)]+[(s['x'], -r) for s, r in zip(springs, R)]
    RA = q*L/2+sum(f*(L-x)/L for x, f in points)
    RB = q*L+sum(f for _, f in points)-RA
    C = RA*L**3/6-q*L**4/24-sum(f*L**3*(1-x/L)**3/6 for x, f in points)
    def y(x):
        t = x/L
        return (C*t-RA*L**3*t**3/6+q*L**4*t**4/24+sum(f*L**3*max(t-xp/L, 0.)**3/6 for xp, f in points))/EI
    def M(x):
        return RA*x-q*x*x/2-sum(f*max(x-xp, 0.) for xp, f in points)
    cuts = sorted(set([0., 1.]+[x/L for x, _ in points]))
    yd, md = set(cuts), set(cuts)
    for left, right in zip(cuts, cuts[1:]):
        slope = [C, 0., -RA*L**3/2, q*L**4/6]
        shear = [RA*L, -q*L*L]
        for xp, f in points:
            t = xp/L
            if t <= left:
                slope[0] += f*L**3*t*t/2
                slope[1] -= f*L**3*t
                slope[2] += f*L**3/2
                shear[0] -= f*L
        yd.update(_roots(slope, left, right))
        md.update(_roots(shear, left, right))
    yvals = [{'x_mm': t*L, 'value_mm': y(t*L)} for t in sorted(yd)]
    mvals = [{'x_mm': t*L, 'value_Nmm': M(t*L)} for t in sorted(md)]
    residuals = []
    sr = []
    for i, (s, r) in enumerate(zip(springs, R)):
        displacement = d[i]-sum(F[i][j]*R[j] for j in range(len(R)))
        residuals.append(r-s['k']*max(displacement, 0.))
        sr.append(dict(s, reaction_up_N=r, displacement_down_mm=displacement, active=r>0))
    warnings = ['Conditional constant-Ig Euler–Bernoulli diagnostic; not Ief or approval.',
                'Fixed spring anchors and stated stiffness are assumptions, not qualified physical data.',
                'No change to FLT, strength, interaction, or regulatory ELS reference length.',
                'End supports are bilateral; no gap, prestress, torsion, shear or connection deformation.']
    mmin = min(mvals, key=lambda z: z['value_Nmm'])
    if mmin['value_Nmm'] < -1e-10*max(1., (q*L+P)*L):
        warnings.append('Negative My occurs: compression side can reverse; resistance is not assessed.')
    if min(RA, RB) < -1e-10*max(1., q*L+P):
        warnings.append('End uplift reaction: bilateral support assumption requires physical verification.')
    if max(map(abs, residuals), default=0.) > 1e-7*max(1., q*L+P):
        warnings.append('Spring-law residual exceeds numerical diagnostic threshold; very stiff springs may be ill-conditioned. Do not silently accept.')
    if not all(isfinite(z) for z in [RA, RB, C]+R+[v['value_mm'] for v in yvals]+[v['value_Nmm'] for v in mvals]):
        raise ArithmeticError('Nonfinite result; no diagnostic released')
    return {'model': 'gross_elastic_conditional_v1', 'inputs': dict(L=L,E=E,Iy=Iy,q=q,P=P,a=a),
            'springs': sr, 'end_reactions_up_N': [RA,RB],
            'deflection_max_down': max(yvals,key=lambda z:z['value_mm']),
            'deflection_min_down': min(yvals,key=lambda z:z['value_mm']),
            'deflection_max_abs': max(yvals,key=lambda z:abs(z['value_mm'])),
            'My_min': mmin, 'My_max': max(mvals,key=lambda z:z['value_Nmm']),
            'extrema_candidates': {'deflection':yvals, 'My':mvals},
            'residuals': {'vertical_equilibrium_N':RA+RB+sum(R)-q*L-P,
                          'moment_equilibrium_Nmm':RB*L+sum(r*s['x'] for s,r in zip(springs,R))-q*L*L/2-P*a,
                          'spring_law_max_abs_N':max(map(abs,residuals),default=0.),
                          'end_deflection_max_abs_mm':max(abs(y(0)),abs(y(L)))},
            'active_set_iterations':iterations, 'warnings':warnings}
