"""Data validation.

Every rule produces an explicit, human-readable finding. Nothing is repaired
silently: if the input is inconsistent, the engineer must see it rather than
receive a report built on quietly patched data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from gridlens.canonical import CanonicalDataset, REFERENCE_SCENARIO_ID


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class ValidationCode(str, Enum):
    MISSING_REFERENCE = "MISSING_REFERENCE"
    MULTIPLE_REFERENCES = "MULTIPLE_REFERENCES"
    NO_SCENARIOS = "NO_SCENARIOS"
    MISSING_TIMESTAMPS = "MISSING_TIMESTAMPS"
    INCONSISTENT_TIME_AXIS = "INCONSISTENT_TIME_AXIS"
    MISSING_ELEMENT_ID = "MISSING_ELEMENT_ID"
    DUPLICATE_ELEMENT_ID = "DUPLICATE_ELEMENT_ID"
    MISSING_UNIT = "MISSING_UNIT"
    INCONSISTENT_UNIT = "INCONSISTENT_UNIT"
    NON_FINITE_VALUE = "NON_FINITE_VALUE"
    SCENARIO_WITHOUT_RESULTS = "SCENARIO_WITHOUT_RESULTS"
    DUPLICATE_RESULT_POINT = "DUPLICATE_RESULT_POINT"


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: ValidationCode
    severity: Severity
    message: str

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"[{self.severity.value}] {self.code.value}: {self.message}"


class ValidationError(Exception):
    """Raised when validation finds at least one ERROR level problem."""

    def __init__(self, findings: list[ValidationFinding]) -> None:
        self.findings = findings
        detail = "\n  - ".join(str(f) for f in findings)
        super().__init__(f"Input data failed validation:\n  - {detail}")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    findings: tuple[ValidationFinding, ...]

    @property
    def errors(self) -> tuple[ValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.WARNING)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise ValidationError(list(self.errors))


def validate(dataset: CanonicalDataset) -> ValidationReport:
    """Run every validation rule and return all findings at once."""
    findings: list[ValidationFinding] = []

    findings += _validate_scenarios(dataset)
    findings += _validate_elements(dataset)
    findings += _validate_time_axis(dataset)
    findings += _validate_values(dataset)
    findings += _validate_units(dataset)
    findings += _validate_coverage(dataset)

    return ValidationReport(tuple(findings))


def _error(code: ValidationCode, message: str) -> ValidationFinding:
    return ValidationFinding(code, Severity.ERROR, message)


def _warning(code: ValidationCode, message: str) -> ValidationFinding:
    return ValidationFinding(code, Severity.WARNING, message)


def _validate_scenarios(dataset: CanonicalDataset) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    if not dataset.scenarios:
        findings.append(_error(ValidationCode.NO_SCENARIOS, "No scenarios were supplied."))
        return findings

    references = [s for s in dataset.scenarios if s.is_reference]
    if not references:
        findings.append(
            _error(
                ValidationCode.MISSING_REFERENCE,
                f"No scenario is flagged as reference (expected exactly one, "
                f"conventionally '{REFERENCE_SCENARIO_ID}').",
            )
        )
    elif len(references) > 1:
        names = ", ".join(s.scenario_id for s in references)
        findings.append(
            _error(
                ValidationCode.MULTIPLE_REFERENCES,
                f"{len(references)} scenarios are flagged as reference: {names}. "
                "Exactly one is required.",
            )
        )

    seen: set[str] = set()
    for scenario in dataset.scenarios:
        if scenario.scenario_id in seen:
            findings.append(
                _error(
                    ValidationCode.DUPLICATE_ELEMENT_ID,
                    f"Scenario id '{scenario.scenario_id}' appears more than once.",
                )
            )
        seen.add(scenario.scenario_id)

    return findings


def _validate_elements(dataset: CanonicalDataset) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    missing = [p for p in dataset.results if not p.element_id]
    if missing:
        findings.append(
            _error(
                ValidationCode.MISSING_ELEMENT_ID,
                f"{len(missing)} result point(s) have no element_id.",
            )
        )

    # One element_id must describe one element. Conflicting names or types mean
    # two different pieces of equipment share an id.
    identity: dict[str, tuple[str, str]] = {}
    conflicts: set[str] = set()
    for point in dataset.results:
        if not point.element_id:
            continue
        current = (point.element_name, point.element_type.value)
        previous = identity.setdefault(point.element_id, current)
        if previous != current:
            conflicts.add(point.element_id)

    for element_id in sorted(conflicts):
        findings.append(
            _error(
                ValidationCode.DUPLICATE_ELEMENT_ID,
                f"element_id '{element_id}' is used for more than one element "
                "(name or type differ between rows).",
            )
        )

    # The same measurement must not be delivered twice.
    keys: set[tuple[str, str, str, str]] = set()
    duplicates: set[tuple[str, str, str, str]] = set()
    for point in dataset.results:
        key = (point.scenario_id, point.timestamp, point.element_id, point.variable.value)
        if key in keys:
            duplicates.add(key)
        keys.add(key)

    for scenario_id, timestamp, element_id, variable in sorted(duplicates):
        findings.append(
            _error(
                ValidationCode.DUPLICATE_RESULT_POINT,
                f"Duplicate result for scenario '{scenario_id}', element "
                f"'{element_id}', variable '{variable}' at {timestamp}.",
            )
        )

    return findings


def _validate_time_axis(dataset: CanonicalDataset) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    if not dataset.results:
        return findings

    missing = [p for p in dataset.results if not p.timestamp]
    if missing:
        findings.append(
            _error(
                ValidationCode.MISSING_TIMESTAMPS,
                f"{len(missing)} result point(s) have no timestamp.",
            )
        )

    per_scenario = {
        scenario_id: {p.timestamp for p in dataset.results if p.scenario_id == scenario_id}
        for scenario_id in {p.scenario_id for p in dataset.results}
    }

    reference = dataset.reference_scenario
    if reference is None or reference.scenario_id not in per_scenario:
        return findings

    reference_axis = per_scenario[reference.scenario_id]
    for scenario_id, axis in sorted(per_scenario.items()):
        if scenario_id == reference.scenario_id:
            continue
        if axis != reference_axis:
            only_ref = len(reference_axis - axis)
            only_scn = len(axis - reference_axis)
            findings.append(
                _warning(
                    ValidationCode.INCONSISTENT_TIME_AXIS,
                    f"Scenario '{scenario_id}' has a different time axis than the "
                    f"reference ({only_ref} timestamp(s) only in reference, "
                    f"{only_scn} only in scenario). Time-aligned differences are "
                    "skipped for this scenario.",
                )
            )

    return findings


def _validate_values(dataset: CanonicalDataset) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    non_finite = [
        p for p in dataset.results if p.value is None or not math.isfinite(p.value)
    ]
    if non_finite:
        sample = non_finite[0]
        findings.append(
            _error(
                ValidationCode.NON_FINITE_VALUE,
                f"{len(non_finite)} result point(s) carry NaN, infinity or null, "
                f"first at scenario '{sample.scenario_id}', element "
                f"'{sample.element_id}', {sample.timestamp}.",
            )
        )

    return findings


def _validate_units(dataset: CanonicalDataset) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    missing = [p for p in dataset.results if not p.unit]
    if missing:
        findings.append(
            _error(
                ValidationCode.MISSING_UNIT,
                f"{len(missing)} result point(s) have no unit.",
            )
        )

    units_per_variable: dict[str, set[str]] = {}
    for point in dataset.results:
        if point.unit:
            units_per_variable.setdefault(point.variable.value, set()).add(point.unit)

    for variable, units in sorted(units_per_variable.items()):
        if len(units) > 1:
            findings.append(
                _error(
                    ValidationCode.INCONSISTENT_UNIT,
                    f"Variable '{variable}' is delivered with mixed units: "
                    f"{', '.join(sorted(units))}.",
                )
            )

    return findings


def _validate_coverage(dataset: CanonicalDataset) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    scenarios_with_results = {p.scenario_id for p in dataset.results}
    for scenario in dataset.scenarios:
        if scenario.scenario_id not in scenarios_with_results:
            findings.append(
                _error(
                    ValidationCode.SCENARIO_WITHOUT_RESULTS,
                    f"Scenario '{scenario.scenario_id}' ({scenario.scenario_name}) "
                    "has no result data at all.",
                )
            )

    known = {s.scenario_id for s in dataset.scenarios}
    for scenario_id in sorted(scenarios_with_results - known):
        findings.append(
            _warning(
                ValidationCode.NO_SCENARIOS,
                f"Results reference scenario '{scenario_id}', which is not defined "
                "in the scenario metadata.",
            )
        )

    return findings
