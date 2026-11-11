"""The calculator: state (mode, setup, memories) + expression evaluation.

Public API (used by the CLI and tests):
    c = Calculator()
    c.run("4sin(30)(30+10*3)")   -> list[Output]   (multi-statements give several)
    c.set_mode("CMPLX"), c.setup.angle = "Rad", ...
    c.solve("x^2+B=0", "x", guess=1), c.calc("3A+B", {"A":5,"B":10})
    c.table(...), equations / stats / distributions helpers (see methods below)
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import random

import mpmath as mp

from . import distributions as dist
from . import functions as fn
from . import linalg as la
from . import stats as st
from .constants import BY_KEY
from .conversions import CONVERSIONS, convert
from .display import (Setup, format_base, format_complex, format_dms, format_real,
                      format_scalar, to_decimal)
from .errors import (CalcError, CannotSolve, DimensionError, MathError, RangeError, SyntaxErr,
                     TimeOut, VariableError)
from .scalars import (add, as_int, check, div, is_complex, is_integer, is_real, is_scalar,
                      mul, neg, power, snap_rational, sub, to_mpc, to_mpf)
from .parser import Lexer, Parser, split_top
from .spreadsheet import Sheet

MODES = ["COMP", "CMPLX", "BASE-N", "MATRIX", "VECTOR", "STAT", "DIST", "SHEET",
         "TABLE", "EQN", "INEQ", "RATIO"]
VARIABLES = ["A", "B", "C", "D", "E", "F", "M", "x", "y"]
STAT_VARS = ["n", "xbar", "ybar", "sumx", "sumx2", "sumy", "sumy2", "sumxy", "sumx3",
             "sumx2y", "sumx4", "sigx", "sig2x", "sx", "s2x", "sigy", "sig2y", "sy", "s2y",
             "minX", "maxX", "minY", "maxY", "Q1", "Med", "Q3", "a", "b", "c", "r"]
STAT_ALIASES = {"x̄": "xbar", "ȳ": "ybar", "σx": "sigx", "σy": "sigy", "Σx": "sumx",
                "Σx²": "sumx2", "Σy": "sumy", "Σy²": "sumy2", "Σxy": "sumxy",
                "σ²x": "sig2x", "σ²y": "sig2y", "s²x": "s2x", "s²y": "s2y"}
STAT_POSTFIX = {"xhat": 0, "xhat1": 0, "xhat2": 1, "yhat": None, "x̂": 0, "x̂1": 0,
                "x̂2": 1, "ŷ": None}
OUTPUT_FORMS = {">rθ": "r∠θ", ">r∠θ": "r∠θ", ">polar": "r∠θ", ">a+bi": "a+bi",
                ">rect": "a+bi"}
ANGLE_MARKS = {"°": "Deg", "deg": "Deg", "ʳ": "Rad", "rad": "Rad", "ᵍ": "Gra", "gra": "Gra"}
FUNC_ALIASES = {"sin⁻¹": "asin", "cos⁻¹": "acos", "tan⁻¹": "atan", "sinh⁻¹": "asinh",
                "cosh⁻¹": "acosh", "tanh⁻¹": "atanh", "arcsin": "asin", "arccos": "acos",
                "arctan": "atan", "∫": "integ", "d/dx": "diff", "Σ": "Sigma",
                "Abs": "abs", "Conjg": "conj"}


@dataclass
class Pair:
    """Two-value result (Pol, Rec)."""
    labels: tuple
    values: tuple


@dataclass
class DisplayHints:
    """How one result should be shown, decided while it was evaluated."""
    dms: bool = False          # input contained a degree-minute-second value
    form: str | None = None    # complex form forced by ▶r∠θ / ▶a+bi


@dataclass
class Output:
    text: str                  # what the display shows
    value: object
    exact_text: str            # exact form (fraction, √, π) - for S⇔D toggling
    decimal_text: str          # decimal form
    hints: DisplayHints


class Calculator:
    def __init__(self, seed=None):
        self.setup = Setup()
        self.mode = "COMP"
        self.vars = {v: Fraction(0) for v in VARIABLES}
        self.ans = Fraction(0)
        self.mats = {k: None for k in ("MatA", "MatB", "MatC", "MatD", "MatAns")}
        self.vcts = {k: None for k in ("VctA", "VctB", "VctC", "VctD", "VctAns")}
        self.stats = st.Stats()
        self.base = 10
        self.history: list[tuple[str, str]] = []
        self.rng = random.Random(seed)
        self._hints = DisplayHints()     # scratch pad for the evaluation in progress only
        self._cls_key = None
        self._cls: dict[str, str] = {}
        self._words_sorted: list[str] = []
        self.sheet_data = Sheet(self)

    # ================================================================ lexer context
    @property
    def sheet(self):
        return self.mode == "SHEET"

    @property
    def base_ctx(self):
        return self.base if self.mode == "BASE-N" else None

    def _functions(self):
        m = self.mode
        if m == "BASE-N":
            return {"Not", "Neg"}
        f = {"sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "asinh",
             "acosh", "atanh", "log", "ln", "exp", "sqrt", "cbrt", "root", "abs", "Pol",
             "Rec", "Rnd", "RanInt#", "nPr", "nCr", "integ", "diff", "Sigma",
             "NormPD", "NormCD", "InvN", "BinomPD", "BinomCD", "PoissPD", "PoissCD"}
        f |= set(FUNC_ALIASES)
        if m == "CMPLX":
            f |= {"conj", "Arg", "ReP", "ImP"}
        if m == "MATRIX":
            f |= {"Det", "Trn", "Identity"}
        if m == "VECTOR":
            f |= {"Angle", "UnitV"}
        if m == "STAT":
            f |= {"P", "Q", "R"}
        if m == "SHEET":
            f |= {"Min", "Max", "Mean", "Sum"}
        return f

    def word_class(self, w):
        return self._classes().get(w)

    def _classes(self):
        """Map of every name the lexer accepts in the current mode -> its role."""
        key = self.mode
        if self._cls_key == key:
            return self._cls
        cls = {}
        for f in self._functions():
            cls[f] = "func"
        if self.mode == "BASE-N":
            cls["Ans"] = "var"
            for w in ("and", "or", "xor", "xnor"):
                cls[w] = "infix"
        else:
            for v in VARIABLES + ["Ans"]:
                cls[v] = "var"
            for c in ("π", "pi", "e", "Ran#"):
                cls[c] = "const"
            for k in BY_KEY:
                cls["#" + k] = "const"
            for w in ("nPr", "nCr"):
                cls[w] = "infix"
            for w in ANGLE_MARKS:
                if len(w) > 1:
                    cls[w] = "postfix"
            for w in CONVERSIONS:
                cls[w] = "postfix"
            if self.mode == "CMPLX":
                cls["i"] = "const"
                for w in OUTPUT_FORMS:
                    cls[w] = "postfix"
            if self.mode == "MATRIX":
                for k in self.mats:
                    cls[k] = "var"
            if self.mode == "VECTOR":
                for k in self.vcts:
                    cls[k] = "var"
                cls["dot"] = "infix"
            if self.mode == "STAT":
                for k in STAT_VARS + list(STAT_ALIASES):
                    cls[k] = "statvar"
                for k in STAT_POSTFIX:
                    cls[k] = "postfix"
                cls[">t"] = "postfix"
        self._cls_key, self._cls = key, cls
        self._words_sorted = sorted(cls, key=len, reverse=True)
        return cls

    @property
    def words_longest_first(self):
        self._classes()
        return self._words_sorted

    def postfix_bp(self, w):
        if w in OUTPUT_FORMS:
            return 5
        if w in CONVERSIONS or w in STAT_POSTFIX:
            return 60
        return 80

    # ================================================================ modes
    def set_mode(self, mode):
        mode = mode.upper()
        if mode not in MODES:
            raise SyntaxErr(f"unknown mode '{mode}'. Modes: {', '.join(MODES)}")
        if mode != self.mode:
            self.history.clear()
            if self.mode == "STAT":
                self.stats = st.Stats()   # manual: leaving STAT clears the editor
            if self.mode == "SHEET":
                self.sheet_data = Sheet(self)   # manual: leaving SHEET clears it
        if mode == "BASE-N" and not isinstance(self.ans, int):
            self.ans = self._to_base_int(self.ans)
        elif mode != "BASE-N" and isinstance(self.ans, int):
            self.ans = Fraction(self.ans)
        self.mode = mode
        self._cls_key = None

    @staticmethod
    def _to_base_int(v):
        """Ans carried into BASE-N: fractional part cut off (manual p.23); 0 if unusable."""
        if not is_real(v):
            return 0
        n = int(v) if isinstance(v, Fraction) else int(mp.floor(v) if v >= 0 else mp.ceil(v))
        return n if -(2 ** 31) <= n < 2 ** 31 else 0

    def set_base(self, base):
        if base not in (2, 8, 10, 16):
            raise SyntaxErr("base must be 2, 8, 10 or 16")
        self.base = base

    # ================================================================ parsing
    def tokenize(self, text):
        return Lexer(self).tokenize(text)

    def parse_tokens(self, toks):
        return Parser(toks, self).parse()

    def parse(self, text):
        return self.parse_tokens(self.tokenize(text))

    # ================================================================ running
    def run(self, text: str, decimal=False) -> list[Output]:
        """Evaluate one input line.

        Supports multi-statements ('a:b'), storing ('expr->A') and the
        independent memory keys ('expr M+', 'expr M-').  decimal=True is the ≈ key.
        """
        text, _, store = text.partition("->")
        text = text.rstrip()
        memory_op = None
        if text.endswith(("M+", "M-")):
            memory_op, text = text[-1], text[:-2]
        outs = []
        for statement in split_top(self.tokenize(text), ":"):
            if len(statement) == 1:
                raise SyntaxErr("empty statement")
            outs.append(self._evaluate_top(self.parse_tokens(statement), decimal))
        last = outs[-1].value
        if store.strip():
            self.store(store.strip(), last)
        if memory_op:
            if not is_scalar(last):
                raise SyntaxErr("M+ / M- need a number")
            m = self.vars["M"]
            self.vars["M"] = add(m, last) if memory_op == "+" else sub(m, last)
        self.history.extend((text, o.text) for o in outs)
        return outs

    def _evaluate_top(self, node, decimal=False) -> Output:
        self._hints = DisplayHints()
        v = self.ev(node, {})
        if self.mode == "BASE-N" and isinstance(v, int):
            self._bcheck(v)
        if isinstance(v, la.Matrix):
            self.mats["MatAns"] = v
        elif isinstance(v, la.Vector):
            self.vcts["VctAns"] = v
        elif isinstance(v, Pair):
            self.ans = v.values[0]
        else:
            self.ans = v
        return self.output(v, decimal, self._hints)

    def output(self, v, decimal=False, hints=None) -> Output:
        hints = hints or DisplayHints()
        exact = self.format(v, decimal_only=False, hints=hints)
        dec = self.format(v, decimal_only=True, hints=hints)
        return Output(dec if decimal else exact, v, exact, dec, hints)

    def format(self, v, decimal_only=False, hints=None) -> str:
        """Display text for any result value under the current setup."""
        hints = hints or DisplayHints()
        s = self.setup
        if isinstance(v, la.Matrix):
            return "[" + ", ".join(
                "[" + ", ".join(format_scalar(x, s, decimal_only) for x in r) + "]"
                for r in v.rows) + "]"
        if isinstance(v, la.Vector):
            return "[" + ", ".join(format_scalar(x, s, decimal_only) for x in v.items) + "]"
        if isinstance(v, Pair):
            return ", ".join(f"{label}={self.format(x, decimal_only)}"
                             for label, x in zip(v.labels, v.values, strict=True))
        if self.mode == "BASE-N" and isinstance(v, int):
            return format_base(v, self.base)
        if is_complex(v):
            return format_complex(v, s, decimal_only, hints.form)
        if hints.form == "r∠θ" and is_real(v):
            return format_complex(to_mpc(v), s, decimal_only, "r∠θ") if v != 0 else "0"
        if hints.dms:
            return format_dms(v, s)
        return format_real(v, s, decimal_only)

    def value_of(self, text):
        """Evaluate an input (e.g. a coefficient) without touching Ans or history."""
        self._hints = DisplayHints()
        v = self.ev(self.parse(text), {})
        if not is_scalar(v) and not isinstance(v, int):
            raise SyntaxErr("a number is required here")
        return v

    def store(self, name, value):
        if name in self.vars:
            if not is_scalar(value):
                raise SyntaxErr("only numbers can be stored in A–F, M, x, y")
            self.vars[name] = value
        elif name in self.mats and name != "MatAns" and isinstance(value, la.Matrix):
            self.mats[name] = value
        elif name in self.vcts and name != "VctAns" and isinstance(value, la.Vector):
            self.vcts[name] = value
        else:
            raise SyntaxErr(f"cannot store into '{name}'")

    # ================================================================ evaluation
    def ev(self, n, env):
        k = n[0]
        if k == "num":
            if n[2]:
                self._hints.dms = True
            if self.mode == "BASE-N":
                v = n[1] if isinstance(n[1], int) else int(n[1])
                if v == 2 ** 31:          # allowed only as the operand of a minus sign
                    return v
                return self._bcheck(v)
            return check(n[1])
        if k == "paren":
            return self.ev(n[1], env)
        if k == "name":
            return self.resolve(n[1], env)
        if k == "neg":
            v = self.ev(n[1], env)
            if self.mode == "BASE-N":
                return self._bcheck(-v)
            if isinstance(v, la.Matrix):
                return la.mat_scale(v, Fraction(-1))
            if isinstance(v, la.Vector):
                return la.vec_scale(v, Fraction(-1))
            return neg(v)
        if k == "bin":
            return self.binary(n[1], self.ev(n[2], env), self.ev(n[3], env))
        if k == "post":
            return self.postfix(n[1], self.ev(n[2], env))
        if k == "call":
            return self.call(n[1], n[2], env)
        if k == "mat":
            return la.Matrix([[self._scalar(self.ev(x, env)) for x in r] for r in n[1]])
        if k == "vec":
            return la.Vector([self._scalar(self.ev(x, env)) for x in n[1]])
        if k in ("cell", "range"):
            return self.sheet_data.ref_value(n, env)
        raise SyntaxErr(f"cannot evaluate '{k}'")

    def _scalar(self, v):
        if not is_scalar(v):
            raise DimensionError("matrix/vector elements must be numbers")
        return v

    def resolve(self, name, env):
        if name in env:
            return env[name]
        if name in self.vars:
            return self.vars[name]
        if name == "Ans":
            return self.ans
        if name in ("π", "pi"):
            return mp.pi + 0
        if name == "e":
            return mp.e + 0
        if name == "i":
            return mp.mpc(0, 1)
        if name == "Ran#":
            return fn.ran_hash(self.rng)
        if name.startswith("#"):
            return BY_KEY[name[1:]][1]
        if name in self.mats:
            if self.mats[name] is None:
                raise DimensionError(f"{name} has not been defined")
            return self.mats[name]
        if name in self.vcts:
            if self.vcts[name] is None:
                raise DimensionError(f"{name} has not been defined")
            return self.vcts[name]
        name = STAT_ALIASES.get(name, name)
        if name in STAT_VARS:
            return self.stats.value(name)
        raise SyntaxErr(f"unknown name '{name}'")

    # ---------------------------------------------------------------- base-n
    def _bcheck(self, v):
        if not -(2 ** 31) <= v < 2 ** 31:
            raise MathError("result outside 32-bit range")
        return v

    def _base_binary(self, op, a, b):
        if op == "+":
            return self._bcheck(a + b)
        if op == "-":
            return self._bcheck(a - b)
        if op == "*":
            return self._bcheck(a * b)
        if op == "/":
            if b == 0:
                raise MathError("division by zero")
            q = abs(a) // abs(b)
            return self._bcheck(q if (a >= 0) == (b >= 0) else -q)
        bitwise = {"and": lambda p, q: p & q, "or": lambda p, q: p | q,
                   "xor": lambda p, q: p ^ q, "xnor": lambda p, q: ~(p ^ q)}
        if op not in bitwise:
            raise SyntaxErr(f"'{op}' is not available in BASE-N mode")
        bits = bitwise[op](a & 0xFFFFFFFF, b & 0xFFFFFFFF) & 0xFFFFFFFF
        return bits - 2 ** 32 if bits >= 2 ** 31 else bits      # back to signed 32-bit

    # ---------------------------------------------------------------- operators
    def binary(self, op, a, b):
        if self.mode == "BASE-N":
            return self._base_binary(op, a, b)
        if op in ("and", "or", "xor", "xnor"):
            raise SyntaxErr("logical operators need BASE-N mode")
        if not (is_scalar(a) and is_scalar(b)):
            if op == "^":
                raise DimensionError("use ², ³ or ⁻¹ for matrices")
            return la.binary(op, a, b)
        if op == "+":
            return add(a, b)
        if op == "-":
            return sub(a, b)
        if op == "*":
            return mul(a, b)
        if op == "/":
            return div(a, b)
        if op == "^":
            return power(a, b, self.mode == "CMPLX")
        if op == "nPr":
            return fn.npr(a, b)
        if op == "nCr":
            return fn.ncr(a, b)
        if op == "∠":
            if self.mode != "CMPLX":
                raise SyntaxErr("∠ needs CMPLX mode")
            return fn.polar(a, b, self.setup.angle)
        if op in ("•", "dot"):
            raise DimensionError("dot product needs vectors")
        raise SyntaxErr(f"unknown operator '{op}'")

    def postfix(self, op, v):
        if op in OUTPUT_FORMS:
            self._hints.form = OUTPUT_FORMS[op]
            return v
        if isinstance(v, la.Matrix):
            if op == "²":
                return la.mat_power(v, 2)
            if op == "³":
                return la.mat_power(v, 3)
            if op == "⁻¹":
                return la.inverse(v)
            raise DimensionError(f"'{op}' not defined for a matrix")
        if isinstance(v, la.Vector):
            raise DimensionError(f"'{op}' not defined for a vector")
        if op == "²":
            return power(v, Fraction(2))
        if op == "³":
            return power(v, Fraction(3))
        if op == "⁻¹":
            return fn.reciprocal(v)
        if op == "!":
            return fn.factorial(v)
        if op == "%":
            return div(v, Fraction(100))
        if op in ANGLE_MARKS:
            return fn.convert_angle(v, ANGLE_MARKS[op], self.setup.angle)
        if op in CONVERSIONS:
            return convert(op, v)
        if op == ">t":
            return self.stats.t_value(v)
        if op in STAT_POSTFIX:
            w = STAT_POSTFIX[op]
            return self.stats.y_hat(v) if w is None else self.stats.x_hat(v, w)
        raise SyntaxErr(f"unknown postfix '{op}'")

    # ---------------------------------------------------------------- functions
    def call(self, name, args, env):
        name = FUNC_ALIASES.get(name, name)
        u = self.setup.angle
        lazy = {"integ": self._integ, "diff": self._diff, "Sigma": self._sigma}
        if name in lazy:
            return lazy[name](args, env)
        if name in ("Min", "Max", "Mean", "Sum"):
            return self.sheet_data.range_func(name, args, env)
        vals = [self.ev(a, env) for a in args]

        def one():
            fn.require_args(name, vals, 1)
            return vals[0]
        if self.mode == "BASE-N":
            v = one()
            if name == "Not":
                return self._base_binary("xor", v, -1)
            return self._bcheck(-v)
        if name == "abs":
            v = one()
            if isinstance(v, la.Matrix):
                return la.mat_abs(v)
            if isinstance(v, la.Vector):
                return la.norm(v)
            return fn.absolute(v)
        if name == "Det":
            return la.det(self._mat(one()))
        if name == "Trn":
            return la.transpose(self._mat(one()))
        if name == "Identity":
            return la.identity(one())
        if name == "Angle":
            fn.require_args(name, vals, 2)
            return la.angle(self._vec(vals[0]), self._vec(vals[1]), u)
        if name == "UnitV":
            return la.unit_vector(self._vec(one()))
        if name == "sqrt":
            return fn.sqrt(one(), self.mode == "CMPLX")
        if name in ("conj", "ReP", "ImP"):
            return {"conj": fn.conjg, "ReP": fn.re_part, "ImP": fn.im_part}[name](one())
        if name == "Arg":
            return fn.arg(one(), u)
        for v in vals:
            if not is_scalar(v):
                raise DimensionError(f"{name} needs numbers")
            if is_complex(v):
                raise MathError(f"{name} does not accept complex numbers")
        angle_funcs = {"sin": fn.sin, "cos": fn.cos, "tan": fn.tan, "asin": fn.asin,
                       "acos": fn.acos, "atan": fn.atan}
        if name in angle_funcs:
            return angle_funcs[name](one(), u)
        simple = {"sinh": fn.sinh, "cosh": fn.cosh, "tanh": fn.tanh, "asinh": fn.asinh,
                  "acosh": fn.acosh, "atanh": fn.atanh, "ln": fn.ln, "exp": fn.exp,
                  "cbrt": fn.cbrt}
        if name in simple:
            return simple[name](one())
        if name == "log":
            fn.require_args(name, vals, 1, 2)
            return fn.log(vals[0]) if len(vals) == 1 else fn.log(vals[1], vals[0])
        if name == "root":
            fn.require_args(name, vals, 2)
            return fn.xroot(vals[0], vals[1])
        if name == "Pol":
            fn.require_args(name, vals, 2)
            r, t = fn.pol(vals[0], vals[1], u)
            self.vars["x"], self.vars["y"] = r, t
            return Pair(("r", "θ"), (r, t))
        if name == "Rec":
            fn.require_args(name, vals, 2)
            x, y = fn.rec(vals[0], vals[1], u)
            self.vars["x"], self.vars["y"] = x, y
            return Pair(("x", "y"), (x, y))
        if name == "Rnd":
            return self.rnd(one())
        if name == "RanInt#":
            fn.require_args(name, vals, 2)
            return fn.ranint(vals[0], vals[1], self.rng)
        if name == "nPr":
            fn.require_args(name, vals, 2)
            return fn.npr(*vals)
        if name == "nCr":
            fn.require_args(name, vals, 2)
            return fn.ncr(*vals)
        if name in ("P", "Q", "R"):
            return {"P": st.P, "Q": st.Q, "R": st.R}[name](one())
        dists = {"NormPD": (dist.normal_pd, 1, 3), "NormCD": (dist.normal_cd, 2, 4),
                 "InvN": (dist.inverse_normal, 1, 3), "BinomPD": (dist.binomial_pd, 3, 3),
                 "BinomCD": (dist.binomial_cd, 3, 3), "PoissPD": (dist.poisson_pd, 2, 2),
                 "PoissCD": (dist.poisson_cd, 2, 2)}
        if name in dists:
            f, lo, hi = dists[name]
            fn.require_args(name, vals, lo, hi)
            return f(*vals)
        raise SyntaxErr(f"unknown function '{name}'")

    def _mat(self, v):
        if not isinstance(v, la.Matrix):
            raise DimensionError("matrix expected")
        return v

    def _vec(self, v):
        if not isinstance(v, la.Vector):
            raise DimensionError("vector expected")
        return v

    def rnd(self, v):
        d = to_decimal(v)
        s = self.setup
        if s.number_format == "Fix":
            r = d.quantize(Decimal(1).scaleb(-s.fix_digits), rounding=ROUND_HALF_UP)
        else:
            sig = (s.sci_digits or 10) if s.number_format == "Sci" else 10
            if d == 0:
                return Fraction(0)
            r = d.quantize(Decimal(1).scaleb(d.adjusted() - sig + 1), rounding=ROUND_HALF_UP)
        return check(Fraction(r))

    # ---------------------------------------------------------------- calculus
    def _real_fn(self, f, env, var="x"):
        def F(t):
            v = self.ev(f, {**env, var: t})
            if not is_real(v):
                raise MathError("function must be real-valued")
            return to_mpf(v)
        return F

    def _integ(self, args, env):
        fn.require_args("∫", args, 3, 4)
        a = to_mpf(self.ev(args[1], env))
        b = to_mpf(self.ev(args[2], env))
        tol = to_mpf(self.ev(args[3], env)) if len(args) == 4 else mp.mpf("1e-5")
        if tol < mp.mpf("1e-14"):
            raise MathError("tol must be ≥ 1e-14")
        if a == b:
            return Fraction(0)
        F = self._real_fn(args[0], env)
        try:
            val, err = mp.quad(F, [a, b], error=True, maxdegree=8)
        except (ZeroDivisionError, ValueError, OverflowError):
            raise MathError("integrand undefined in the interval") from None
        if not mp.isfinite(val):
            raise MathError("integral diverges")
        if err > tol * max(1, abs(val)):
            raise TimeOut(f"integration error estimate {mp.nstr(err, 3)} exceeds tol")
        return check(snap_rational(val))

    def _diff(self, args, env):
        fn.require_args("d/dx", args, 2, 3)
        a = to_mpf(self.ev(args[1], env))
        tol = to_mpf(self.ev(args[2], env)) if len(args) == 3 else mp.mpf("1e-10")
        F = self._real_fn(args[0], env)
        try:
            d = mp.diff(F, a)
            left = mp.diff(F, a, direction=-1)
            right = mp.diff(F, a, direction=1)
        except MathError:
            raise MathError("function undefined near the point") from None
        scale = max(1, abs(d))
        if abs(left - right) > max(tol, mp.mpf("1e-8")) * scale:
            raise MathError("function is not differentiable at this point")
        return check(snap_rational(d))

    def _sigma(self, args, env):
        fn.require_args("Σ", args, 3)
        a, b = self.ev(args[1], env), self.ev(args[2], env)
        if not (is_integer(a) and is_integer(b)):
            raise MathError("Σ limits must be integers")
        a, b = as_int(a), as_int(b)
        if not (-10 ** 10 < a <= b < 10 ** 10):
            raise MathError("Σ needs a ≤ b within ±1e10")
        if b - a > 10 ** 6:
            raise TimeOut("Σ over more than 1,000,000 terms")
        s = Fraction(0)
        for k in range(a, b + 1):
            v = self.ev(args[0], {**env, "x": Fraction(k)})
            s = add(s, v)
        return s

    # ================================================================ CALC / SOLVE
    def variables_in(self, node, acc=None):
        acc = [] if acc is None else acc
        if isinstance(node, tuple):
            if node[0] == "name" and node[1] in VARIABLES and node[1] not in acc:
                acc.append(node[1])
            for x in node[1:]:
                if isinstance(x, (tuple, list)):
                    for y in (x if isinstance(x, list) else [x]):
                        self.variables_in(y, acc)
        elif isinstance(node, list):
            for y in node:
                self.variables_in(y, acc)
        return acc

    def calc(self, text, values: dict):
        """CALC: assign values to variables then evaluate.  'y=expr' assigns y."""
        for k, v in values.items():
            self.store(k, v)
        toks = self.tokenize(text)
        outs = []
        for part in split_top(toks, ":"):
            sides = split_top(part, "=")
            if len(sides) == 2:
                lhs = self.parse_tokens(sides[0])
                if lhs[0] != "name" or lhs[1] not in VARIABLES:
                    raise SyntaxErr("left side of CALC '=' must be a variable")
                out = self._evaluate_top(self.parse_tokens(sides[1]))
                self.vars[lhs[1]] = out.value
                outs.append(out)
            else:
                outs.append(self._evaluate_top(self.parse_tokens(part)))
        return outs

    def calc_variables(self, text):
        """Variables (A-F, M, x, y) used on either side of a CALC/SOLVE input."""
        sides = split_top(self.tokenize(text), "=")
        return self.variables_in([self.parse_tokens(t) for t in sides])

    def solve(self, text, var="x", guess=None, values=None):
        """SOLVE: Newton/secant iteration for var (manual p.19).
        Returns (solution, L-R residual).  Raises CannotSolve."""
        if self.mode != "COMP":
            raise SyntaxErr("SOLVE is available in COMP mode")
        for k, v in (values or {}).items():
            self.store(k, v)
        toks = self.tokenize(text)
        sides = split_top(toks, "=")
        if len(sides) > 2:
            raise SyntaxErr("only one '=' allowed")
        lhs = self.parse_tokens(sides[0])
        rhs = self.parse_tokens(sides[1]) if len(sides) == 2 else ("num", Fraction(0), False)
        used = self.variables_in([lhs, rhs])
        if not used:
            raise VariableError("the equation contains no variable")
        if var not in used:
            raise VariableError(f"'{var}' does not appear in the equation")
        x0 = to_mpf(guess if guess is not None else self.vars[var])

        def F(t):
            env = {var: t}
            left, right = self.ev(lhs, env), self.ev(rhs, env)
            if not (is_real(left) and is_real(right)):
                raise MathError("complex value")
            return to_mpf(sub(left, right))

        root = None
        for solver, start in (("secant", x0), ("secant", x0 + 1), ("mnewton", x0)):
            try:
                with mp.workdps(34):
                    cand = mp.findroot(F, start, solver=solver, tol=mp.mpf("1e-28"), maxsteps=200)
                if is_complex(cand):
                    continue
                res = F(cand)
                if abs(res) <= mp.mpf("1e-12") * max(1, abs(to_mpf(self.ev(lhs, {var: cand})))):
                    root = cand
                    break
            except (CalcError, ValueError, ZeroDivisionError, OverflowError):
                continue
        if root is None:
            raise CannotSolve("no solution found from this initial value")
        root = check(snap_rational(root))
        self.vars[var] = root
        resid = F(to_mpf(root))
        return root, check(resid)

    # ================================================================ TABLE
    def table(self, f_text, g_text, start, end, step):
        """Number table of f(x) (and g(x)) for x = start, start+step, ... end.
        Rows that fail show 'ERROR'.  Row limits: 45 for f only, 30 for f and g."""
        fnode = self.parse(f_text)
        gnode = self.parse(g_text) if g_text else None
        start, end, step = (snap_rational(check(v)) for v in (start, end, step))
        if step == 0 or (end - start) / step < 0:
            raise RangeError("step must move from Start toward End")
        span = div(sub(end, start), step)
        # exact floor for rationals; for floats tolerate rounding just below an integer
        whole = int(span) if isinstance(span, Fraction) else int(mp.floor(span + mp.mpf("1e-20")))
        rows = whole + 1
        limit = 30 if gnode is not None else 45
        if rows > limit:
            raise RangeError(f"table would have {rows} rows (limit {limit})")
        out = []
        x = start
        for _ in range(rows):
            row = [x]
            for node in (fnode, gnode):
                if node is None:
                    continue
                try:
                    row.append(self.ev(node, {"x": x}))
                except CalcError:
                    row.append("ERROR")
            out.append(row)
            x = add(x, step)
        self.vars["x"] = out[-1][0]       # manual: table generation changes x
        return out

    # ================================================================ resets
    def reset(self, what):
        if what in ("setup", "all"):
            self.setup = Setup()
        if what in ("memory", "all"):
            self.vars = {v: Fraction(0) for v in VARIABLES}
            self.ans = Fraction(0)
            self.mats = {k: None for k in self.mats}
            self.vcts = {k: None for k in self.vcts}
        if what == "all":
            self.set_mode("COMP")
            self.stats = st.Stats()
            self.history.clear()
