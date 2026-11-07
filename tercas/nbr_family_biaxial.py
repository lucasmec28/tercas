"""Exact signed N=0 interaction arithmetic, for a qualified family consumer.

NBR14762:2010 9.9: simultaneous moments, axis/sign-specific design resistances.
This module does not qualify supplied resistances, load heights or stability.
Four quadratic forms per physical load interval give the continuous maximum.
No sampled maximum, sign migration, or independent-maximum addition is used.
"""
from fractions import Fraction as F
import math

SCHEMA = 'NBR_family_signed_biaxial_arithmetic_v1'
SCOPE = 'NBR14762:2010 9.9, N=0; aritmética concomitante com resistências fornecidas pelo consumidor qualificado.'
NAMES = ('Mx_positive', 'Mx_negative', 'My_positive', 'My_negative')


def _real(value, name, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError('Número finito inválido: ' + name)
    return F(value)


def _bound(value, upwards):
    f = float(value)
    if (upwards and F(f) < value) or (not upwards and F(f) > value):
        f = math.nextafter(f, math.inf if upwards else -math.inf)
    return f


def _coefficients(combo, L, a, after, axis):
    q = _real(combo['q_vector'][axis], 'q ' + axis)
    p = _real(combo['P_vector'][axis], 'P ' + axis)
    return (-q/2, q*L/2+p*(L-a)/L-(p if after else 0), p*a if after else F(0))


def _value(co, x):
    return (co[0]*x+co[1])*x+co[2]


def _stations(co, lo, hi):
    xs = [lo, hi]
    if co[0]:
        vertex = -co[1]/(2*co[0])
        if lo < vertex < hi:
            xs.append(vertex)
    return xs


def interaction(combo, span_mm, capacities):
    """Exact rational certificate, including absent-but-unneeded signed branches.

Each input float is interpreted as its exact binary rational value. An absent
resistance is permitted only if the corresponding signed moment is nowhere
positive, proved by all endpoints and interior vertices of every load interval.
"""
    L = _real(span_mm, 'vão físico', True)
    a = _real(combo['x_mm'], 'posição P')
    if not 0 <= a <= L or not isinstance(capacities, dict) or set(capacities) != set(NAMES):
        raise ValueError('Posição P ou inventário resistente inválido.')
    caps = {k: None if capacities[k] is None else _real(capacities[k], k, True) for k in NAMES}
    pieces = [(lo, hi, after) for lo, hi, after in ((F(0), a, False), (a, L, True)) if lo < hi]
    fields = [(lo, hi, after, _coefficients(combo, L, a, after, 'normal'),
               _coefficients(combo, L, a, after, 'parallel')) for lo, hi, after in pieces]
    active, sign_proof = {}, []
    for axis, i in (('Mx', 3), ('My', 4)):
        lows, highs = [], []
        for row in fields:
            lo, hi = row[:2]; co = row[i]
            xs = _stations(co, lo, hi); values = [_value(co, x) for x in xs]
            lows.append(min(values)); highs.append(max(values))
            sign_proof.append(dict(axis=axis, start_exact=str(lo), end_exact=str(hi),
                coefficients_exact=[str(c) for c in co], candidate_positions_exact=[str(x) for x in xs],
                minimum_exact=str(min(values)), maximum_exact=str(max(values))))
        active[axis+'_positive'] = max(highs) > 0
        active[axis+'_negative'] = min(lows) < 0
    missing = [k for k in NAMES if active[k] and caps[k] is None]
    base = dict(schema=SCHEMA, scope=SCOPE, physical_span_mm=span_mm,
        capacities_Nmm=dict(capacities), active_signed_branches=active, missing=missing,
        sign_certificate=sign_proof, resistance_qualified=False,
        primary_torsion_assessed=False, whole_member_approved=False)
    if missing:
        return dict(base, status='pending_signed_resistance', envelope_certificate=[],
                    governing=None, criterion_status=None)
    # Filler 1 is used ONLY on an identically inactive signed branch. Its
    # quadratic is nonpositive everywhere and cannot exceed the active branch.
    # It is not a substituted resistance and is identified in each proof row.
    forms = []
    candidates = set()
    for lo, hi, after, mx, my in fields:
        for sx in (-1, 1):
            for sy in (-1, 1):
                nx = 'Mx_'+('positive' if sx > 0 else 'negative')
                ny = 'My_'+('positive' if sy > 0 else 'negative')
                rx, ry = caps[nx] or F(1), caps[ny] or F(1)
                co = tuple(sx*x/rx+sy*y/ry for x, y in zip(mx, my))
                xs = _stations(co, lo, hi); candidates.update(xs)
                forms.append(dict(start_exact=str(lo), end_exact=str(hi), after_P=after,
                    signs=[sx, sy], inactive_denominator_fillers=[k for k in (nx,ny) if caps[k] is None],
                    coefficients_exact=[str(c) for c in co], candidate_positions_exact=[str(x) for x in xs]))
    def state(x):
        after = x > a
        mx = _value(_coefficients(combo, L, a, after, 'normal'), x)
        my = _value(_coefficients(combo, L, a, after, 'parallel'), x)
        nx='Mx_'+('positive' if mx>=0 else 'negative'); ny='My_'+('positive' if my>=0 else 'negative')
        ix = abs(mx)/caps[nx] if mx else F(0)
        iy = abs(my)/caps[ny] if my else F(0)
        return mx,my,ix+iy
    x = max(sorted(candidates), key=lambda x:state(x)[2])
    mx,my,index=state(x); lower,upper=_bound(index,False),_bound(index,True)
    return dict(base, status='computed_arithmetic', envelope_certificate=forms,
        governing=dict(x_mm=float(x), x_exact=str(x), Mx_Nmm=float(mx), My_Nmm=float(my),
            Mx_exact=str(mx), My_exact=str(my), index_exact=str(index),
            index_lower=lower, index_upper=upper),
        criterion_status='meets' if upper<=1 else 'fails' if lower>1 else 'boundary_inconclusive')


def validate_saved(record, combo, span_mm, capacities):
    # Reconstruct only exact arithmetic identities, never a section, eigenvalue,
    # resistance or solver. Every candidate/branch and the maximum are checked.
    expected = interaction(combo, span_mm, capacities)
    if record != expected:
        raise ValueError('Interação salva difere dos esforços, resistências ou máximo contínuo.')
    return record


def demand(combo, span_mm, axis, sign=None):
    """Directed exact pure-axis maximum for component indices and witnesses."""
    L=_real(span_mm,'vão físico',True);a=_real(combo['x_mm'],'posição P')
    if axis not in ('normal','parallel') or sign not in (None,'positive','negative') or not 0<=a<=L:
        raise ValueError('Eixo, sinal ou posição inválidos.')
    xs=set()
    for lo,hi,after in ((F(0),a,False),(a,L,True)):
        if lo<hi:xs.update(_stations(_coefficients(combo,L,a,after,axis),lo,hi))
    def value(x):
        m=_value(_coefficients(combo,L,a,x>a,axis),x)
        return abs(m) if sign is None else max(F(0),m*(1 if sign=='positive' else -1))
    x=max(sorted(xs),key=value);maximum=value(x)
    mx=_value(_coefficients(combo,L,a,x>a,'normal'),x)
    my=_value(_coefficients(combo,L,a,x>a,'parallel'),x)
    return dict(Msd_Nmm=_bound(maximum,True),Msd_exact=str(maximum),
        witness=dict(x_mm=float(x),x_exact=str(x),Mx_Nmm=float(mx),My_Nmm=float(my),Mx_exact=str(mx),My_exact=str(my)),
        candidate_x_mm=[float(x) for x in sorted(xs)],candidate_x_exact=[str(x) for x in sorted(xs)],
        axis=axis,sign=sign,physical_span_mm=span_mm,exact_piecewise_extremum=True)
