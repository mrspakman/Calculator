"""Equation/Func, Inequality and Ratio modes (manual pp.24-30)."""
from dataclasses import dataclass
from fractions import Fraction
import math

import mpmath as mp

from .display import Surd, _sqfree
from .errors import MathError
from .linalg import _eliminate
from .scalars import check, exact_root, is_complex, mpf_to_fraction, snap_rational, to_mpf


# ---------------------------------------------------------------- simultaneous

@dataclass
class SimulResult:
    status: str            # "unique" / "none" / "infinite"
    values: list


def simultaneous(rows):
    """rows: n lists of n+1 coefficients [a1 .. an, constant]."""
    n = len(rows)
    if not 2 <= n <= 4 or any(len(r) != n + 1 for r in rows):
        raise MathError("simultaneous equations need 2–4 unknowns")
    red, _, piv = _eliminate([[snap_rational(v) for v in r] for r in rows])
    if n in piv:
        return SimulResult("none", [])
    if len(piv) < n:
        return SimulResult("infinite", [])
    return SimulResult("unique", [check(red[i][n]) for i in range(n)])


# ---------------------------------------------------------------- polynomials

def _horner(coeffs, x):
    s = 0
    for c in coeffs:
        s = s * x + c
    return s


def _divisors(n: int):
    n = abs(n)
    small, large, d = [], [], 1
    while d * d <= n:
        if n % d == 0:
            small.append(d)
            if d * d != n:
                large.append(n // d)
        d += 1
    return small + large[::-1]


def _deflate(coeffs, r):
    out, s = [], 0
    for c in coeffs[:-1]:
        s = s * r + c
        out.append(s)
    return out


def _rational_roots(coeffs: list[Fraction]):
    """Exact rational roots (with multiplicity); returns (roots, remaining coeffs)."""
    roots = []
    while len(coeffs) > 1 and coeffs[-1] == 0:
        roots.append(Fraction(0))
        coeffs = coeffs[:-1]
    if len(coeffs) <= 2:
        if len(coeffs) == 2:
            roots.append(-coeffs[1] / coeffs[0])
            coeffs = coeffs[:1]
        return roots, coeffs
    lcm = 1
    for c in coeffs:
        lcm = lcm * c.denominator // math.gcd(lcm, c.denominator)
    ints = [int(c * lcm) for c in coeffs]
    if max(abs(ints[0]), abs(ints[-1])) > 10 ** 12:
        return roots, coeffs
    found = True
    while found and len(coeffs) > 2:
        found = False
        ints = [int(c * lcm) for c in coeffs]
        for p in _divisors(ints[-1]):
            for q in _divisors(ints[0]):
                for cand in (Fraction(p, q), Fraction(-p, q)):
                    if _horner(coeffs, cand) == 0:
                        roots.append(cand)
                        coeffs = _deflate(coeffs, cand)
                        found = True
                        break
                if found:
                    break
            if found:
                break
    if len(coeffs) == 2:
        roots.append(-coeffs[1] / coeffs[0])
        coeffs = coeffs[:1]
    return roots, coeffs


def _quadratic_exact(a, b, c):
    disc = b * b - 4 * a * c
    p = -b / (2 * a)
    if disc == 0:
        return [p, p]
    r = exact_root(abs(disc), 2)
    if r is not None:
        q = r / (2 * a)
        if disc > 0:
            return [p + q, p - q]
        return [check(mp.mpc(to_mpf(p), to_mpf(q))), check(mp.mpc(to_mpf(p), -to_mpf(q)))]
    dn, dd = abs(disc).numerator, abs(disc).denominator
    s, t = _sqfree(dn * dd)                 # √(dn/dd) = s√t / dd
    q = Fraction(s, dd) / (2 * a)
    imag = disc < 0
    return [Surd(p, abs(q), t, imag), Surd(p, -abs(q), t, imag)]


def _value(v):
    return v.value() if isinstance(v, Surd) else (to_mpf(v) if not is_complex(v) else v)


def _is_real(v):
    return not (isinstance(v, Surd) and v.imag) and not is_complex(v)


def polynomial_roots(coeffs):
    """coeffs high→low, degree 2–4.  Returns roots (Fraction / Surd / mpf / mpc),
    real roots first in descending order, then complex roots; repeated roots kept."""
    if not 3 <= len(coeffs) <= 5:
        raise MathError("polynomial degree must be 2–4")
    if coeffs[0] == 0:
        raise MathError("leading coefficient must not be 0")
    coeffs = [snap_rational(c) for c in coeffs]
    roots = []
    if all(isinstance(c, Fraction) for c in coeffs):
        roots, rest = _rational_roots(list(coeffs))
        if len(rest) == 3:
            roots += _quadratic_exact(*rest)
            rest = rest[:1]
        if len(rest) > 1:
            roots += _numeric_roots(rest)
    else:
        roots = _numeric_roots(coeffs)
    reals = sorted((r for r in roots if _is_real(r)), key=_value, reverse=True)
    cplx = sorted((r for r in roots if not _is_real(r)), key=lambda z: -_value(z).imag)
    return reals + cplx


def _numeric_roots(coeffs):
    cs = [to_mpf(c) for c in coeffs]
    with mp.workdps(120):
        rs = mp.polyroots(cs, maxsteps=500, extraprec=400)
    out = []
    for r in rs:
        r = check(mp.mpc(r) if isinstance(r, mp.mpc) else r)
        out.append(snap_rational(r) if not is_complex(r) else r)
    return out


def quadratic_extremum(a, b, c):
    """x, y of the local min (a>0) or max (a<0) of y = ax²+bx+c."""
    if a == 0:
        raise MathError("leading coefficient must not be 0")
    a, b, c = (snap_rational(v) for v in (a, b, c))
    x = -b / (2 * a)
    return x, c - b * b / (4 * a), ("minimum" if a > 0 else "maximum")


def unique_roots(roots):
    out = []
    for r in roots:
        if not any(abs(_value(r) - _value(o)) <= mp.mpf("1e-20") * max(1, abs(_value(o))) for o in out):
            out.append(r)
    return out


# ---------------------------------------------------------------- inequalities

def inequality(coeffs, rel):
    """Solve a·x^n + ... rel 0 with rel in {'>','<','>=','<='}.
    Returns a list of segment strings' building blocks:
      ("all",) / ("none",) / list of (lo, lo_incl, hi, hi_incl) with None = ∞."""
    if rel not in (">", "<", ">=", "<="):
        raise MathError("relation must be >, <, >= or <=")
    roots = polynomial_roots(coeffs)
    real = sorted(unique_roots([r for r in roots if _is_real(r)]), key=_value)
    vals = [_value(r) for r in real]
    cs = [to_mpf(c) for c in coeffs]

    def ok(x):
        y = mp.polyval(cs, x)
        return {">": y > 0, "<": y < 0, ">=": y >= 0, "<=": y <= 0}[rel]

    # pieces: interval before r0, r0, (r0,r1), r1, ..., after last
    pieces = []
    edges = [None] + list(range(len(real))) + [None]
    if not real:
        return [("all",)] if ok(mp.mpf(0)) else [("none",)]
    tests = [vals[0] - 1] + [(vals[i] + vals[i + 1]) / 2 for i in range(len(vals) - 1)] + [vals[-1] + 1]
    for i in range(len(real) + 1):
        pieces.append(("open", i, ok(tests[i])))
        if i < len(real):
            pieces.append(("point", i, rel in (">=", "<=")))
    segs, cur = [], None
    for kind, i, inc in pieces:
        if inc:
            if cur is None:
                if kind == "open":
                    cur = [None if i == 0 else real[i - 1], False]
                else:
                    cur = [real[i], True]
            cur_end = (real[i] if kind == "point" else (None if i == len(real) else real[i]),
                       kind == "point")
        else:
            if cur is not None:
                segs.append((cur[0], cur[1], cur_end[0], cur_end[1]))
                cur = None
    if cur is not None:
        segs.append((cur[0], cur[1], cur_end[0], cur_end[1]))
    if not segs:
        return [("none",)]
    if len(segs) == 1 and segs[0][0] is None and segs[0][2] is None:
        return [("all",)]
    return segs


# ---------------------------------------------------------------- ratio

def ratio(kind, a, b, c_or_d):
    """kind 1: A:B = X:D -> X = A·D/B ;  kind 2: A:B = C:X -> X = B·C/A."""
    from .scalars import div, mul
    if 0 in (a, b, c_or_d):
        raise MathError("ratio coefficients must not be 0")
    if kind == 1:
        return div(mul(a, c_or_d), b)
    if kind == 2:
        return div(mul(b, c_or_d), a)
    raise MathError("ratio type must be 1 (A:B=X:D) or 2 (A:B=C:X)")


def format_inequality(segs, fmt):
    """Render inequality() output, e.g. 'x<-3, 1≤x', 'All Real Numbers'."""
    out = []
    for sg in segs:
        if sg[0] == "all":
            return "All Real Numbers"
        if sg[0] == "none":
            return "No Solution"
        lo, lo_inc, hi, hi_inc = sg
        f = lambda v: str(v) if isinstance(v, Surd) else fmt(v)
        if lo is not None and lo is hi:
            out.append(f"x={f(lo)}")
            continue
        a = (f(lo) + ("≤" if lo_inc else "<")) if lo is not None else ""
        b = (("≤" if hi_inc else "<") + f(hi)) if hi is not None else ""
        out.append(a + "x" + b)
    return ", ".join(out)


def format_root(v, fmt):
    return str(v) if isinstance(v, Surd) else fmt(v)
