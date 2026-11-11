"""Text-mode simulation of the calculator.   Run:  python -m calc"""
from fractions import Fraction
from pathlib import Path
import sys

from . import equations as eq
from . import functions as fn
from .calculator import MODES, VARIABLES, Calculator
from .constants import CONSTANTS
from .conversions import CONVERSIONS
from .display import format_eng, format_dms
from .errors import CalcError
from .formula_store import FormulaStore
from .formulas import FormulaError, format_result, parse_equation, solve as fsolve, variables
from .stats import TYPES

HELP = """\
Type an expression and press Enter.  Examples:  4sin(30)(30+10*3)   2^0.5   500k+25k
  multi-statements  3+3:3*3      store  3+5->A      memory  10*5 M+   (M- subtracts)
  ~expr  show decimal (≈)   sd  toggle exact/decimal   eng / eng<  engineering notation
  dms  show last result as °'"   fact  prime factors of last result
Settings
  mode [COMP|CMPLX|BASE-N|MATRIX|VECTOR|STAT|DIST|SHEET|TABLE|EQN|INEQ|RATIO]
  setup  (show)   setup angle Deg|Rad|Gra   setup io MathO|DecimalO
  setup fix N | sci N | norm 1|2   setup engsym on|off   setup frac ab/c|d/c
  setup complex a+bi|r∠θ   setup freq on|off   setup eqncomplex on|off
  setup table f|fg   setup decimal .|,   setup sep on|off   setup autocalc on|off
  reset setup|memory|all    vars    history    const [category]    conv
Our formula library (20 slots, kept through power-off)
  f list   f save N Name : R = R1*R2/(R1+R2)   f del N   f use N
Mode tools
  calc <expr>            CALC (prompts for each variable)
  solve <equation>       SOLVE (Newton; asks which variable and a start value)
  dec | hex | bin | oct  BASE-N number base
  mat A [[2,1],[1,1]]    vct A [1,2]
  stat type <t> (1-Var a+bx a+bx+cx2 a+bln ae^bx ab^x ax^b a+b/x)
  stat add x [y] [freq]  stat list  stat del N  stat clear  stat calc  stat reg
  dist <NormPD|NormCD|InvN|BinomPD|BinomCD|PoissPD|PoissCD>
  table     simul N     poly N     ineq N > | < | >= | <=     ratio 1|2
  cell A1 =A2+7    cell A1 (clears)   sheet   fill formula =2A1-3 B1:B3
  fill value B1*3 C1:C3   copy A1 | cut A1 | paste B2   recalc   sheet clear
  help   quit"""

DATA = Path(__file__).resolve().parent.parent / "calc_data"


class CLI:
    def __init__(self, inp=input, out=print):
        self.c = Calculator()
        self.inp, self.out = inp, out
        DATA.mkdir(exist_ok=True)
        self.formulas = FormulaStore(DATA / "formulas.json")
        self.last = None
        self.showing_exact = True
        self.eng_shift = 0

    def ask(self, prompt):
        return self.inp(prompt)

    def num(self, prompt, default=None):
        while True:
            raw = self.ask(prompt + (f" [{self.c.format(default)}]" if default is not None else "") + ": ").strip()
            if not raw and default is not None:
                return default
            try:
                return self.c.value_of(raw)
            except CalcError as e:
                self.out(str(e))

    def status(self):
        s = self.c.setup
        nf = s.number_format + (str(s.fix_digits) if s.number_format == "Fix" else
                                str(s.sci_digits) if s.number_format == "Sci" else "")
        base = {2: "BIN", 8: "OCT", 10: "DEC", 16: "HEX"}[self.c.base] if self.c.mode == "BASE-N" else ""
        return f"[{self.c.mode} {base}{s.angle} {nf} {s.io}]".replace("  ", " ")

    def loop(self):
        self.out("Formula calculator (desktop simulation). Type 'help' for commands.")
        while True:
            try:
                line = self.ask(f"{self.status()} > ")
            except (EOFError, KeyboardInterrupt):
                self.out("")
                return
            if line.strip() in ("quit", "exit", "q"):
                return
            try:
                self.handle(line)
            except CalcError as e:
                self.out(str(e))
            except FormulaError as e:
                self.out(f"Formula error: {e}")

    # ------------------------------------------------------------------ dispatch
    def handle(self, line):
        line = line.strip()
        if not line:
            return
        word, _, rest = line.partition(" ")
        rest = rest.strip()
        cmd = getattr(self, "cmd_" + word.lower().replace("-", "_"), None)
        if cmd and word.lower() not in ("e",):
            return cmd(rest)
        decimal = line.startswith("~")
        outs = self.c.run(line.lstrip("~"), decimal=decimal)
        for o in outs:
            self.out(o.text)
        self.last = outs[-1]
        self.showing_exact = not decimal
        self.eng_shift = 0

    # ------------------------------------------------------------------ general
    def cmd_help(self, rest):
        self.out(HELP)

    def cmd_mode(self, rest):
        if not rest:
            self.out("Modes: " + "  ".join(MODES))
            return
        self.c.set_mode(rest)
        self.out(f"Mode {self.c.mode}")

    def cmd_setup(self, rest):
        s = self.c.setup
        if not rest:
            for k, v in vars(s).items():
                if k != "extra":
                    self.out(f"  {k:16} {v}")
            return
        key, _, val = rest.partition(" ")
        val = val.strip()
        onoff = lambda: {"on": True, "off": False}[val.lower()]
        try:
            if key == "angle":
                s.angle = {"deg": "Deg", "rad": "Rad", "gra": "Gra"}[val.lower()[:3]]
            elif key == "io":
                s.io = {"matho": "MathO", "decimalo": "DecimalO"}[val.lower()]
            elif key == "fix":
                s.number_format, s.fix_digits = "Fix", _digit(val)
            elif key == "sci":
                s.number_format, s.sci_digits = "Sci", _digit(val)
            elif key == "norm":
                s.number_format = {"1": "Norm1", "2": "Norm2"}[val]
            elif key == "engsym":
                s.eng_symbol = onoff()
            elif key == "frac":
                s.fraction = {"ab/c": "ab/c", "d/c": "d/c"}[val]
            elif key == "complex":
                s.complex_form = {"a+bi": "a+bi", "r∠θ": "r∠θ", "polar": "r∠θ"}[val]
            elif key == "freq":
                s.stat_freq = self.c.stats.freq_column = onoff()
            elif key == "eqncomplex":
                s.eqn_complex = onoff()
            elif key == "table":
                s.table = {"f": "f(x)", "fg": "f(x),g(x)"}[val]
            elif key == "decimal":
                s.decimal_mark = {".": ".", ",": ","}[val]
            elif key == "sep":
                s.digit_separator = onoff()
            elif key == "autocalc":
                s.sheet_auto_calc = onoff()
            else:
                self.out(f"unknown setup item '{key}'")
                return
        except (KeyError, ValueError):
            self.out(f"bad value '{val}' for {key}")
            return
        self.out("OK")

    def cmd_reset(self, rest):
        if rest not in ("setup", "memory", "all"):
            self.out("reset setup | memory | all")
            return
        self.c.reset(rest)
        self.out("Reset done")

    def cmd_vars(self, rest):
        for v in VARIABLES + ["Ans"]:
            val = self.c.ans if v == "Ans" else self.c.vars[v]
            self.out(f"  {v:4}= {self.c.format(val)}")

    def cmd_history(self, rest):
        for i, (q, a) in enumerate(self.c.history, 1):
            self.out(f"  {i:3}  {q}  =  {a}")

    def cmd_sd(self, rest):
        if not self.last:
            return
        self.showing_exact = not self.showing_exact
        self.out(self.last.exact_text if self.showing_exact else self.last.decimal_text)

    def cmd_eng(self, rest):
        if self.last:
            self.eng_shift += 1
            self.out(format_eng(self.last.value, self.c.setup, self.eng_shift - 1))

    def cmd_eng_(self, rest):
        pass

    def cmd_dms(self, rest):
        if self.last:
            self.out(format_dms(self.last.value, self.c.setup))

    def cmd_fact(self, rest):
        if self.last:
            fs = fn.prime_factors(self.last.value)
            self.out("×".join(f"{p}" + (f"^{e}" if e > 1 else "") for p, e in fs) or "1")

    def cmd_const(self, rest):
        for cat, key, nm, val, unit in CONSTANTS:
            if not rest or rest.lower() in cat.lower():
                self.out(f"  #{key:9} {nm:6} {self.c.format(val, True):>22}  {unit}   ({cat})")

    def cmd_conv(self, rest):
        cats = {}
        for k, (cat, _) in CONVERSIONS.items():
            cats.setdefault(cat, []).append(k)
        for cat, ks in cats.items():
            self.out(f"  {cat:12} " + "  ".join(ks))

    # ------------------------------------------------------------------ CALC / SOLVE
    def cmd_calc(self, rest):
        if self.c.mode not in ("COMP", "CMPLX"):
            self.c.set_mode("COMP")
        expr = rest or self.ask("Expression: ")
        values = {}
        for v in self.c.calc_variables(expr):
            if "=" in expr and expr.split("=")[0].strip() == v:
                continue
            values[v] = self.num(f"  {v}?", self.c.vars[v])
        for o in self.c.calc(expr, values):
            self.out(o.text)
            self.last = o

    def cmd_solve(self, rest):
        if self.c.mode != "COMP":
            self.c.set_mode("COMP")
        expr = rest or self.ask("Equation (e.g. x^2+B=0): ")
        used = self.c.calc_variables(expr)
        var = self.ask(f"Solve for ({'/'.join(used)}) [{used[0] if used else 'x'}]: ").strip() or (used[0] if used else "x")
        values = {}
        for v in used:
            if v != var:
                values[v] = self.num(f"  {v}?", self.c.vars[v])
        guess = self.num(f"  start value for {var}", self.c.vars.get(var, Fraction(0)))
        root, resid = self.c.solve(expr, var, guess, values)
        self.out(f"{var}= {self.c.format(root, True)}\nL-R= {self.c.format(resid, True)}")

    # ------------------------------------------------------------------ BASE-N
    def _base(self, b):
        if self.c.mode != "BASE-N":
            self.out("Base selection needs BASE-N mode (mode BASE-N)")
            return
        self.c.set_base(b)
        self.out(self.c.format(self.c.ans))

    def cmd_dec(self, rest): self._base(10)
    def cmd_hex(self, rest): self._base(16)
    def cmd_bin(self, rest): self._base(2)
    def cmd_oct(self, rest): self._base(8)

    # ------------------------------------------------------------------ MATRIX / VECTOR
    def cmd_mat(self, rest):
        name, _, lit = rest.partition(" ")
        key = "Mat" + name.upper().replace("MAT", "")
        if key not in self.c.mats or key == "MatAns":
            self.out("mat A|B|C|D [[..],[..]]")
            return
        if not lit:
            m = self.c.mats[key]
            self.out(self.c.format(m) if m else f"{key} is not defined")
            return
        saved = self.c.mode
        self.c.set_mode("MATRIX")
        v = self.c.ev(self.c.parse(lit), {})
        from .linalg import Matrix
        if not isinstance(v, Matrix):
            self.c.set_mode(saved)
            self.out("give a matrix like [[1,2],[3,4]]")
            return
        self.c.mats[key] = v
        self.out(f"{key} = {self.c.format(v)}")

    def cmd_vct(self, rest):
        name, _, lit = rest.partition(" ")
        key = "Vct" + name.upper().replace("VCT", "")
        if key not in self.c.vcts or key == "VctAns":
            self.out("vct A|B|C|D [x,y(,z)]")
            return
        if not lit:
            v = self.c.vcts[key]
            self.out(self.c.format(v) if v else f"{key} is not defined")
            return
        self.c.set_mode("VECTOR")
        v = self.c.ev(self.c.parse(lit), {})
        from .linalg import Vector
        if not isinstance(v, Vector):
            self.out("give a vector like [1,2] or [1,2,3]")
            return
        self.c.vcts[key] = v
        self.out(f"{key} = {self.c.format(v)}")

    # ------------------------------------------------------------------ STAT
    def cmd_stat(self, rest):
        if self.c.mode != "STAT":
            self.c.set_mode("STAT")
        s = self.c.stats
        sub, _, args = rest.partition(" ")
        if sub == "type":
            if args not in TYPES:
                self.out("types: " + "  ".join(TYPES))
                return
            s.set_type(args)
            self.out(f"Type {args}: {TYPES[args]}")
        elif sub == "add":
            vals = [self.c.value_of(a) for a in args.split()]
            paired = s.kind != "1-Var"
            need = 2 if paired else 1
            if len(vals) < need:
                self.out("stat add x y [freq]" if paired else "stat add x [freq]")
                return
            freq = vals[need] if len(vals) > need else Fraction(1)
            s.add(vals[0], vals[1] if paired else None, freq)
            self.out(f"row {len(s.rows)} added")
        elif sub == "list":
            for i, (x, y, f) in enumerate(s.rows, 1):
                cols = [self.c.format(x)] + ([self.c.format(y)] if y is not None else []) + \
                       ([self.c.format(f)] if s.freq_column else [])
                self.out(f"  {i:3}  " + "  ".join(f"{c:>12}" for c in cols))
        elif sub == "del":
            s.rows.pop(int(args) - 1)
        elif sub == "clear":
            s.rows.clear()
        elif sub == "calc":
            names = ["n", "xbar", "sumx", "sumx2", "sig2x", "sigx", "s2x", "sx", "minX", "Q1", "Med", "Q3", "maxX"]
            if s.kind != "1-Var":
                names = ["n", "xbar", "sumx", "sumx2", "sigx", "sx", "ybar", "sumy", "sumy2", "sumxy",
                         "sigy", "sy", "minX", "maxX", "minY", "maxY"]
            for nm in names:
                try:
                    self.out(f"  {nm:6}= {self.c.format(s.value(nm), True)}")
                except CalcError as e:
                    self.out(f"  {nm:6}  {e}")
        elif sub == "reg":
            for k, v in s.regression().items():
                self.out(f"  {k} = {self.c.format(v, True)}")
        else:
            self.out("stat type|add|list|del|clear|calc|reg")

    # ------------------------------------------------------------------ DIST
    def cmd_dist(self, rest):
        from . import distributions as d
        specs = {"normpd": (d.normal_pd, ["x", "σ", "μ"], [None, Fraction(1), Fraction(0)]),
                 "normcd": (d.normal_cd, ["Lower", "Upper", "σ", "μ"], [None, None, Fraction(1), Fraction(0)]),
                 "invn": (d.inverse_normal, ["Area", "σ", "μ"], [None, Fraction(1), Fraction(0)]),
                 "binompd": (d.binomial_pd, ["x", "N", "p"], [None] * 3),
                 "binomcd": (d.binomial_cd, ["x", "N", "p"], [None] * 3),
                 "poisspd": (d.poisson_pd, ["x", "λ"], [None] * 2),
                 "poisscd": (d.poisson_cd, ["x", "λ"], [None] * 2)}
        key = rest.lower()
        if key not in specs:
            self.out("dist NormPD|NormCD|InvN|BinomPD|BinomCD|PoissPD|PoissCD")
            return
        f, names, defaults = specs[key]
        xs = [None]
        if names[0] == "x" and key not in ("normpd",) or key == "normpd":
            raw = self.ask("  x (one value, or several separated by spaces for a list): ").strip()
            xs = [self.c.value_of(t) for t in raw.split()]
            names, defaults = names[1:], defaults[1:]
        params = [self.num(f"  {n}", dv) for n, dv in zip(names, defaults)]
        for x in xs:
            args = ([x] if x is not None else []) + params
            try:
                v = f(*args)
                self.c.ans = v
                self.out((f"  x={self.c.format(x)}  " if len(xs) > 1 else "  ") + f"p= {self.c.format(v, True)}")
            except CalcError as e:
                self.out(f"  x={self.c.format(x)}  ERROR ({e})")

    # ------------------------------------------------------------------ TABLE
    def cmd_table(self, rest):
        self.c.set_mode("TABLE")
        f = self.ask("  f(x)= ")
        g = self.ask("  g(x)= (blank for none) ") if self.c.setup.table == "f(x),g(x)" else ""
        start = self.num("  Start", Fraction(1))
        end = self.num("  End", Fraction(5))
        step = self.num("  Step", Fraction(1))
        rows = self.c.table(f, g.strip() or None, start, end, step)
        self.out("      x" + " " * 10 + "f(x)" + (" " * 12 + "g(x)" if g.strip() else ""))
        for r in rows:
            self.out("  " + "  ".join(f"{(v if isinstance(v, str) else self.c.format(v, True)):>14}" for v in r))

    # ------------------------------------------------------------------ EQN / INEQ / RATIO
    def _coeffs(self, n, letters):
        return [self.num(f"  {l}") for l in letters[:n]]

    def cmd_simul(self, rest):
        n = int(rest or 2)
        if not 2 <= n <= 4:
            self.out("simul 2|3|4")
            return
        self.c.set_mode("EQN")
        rows = []
        xs = "xyzt"[:n]
        self.out("  enter a1 x + a2 y ... = c as coefficients")
        for i in range(n):
            rows.append(self._coeffs(n + 1, [f"eq{i + 1} {v}" for v in xs] + [f"eq{i + 1} ="]))
        r = eq.simultaneous(rows)
        if r.status == "none":
            self.out("No Solution")
        elif r.status == "infinite":
            self.out("Infinite Solution")
        else:
            for v, val in zip(xs, r.values):
                self.out(f"  {v}= {self.c.format(val)}")

    def cmd_poly(self, rest):
        n = int(rest or 2)
        if not 2 <= n <= 4:
            self.out("poly 2|3|4")
            return
        self.c.set_mode("EQN")
        cs = self._coeffs(n + 1, "abcde")
        roots = eq.polynomial_roots(cs)
        if not self.c.setup.eqn_complex:
            roots = [r for r in roots if eq._is_real(r)]
            if not roots:
                self.out("No Real Roots")
        for i, r in enumerate(roots, 1):
            self.out(f"  x{i}= {eq.format_root(r, self.c.format)}")
        if n == 2:
            x, y, kind = eq.quadratic_extremum(*cs)
            self.out(f"  {kind}: x= {self.c.format(x)}  y= {self.c.format(y)}")

    def cmd_ineq(self, rest):
        parts = rest.split()
        if len(parts) != 2 or parts[0] not in "234" or parts[1] not in (">", "<", ">=", "<="):
            self.out("ineq 2|3|4  > | < | >= | <=")
            return
        self.c.set_mode("INEQ")
        n = int(parts[0])
        cs = self._coeffs(n + 1, "abcde")
        self.out("  " + eq.format_inequality(eq.inequality(cs, parts[1]), self.c.format))

    def cmd_ratio(self, rest):
        kind = int(rest or 1)
        self.c.set_mode("RATIO")
        a, b = self.num("  A"), self.num("  B")
        third = self.num("  D" if kind == 1 else "  C")
        x = eq.ratio(kind, a, b, third)
        self.c.ans = x
        self.out(f"  X= {self.c.format(x)}")

    # ------------------------------------------------------------------ SHEET
    def _sheet(self):
        if self.c.mode != "SHEET":
            self.c.set_mode("SHEET")
        return self.c.sheet_data

    def cmd_cell(self, rest):
        ref, _, content = rest.partition(" ")
        self._sheet().set(ref.upper(), content)
        self.cmd_sheet("")

    def cmd_sheet(self, rest):
        sh = self._sheet()
        if rest == "clear":
            sh.delete_all()
            return
        grid = sh.grid()
        rows = sorted({int(r[1:]) for r in grid} or {1})
        self.out("      " + "".join(f"{c:>12}" for c in "ABCDE"))
        for r in range(1, max(rows) + 1):
            self.out(f"  {r:3} " + "".join(f"{grid.get(f'{c}{r}', ''):>12}" for c in "ABCDE"))
        self.out(f"  memory used {sh.memory_used()}/1700 bytes")

    def cmd_fill(self, rest):
        kind, _, args = rest.partition(" ")
        content, _, rng = args.rpartition(" ")
        sh = self._sheet()
        (sh.fill_formula if kind == "formula" else sh.fill_value)(content, rng.upper())
        self.cmd_sheet("")

    def cmd_copy(self, rest): self._sheet().copy(rest.upper())
    def cmd_cut(self, rest): self._sheet().cut(rest.upper())

    def cmd_paste(self, rest):
        self._sheet().paste(rest.upper())
        self.cmd_sheet("")

    def cmd_recalc(self, rest):
        self._sheet().recalculate()
        self.cmd_sheet("")

    # ------------------------------------------------------------------ formulas
    def cmd_f(self, rest):
        sub, _, args = rest.partition(" ")
        st = self.formulas
        if sub == "list":
            for i, s in enumerate(st.slots, 1):
                if s:
                    self.out(f"  F{i:<2} {s['name']:<16} {s['formula']}")
            if all(s is None for s in st.slots):
                self.out("  (no formulas stored)")
        elif sub == "save":
            head, _, formula = args.partition(":")
            slot, _, name = head.strip().partition(" ")
            st.put(int(slot.lstrip("Ff")), name.strip() or f"F{slot}", formula.strip())
            self.out(f"Saved F{slot}")
        elif sub == "del":
            st.delete(int(args.lstrip("Ff")))
            self.out("Deleted")
        elif sub == "use":
            slot = int(args.lstrip("Ff"))
            e = st.get(slot)
            if not e:
                self.out("Empty slot")
                return
            q = parse_equation(e["formula"])
            names = variables(q)
            self.out(f"F{slot}: {e['formula']}   variables: {', '.join(names)}")
            target = self.ask("  Solve for: ").strip()
            vals = {}
            self.out("  enter values (blank = keep symbolic)")
            for n in names:
                if n == target:
                    continue
                raw = self.ask(f"    {n}? ").strip()
                if raw:
                    vals[n] = float(self.c.value_of(raw))
            self.out(format_result(fsolve(q, target, vals)))
        else:
            self.out("f list | f save N Name : formula | f del N | f use N")


def _digit(v):
    d = int(v)
    if not 0 <= d <= 9:
        raise ValueError
    return d


def main():
    CLI().loop()


if __name__ == "__main__":
    main()
