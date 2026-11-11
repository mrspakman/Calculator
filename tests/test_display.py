from fractions import Fraction as F

import mpmath as mp

from calc.display import Setup, exact_form, format_decimal, format_real


def fmt(x, **kw):
    s = Setup(**kw)
    return format_decimal(x, s)


def test_norm1_thresholds():
    assert fmt(F(1, 100)) == "0.01"
    assert fmt(F(99, 10000)) == "9.9×10^-3"
    assert fmt(F(9999999999)) == "9999999999"
    assert fmt(F(10 ** 10)) == "1×10^10"
    assert fmt(F(99999999995, 10)) == "1×10^10"     # rounds up into sci


def test_norm2_thresholds():
    assert fmt(F(1, 10 ** 9), number_format="Norm2") == "0.000000001"
    assert fmt(F(1, 10 ** 10), number_format="Norm2") == "1×10^-10"


def test_ten_digit_half_up_rounding():
    assert fmt(F(2, 3)) == "0.6666666667"
    assert fmt(F("1.23456789045")) == "1.23456789"   # 10 sig digits: ...890|45 -> ...890
    assert fmt(F("1.23456789050")) == "1.234567891"  # half rounds up
    assert fmt(F("-1.23456789050")) == "-1.234567891"


def test_fix_and_sci():
    assert fmt(F(100, 7), number_format="Fix", fix_digits=3) == "14.286"
    assert fmt(F(0), number_format="Fix", fix_digits=2) == "0.00"
    assert fmt(F(1, 7), number_format="Sci", sci_digits=5) == "1.4286×10^-1"
    assert fmt(F(1), number_format="Sci", sci_digits=3) == "1.00×10^0"


def test_separators():
    assert fmt(F(1234567), digit_separator=True) == "1,234,567"
    assert fmt(F("1234.5"), decimal_mark=",") == "1234,5"


def test_exact_forms():
    assert exact_form(mp.pi / 6) == "π/6"
    assert exact_form(-2 * mp.pi / 3) == "-2π/3"
    assert exact_form(mp.sqrt(2) / 2) == "√2/2"
    assert exact_form(3 * mp.sqrt(2)) == "3√2"
    assert exact_form(mp.mpf(2)) is None                # rational is not a surd
    assert exact_form(mp.e) is None
    assert exact_form(mp.mpf("1.4142135623")) is None   # close to √2 but not equal


def test_fraction_display_limits():
    s = Setup()
    assert format_real(F(22, 15), s) == "22/15"
    assert format_real(F(1, 12345678901), s) != "1/12345678901"   # > 10 digits -> decimal
