"""Scalar number model.

Design (see docs/NUMERICS.md):
* Exact rationals (fractions.Fraction) whenever the math allows it, so
  0.1 + 0.2 - 0.3 == 0 exactly and 4/5 + 2/3 == 22/15 exactly.
* Otherwise mpmath binary floats at 34 significant digits (display shows 10).
* Complex values are mpmath mpc.
* Cancellation snap: an add/subtract result smaller than 1e-25 x the operands
  is set to 0 (34-digit arithmetic noise, not a real value).
* Range: |x| >= 1e100 -> Math ERROR; 0 < |x| < 1e-99 -> 0 (manual p.40).
"""
from fractions import Fraction
import math

import mpmath as mp

from .errors import MathError

mp.mp.dps = 34

MAX_ABS = mp.mpf("1e100")
MIN_ABS = mp.mpf("1e-99")
SNAP = mp.mpf("1e-25")
MAX_FRACTION_DIGITS = 80

Real = (Fraction, mp.mpf)


def is_real(v) -> bool:
    return isinstance(v, Real)


def is_complex(v) -> bool:
    return isinstance(v, mp.mpc)


def is_scalar(v) -> bool:
    return isinstance(v, (Fraction, mp.mpf, mp.mpc))


def to_mpf(v) -> mp.mpf:
    if isinstance(v, Fraction):
        return mp.mpf(v.numerator) / v.denominator
    if isinstance(v, mp.mpf):
        return v
    if isinstance(v, int):
        return mp.mpf(v)
    raise MathError("real number expected")


def to_mpc(v) -> mp.mpc:
    return v if isinstance(v, mp.mpc) else mp.mpc(to_mpf(v), 0)


def is_integer(v) -> bool:
    if isinstance(v, Fraction):
        return v.denominator == 1
    if isinstance(v, mp.mpf):
        return mp.isint(v)
    return False


def as_int(v, what="integer") -> int:
    if not is_integer(v):
        raise MathError(f"{what} required")
    return int(v) if isinstance(v, Fraction) else int(mp.nint(v))


def mpf_to_fraction(x: mp.mpf) -> Fraction:
    """Exact rational value of a binary float."""
    man, exp = mp.mpf(x).man_exp
    return Fraction(man) * (Fraction(2) ** exp)


def snap_rational(x, max_den=1000):
    """Return a Fraction if mpf x equals a simple rational to 1e-25, else x."""
    if not isinstance(x, mp.mpf):
        return x
    if x == 0:
        return Fraction(0)
    f = Fraction(mp.nstr(x, 32, min_fixed=-mp.inf, max_fixed=mp.inf)).limit_denominator(max_den)
    if abs(to_mpf(f) - x) <= SNAP * abs(x):
        return f
    return x


def _digits(n: int) -> int:
    return len(str(abs(n)))


def check(v):
    """Normalise a scalar and enforce the calculation range."""
    if isinstance(v, int):
        v = Fraction(v)
    if isinstance(v, Fraction):
        if v == 0:
            return v
        a = abs(v)
        if a >= 10 ** 100:
            raise MathError("result out of range (|x| >= 1e100)")
        if a < Fraction(1, 10 ** 99):
            return Fraction(0)
        if _digits(v.numerator) > MAX_FRACTION_DIGITS or _digits(v.denominator) > MAX_FRACTION_DIGITS:
            return check(to_mpf(v))
        return v
    if isinstance(v, mp.mpf):
        if not mp.isfinite(v):
            raise MathError("result out of range")
        a = abs(v)
        if a >= MAX_ABS:
            raise MathError("result out of range (|x| >= 1e100)")
        if a < MIN_ABS:
            return mp.mpf(0)
        return v
    if isinstance(v, mp.mpc):
        re, im = check(v.real), check(v.imag)
        if im == 0 or abs(im) < SNAP * abs(re):
            return re
        if abs(re) < SNAP * abs(im):
            re = mp.mpf(0)
        return mp.mpc(re, im)
    raise MathError("not a number")


def _snap_sum(r, a, b):
    if r != 0 and abs(r) < SNAP * max(abs(a), abs(b)):
        return mp.mpf(0)
    return r


def add(a, b):
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return check(a + b)
    if is_complex(a) or is_complex(b):
        a, b = to_mpc(a), to_mpc(b)
        return check(mp.mpc(_snap_sum(a.real + b.real, a.real, b.real),
                            _snap_sum(a.imag + b.imag, a.imag, b.imag)))
    a, b = to_mpf(a), to_mpf(b)
    return check(_snap_sum(a + b, a, b))


def neg(a):
    return -a


def sub(a, b):
    return add(a, neg(b))


def mul(a, b):
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return check(a * b)
    if is_complex(a) or is_complex(b):
        return check(to_mpc(a) * to_mpc(b))
    return check(to_mpf(a) * to_mpf(b))


def div(a, b):
    if b == 0:
        raise MathError("division by zero")
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return check(a / b)
    if is_complex(a) or is_complex(b):
        return check(to_mpc(a) / to_mpc(b))
    return check(to_mpf(a) / to_mpf(b))


def exact_root(f: Fraction, n: int):
    """n-th root of a non-negative Fraction if it is rational, else None."""
    def iroot(k):
        if k < 0:
            return None
        r = round(k ** (1.0 / n)) if k < 2 ** 1000 else int(mp.nint(mp.root(k, n)))
        for c in (r - 1, r, r + 1):
            if c >= 0 and c ** n == k:
                return c
        return None
    p, q = iroot(f.numerator), iroot(f.denominator)
    return Fraction(p, q) if p is not None and q is not None else None


def power(a, b, complex_mode=False):
    """a ** b with the manual's domain rules (p.41)."""
    if is_complex(a) or is_complex(b):
        if a == 0:
            if is_real(b) and b > 0:
                return Fraction(0)
            raise MathError("0 to a non-positive power")
        if is_integer(b) and is_real(b):
            n = as_int(b)
            if abs(n) >= 10 ** 10:
                raise MathError("exponent out of range")
            return check(mp.power(to_mpc(a), n))
        return check(mp.power(to_mpc(a), to_mpc(b)))

    if a == 0:
        if b > 0:
            return Fraction(0)
        raise MathError("0 to a non-positive power")

    if isinstance(b, Fraction) and b.denominator == 1:
        n = b.numerator
        if isinstance(a, Fraction):
            mag = max(math.log10(abs(a.numerator)) if a.numerator else 0,
                      math.log10(a.denominator))
            if abs(n) * mag > 200:  # result would be huge -> use floats/range check
                return check(mp.power(to_mpf(a), n))
            return check(a ** n)
        return check(mp.power(a, n))

    if isinstance(b, Fraction):   # rational, non-integer exponent p/q
        p, q = b.numerator, b.denominator
        if a < 0:
            if q % 2 == 1:        # odd root of a negative number is real
                mag = power(-a, b)
                return neg(mag) if p % 2 else mag
            if complex_mode:
                return check(mp.power(to_mpc(a), to_mpf(b)))
            raise MathError("even root of a negative number")
        if isinstance(a, Fraction) and q <= 64:
            r = exact_root(a, q)
            if r is not None:
                return power(r, Fraction(p))
        return check(mp.power(to_mpf(a), to_mpf(b)))

    # b is an mpf
    if a < 0:
        if mp.isint(b):
            return check(mp.power(to_mpf(a), b))
        if complex_mode:
            return check(mp.power(to_mpc(a), b))
        raise MathError("negative base with non-integer exponent")
    return check(mp.power(to_mpf(a), b))
