"""47 scientific constants, CODATA 2022 (the reference manual used CODATA 2010).
Exactly defined SI constants are computed from their definitions at full precision.
Values verified against scipy.constants in tests/test_constants.py."""
import mpmath as mp

h = mp.mpf("6.62607015e-34")
e = mp.mpf("1.602176634e-19")
k = mp.mpf("1.380649e-23")
NA = mp.mpf("6.02214076e23")
c0 = mp.mpf(299792458)

# (menu category, key, display name, value, unit)
CONSTANTS = [
    ("Universal", "h", "h", h, "J s"),
    ("Universal", "hbar", "ħ", h / (2 * mp.pi), "J s"),
    ("Universal", "c0", "c₀", c0, "m/s"),
    ("Universal", "eps0", "ε₀", mp.mpf("8.8541878188e-12"), "F/m"),
    ("Universal", "mu0", "μ₀", mp.mpf("1.25663706127e-6"), "N/A²"),
    ("Universal", "Z0", "Z₀", mp.mpf("376.730313412"), "Ω"),
    ("Universal", "G", "G", mp.mpf("6.67430e-11"), "m³/(kg s²)"),
    ("Universal", "lP", "lP", mp.mpf("1.616255e-35"), "m"),
    ("Universal", "tP", "tP", mp.mpf("5.391247e-44"), "s"),
    ("Electromagnetic", "muN", "μN", mp.mpf("5.0507837393e-27"), "J/T"),
    ("Electromagnetic", "muB", "μB", mp.mpf("9.2740100657e-24"), "J/T"),
    ("Electromagnetic", "e", "e", e, "C"),
    ("Electromagnetic", "Phi0", "Φ₀", h / (2 * e), "Wb"),
    ("Electromagnetic", "G0", "G₀", 2 * e * e / h, "S"),
    ("Electromagnetic", "KJ", "KJ", 2 * e / h, "Hz/V"),
    ("Electromagnetic", "RK", "RK", h / (e * e), "Ω"),
    ("Atomic&Nuclear", "mp", "mp", mp.mpf("1.67262192595e-27"), "kg"),
    ("Atomic&Nuclear", "mn", "mn", mp.mpf("1.67492750056e-27"), "kg"),
    ("Atomic&Nuclear", "me", "me", mp.mpf("9.1093837139e-31"), "kg"),
    ("Atomic&Nuclear", "mmu", "mμ", mp.mpf("1.883531627e-28"), "kg"),
    ("Atomic&Nuclear", "a0", "a₀", mp.mpf("5.29177210544e-11"), "m"),
    ("Atomic&Nuclear", "alpha", "α", mp.mpf("7.2973525643e-3"), ""),
    ("Atomic&Nuclear", "re", "re", mp.mpf("2.8179403205e-15"), "m"),
    ("Atomic&Nuclear", "lambdaC", "λC", mp.mpf("2.42631023538e-12"), "m"),
    ("Atomic&Nuclear", "gammap", "γp", mp.mpf("2.6752218708e8"), "1/(s T)"),
    ("Atomic&Nuclear", "lambdaCp", "λCp", mp.mpf("1.3214098536e-15"), "m"),
    ("Atomic&Nuclear", "lambdaCn", "λCn", mp.mpf("1.31959090382e-15"), "m"),
    ("Atomic&Nuclear", "Rinf", "R∞", mp.mpf("10973731.568157"), "1/m"),
    ("Atomic&Nuclear", "mup", "μp", mp.mpf("1.41060679545e-26"), "J/T"),
    ("Atomic&Nuclear", "mue", "μe", mp.mpf("-9.2847646917e-24"), "J/T"),
    ("Atomic&Nuclear", "mun", "μn", mp.mpf("-9.6623653e-27"), "J/T"),
    ("Atomic&Nuclear", "mumu", "μμ", mp.mpf("-4.4904483e-26"), "J/T"),
    ("Atomic&Nuclear", "mtau", "mτ", mp.mpf("3.16754e-27"), "kg"),
    ("Physico-Chem", "u", "u", mp.mpf("1.66053906892e-27"), "kg"),
    ("Physico-Chem", "F", "F", e * NA, "C/mol"),
    ("Physico-Chem", "NA", "NA", NA, "1/mol"),
    ("Physico-Chem", "k", "k", k, "J/K"),
    ("Physico-Chem", "Vm", "Vm", k * NA * mp.mpf("273.15") / 101325, "m³/mol (273.15 K, 101.325 kPa)"),
    ("Physico-Chem", "R", "R", k * NA, "J/(mol K)"),
    ("Physico-Chem", "c1", "c₁", 2 * mp.pi * h * c0 ** 2, "W m²"),
    ("Physico-Chem", "c2", "c₂", h * c0 / k, "m K"),
    ("Physico-Chem", "sigma", "σ", 2 * mp.pi ** 5 * k ** 4 / (15 * h ** 3 * c0 ** 2), "W/(m² K⁴)"),
    ("Adopted Values", "g", "g", mp.mpf("9.80665"), "m/s²"),
    ("Adopted Values", "atm", "atm", mp.mpf(101325), "Pa"),
    ("Adopted Values", "RK90", "RK-90", mp.mpf("25812.807"), "Ω"),
    ("Adopted Values", "KJ90", "KJ-90", mp.mpf("483597.9e9"), "Hz/V"),
    ("Other", "t", "t", mp.mpf("273.15"), "K"),
]

BY_KEY = {key: (name, value, unit) for _, key, name, value, unit in CONSTANTS}
assert len(CONSTANTS) == 47
