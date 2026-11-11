# Feature Inventory (from the fx-991EX User's Guide, RJA532432-001V01)

Source: owner-supplied user manual. This is our *functional* spec: same math
capabilities, our own design and UI. Status: ☐ not started · ◐ prototype · ☑ verified.

Phase numbers are a **proposal**, not yet agreed.

**Status 2026-11-11:** all phases 0-4 are implemented in the desktop simulation (`calc/`)
and covered by tests (◐ = implemented and tested in the simulation; ☑ will mean
verified on the target hardware). Exceptions: natural textbook display (UI stage) and QR (dropped).

## Reference numbers from the manual (confirmed, Casio's published specs)
- Calculation range: ±1×10⁻⁹⁹ to ±9.999999999×10⁹⁹, or 0
- Internal digits: 15. Display precision: ±1 at the 10th digit (single calc); errors accumulate.
- Power: solar cell + LR44 ×1. Battery life ≈ 2 years at 1 h/day. (fx-570EX, AAA only: 0.0006 W.)
- Auto power-off ≈ 10 min. Size 11.1 × 77 × 165.5 mm, 90 g with battery.
- Removing the battery clears memory on the Casio (ours must NOT lose the 20 formulas).
- Per-function input ranges: manual pp. 40–41 → becomes our range-check test table.

## Phase 0 — Our own features (already started)
- ◐ 20 stored formulas: name / edit / replace / recall / persist
- ◐ Solve-for any variable: symbolic rearrangement
- ◐ Evaluate with known values; Newton fallback

## Phase 1 — Core calculator (Calculate mode)
- ◐ Arithmetic with documented operator priority (manual p. 8–9, 13 levels)
- ◐ Fractions (proper/mixed, reduced), S⇔D toggle, exact √ and π forms
- ◐ %, degrees-minutes-seconds, engineering notation (ENG), engineering symbols (m µ n p f k M G T P E)
- ◐ sin/cos/tan + inverses (Deg/Rad/Grad), sinh…tanh⁻¹, angle-unit conversion
- ◐ 10^x, e^x, log, log_a(b), ln, x², x³, x^y, √, ∛, ˣ√y, x⁻¹, x!, Abs
- ◐ Pol/Rec, nPr, nCr, Ran#, RanInt#, Rnd
- ◐ Prime factorization (≤ 10 digits)
- ◐ Numerical ∫ (Gauss-Kronrod, tol), d/dx at a point (central difference), Σ
- ◐ Ans, variables A–F, x, y, M (M+, M−), multi-statements (:), history/replay
- ◐ Setup: Fix/Sci/Norm1/Norm2, angle unit, fraction format, decimal mark, digit separator
- ◐ CALC (prompt for variables) and SOLVE (Newton, initial guess, L−R residual)
- ◐ Error types: Math, Stack, Syntax, Argument, Dimension, Variable, Cannot Solve, Range, Time Out

## Phase 2 — Engineering-heavy modes
- ◐ Complex: a+bi and r∠θ, conjugate, abs, arg, Re, Im, ▶r∠θ / ▶a+bi
- ◐ Equation: simultaneous linear 2–4 unknowns; polynomial degree 2–4 (incl. complex roots, quadratic min/max)
- ◐ Matrix: up to 4×4, MatA–D, MatAns, +, −, ×, det, transpose, inverse, identity, x², x³, Abs
- ◐ Vector: 2D/3D, VctA–D, VctAns, dot, cross, abs, angle, unit vector
- ◐ Base-N: DEC/HEX/BIN/OCT, 32-bit two's complement, and/or/xor/xnor/Not/Neg
- ◐ Scientific constants (47, CODATA — we should use current CODATA, not 2010)
- ◐ Unit conversions (manual p. 44 list; NIST SP 811)

## Phase 3 — Statistics and data
- ◐ Statistics: 1-var and 8 regression types, Freq column, Σ terms, mean, σ, s, min/max, quartiles, r, estimates x̂ ŷ
- ◐ Normal-distribution P(t), Q(t), R(t), ▶t
- ◐ Distribution: Normal PD/CD/inverse, Binomial PD/CD, Poisson PD/CD, list input
- ◐ Table: f(x), g(x), start/end/step, row limits (45 / 30)
- ◐ Inequality: degree 2–4 polynomial inequalities
- ◐ Ratio: A:B = X:D and A:B = C:X

## Phase 4 — Large / questionable value
- ◐ Spreadsheet: 5 × 45 cells, relative/absolute refs, Min/Max/Mean/Sum, fill, copy/cut, recalculation, 1,700-byte limit
- ✗ QR code: links to the manufacturer's website. **Proposed: drop** (no equivalent service for us).
- ☐ Natural textbook display (2-D fractions, ∫ templates): depends on the display; belongs to the screen/UI stage

## Verification approach (proposed)
Every function gets automated tests that compare against an **independent**
high-precision reference (mpmath at 50 digits), not against our own code:
1. Every worked example in the manual becomes a test case.
2. Input-range edges from manual pp. 40–41 (just inside → result; just outside → correct error).
3. Randomized inputs compared to the reference at ≥ 10 correct significant digits.
4. Known-hard cases: near-singular points, cancellation, huge/tiny magnitudes.
The same test vectors are reused later against the C firmware.
