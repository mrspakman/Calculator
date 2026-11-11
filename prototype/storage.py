"""20-slot formula storage, persisted to a JSON file (stands in for flash)."""
import json
from pathlib import Path

from engine import parse_equation

SLOTS = 20


class FormulaStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.slots: list[dict | None] = [None] * SLOTS
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self.slots = (data + [None] * SLOTS)[:SLOTS]

    def _save(self):
        self.path.write_text(json.dumps(self.slots, indent=2))

    def put(self, slot: int, name: str, text: str):
        parse_equation(text)  # reject bad formulas before storing
        self._check(slot)
        self.slots[slot - 1] = {"name": name, "formula": text}
        self._save()

    def get(self, slot: int) -> dict | None:
        self._check(slot)
        return self.slots[slot - 1]

    def delete(self, slot: int):
        self._check(slot)
        self.slots[slot - 1] = None
        self._save()

    def first_free(self) -> int | None:
        return next((i + 1 for i, s in enumerate(self.slots) if s is None), None)

    @staticmethod
    def _check(slot: int):
        if not 1 <= slot <= SLOTS:
            raise IndexError(f"Slot must be 1–{SLOTS}.")
