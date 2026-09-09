"""Canonical data model.

Everything entering GridLens is converted into these types as early as possible.
From the processing layer upwards no PowerFactory concept appears any more - only
``ResultPoint``, ``Scenario``, ``Outage`` and ``QaCheck``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ElementType(str, Enum):
    """Canonical equipment classes GridLens distinguishes."""

    LINE = "line"
    TRANSFORMER = "transformer"
    BUSBAR = "busbar"
    OTHER = "other"


class Variable(str, Enum):
    """Canonical measured quantities."""

    LOADING = "loading"
    VOLTAGE = "voltage"
    VOLTAGE_ANGLE = "voltage_angle"

    @property
    def canonical_unit(self) -> str:
        return {
            "loading": "%",
            "voltage": "p.u.",
            "voltage_angle": "deg",
        }[self.value]


#: Reference scenario identifier. Exactly one scenario must carry it.
REFERENCE_SCENARIO_ID = "REF"


@dataclass(frozen=True, slots=True)
class ElementRef:
    """Identity of a piece of equipment, independent of scenario or time."""

    element_id: str
    element_name: str
    element_type: ElementType
    voltage_level: Optional[str] = None
    substation: Optional[str] = None
    area: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ResultPoint:
    """One measured value: study x scenario x time x element x variable."""

    study_id: str
    scenario_id: str
    timestamp: str
    element_id: str
    element_name: str
    element_type: ElementType
    variable: Variable
    value: float
    unit: str
    voltage_level: Optional[str] = None
    substation: Optional[str] = None
    area: Optional[str] = None

    @property
    def element(self) -> ElementRef:
        return ElementRef(
            element_id=self.element_id,
            element_name=self.element_name,
            element_type=self.element_type,
            voltage_level=self.voltage_level,
            substation=self.substation,
            area=self.area,
        )


@dataclass(frozen=True, slots=True)
class Scenario:
    """A scenario as defined upstream. GridLens never creates these."""

    study_id: str
    scenario_id: str
    scenario_name: str
    is_reference: bool
    simulation_start: str
    simulation_end: str
    simulation_status: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class Outage:
    """A switching action belonging to a scenario, as delivered upstream."""

    outage_id: str
    scenario_id: str
    element_id: str
    element_name: str
    element_type: ElementType
    start_time: str
    end_time: str
    action: str


@dataclass(frozen=True, slots=True)
class QaCheck:
    """One upstream QA result. GridLens displays it and does not interpret it."""

    model_id: str
    model_version: str
    check_id: str
    check_name: str
    status: str
    message: str = ""
    affected_element: str = ""


@dataclass(frozen=True, slots=True)
class StudyInfo:
    """Study-level metadata that is not derivable from the result points."""

    study_id: str
    study_name: str
    model_name: str
    model_version: str
    simulation_time_step: str
    study_description: str = ""


@dataclass(slots=True)
class CanonicalDataset:
    """The complete normalized input to the processing layer."""

    study: StudyInfo
    scenarios: list[Scenario] = field(default_factory=list)
    outages: list[Outage] = field(default_factory=list)
    qa_checks: list[QaCheck] = field(default_factory=list)
    results: list[ResultPoint] = field(default_factory=list)

    @property
    def reference_scenario(self) -> Optional[Scenario]:
        """The single reference scenario, or None when it is missing.

        Validation reports the missing/duplicate cases; this accessor stays
        forgiving so validation can produce a full list of findings.
        """
        references = [s for s in self.scenarios if s.is_reference]
        return references[0] if len(references) == 1 else None

    @property
    def scenario_ids(self) -> list[str]:
        return [s.scenario_id for s in self.scenarios]

    def results_for(self, scenario_id: str) -> list[ResultPoint]:
        return [p for p in self.results if p.scenario_id == scenario_id]

    def timestamps(self) -> list[str]:
        return sorted({p.timestamp for p in self.results})
