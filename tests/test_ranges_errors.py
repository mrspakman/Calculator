"""Input ranges (manual pp.40-41): just inside -> a result, just outside -> the
documented error.  Plus every error type in the manual's error list."""
from fractions import Fraction as F

import pytest

from calc.calculator import Calculator
from calc.errors import (ArgumentError, CannotSolve, CircularError, DimensionError,
                         MathError, MemoryErr, RangeError, StackError, SyntaxErr, TimeOut,
                         VariableError)


@pytest.fixture
def c():
    return Calculator()


def ok(c, text):
    return c.run(text)[0].value


def err(c, text, exc=MathError):
    with pytest.raises(exc):
        c.run(text)


EDGES = [  # (angle unit, inside, outside)
    ("Deg", "sin(8.999999999E9)", "sin(9E9)"),
    ("Rad", "cos(157079632.6)", "cos(157079632.7)"),
    ("Gra", "sin(9.999999999E9)", "sin(1E10)"),
    ("Deg", "asin(1)", "asin(1.0000000001)"),
    ("Deg", "acos(-1)", "acos(-1.0000000001)"),
    ("Deg", "sinh(230.2585092)", "sinh(230.2585093)"),
    ("Deg", "cosh(-230.2585092)", "cosh(-230.2585093)"),
    ("Deg", "acosh(1)", "acosh(0.9999999999)"),
    ("Deg", "atanh(0.9999999999)", "atanh(1)"),
    ("Deg", "log(1E-99)", "log(0)"),
    ("Deg", "ln(1E-99)", "ln(-1)"),
    ("Deg", "10^(99.99999999)", "10^(100)"),
    ("Deg", "e^(230.2585092)", "e^(230.2585093)"),
    ("Deg", "sqrt(0)", "sqrt(-1E-99)"),
    ("Deg", "(1E49)²", "(1E50)²"),
    ("Deg", "(1E-99)⁻¹", "0⁻¹"),
    ("Deg", "69!", "70!"),
    ("Deg", "0!", "(-1)!"),
    ("Deg", "9999999999nPr2", "10000000000nPr2"),
    ("Deg", "9999999999nCr2", "10000000000nCr2"),
    ("Deg", "(-8)^(1/3)", "(-8)^(1/2)"),
    ("Deg", "root(3,-8)", "root(2,-8)"),
    ("Deg", "2^332", "2^333"),
    ("Deg", "9.999999999E99", "9.999999999E99*10"),
]


@pytest.mark.parametrize("unit,inside,outside", EDGES)
def test_input_range_edges(c, unit, inside, outside):
    c.setup.angle = unit
    ok(c, inside)
    err(c, outside)


def test_tan_undefined(c):
    for x in (90, 270, -90, 450):
        err(c, f"tan({x})")
    c.setup.angle = "Rad"
    err(c, "tan(pi/2)")
    c.setup.angle = "Gra"
    err(c, "tan(100)")


def test_exact_special_angles(c):
    assert ok(c, "sin(180)") == 0 and ok(c, "cos(90)") == 0 and ok(c, "tan(45)") == 1
    c.setup.angle = "Rad"
    assert ok(c, "sin(pi)") == 0 and ok(c, "cos(pi/2)") == 0 and ok(c, "sin(pi/6)") == F(1, 2)


def test_underflow_to_zero(c):
    assert ok(c, "1E-99/10") == 0


def test_division_by_zero(c):
    err(c, "1/0")
    err(c, "1/(2-2)")
    err(c, "0^0")
    err(c, "0^(-1)")


def test_syntax_errors(c):
    for bad in ("2+", "*3", "sin 30", "2 3", "(", "3+)", "foo", "1..2"):
        with pytest.raises(SyntaxErr):
            c.run(bad)


def test_stack_error(c):
    with pytest.raises(StackError):
        c.run("(" * 60 + "1")


def test_argument_error(c):
    with pytest.raises(ArgumentError):
        c.run("log(1,2,3)")
    with pytest.raises(ArgumentError):
        c.run("Pol(1)")


def test_dimension_errors(c):
    c.set_mode("MATRIX")
    with pytest.raises(DimensionError):
        c.run("MatA")                        # undefined
    c.mats["MatA"] = c.run("[[1,2],[3,4]]")[0].value
    c.mats["MatB"] = c.run("[[1,2,3]]")[0].value
    with pytest.raises(DimensionError):
        c.run("MatA+MatB")
    with pytest.raises(DimensionError):
        c.run("MatA*MatB")
    with pytest.raises(MathError):
        c.mats["MatC"] = c.run("[[1,2],[2,4]]")[0].value
        c.run("MatC⁻¹")                     # singular


def test_solve_errors(c):
    with pytest.raises(VariableError):
        c.solve("2+3=5", "x")
    with pytest.raises(CannotSolve):
        c.solve("x^2+1=0", "x", guess=F(1))


def test_range_error_table(c):
    with pytest.raises(RangeError):
        c.table("x", None, F(1), F(100), F(1))     # 100 rows > 45
    with pytest.raises(RangeError):
        c.table("x", "x", F(1), F(31), F(1))       # 31 rows > 30
    with pytest.raises(RangeError):
        c.table("x", None, F(1), F(5), F(-1))


def test_timeout_error(c):
    with pytest.raises((TimeOut, MathError)):
        c.run("integ(1/x,-1,1)")
    with pytest.raises(TimeOut):
        c.run("Sigma(x,1,10000000)")


def test_not_differentiable(c):
    with pytest.raises(MathError):
        c.run("diff(abs(x),0)")


def test_circular_and_memory_errors(c):
    c.set_mode("SHEET")
    sh = c.sheet_data
    sh.set("A1", "=B1")
    sh.set("B1", "=A1")
    with pytest.raises(CircularError):
        sh.value("A1")
    sh.delete_all()
    with pytest.raises(MemoryErr):
        for r in range(1, 46):
            for col in "ABCDE":
                sh.set(f"{col}{r}", "=1+2+3+4+5+6+7+8+9+10+11+12")


def test_base_n_range(c):
    c.set_mode("BASE-N")
    assert ok(c, "2147483647") == 2147483647
    with pytest.raises(MathError):
        c.run("2147483647+1")
    assert ok(c, "-2147483648") == -2147483648
    c.set_base(16)
    assert ok(c, "FFFFFFFF") == -1                 # two's complement
    assert ok(c, "7/2") == 3                       # fractional part cut off
    with pytest.raises(SyntaxErr):
        c.set_base(2)
        c.run("102")


def test_distribution_argument_checks():
    from calc import distributions as d
    with pytest.raises(MathError):
        d.normal_pd(F(0), F(0))
    with pytest.raises(MathError):
        d.binomial_pd(F(3), F(2), F("0.5"))
    with pytest.raises(MathError):
        d.binomial_pd(F(1), F(2), F("1.5"))
    with pytest.raises(MathError):
        d.poisson_pd(F("1.5"), F(2))
    with pytest.raises(MathError):
        d.inverse_normal(F(1))


def test_errors_do_not_change_ans(c):
    c.run("5")
    with pytest.raises(MathError):
        c.run("1/0")
    assert c.ans == 5
