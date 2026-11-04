"""Real roots inside (0, 1) for low-degree response polynomials.

Input floats are treated as their exact binary rational values. An exact Sturm
sequence isolates the distinct roots, so a very small nonzero leading term is
neither discarded nor sent to a badly conditioned companion eigensystem.
Isolation ends only when the interval has no intermediate representable float.
Roots that round to a boundary are represented by the nearest interior float;
the response solver separately evaluates both physical element boundaries.

This is numerical root extraction, not a structural tolerance or a new theory.
The frame uses degrees at most three. Repeated roots are removed algebraically,
not merged using an arbitrary distance. Distinct roots can share one returned
float when the coordinate precision cannot distinguish them.
"""
from fractions import Fraction
import math


def _trim(coeff):
    out = list(coeff)
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return out or [Fraction(0)]


def _value(coeff, x):
    value = Fraction(0)
    for c in reversed(coeff):
        value = value*x+c
    return value


def _divide(dividend, divisor):
    rest = _trim(dividend)
    divisor = _trim(divisor)
    if divisor == [0]:
        raise ZeroDivisionError('Zero polynomial divisor')
    quotient = [Fraction(0)]*max(1, len(rest)-len(divisor)+1)
    while rest != [0] and len(rest) >= len(divisor):
        shift = len(rest)-len(divisor)
        factor = rest[-1]/divisor[-1]
        quotient[shift] = factor
        for i, c in enumerate(divisor):
            rest[i+shift] -= factor*c
        rest = _trim(rest)
    return _trim(quotient), rest


def _sturm(coeff):
    # Positive normalization preserves every sign variation and limits growth.
    normalize = lambda p: [c/abs(p[-1]) for c in p]
    first = normalize(coeff)
    second = normalize([i*first[i] for i in range(1, len(first))])
    sequence = [first, second]
    while len(sequence[-1]) > 1:
        _, remainder = _divide(sequence[-2], sequence[-1])
        if remainder == [0]:
            break
        sequence.append(normalize([-c for c in remainder]))
    return sequence


def _variations(sequence, x):
    signs = []
    for coeff in sequence:
        value = _value(coeff, x)
        if value:
            signs.append(value > 0)
    return sum(a != b for a, b in zip(signs, signs[1:]))


def _interior_float(x):
    value = float(x)
    if value <= 0:
        return math.nextafter(0., 1.)
    if value >= 1:
        return math.nextafter(1., 0.)
    return value


def real_roots_open_unit_interval(coeff):
    """Return sorted finite float representatives of all distinct roots.

    Finite real coefficients only. The zero/constant polynomial contributes no
    isolated root. Endpoint roots are removed exactly before the open-interval
    count. No coefficient threshold, imaginary-part threshold or root grid is
    used. All arithmetic in the root-counting proof is exact rational arithmetic.
    """
    raw = [float(c) for c in coeff]
    if not all(math.isfinite(c) for c in raw):
        raise ValueError('Polynomial coefficients must be finite')
    p = _trim([Fraction(c) for c in raw])
    if len(p) < 2:
        return []
    while len(p) > 1 and p[0] == 0:
        p = p[1:]
    while len(p) > 1 and sum(p) == 0:
        p, remainder = _divide(p, [Fraction(-1), Fraction(1)])
        if remainder != [0]:
            raise ArithmeticError('Exact endpoint factor division failed')
    if len(p) < 2:
        return []
    if len(p) == 2:
        root = -p[0]/p[1]
        return [_interior_float(root)] if 0 < root < 1 else []
    sequence = _sturm(p)
    # The last nonzero remainder is gcd(p,p'). Divide it out to avoid a common
    # zero of the entire sequence at a repeated root used as an interval bound.
    if len(sequence[-1]) > 1:
        p, remainder = _divide(p, sequence[-1])
        if remainder != [0]:
            raise ArithmeticError('Exact square-free factor division failed')
        if len(p) == 2:
            root = -p[0]/p[1]
            return [_interior_float(root)] if 0 < root < 1 else []
        sequence = _sturm(p)
    zero, one = Fraction(0), Fraction(1)
    v0, v1 = _variations(sequence, zero), _variations(sequence, one)
    pending = [(zero, one, v0, v1)]
    roots = []
    while pending:
        left, right, vl, vr = pending.pop()
        count = vl-vr
        if count < 0:
            raise ArithmeticError('Inconsistent exact Sturm root count')
        if count == 0:
            continue
        if count == 1 and _value(p, right) == 0:
            roots.append(_interior_float(right))
            continue
        if math.nextafter(float(left), math.inf) >= float(right):
            # If multiple roots share this final floating-point interval, one
            # representable coordinate suffices; both boundaries are already
            # evaluated by the frame and no physical separation is imposed.
            roots.append(_interior_float((left+right)/2))
            continue
        middle = (left+right)/2
        vm = _variations(sequence, middle)
        pending.append((middle, right, vm, vr))
        pending.append((left, middle, vl, vm))
    return sorted(set(roots))
