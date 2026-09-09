"""Tests fuer Fallergebnis, Referenzdeltas und Blockvergleich."""

import sys
from pathlib import Path

import pytest

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import payload


def series_item(key, category, values, unit="%"):
    points = [("{:02d}:00".format(i), float(i), v) for i, v in enumerate(values)]
    return {
        "category": category, "object": None, "key": key,
        "element_id": key, "element_name": key, "voltage_level": "110 kV",
        "variable_id": "c:loading", "variable": "Auslastung",
        "unit": unit, "points": points,
    }


def case(case_id, items, status="konvergiert"):
    record = {
        "id": case_id, "name": "Fall " + case_id, "kind": "scenario",
        "description": "", "status": status, "error_code": 0,
        "message": "", "snapshot": None, "outages": [],
    }
    return payload.scenario_result(
        record, items, ["00:00", "01:00", "02:00"], [0.0, 1.0, 2.0], "h")


def test_scenario_result_groups_by_category_and_computes_statistics():
    result = case("REF", [series_item("L1", "line", [10.0, 40.0, 20.0])])
    item, stats = result["by_category"]["line"][0]
    assert item["element_name"] == "L1"
    assert stats["min"] == 10.0 and stats["max"] == 40.0
    assert result["stats_by_key"][("line", "L1")] is stats


def test_reference_flag_is_set_only_for_the_reference_case():
    ref = case("REF", [])
    other = case("S01", [])
    payload.apply_reference([ref, other])
    assert ref["is_reference"] == 1
    assert other["is_reference"] == 0


def test_deltas_are_computed_against_the_reference():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0, 80.0])])
    s01 = case("S01", [series_item("L1", "line", [110.0, 118.0, 112.0])])
    payload.apply_reference([ref, s01])
    stats = s01["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] == 82.0
    assert stats["delta_max"] == 36.0


def test_incompatible_time_axis_invalidates_case_before_reference_delta():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0, 80.0])])
    s01 = case("S01", [series_item("L1", "line", [110.0, 118.0, 112.0])])
    s01["labels"] = ["00:00", "12:00", "24:00"]
    s01["plot_times"] = [0.0, 12.0, 24.0]
    payload.apply_reference([ref, s01])
    assert s01["status"] != "konvergiert"
    assert "Zeitachse" in s01["message"]
    stats = s01["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] is None
    assert stats["delta_max"] is None


def test_element_missing_from_the_reference_gets_no_substitute_zero():
    ref = case("REF", [])
    s01 = case("S01", [series_item("L1", "line", [110.0])])
    payload.apply_reference([ref, s01])
    stats = s01["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] is None
    assert stats["delta_max"] is None


def test_a_non_converged_reference_leaves_all_deltas_empty():
    ref = case("REF", [series_item("L1", "line", [80.0])],
               status="NICHT KONVERGIERT")
    s01 = case("S01", [series_item("L1", "line", [110.0])])
    payload.apply_reference([ref, s01])
    stats = s01["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] is None and stats["delta_max"] is None


def test_reference_case_keeps_zero_delta_against_itself():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0])])
    payload.apply_reference([ref])
    stats = ref["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] == 82.0
    assert stats["delta_max"] == 0.0


def test_critical_keys_span_every_case():
    ref = case("REF", [series_item("L1", "line", [80.0])])
    s01 = case("S01", [series_item("L1", "line", [118.0])])
    assert payload.critical_keys([ref, s01], "line") == {("line", "L1")}


def test_a_non_converged_case_never_makes_an_element_critical():
    ref = case("REF", [series_item("L1", "line", [80.0])])
    bad = case("S01", [series_item("L1", "line", [118.0])],
               status="NICHT KONVERGIERT")
    assert payload.critical_keys([ref, bad], "line") == set()


def build(results):
    payload.apply_reference(results)
    return payload.build_cases_payload(
        None, results, "Projekt", "GridLens_REF")


def test_block_comparison_emits_a_row_for_every_case():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0])])
    s01 = case("S01", [series_item("L1", "line", [110.0, 118.0])])
    s02 = case("S02", [series_item("L1", "line", [94.0, 96.0])])
    rows = build([ref, s01, s02])["ScriptedLineStatistics"]
    assert [(r["scenario_id"], r["max_loading"]) for r in rows] == [
        ("REF", 82.0), ("S01", 118.0), ("S02", 96.0)
    ]
    assert [r["reference_max_loading"] for r in rows] == [82.0, 82.0, 82.0]
    assert [r["delta_max_loading"] for r in rows] == [0.0, 36.0, 14.0]


def test_an_element_critical_nowhere_produces_no_row():
    ref = case("REF", [series_item("L1", "line", [80.0])])
    s01 = case("S01", [series_item("L1", "line", [82.0])])
    assert build([ref, s01])["ScriptedLineStatistics"] == []


def test_a_switched_off_element_gets_no_zero_row():
    ref = case("REF", [series_item("L1", "line", [118.0])])
    s01 = case("S01", [])
    rows = build([ref, s01])["ScriptedLineStatistics"]
    assert [r["scenario_id"] for r in rows] == ["REF"]


def test_non_converged_case_appears_only_in_scenarios_and_quality():
    ref = case("REF", [series_item("L1", "line", [118.0])])
    bad = case("S01", [series_item("L1", "line", [900.0])],
               status="NICHT KONVERGIERT")
    result = build([ref, bad])
    assert [r["scenario_id"] for r in result["ScriptedLineStatistics"]] == ["REF"]
    assert [r["scenario_id"] for r in result["ScriptedRankings"]] == ["REF"]
    assert [r["scenario_id"] for r in result["ScriptedLineLoadingBars"]] == ["REF"]
    assert "S01" in {r["scenario_id"] for r in result["ScriptedScenarios"]}
    assert any(r["status"] == "FAIL" for r in result["ScriptedModelQuality"])


def test_bar_label_carries_the_case_id():
    ref = case("REF", [series_item("L1", "line", [118.0])])
    bars = build([ref])["ScriptedLineLoadingBars"]
    assert bars[0]["bar_label"] == "REF · L1"
    assert bars[0]["element_name"] == "L1"


def test_rankings_no_longer_fake_a_reference_comparison():
    ref = case("REF", [series_item("L1", "line", [80.0])])
    s01 = case("S01", [series_item("L1", "line", [118.0])])
    rows = build([ref, s01])["ScriptedRankings"]
    top = [r for r in rows if r["scenario_id"] == "S01"][0]
    assert top["metric_value"] == 118.0
    assert top["reference_value"] == 80.0
    assert top["delta_value"] == 38.0


def test_outages_and_matrix_come_from_the_case_record():
    ref = case("REF", [])
    s01 = case("S01", [])
    s01["outages"] = [("ElmLne", "Leitung 17")]
    result = build([ref, s01])
    assert [(r["scenario_id"], r["element_name"])
            for r in result["ScriptedOutages"]] == [("S01", "Leitung 17")]
    assert result["ScriptedScenarioMatrix"][0]["status_label"] == "OFF"
    assert result["ScriptedScenarioMatrix"][0]["is_out_of_service"] == 1


def test_each_plot_carries_one_curve_per_case_and_only_its_own_element():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0]),
                       series_item("L2", "line", [10.0, 12.0])])
    s01 = case("S01", [series_item("L1", "line", [110.0, 118.0]),
                       series_item("L2", "line", [11.0, 13.0])])
    result = build([ref, s01])
    plots = result["ScriptedPlots"]
    assert len(plots) == 1
    assert plots[0]["element_name"] == "L1"
    roles = {r["series_role"] for r in result["ScriptedPlotData"]
             if r["plot_id"] == plots[0]["plot_id"]}
    assert roles == {"REF", "S01"}


def test_plot_data_never_mixes_two_elements():
    ref = case("REF", [series_item("L1", "line", [118.0]),
                       series_item("T1", "transformer", [130.0])])
    result = build([ref])
    by_plot = {}
    for row in result["ScriptedPlotData"]:
        by_plot.setdefault(row["plot_id"], set()).add(row["value"])
    assert by_plot == {"P001": {118.0}, "P002": {130.0}}


def test_validate_payload_accepts_case_ids_as_series_role():
    from gridlens_pf import publish
    ref = case("REF", [series_item("L1", "line", [118.0])])
    s01 = case("S01", [series_item("L1", "line", [120.0])])
    publish.validate_payload(build([ref, s01]))


def test_validate_payload_rejects_an_unknown_series_role():
    from gridlens_pf import publish
    ref = case("REF", [series_item("L1", "line", [118.0])])
    data = build([ref])
    data["ScriptedPlotData"][0]["series_role"] = "Phantom"
    with pytest.raises(ValueError, match="series_role"):
        publish.validate_payload(data)


def case_with_axis(case_id, items, labels, plot_times, status="konvergiert"):
    record = {
        "id": case_id, "name": "Fall " + case_id, "kind": "scenario",
        "description": "", "status": status, "error_code": 0,
        "message": "", "snapshot": None, "outages": [],
    }
    return payload.scenario_result(record, items, labels, plot_times, "h")


def test_cases_with_different_axes_are_rejected_without_a_reference():
    """GL-PR-004: axis consistency must not depend on a converged REF."""
    a = case_with_axis("S01", [series_item("L1", "line", [118.0, 120.0])],
                       ["00:00", "01:00"], [0.0, 1.0])
    b = case_with_axis("S02", [series_item("L1", "line", [119.0, 121.0])],
                       ["00:00", "24:00"], [0.0, 24.0])
    result = payload.build_cases_payload(None, [a, b], "Projekt", "GridLens_S01")
    statuses = {r["scenario_id"]: r["simulation_status"]
                for r in result["ScriptedScenarios"]}
    assert statuses["S01"] == "konvergiert"
    assert statuses["S02"] != "konvergiert"


def test_report_metadata_never_mixes_axes_when_the_reference_failed():
    """GL-PR-004: a failed REF must not leave the axis check switched off."""
    ref = case_with_axis("REF", [series_item("L1", "line", [80.0, 81.0])],
                         ["00:00", "01:00"], [0.0, 1.0],
                         status="NICHT KONVERGIERT")
    s01 = case_with_axis("S01", [series_item("L1", "line", [118.0, 120.0])],
                         ["00:00", "01:00"], [0.0, 1.0])
    s02 = case_with_axis("S02", [series_item("L1", "line", [119.0, 121.0])],
                         ["00:00", "24:00"], [0.0, 24.0])
    result = payload.build_cases_payload(
        None, [ref, s01, s02], "Projekt", "GridLens_REF")
    statuses = {r["scenario_id"]: r["simulation_status"]
                for r in result["ScriptedScenarios"]}
    assert statuses["S02"] != "konvergiert"
    meta = result["ScriptedReportMeta"][0]
    assert (meta["simulation_start"], meta["simulation_end"]) == ("00:00", "01:00")


def test_two_elements_with_the_same_name_stay_separable_in_the_matrix():
    """GL-PR-006: identical loc_name must not collapse the outage matrix."""
    s01 = case("S01", [])
    s01["outages"] = [
        ("ElmLne", "Leitung 17", "Netz\\Nord\\Leitung 17.ElmLne"),
        ("ElmLne", "Leitung 17", "Netz\\Sued\\Leitung 17.ElmLne"),
    ]
    result = payload.build_cases_payload(
        None, [s01], "Projekt", "GridLens_S01")
    matrix = result["ScriptedScenarioMatrix"]
    assert len(matrix) == 2
    assert len({row["element_id"] for row in matrix}) == 2
    # The MRT groups the matrix by element_name, so that column must separate
    # the two physical elements as well.
    assert len({row["element_name"] for row in matrix}) == 2
    assert all("\\" not in row["element_name"] for row in matrix)
    assert all(row["element_name"].startswith("Leitung 17") for row in matrix)


def test_a_unique_element_name_is_not_decorated():
    """GL-PR-006: disambiguation must not uglify the normal report."""
    s01 = case("S01", [])
    s01["outages"] = [("ElmLne", "Leitung 17", "Netz\\Nord\\Leitung 17.ElmLne")]
    result = payload.build_cases_payload(
        None, [s01], "Projekt", "GridLens_S01")
    row = result["ScriptedScenarioMatrix"][0]
    assert row["element_name"] == "Leitung 17"
    assert row["element_id"] == "Leitung 17"


class FallbackApp:
    """Minimal PowerFactory double for the single-state AKTIV fallback."""

    def __init__(self, objects):
        self._objects = objects

    def GetCalcRelevantObjects(self, pattern, calc_relevant=0):
        suffix = pattern.split(".")[-1]
        return [obj for obj in self._objects
                if obj.GetClassName() == suffix]

    def GetActiveScenario(self):
        return None

    def GetActiveProject(self):
        return None


class FallbackElement:
    def __init__(self, name, full_name):
        self.loc_name = name
        self.outserv = 1
        self._full_name = full_name

    def GetClassName(self):
        return "ElmLne"

    def GetFullName(self):
        return self._full_name


def test_active_fallback_also_separates_equally_named_outages():
    """GL-PR-006: the AKTIV fallback must not collapse duplicates either."""
    app = FallbackApp([
        FallbackElement("Leitung 17", "Netz\\Nord\\Leitung 17.ElmLne"),
        FallbackElement("Leitung 17", "Netz\\Sued\\Leitung 17.ElmLne"),
    ])
    result = payload.build_payload(
        app, None, None, [], ["00:00"], [0.0], "h")
    matrix = result["ScriptedScenarioMatrix"]
    assert len(matrix) == 2
    assert len({row["element_name"] for row in matrix}) == 2


def test_a_run_in_which_every_case_failed_still_publishes():
    """GL-PR-012: required fields must not block the honest failure report."""
    from gridlens_pf import publish
    failed = [case("REF", [], status="NICHT KONVERGIERT"),
              case("S01", [], status="NICHT KONVERGIERT")]
    data = build(failed)
    publish.validate_payload(data)
    statuses = {r["scenario_id"]: r["simulation_status"]
                for r in data["ScriptedScenarios"]}
    assert set(statuses) == {"REF", "S01"}
    assert any(row["status"] == "FAIL" for row in data["ScriptedModelQuality"])


def test_a_table_is_capped_and_the_cut_is_visible():
    """A runaway model must not produce an unbounded report in silence."""
    config = payload.config
    original = config.MAX_TABLE_ROWS
    config.MAX_TABLE_ROWS = 3
    try:
        items = [series_item("L{:03d}".format(index), "line", [118.0 + index])
                 for index in range(10)]
        ref = case("REF", items)
        data = build([ref])
        assert len(data["ScriptedLineStatistics"]) == 3
        quality = {row["check_id"]: row for row in data["ScriptedModelQuality"]}
        assert "table_limit_ScriptedLineStatistics" in quality
        cut = quality["table_limit_ScriptedLineStatistics"]
        assert cut["status"] == "FAIL"
        assert "10" in cut["message"] and "3" in cut["message"]
    finally:
        config.MAX_TABLE_ROWS = original


def test_a_table_within_the_limit_reports_no_cut():
    config = payload.config
    ref = case("REF", [series_item("L1", "line", [118.0])])
    data = build([ref])
    assert len(data["ScriptedLineStatistics"]) <= config.MAX_TABLE_ROWS
    assert not any(row["check_id"].startswith("table_limit_")
                   for row in data["ScriptedModelQuality"])


def test_the_capped_payload_still_satisfies_the_contract():
    from gridlens_pf import publish
    config = payload.config
    original = config.MAX_TABLE_ROWS
    config.MAX_TABLE_ROWS = 2
    try:
        items = [series_item("L{:03d}".format(index), "line", [118.0 + index])
                 for index in range(8)]
        data = build([case("REF", items)])
        publish.validate_payload(data)
    finally:
        config.MAX_TABLE_ROWS = original
