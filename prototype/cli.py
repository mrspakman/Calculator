"""Text-menu simulation of the calculator workflow.  Run: python cli.py"""
from pathlib import Path

from engine import FormulaError, format_result, parse_equation, solve, variables
from storage import FormulaStore

store = FormulaStore(Path(__file__).with_name("formulas.json"))
last_values: dict[str, float] = {}  # remembered between runs, like a calculator


def show_list():
    for i, s in enumerate(store.slots, 1):
        if s:
            print(f"F{i:<2} {s['name']:<14} {s['formula']}")
    if all(s is None for s in store.slots):
        print("(no formulas stored)")


def ask_slot(prompt="Slot #: ") -> int:
    return int(input(prompt).strip().lstrip("Ff"))


def add_or_edit():
    default = store.first_free()
    raw = input(f"Slot # [{default}]: ").strip().lstrip("Ff")
    slot = int(raw) if raw else default
    name = input("Name: ").strip() or f"F{slot}"
    text = input("Formula (e.g. R = R1*R2/(R1+R2)): ")
    store.put(slot, name, text)
    print(f"Saved F{slot}.")


def use():
    slot = ask_slot()
    entry = store.get(slot)
    if not entry:
        print("Empty slot.")
        return
    eq = parse_equation(entry["formula"])
    names = variables(eq)
    print(f"F{slot}: {entry['formula']}   variables: {', '.join(names)}")
    target = input("Solve for: ").strip()
    values = {}
    print("Enter values (blank = leave symbolic, '.' = reuse last)")
    for n in names:
        if n == target:
            continue
        hint = f" [{last_values[n]:g}]" if n in last_values else ""
        raw = input(f"  {n}?{hint} ").strip()
        if raw == "." and n in last_values:
            values[n] = last_values[n]
        elif raw:
            values[n] = float(raw)
    last_values.update(values)
    print(format_result(solve(eq, target, values)))


MENU = {"1": ("List", show_list), "2": ("Add / replace", add_or_edit),
        "3": ("Use formula", use),
        "4": ("Delete", lambda: (store.delete(ask_slot()), print("Deleted.")))}


def main():
    while True:
        print("\n" + "  ".join(f"{k}){v[0]}" for k, v in MENU.items()) + "  q)Quit")
        choice = input("> ").strip().lower()
        if choice == "q":
            return
        try:
            MENU[choice][1]()
        except (FormulaError, IndexError, ValueError, KeyError) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
