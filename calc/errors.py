"""Calculator error types (names follow the reference manual's error list)."""


class CalcError(Exception):
    name = "ERROR"

    def __init__(self, detail: str = ""):
        super().__init__(detail)
        self.detail = detail

    def __str__(self):
        return f"{self.name}: {self.detail}" if self.detail else self.name


class MathError(CalcError):
    name = "Math ERROR"        # out of range, illegal operation (e.g. ÷0)


class StackError(CalcError):
    name = "Stack ERROR"       # expression nested too deeply


class SyntaxErr(CalcError):
    name = "Syntax ERROR"


class ArgumentError(CalcError):
    name = "Argument ERROR"


class DimensionError(CalcError):
    name = "Dimension ERROR"


class VariableError(CalcError):
    name = "Variable ERROR"


class CannotSolve(CalcError):
    name = "Cannot Solve"


class RangeError(CalcError):
    name = "Range ERROR"


class TimeOut(CalcError):
    name = "Time Out"


class CircularError(CalcError):
    name = "Circular ERROR"


class MemoryErr(CalcError):
    name = "Memory ERROR"
