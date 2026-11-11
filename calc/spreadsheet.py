"""Spreadsheet mode: 5 columns (A-E) x 45 rows (manual pp.33-36)."""
from fractions import Fraction
import re

from .errors import CalcError, CircularError, MathError, MemoryErr, RangeError, SyntaxErr
from .scalars import add, div, to_mpf

COLS, ROWS, MEMORY = "ABCDE", 45, 1700
_REF = re.compile(r"(\$?)([A-E])(\$?)(\d{1,2})")


def parse_ref(ref):
    m = _REF.fullmatch(ref.replace(" ", ""))
    if not m or not 1 <= int(m.group(4)) <= ROWS:
        raise RangeError(f"'{ref}' is not a cell between A1 and E45")
    return COLS.index(m.group(2)), int(m.group(4))


def name(col, row):
    return f"{COLS[col]}{row}"


def cells_in(a, b):
    (c1, r1), (c2, r2) = parse_ref(a), parse_ref(b)
    return [name(c, r) for c in range(min(c1, c2), max(c1, c2) + 1)
            for r in range(min(r1, r2), max(r1, r2) + 1)]


def shift_refs(text, dc, dr):
    """Move relative references by (dc, dr); out-of-range parts become '?'."""
    def rep(m):
        cabs, col, rabs, row = m.groups()
        c, r = COLS.index(col), int(row)
        if not cabs:
            c += dc
        if not rabs:
            r += dr
        cs = COLS[c] if 0 <= c < 5 else "?"
        rs = str(r) if 1 <= r <= ROWS else "?"
        return f"{cabs}{cs}{rabs}{rs}"
    return _REF.sub(rep, text)


class Sheet:
    def __init__(self, calc):
        self.calc = calc
        self.cells: dict[str, str] = {}     # raw content: "=A1+7" formula or constant value text
        self.consts: dict[str, object] = {}
        self.cache: dict[str, object] = {}
        self._stack: list[str] = []
        self.clipboard = None

    # ------------------------------------------------------------ editing
    def memory_used(self):
        return sum(len(t) + 11 if t.startswith("=") else 10 for t in self.cells.values())

    def set(self, ref, text):
        """Enter a cell.  '=...' is a formula (re-evaluated when inputs change);
        anything else is a constant, evaluated once now (manual p.33)."""
        ref = name(*parse_ref(ref))
        text = text.strip()
        if not text:
            self.delete(ref)
            return
        old = self.cells.get(ref)
        if text.startswith("="):
            if len(text) - 1 > 49:
                raise MemoryErr("formula longer than 49 bytes")
            self.cells[ref] = text
            self.consts.pop(ref, None)
        else:
            value = self._eval(text)
            self.cells[ref] = text
            self.consts[ref] = value
        if self.memory_used() > MEMORY:
            if old is None:
                self.cells.pop(ref)
            else:
                self.cells[ref] = old
            raise MemoryErr("spreadsheet memory (1,700 bytes) exceeded")
        self._changed()

    def delete(self, ref):
        ref = name(*parse_ref(ref))
        self.cells.pop(ref, None)
        self.consts.pop(ref, None)
        self._changed()

    def delete_all(self):
        self.cells.clear()
        self.consts.clear()
        self._changed()

    def _changed(self):
        if self.calc.setup.sheet_auto_calc:
            self.cache.clear()

    def recalculate(self):
        self.cache.clear()

    def copy(self, src):
        src = name(*parse_ref(src))
        self.clipboard = ("copy", src, self.cells.get(src))

    def cut(self, src):
        src = name(*parse_ref(src))
        self.clipboard = ("cut", src, self.cells.get(src))

    def paste(self, dst):
        if not self.clipboard:
            raise SyntaxErr("nothing to paste")
        kind, src, text = self.clipboard
        if text is None:
            self.delete(dst)
            return
        if kind == "copy" and text.startswith("="):
            (sc, sr), (dc, dr) = parse_ref(src), parse_ref(dst)
            text = shift_refs(text, dc - sc, dr - sr)
        self.set(dst, text)
        if kind == "cut":
            self.delete(src)
            self.clipboard = None

    def fill_formula(self, formula, rng):
        a, b = rng.split(":")
        cells = cells_in(a, b)
        c0, r0 = parse_ref(cells[0])
        for ref in cells:
            c, r = parse_ref(ref)
            self.set(ref, "=" + shift_refs(formula.lstrip("="), c - c0, r - r0))

    def fill_value(self, expr, rng):
        a, b = rng.split(":")
        cells = cells_in(a, b)
        c0, r0 = parse_ref(cells[0])
        for ref in cells:
            c, r = parse_ref(ref)
            self.set(ref, shift_refs(expr, c - c0, r - r0))

    # ------------------------------------------------------------ evaluation
    def _eval(self, text):
        if self.calc.mode != "SHEET":
            raise SyntaxErr("the spreadsheet is only available in SHEET mode")
        if "?" in text:
            raise RangeError("reference outside A1:E45")
        return self.calc.ev(self.calc.parse(text), {})

    def value(self, ref):
        ref = name(*parse_ref(ref))
        if ref in self.cache:
            v = self.cache[ref]
            if isinstance(v, CalcError):
                raise v
            return v
        text = self.cells.get(ref)
        if text is None:
            return None
        if not text.startswith("="):
            return self.consts[ref]
        if ref in self._stack:
            raise CircularError(f"circular reference through {ref}")
        self._stack.append(ref)
        try:
            v = self._eval(text[1:])
            self.cache[ref] = v
            return v
        except CalcError as e:
            if not isinstance(e, CircularError):
                self.cache[ref] = e
            raise
        finally:
            self._stack.pop()

    def ref_value(self, node, _env):
        if node[0] == "range":
            raise SyntaxErr("a cell range can only be used inside Min/Max/Mean/Sum")
        v = self.value(node[1].replace("$", ""))
        return Fraction(0) if v is None else v

    def range_func(self, fname, args, _env):
        if len(args) != 1 or args[0][0] != "range":
            raise SyntaxErr(f"{fname} needs a cell range like A1:A3")
        vals = [v for v in (self.value(r) for r in cells_in(args[0][1].replace("$", ""),
                                                            args[0][2].replace("$", "")))
                if v is not None]
        if not vals:
            raise MathError(f"{fname}: range contains no values")
        if fname == "Min":
            return min(vals, key=to_mpf)
        if fname == "Max":
            return max(vals, key=to_mpf)
        s = Fraction(0)
        for v in vals:
            s = add(s, v)
        return s if fname == "Sum" else div(s, Fraction(len(vals)))

    def grid(self):
        """Formatted values: {ref: text}."""
        out = {}
        for ref in self.cells:
            try:
                out[ref] = self.calc.format(self.value(ref))
            except CalcError:
                out[ref] = "ERROR"
        return out
