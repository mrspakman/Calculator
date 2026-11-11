"""Scalar math functions with the input ranges from manual pp. 40-41."""
from fractions import Fraction
import math
import random

import mpmath as mp

from .errors import ArgumentError, MathError
from .scalars import (SNAP, add, as_int, check, div, is_complex, is_integer, is_real,
                      mul, power, snap_rational, to_mpc, to_mpf)

DEG, RAD, GRA = "Deg", "Rad", "Gra"

# Exact sin values at multiples of 30 degrees (others computed numerically).
_EXACT_SIN = {0: Fraction(0), 30: Fraction(1, 2), 90: Fraction(1), 150: Fraction(1, 2),
              180: Fraction(0), 210: Fraction(-1, 2), 270: Fraction(-1), 330: Fraction(-1, 2)}


def _real(x, fname):
    if not is_real(x):
        raise MathError(f"{fname}: real argument required")
    return x


# ---------- angle helpers ----------

def to_degrees_exact(x, unit):
    """Angle as exact Fraction degrees when that is exactly known, else None."""
    if isinstance(x, Fraction):
        if unit == DEG:
            return x
        if unit == GRA:
            return x * Fraction(9, 10)
    xd = to_mpf(x)
    if unit == RAD:
        d = xd * 180 / mp.pi
    elif unit == GRA:
        d = xd * mp.mpf(9) / 10
    else:
        d = xd
    n = mp.nint(d)
    if abs(d - n) <= SNAP * max(1, abs(d)):
        return Fraction(int(n))
    return None


def to_radians(x, unit):
    x = to_mpf(x)
    if unit == DEG:
        return x * mp.pi / 180
    if unit == GRA:
        return x * mp.pi / 200
    return x


def from_radians(r, unit):
    """Convert radians to the current unit; snap to an exact integer degree/grad."""
    r = to_mpf(r)
    if unit == DEG:
        return snap_rational(r * 180 / mp.pi, 60)
    if unit == GRA:
        return snap_rational(r * 200 / mp.pi, 60)
    return r


def convert_angle(x, from_unit, to_unit):
    """Angle-unit marker (°, r, g): value in from_unit, expressed in to_unit."""
    if from_unit == to_unit:
        return x
    if isinstance(x, Fraction) and {from_unit, to_unit} == {DEG, GRA}:
        return x * (Fraction(9, 10) if from_unit == GRA else Fraction(10, 9))
    return check(from_radians(to_radians(x, from_unit), to_unit))


_TRIG_LIMIT = {DEG: mp.mpf("9e9"), RAD: mp.mpf("157079632.7"), GRA: mp.mpf("1e10")}


def _trig_check(x, unit):
    x = _real(x, "trig")
    if abs(to_mpf(x)) >= _TRIG_LIMIT[unit]:
        raise MathError("angle out of input range")
    return x


def _sin_exact_deg(d: Fraction):
    r = d % 360
    if r in _EXACT_SIN:
        return _EXACT_SIN[r]
    return None


def sin(x, unit):
    x = _trig_check(x, unit)
    d = to_degrees_exact(x, unit)
    if d is not None and (e := _sin_exact_deg(d)) is not None:
        return e
    return check(_snap_small(mp.sin(to_radians(x, unit))))


def cos(x, unit):
    x = _trig_check(x, unit)
    d = to_degrees_exact(x, unit)
    if d is not None and (e := _sin_exact_deg(90 - d)) is not None:
        return e
    return check(_snap_small(mp.cos(to_radians(x, unit))))


def tan(x, unit):
    x = _trig_check(x, unit)
    d = to_degrees_exact(x, unit)
    if d is not None:
        if d % 180 == 90:
            raise MathError("tan undefined at odd multiples of 90°")
        s, c = _sin_exact_deg(d), _sin_exact_deg(90 - d)
        if s is not None and c is not None:
            return s / c
        if d % 180 in (45, 135):
            return Fraction(1) if d % 180 == 45 else Fraction(-1)
    return check(_snap_small(mp.tan(to_radians(x, unit))))


def _snap_small(v):
    return mp.mpf(0) if abs(v) < SNAP else v


def asin(x, unit):
    x = _real(x, "sin⁻¹")
    if abs(to_mpf(x)) > 1:
        raise MathError("sin⁻¹ needs |x| ≤ 1")
    return check(from_radians(mp.asin(to_mpf(x)), unit))


def acos(x, unit):
    x = _real(x, "cos⁻¹")
    if abs(to_mpf(x)) > 1:
        raise MathError("cos⁻¹ needs |x| ≤ 1")
    return check(from_radians(mp.acos(to_mpf(x)), unit))


def atan(x, unit):
    x = _real(x, "tan⁻¹")
    return check(from_radians(mp.atan(to_mpf(x)), unit))


HYP_LIMIT = mp.mpf("230.2585092")


def sinh(x):
    x = to_mpf(_real(x, "sinh"))
    if abs(x) > HYP_LIMIT:
        raise MathError("sinh input out of range")
    return check(mp.sinh(x))


def cosh(x):
    x = to_mpf(_real(x, "cosh"))
    if abs(x) > HYP_LIMIT:
        raise MathError("cosh input out of range")
    return check(mp.cosh(x))


def tanh(x):
    return check(mp.tanh(to_mpf(_real(x, "tanh"))))


def asinh(x):
    return check(mp.asinh(to_mpf(_real(x, "sinh⁻¹"))))


def acosh(x):
    x = to_mpf(_real(x, "cosh⁻¹"))
    if x < 1:
        raise MathError("cosh⁻¹ needs x ≥ 1")
    return check(mp.acosh(x))


def atanh(x):
    x = to_mpf(_real(x, "tanh⁻¹"))
    if abs(x) >= 1:
        raise MathError("tanh⁻¹ needs |x| < 1")
    return check(mp.atanh(x))


# ---------- logs / exponentials ----------

def log(x, base=None):
    """log10(x) or log_base(x)."""
    x = _real(x, "log")
    if x <= 0:
        raise MathError("log needs x > 0")
    if base is None:
        if isinstance(x, Fraction):
            # exact for powers of ten
            for v, sign in ((x, 1), (1 / x, -1)):
                if v.denominator == 1 and v.numerator > 0:
                    s = str(v.numerator)
                    if s[0] == "1" and set(s[1:]) <= {"0"}:
                        return Fraction(sign * (len(s) - 1))
        return check(snap_rational(mp.log10(to_mpf(x)), 100))
    base = _real(base, "log")
    if base <= 0 or base == 1:
        raise MathError("log base must be > 0 and ≠ 1")
    return check(snap_rational(mp.log(to_mpf(x)) / mp.log(to_mpf(base)), 100))


def ln(x):
    x = _real(x, "ln")
    if x <= 0:
        raise MathError("ln needs x > 0")
    if x == 1:
        return Fraction(0)
    return check(mp.log(to_mpf(x)))


def exp(x):
    x = _real(x, "e^")
    if to_mpf(x) > mp.mpf("230.2585092"):
        raise MathError("e^x input out of range")
    if x == 0:
        return Fraction(1)
    return check(mp.exp(to_mpf(x)))


def ten_pow(x):
    x = _real(x, "10^")
    if to_mpf(x) >= 100:
        raise MathError("10^x input out of range")
    return power(Fraction(10), x)


# ---------- roots and powers ----------

def sqrt(x, complex_mode=False):
    if is_complex(x) or (complex_mode and is_real(x) and x < 0):
        return check(mp.sqrt(to_mpc(x)))
    if x < 0:
        raise MathError("√ needs x ≥ 0")
    return power(x, Fraction(1, 2))


def cbrt(x):
    return power(_real(x, "∛"), Fraction(1, 3))


def xroot(n, x):
    """n-th root of x  (ˣ√y).  Negative x allowed for odd integer n."""
    n, x = _real(n, "root"), _real(x, "root")
    if n == 0:
        raise MathError("0th root")
    if x < 0:
        if not (is_integer(n) and as_int(n) % 2):
            raise MathError("even root of a negative number")
        return check(-power(-x, div(Fraction(1), n)))
    return power(x, div(Fraction(1), n))


def reciprocal(x):
    return div(Fraction(1), x)


def factorial(x):
    x = _real(x, "x!")
    if not is_integer(x) or not 0 <= x <= 69:
        raise MathError("x! needs integer 0 ≤ x ≤ 69")
    return Fraction(math.factorial(as_int(x)))


def _nr_check(n, r, fname):
    n, r = _real(n, fname), _real(r, fname)
    if not (is_integer(n) and is_integer(r)):
        raise MathError(f"{fname} needs integers")
    n, r = as_int(n), as_int(r)
    if not (0 <= r <= n < 10 ** 10):
        raise MathError(f"{fname} needs 0 ≤ r ≤ n < 1e10")
    return n, r


def npr(n, r):
    n, r = _nr_check(n, r, "nPr")
    out = 1
    for k in range(n - r + 1, n + 1):
        out *= k
        if out >= 10 ** 100:
            raise MathError("nPr result out of range")
    return Fraction(out)


def ncr(n, r):
    n, r = _nr_check(n, r, "nCr")
    r = min(r, n - r)
    out = 1
    for k in range(1, r + 1):
        out = out * (n - r + k) // k
        if out >= 10 ** 100:
            raise MathError("nCr result out of range")
    return Fraction(out)


def absolute(x):
    if is_complex(x):
        return check(abs(x))
    return abs(x)


def pol(x, y, unit):
    """Rectangular -> polar.  θ in (-180°, 180°]."""
    x, y = _real(x, "Pol"), _real(y, "Pol")
    if x == 0 and y == 0:
        raise MathError("Pol(0,0) undefined angle")
    r = sqrt(add(mul(x, x), mul(y, y)))
    theta = check(from_radians(mp.atan2(to_mpf(y), to_mpf(x)), unit))
    return r, theta


def rec(r, theta, unit):
    r, theta = _real(r, "Rec"), _real(theta, "Rec")
    return mul(r, cos(theta, unit)), mul(r, sin(theta, unit))


def ran_hash(rng=random):
    return Fraction(rng.randint(0, 999), 1000)


def ranint(a, b, rng=random):
    a, b = _real(a, "RanInt#"), _real(b, "RanInt#")
    if not (is_integer(a) and is_integer(b)):
        raise MathError("RanInt# needs integers")
    a, b = as_int(a), as_int(b)
    if not (a < b and abs(a) < 10 ** 10 and abs(b) < 10 ** 10 and b - a < 10 ** 10):
        raise MathError("RanInt# needs a < b within range")
    return Fraction(rng.randint(a, b))


# ---------- complex helpers ----------

def conjg(z):
    return check(mp.conj(z)) if is_complex(z) else z


def arg(z, unit):
    z = to_mpc(z)
    if z == 0:
        raise MathError("arg(0) undefined")
    return check(from_radians(mp.arg(z), unit))


def re_part(z):
    return check(z.real) if is_complex(z) else z


def im_part(z):
    return check(z.imag) if is_complex(z) else Fraction(0)


def polar(r, theta, unit):
    """r∠θ -> complex value."""
    r, theta = _real(r, "∠"), _real(theta, "∠")
    c, s = cos(theta, unit), sin(theta, unit)
    re, im = mul(r, c), mul(r, s)
    if im == 0:
        return re
    return check(mp.mpc(to_mpf(re), to_mpf(im)))


# ---------- prime factorisation ----------

def prime_factors(n) -> list[tuple[int, int]]:
    """Factor a positive integer of at most 10 digits (manual p.12)."""
    if not is_integer(n) or n <= 0:
        raise MathError("FACT needs a positive integer")
    n = as_int(n)
    if n >= 10 ** 10:
        raise MathError("FACT needs at most 10 digits")
    out, p = [], 2
    while p * p <= n:
        e = 0
        while n % p == 0:
            n //= p
            e += 1
        if e:
            out.append((p, e))
        p += 1 if p == 2 else 2
    if n > 1:
        out.append((n, 1))
    return out


def require_args(fname, args, lo, hi=None):
    hi = lo if hi is None else hi
    if not lo <= len(args) <= hi:
        raise ArgumentError(f"{fname} takes {lo}" + (f"–{hi}" if hi != lo else "") + " argument(s)")
