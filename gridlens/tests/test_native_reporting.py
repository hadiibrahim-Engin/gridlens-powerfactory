"""Tests for the self-contained active-model PowerFactory publisher."""

import ast
import base64
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest


DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

import gridlens_pf as native


class PFObject:
    def __init__(self, class_name, name, full_name=None, **attributes):
        self._class_name = class_name
        self.loc_name = name
        self._full_name = full_name or name + "." + class_name
        for key, value in attributes.items():
            setattr(self, key, value)

    def GetClassName(self):
        return self._class_name

    def GetFullName(self):
        return self._full_name


class ElmRes(PFObject):
    def __init__(self):
        super().__init__("ElmRes", "Quasi-Dynamic Simulation AC")
        self.line = PFObject("ElmLne", "Line A", "Grid.Line A.ElmLne", outserv=0)
        self.line_ok = PFObject("ElmLne", "Line B", "Grid.Line B.ElmLne", outserv=0)
        self.transformer = PFObject("ElmTr2", "Transformer 1", "Grid.Transformer 1.ElmTr2", outserv=1)
        self.terminal = PFObject("ElmTerm", "Bus 1", "Grid.Bus 1.ElmTerm", outserv=0, uknom=110.0)
        self.terminal_high = PFObject("ElmTerm", "Bus 2", "Grid.Bus 2.ElmTerm", outserv=0, uknom=110.0)
        self.columns = (
            (None, "b:tnow", "h"),
            (self.line, "c:loading", "%"),
            (self.line_ok, "c:loading", "%"),
            (self.transformer, "c:loading", "%"),
            (self.terminal, "m:u", "p.u."),
            (self.terminal_high, "m:u", "p.u."),
            (self.terminal, "m:phiu", "deg"),
            (self.terminal_high, "m:phiu", "deg"),
        )
        self.values = (
            (0.0, "90,0", 60.0, 80.0, 1.01, 1.01, -1.0, 2.0),
            (1.0, "101.0", 70.0, 110.0, 0.94, 1.06, -4.0, 6.0),
            (2.0, 95.0, 65.0, 99.0, 0.99, 1.02, -2.0, 3.0),
        )
        self.loaded = False

    def Load(self):
        self.loaded = True

    def Release(self):
        self.loaded = False

    def GetNumberOfRows(self):
        return len(self.values)

    def GetNumberOfColumns(self):
        return len(self.columns)

    def GetObject(self, column):
        return self.columns[column][0]

    def GetVariable(self, column):
        return self.columns[column][1]

    def GetUnit(self, column):
        return self.columns[column][2]

    def GetValue(self, row, column):
        return 0, self.values[row][column]


class StudyCase(PFObject):
    def __init__(self, result):
        super().__init__("IntCase", "Active Study", "Project.Active Study.IntCase")
        self.result = result

    def GetContents(self, pattern, *args):
        if pattern in (native.RESULT_FILE_NAME, "*.ElmRes"):
            return [self.result]
        return []


class SQLiteReport:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.tables = {}
        self.resets = 0
        self.fail_field = None

    def GetClassName(self):
        return "IntReport"

    def Reset(self):
        for name in self.tables:
            self.connection.execute(f'DROP TABLE "Scripted{name}"')
        self.tables = {}
        self.resets += 1

    def CreateTable(self, name):
        self.connection.execute(
            f'CREATE TABLE "Scripted{name}" (_row_index INTEGER PRIMARY KEY)'
        )
        self.tables[name] = {}

    def CreateField(self, table, name, field_type):
        sql_type = {0: "TEXT", 1: "INTEGER", 2: "REAL"}[field_type]
        self.connection.execute(
            f'ALTER TABLE "Scripted{table}" ADD COLUMN "{name}" {sql_type}'
        )
        self.tables[table][name] = field_type

    def SetValue(self, table, field, row, value):
        if field == self.fail_field:
            raise RuntimeError("simulated failure")
        self.connection.execute(
            f'INSERT OR IGNORE INTO "Scripted{table}" (_row_index) VALUES (?)',
            (row,),
        )
        self.connection.execute(
            f'UPDATE "Scripted{table}" SET "{field}"=? WHERE _row_index=?',
            (value, row),
        )


@pytest.fixture
def active_model():
    result = ElmRes()
    study = StudyCase(result)
    scenario = PFObject("IntScenario", "Base Scenario")
    project = PFObject("IntPrj", "Grid Project")
    app = SimpleNamespace(
        GetActiveScenario=lambda: scenario,
        GetActiveProject=lambda: project,
        GetCalcRelevantObjects=lambda pattern, *args: [
            result.line, result.line_ok, result.transformer
        ],
    )
    return app, study, result


def prepared_payload(active_model):
    app, study, result = active_model
    result.Load()
    series, labels, plot_times, time_unit = native.collect_series(result)
    return native.build_payload(
        app, study, result, series, labels, plot_times, time_unit)


def test_result_without_an_explicit_time_column_is_rejected():
    result = ElmRes()
    result.columns = result.columns[1:]
    result.values = tuple(row[1:] for row in result.values)
    with pytest.raises(RuntimeError, match="Zeit|time"):
        native.collect_series(result)


def test_result_cell_with_nonzero_error_code_is_rejected():
    result = ElmRes()
    original = result.GetValue

    def get_value(row, column):
        if row == 1 and column == 1:
            return 7, 0.0
        return original(row, column)

    result.GetValue = get_value
    with pytest.raises(RuntimeError, match="Zelle|GetValue|Ergebniswert"):
        native.collect_series(result)


def test_partial_result_series_is_rejected_instead_of_silently_shortened():
    result = ElmRes()
    rows = [list(row) for row in result.values]
    rows[1][1] = None
    result.values = tuple(tuple(row) for row in rows)
    with pytest.raises(RuntimeError, match="Zelle|Ergebniswert"):
        native.collect_series(result)


def test_runtime_package_is_self_contained_and_has_no_mock_input():
    """The deployment must run on the standard library plus powerfactory."""
    entry = DEPLOYMENT / "gridlens_report.py"
    package = DEPLOYMENT / "gridlens_pf"
    assert entry.is_file()
    assert package.is_dir()
    assert {path.name for path in DEPLOYMENT.iterdir() if path.is_file()} == {
        "MASTER_GRIDLENS.mrt", "README.md", "gridlens_report.py"
    }

    allowed = {"hashlib", "math", "os", "sys", "datetime", "powerfactory"}
    for path in [entry] + sorted(package.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "mock-payload" not in source, path
        assert "report-schema" not in source, path
        assert "import json" not in source, path
        assert "sqlite3" not in source, path
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in allowed, (path, alias.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                root = (node.module or "").split(".")[0]
                assert root in allowed | {"gridlens_pf"}, (path, node.module)

    assert native.PUBLISHER_VERSION == "4.1.0"
    assert native.TEMPLATE_VERSION == "2.2.0"
    assert native.DATA_CONTRACT_VERSION == "2.2"


def test_mrt_sources_match_embedded_table_contract():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    sources = root.find("Dictionary/DataSources")
    expected = {name: dict(fields) for name, fields in native.TABLES}
    assert {source.findtext("Name") for source in sources} == set(expected)
    for source in sources:
        name = source.findtext("Name")
        columns = dict(
            value.text.split(",", 1)
            for value in source.findall("Columns/value")
        )
        assert set(columns) == set(expected[name])
        type_names = {
            "string": "System.String", "integer": "System.Int32",
            "number": "System.Double",
        }
        assert columns == {
            field: type_names[kind] for field, kind in expected[name].items()
        }
        assert source.findtext("NameInSource") == "SQLite"
        assert 'FROM "{}"'.format(name) in source.findtext("SqlCommand")


def test_active_elmres_is_selected_and_statistics_are_built(active_model):
    app, study, result = active_model
    assert native.select_result(study) is result
    payload = prepared_payload(active_model)
    line = payload["ScriptedLineStatistics"][0]
    transformer = payload["ScriptedTransformerStatistics"][0]
    voltages = payload["ScriptedVoltageStatistics"]
    assert line["element_id"] == "Line A"
    assert line["max_loading"] == 101.0
    assert line["mean_loading"] == pytest.approx(95.3333333333)
    assert transformer["max_loading"] == 110.0
    assert {row["element_id"] for row in voltages} == {"Bus 1", "Bus 2"}
    assert next(row for row in voltages if row["element_id"] == "Bus 1")["min_voltage"] == 0.94
    assert {row["element_id"] for row in payload["ScriptedLineStatistics"]} == {"Line A"}
    assert payload["ScriptedReportMeta"][0]["study_name"] == "Active Study"
    assert payload["ScriptedReportMeta"][0]["study_id"] == "Active Study"
    assert payload["ScriptedReportMeta"][0]["simulation_start"] == "00:00"
    assert payload["ScriptedReportMeta"][0]["simulation_end"] == "02:00"
    assert payload["ScriptedReportMeta"][0]["simulation_time_step"] == "1 h"
    assert payload["ScriptedScenarios"][0]["scenario_id"] == "AKTIV"
    assert payload["ScriptedScenarios"][0]["scenario_name"] == "Base Scenario"
    assert payload["ScriptedScenarios"][0]["is_reference"] == 0
    assert payload["ScriptedScenarioMatrix"] == [{
        "element_id": "Transformer 1",
        "element_name": "Transformer 1",
        "element_type": "transformer",
        "scenario_id": "AKTIV",
        "is_out_of_service": 1,
        "status_label": "OFF",
    }]
    assert {row["ranking_type"] for row in payload["ScriptedRankings"]} == {
        "highest_line_loading", "highest_transformer_loading",
        "lowest_voltage", "highest_voltage",
    }
    assert len(payload["ScriptedPlots"]) == 4
    assert len(payload["ScriptedPlotData"]) == 12
    assert [row["timestamp"] for row in payload["ScriptedPlotData"][:3]] == [0.0, 1.0, 2.0]
    # series_role carries the case id now, so each chart can hold one curve per
    # case. In the single-state fallback that is the compact id AKTIV.
    assert {row["series_role"] for row in payload["ScriptedPlotData"]} == {"AKTIV"}
    assert all("Auslastung" in row["plot_title"] or "Spannungsbetrag" in row["plot_title"]
               for row in payload["ScriptedPlots"])
    assert payload["ScriptedLineLoadingBars"][0]["element_name"] == "Line A"
    assert payload["ScriptedTransformerLoadingBars"][0]["max_loading"] == 110.0
    assert {row["element_name"] for row in payload["ScriptedVoltageMagnitudeBars"]} == {
        "Bus 1", "Bus 2"
    }
    angle = payload["ScriptedVoltageAngleBars"][0]
    assert angle["element_name"] == "Bus 2"
    assert angle["min_angle"] == 2.0
    assert angle["max_angle"] == 6.0
    assert angle["max_abs_angle"] == 6.0
    quality = {row["check_id"]: row for row in payload["ScriptedModelQuality"]}
    assert quality["time_variation"]["status"] == "PASS"
    assert quality["limit_voltage"]["message"] == (
        "Grenzwertverletzung bei Spannung < 0,95 p.u. oder > 1,05 p.u."
    )


def test_native_publish_and_mrt_sql_read_active_values(active_model):
    payload = prepared_payload(active_model)
    report = SQLiteReport()
    try:
        native.publish_report(report, payload)
        assert len(report.tables) == len(native.TABLES)
        value = report.connection.execute(
            'SELECT max_loading FROM "ScriptedLineStatistics"'
        ).fetchone()[0]
        assert value == 101.0
        root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
        for source in root.findall("Dictionary/DataSources/*"):
            report.connection.execute(source.findtext("SqlCommand")).fetchall()
    finally:
        report.connection.close()


def test_rerun_replaces_old_rows(active_model):
    payload = prepared_payload(active_model)
    report = SQLiteReport()
    try:
        native.publish_report(report, payload)
        payload["ScriptedLineStatistics"] = []
        native.publish_report(report, payload)
        assert report.resets == 2
        assert report.connection.execute(
            'SELECT count(*) FROM "ScriptedLineStatistics"'
        ).fetchone()[0] == 0
    finally:
        report.connection.close()


def test_invalid_number_is_rejected_before_reset(active_model):
    payload = prepared_payload(active_model)
    payload["ScriptedLineStatistics"][0]["max_loading"] = "invalid"
    report = SQLiteReport()
    try:
        with pytest.raises(ValueError, match="max_loading"):
            native.publish_report(report, payload)
        assert report.resets == 0
    finally:
        report.connection.close()


def test_plot_sampling_keeps_endpoints_and_extrema():
    points = [(str(index), float(index), 50.0) for index in range(1000)]
    points[333] = ("333", 333.0, 125.0)
    points[777] = ("777", 777.0, 10.0)
    sampled = native.sampled_plot_points({"points": points})
    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]
    assert points[333] in sampled
    assert points[777] in sampled
    assert len(sampled) <= native.MAX_PLOT_POINTS + 2


def test_noncritical_series_are_omitted_from_report(active_model):
    _, _, result = active_model
    result.columns = result.columns[:6]
    result.values = (
        (0.0, 90.0, 60.0, 80.0, 1.00, 1.01),
        (1.0, 99.0, 70.0, 95.0, 0.95, 1.05),
        (2.0, 95.0, 65.0, 99.0, 0.99, 1.02),
    )
    payload = prepared_payload(active_model)
    for table in (
        "ScriptedLineStatistics", "ScriptedTransformerStatistics",
        "ScriptedVoltageStatistics",
        "ScriptedScenarioComparison", "ScriptedRankings",
        "ScriptedRelevantTimePoints", "ScriptedPlots", "ScriptedPlotData",
        "ScriptedLineLoadingBars", "ScriptedTransformerLoadingBars",
    ):
        assert payload[table] == []
    assert payload["ScriptedVoltageMagnitudeBars"] == []
    assert payload["ScriptedVoltageAngleBars"] == []
    assert payload["ScriptedScenarioMatrix"][0]["status_label"] == "OFF"


def test_static_results_and_missing_angles_are_reported(active_model):
    _, _, result = active_model
    result.columns = result.columns[:6]
    result.values = (
        (0.0, 101.0, 60.0, 110.0, 0.94, 1.06),
        (1.0, 101.0, 60.0, 110.0, 0.94, 1.06),
        (2.0, 101.0, 60.0, 110.0, 0.94, 1.06),
    )
    payload = prepared_payload(active_model)
    quality = {row["check_id"]: row for row in payload["ScriptedModelQuality"]}
    assert quality["time_variation"]["status"] == "WARNING"
    assert "zeitlich konstant" in quality["time_variation"]["message"]
    assert quality["series_voltage_angle"]["status"] == "WARNING"
    assert "m:phiu" in quality["series_voltage_angle"]["message"]


def test_invalid_plot_relation_is_rejected_before_reset(active_model):
    payload = prepared_payload(active_model)
    payload["ScriptedPlotData"][0]["plot_id"] = "missing"
    report = SQLiteReport()
    try:
        with pytest.raises(ValueError, match="no parent plot"):
            native.publish_report(report, payload)
        assert report.resets == 0
    finally:
        report.connection.close()


def test_partial_publication_is_reset_with_cell_context(active_model):
    report = SQLiteReport()
    report.fail_field = "max_loading"
    try:
        with pytest.raises(RuntimeError, match=r"SetValue\(LineStatistics.max_loading"):
            native.publish_report(report, prepared_payload(active_model))
        assert report.resets == 2
        assert not report.tables
    finally:
        report.connection.close()


def test_external_compython_entry_point(active_model, monkeypatch):
    app_base, study, result = active_model
    report = SQLiteReport()
    messages = []
    app = SimpleNamespace(
        GetCurrentScript=lambda: SimpleNamespace(GetParent=lambda: report),
        GetActiveStudyCase=lambda: study,
        GetActiveScenario=app_base.GetActiveScenario,
        GetActiveProject=app_base.GetActiveProject,
        GetCalcRelevantObjects=app_base.GetCalcRelevantObjects,
        PrintPlain=messages.append,
    )
    monkeypatch.setitem(
        sys.modules, "powerfactory", SimpleNamespace(GetApplication=lambda: app)
    )
    try:
        native.main()
        assert len(report.tables) == len(native.TABLES)
        assert "GridLens publisher: " + native.PUBLISHER_VERSION in messages
        assert "GridLens mode: report" in messages
        assert messages[-1] == "GridLens: {} Tabellen publiziert.".format(
            len(native.TABLES))
        assert result.loaded is False
    finally:
        report.connection.close()


def test_mrt_reference_graph_plot_relation_and_branding_are_intact():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    report_file = root.findtext("ReportFile", default="")
    assert report_file == ""
    serialized = ET.tostring(root, encoding="unicode")
    production_files = serialized + (DEPLOYMENT / "gridlens_report.py").read_text()
    for local_path_marker in ("/Users/", "/home/", "file://", "C:\\", "C:/"):
        assert local_path_marker not in production_files
    references = [node.get("Ref") for node in root.iter() if node.get("Ref")]
    assert len(references) == len(set(references))
    by_ref = {node.get("Ref"): node for node in root.iter() if node.get("Ref")}
    relation = root.find("Dictionary/Relations/PlotsToPlotData")
    assert by_ref[relation.find("ParentSource").get("isRef")].findtext("Name") == "ScriptedPlots"
    assert by_ref[relation.find("ChildSource").get("isRef")].findtext("Name") == "ScriptedPlotData"
    assert relation.findtext("ParentColumns/value") == "plot_id"
    assert relation.findtext("ChildColumns/value") == "plot_id"
    plot_chart = root.find(".//PlotsChart")
    assert plot_chart.find("MasterComponent").get("isRef") == root.find(
        ".//PlotsPlotBand"
    ).get("Ref")

    images = [node for node in root.iter() if node.get("type") == "Image"]
    assert {node.findtext("Name") for node in images} == {
        "DigSilentLogoCover", "DigSilentLogo", "DigSilentLogo1", "DigSilentLogo2"
    }
    for node in images:
        assert base64.b64decode(node.findtext("ImageBytes")).startswith(b"\x89PNG\r\n\x1a\n")
    assert any(node.text == "[181:18:62]" for node in root.iter("Brush"))
    assert root.find(".//PlotsPlotBand").findtext("CanBreak") in (None, "False")


def test_mrt_toc_critical_styles_and_chart_scaling_are_configured():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    toc = root.find(".//BandTableOfContents")
    assert toc is not None
    assert toc.findtext("DataSourceName") == "ScriptedReportMeta"
    assert toc.findtext("NewPageAfter") == "True"
    links = [
        node for node in toc.findall("Components/*")
        if (node.findtext("Name") or "").startswith("TableOfContentsLink")
    ]
    assert len(links) == 14
    hyperlinks = {node.findtext("Hyperlink") for node in links}
    bookmarks = {node.text for node in root.iter("Bookmark")}
    assert hyperlinks == {"#" + bookmark for bookmark in bookmarks}
    assert root.find(".//ReferencePageBreakBand").findtext("NewPageAfter") == "True"
    assert root.find(".//ReferenceStateDataBand/Filters").get("count") == "0"
    for name in ("HeaderRight", "HeaderRight1", "HeaderRight2"):
        assert root.find(".//" + name).findtext("Text") == (
            "{ScriptedReportMeta.result_name}"
        )

    x_axis = root.find(".//PlotsChart/Area/XAxis")
    assert x_axis.findtext("StartFromZero") == "False"
    assert x_axis.findtext("ShowEdgeValues") == "True"
    assert x_axis.findtext("Labels/Step") == "5"
    assert x_axis.findtext("Title/Text") == "Zeit [h]"
    assert root.find(".//PlotsChart/Area/YAxis").findtext("StartFromZero") == "False"

    expected_bar_charts = {
        "LineLoadingBarChart": "ScriptedLineLoadingBars",
        "TransformerLoadingBarChart": "ScriptedTransformerLoadingBars",
        "VoltageMagnitudeBarChart": "ScriptedVoltageMagnitudeBars",
        "VoltageAngleBarChart": "ScriptedVoltageAngleBars",
    }
    for chart_name, data_source in expected_bar_charts.items():
        chart = root.find(".//" + chart_name)
        assert chart is not None
        assert chart.findtext("DataSourceName") == data_source
        assert chart.find("Area").get("type").endswith("StiClusteredBarArea")
        assert all(
            series.get("type").endswith("StiClusteredBarSeries")
            for series in chart.find("Series")
        )
        assert chart.find("Style").get("type").endswith("StiStyle29")
        assert all(
            series.findtext("AllowApplyStyle") == "False"
            for series in chart.find("Series")
        )

    assert root.find(".//VoltageAngleAnalysisTitleBandText/Bookmark").text == (
        "section-voltage-angle"
    )
    page_breaks = [
        node for node in root.iter()
        if (node.findtext("Name") or "").endswith("PageBreakBand")
    ]
    assert len(page_breaks) >= 11
    assert all(node.findtext("NewPageAfter") == "True" for node in page_breaks)

    for name in ("ScenarioComparisonCell1", "LineAnalysisMaxCell3",
                 "TransformerAnalysisMaxCell3", "VoltageAnalysisMinCell3",
                 "VoltageAnalysisMaxCell3", "RelevantTimePointsCell4"):
        node = root.find(".//" + name)
        assert node.findtext("Brush") == "[255:232:237]"
        assert node.findtext("TextBrush") == "[145:13:48]"
        assert "Bold" in node.findtext("Font")

    voltage_min = root.find(".//AppendixVoltagesCell3/Conditions/value").text
    voltage_max = root.find(".//AppendixVoltagesCell4/Conditions/value").text
    assert "LessThan" in voltage_min and "0_.95" in voltage_min
    assert "GreaterThan" in voltage_max and "1_.05" in voltage_max


def test_time_series_auto_series_can_show_distinct_colours():
    """Auto-series copy the template series. With AllowApplyStyle=False and a
    hard-coded LineColor every case curve would render in the same burgundy."""
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    series = root.find(".//*[@type='Stimulsoft.Report.Chart.StiLineSeries']")
    assert series is not None
    assert series.findtext("AutoSeriesKeyDataColumn") == "ScriptedPlotData.series_role"
    assert series.findtext("AllowApplyStyle") == "True"
    assert series.find("LineColor") is None
    chart = next(
        c for c in root.findall(".//*[@type='Stimulsoft.Report.Chart.StiChart']")
        if c.findtext("Name") == "PlotsChart"
    )
    style = chart.find("Style")
    assert style is not None
    # This is the same built-in style type used by the proven bar charts. With
    # style application enabled and no fixed LineColor, Stimulsoft assigns its
    # palette to the generated auto-series.
    assert style.get("type").endswith("StiStyle29")


def test_bar_charts_are_labelled_with_the_case_id():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    bars = root.findall(".//*[@type='Stimulsoft.Report.Chart.StiClusteredBarSeries']")
    assert bars
    for series in bars:
        argument = series.findtext("ArgumentDataColumn") or ""
        assert argument.endswith(".bar_label"), argument


def test_every_contract_table_declares_its_required_fields():
    """GL-PR-012: the contract must state what may never be empty."""
    declared = {name for name, _ in native.TABLES}
    assert set(native.REQUIRED_FIELDS) == declared
    for name, fields in native.TABLES:
        known = {field for field, _ in fields}
        assert set(native.REQUIRED_FIELDS[name]) <= known, name


def test_a_missing_required_field_is_rejected_before_reset(active_model):
    payload = prepared_payload(active_model)
    del payload["ScriptedLineStatistics"][0]["element_name"]
    report = SQLiteReport()
    try:
        with pytest.raises(ValueError, match="element_name"):
            native.publish_report(report, payload)
        assert report.resets == 0
    finally:
        report.connection.close()


def test_a_null_required_field_is_rejected_before_reset(active_model):
    payload = prepared_payload(active_model)
    payload["ScriptedLineStatistics"][0]["max_loading"] = None
    report = SQLiteReport()
    try:
        with pytest.raises(ValueError, match="max_loading"):
            native.publish_report(report, payload)
        assert report.resets == 0
    finally:
        report.connection.close()


def test_an_empty_required_string_is_rejected(active_model):
    payload = prepared_payload(active_model)
    payload["ScriptedScenarios"][0]["scenario_id"] = "   "
    report = SQLiteReport()
    try:
        with pytest.raises(ValueError, match="scenario_id"):
            native.publish_report(report, payload)
    finally:
        report.connection.close()


def test_an_absent_reference_value_stays_allowed(active_model):
    """Missing reference data must stay null, never become a fake 0.0."""
    payload = prepared_payload(active_model)
    row = payload["ScriptedLineStatistics"][0]
    row["reference_max_loading"] = None
    row["delta_max_loading"] = None
    report = SQLiteReport()
    try:
        native.publish_report(report, payload)
        stored = report.connection.execute(
            'SELECT reference_max_loading FROM "ScriptedLineStatistics"'
        ).fetchone()[0]
        assert stored is None
    finally:
        report.connection.close()


def test_the_timeseries_chart_labels_its_y_axis_with_the_plot_unit():
    """GL-PR-015: one chart may show %, p.u. or deg, so the unit must show."""
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    charts = [node for node in root.iter("PlotsChart")]
    assert len(charts) == 1
    y_axis = charts[0].find("Area/YAxis")
    title = y_axis.find("Title")
    assert title is not None
    assert title.findtext("Text") == "{ScriptedPlots.unit}"


def test_the_timeseries_chart_still_labels_its_x_axis():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    chart = next(node for node in root.iter("PlotsChart"))
    assert chart.find("Area/XAxis/Title").findtext("Text") == "Zeit [h]"


def test_the_contract_no_longer_declares_an_unrendered_reference_table():
    """GL-PR-009: a generated table no band binds is a claim without a page."""
    names = {name for name, _ in native.TABLES}
    assert "ScriptedReferenceComparison" not in names
    assert len(native.TABLES) == 17


def test_no_payload_carries_the_removed_reference_table():
    assert "ScriptedReferenceComparison" not in native.empty_payload()


def test_the_template_declares_the_versions_the_runtime_expects():
    """GL-PR-013: template and runtime must name the same release."""
    text = (DEPLOYMENT / "MASTER_GRIDLENS.mrt").read_text(encoding="utf-8")
    assert "Template {}; data contract {}.".format(
        native.TEMPLATE_VERSION, native.DATA_CONTRACT_VERSION) in text


def test_the_reference_delta_is_still_rendered_by_the_statistics_tables():
    """Removing the duplicate must not remove the comparison itself."""
    text = (DEPLOYMENT / "MASTER_GRIDLENS.mrt").read_text(encoding="utf-8")
    for expression in (
        "{ScriptedLineStatistics.delta_max_loading}",
        "{ScriptedTransformerStatistics.delta_max_loading}",
    ):
        assert expression in text


class CodeReport(SQLiteReport):
    """IntReport double that answers one call with a PowerFactory error code."""

    def __init__(self, failing=None, code=1):
        super().__init__()
        self.failing = failing
        self.code = code

    def CreateTable(self, name):
        super().CreateTable(name)
        return self.code if self.failing == "CreateTable" else None

    def CreateField(self, table, name, field_type):
        super().CreateField(table, name, field_type)
        return self.code if self.failing == "CreateField" else None

    def SetValue(self, table, field, row, value):
        super().SetValue(table, field, row, value)
        return self.code if self.failing == "SetValue" else None


def test_a_successful_publication_ignores_empty_api_returns(active_model):
    report = CodeReport()
    try:
        native.publish_report(report, prepared_payload(active_model))
        assert len(report.tables) == len(native.TABLES)
    finally:
        report.connection.close()


def test_an_object_handle_return_is_not_mistaken_for_an_error(active_model):
    """CreateTable may hand back the created object, which is not a code."""
    report = CodeReport(failing="CreateTable", code=object())
    try:
        native.publish_report(report, prepared_payload(active_model))
        assert len(report.tables) == len(native.TABLES)
    finally:
        report.connection.close()


@pytest.mark.parametrize("call", ["CreateTable", "CreateField", "SetValue"])
def test_a_non_zero_api_code_stops_the_publication(active_model, call):
    """The review requires these return codes to be evaluated, not ignored."""
    report = CodeReport(failing=call, code=1)
    try:
        with pytest.raises(RuntimeError, match=call):
            native.publish_report(report, prepared_payload(active_model))
        assert report.resets == 2
    finally:
        report.connection.close()


def test_api_error_code_reads_only_real_numeric_failures():
    assert native.api_error_code(None) is None
    assert native.api_error_code(0) is None
    assert native.api_error_code("Tabelle") is None
    assert native.api_error_code(1) == 1.0
    assert native.api_error_code((2, "Fehler")) == 2.0


def test_label_and_free_text_fields_have_different_limits():
    assert native.text_limit("element_name") == native.MAX_LABEL_LENGTH
    assert native.text_limit("bar_label") == native.MAX_LABEL_LENGTH
    assert native.text_limit("unit") == native.MAX_LABEL_LENGTH
    assert native.text_limit("message") == native.MAX_TEXT_LENGTH
    assert native.text_limit("description") == native.MAX_TEXT_LENGTH
    assert native.MAX_LABEL_LENGTH < native.MAX_TEXT_LENGTH


def test_a_short_name_passes_through_unchanged(active_model):
    payload = prepared_payload(active_model)
    report = SQLiteReport()
    try:
        native.publish_report(report, payload)
        name = report.connection.execute(
            'SELECT element_name FROM "ScriptedLineStatistics"'
        ).fetchone()[0]
        assert name == "Line A"
    finally:
        report.connection.close()


def test_an_overlong_label_is_clipped_before_it_reaches_the_report(active_model):
    """Unbounded names break the table layout and the chart legend."""
    payload = prepared_payload(active_model)
    payload["ScriptedLineStatistics"][0]["element_name"] = "L" * 400
    native.validate_payload(payload)
    clipped = payload["ScriptedLineStatistics"][0]["element_name"]
    assert len(clipped) == native.MAX_LABEL_LENGTH


def test_two_different_overlong_names_stay_different(active_model):
    """Clipping must not merge two physically separate elements."""
    first = native.clip_text("Leitung " + "A" * 300 + " Nord", 80)
    second = native.clip_text("Leitung " + "A" * 300 + " Sued", 80)
    assert first != second
    assert len(first) == len(second) == 80


def test_free_text_keeps_more_room_than_a_label():
    message = "Meldung " * 200
    assert len(native.clip_text(message, native.MAX_TEXT_LENGTH)) == (
        native.MAX_TEXT_LENGTH)
    assert len(native.clip_text("kurz", native.MAX_TEXT_LENGTH)) == 4


CHART_FLAGS = {
    "LineLoadingBarChartBand": ("has_line_bars", "ScriptedLineLoadingBars"),
    "TransformerLoadingBarChartBand": (
        "has_transformer_bars", "ScriptedTransformerLoadingBars"),
    "VoltageMagnitudeBarChartBand": (
        "has_voltage_bars", "ScriptedVoltageMagnitudeBars"),
    "VoltageAngleBarChartBand": ("has_angle_bars", "ScriptedVoltageAngleBars"),
    "PlotsPageBreakBand": (None, None),
}


def decode_filter(value):
    """Undo the Stimulsoft XML name encoding used in Filters values."""
    import re
    return re.sub(r"_x([0-9A-Fa-f]{4})_",
                  lambda m: chr(int(m.group(1), 16)), value)


def test_report_meta_declares_a_render_flag_for_every_chart():
    """GL-PR-015: an empty chart must not be drawn as a blank frame."""
    fields = dict(dict(native.TABLES)["ScriptedReportMeta"])
    for flag, _ in CHART_FLAGS.values():
        if flag:
            assert fields.get(flag) == "string", flag


def test_each_chart_band_is_filtered_by_its_own_render_flag():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    for band_name, (flag, _) in CHART_FLAGS.items():
        if not flag:
            continue
        band = next(node for node in root.iter(band_name))
        assert band.findtext("DataSourceName") == "ScriptedReportMeta"
        values = [decode_filter(v.text) for v in band.findall("Filters/value")]
        assert values == ['ScriptedReportMeta.{} == "1"'.format(flag)], band_name


def test_a_chart_flag_is_one_when_the_table_has_rows(active_model):
    payload = prepared_payload(active_model)
    meta = payload["ScriptedReportMeta"][0]
    assert payload["ScriptedLineLoadingBars"]
    assert meta["has_line_bars"] == "1"


def test_a_chart_flag_is_zero_when_the_table_is_empty(active_model):
    _, _, result = active_model
    result.columns = result.columns[:6]
    result.values = (
        (0.0, 90.0, 60.0, 80.0, 1.00, 1.01),
        (1.0, 99.0, 70.0, 95.0, 0.95, 1.05),
        (2.0, 95.0, 65.0, 99.0, 0.99, 1.02),
    )
    payload = prepared_payload(active_model)
    meta = payload["ScriptedReportMeta"][0]
    assert payload["ScriptedVoltageAngleBars"] == []
    assert meta["has_angle_bars"] == "0"
    assert payload["ScriptedLineLoadingBars"] == []
    assert meta["has_line_bars"] == "0"


def test_the_mrt_source_declares_the_render_flags():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    source = next(n for n in root.iter("ScriptedReportMeta")
                  if n.findtext("Name") == "ScriptedReportMeta")
    columns = {v.text.split(",", 1)[0] for v in source.findall("Columns/value")}
    for flag, _ in CHART_FLAGS.values():
        if flag:
            assert flag in columns


def test_status_and_quality_bands_are_never_filtered():
    """A failed case must stay visible even when no element is critical.

    The critical-only rule governs which elements reach the limit tables. It
    must never decide whether the reader learns that a case failed.
    """
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    for band_name, source in (
        ("ScenariosDataBand", "ScriptedScenarios"),
        ("ModelQualityDataBand", "ScriptedModelQuality"),
        ("OutagesDataBand", "ScriptedOutages"),
        ("ScenarioMatrixDataBand", "ScriptedScenarioMatrix"),
    ):
        band = next(node for node in root.iter(band_name))
        assert band.findtext("DataSourceName") == source
        assert band.findall("Filters/value") == [], band_name


def test_a_failed_case_reaches_the_status_tables_without_any_element(active_model):
    payload = prepared_payload(active_model)
    payload["ScriptedScenarios"].append({
        "scenario_id": "S09", "scenario_name": "Abgebrochen",
        "is_reference": 0, "description": "",
        "simulation_status": "NICHT KONVERGIERT",
        "simulation_start": "", "simulation_end": "",
    })
    report = SQLiteReport()
    try:
        native.publish_report(report, payload)
        rows = report.connection.execute(
            'SELECT simulation_status FROM "ScriptedScenarios" '
            'WHERE scenario_id = "S09"').fetchall()
        assert [row[0] for row in rows] == ["NICHT KONVERGIERT"]
    finally:
        report.connection.close()


def test_every_declared_list_count_matches_its_children():
    """Stimulsoft stores an explicit count on each list; a stale one is a
    silent inconsistency that XML validity alone never reveals."""
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    stale = [
        (node.tag, node.get("count"), len(list(node)))
        for node in root.iter()
        if node.get("isList") == "true" and node.get("count") is not None
        and int(node.get("count")) != len(list(node))
    ]
    assert stale == []


def test_the_data_source_list_counts_the_contract_tables():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    sources = root.find("Dictionary/DataSources")
    assert int(sources.get("count")) == len(native.TABLES)
