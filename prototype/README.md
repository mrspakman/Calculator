# Desktop prototype (Python + SymPy)

Simulates the calculator workflow before any hardware. SymPy here is the
**reference answer key**, not the final embedded engine.

    pip install -r requirements.txt
    python cli.py        # text menu: list / add / use / delete
    python -m pytest -q  # engine tests

Files: `engine.py` (math), `storage.py` (20 slots, JSON stands in for flash),
`cli.py` (menu), `test_engine.py`.

## What it does
- Mode 1: evaluate a stored formula with entered values.
- Mode 2: "Solve for" any variable → symbolic rearrangement + required conditions.
- Mode 3: rearrange, then evaluate when every other variable has a value.
- Lists missing values instead of guessing; flags divide-by-zero; reports all roots;
  discards complex results; Newton fallback when no rearrangement exists.

## Known limits (prototype)
- Output form is SymPy's, e.g. `-R*R1/(R - R1)` rather than `R*R1/(R1 - R)`.
- Only checks "denominator ≠ 0"; no physical-range checks (e.g. resistance > 0).
- Newton fallback uses a fixed start guess of 1 and returns one root.
