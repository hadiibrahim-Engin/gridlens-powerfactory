"""Data contract tests."""

from __future__ import annotations

import textwrap

import pytest

from gridlens import DATA_CONTRACT_VERSION
from gridlens.contracts.loader import (
    ContractError,
    load_input_contract,
    load_report_contract,
)

EXPECTED_SOURCES = [
    "ScriptedReportMeta",
    "ScriptedModelQuality",
    "ScriptedScenarios",
    "ScriptedOutages",
    "ScriptedScenarioMatrix",
    "ScriptedLineStatistics",
    "ScriptedTransformerStatistics",
    "ScriptedVoltageStatistics",
    "ScriptedLineLoadingBars",
    "ScriptedTransformerLoadingBars",
    "ScriptedVoltageMagnitudeBars",
    "ScriptedVoltageAngleBars",
    "ScriptedReferenceComparison",
    "ScriptedScenarioComparison",
    "ScriptedRankings",
    "ScriptedRelevantTimePoints",
    "ScriptedPlots",
    "ScriptedPlotData",
]


def test_report_contract_loads():
    contract = load_report_contract()
    assert contract.sources


def test_report_contract_version_matches_package():
    contract = load_report_contract()
    assert contract.version == DATA_CONTRACT_VERSION


def test_all_mandatory_sources_present():
    contract = load_report_contract()
    assert list(contract.source_names) == EXPECTED_SOURCES


def test_report_meta_is_single_row():
    contract = load_report_contract()
    assert contract.source("ScriptedReportMeta").single_row


def test_mandatory_report_meta_fields_exist():
    meta = load_report_contract().source("ScriptedReportMeta")
    for name in (
        "study_id",
        "study_name",
        "model_name",
        "model_version",
        "simulation_start",
        "simulation_end",
        "simulation_time_step",
        "generation_date",
        "template_name",
        "template_version",
        "data_contract_version",
        "result_name",
        "assessment_scope",
        "assessment_status",
    ):
        assert meta.field(name).name == name


def test_ranking_fields_match_specification():
    rankings = load_report_contract().source("ScriptedRankings")
    for name in (
        "ranking_type",
        "rank",
        "scenario_id",
        "element_id",
        "element_name",
        "element_type",
        "metric_name",
        "metric_value",
        "unit",
        "reference_value",
        "delta_value",
        "event_time",
    ):
        assert rankings.field(name).name == name


def test_unknown_field_raises_with_helpful_message():
    scenarios = load_report_contract().source("ScriptedScenarios")

    with pytest.raises(ContractError) as excinfo:
        scenarios.field("does_not_exist")

    message = str(excinfo.value)
    assert "does_not_exist" in message
    assert "scenario_id" in message  # lists the known fields


def test_unknown_source_raises():
    contract = load_report_contract()
    with pytest.raises(ContractError, match="Unknown data source"):
        contract.source("ScriptedNope")


def test_incompatible_version_is_detected():
    contract = load_report_contract()
    with pytest.raises(ContractError, match="Incompatible data contract version"):
        contract.require_version("99.0")


def test_matching_version_passes():
    load_report_contract().require_version(DATA_CONTRACT_VERSION)


def test_input_contract_loads_and_declares_all_inputs():
    contract = load_input_contract()
    assert list(contract.source_names) == ["I-QA", "I-SCENARIO", "I-OUTAGE", "I-RESULT"]


def test_duplicate_data_source_is_rejected(tmp_path):
    path = tmp_path / "dup-source.yaml"
    path.write_text(
        textwrap.dedent(
            """
            version: "1.0"
            data_sources:
              - name: A
                fields: [{ name: x, type: string }]
              - name: A
                fields: [{ name: y, type: string }]
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="duplicate data source"):
        load_report_contract(path)


def test_duplicate_field_is_rejected(tmp_path):
    path = tmp_path / "dup-field.yaml"
    path.write_text(
        textwrap.dedent(
            """
            version: "1.0"
            data_sources:
              - name: A
                fields:
                  - { name: x, type: string }
                  - { name: x, type: string }
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="duplicate field"):
        load_report_contract(path)


def test_unsupported_field_type_is_rejected(tmp_path):
    path = tmp_path / "bad-type.yaml"
    path.write_text(
        textwrap.dedent(
            """
            version: "1.0"
            data_sources:
              - name: A
                fields: [{ name: x, type: datetime }]
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="unsupported type"):
        load_report_contract(path)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(ContractError, match="not found"):
        load_report_contract(tmp_path / "absent.yaml")


# -- payload validation -------------------------------------------------------


def test_missing_required_field_produces_readable_error():
    scenarios = load_report_contract().source("ScriptedScenarios")

    with pytest.raises(ContractError) as excinfo:
        scenarios.validate_rows([{"scenario_id": "REF"}])

    message = str(excinfo.value)
    assert "ScriptedScenarios" in message
    assert "missing 'scenario_name'" in message


def test_null_required_field_is_rejected():
    scenarios = load_report_contract().source("ScriptedScenarios")

    with pytest.raises(ContractError, match="is null"):
        scenarios.validate_rows(
            [
                {
                    "scenario_id": "REF",
                    "scenario_name": None,
                    "is_reference": 1,
                    "simulation_status": "OK",
                    "simulation_start": "t0",
                    "simulation_end": "t1",
                }
            ]
        )


def test_single_row_source_rejects_multiple_rows():
    meta = load_report_contract().source("ScriptedReportMeta")
    with pytest.raises(ContractError, match="single_row"):
        meta.validate_rows([])


def test_payload_missing_a_source_is_rejected():
    contract = load_report_contract()
    with pytest.raises(ContractError, match="missing data source"):
        contract.validate_payload({"ScriptedReportMeta": []})


def test_payload_with_unknown_source_is_rejected(mock_payload):
    contract = load_report_contract()
    payload = dict(mock_payload)
    payload["ScriptedSomethingElse"] = []

    with pytest.raises(ContractError, match="outside contract"):
        contract.validate_payload(payload)
