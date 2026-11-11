"""Matrix (up to 4x4) and vector (2D/3D) arithmetic using exact-where-possible scalars."""
from dataclasses import dataclass
from fractions import Fraction

import mpmath as mp

from . import functions as fn
from .errors import DimensionError, MathError
from .scalars import add, check, div, is_scalar, mul, sub, to_mpf


@dataclass
class Matrix:
    rows: list

    @property
    def shape(self):
        return len(self.rows), len(self.rows[0])

    def __post_init__(self):
        if not self.rows or not self.rows[0]:
            raise DimensionError("empty matrix")
        n = len(self.rows[0])
        if any(len(r) != n for r in self.rows):
            raise DimensionError("ragged matrix")
        if len(self.rows) > 4 or n > 4:
            raise DimensionError("matrices are limited to 4x4")


@dataclass
class Vector:
    items: list

    def __post_init__(self):
        if len(self.items) not in (2, 3):
            raise DimensionError("vectors must be 2D or 3D")


def _abs_mag(v):
    return abs(to_mpf(v)) if not isinstance(v, Fraction) else abs(v)


def mat_add(a: Matrix, b: Matrix, op=add):
    if a.shape != b.shape:
        raise DimensionError("matrix sizes differ")
    return Matrix([[op(x, y) for x, y in zip(ra, rb, strict=True)]
                   for ra, rb in zip(a.rows, b.rows, strict=True)])


def mat_scale(a: Matrix, k):
    return Matrix([[mul(k, x) for x in r] for r in a.rows])


def mat_mul(a: Matrix, b: Matrix):
    (n, m), (m2, p) = a.shape, b.shape
    if m != m2:
        raise DimensionError("columns of left ≠ rows of right")
    out = []
    for i in range(n):
        row = []
        for j in range(p):
            s = Fraction(0)
            for k in range(m):
                s = add(s, mul(a.rows[i][k], b.rows[k][j]))
            row.append(s)
        out.append(row)
    return Matrix(out)


def transpose(a: Matrix):
    return Matrix([list(c) for c in zip(*a.rows, strict=True)])


def identity(n):
    if not (fn.is_integer(n) and 1 <= n <= 4):
        raise MathError("Identity needs 1 to 4")
    n = int(n)
    return Matrix([[Fraction(int(i == j)) for j in range(n)] for i in range(n)])


def _eliminate(rows):
    """Gauss-Jordan on a copy; returns (reduced rows, det, pivot columns)."""
    a = [list(r) for r in rows]
    n, m = len(a), len(a[0])
    det = Fraction(1)
    pivots, r = [], 0
    for c in range(m):
        if r >= n:
            break
        best = max(range(r, n), key=lambda i: _abs_mag(a[i][c]))
        if a[best][c] == 0:
            continue
        if best != r:
            a[r], a[best] = a[best], a[r]
            det = -det
        piv = a[r][c]
        det = mul(det, piv)
        a[r] = [div(x, piv) for x in a[r]]
        for i in range(n):
            if i != r and a[i][c] != 0:
                f = a[i][c]
                a[i] = [sub(x, mul(f, y)) for x, y in zip(a[i], a[r], strict=True)]
        pivots.append(c)
        r += 1
    return a, det, pivots


def det(a: Matrix):
    n, m = a.shape
    if n != m:
        raise DimensionError("determinant needs a square matrix")
    _, d, piv = _eliminate(a.rows)
    return check(d) if len(piv) == n else Fraction(0)


def inverse(a: Matrix):
    n, m = a.shape
    if n != m:
        raise DimensionError("inverse needs a square matrix")
    aug = [r + [Fraction(int(i == j)) for j in range(n)] for i, r in enumerate(a.rows)]
    red, _, piv = _eliminate(aug)
    if piv[:n] != list(range(n)):
        raise MathError("matrix is singular")
    return Matrix([r[n:] for r in red])


def mat_power(a: Matrix, k: int):
    n, m = a.shape
    if n != m:
        raise DimensionError("power needs a square matrix")
    out = a
    for _ in range(k - 1):
        out = mat_mul(out, a)
    return out


def mat_abs(a: Matrix):
    return Matrix([[abs(x) for x in r] for r in a.rows])


# ---------------------------------------------------------------- vectors

def vec_add(a: Vector, b: Vector, op=add):
    if len(a.items) != len(b.items):
        raise DimensionError("vector sizes differ")
    return Vector([op(x, y) for x, y in zip(a.items, b.items, strict=True)])


def vec_scale(a: Vector, k):
    return Vector([mul(k, x) for x in a.items])


def dot(a: Vector, b: Vector):
    if len(a.items) != len(b.items):
        raise DimensionError("vector sizes differ")
    s = Fraction(0)
    for x, y in zip(a.items, b.items, strict=True):
        s = add(s, mul(x, y))
    return s


def cross(a: Vector, b: Vector):
    if len(a.items) != len(b.items):
        raise DimensionError("vector sizes differ")
    x = a.items + [Fraction(0)] * (3 - len(a.items))
    y = b.items + [Fraction(0)] * (3 - len(b.items))
    return Vector([sub(mul(x[1], y[2]), mul(x[2], y[1])),
                   sub(mul(x[2], y[0]), mul(x[0], y[2])),
                   sub(mul(x[0], y[1]), mul(x[1], y[0]))])


def norm(a: Vector):
    return fn.sqrt(dot(a, a))


def angle(a: Vector, b: Vector, unit):
    na, nb = norm(a), norm(b)
    if na == 0 or nb == 0:
        raise MathError("angle with a zero vector")
    c = div(dot(a, b), mul(na, nb))
    if not isinstance(c, Fraction):
        c = max(min(c, mp.mpf(1)), mp.mpf(-1))   # rounding can push |cos| a hair past 1
    return fn.acos(c, unit)


def unit_vector(a: Vector):
    n = norm(a)
    if n == 0:
        raise MathError("zero vector has no direction")
    return Vector([div(x, n) for x in a.items])


def binary(op, a, b):
    """Dispatch +, -, *, / and • for matrices, vectors and scalars."""
    ma, mb = isinstance(a, Matrix), isinstance(b, Matrix)
    va, vb = isinstance(a, Vector), isinstance(b, Vector)
    if op == "+":
        if ma and mb:
            return mat_add(a, b)
        if va and vb:
            return vec_add(a, b)
    elif op == "-":
        if ma and mb:
            return mat_add(a, b, sub)
        if va and vb:
            return vec_add(a, b, sub)
    elif op == "*":
        if ma and mb:
            return mat_mul(a, b)
        if ma and is_scalar(b):
            return mat_scale(a, b)
        if mb and is_scalar(a):
            return mat_scale(b, a)
        if va and vb:
            return cross(a, b)
        if va and is_scalar(b):
            return vec_scale(a, b)
        if vb and is_scalar(a):
            return vec_scale(b, a)
    elif op == "/":
        if ma and is_scalar(b):
            return mat_scale(a, div(Fraction(1), b))
        if va and is_scalar(b):
            return vec_scale(a, div(Fraction(1), b))
    elif op in ("•", "dot"):
        if va and vb:
            return dot(a, b)
    raise DimensionError(f"'{op}' not defined for these operands")
