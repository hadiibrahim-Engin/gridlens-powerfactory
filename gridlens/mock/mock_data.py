"""Synthetic mock dataset.

Clearly artificial by construction: names are prefixed with MOCK-, values are
generated from a fixed formula and the seed is fixed, so the dataset is fully
reproducible and can never be mistaken for measured data.

Covers REF plus S01..S04, several lines, transformers and busbars across two
voltage levels, single and combined outages, and multiple time steps.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridlens.canonical import StudyInfo
from gridlens.adapters.record_adapter import RecordAdapter
from gridlens.canonical import CanonicalDataset

STUDY_ID = "MOCK-STUDY-001"

#: Fixed generation date so a mock build is byte-for-byte reproducible.
FIXED_GENERATION_DATE = "2026-01-01 00:00"

TIME_STEP = "15 min"

#: Eight quarter-hour steps: enough for a meaningful p95 and distinct extremes.
TIMESTAMPS: tuple[str, ...] = (
    "2026-09-15 00:00",
    "2026-09-15 00:15",
    "2026-09-15 00:30",
    "2026-09-15 00:45",
    "2026-09-15 01:00",
    "2026-09-15 01:15",
    "2026-09-15 01:30",
    "2026-09-15 01:45",
)


@dataclass(frozen=True, slots=True)
class MockElement:
    element_id: str
    element_name: str
    element_type: str
    voltage_level: str
    variable: str
    unit: str
    base_value: float
    amplitude: float


LINES: tuple[MockElement, ...] = (
    MockElement("MOCK-LNE-A", "MOCK Leitung A", "ElmLne", "110 kV", "loading", "%", 62.0, 8.0),
    MockElement("MOCK-LNE-B", "MOCK Leitung B", "ElmLne", "110 kV", "loading", "%", 55.0, 6.0),
    MockElement("MOCK-LNE-C", "MOCK Leitung C", "ElmLne", "20 kV", "loading", "%", 48.0, 5.0),
    MockElement("MOCK-LNE-D", "MOCK Leitung D", "ElmLne", "20 kV", "loading", "%", 41.0, 4.0),
)

TRANSFORMERS: tuple[MockElement, ...] = (
    MockElement("MOCK-TR-1", "MOCK Trafo T1", "ElmTr2", "110/20 kV", "loading", "%", 58.0, 7.0),
    MockElement("MOCK-TR-2", "MOCK Trafo T2", "ElmTr2", "110/20 kV", "loading", "%", 51.0, 5.0),
)

BUSBARS: tuple[MockElement, ...] = (
    MockElement("MOCK-BUS-1", "MOCK Sammelschiene 1", "ElmTerm", "110 kV", "voltage", "p.u.", 1.045, 0.008),
    MockElement("MOCK-BUS-2", "MOCK Sammelschiene 2", "ElmTerm", "20 kV", "voltage", "p.u.", 0.995, 0.010),
    MockElement("MOCK-BUS-3", "MOCK Sammelschiene 3", "ElmTerm", "20 kV", "voltage", "p.u.", 0.948, 0.012),
)

VOLTAGE_ANGLES: tuple[MockElement, ...] = (
    MockElement("MOCK-BUS-1", "MOCK Sammelschiene 1", "ElmTerm", "110 kV", "voltage_angle", "deg", -1.0, 1.5),
    MockElement("MOCK-BUS-2", "MOCK Sammelschiene 2", "ElmTerm", "20 kV", "voltage_angle", "deg", -4.0, 2.5),
    MockElement("MOCK-BUS-3", "MOCK Sammelschiene 3", "ElmTerm", "20 kV", "voltage_angle", "deg", -7.0, 3.0),
)

ALL_ELEMENTS: tuple[MockElement, ...] = LINES + TRANSFORMERS + BUSBARS + VOLTAGE_ANGLES


#: scenario_id -> (name, description, switched-off element ids)
SCENARIOS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("REF", "Referenzzustand", "Normalzustand ohne untersuchte Freischaltungen", ()),
    ("S01", "Freischaltung Leitung A", "Einzelfreischaltung", ("MOCK-LNE-A",)),
    ("S02", "Freischaltung Leitung B", "Einzelfreischaltung", ("MOCK-LNE-B",)),
    ("S03", "Leitung A + Leitung B", "Kombination mehrerer Freischaltungen",
     ("MOCK-LNE-A", "MOCK-LNE-B")),
    ("S04", "Leitung A + Trafo T2", "Kombination Leitung und Transformator",
     ("MOCK-LNE-A", "MOCK-TR-2")),
)

QA_CHECKS: tuple[tuple[str, str, str, str, str], ...] = (
    ("LF_CONVERGENCE", "Basis-Lastfluss", "OK", "Lastfluss konvergiert", ""),
    ("TOPOLOGY", "Topologieprüfung", "OK", "Keine unerwarteten Inseln erkannt", ""),
    ("DATA_CHECK", "Datenvollständigkeit", "WARNING",
     "Beispielwarnung für Template-Test", "MOCK-LNE-C"),
    ("UNIT_CHECK", "Einheitenprüfung", "OK", "Alle Einheiten konsistent", ""),
)


def _shape(step_index: int, amplitude: float) -> float:
    """Deterministic load shape: a simple triangular ramp over the day.

    Chosen over a random walk so every regenerated mock dataset is identical.
    """
    half = len(TIMESTAMPS) / 2.0
    distance_from_peak = abs(step_index - half) / half
    return amplitude * (1.0 - distance_from_peak)


def _redistribution(element: MockElement, switched_off: tuple[str, ...]) -> float:
    """Offset applied to an element when other equipment is switched off.

    Purely synthetic: it only has to produce plausible, clearly ordered
    differences so every report section has something to show.
    """
    if element.element_id in switched_off:
        return 0.0

    offset = 0.0
    for off_id in switched_off:
        if element.variable == "loading":
            # A line out of service loads its neighbours; same voltage level counts double.
            offset += 11.0 if off_id.startswith("MOCK-LNE") else 7.0
        else:
            # Voltage sags slightly when equipment is removed.
            offset -= 0.006 if off_id.startswith("MOCK-LNE") else 0.004

    return offset


def build_dataset() -> CanonicalDataset:
    """Build the complete synthetic canonical dataset."""
    scenario_records = []
    outage_records = []
    result_records = []

    for scenario_id, name, description, switched_off in SCENARIOS:
        scenario_records.append(
            {
                "study_id": STUDY_ID,
                "scenario_id": scenario_id,
                "scenario_name": name,
                "is_reference": 1 if scenario_id == "REF" else 0,
                "description": description,
                "simulation_start": TIMESTAMPS[0],
                "simulation_end": TIMESTAMPS[-1],
                "simulation_status": "COMPLETED",
            }
        )

        for index, element_id in enumerate(switched_off):
            element = next(e for e in ALL_ELEMENTS if e.element_id == element_id)
            outage_records.append(
                {
                    "outage_id": f"{scenario_id}-OUT-{index + 1:02d}",
                    "scenario_id": scenario_id,
                    "element_id": element.element_id,
                    "element_name": element.element_name,
                    "element_type": element.element_type,
                    "start_time": TIMESTAMPS[0],
                    "end_time": TIMESTAMPS[-1],
                    "action": "OUT_OF_SERVICE",
                }
            )

        for element in ALL_ELEMENTS:
            # A switched-off element produces no measurements in that scenario.
            if element.element_id in switched_off:
                continue

            offset = _redistribution(element, switched_off)

            for step_index, timestamp in enumerate(TIMESTAMPS):
                value = element.base_value + offset + _shape(step_index, element.amplitude)

                result_records.append(
                    {
                        "study_id": STUDY_ID,
                        "scenario_id": scenario_id,
                        "timestamp": timestamp,
                        "element_id": element.element_id,
                        "element_name": element.element_name,
                        "element_type": element.element_type,
                        "variable": element.variable,
                        "value": round(value, 4),
                        "unit": element.unit,
                        "voltage_level": element.voltage_level,
                    }
                )

    qa_records = [
        {
            "model_id": "MOCK-MODEL",
            "model_version": "2026.08",
            "check_id": check_id,
            "check_name": check_name,
            "status": status,
            "message": message,
            "affected_element": affected,
        }
        for check_id, check_name, status, message, affected in QA_CHECKS
    ]

    study = StudyInfo(
        study_id=STUDY_ID,
        study_name="MOCK Freischaltungsanalyse Testnetz",
        study_description=(
            "Synthetischer Beispieldatensatz zur Template-Entwicklung. "
            "Enthält keine realen Netzdaten."
        ),
        model_name="MOCK_GridModel_2026",
        model_version="2026.08",
        simulation_time_step=TIME_STEP,
    )

    return RecordAdapter(
        study=study,
        scenario_records=scenario_records,
        result_records=result_records,
        outage_records=outage_records,
        qa_records=qa_records,
    ).load()
