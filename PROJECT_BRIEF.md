# Project Brief — Formula-Storing Handheld Calculator

This file is the single source of truth for goals and decisions.
Update it when a decision changes; don't re-ask the owner for anything recorded here.

## Goal

A handheld calculator with roughly the size, weight, and convenience of a Casio
ClassWiz fx-991EX that can **store formulas and rearrange them algebraically**.
Replaceable batteries, very long battery life, no recharging.

**Approach:** prove the software in simulation first. No hardware spend until the
software works and its resource needs are measured.

## Core functional requirements

- Store up to **20 user-defined formulas** (user-entered, not a fixed built-in list).
- Name, edit, replace, recall formulas.
- Formulas persist through power-off and battery replacement (non-volatile storage).
- Detect variables in a formula; user picks "Solve for: ___".
- **Symbolic rearrangement** without needing values for other variables.
  - Example: `P = I^2*R`, solve for R → `R = P/I^2`
- Enter known values → numerical result.
  - Example: P = 100, I = 2 → R = 25
- Simplify expressions.
- Clearly handle: multiple solutions, domain restrictions, invalid input,
  non-convergence, and underdetermined cases (more unknowns than equations).

**Optional / nice to have:** variable descriptions, discipline categories, units.

## Usage modes (priority order)

1. **Evaluate (first mode to build):** recall a stored formula, e.g.
   `R = R1·R2/(R1+R2)`, enter values for the right-hand-side variables, get R.
   No rearrangement needed.
2. **Rearrange:** "Solve for: ___" symbolically (e.g. solve the formula above for R1).
3. **Rearrange + evaluate:** solve for a variable, then enter values.

Owner confirmed that many real formulas repeat a variable (like the parallel-resistor
formula) and some are more complex, so mode 2 needs more than a simple
"undo one operation at a time" engine.

## Additional math (wish list, can be phased)

- Differentiation
- Integration — keep these distinct:
  - **Numerical definite** integration (cheap, likely early)
  - **Symbolic indefinite** integration (expensive, may be phased in later)
- Inverse functions

## Software approach (proposed)

Hybrid engine:
1. Focused symbolic algorithms for rearranging/simplifying *supported* equation types.
2. Direct substitution and evaluation when values are known.
3. Newton's method / other numerical solvers when no analytic solution is available.
4. Numerical integration where appropriate.

Numerical methods **supplement** symbolic rearrangement — they never replace the
requirement to return a rearranged formula.

- Evaluate existing embedded algebra engines **before** writing a CAS from scratch.
- If a restricted engine is used, its supported equation types and limits must be
  written down explicitly.
- Desktop proof of concept: Python + SymPy (reference/oracle).
- Embedded firmware: likely C or C++ (not final). Language alone doesn't set battery life.

## Hardware & energy preferences

- Lightweight plastic handheld enclosure.
- Reflective monochrome display, no power-hungry backlight.
- Physical buttons.
- Small replaceable battery, ideally a coin cell **if measurements show it's practical**.
- Low standby current, keypress wake, auto power-off.
- Final device = custom PCB (not a dev board).
- Choose hardware from **measured** software needs; don't assume a big processor.

## Status of facts — keep these separated

### Confirmed (owner's decisions)
- Software simulation before hardware.
- 20 user formulas, persistent.
- Symbolic rearrangement is mandatory; numeric is supplemental.
- Replaceable batteries, no recharge.
- Owner handles power electronics. Claude helps with software architecture,
  engine selection, firmware, equation entry, storage, display/keypad, programming, debugging.

- The computation code is the deliverable; the UI (CLI/GUI) is temporary and will be discarded.
  The compute core must be extremely lightweight and UI-independent, and still work seamlessly.

### Proposed / candidates (NOT decided)
- CR2450 coin cell.
- STM32U5 dev board for prototyping.
- Sharp reflective Memory LCD.
- C/C++ firmware.

### From the fx-991EX manual (Casio published specs)
- Power is solar cell **+** LR44; ≈ 2 yr battery life at 1 h/day. Solar assist is part of its battery life.
- 15 internal digits; display ±1 at 10th digit; range 1e-99 … 9.999999999e99.
- 11.1 × 77 × 165.5 mm, 90 g. Auto-off ≈ 10 min.

### Untested assumptions (must be measured)
- ClassWiz-like battery life is achievable (target, not spec).
- A coin cell can supply the peak current of the solver.
- Formula storage is small relative to engine code + working RAM (likely, unverified).
- Whether the fx-991EX's own processor class could run this software — **unknown**;
  the fx-991EX has no supported user-programming interface.

## Working style (owner preferences)

- Brainstorm, then execute. Agree on direction before building.
- Keep things simple; keep responses short and digestible (audience: an EE, not a beginner).
- Offer input that improves the project.
- Don't draw conclusions from exploratory questions.

## Roadmap (current)

1. ~~Define minimum software scope~~ (done: modes 1–3, one unknown at a time).
2. ~~Desktop simulation~~ (done: `calc/`, full fx-991EX function set + stored formulas, 123 tests).
2b. Define the remaining parts of OUR calculator (keypad, screen/UI, formula entry flow, units/descriptions) and fold them into the code. ← *we are here*
3. Survey embedded algebra engines; pick candidates.
4. Prototype engine in C/C++ on desktop; measure code size, RAM, run time.
5. Map measurements to MCU/battery candidates; only then buy hardware.

## Decision log

| Date | Decision |
|------|----------|
| 2026-11-11 | Project brief created from owner's initial goals. |
| 2026-11-11 | No built-in formulas; all user-created. |
| 2026-11-11 | First mode to build = evaluate a stored formula with entered values. |
| 2026-11-11 | Repeated-variable formulas are common → rearrangement engine must handle them. |
| 2026-11-11 | Owner wants the full fx-991EX function set added to our build (see docs/FEATURES.md). Phasing and verification approach proposed, awaiting agreement. Device is intended for use with important equipment → correctness verification is a first-class requirement. |
| 2026-11-11 | Built full desktop simulation in Python (`calc/`). Exact rationals + 34-digit floats; QR dropped; known differences listed in docs/NUMERICS.md. |
| 2026-11-11 | Owner: compute core must be extremely lightweight; UI is throwaway, owner keeps the compute code. Current core depends on SymPy (68.6 MB) and mpmath (4.6 MB), so it does not meet this yet. Plan proposed, awaiting agreement. |
| 2026-11-11 | Code-quality pass: lint-clean (ruff), pyproject.toml, 6 defects found and fixed with regression tests; 140 tests pass. C-core plan still awaiting owner decisions. |
| 2026-11-11 | Limitation: solve for one variable at a time. A numeric answer requires every other variable to have a value; otherwise show the symbolic rearrangement and name the missing values. |
