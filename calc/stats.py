"""Single-variable statistics and the eight regression types (manual pp.20-23)."""
from fractions import Fraction

import mpmath as mp

from . import functions as fn
from .errors import MathError
from .linalg import _eliminate
from .scalars import add, check, div, is_integer, mul, power, sub, to_mpf

TYPES = {
    "1-Var": "single variable",
    "a+bx": "y=a+bx",
    "a+bx+cx2": "y=a+bx+cx²",
    "a+bln": "y=a+b·ln(x)",
    "ae^bx": "y=a·e^(bx)",
    "ab^x": "y=a·b^x",
    "ax^b": "y=a·x^b",
    "a+b/x": "y=a+b/x",
}

MAX_ROWS = {1: 160, 2: 80, 3: 53}   # by number of columns


class Stats:
    def __init__(self):
        self.kind = "1-Var"
        self.rows: list[list] = []      # [x, (y), freq]
        self.freq_column = False

    # ------------------------------------------------------------ data entry
    def columns(self):
        return (1 if self.kind == "1-Var" else 2) + (1 if self.freq_column else 0)

    def set_type(self, kind):
        if kind not in TYPES:
            raise MathError(f"unknown statistics type '{kind}'")
        if (kind == "1-Var") != (self.kind == "1-Var"):
            self.rows = []               # manual: switching 1-var/paired clears data
        self.kind = kind

    def add(self, x, y=None, freq=Fraction(1)):
        if len(self.rows) >= MAX_ROWS[self.columns()]:
            raise MathError("statistics editor is full")
        if freq < 0:
            raise MathError("frequency must be ≥ 0")
        if self.kind == "1-Var":
            self.rows.append([x, None, freq])
        else:
            if y is None:
                raise MathError("paired data needs x and y")
            self.rows.append([x, y, freq])

    # ------------------------------------------------------------ sums
    def _data(self):
        if not self.rows:
            raise MathError("no statistics data")
        return [(r[0], r[1], r[2]) for r in self.rows if r[2] != 0]

    def n(self):
        s = Fraction(0)
        for _, _, f in self._data():
            s = add(s, f)
        if s == 0:
            raise MathError("no statistics data")
        return s

    def _sum(self, g):
        s = Fraction(0)
        for x, y, f in self._data():
            s = add(s, mul(f, g(x, y)))
        return s

    def sums(self):
        sq = lambda v: mul(v, v)
        out = {"sumx": self._sum(lambda x, y: x), "sumx2": self._sum(lambda x, y: sq(x))}
        if self.kind != "1-Var":
            out.update({
                "sumy": self._sum(lambda x, y: y), "sumy2": self._sum(lambda x, y: sq(y)),
                "sumxy": self._sum(lambda x, y: mul(x, y)),
                "sumx3": self._sum(lambda x, y: mul(sq(x), x)),
                "sumx2y": self._sum(lambda x, y: mul(sq(x), y)),
                "sumx4": self._sum(lambda x, y: sq(sq(x))),
            })
        return out

    def _mean(self, idx):
        return div(self._sum(lambda x, y: (x, y)[idx]), self.n())

    def _ss(self, idx):
        """Σ f·(v - mean)²  (two-pass, exact for rational data)."""
        m = self._mean(idx)
        return self._sum(lambda x, y: mul(sub((x, y)[idx], m), sub((x, y)[idx], m)))

    def pop_var(self, idx=0):
        return div(self._ss(idx), self.n())

    def sample_var(self, idx=0):
        n = self.n()
        if n <= 1:
            raise MathError("sample variance needs n > 1")
        return div(self._ss(idx), sub(n, Fraction(1)))

    def _sorted_expanded(self):
        vals = []
        for x, _, f in self._data():
            if not is_integer(f):
                raise MathError("quartiles need integer frequencies")
            vals += [x] * int(f)
        return sorted(vals, key=to_mpf)

    @staticmethod
    def _median(v):
        m = len(v)
        if m == 0:
            raise MathError("not enough data")
        return v[m // 2] if m % 2 else div(add(v[m // 2 - 1], v[m // 2]), Fraction(2))

    def quartiles(self):
        v = self._sorted_expanded()
        m = len(v)
        if m == 1:
            return v[0], v[0], v[0]
        half = m // 2
        lower, upper = v[:half], v[half + (m % 2):]
        return self._median(lower), self._median(v), self._median(upper)

    def value(self, name):
        """Statistics variables usable in expressions."""
        paired = self.kind != "1-Var"
        y_ok = {"ybar", "sigy", "sig2y", "sy", "s2y", "minY", "maxY", "sumy", "sumy2",
                "sumxy", "sumx3", "sumx2y", "sumx4", "a", "b", "c", "r"}
        if name in y_ok and not paired:
            raise MathError(f"'{name}' needs paired-variable statistics")
        if name in ("Q1", "Med", "Q3") and paired:
            raise MathError(f"'{name}' is for single-variable statistics only")
        if name.startswith("sum"):
            return self.sums()[name]
        table = {
            "n": self.n, "xbar": lambda: self._mean(0), "ybar": lambda: self._mean(1),
            "sig2x": lambda: self.pop_var(0), "sig2y": lambda: self.pop_var(1),
            "sigx": lambda: fn.sqrt(self.pop_var(0)), "sigy": lambda: fn.sqrt(self.pop_var(1)),
            "s2x": lambda: self.sample_var(0), "s2y": lambda: self.sample_var(1),
            "sx": lambda: fn.sqrt(self.sample_var(0)), "sy": lambda: fn.sqrt(self.sample_var(1)),
            "minX": lambda: min((d[0] for d in self._data()), key=to_mpf),
            "maxX": lambda: max((d[0] for d in self._data()), key=to_mpf),
            "minY": lambda: min((d[1] for d in self._data()), key=to_mpf),
            "maxY": lambda: max((d[1] for d in self._data()), key=to_mpf),
            "Q1": lambda: self.quartiles()[0], "Med": lambda: self.quartiles()[1],
            "Q3": lambda: self.quartiles()[2],
        }
        if name in table:
            return table[name]()
        if name in ("a", "b", "c", "r"):
            return self.regression()[name]
        raise MathError(f"unknown statistics variable '{name}'")

    # ------------------------------------------------------------ regression
    def _transformed(self):
        k = self.kind
        tx = {"a+bln": fn.ln, "ax^b": fn.ln, "a+b/x": fn.reciprocal}.get(k, lambda v: v)
        ty = {"ae^bx": fn.ln, "ab^x": fn.ln, "ax^b": fn.ln}.get(k, lambda v: v)
        return [(tx(x), ty(y), f) for x, y, f in self._data()]

    def regression(self):
        k = self.kind
        if k == "1-Var":
            raise MathError("regression needs paired-variable data")
        data = self._transformed()
        n = Fraction(0)
        for *_, f in data:
            n = add(n, f)

        def S(g):
            s = Fraction(0)
            for x, y, f in data:
                s = add(s, mul(f, g(x, y)))
            return s

        if k == "a+bx+cx2":
            sx, sx2 = S(lambda x, y: x), S(lambda x, y: mul(x, x))
            sx3, sx4 = S(lambda x, y: power(x, Fraction(3))), S(lambda x, y: power(x, Fraction(4)))
            sy, sxy, sx2y = S(lambda x, y: y), S(lambda x, y: mul(x, y)), S(lambda x, y: mul(mul(x, x), y))
            aug = [[n, sx, sx2, sy], [sx, sx2, sx3, sxy], [sx2, sx3, sx4, sx2y]]
            red, _, piv = _eliminate(aug)
            if piv != [0, 1, 2]:
                raise MathError("quadratic regression is singular for this data")
            return {"a": red[0][3], "b": red[1][3], "c": red[2][3]}
        mx, my = div(S(lambda x, y: x), n), div(S(lambda x, y: y), n)
        sxx = S(lambda x, y: mul(sub(x, mx), sub(x, mx)))
        syy = S(lambda x, y: mul(sub(y, my), sub(y, my)))
        sxy = S(lambda x, y: mul(sub(x, mx), sub(y, my)))
        if sxx == 0:
            raise MathError("all x values are equal")
        b = div(sxy, sxx)
        a = sub(my, mul(b, mx))
        r = Fraction(0) if syy == 0 else div(sxy, fn.sqrt(mul(sxx, syy)))
        if k in ("ae^bx", "ab^x", "ax^b"):
            a = fn.exp(a)
        if k == "ab^x":
            b = fn.exp(b)
        return {"a": a, "b": b, "r": r}

    def y_hat(self, x):
        k, c = self.kind, self.regression()
        a, b = c["a"], c["b"]
        if k == "a+bx":
            return add(a, mul(b, x))
        if k == "a+bx+cx2":
            return add(add(a, mul(b, x)), mul(c["c"], mul(x, x)))
        if k == "a+bln":
            return add(a, mul(b, fn.ln(x)))
        if k == "ae^bx":
            return mul(a, fn.exp(mul(b, x)))
        if k == "ab^x":
            return mul(a, power(b, x))
        if k == "ax^b":
            return mul(a, power(x, b))
        if k == "a+b/x":
            return add(a, div(b, x))
        raise MathError("regression needs paired-variable data")

    def x_hat(self, y, which=0):
        k, c = self.kind, self.regression()
        a, b = c["a"], c["b"]
        if k == "a+bx":
            return div(sub(y, a), b)
        if k == "a+bx+cx2":
            cc = c["c"]
            disc = sub(mul(b, b), mul(Fraction(4), mul(cc, sub(a, y))))
            if disc < 0:
                raise MathError("no real x for this y")
            sq = fn.sqrt(disc)
            return div(add(-b, sq if which == 0 else -sq), mul(Fraction(2), cc))
        if k == "a+bln":
            return fn.exp(div(sub(y, a), b))
        if k == "ae^bx":
            return div(fn.ln(div(y, a)), b)
        if k == "ab^x":
            return div(fn.ln(div(y, a)), fn.ln(b))
        if k == "ax^b":
            return power(div(y, a), div(Fraction(1), b))
        if k == "a+b/x":
            return div(b, sub(y, a))
        raise MathError("regression needs paired-variable data")

    # ------------------------------------------------------------ normal dist (1-var)
    def t_value(self, x):
        return div(sub(x, self._mean(0)), fn.sqrt(self.pop_var(0)))


def phi(t):
    return mp.ncdf(to_mpf(t))


def P(t):
    return check(phi(t))


def Q(t):
    return check(abs(phi(t) - mp.mpf("0.5")))


def R(t):
    return check(1 - phi(t))
