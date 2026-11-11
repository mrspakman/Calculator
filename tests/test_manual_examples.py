"""Every worked example in the fx-991EX User's Guide, by page."""
from fractions import Fraction as F

import pytest

from calc import equations as eq
from calc.calculator import Calculator
from calc.cli import CLI


@pytest.fixture
def c():
    return Calculator(seed=1)


def run(c, text, decimal=False):
    return c.run(text, decimal=decimal)[-1].text


# p.5-6 input/output formats
def test_p6_formats(c):
    assert run(c, "4/5+2/3") == "22/15"
    assert run(c, "4/5+2/3", decimal=True) == "1.466666667"
    assert run(c, "(1+sqrt(2))/sqrt(2)", decimal=True) == "1.707106781"


def test_p6_p7_number_format(c):
    c.setup.number_format, c.setup.fix_digits = "Fix", 3
    assert run(c, "100/7", True) == "14.286"
    c.setup.number_format, c.setup.sci_digits = "Sci", 5
    assert run(c, "1/7", True) == "1.4286×10^-1"
    c.setup.number_format = "Norm1"
    assert run(c, "1/200", True) == "5×10^-3"
    c.setup.number_format = "Norm2"
    assert run(c, "1/200", True) == "0.005"


# p.8-9 input rules and priority
def test_p8_priority(c):
    assert run(c, "4*sin(30)*(30+10*3)") == "120"
    assert run(c, "4sin(30)(30+10*3)") == "120"
    assert run(c, "6/2(1+2)") == "1"            # implicit × binds tighter than ÷
    assert run(c, "2/2sqrt(2)", True) == run(c, "2/(2sqrt(2))", True)
    assert run(c, "-2^2") == "-4"
    assert run(c, "(-2)^2") == "4"
    assert run(c, "sin(30)+15") == "31/2"


# p.10 toggling and fractions
def test_p10(c):
    assert run(c, "pi/6") == "π/6"
    assert run(c, "pi/6", True) == "0.5235987756"
    assert run(c, "(sqrt(2)+2)*sqrt(3)", True) == "5.913591358"
    assert run(c, "2/3+1+1/2") == "13/6"
    c.setup.fraction = "ab/c"
    assert run(c, "2/3+1+1/2") == "2 1/6"


# p.11 percent, DMS, multi-statements, ENG
def test_p11(c):
    assert run(c, "150*20%") == "30"
    assert run(c, "660/880%") == "75"
    assert run(c, "3500-3500*25%") == "2625"
    assert run(c, "2°20'30\"+0°9'30\"") == "2°30'0\""
    outs = c.run("3+3:3*3")
    assert [o.text for o in outs] == ["6", "9"]
    from calc.display import format_eng
    assert format_eng(F(1234), c.setup, 0) == "1.234×10^3"
    assert format_eng(F(1234), c.setup, 1) == "1234×10^0"
    assert format_eng(F(1234), c.setup, -1) == "0.001234×10^6"


# p.12 engineering symbols, prime factorisation, history
def test_p12(c):
    assert run(c, "500k") == "500000"
    c.setup.eng_symbol = True
    assert run(c, "999k+25k") == "1.024M"
    from calc.functions import prime_factors
    assert prime_factors(F(1014)) == [(2, 1), (3, 1), (13, 2)]


# p.13 memories
def test_p13_memory(c):
    c.run("14*13")
    assert run(c, "Ans/7") == "26"
    c.run("123+456")
    assert run(c, "789-Ans") == "210"
    c.run("3+5->A")
    assert run(c, "A*10") == "80"
    c.run("0->M")
    c.run("10*5 M+")
    c.run("10+5 M-")
    assert run(c, "M") == "35"


# p.14-16 functions
def test_p14_functions(c):
    assert run(c, "sin(30)") == "1/2"
    assert run(c, "(pi/2)rad") == "90"
    assert run(c, "e^(5)*2", True) == "296.8263182"
    assert run(c, "log(1000)") == "3"
    assert run(c, "log(2,16)") == "4"
    assert run(c, "ln(90)", True) == "4.49980967"
    assert run(c, "(1+1)^(2+2)") == "16"
    assert run(c, "(5^2)^3") == "15625"
    assert run(c, "root(5,32)") == "2"
    assert run(c, "sqrt(2)*3") == "3√2"
    assert run(c, "sqrt(2)*3", True) == "4.242640687"


def test_p15_calculus(c):
    assert run(c, "integ(ln(x),1,e)") == "1"
    c.setup.angle = "Rad"
    assert run(c, "diff(sin(x),pi/2)") == "0"
    c.setup.angle = "Deg"
    assert run(c, "Sigma(x+1,1,5)") == "20"


def test_p16(c):
    assert run(c, "Pol(sqrt(2),sqrt(2))") == "r=2, θ=45"
    assert run(c, "Rec(sqrt(2),45)") == "x=1, y=1"
    assert run(c, "(5+3)!") == "40320"
    assert run(c, "abs(2-7)*2") == "10"
    assert run(c, "10nPr4") == "5040"
    assert run(c, "10nCr4") == "210"
    c.setup.number_format, c.setup.fix_digits, c.setup.io = "Fix", 3, "DecimalO"
    assert run(c, "10/3*3") == "10.000"
    assert run(c, "Rnd(10/3)*3") == "9.999"


def test_p16_random(c):
    for _ in range(200):
        v = c.run("1000Ran#")[0].value
        assert 0 <= v <= 999 and v.denominator == 1
        r = c.run("RanInt#(1,6)")[0].value
        assert 1 <= r <= 6


# p.18 complex
def test_p18_complex(c):
    c.set_mode("CMPLX")
    assert run(c, "(1+i)^4+(1-i)^2") == "-4-2i"
    assert run(c, "2∠45") == "√2+√2i"
    c.setup.complex_form = "r∠θ"
    assert run(c, "sqrt(2)+sqrt(2)i") == "2∠45"
    c.setup.complex_form = "a+bi"
    assert run(c, "conj(2+3i)") == "2-3i"
    assert run(c, "abs(1+i)") == "√2"
    assert run(c, "Arg(1+i)") == "45"
    assert run(c, "ReP(2+3i)") == "2"
    assert run(c, "ImP(2+3i)") == "3"
    assert run(c, "sqrt(2)+sqrt(2)i>rθ") == "2∠45"
    assert run(c, "2∠45>a+bi") == "√2+√2i"


# p.18-20 CALC and SOLVE
def test_p19_calc_solve(c):
    assert c.calc("3A+B", {"A": F(5), "B": F(10)})[-1].text == "25"
    root, resid = c.solve("x^2+B=0", "x", guess=1, values={"B": F(-2)})
    assert c.format(root, True) == "1.414213562"
    assert resid == 0


# p.20-23 statistics
def test_p20_ex1_log_regression(c):
    c.set_mode("STAT")
    c.stats.set_type("a+bln")
    for x, y in [(170, 66), (173, 68), (179, 75)]:
        c.stats.add(F(x), F(y))
    assert run(c, "a", True) == "-852.1627746"
    assert run(c, "b", True) == "178.6897969"
    assert run(c, "r", True) == "0.9919863213"


def test_p22_ex2_freq_mean_and_ex5(c):
    c.set_mode("STAT")
    for x, f in [(1, 1), (2, 2), (3, 3), (4, 2), (5, 1)]:
        c.stats.add(F(x), freq=F(f))
    assert run(c, "xbar") == "3"
    assert run(c, "2>t", True) == "-0.8660254038"
    c.setup.sci_digits, c.setup.number_format = 5, "Sci"
    assert run(c, "P(Ans)", True) == "1.9324×10^-1"   # manual: 0.19324


def test_p22_ex3_ex4(c):
    c.set_mode("STAT")
    c.stats.set_type("a+bln")
    for x, y in [(20, 3150), (110, 7310), (200, 8800), (290, 9310)]:
        c.stats.add(F(x), F(y))
    c.setup.number_format, c.setup.fix_digits = "Fix", 3
    assert run(c, "r", True) == "0.998"
    assert run(c, "a", True) == "-3857.984"
    assert run(c, "b", True) == "2357.532"
    assert run(c, "160yhat", True) == "8106.898"


# p.23-24 base-n
def test_p23_base_n(c):
    c.set_mode("BASE-N")
    c.set_base(2)
    assert run(c, "11+1") == "0000 0000 0000 0000 0000 0000 0000 0100"
    c.set_base(10)
    assert run(c, "d10+h10+b10+o10") == "36"
    assert run(c, "15*37") == "555"
    c.set_base(16)
    assert c.format(c.ans) == "0000022B"
    c.set_base(2)
    assert run(c, "1010 and 1100").endswith("1000")
    assert run(c, "Not(1010)") == "1111 1111 1111 1111 1111 1111 1111 0101"


# p.24-25 equations
def test_p25_equations(c):
    r = eq.simultaneous([[F(1), F(2), F(3)], [F(2), F(3), F(4)]])
    assert r.status == "unique" and r.values == [-1, 2]
    roots = eq.polynomial_roots([F(1), F(2), F(-2)])
    assert [str(x) for x in roots] == ["-1+√3", "-1-√3"]
    assert eq.quadratic_extremum(F(1), F(2), F(-2))[:2] == (-1, -3)


# p.25-27 matrices
def test_p26_matrices(c):
    c.set_mode("MATRIX")
    c.mats["MatA"] = c.run("[[2,1],[1,1]]")[0].value
    c.mats["MatB"] = c.run("[[2,-1],[-1,2]]")[0].value
    assert run(c, "MatA*MatB") == "[[3, 0], [1, 1]]"
    c.mats["MatB"] = c.run("[[1,0,-1],[0,-1,1]]")[0].value
    assert run(c, "Det(MatA)") == "1"
    assert run(c, "Identity(2)+MatA") == "[[3, 1], [1, 2]]"
    assert run(c, "Trn(MatB)") == "[[1, 0], [0, -1], [-1, 1]]"
    assert run(c, "MatA⁻¹") == "[[1, -1], [-1, 2]]"
    assert run(c, "MatA²") == "[[5, 3], [3, 2]]"
    assert run(c, "MatA³") == "[[13, 8], [8, 5]]"
    assert run(c, "abs(MatB)") == "[[1, 0, 1], [0, 1, 1]]"


# p.27 table
def test_p27_table(c):
    rows = c.table("x^2+1/2", "x^2-1/2", F(-1), F(1), F(1, 2))
    assert [[c.format(v, True) for v in r] for r in rows] == [
        ["-1", "1.5", "0.5"], ["-0.5", "0.75", "-0.25"], ["0", "0.5", "-0.5"],
        ["0.5", "0.75", "-0.25"], ["1", "1.5", "0.5"]]


# p.28-29 vectors
def test_p29_vectors(c):
    c.set_mode("VECTOR")
    c.vcts["VctA"] = c.run("[1,2]")[0].value
    c.vcts["VctB"] = c.run("[3,4]")[0].value
    c.vcts["VctC"] = c.run("[2,-1,2]")[0].value
    assert run(c, "VctA+VctB") == "[4, 6]"
    assert run(c, "VctA•VctB") == "11"
    assert run(c, "VctA*VctB") == "[0, 0, -2]"
    assert run(c, "abs(VctC)") == "3"
    c.setup.number_format, c.setup.fix_digits = "Fix", 3
    assert run(c, "Angle(VctA,VctB)", True) == "10.305"
    c.setup.number_format = "Norm1"
    assert run(c, "UnitV(VctB)", True) == "[0.6, 0.8]"


# p.29-30 inequality and ratio
def test_p30_inequality(c):
    segs = eq.inequality([F(3), F(3), F(-1), F(0)], ">")
    assert eq.format_inequality(segs, c.format) == "(-3-√21)/6<x<0, (-3+√21)/6<x"
    assert eq.format_inequality(eq.inequality([F(1), F(0), F(0)], ">="), c.format) == "All Real Numbers"
    assert eq.format_inequality(eq.inequality([F(1), F(0), F(0)], "<"), c.format) == "No Solution"


def test_p30_ratio(c):
    assert c.format(eq.ratio(1, F(3), F(8), F(12)), True) == "4.5"
    assert eq.ratio(1, F(1), F(2), F(10)) == 5


# p.31-33 distributions
def test_p32_distributions(c):
    from calc import distributions as d
    assert c.format(d.normal_pd(F(36), F(2), F(35)), True) == "0.1760326634"
    # The manual's list screen TRUNCATES to 4 decimals (0.12677 shows as 0.1267);
    # we round correctly, so compare the truncated digits.
    expect = {10: "0.1859", 11: "0.1267", 12: "0.0633", 13: "0.0219"}
    c.setup.number_format, c.setup.fix_digits = "Fix", 9
    for x, p in expect.items():
        assert c.format(d.binomial_pd(F(x), F(15), F("0.6")), True)[:6] == p


# p.33-36 spreadsheet
def test_p33_spreadsheet(c):
    c.set_mode("SHEET")
    sh = c.sheet_data
    sh.set("A1", "7*5")
    sh.set("A2", "7*6")
    sh.set("A3", "A2+7")
    sh.set("B1", "=A1+7")
    assert sh.grid() == {"A1": "35", "A2": "42", "A3": "49", "B1": "42"}
    sh.set("B2", "=A2+7")
    sh.fill_formula("=2A1-3", "B1:B3")
    assert [sh.cells[r] for r in ("B1", "B2", "B3")] == ["=2A1-3", "=2A2-3", "=2A3-3"]
    sh.fill_value("B1*3", "C1:C3")
    sh.set("A4", "=Sum(A1:A3)")
    g = sh.grid()
    assert [g[r] for r in ("B1", "B2", "B3", "C1", "C2", "C3", "A4")] == \
        ["67", "81", "95", "201", "243", "285", "126"]


def test_p34_relative_absolute_refs(c):
    from calc.spreadsheet import shift_refs
    assert shift_refs("=A1+7", 1, 2) == "=B3+7"
    assert shift_refs("=$A1+A$1+$A$1", 1, 2) == "=$A3+B$1+$A$1"


# p.37 constants and conversions
def test_p37(c):
    assert run(c, "#c0") == "299792458"
    assert run(c, "5cm>in", True) == "1.968503937"


# FAQ p.43
def test_p43_closing_paren(c):
    assert run(c, "sin(30)+15") == "31/2"
    assert run(c, "sin(30+15", True) == "0.7071067812"


def test_cli_scripted_session():
    lines = iter(["poly 2", "1", "2", "-2", "quit"])
    out = []
    cli = CLI(inp=lambda p: next(lines), out=out.append)
    cli.loop()
    assert "  x1= -1+√3" in out and "  x2= -1-√3" in out
