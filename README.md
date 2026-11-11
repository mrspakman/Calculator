# Formula Calculator: desktop simulation

Software-first prototype of a handheld calculator with the fx-991EX function set
**plus** 20 stored formulas with symbolic "Solve for" rearrangement.
Goals and decisions: [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md). Feature checklist:
[`docs/FEATURES.md`](docs/FEATURES.md). Numerical design and known differences:
[`docs/NUMERICS.md`](docs/NUMERICS.md).

## Run

    pip install -e ".[test]"
    python -m calc            # interactive text calculator; type 'help'
    python -m pytest -q       # verification tests
    ruff check calc tests     # lint (rules in pyproject.toml)

## Typing expressions (one-line input)

| Want | Type |
|---|---|
| ×, ÷, implicit × | `*` `/`, `2sin(30)`, `2(1+3)` (implicit × binds tighter than ÷, as on the real device) |
| powers / roots | `x^2` `x²` `x³` `x⁻¹` `sqrt(2)` `√2` `cbrt(8)` `root(5,32)` |
| scientific notation | `1.5E-3` |
| engineering symbols | `500k` `2.2u` `10M` (m u n p f k M G T P E, directly after a number) |
| DMS / angle units | `2°20'30"`, `90°`, `(pi/2)rad`, `100gra` |
| constants | `pi` `e` and 47 physical constants as `#c0`, `#h`, `#NA` … (`const` lists them) |
| conversions | `5cm>in`, `100C>F`, `1atm>Pa` (`conv` lists them) |
| functions | `sin cos tan asin acos atan sinh … log(x) log(a,b) ln exp abs Pol Rec Rnd nPr nCr Ran# RanInt#(a,b)` |
| calculus | `integ(ln(x),1,e)`  `diff(sin(x),pi/2)`  `Sigma(x+1,1,5)` (variable is always x) |
| memories | `3+5->A`, `Ans`, `10*5 M+`, variables `A–F M x y` |
| decimal result (≈) | prefix with `~`, or `sd` to toggle the last result |
| complex (mode CMPLX) | `(1+i)^4`, `2∠45` (or `2@45`), `conj( Arg( ReP( ImP(`, `>rθ` `>a+bi` |
| base-n (mode BASE-N) | `dec hex bin oct`, `d10+h10+b10+o10`, `and or xor xnor Not( Neg(` |
| matrices / vectors | `mat A [[2,1],[1,1]]`, `MatA⁻¹`, `Det( Trn( Identity(`; `vct A [1,2]`, `VctA•VctB`, `Angle( UnitV(` |

Stored formulas: `f save 1 Parallel : R = R1*R2/(R1+R2)`, then `f use 1` → choose
"Solve for" → enter known values (blank = keep symbolic).

## Layout

    calc/            the calculator (Python; reference model for the C firmware)
      scalars.py     number model: exact fractions + 34-digit floats, range checks
      parser.py      tokenizer + operator-priority parser (manual pp.8-9)
      functions.py   math functions with the manual's input ranges
      display.py     Norm/Fix/Sci/ENG, fractions, √ and π forms
      calculator.py  modes, memories, CALC, SOLVE, ∫, d/dx, Σ, table
      linalg.py stats.py distributions.py equations.py spreadsheet.py
      constants.py conversions.py formulas.py formula_store.py cli.py
    tests/           manual examples, independent-reference tests, range edges,
                     and one regression test per defect found in review

`cli.py` is the only file that does input/output. Everything else is pure
computation, so the interface can be replaced without touching the math.
