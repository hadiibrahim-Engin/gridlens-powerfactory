"""Validation tests: every rule must produce a traceable finding."""

from __future__ import annotations

import pytest

from gridlens.adapters.base import AdapterError
from gridlens.processing import run, validate
from gridlens.processing.validation import ValidationCode, ValidationError
from gridlens.tests.conftest import TIMES, build, result_record, scenario_record


def codes(dataset):
    return {f.code for f in validate(dataset).findings}


def test_valid_dataset_has_no_findings(simple_dataset):
    report = validate(simple_dataset)
    assert report.ok
    assert not report.findings


def test_missing_reference_is_detected():
    dataset = build(
        [scenario_record("S01"), scenario_record("S02")],
        [
            result_record("S01", TIMES[0], "L1", 10.0),
            result_record("S02", TIMES[0], "L1", 10.0),
        ],
    )
    assert ValidationCode.MISSING_REFERENCE in codes(dataset)


def test_multiple_references_are_detected():
    dataset = build(
        [scenario_record("REF", is_reference=True), scenario_record("S01", is_reference=True)],
        [
            result_record("REF", TIMES[0], "L1", 10.0),
            result_record("S01", TIMES[0], "L1", 10.0),
        ],
    )
    assert ValidationCode.MULTIPLE_REFERENCES in codes(dataset)


def test_no_scenarios_is_detected():
    assert ValidationCode.NO_SCENARIOS in codes(build([], []))


def test_scenario_without_results_is_detected():
    dataset = build(
        [scenario_record("REF", is_reference=True), scenario_record("S01")],
        [result_record("REF", TIMES[0], "L1", 10.0)],
    )
    assert ValidationCode.SCENARIO_WITHOUT_RESULTS in codes(dataset)


def test_inconsistent_time_axis_is_reported_as_warning():
    dataset = build(
        [scenario_record("REF", is_reference=True), scenario_record("S01")],
        [
            result_record("REF", TIMES[0], "L1", 10.0),
            result_record("REF", TIMES[1], "L1", 11.0),
            result_record("S01", TIMES[0], "L1", 12.0),  # missing TIMES[1]
        ],
    )

    report = validate(dataset)
    assert ValidationCode.INCONSISTENT_TIME_AXIS in {f.code for f in report.warnings}
    # A differing axis is not fatal - the report simply skips aligned differences.
    assert report.ok


def test_duplicate_element_id_across_different_elements_is_detected():
    dataset = build(
        [scenario_record("REF", is_reference=True)],
        [
            result_record("REF", TIMES[0], "L1", 10.0, element_name="Line one"),
            result_record("REF", TIMES[1], "L1", 11.0, element_name="Line two"),
        ],
    )
    assert ValidationCode.DUPLICATE_ELEMENT_ID in codes(dataset)


def test_duplicate_result_point_is_detected():
    dataset = build(
        [scenario_record("REF", is_reference=True)],
        [
            result_record("REF", TIMES[0], "L1", 10.0),
            result_record("REF", TIMES[0], "L1", 10.0),
        ],
    )
    assert ValidationCode.DUPLICATE_RESULT_POINT in codes(dataset)


def test_nan_value_is_detected():
    dataset = build(
        [scenario_record("REF", is_reference=True)],
        [result_record("REF", TIMES[0], "L1", float("nan"))],
    )
    assert ValidationCode.NON_FINITE_VALUE in codes(dataset)


def test_mixed_units_for_one_variable_are_detected():
    dataset = build(
        [scenario_record("REF", is_reference=True)],
        [
            result_record("REF", TIMES[0], "L1", 10.0, unit="%"),
            result_record("REF", TIMES[1], "L2", 0.5, unit="p.u."),
        ],
    )
    assert ValidationCode.INCONSISTENT_UNIT in codes(dataset)


def test_results_for_undeclared_scenario_are_reported():
    dataset = build(
        [scenario_record("REF", is_reference=True)],
        [
            result_record("REF", TIMES[0], "L1", 10.0),
            result_record("GHOST", TIMES[0], "L1", 10.0),
        ],
    )
    report = validate(dataset)
    assert any("GHOST" in f.message for f in report.warnings)


def test_missing_element_id_is_rejected_by_the_adapter():
    """The adapter refuses to invent an identity - it fails loudly instead."""
    with pytest.raises(AdapterError, match="element_id"):
        build(
            [scenario_record("REF", is_reference=True)],
            [result_record("REF", TIMES[0], "", 10.0)],
        )


def test_unknown_variable_is_rejected_by_the_adapter():
    with pytest.raises(AdapterError, match="Unknown variable"):
        build(
            [scenario_record("REF", is_reference=True)],
            [result_record("REF", TIMES[0], "L1", 10.0, variable="c:reactive_power")],
        )


def test_findings_carry_readable_messages():
    dataset = build(
        [scenario_record("S01")],
        [result_record("S01", TIMES[0], "L1", 10.0)],
    )
    report = validate(dataset)

    assert report.errors
    for finding in report.errors:
        assert len(finding.message) > 20
        assert finding.code.value in str(finding)


def test_pipeline_refuses_to_process_invalid_data():
    dataset = build(
        [scenario_record("S01")],  # no reference
        [result_record("S01", TIMES[0], "L1", 10.0)],
    )

    with pytest.raises(ValidationError) as excinfo:
        run(dataset)

    assert "MISSING_REFERENCE" in str(excinfo.value)


def test_validation_reports_every_problem_at_once():
    dataset = build(
        [scenario_record("S01"), scenario_record("S02")],  # no reference
        [
            result_record("S01", TIMES[0], "L1", float("nan")),
            result_record("S01", TIMES[0], "L1", 5.0),  # duplicate
        ],
    )
    found = codes(dataset)

    assert ValidationCode.MISSING_REFERENCE in found
    assert ValidationCode.NON_FINITE_VALUE in found
    assert ValidationCode.DUPLICATE_RESULT_POINT in found
    assert ValidationCode.SCENARIO_WITHOUT_RESULTS in found
