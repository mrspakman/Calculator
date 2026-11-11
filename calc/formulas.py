"""Stored-formula engine (our own feature): symbolic rearrangement with SymPy.

One job: given a stored equation, a target variable, and any known values,
return the rearranged formula(s), the conditions they require, and a number
when every other variable has a value.
"""
import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor, implicit_multiplication, parse_expr,
    standard_transformations)

_TRANSFORMS = standard_transformations + (implicit_multiplication, convert_xor)
# Names typed by the user that should mean the math constant/function, not a variable.
_LOCALS = {"pi": sp.pi, "e": sp.E, "sqrt": sp.sqrt, "ln": sp.log, "log": sp.log,
           "exp": sp.exp, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
           "asin": sp.asin, "acos": sp.acos, "atan": sp.atan}


class FormulaError(ValueError):
    """Bad input the user should see in plain words."""


def parse_equation(text: str) -> sp.Eq:
    if text.count("=") != 1:
        raise FormulaError("Formula must contain exactly one '='.")
    left, right = text.split("=")
    # Every typed name is a plain variable unless it's a known function/constant.
    # (Stops SymPy treating I as sqrt(-1), E/S/N/Q as built-ins, etc.)
    names = {n: sp.Symbol(n) for n in re.findall(r"[A-Za-z_]\w*", text) if n not in _LOCALS}
    local = {**names, **_LOCALS}
    try:
        lhs = parse_expr(left.strip(), local_dict=dict(local), transformations=_TRANSFORMS)
        rhs = parse_expr(right.strip(), local_dict=dict(local), transformations=_TRANSFORMS)
    except Exception as exc:  # SymPy raises many types for bad syntax
        raise FormulaError(f"Could not read formula: {exc}") from None
    return sp.Eq(lhs, rhs)


def variables(eq: sp.Eq) -> list[str]:
    return sorted(str(s) for s in eq.free_symbols)


@dataclass
class Result:
    target: str
    solutions: list = field(default_factory=list)   # symbolic right-hand sides
    conditions: list = field(default_factory=list)  # expressions that must be != 0
    missing: list = field(default_factory=list)     # unknowns blocking a number
    numbers: list = field(default_factory=list)     # numeric answers
    method: str = "symbolic"                        # "symbolic" or "numeric (Newton)"
    messages: list = field(default_factory=list)    # warnings / errors for the user


def _denominator_conditions(exprs) -> list:
    conds = set()
    for ex in exprs:
        for part in sp.preorder_traversal(ex):
            if isinstance(part, sp.Pow) and part.exp.is_negative:
                conds.add(sp.simplify(part.base))
    return sorted(conds, key=str)


def solve(eq: sp.Eq, target: str, values: dict[str, float] | None = None) -> Result:
    values = values or {}
    sym = {str(s): s for s in eq.free_symbols}
    if target not in sym:
        raise FormulaError(f"'{target}' is not a variable in this formula.")
    t = sym[target]
    res = Result(target=target)

    # 1. Symbolic rearrangement.
    try:
        res.solutions = [sp.simplify(s) for s in sp.solve(eq, t)]
    except NotImplementedError:
        res.solutions = []
    if res.solutions:
        res.conditions = _denominator_conditions([eq.lhs, eq.rhs, *res.solutions])
        if len(res.solutions) > 1:
            res.messages.append(f"{len(res.solutions)} solutions; check which is physical.")
    else:
        res.messages.append("No symbolic rearrangement found.")

    # 2. Numeric answer only if every other variable has a value.
    others = [n for n in sym if n != target]
    res.missing = [n for n in others if n not in values]
    if res.missing:
        return res
    subs = {sym[n]: sp.nsimplify(v) for n, v in values.items() if n in sym}

    for c in res.conditions:
        if c.subs(subs) == 0:
            res.messages.append(f"Invalid: requires {c} ≠ 0.")
            return res

    if res.solutions:
        for s in res.solutions:
            v = sp.N(s.subs(subs))
            if v.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
                res.messages.append("Undefined result (division by zero or similar).")
            elif not v.is_real:
                res.messages.append(f"Complex result {v} discarded (outside real domain).")
            else:
                res.numbers.append(float(v))
    else:
        # 3. Numeric fallback (Newton) when no rearrangement exists.
        res.method = "numeric (Newton)"
        f = (eq.lhs - eq.rhs).subs(subs)
        try:
            res.numbers.append(float(sp.nsolve(f, t, 1)))
        except Exception:
            res.messages.append("Numeric solver did not converge.")
    return res


def format_result(res: Result) -> str:
    lines = [f"{res.target} = {sp.sstr(s)}" for s in res.solutions]
    lines += [f"  requires {c} ≠ 0" for c in res.conditions]
    if res.missing:
        lines.append("Missing values: " + ", ".join(res.missing))
    for n in res.numbers:
        lines.append(f"→ {res.target} = {n:.10g}" + ("" if res.method == "symbolic" else f"  [{res.method}]"))
    lines += res.messages
    return "\n".join(lines)
