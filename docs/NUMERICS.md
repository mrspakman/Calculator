# Numerical design, verification, and known differences

## Number model
- **Exact rationals** (Python `Fraction`) whenever the operation allows it:
  `0.1+0.2-0.3` is exactly 0, `4/5+2/3` is exactly 22/15. This matches the
  decimal behaviour of a real calculator, unlike binary floating point.
- **34-significant-digit floats** (mpmath) for irrational results. The display
  shows 10 digits, so 24 guard digits absorb rounding error. (The reference device
  uses 15 internal digits.)
- **Cancellation snap:** an add/subtract result below 1e-25 × its operands becomes
  0, e.g. `sqrt(2)^2-2` = 0. Trig at exact multiples of 30°/90° (and π/6, π/2 … in
  Rad) returns exact values; `tan(90°)` is Math ERROR.
- **Range:** |x| ≥ 1e100 → Math ERROR; |x| < 1e-99 → 0 (manual p.40).
- **Rounding:** display rounds half-up at 10 significant digits.

## Verification (`python -m pytest -q`)
1. `tests/test_manual_examples.py`: every worked example in the user's guide.
2. `tests/test_reference.py`: thousands of random inputs compared with
   **independent** code (Python's C math library, cmath, SciPy, NumPy) at 1e-12
   relative tolerance. That is 100× tighter than the 10 displayed digits.
3. `tests/test_ranges_errors.py`: each input-range edge from manual pp.40-41
   (just inside works, just outside gives the documented error), plus every error type.
4. `tests/test_display.py`, `tests/test_formulas.py`.

Testing reduces risk; it does not prove the absence of errors. For safety-critical
values, keep an independent cross-check.

## Deliberate or known differences from the reference manual
| Area | Ours | Why |
|---|---|---|
| Precision | 34 digits internal | more margin; display still 10 digits |
| `2^3^2` | 64 (left to right) | the manual states equal priorities evaluate left to right |
| Binomial list example p.32 | 0.1268, 0.0634 | the manual's screen truncates (0.12678 → 0.1267); we round correctly (checked with SciPy) |
| Constants | CODATA 2022 | the manual uses CODATA 2010 |
| Prime factorisation | no 1,018,081 factor limit | trial division is cheap here |
| Distributions | full precision | the manual quotes 6 significant digits |
| d/dx | Math ERROR when left and right derivatives disagree (e.g. abs at 0) | safer than returning a misleading number |
| ∫ | mpmath tanh-sinh quadrature; Time Out if error estimate > tol × max(1, \|result\|) | the device uses Gauss-Kronrod; the tolerance concept is the same |
| SOLVE | tries secant from the start value, then start+1, then a modified Newton method; no "Continue [=]" prompt | gives the same answer or Cannot Solve |
| Exact display | fractions, k·π/c and single surds a√b/c; equation roots also (p±q√r)/s | sums like √6+2√3 in Calculate mode show as decimals |
| Natural textbook (2-D) display | not implemented | belongs to the screen/UI stage |
| QR code | dropped | it links to the manufacturer's website |
| Engineering symbols | `2M` = 2×10⁶, `2E` = 2×10¹⁸ | for memory M or variable E write `2*M`, `2 E` |
| Quartiles | median of lower/upper half, excluding the median when n is odd | assumed to match the device; not confirmed on hardware |
| Unit factors | exact SI definitions (NIST SP 811); international acre; 15 °C calorie (as the manual states); mechanical hp | factors the manual does not state were chosen from NIST |
| Molar volume Vm | 273.15 K, 101.325 kPa | CODATA also lists a 100 kPa value |
| Root order (EQN) | real roots largest first, then complex | display order only |
