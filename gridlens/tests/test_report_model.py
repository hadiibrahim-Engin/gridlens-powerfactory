"""Report data model and IntReport bridge tests."""

from __future__ import annotations

import pytest

from gridlens import DATA_CONTRACT_VERSION, TEMPLATE_NAME, TEMPLATE_VERSION
from gridlens.contracts.loader import load_report_contract
from gridlens.mock import FIXED_GENERATION_DATE
from gridlens.powerfactory_reporting import InMemoryIntReportBridge
from gridlens.report_model import build_report_payload


def test_payload_covers_every_contract_source(mock_payload):
    contract = load_report_contract()
    assert set(mock_payload) == set(contract.source_names)


def test_payload_validates_against_the_contract(mock_payload):
    load_report_contract().validate_payload(mock_payload)


def test_report_meta_carries_template_and_contract_version(mock_payload):
    meta = mock_payload["ScriptedReportMeta"][0]
    assert meta["template_name"] == TEMPLATE_NAME
    assert meta["template_version"] == TEMPLATE_VERSION
    assert meta["data_contract_version"] == DATA_CONTRACT_VERSION


def test_report_meta_is_exactly_one_row(mock_payload):
    assert len(mock_payload["ScriptedReportMeta"]) == 1


def test_generation_date_is_taken_from_the_caller(mock_payload):
    assert mock_payload["ScriptedReportMeta"][0]["generation_date"] == FIXED_GENERATION_DATE


def test_scenario_matrix_covers_every_element_and_scenario(mock_payload):
    matrix = mock_payload["ScriptedScenarioMatrix"]

    elements = {row["element_id"] for row in matrix}
    scenarios = {row["scenario_id"] for row in matrix}
    assert len(matrix) == len(elements) * len(scenarios)


def test_scenario_matrix_marks_switched_elements(mock_payload):
    matrix = mock_payload["ScriptedScenarioMatrix"]

    line_a_s01 = next(
        row for row in matrix
        if row["element_id"] == "MOCK-LNE-A" and row["scenario_id"] == "S01"
    )
    assert line_a_s01["is_out_of_service"] == 1
    assert line_a_s01["status_label"] == "OFF"

    line_a_ref = next(
        row for row in matrix
        if row["element_id"] == "MOCK-LNE-A" and row["scenario_id"] == "REF"
    )
    assert line_a_ref["is_out_of_service"] == 0
    assert line_a_ref["status_label"] == "ON"


def test_exactly_one_scenario_is_flagged_as_reference(mock_payload):
    flags = [row["is_reference"] for row in mock_payload["ScriptedScenarios"]]
    assert sum(flags) == 1


def test_loading_values_are_rounded_to_one_decimal(mock_payload):
    for row in mock_payload["ScriptedLineStatistics"]:
        assert row["max_loading"] == round(row["max_loading"], 1)


def test_voltage_values_are_rounded_to_three_decimals(mock_payload):
    for row in mock_payload["ScriptedVoltageStatistics"]:
        assert row["min_voltage"] == round(row["min_voltage"], 3)


def test_payload_is_reproducible(mock_result):
    first = build_report_payload(mock_result, generation_date=FIXED_GENERATION_DATE)
    second = build_report_payload(mock_result, generation_date=FIXED_GENERATION_DATE)
    assert first == second


def test_every_multi_row_source_has_data(mock_payload):
    """The mock dataset must exercise every section of the report."""
    for name, rows in mock_payload.items():
        assert rows, f"{name} is empty - mock data does not cover this section"


def test_relevant_time_points_have_an_element_and_value(mock_payload):
    """The report omits coincidence markers that cannot support a decision."""
    for row in mock_payload["ScriptedRelevantTimePoints"]:
        assert row["element_id"]
        assert row["metric_value"] is not None


def test_mock_data_is_recognisably_synthetic(mock_payload):
    meta = mock_payload["ScriptedReportMeta"][0]
    assert "MOCK" in meta["study_id"]
    assert "MOCK" in meta["model_name"]


# -- IntReport bridge ---------------------------------------------------------


def test_bridge_publishes_every_contract_table(mock_payload):
    bridge = InMemoryIntReportBridge()
    bridge.publish(mock_payload, load_report_contract())

    assert set(bridge.table_names) == set(load_report_contract().source_names)


def test_bridge_declares_every_contract_field(mock_payload):
    contract = load_report_contract()
    bridge = InMemoryIntReportBridge()
    bridge.publish(mock_payload, contract)

    for source in contract.sources:
        assert set(bridge.tables[source.name].fields) == set(source.field_names)


def test_bridge_writes_every_row(mock_payload):
    bridge = InMemoryIntReportBridge()
    bridge.publish(mock_payload, load_report_contract())

    for name, rows in mock_payload.items():
        assert bridge.row_count(name) == len(rows)


def test_bridge_writes_correct_values(mock_payload):
    bridge = InMemoryIntReportBridge()
    bridge.publish(mock_payload, load_report_contract())

    expected = mock_payload["ScriptedReportMeta"][0]["study_name"]
    assert bridge.tables["ScriptedReportMeta"].value(0, "study_name") == expected


def test_bridge_rejects_a_payload_that_violates_the_contract(mock_payload):
    payload = dict(mock_payload)
    payload["ScriptedScenarios"] = [{"scenario_id": "REF"}]  # missing required fields

    with pytest.raises(Exception, match="ScriptedScenarios"):
        InMemoryIntReportBridge().publish(payload, load_report_contract())


def test_bridge_creates_schema_even_without_rows(mock_payload):
    """A table with no rows must still exist, so the template stays bound."""
    payload = dict(mock_payload)
    payload["ScriptedOutages"] = []

    bridge = InMemoryIntReportBridge()
    bridge.publish(payload, load_report_contract())

    assert "ScriptedOutages" in bridge.tables
    assert bridge.tables["ScriptedOutages"].fields
    assert bridge.row_count("ScriptedOutages") == 0
