"""Unit conversions (manual p.44).  Factors are exact SI definitions where they exist
(NIST SP 811).  Names are typed as e.g.  5 cm>in   or   100 C>F ."""
from fractions import Fraction as Fr

import mpmath as mp

# key: (category, factor to multiply by) ; temperatures handled separately
_PAIRS = [
    ("Length", "in", "cm", Fr("2.54")),
    ("Length", "ft", "m", Fr("0.3048")),
    ("Length", "yd", "m", Fr("0.9144")),
    ("Length", "mile", "km", Fr("1.609344")),
    ("Length", "nmile", "m", Fr(1852)),
    ("Length", "pc", "km", None),                # 1 pc = 648000/π au, au = 149597870700 m
    ("Area", "acre", "m2", Fr("4046.8564224")),  # international acre
    ("Volume", "galUS", "L", Fr("3.785411784")),
    ("Volume", "galUK", "L", Fr("4.54609")),
    ("Mass", "oz", "g", Fr("28.349523125")),
    ("Mass", "lb", "kg", Fr("0.45359237")),
    ("Velocity", "kmh", "ms", Fr(1, 36) * 10),   # km/h -> m/s = 1/3.6
    ("Pressure", "atm", "Pa", Fr(101325)),
    ("Pressure", "mmHg", "Pa", Fr("133.322387415")),
    ("Pressure", "kgfcm2", "Pa", Fr("98066.5")),
    ("Pressure", "lbfin2", "kPa", Fr("6.894757293168361")),
    ("Energy", "kgfm", "J", Fr("9.80665")),
    ("Energy", "cal", "J", Fr("4.1855")),        # 15 °C calorie, as the manual states
    ("Power", "hp", "kW", Fr("0.74569987158227022")),
]

CONVERSIONS = {}
for cat, a, b, f in _PAIRS:
    if f is None:
        CONVERSIONS[f"{a}>{b}"] = (cat, ("pc", 1))
        CONVERSIONS[f"{b}>{a}"] = (cat, ("pc", -1))
    else:
        CONVERSIONS[f"{a}>{b}"] = (cat, f)
        CONVERSIONS[f"{b}>{a}"] = (cat, 1 / f)
CONVERSIONS["F>C"] = ("Temperature", "F>C")
CONVERSIONS["C>F"] = ("Temperature", "C>F")

PC_KM = mp.mpf(648000) / mp.pi * mp.mpf(149597870700) / 1000


def convert(name, x):
    """x is a calculator scalar; returns new scalar."""
    from .scalars import add, check, div, mul
    cat, f = CONVERSIONS[name]
    if f == "F>C":
        return mul(add(x, Fr(-32)), Fr(5, 9))
    if f == "C>F":
        return add(mul(x, Fr(9, 5)), Fr(32))
    if isinstance(f, tuple):
        return check(mul(x, PC_KM) if f[1] == 1 else div(x, PC_KM))
    return mul(x, f)
