"""Regression controls for exact rational isolation, not structural checks."""
import math
from fractions import Fraction

import pytest

from tercas.bounded_polynomial import real_roots_open_unit_interval as roots
from tercas.three_girt_frame import _roots_inside


@pytest.mark.parametrize('coeff, expected', [
    ([], []), ([0.], []), ([0., 0., 0.], []), ([3.], []),
    ([-.5, 1.], [.5]), ([.5, 1.], []), ([-2., 1.], []),
    ([0., 1.], []), ([-1., 1.], []), ([0., -1., 1.], []),
    ([0., 0., 1.], []), ([1., -2., 1.], []),
    ([.25, -1., 1.], [.5]), ([-.125, .75, -1.5, 1.], [.5]),
    ([0., .25, -1., 1.], [.5]),
    ([-.09375, .6875, -1.5, 1.], [.25, .5, .75]),
    ([1., 0., 1.], []), ([1., 0., 0., 1.], []),
])
def test_closed_form_exact_dyadic_controls(coeff, expected):
    assert roots(coeff) == expected
    assert _roots_inside(coeff) == expected


@pytest.mark.parametrize('scale', [-1000, -500, -20, 0, 20, 500, 1000])
def test_scaling_does_not_change_distinct_roots(scale):
    coefficients = [math.ldexp(c, scale) for c in [-.09375, .6875, -1.5, 1.]]
    assert roots(coefficients) == [.25, .5, .75]


@pytest.mark.parametrize('coeff, expected', [
    ([-.0874369143356648, .17487382867132908, 1.6650666479014247e-16, 0.], .5000000000000012),
    ([-.12490987762237733, .2498197552447551, 3.466798941046163e-16, 0.], .4999999999999988),
    ([-.5, 1., 1e-300], .5),
    ([-.5, 1., 0., 1e-300], .5),
    ([-.5, 1., -1e-300], .5),
])
def test_small_leading_coefficient_is_retained_without_spurious_root(coeff, expected):
    actual = roots(coeff)
    assert len(actual) == 1
    assert abs(actual[0]-expected) <= 2*math.ulp(expected)
    # Test the represented polynomial, not an approximate degree reduction.
    t = Fraction(actual[0])
    value = sum(Fraction(c)*t**i for i, c in enumerate(coeff))
    assert abs(float(value)) < 1e-14


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_coefficients_fail_closed(bad):
    with pytest.raises(ValueError, match='finite'):
        roots([-.5, 1., bad])


def test_exactly_repeated_is_distinct_from_close_separated_roots():
    a, b = Fraction(1, 2), Fraction(1, 2)+Fraction(1, 2**20)
    coeff = [float(a*b), -float(a+b), 1.]
    assert roots(coeff) == [float(a), float(b)]
    assert roots([.25, -1., 1.]) == [.5]


def test_interior_roots_near_endpoints_are_not_discarded():
    x = math.ldexp(1., -1000)
    assert roots([-x, 1.]) == [x]
    x = math.nextafter(1., 0.)
    assert roots([-x, 1.]) == [x]


def test_zero_roots_are_removed_without_discarding_small_real_root():
    tiny = math.ldexp(1., -1000)
    assert roots([0., -tiny, 1.]) == [tiny]


def test_boundary_rounding_returns_interior_representative():
    tiny = math.nextafter(0., 1.)
    assert roots([-tiny, 2.]) == [tiny]
