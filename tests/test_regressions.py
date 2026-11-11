"""One test per defect found in review, so each stays fixed."""
from fractions import Fraction as F

import pytest

from calc import equations as eq
from calc.calculator import Calculator
from calc.cli import CLI


def ineq(coeffs, rel):
    c = Calculator()
    return eq.format_inequality(eq.inequality([F(x) for x in coeffs], rel), c.format)


def test_dms_display_does_not_leak_into_later_values():
    c = Calculator()
    c.run("2°20'30\"+1")
    assert c.format(F(1, 2)) == "1/2"
    assert c.run("1/2")[0].text == "1/2"


def test_output_form_does_not_leak():
    c = Calculator()
    c.set_mode("CMPLX")
    c.run("1+i>rθ")
    assert c.run("2+3i")[0].text == "2+3i"


def test_fix_has_no_negative_zero():
    c = Calculator()
    c.setup.number_format, c.setup.fix_digits = "Fix", 3
    assert c.format(F(-1, 10000), True) == "0.000"


@pytest.mark.parametrize("coeffs,rel,expect", [
    ([1, 0, 0], ">", "x<0, 0<x"),                 # must not merge across excluded 0
    ([1, 0, 0], ">=", "All Real Numbers"),
    ([1, 0, 0], "<=", "x=0"),
    ([1, -1, 0, 0], ">=", "x=0, 1≤x"),            # x²(x-1) ≥ 0: isolated point + ray
    ([1, -1, 0, 0], ">", "1<x"),
    ([1, 0, -1], "<=", "-1≤x≤1"),
    ([1, 0, -1], ">", "x<-1, 1<x"),
    ([-1, 0, -1], ">", "No Solution"),
    ([1, 0, -5, 0, 4], "<", "-2<x<-1, 1<x<2"),
])
def test_inequality_segments(coeffs, rel, expect):
    assert ineq(coeffs, rel) == expect


def run_cli(*lines):
    it = iter([*lines, "quit"])
    out = []
    CLI(inp=lambda _prompt: next(it), out=out.append).loop()
    return out


def test_cli_survives_malformed_arguments():
    out = run_cli("simul x", "ineq 9 >", "1+1")
    assert out[-1] == "2"
    assert any(o.startswith(("Input error", "ineq")) for o in out)


def test_cli_eng_and_shift_eng():
    out = run_cli("1234", "eng", "eng", "eng<", "eng<")
    assert out[-4:] == ["1.234×10^3", "1234×10^0", "1.234×10^3", "0.001234×10^6"]


def test_mplus_requires_a_number():
    c = Calculator()
    c.set_mode("VECTOR")
    with pytest.raises(Exception, match="number"):
        c.run("[1,2] M+")


def test_table_row_count_is_exact():
    c = Calculator()
    assert len(c.table("x", None, F(0), F(1), F(1, 10))) == 11     # 0, 0.1 ... 1.0
    assert len(c.table("x", None, F(0), F(1), F(3, 10))) == 4      # 0 .. 0.9


def test_ans_carried_into_and_out_of_base_n():
    c = Calculator()
    c.run("9/2")
    c.set_mode("BASE-N")
    assert c.ans == 4 and c.format(c.ans) == "4"
    c.set_mode("COMP")
    assert c.run("Ans+1/2")[0].text == "9/2"
