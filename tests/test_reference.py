"""Randomised comparison against INDEPENDENT references (Python's C math library,
cmath, SciPy, NumPy) - never against our own code.  Tolerance 1e-12 relative,
i.e. far tighter than the 10 displayed digits."""
from fractions import Fraction as F
import cmath
import math
import random

import numpy as np
import pytest
from scipy import integrate, stats as sst

from calc import distributions as d
from calc import equations as eq
from calc.calculator import Calculator
from calc.scalars import to_mpf

RNG = random.Random(12345)
N = 400
REL = 1e-12


def close(ours, ref, rel=REL, abs_=1e-14):
    """|ours - ref| within rel·|ref| (or abs_ near zero).  Works for real and complex."""
    ours = complex(to_mpf(ours)) if isinstance(ours, F) else complex(ours)
    return abs(ours - ref) <= max(rel * abs(ref), abs_)


def val(c, text):
    return c.run(text)[0].value


def rnd(lo, hi):
    return RNG.uniform(lo, hi)


def lit(x):
    return repr(x).replace("e", "E")


@pytest.fixture
def c():
    return Calculator()


@pytest.mark.parametrize("fname,ref,lo,hi", [
    ("sin", lambda x: math.sin(math.radians(x)), -720, 720),
    ("cos", lambda x: math.cos(math.radians(x)), -720, 720),
    ("tan", lambda x: math.tan(math.radians(x)), -89, 89),
])
def test_trig_degrees(c, fname, ref, lo, hi):
    for _ in range(N):
        x = rnd(lo, hi)
        assert close(val(c, f"{fname}({lit(x)})"), ref(x), abs_=1e-13), (fname, x)


@pytest.mark.parametrize("fname,ref,lo,hi", [
    ("sin", math.sin, -50, 50), ("cos", math.cos, -50, 50), ("tan", math.tan, -1.5, 1.5),
    ("asin", math.asin, -1, 1), ("acos", math.acos, -1, 1), ("atan", math.atan, -1e6, 1e6),
])
def test_trig_radians(c, fname, ref, lo, hi):
    c.setup.angle = "Rad"
    for _ in range(N):
        x = rnd(lo, hi)
        assert close(val(c, f"{fname}({lit(x)})"), ref(x), abs_=1e-13), (fname, x)


def test_trig_gradians(c):
    c.setup.angle = "Gra"
    for _ in range(N):
        x = rnd(-800, 800)
        assert close(val(c, f"sin({lit(x)})"), math.sin(x * math.pi / 200), abs_=1e-13)


@pytest.mark.parametrize("fname,ref,lo,hi", [
    ("sinh", math.sinh, -200, 200), ("cosh", math.cosh, -200, 200), ("tanh", math.tanh, -20, 20),
    ("asinh", math.asinh, -1e10, 1e10), ("acosh", math.acosh, 1, 1e10), ("atanh", math.atanh, -0.999, 0.999),
    ("ln", math.log, 1e-50, 1e50), ("log", math.log10, 1e-50, 1e50), ("exp", math.exp, -200, 200),
    ("sqrt", math.sqrt, 0, 1e90), ("cbrt", lambda x: math.copysign(abs(x) ** (1 / 3), x), -1e30, 1e30),
])
def test_elementary(c, fname, ref, lo, hi):
    for _ in range(N):
        x = rnd(lo, hi)
        assert close(val(c, f"{fname}({lit(x)})"), ref(x), rel=1e-12), (fname, x)


def test_powers_and_logs(c):
    for _ in range(N):
        a, b = rnd(0.001, 1000), rnd(-30, 30)
        assert close(val(c, f"{lit(a)}^({lit(b)})"), a ** b), (a, b)
        assert close(val(c, f"log({lit(a + 1.5)},{lit(a)})"), math.log(a) / math.log(a + 1.5)), a
        n = RNG.randint(2, 9)
        assert close(val(c, f"root({n},{lit(a)})"), a ** (1 / n))


def test_arithmetic_exact(c):
    for _ in range(N):
        a = F(RNG.randint(-10 ** 6, 10 ** 6), RNG.randint(1, 999))
        b = F(RNG.randint(-999, 999), RNG.randint(1, 99))
        assert val(c, f"({a})+({b})") == a + b
        assert val(c, f"({a})*({b})") == a * b
        if b:
            assert val(c, f"({a})/({b})") == a / b


def test_factorial_permutation_combination(c):
    for n in range(70):
        assert val(c, f"{n}!") == math.factorial(n)
    for _ in range(N):
        n = RNG.randint(0, 300)
        r = RNG.randint(0, n)
        if math.perm(n, r) < 1e100:
            assert val(c, f"{n}nPr{r}") == math.perm(n, r)
        if math.comb(n, r) < 1e100:
            assert val(c, f"{n}nCr{r}") == math.comb(n, r)


def test_pol_rec(c):
    for _ in range(N):
        x, y = rnd(-1e3, 1e3), rnd(-1e3, 1e3)
        v = val(c, f"Pol({lit(x)},{lit(y)})").values
        assert close(v[0], math.hypot(x, y))
        assert close(v[1], math.degrees(math.atan2(y, x)), abs_=1e-12)
        v = val(c, f"Rec({lit(x)},{lit(y)})").values
        assert close(v[0], x * math.cos(math.radians(y)), abs_=1e-10)
        assert close(v[1], x * math.sin(math.radians(y)), abs_=1e-10)


def test_complex_arithmetic(c):
    c.set_mode("CMPLX")
    for _ in range(N):
        a = complex(rnd(-50, 50), rnd(-50, 50))
        b = complex(rnd(-50, 50), rnd(-50, 50))
        A = f"({lit(a.real)}+({lit(a.imag)})i)"
        B = f"({lit(b.real)}+({lit(b.imag)})i)"
        for op, ref in (("+", a + b), ("-", a - b), ("*", a * b), ("/", a / b)):
            v = val(c, f"{A}{op}{B}")
            assert abs(complex(v) - ref) <= 1e-12 * abs(ref) + 1e-12
        assert close(val(c, f"abs({A})"), abs(a))
        assert close(val(c, f"Arg({A})"), math.degrees(cmath.phase(a)), abs_=1e-12)
        k = RNG.randint(-6, 6)
        ref = a ** k
        assert abs(complex(val(c, f"{A}^{k}")) - ref) <= 1e-11 * abs(ref) + 1e-12


def test_distributions_vs_scipy():
    for _ in range(N):
        x, s, m = rnd(-20, 20), rnd(0.1, 10), rnd(-10, 10)
        Fx, Fs, Fm = F(x), F(s), F(m)
        assert close(d.normal_pd(Fx, Fs, Fm), sst.norm.pdf(x, m, s), abs_=1e-15)
        lo, hi = sorted((rnd(-30, 30), rnd(-30, 30)))
        ref = sst.norm.cdf(hi, m, s) - sst.norm.cdf(lo, m, s)
        assert close(d.normal_cd(F(lo), F(hi), Fs, Fm), ref, abs_=1e-13)
        area = rnd(1e-6, 1 - 1e-6)
        assert close(d.inverse_normal(F(area), Fs, Fm), sst.norm.ppf(area, m, s), rel=1e-9, abs_=1e-9)
        n = RNG.randint(1, 200)
        k = RNG.randint(0, n)
        p = round(rnd(0, 1), 4)
        fp = F(str(p))
        assert close(d.binomial_pd(F(k), F(n), fp), sst.binom.pmf(k, n, p), rel=1e-9, abs_=1e-15)
        assert close(d.binomial_cd(F(k), F(n), fp), sst.binom.cdf(k, n, p), rel=1e-9, abs_=1e-14)
        lam = rnd(0.01, 100)
        k = RNG.randint(0, 150)
        assert close(d.poisson_pd(F(k), F(lam)), sst.poisson.pmf(k, lam), rel=1e-9, abs_=1e-15)
        assert close(d.poisson_cd(F(k), F(lam)), sst.poisson.cdf(k, lam), rel=1e-9, abs_=1e-14)


def test_statistics_vs_numpy(c):
    c.set_mode("STAT")
    for _ in range(40):
        data = [round(rnd(-100, 100), 3) for _ in range(RNG.randint(3, 40))]
        c.stats.rows.clear()
        for x in data:
            c.stats.add(F(str(x)))
        a = np.array(data)
        assert close(val(c, "xbar"), a.mean())
        assert close(val(c, "sigx"), a.std())
        assert close(val(c, "sx"), a.std(ddof=1))
        assert close(val(c, "sumx2"), (a ** 2).sum(), rel=1e-12)


REG = {"a+bx": (lambda x: x, lambda y: y), "a+bln": (np.log, lambda y: y),
       "ae^bx": (lambda x: x, np.log), "ax^b": (np.log, np.log), "a+b/x": (lambda x: 1 / x, lambda y: y)}


@pytest.mark.parametrize("kind", list(REG))
def test_regression_vs_scipy(c, kind):
    c.set_mode("STAT")
    for _ in range(20):
        c.stats = type(c.stats)()
        c.stats.set_type(kind)
        xs = [round(rnd(0.5, 50), 3) for _ in range(12)]
        ys = [round(rnd(0.5, 50), 3) for _ in range(12)]
        for x, y in zip(xs, ys, strict=True):
            c.stats.add(F(str(x)), F(str(y)))
        tx, ty = REG[kind]
        lr = sst.linregress(tx(np.array(xs)), ty(np.array(ys)))
        a = math.exp(lr.intercept) if kind in ("ae^bx", "ax^b") else lr.intercept
        assert close(val(c, "a"), a, rel=1e-10)
        assert close(val(c, "b"), lr.slope, rel=1e-10)
        assert close(val(c, "r"), lr.rvalue, rel=1e-10)


def test_quadratic_regression_vs_numpy(c):
    c.set_mode("STAT")
    c.stats.set_type("a+bx+cx2")
    xs = [rnd(-10, 10) for _ in range(15)]
    ys = [rnd(-10, 10) for _ in range(15)]
    for x, y in zip(xs, ys, strict=True):
        c.stats.add(F(x), F(y))
    cc, bb, aa = np.polyfit(xs, ys, 2)
    for name, ref in (("a", aa), ("b", bb), ("c", cc)):
        assert close(val(c, name), ref, rel=1e-9)


def test_matrices_vs_numpy(c):
    c.set_mode("MATRIX")
    for _ in range(100):
        n = RNG.randint(1, 4)
        m = np.array([[RNG.randint(-9, 9) for _ in range(n)] for _ in range(n)], dtype=float)
        c.mats["MatA"] = c.run(str(m.astype(int).tolist()))[0].value
        assert close(val(c, "Det(MatA)"), np.linalg.det(m), abs_=1e-9)
        if abs(np.linalg.det(m)) > 1e-9:
            inv = val(c, "MatA⁻¹")
            assert np.allclose(np.array([[float(to_mpf(x)) for x in r] for r in inv.rows]),
                               np.linalg.inv(m), rtol=1e-12, atol=1e-12)


def test_simultaneous_vs_numpy():
    for _ in range(200):
        n = RNG.randint(2, 4)
        A = [[F(RNG.randint(-20, 20)) for _ in range(n)] for _ in range(n)]
        b = [F(RNG.randint(-20, 20)) for _ in range(n)]
        An = np.array(A, dtype=float)
        r = eq.simultaneous([[*row, bi] for row, bi in zip(A, b, strict=True)])
        if abs(np.linalg.det(An)) > 1e-9:
            assert r.status == "unique"
            ours = [float(to_mpf(v)) for v in r.values]
            assert np.allclose(ours, np.linalg.solve(An, np.array(b, float)))
        else:
            assert r.status in ("none", "infinite")


def test_polynomial_roots_are_roots():
    for _ in range(300):
        deg = RNG.randint(2, 4)
        cs = [F(RNG.randint(-30, 30)) for _ in range(deg + 1)]
        if cs[0] == 0:
            cs[0] = F(1)
        roots = eq.polynomial_roots(cs)
        assert len(roots) == deg
        def order(z):
            return round(z.real, 6), round(z.imag, 6)

        ref = sorted(np.roots([float(x) for x in cs]), key=order)
        ours = sorted((complex(eq._value(r)) for r in roots), key=order)
        for a, b in zip(ours, ref, strict=True):
            assert abs(a - b) <= 1e-6 * max(1, abs(b)), (cs, ours, ref)   # numpy is the weaker side
        for r in roots:      # each root actually satisfies the polynomial
            z = complex(eq._value(r))
            terms = [complex(float(cf)) * z ** (deg - i) for i, cf in enumerate(cs)]
            assert abs(sum(terms)) <= 1e-8 * max(1, max(abs(t) for t in terms))


def test_integration_vs_scipy(c):
    c.setup.angle = "Rad"
    cases = [("sin(x)", np.sin, 0, 3), ("x^2*e^(-x)", lambda x: x * x * np.exp(-x), 0, 5),
             ("1/(1+x^2)", lambda x: 1 / (1 + x * x), -4, 4), ("sqrt(x)", np.sqrt, 0, 2),
             ("ln(x)", np.log, 0.5, 9)]
    for f, ref, a, b in cases:
        expect = integrate.quad(ref, a, b, epsabs=1e-13, epsrel=1e-13)[0]
        assert close(val(c, f"integ({f},{a},{b})"), expect, rel=1e-10)


def test_derivatives(c):
    c.setup.angle = "Rad"
    for _ in range(50):
        a = rnd(0.1, 3)
        assert close(val(c, f"diff(x^3,{lit(a)})"), 3 * a * a, rel=1e-10)
        assert close(val(c, f"diff(sin(x),{lit(a)})"), math.cos(a), rel=1e-10, abs_=1e-12)
        assert close(val(c, f"diff(ln(x),{lit(a)})"), 1 / a, rel=1e-10)
