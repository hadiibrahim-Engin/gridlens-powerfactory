"""Shared fixtures and builders.

The synthetic datasets built here use hand-picked round numbers so the expected
statistics can be written out by hand in the assertions.
"""

from __future__ import annotations

import pytest

from gridlens.adapters.record_adapter import RecordAdapter
from gridlens.canonical import CanonicalDataset, StudyInfo

STUDY = StudyInfo(
    study_id="T-STUDY",
    study_name="Test study",
    model_name="TestModel",
    model_version="1.0",
    simulation_time_step="15 min",
)

TIMES = ("2026-01-01 00:00", "2026-01-01 00:15", "2026-01-01 00:30", "2026-01-01 00:45")


def scenario_record(scenario_id: str, is_reference: bool = False, **overrides):
    record = {
        "study_id": STUDY.study_id,
        "scenario_id": scenario_id,
        "scenario_name": f"Scenario {scenario_id}",
        "is_reference": 1 if is_reference else 0,
        "description": "",
        "simulation_start": TIMES[0],
        "simulation_end": TIMES[-1],
        "simulation_status": "COMPLETED",
    }
    record.update(overrides)
    return record


def result_record(
    scenario_id: str,
    timestamp: str,
    element_id: str,
    value: float,
    *,
    element_type: str = "ElmLne",
    variable: str = "loading",
    unit: str = "%",
    element_name: str | None = None,
    voltage_level: str = "110 kV",
    **overrides,
):
    record = {
        "study_id": STUDY.study_id,
        "scenario_id": scenario_id,
        "timestamp": timestamp,
        "element_id": element_id,
        "element_name": element_name or f"Element {element_id}",
        "element_type": element_type,
        "variable": variable,
        "value": value,
        "unit": unit,
        "voltage_level": voltage_level,
    }
    record.update(overrides)
    return record


def build(scenarios, results, outages=(), qa=()) -> CanonicalDataset:
    return RecordAdapter(
        study=STUDY,
        scenario_records=scenarios,
        result_records=results,
        outage_records=outages,
        qa_records=qa,
    ).load()


@pytest.fixture
def simple_dataset() -> CanonicalDataset:
    """One line in REF and S01, with values chosen for exact assertions.

    REF loading: 10, 20, 30, 40  -> min 10, max 40, mean 25
    S01 loading: 20, 30, 40, 60  -> min 20, max 60, mean 37.5
    """
    scenarios = [scenario_record("REF", is_reference=True), scenario_record("S01")]

    results = []
    for timestamp, value in zip(TIMES, (10.0, 20.0, 30.0, 40.0)):
        results.append(result_record("REF", timestamp, "L1", value))
    for timestamp, value in zip(TIMES, (20.0, 30.0, 40.0, 60.0)):
        results.append(result_record("S01", timestamp, "L1", value))

    return build(scenarios, results)


@pytest.fixture
def mock_dataset() -> CanonicalDataset:
    from gridlens.mock import build_dataset

    return build_dataset()


@pytest.fixture
def mock_result(mock_dataset):
    from gridlens.processing import run

    return run(mock_dataset)


@pytest.fixture
def mock_payload(mock_result):
    from gridlens.mock import FIXED_GENERATION_DATE
    from gridlens.report_model import build_report_payload

    return build_report_payload(mock_result, generation_date=FIXED_GENERATION_DATE)
