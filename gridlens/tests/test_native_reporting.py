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

import gridlens_pf as native  # noqa: E402


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


def test_runtime_package_is_self_contained_and_has_no_mock_input():
    """The deployment must run on the standard library plus powerfactory."""
    entry = DEPLOYMENT / "gridlens_report.py"
    package = DEPLOYMENT / "gridlens_pf"
    assert entry.is_file()
    assert package.is_dir()
    assert {path.name for path in DEPLOYMENT.iterdir() if path.is_file()} == {
        "MASTER_GRIDLENS.mrt", "README.md", "gridlens_report.py"
    }

    allowed = {"math", "os", "sys", "datetime", "powerfactory"}
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

    assert native.PUBLISHER_VERSION == "4.0.0"
    assert native.TEMPLATE_VERSION == "2.1.0"
    assert native.DATA_CONTRACT_VERSION == "2.1"


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
    assert payload["ScriptedReferenceComparison"] == []
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
        assert len(report.tables) == 18
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
    result.values = (
        (0.0, 90.0, 60.0, 80.0, 1.00, 1.01),
        (1.0, 99.0, 70.0, 95.0, 0.95, 1.05),
        (2.0, 95.0, 65.0, 99.0, 0.99, 1.02),
    )
    payload = prepared_payload(active_model)
    for table in (
        "ScriptedLineStatistics", "ScriptedTransformerStatistics",
        "ScriptedVoltageStatistics", "ScriptedReferenceComparison",
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
        assert len(report.tables) == 18
        assert "GridLens publisher: 4.0.0" in messages
        assert "GridLens mode: report" in messages
        assert messages[-1] == "GridLens: 18 Tabellen publiziert."
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
