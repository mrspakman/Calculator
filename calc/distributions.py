"""Probability distributions (manual p.31).  Exact rational arithmetic is used
for binomial probabilities when the inputs are rational."""
from fractions import Fraction
import math

import mpmath as mp

from .errors import MathError
from .scalars import as_int, check, is_integer, to_mpf


def _sigma(s):
    if s <= 0:
        raise MathError("σ must be > 0")
    return to_mpf(s)


def normal_pd(x, sigma=Fraction(1), mu=Fraction(0)):
    s = _sigma(sigma)
    z = (to_mpf(x) - to_mpf(mu)) / s
    return check(mp.npdf(z) / s)


def normal_cd(lower, upper, sigma=Fraction(1), mu=Fraction(0)):
    s = _sigma(sigma)
    lo, hi = to_mpf(lower), to_mpf(upper)
    if lo > hi:
        lo, hi = hi, lo
    m = to_mpf(mu)
    return check(mp.ncdf((hi - m) / s) - mp.ncdf((lo - m) / s))


def inverse_normal(area, sigma=Fraction(1), mu=Fraction(0)):
    s = _sigma(sigma)
    a = to_mpf(area)
    if not 0 < a < 1:
        raise MathError("area must be between 0 and 1")
    z = mp.sqrt(2) * mp.erfinv(2 * a - 1)
    return check(to_mpf(mu) + s * z)


def _binom_args(x, n, p):
    if not is_integer(n) or n < 0:
        raise MathError("N must be a non-negative integer")
    if not 0 <= p <= 1:
        raise MathError("p must be between 0 and 1")
    if not is_integer(x) or not 0 <= x <= n:
        raise MathError("x must be an integer 0 ≤ x ≤ N")
    return as_int(x), as_int(n)


def _binom_term(k, n, p):
    if isinstance(p, Fraction) and n <= 1000:
        return Fraction(math.comb(n, k)) * p ** k * (1 - p) ** (n - k)
    pm = to_mpf(p)
    return mp.binomial(n, k) * pm ** k * (1 - pm) ** (n - k)


def binomial_pd(x, n, p):
    x, n = _binom_args(x, n, p)
    return check(_binom_term(x, n, p))


def binomial_cd(x, n, p):
    x, n = _binom_args(x, n, p)
    s = Fraction(0) if isinstance(p, Fraction) and n <= 1000 else mp.mpf(0)
    for k in range(x + 1):
        s += _binom_term(k, n, p)
    return check(min(s, 1) if isinstance(s, Fraction) else min(s, mp.mpf(1)))


def _poisson_args(x, lam):
    if lam <= 0:
        raise MathError("λ must be > 0")
    if not is_integer(x) or x < 0:
        raise MathError("x must be a non-negative integer")
    return as_int(x), to_mpf(lam)


def poisson_pd(x, lam):
    x, l = _poisson_args(x, lam)
    return check(mp.exp(-l) * l ** x / mp.factorial(x))


def poisson_cd(x, lam):
    x, l = _poisson_args(x, lam)
    s = mp.mpf(0)
    term = mp.exp(-l)
    for k in range(x + 1):
        if k:
            term *= l / k
        s += term
    return check(min(s, mp.mpf(1)))
