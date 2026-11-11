"""Our own feature: stored formulas with symbolic rearrangement (Phase 0)."""
import pytest

from calc.formula_store import FormulaStore
from calc.formulas import FormulaError, parse_equation, solve

PAR = parse_equation("R = R1*R2/(R1+R2)")


def test_evaluate():
    assert solve(PAR, "R", {"R1": 100, "R2": 220}).numbers == pytest.approx([68.75])


def test_rearrange_repeated_variable():
    r = solve(PAR, "R2")
    assert len(r.solutions) == 1 and sorted(r.missing) == ["R", "R1"]


def test_rearrange_and_evaluate():
    assert solve(PAR, "R2", {"R": 68.75, "R1": 100}).numbers == pytest.approx([220])


def test_divide_by_zero_flagged():
    r = solve(PAR, "R2", {"R": 100, "R1": 100})
    assert not r.numbers and any("≠ 0" in m for m in r.messages)


def test_two_roots():
    eq = parse_equation("P = I^2 R")
    assert solve(eq, "R", {"P": 100, "I": 2}).numbers == pytest.approx([25])
    assert sorted(solve(eq, "I", {"P": 100, "R": 25}).numbers) == pytest.approx([-2, 2])


def test_numeric_fallback():
    r = solve(parse_equation("y = x + cos(x)"), "x", {"y": 2})
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
    with pytest.raises(IndexError):
        FormulaStore(f).put(21, "x", "a = b")
