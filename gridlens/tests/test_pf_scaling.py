"""Tests fuer spaltenweises Ergebnislesen und die Groessengrenzen."""

import sys
from pathlib import Path

import pytest

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import config, results


class Element:
    def __init__(self, class_name, name):
        self._class_name = class_name
        self.loc_name = name
        self.uknom = 110.0

    def GetClassName(self):
        return self._class_name

    def GetFullName(self):
        return "Grid." + self.loc_name + "." + self._class_name


class BigResult:
    """ElmRes double that counts how the reader accesses its data."""

    def __init__(self, rows=4, lines=2, column_values=True):
        self.rows = rows
        self.column_values = column_values
        self.cell_reads = 0
        self.column_reads = 0
        self._columns = [(None, "b:tnow", "h")]
        for index in range(lines):
            self._columns.append(
                (Element("ElmLne", "L{:03d}".format(index)), "c:loading", "%"))

    def GetNumberOfRows(self):
        return self.rows

    def GetNumberOfColumns(self):
        return len(self._columns)

    def GetObject(self, column):
        return self._columns[column][0]

    def GetVariable(self, column):
        return self._columns[column][1]

    def GetUnit(self, column):
        return self._columns[column][2]

    def _cell(self, row, column):
        if column == 0:
            return float(row)
        return 10.0 + row + column

    def GetValue(self, row, column):
        self.cell_reads += 1
        return 0, self._cell(row, column)

    def GetColumnValues(self, column):
        if not self.column_values:
            raise RuntimeError("not supported in this PowerFactory build")
        self.column_reads += 1
        return [self._cell(row, column) for row in range(self.rows)]


def test_the_reader_prefers_column_wise_access():
    """GL-PR-010: DIgSILENT recommends column reads over cell-by-cell."""
    elmres = BigResult(rows=6, lines=3)
    series, labels, plot_times, _ = results.collect_series(elmres)
    assert len(series) == 3
    assert len(labels) == 6
    assert elmres.column_reads == 4
    assert elmres.cell_reads == 0


def test_column_wise_and_cell_wise_reads_agree():
    fast = results.collect_series(BigResult(rows=6, lines=3))[0]
    slow = results.collect_series(
        BigResult(rows=6, lines=3, column_values=False))[0]
    assert [item["points"] for item in fast] == [item["points"] for item in slow]


def test_the_reader_falls_back_to_cells_when_columns_are_unavailable():
    elmres = BigResult(rows=6, lines=3, column_values=False)
    series, _, _, _ = results.collect_series(elmres)
    assert len(series) == 3
    assert elmres.cell_reads > 0


def test_a_short_column_is_rejected_instead_of_silently_padded():
    elmres = BigResult(rows=6, lines=2)
    elmres.GetColumnValues = lambda column: [1.0, 2.0]
    with pytest.raises(RuntimeError, match="Spalte|column"):
        results.collect_series(elmres)


def test_too_many_rows_are_refused_with_the_configured_limit():
    elmres = BigResult(rows=config.MAX_RESULT_ROWS + 1, lines=1)
    with pytest.raises(RuntimeError, match=str(config.MAX_RESULT_ROWS)):
        results.collect_series(elmres)


def test_too_many_result_cells_are_refused():
    elmres = BigResult(rows=1000, lines=10)
    original = config.MAX_RESULT_CELLS
    config.MAX_RESULT_CELLS = 100
    try:
        with pytest.raises(RuntimeError, match="100"):
            results.collect_series(elmres)
    finally:
        config.MAX_RESULT_CELLS = original


def test_the_limits_are_documented_as_numbers():
    assert config.MAX_RESULT_ROWS > 0
    assert config.MAX_RESULT_CELLS > config.MAX_RESULT_ROWS


def make_result(case_id, series_count, rows):
    from gridlens_pf import payload
    labels = ["{:02d}".format(index) for index in range(rows)]
    plot_times = [float(index) for index in range(rows)]
    items = []
    for index in range(series_count):
        key = "L{:04d}".format(index)
        items.append({
            "category": "line", "object": None, "key": key,
            "element_id": key, "element_name": key, "voltage_level": "110 kV",
            "variable_id": "c:loading", "variable": "Auslastung", "unit": "%",
            "points": [(labels[row], plot_times[row], 50.0 + row)
                       for row in range(rows)],
        })
    record = {
        "id": case_id, "name": case_id, "kind": "scenario", "description": "",
        "status": "konvergiert", "error_code": 0, "message": "",
        "snapshot": None, "outages": [],
    }
    return payload.scenario_result(record, items, labels, plot_times, "h")


def test_a_run_within_the_budget_is_accepted():
    results.check_run_budget([make_result("REF", 2, 10)])


def test_the_run_budget_counts_every_case_together():
    """GL-PR-010: all cases are held in memory at once, so the budget is global."""
    original = config.MAX_RUN_CELLS
    config.MAX_RUN_CELLS = 100
    try:
        cases = [make_result("REF", 3, 20), make_result("S01", 3, 20)]
        with pytest.raises(RuntimeError, match="MAX_RUN_CELLS"):
            results.check_run_budget(cases)
    finally:
        config.MAX_RUN_CELLS = original


def test_the_run_budget_names_the_measured_cost():
    original = config.MAX_RUN_CELLS
    config.MAX_RUN_CELLS = 10
    try:
        with pytest.raises(RuntimeError) as failure:
            results.check_run_budget([make_result("REF", 2, 10)])
        assert "10" in str(failure.value)
    finally:
        config.MAX_RUN_CELLS = original


def test_the_reader_keeps_only_the_plot_sample_of_a_long_series():
    """Memory must not grow with the number of time steps per series."""
    elmres = BigResult(rows=1000, lines=1)
    series, labels, _, _ = results.collect_series(elmres)
    assert len(labels) == 1000
    assert len(series[0]["points"]) <= config.MAX_PLOT_POINTS


def test_statistics_are_computed_over_the_full_column_not_the_sample():
    """Mean and P95 are wrong if they only see the 61 sampled points."""
    elmres = BigResult(rows=1000, lines=1)
    series, _, _, _ = results.collect_series(elmres)
    stats = series[0]["statistics"]
    assert stats["min"] == 11.0
    assert stats["max"] == 1010.0
    assert stats["mean"] == 510.5
    assert stats["p95"] == 960.0


def test_the_retained_sample_still_carries_the_extremes():
    elmres = BigResult(rows=1000, lines=1)
    series, _, _, _ = results.collect_series(elmres)
    values = [value for _, _, value in series[0]["points"]]
    assert min(values) == 11.0
    assert max(values) == 1010.0


def test_a_short_series_is_not_sampled_at_all():
    elmres = BigResult(rows=5, lines=1)
    series, _, _, _ = results.collect_series(elmres)
    assert len(series[0]["points"]) == 5


def test_the_case_result_reuses_the_statistics_from_the_reader():
    from gridlens_pf import payload
    elmres = BigResult(rows=1000, lines=1)
    series, labels, plot_times, unit = results.collect_series(elmres)
    record = {
        "id": "REF", "name": "Referenz", "kind": "reference", "description": "",
        "status": "konvergiert", "error_code": 0, "message": "",
        "snapshot": None, "outages": [],
    }
    result = payload.scenario_result(record, series, labels, plot_times, unit)
    _, stats = result["by_category"]["line"][0]
    assert stats["mean"] == 510.5
    assert stats["p95"] == 960.0


def test_a_hand_built_series_without_statistics_still_works():
    """Existing callers that construct series by hand must keep working."""
    from gridlens_pf import payload
    item = {
        "category": "line", "object": None, "key": "L1", "element_id": "L1",
        "element_name": "L1", "voltage_level": "110 kV",
        "variable_id": "c:loading", "variable": "Auslastung", "unit": "%",
        "points": [("00:00", 0.0, 10.0), ("01:00", 1.0, 30.0)],
    }
    record = {
        "id": "REF", "name": "R", "kind": "reference", "description": "",
        "status": "konvergiert", "error_code": 0, "message": "",
        "snapshot": None, "outages": [],
    }
    result = payload.scenario_result(
        record, [item], ["00:00", "01:00"], [0.0, 1.0], "h")
    _, stats = result["by_category"]["line"][0]
    assert stats["min"] == 10.0 and stats["max"] == 30.0
