"""Normalization of upstream vocabulary onto the canonical model.

PowerFactory class names and variable codes are recognised here and nowhere else.
Unknown values are *not* guessed: they are mapped to an explicit fallback or
rejected, so the validation stage can report them.
"""

from __future__ import annotations

from gridlens.adapters.base import AdapterError
from gridlens.canonical import ElementType, Variable

#: PowerFactory class names and common spellings -> canonical element type.
_ELEMENT_TYPE_ALIASES: dict[str, ElementType] = {
    "line": ElementType.LINE,
    "elmlne": ElementType.LINE,
    "transformer": ElementType.TRANSFORMER,
    "trafo": ElementType.TRANSFORMER,
    "elmtr2": ElementType.TRANSFORMER,
    "elmtr3": ElementType.TRANSFORMER,
    "busbar": ElementType.BUSBAR,
    "node": ElementType.BUSBAR,
    "terminal": ElementType.BUSBAR,
    "elmterm": ElementType.BUSBAR,
}

#: PowerFactory result variable codes -> canonical variable.
_VARIABLE_ALIASES: dict[str, Variable] = {
    "loading": Variable.LOADING,
    "c:loading": Variable.LOADING,
    "m:loading": Variable.LOADING,
    "voltage": Variable.VOLTAGE,
    "u": Variable.VOLTAGE,
    "m:u": Variable.VOLTAGE,
    "m:u1": Variable.VOLTAGE,
    "voltage_angle": Variable.VOLTAGE_ANGLE,
    "angle": Variable.VOLTAGE_ANGLE,
    "m:phiu": Variable.VOLTAGE_ANGLE,
    "m:phiu1": Variable.VOLTAGE_ANGLE,
}

_UNIT_ALIASES: dict[str, str] = {
    "%": "%",
    "percent": "%",
    "p.u.": "p.u.",
    "pu": "p.u.",
    "deg": "deg",
    "degree": "deg",
    "degrees": "deg",
    "°": "deg",
}


def normalize_element_type(raw: str) -> ElementType:
    """Map an upstream element type onto the canonical vocabulary.

    Unrecognised types become ``OTHER`` rather than an error: an unfamiliar piece
    of equipment is not a data defect, it simply gets no specialised analysis.
    """
    if raw is None:
        raise AdapterError("Element type is missing.")
    return _ELEMENT_TYPE_ALIASES.get(str(raw).strip().lower(), ElementType.OTHER)


def normalize_variable(raw: str) -> Variable:
    """Map an upstream variable code onto the canonical vocabulary.

    Unknown variables are rejected: silently dropping or reinterpreting a
    measured quantity would corrupt every statistic derived from it.
    """
    if raw is None:
        raise AdapterError("Variable name is missing.")

    key = str(raw).strip().lower()
    if key not in _VARIABLE_ALIASES:
        known = ", ".join(sorted(_VARIABLE_ALIASES))
        raise AdapterError(f"Unknown variable '{raw}'. Known variables: {known}.")
    return _VARIABLE_ALIASES[key]


def normalize_unit(raw: str, variable: Variable) -> str:
    """Normalize a unit string, defaulting to the variable's canonical unit."""
    if raw is None or str(raw).strip() == "":
        return variable.canonical_unit
    return _UNIT_ALIASES.get(str(raw).strip().lower(), str(raw).strip())
