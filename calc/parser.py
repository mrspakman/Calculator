"""Tokenizer and Pratt parser for linear (one-line) input.

Operator priority follows the reference manual (p.8-9), highest first:
  1 parentheses  2 functions f(  3 postfix ² ³ ⁻¹ ! ° % ▶t, eng symbols, ^, roots
  5 negative sign  6 conversions, x̂ ŷ  7 implicit multiplication
  8 nPr nCr ∠  9 dot product  10 × ÷  11 + −  12 and  13 or xor xnor
Equal priorities evaluate left to right (so 2^3^2 = (2^3)^2 = 64, as the manual states).
"""
from dataclasses import dataclass
from fractions import Fraction
import re

from .errors import StackError, SyntaxErr

ENG_SYMBOLS = {"m": -3, "u": -6, "n": -9, "p": -12, "f": -15, "k": 3, "M": 6,
               "G": 9, "T": 12, "P": 15, "E": 18}

MAX_DEPTH = 40
DIGIT_CHARS = "0123456789"

_NUM_RE = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:E[+\-]?\d+)?")
_DMS_RE = re.compile(r"°(\d+\.?\d*)'(?:(\d+\.?\d*)\")?")
_CELL_RE = re.compile(r"\$?[A-E]\$?\d{1,2}")

_NORMALISE = {"−": "-", "×": "*", "÷": "/", "µ": "u", "μ": "u", "▶": ">", "·": "*",
              "⋅": "•", "→": "->"}

SYMBOL_OPS = ["⁻¹", "->", "²", "³", "!", "%", "°", "ʳ", "ᵍ", "√", "∛", "∠", "@", "•",
              "+", "-", "*", "/", "^", "(", ")", ",", ":", "[", "]", "="]


@dataclass
class Tok:
    kind: str      # NUM NAME OP CELL END
    value: object
    pos: int
    dms: bool = False


class Lexer:
    def __init__(self, ctx):
        """ctx supplies: words (set of known names), base_ctx (None or 2/8/10/16),
        sheet (bool) for spreadsheet cell references."""
        self.ctx = ctx

    def tokenize(self, text: str) -> list[Tok]:
        for a, b in _NORMALISE.items():
            text = text.replace(a, b)
        words = sorted(self.ctx.words, key=len, reverse=True)
        toks, i, n = [], 0, len(text)
        while i < n:
            ch = text[i]
            if ch.isspace():
                i += 1
                continue
            # spreadsheet cell references / ranges
            if self.ctx.sheet and (m := _CELL_RE.match(text, i)) and not _alnum(text, m.end()):
                toks.append(Tok("CELL", m.group().replace("$", "$"), i))
                i = m.end()
                continue
            # base-n literals
            if self.ctx.base_ctx:
                tok, j = self._base_literal(text, i, words)
                if tok:
                    toks.append(tok)
                    i = j
                    continue
            # postfix words starting with '>' (▶t, ▶r∠θ, ▶a+bi) and conversions
            w = self._match_word(text, i, words)
            if w:
                toks.append(Tok("NAME", w, i))
                i += len(w)
                continue
            if ch in DIGIT_CHARS or (ch == "." and i + 1 < n and text[i + 1] in DIGIT_CHARS):
                tok, i = self._number(text, i, words)
                toks.append(tok)
                continue
            for op in SYMBOL_OPS:
                if text.startswith(op, i):
                    toks.append(Tok("OP", op, i))
                    i += len(op)
                    break
            else:
                raise SyntaxErr(f"unexpected '{text[i:i + 8]}' at position {i + 1}")
        toks.append(Tok("END", None, n))
        return toks

    def _match_word(self, text, i, words):
        for w in words:
            if text.startswith(w, i):
                # words ending in a letter must not run into more letters
                # unless the rest can itself be split into known words
                return w
        return None

    def _number(self, text, i, words):
        m = _NUM_RE.match(text, i)
        s = m.group()
        j = m.end()
        dm = _DMS_RE.match(text, j)
        if dm:
            d = Fraction(s)
            mins = Fraction(dm.group(1))
            secs = Fraction(dm.group(2)) if dm.group(2) else Fraction(0)
            return Tok("NUM", d + mins / 60 + secs / 3600, i, dms=True), dm.end()
        value = Fraction(s)
        # engineering symbol suffix directly after the number
        if j < len(text) and text[j] in ENG_SYMBOLS:
            nxt = text[j + 1] if j + 1 < len(text) else ""
            is_word = any(text.startswith(w, j) and len(w) > 1 for w in words)
            if not (nxt.isascii() and nxt.isalnum() or (nxt and nxt in "(_#")) and not is_word:
                value *= Fraction(10) ** ENG_SYMBOLS[text[j]]
                j += 1
        return Tok("NUM", value, i), j

    def _base_literal(self, text, i, words):
        base = self.ctx.base_ctx
        prefix = {"d": 10, "h": 16, "b": 2, "o": 8}
        # known words (Ans, Not, Neg, and, or...) win over hex digits
        for w in words:
            if text.startswith(w, i) and not (len(w) == 1 and w in "ABCDEF"):
                return None, i
        b = base
        j = i
        if text[i] in prefix and i + 1 < len(text) and re.match(r"[0-9A-F]", text[i + 1]):
            b = prefix[text[i]]
            j = i + 1
        m = re.compile(r"[0-9A-F]+").match(text, j)
        if not m:
            return None, i
        digits = m.group()
        try:
            value = int(digits, b)
        except ValueError:
            raise SyntaxErr(f"'{digits}' is not a valid base-{b} number") from None
        bits = {2: 32, 8: 32, 16: 32}.get(b)
        if bits and value >= 2 ** 31:          # two's complement entry
            if value >= 2 ** 32:
                raise SyntaxErr("value exceeds 32 bits")
            value -= 2 ** 32
        return Tok("NUM", value, i), m.end()


def _alnum(text, j):
    return j < len(text) and text[j].isascii() and text[j].isalnum()


# ---------------------------------------------------------------- parser

BINARY = {"or": 10, "xor": 10, "xnor": 10, "and": 20, "+": 30, "-": 30, "*": 40, "/": 40,
          "•": 45, "dot": 45, "nPr": 50, "nCr": 50, "∠": 50, "@": 50, "^": 80}
POSTFIX_SYMBOLS = {"²", "³", "⁻¹", "!", "%", "°", "ʳ", "ᵍ"}
IMPLICIT_BP = 55
NEG_BP = 70
POSTFIX_BP = 80
OUTPUT_FORMAT_BP = 5   # ▶r∠θ, ▶a+bi apply to the whole expression


class Parser:
    def __init__(self, tokens, ctx):
        self.toks, self.i, self.ctx, self.depth = tokens, 0, ctx, 0

    def peek(self):
        return self.toks[self.i]

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def at(self, kind, value=None):
        t = self.peek()
        return t.kind == kind and (value is None or t.value == value)

    def expect_close(self):
        if self.at("OP", ")"):
            self.next()
        elif not self.at("END"):
            raise SyntaxErr(f"expected ')' at position {self.peek().pos + 1}")
        # closing parentheses may be omitted at the end of input (manual p.8)

    def parse(self):
        node = self.expr(0)
        if not self.at("END"):
            t = self.peek()
            raise SyntaxErr(f"unexpected '{t.value}' at position {t.pos + 1}")
        return node

    # -- Pratt core
    def expr(self, rbp):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise StackError("expression nested too deeply")
        left = self.nud(self.next())
        while True:
            t = self.peek()
            lbp = self.lbp(t)
            if lbp <= rbp:
                break
            left = self.led(t, left)
        self.depth -= 1
        return left

    def starts_operand(self, t):
        if t.kind in ("NUM", "CELL"):
            return True
        if t.kind == "OP":
            return t.value in ("(", "[", "√", "∛")
        if t.kind == "NAME":
            c = self.ctx.word_class(t.value)
            return c in ("var", "const", "func", "statvar")
        return False

    def lbp(self, t):
        if t.kind == "END":
            return 0
        if t.kind == "OP":
            if t.value in BINARY:
                return BINARY[t.value]
            if t.value in POSTFIX_SYMBOLS:
                return POSTFIX_BP
        if t.kind == "NAME":
            c = self.ctx.word_class(t.value)
            if c == "infix":
                return BINARY[t.value]
            if c == "postfix":
                return self.ctx.postfix_bp(t.value)
        if self.starts_operand(t):
            return IMPLICIT_BP
        return 0

    def nud(self, t):
        if t.kind == "NUM":
            return ("num", t.value, t.dms)
        if t.kind == "CELL":
            if self.at("OP", ":"):
                self.next()
                end = self.next()
                if end.kind != "CELL":
                    raise SyntaxErr("bad cell range")
                return ("range", t.value, end.value)
            return ("cell", t.value)
        if t.kind == "OP":
            v = t.value
            if v == "(":
                e = self.expr(0)
                self.expect_close()
                return ("paren", e)
            if v == "-":
                return ("neg", self.expr(NEG_BP))
            if v == "+":
                return self.expr(NEG_BP)
            if v in ("√", "∛"):
                if self.at("OP", "("):
                    self.next()
                    e = self.expr(0)
                    self.expect_close()
                    return ("call", "sqrt" if v == "√" else "cbrt", [e])
                return ("call", "sqrt" if v == "√" else "cbrt", [self.expr(POSTFIX_BP)])
            if v == "[":
                return self.bracket()
            raise SyntaxErr(f"unexpected '{v}' at position {t.pos + 1}")
        if t.kind == "NAME":
            c = self.ctx.word_class(t.value)
            if c == "func":
                if not self.at("OP", "("):
                    raise SyntaxErr(f"'{t.value}' needs '(' (position {t.pos + 1})")
                self.next()
                args = []
                if not self.at("OP", ")") and not self.at("END"):
                    args.append(self.expr(0))
                    while self.at("OP", ","):
                        self.next()
                        args.append(self.expr(0))
                self.expect_close()
                return ("call", t.value, args)
            if c in ("var", "const", "statvar"):
                return ("name", t.value)
            if c == "prefix":      # base-n d/h/b/o handled in lexer; Not/Neg are funcs
                return ("pre", t.value, self.expr(NEG_BP))
            raise SyntaxErr(f"'{t.value}' cannot start an expression")
        raise SyntaxErr("incomplete expression")

    def bracket(self):
        items = []
        if not self.at("OP", "]"):
            items.append(self.expr(0) if not self.at("OP", "[") else self._row())
            while self.at("OP", ","):
                self.next()
                items.append(self.expr(0) if not self.at("OP", "[") else self._row())
        if not self.at("OP", "]"):
            raise SyntaxErr("expected ']'")
        self.next()
        if items and all(isinstance(x, tuple) and x[0] == "row" for x in items):
            return ("mat", [x[1] for x in items])
        if any(isinstance(x, tuple) and x[0] == "row" for x in items):
            raise SyntaxErr("mixed matrix/vector literal")
        return ("vec", items)

    def _row(self):
        self.next()  # '['
        row = [self.expr(0)]
        while self.at("OP", ","):
            self.next()
            row.append(self.expr(0))
        if not self.at("OP", "]"):
            raise SyntaxErr("expected ']'")
        self.next()
        return ("row", row)

    def led(self, t, left):
        if t.kind == "OP" and t.value in BINARY:
            self.next()
            op = {"@": "∠"}.get(t.value, t.value)
            return ("bin", op, left, self.expr(BINARY[t.value]))
        if t.kind == "OP" and t.value in POSTFIX_SYMBOLS:
            self.next()
            return ("post", t.value, left)
        if t.kind == "NAME":
            c = self.ctx.word_class(t.value)
            if c == "infix":
                self.next()
                return ("bin", t.value, left, self.expr(BINARY[t.value]))
            if c == "postfix":
                self.next()
                return ("post", t.value, left)
        # implicit multiplication
        if t.kind == "NUM":
            raise SyntaxErr(f"number cannot follow a value (position {t.pos + 1})")
        return ("bin", "*", left, self.expr(IMPLICIT_BP))


def split_top(tokens, sep):
    """Split a token list on OP sep at bracket depth 0."""
    parts, cur, depth = [], [], 0
    for t in tokens[:-1]:
        if t.kind == "OP" and t.value in ("(", "["):
            depth += 1
        elif t.kind == "OP" and t.value in (")", "]"):
            depth -= 1
        if t.kind == "OP" and t.value == sep and depth == 0:
            parts.append(cur + [Tok("END", None, t.pos)])
            cur = []
        else:
            cur.append(t)
    parts.append(cur + [tokens[-1]])
    return parts
