"""Portable bitwise regression for EN's pure scalar memoization.

The independent scalar/extrema oracle below is copied from the pre-cache
field_envelope.py at ae0d90a5660eb1cabe5fb5c02e8a4b1722bffd70. It deliberately
does not call the production scalar, sigma, roots, or extrema implementation.
This is a numerical-equivalence test, not independent structural qualification.

Copy this file into the repository's tests/ and run pytest on it. It needs only
the repository's ordinary numpy/scipy/pytest dependencies, no external checkout,
source snapshot, UI, network solver, or application data file.
"""

import itertools
import math
import random
import struct

import numpy as np
import pytest
from scipy.optimize import brentq

from tercas.three_girt_en_normal import field_envelope as actual


def oracle_bimoment(field, t, derivative=0):
    h, B0, U, V = (field[k] for k in ('h', 'B0', 'U', 'V'))
    t = float(t)
    if h == 0:
        return (B0+V*t+U*t*t/2 if derivative == 0 else
                V+U*t if derivative == 1 else U if derivative == 2 else 0.)
    z = h*t
    sh = math.sinh(z)
    ch = math.cosh(z)
    if derivative == 0:
        return math.fsum((B0, U*2*(math.sinh(z/2)/h)**2, V*sh/h))
    if derivative == 1:
        return math.fsum((U*sh/h, V*ch))
    if derivative == 2:
        return math.fsum((U*ch, V*h*sh))
    if derivative == 3:
        return math.fsum((U*h*sh, V*h*h*ch))
    raise ValueError('Only derivatives 0 to 3 are needed')


def oracle_sigma(p, w, field, t, derivative=0):
    normal = (math.fsum((p[0], p[1]*t, p[2]*t*t)) if derivative == 0 else
              p[1]+2*p[2]*t if derivative == 1 else 2*p[2] if derivative == 2 else 0.)
    return math.fsum((normal, w*oracle_bimoment(field, t, derivative)))


def oracle_finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name+' must be a finite real number')
    return float(value)


def oracle_distinct(values):
    return sorted(set(float(v) for v in values))


def oracle_monotone_roots(fn, knots):
    roots = []
    for a, b in zip(knots[:-1], knots[1:]):
        fa, fb = fn(a), fn(b)
        if not math.isfinite(fa) or not math.isfinite(fb):
            raise ArithmeticError('Nonfinite analytical derivative')
        if fa == 0:
            roots.append(a)
        if fb == 0:
            roots.append(b)
        if (fa < 0 < fb) or (fb < 0 < fa):
            roots.append(brentq(fn, a, b, xtol=5e-15, rtol=1e-14, maxiter=100))
    return oracle_distinct(roots)


def oracle_extrema(polynomial, omega_over_Cw, field, left=0., right=1.):
    p = [oracle_finite(v, 'normal coefficient') for v in polynomial]
    if len(p) != 3:
        raise ValueError('Three ascending quadratic coefficients required')
    w = oracle_finite(omega_over_Cw, 'omega/Cw')
    left, right = oracle_finite(left, 'left'), oracle_finite(right, 'right')
    if not 0 <= left < right <= 1:
        raise ValueError('Nonempty normalized interval required')
    for key in ('h', 'B0', 'U', 'V'):
        oracle_finite(field[key], key)
    if field['h'] < 0 or field['h'] > 10:
        raise ValueError('Hyperbolic domain outside [0,10]')
    if w == 0 or field['h'] == 0:
        c = p[2]+(w*field['U']/2 if field['h'] == 0 else 0.)
        b = p[1]+(w*field['V'] if field['h'] == 0 else 0.)
        root = -b/(2*c) if c else None
        knots = oracle_distinct([left, right]+([root] if root is not None and left < root < right else []))
    else:
        third = lambda t: oracle_sigma(p, w, field, t, 3)
        second = lambda t: oracle_sigma(p, w, field, t, 2)
        first = lambda t: oracle_sigma(p, w, field, t, 1)
        k3 = oracle_distinct([left, right]+oracle_monotone_roots(third, [left, right]))
        k2 = oracle_distinct([left, right]+oracle_monotone_roots(second, k3))
        knots = oracle_distinct([left, right]+oracle_monotone_roots(first, k2))
    points = [dict(t=t, sigma_MPa=oracle_sigma(p, w, field, t)) for t in knots]
    if any(not math.isfinite(v['sigma_MPa']) for v in points):
        raise ArithmeticError('Nonfinite analytical stress')
    return dict(minimum=min(points, key=lambda v: v['sigma_MPa']),
                maximum=max(points, key=lambda v: v['sigma_MPa']),
                maximum_absolute=max(points, key=lambda v: abs(v['sigma_MPa'])),
                candidate_count=len(points))


def encoded(value):
    """Retain types, dict order, signed zero, and binary64 payloads."""
    if type(value) is float or isinstance(value, np.floating):
        return type(value).__name__, struct.pack('!d', value).hex()
    if isinstance(value, dict):
        return 'dict', tuple((k, encoded(v)) for k, v in value.items())
    if isinstance(value, (tuple, list)):
        return type(value).__name__, tuple(encoded(v) for v in value)
    return type(value).__name__, repr(value)


def outcome(fn, *args):
    try:
        return 'ok', encoded(fn(*args))
    except Exception as exc:
        return 'error', type(exc).__name__, str(exc)


def test_6085_deterministic_bitwise_and_exception_comparisons():
    actual._cached_bimoment.cache_clear()
    rng = random.Random(20261105)
    counts = dict(bimoment=0, stress_extrema=0)
    successes = dict(bimoment=0, stress_extrema=0)

    def compare(name, *args):
        reference = oracle_bimoment if name == 'bimoment' else oracle_extrema
        expected = outcome(reference, *args)
        observed = outcome(getattr(actual, name), *args)
        assert observed == expected, (name, args, expected, observed)
        counts[name] += 1
        successes[name] += expected[0] == 'ok'

    for signs in itertools.product((0., -0.), repeat=5):
        field = dict(zip(('h', 'B0', 'U', 'V'), signs[:4]))
        for derivative in (-1, 0, 1, 2, 3, 4, False, True, 1.0, np.int64(1)):
            compare('bimoment', field, signs[4], derivative)
    for _ in range(1000):
        h = rng.choice((0., -0., 1e-150, 1e-10, .01, .7, 3., 10.))
        field = dict(h=h, B0=rng.uniform(-1e12, 1e12), U=rng.uniform(-1e12, 1e12), V=rng.uniform(-1e12, 1e12))
        for derivative in (0, 1, 2, 3):
            compare('bimoment', field, rng.choice((0., -0., .37, 1., rng.random())), derivative)
    for field in (dict(h=0, B0=2, U=3, V=4), dict(h=2, B0=2, U=3, V=4),
                  dict(h=np.float64(2), B0=2., U=3., V=4.), dict(h=2., B0=2., U=3., V=4.)):
        for derivative in (0, 1, 2, 3, 4):
            for t in ('0.37', 0, np.float64(.37), 'bad'):
                compare('bimoment', field, t, derivative)
    for h in (0., 1., math.nan, math.inf, -math.inf):
        for key in ('B0', 'U', 'V'):
            for value in (math.nan, math.inf, -math.inf):
                field = dict(h=h, B0=2., U=3., V=4.)
                field[key] = value
                for derivative in (0, 1, 2, 3):
                    compare('bimoment', field, .37, derivative)
    for _ in range(750):
        h = rng.choice((0., -0., 1e-10, .001, .7, 3., 10.))
        field = dict(h=h, B0=rng.uniform(-1e6, 1e6), U=rng.uniform(-1e6, 1e6), V=rng.uniform(-1e6, 1e6))
        p = [rng.uniform(-1e5, 1e5) for _ in range(3)]
        w = rng.choice((0., -0., 1e-8, .1, -.1, rng.uniform(-1, 1)))
        left, right = rng.choice(((0., 1.), (0., math.nextafter(0., 1.)),
                                 (.37, math.nextafter(.37, 1.)), (.001, .999)))
        compare('stress_extrema', p, w, field, left, right)
        p[0] = -p[0]
        field['B0'] = -field['B0']
        compare('stress_extrema', p, w, field, left, right)
    for args in [([1., 2., 3.], 1., dict(h=1., B0=math.nan, U=1., V=1.), 0., 1.),
                 ([1., 2.], 1., dict(h=1., B0=1., U=1., V=1.), 0., 1.),
                 ([1., 2., 3.], 1., dict(h=11., B0=1., U=1., V=1.), 0., 1.),
                 ([1., 2., 3.], 1., dict(h=1., B0=1., U=1., V=1.), 1., 0.),
                 ([1., 2., 3.], 1., dict(h=1, B0=1, U=1, V=1), 0., 1.)]:
        compare('stress_extrema', *args)
    assert counts == dict(bimoment=4580, stress_extrema=1505)
    assert successes['bimoment'] >= 4300
    assert successes['stress_extrema'] == 1501


def test_mutation_cannot_contaminate_cached_values():
    field = dict(h=0., B0=1., U=2., V=3.)
    p = [1., 2., -3.]
    expected = encoded(oracle_extrema(p, 1., field))
    result = actual.stress_extrema(p, 1., field)
    result['minimum']['sigma_MPa'] = 999.
    assert encoded(actual.stress_extrema(p, 1., field)) == expected
    for key in ('h', 'B0', 'U', 'V'):
        field[key] += 1.
        for derivative in range(4):
            assert outcome(actual.bimoment, field, .37, derivative) == outcome(oracle_bimoment, field, .37, derivative)


def test_lru_is_bounded_and_eviction_preserves_values():
    actual._cached_bimoment.cache_clear()
    field = dict(h=0., B0=1., U=2., V=3.)
    expected = encoded(actual.bimoment(field, .5))
    capacity = actual._cached_bimoment.cache_info().maxsize
    assert isinstance(capacity, int) and 0 < capacity <= 65536
    for i in range(capacity+16):
        actual.bimoment(dict(h=0., B0=float(i), U=1., V=2.), .5)
    assert actual._cached_bimoment.cache_info().currsize == capacity
    assert encoded(actual.bimoment(field, .5)) == expected


def test_overflow_and_failure_are_not_cached_as_success():
    field = dict(h=1000., B0=1., U=2., V=3.)
    for _ in range(2):
        assert outcome(actual.bimoment, field, 1.) == outcome(oracle_bimoment, field, 1.)
    field['h'] = 1.
    assert outcome(actual.bimoment, field, 1.) == outcome(oracle_bimoment, field, 1.)


@pytest.mark.parametrize('h', [0., 1e-8, .1, 1., 5., 10.])
def test_multiple_roots_and_changed_constant_terms(h):
    field = dict(h=h, B0=0., U=math.cosh(1)*2, V=-math.sinh(1))
    for p0 in (0., -0., 1e12, -1e12):
        for b0 in (0., -0., 1e12, -1e12):
            field['B0'] = b0
            args = ([p0, 1.1, -1.1], 1., field)
            assert outcome(actual.stress_extrema, *args) == outcome(oracle_extrema, *args)
