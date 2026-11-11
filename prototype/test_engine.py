import pytest

from engine import FormulaError, parse_equation, solve
from storage import FormulaStore

PAR = parse_equation("R = R1*R2/(R1+R2)")


def test_mode1_evaluate():
    assert solve(PAR, "R", {"R1": 100, "R2": 220}).numbers == pytest.approx([68.75])


def test_mode2_rearrange_repeated_variable():
    r = solve(PAR, "R2")
    assert len(r.solutions) == 1
    assert r.missing == ["R", "R1"] or sorted(r.missing) == ["R", "R1"]
    assert any(str(c) in ("R - R1", "-R + R1", "R1 - R") for c in r.conditions)


def test_mode3_rearrange_and_evaluate():
    assert solve(PAR, "R2", {"R": 68.75, "R1": 100}).numbers == pytest.approx([220])


def test_divide_by_zero_flagged():
    r = solve(PAR, "R2", {"R": 100, "R1": 100})
    assert not r.numbers and any("≠ 0" in m for m in r.messages)


def test_power_law_and_two_roots():
    eq = parse_equation("P = I^2 R")
    assert solve(eq, "R", {"P": 100, "I": 2}).numbers == pytest.approx([25])
    assert sorted(solve(eq, "I", {"P": 100, "R": 25}).numbers) == pytest.approx([-2, 2])


def test_numeric_fallback_when_no_symbolic():
    eq = parse_equation("y = x + cos(x)")
    r = solve(eq, "x", {"y": 2})
    assert r.method.startswith("numeric") and r.numbers


def test_bad_input():
    with pytest.raises(FormulaError):
        parse_equation("R1*R2")
    with pytest.raises(FormulaError):
        solve(PAR, "Q")


def test_storage_persists(tmp_path):
    f = tmp_path / "f.json"
    FormulaStore(f).put(1, "Parallel", "R = R1*R2/(R1+R2)")
    assert FormulaStore(f).get(1)["name"] == "Parallel"
