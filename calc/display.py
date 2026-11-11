"""Result formatting: Norm1/Norm2/Fix/Sci, ENG, engineering symbols, fractions,
√ and π forms, DMS, complex, base-n, matrices/vectors.  10 display digits."""
from dataclasses import dataclass, field
import decimal
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import math

import mpmath as mp

from .scalars import SNAP, is_complex, to_mpf

decimal.getcontext().prec = 60
DIGITS = 10
_SYM = {-15: "f", -12: "p", -9: "n", -6: "µ", -3: "m", 0: "", 3: "k", 6: "M", 9: "G",
        12: "T", 15: "P", 18: "E"}


@dataclass
class Setup:
    angle: str = "Deg"            # Deg / Rad / Gra
    io: str = "MathO"             # MathO (exact forms) / DecimalO
    number_format: str = "Norm1"  # Norm1 / Norm2 / Fix / Sci
    fix_digits: int = 9
    sci_digits: int = 0           # 0 means 10
    eng_symbol: bool = False
    fraction: str = "d/c"         # "ab/c" mixed or "d/c" improper
    complex_form: str = "a+bi"    # "a+bi" / "r∠θ"
    stat_freq: bool = False
    sheet_auto_calc: bool = True
    sheet_show: str = "Formula"
    eqn_complex: bool = True
    table: str = "f(x),g(x)"      # "f(x)" / "f(x),g(x)"
    decimal_mark: str = "."       # "." or ","
    digit_separator: bool = False
    extra: dict = field(default_factory=dict)


def to_decimal(x) -> Decimal:
    if isinstance(x, Fraction):
        return Decimal(x.numerator) / Decimal(x.denominator)
    return Decimal(mp.nstr(to_mpf(x), 40, min_fixed=-mp.inf, max_fixed=mp.inf))


def _round_sig(d: Decimal, sig: int) -> tuple[Decimal, int]:
    """Round to sig significant digits; return (rounded, exponent of leading digit)."""
    if d == 0:
        return Decimal(0), 0
    e = d.adjusted()
    q = Decimal(1).scaleb(e - sig + 1)
    r = d.quantize(q, rounding=ROUND_HALF_UP)
    return r, r.adjusted()


def _strip(s: str) -> str:
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _group(s: str, setup: Setup) -> str:
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    ip, _, fp = s.partition(".")
    if setup.digit_separator and len(ip) > 3:
        sep = "," if setup.decimal_mark == "." else " "
        ip = f"{int(ip):,}".replace(",", sep)
    out = ip + ((setup.decimal_mark + fp) if fp else "")
    return ("-" if neg else "") + out


def _sci(d: Decimal, sig: int, setup: Setup, keep_zeros=False) -> str:
    r, e = _round_sig(d, sig)
    mant = r.scaleb(-e)
    s = f"{mant:.{sig - 1}f}" if sig > 1 else f"{mant:.0f}"
    if not keep_zeros:
        s = _strip(s)
    return _group(s, setup) + f"×10^{e}"


def format_decimal(x, setup: Setup) -> str:
    d = to_decimal(x)
    if d == 0:
        return _zero(setup)
    nf = setup.number_format
    if setup.eng_symbol and nf.startswith("Norm"):
        return format_eng(x, setup, use_symbols=True)
    if nf == "Sci":
        sig = setup.sci_digits or 10
        return _sci(d, sig, setup, keep_zeros=True)
    if nf == "Fix":
        if abs(d) >= Decimal("1e10"):
            return _sci(d, 10, setup)
        q = Decimal(1).scaleb(-setup.fix_digits)
        r = d.quantize(q, rounding=ROUND_HALF_UP)
        if r == 0:
            r = abs(r)                      # no "-0.000"
        s = f"{r:.{setup.fix_digits}f}"
        return _group(s, setup)
    # Norm 1 / Norm 2
    r, e = _round_sig(d, DIGITS)
    lo = Decimal("1e-2") if nf == "Norm1" else Decimal("1e-9")
    if abs(r) >= Decimal("1e10") or abs(r) < lo:
        return _sci(d, DIGITS, setup)
    s = _strip(f"{r:f}")
    return _group(s, setup)


def _zero(setup):
    if setup.number_format == "Fix":
        return _group(f"{Decimal(0):.{setup.fix_digits}f}", setup)
    return "0"


def format_eng(x, setup: Setup, shift: int = 0, use_symbols=False) -> str:
    """Engineering notation: exponent a multiple of 3. shift moves the decimal
    point by 3 digits per step (ENG key = +1 step left, SHIFT ENG = -1)."""
    d = to_decimal(x)
    if d == 0:
        return "0"
    r, e = _round_sig(d, DIGITS)
    exp3 = (e // 3) * 3 - 3 * shift
    mant = r.scaleb(-exp3)
    s = _strip(f"{mant:f}")
    if use_symbols and exp3 in _SYM:
        return _group(s, setup) + _SYM[exp3]
    return _group(s, setup) + f"×10^{exp3}"


# ---------------------------------------------------------- exact forms

def _sqfree(n: int) -> tuple[int, int]:
    """n = s² · t with t square-free; returns (s, t).  n small (≤ 1e12)."""
    s, t, p = 1, n, 2
    while p * p <= t:
        while t % (p * p) == 0:
            t //= p * p
            s *= p
        p += 1
    return s, t


def frac_str(f: Fraction, setup: Setup) -> str | None:
    """Fraction display if it fits in 10 digits (manual p.10), else None."""
    if f.denominator == 1:
        return None
    n, d = f.numerator, f.denominator
    if setup.fraction == "ab/c" and abs(n) > d:
        w, rem = divmod(abs(n), d)
        if len(str(w)) + len(str(rem)) + len(str(d)) + 2 > DIGITS + 2:
            return None
        return f"{'-' if n < 0 else ''}{w} {rem}/{d}"
    if len(str(abs(n))) + len(str(d)) + 1 > DIGITS + 1:
        return None
    return f"{n}/{d}"


def exact_form(x) -> str | None:
    """Recognise k·π/c and a·√b/c values (|x| < 1e6) from a high-precision mpf."""
    if not isinstance(x, mp.mpf) or x == 0 or abs(x) >= 10 ** 6:
        return None
    # π multiples
    k = x / mp.pi
    f = Fraction(mp.nstr(k, 32, min_fixed=-mp.inf, max_fixed=mp.inf)).limit_denominator(1000)
    if f != 0 and abs(mp.mpf(f.numerator) / f.denominator - k) <= SNAP * abs(k):
        num = "" if abs(f.numerator) == 1 else str(abs(f.numerator))
        return f"{'-' if f < 0 else ''}{num}π" + (f"/{f.denominator}" if f.denominator != 1 else "")
    # single surds: x² rational
    sq = x * x
    f = Fraction(mp.nstr(sq, 32, min_fixed=-mp.inf, max_fixed=mp.inf)).limit_denominator(10 ** 6)
    if f > 0 and abs(mp.mpf(f.numerator) / f.denominator - sq) <= SNAP * sq:
        p, q = f.numerator, f.denominator
        if p * q > 10 ** 12:
            return None
        s, t = _sqfree(p * q)            # √(p/q) = √(pq)/q = s√t/q
        if t == 1:
            return None                  # actually rational
        coef = Fraction(s, q)
        num = "" if coef.numerator == 1 else str(coef.numerator)
        out = f"{num}√{t}" + (f"/{coef.denominator}" if coef.denominator != 1 else "")
        return ("-" if x < 0 else "") + out
    return None


@dataclass
class Surd:
    """Exact (p + q·√t)/1 value for equation roots; t square-free, t may be -1·t for i."""
    p: Fraction
    q: Fraction
    t: int
    imag: bool = False

    def value(self):
        r = mp.sqrt(self.t) * (mp.mpf(self.q.numerator) / self.q.denominator)
        p = mp.mpf(self.p.numerator) / self.p.denominator
        if self.imag:
            return mp.mpc(p, r)
        return p + r

    def __str__(self):
        den = math.lcm(self.p.denominator, self.q.denominator)
        a, b = self.p * den, self.q * den
        a, b = int(a), int(b)
        root = "i" if self.t == 1 and self.imag else (f"√{self.t}" + ("i" if self.imag else ""))
        bs = "" if abs(b) == 1 else str(abs(b))
        if a == 0:
            core = f"{'-' if b < 0 else ''}{bs}{root}"
            return core if den == 1 else f"{core}/{den}"
        core = f"{a}{'-' if b < 0 else '+'}{bs}{root}"
        return core if den == 1 else f"({core})/{den}"


# ---------------------------------------------------------- top level

def format_real(x, setup: Setup, decimal_only=False) -> str:
    """Exact form (fraction, π, √) when io is MathO and not forced decimal (≈)."""
    exact_ok = setup.io == "MathO" and not decimal_only
    if isinstance(x, Surd):
        return str(x) if exact_ok else format_decimal(x.value(), setup)
    if exact_ok:
        e = frac_str(x, setup) if isinstance(x, Fraction) else exact_form(x)
        if e:
            return e
    return format_decimal(x, setup)


def format_dms(x, setup: Setup) -> str:
    d = to_decimal(x)
    neg = d < 0
    d = abs(d)
    deg = int(d)
    rem = (d - deg) * 60
    mins = int(rem)
    secs = ((rem - mins) * 60).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if secs >= 60:
        secs -= 60
        mins += 1
    if mins >= 60:
        mins -= 60
        deg += 1
    s = _strip(f"{secs:f}")
    return f"{'-' if neg else ''}{deg}°{mins}'{s}\""


def format_complex(z, setup: Setup, decimal_only=False, form=None) -> str:
    from .functions import arg as _arg
    form = form or setup.complex_form
    if form == "r∠θ":
        r = abs(z)
        th = _arg(z, setup.angle)
        return f"{format_real(r, setup, decimal_only)}∠{format_real(th, setup, decimal_only)}"
    re, im = z.real, z.imag
    re_s = "" if re == 0 else format_real(re, setup, decimal_only)
    im_abs = format_real(abs(im), setup, decimal_only)
    im_abs = "" if im_abs == "1" else im_abs
    if not re_s:
        return f"{'-' if im < 0 else ''}{im_abs}i"
    return f"{re_s}{'-' if im < 0 else '+'}{im_abs}i"


def format_base(v: int, base: int) -> str:
    u = v & 0xFFFFFFFF
    if base == 10:
        return str(v)
    if base == 16:
        return f"{u:08X}"
    if base == 8:
        return f"{u:011o}"
    b = f"{u:032b}"
    return " ".join(b[i:i + 4] for i in range(0, 32, 4))


def format_scalar(v, setup: Setup, decimal_only=False) -> str:
    if is_complex(v):
        return format_complex(v, setup, decimal_only)
    return format_real(v, setup, decimal_only)
