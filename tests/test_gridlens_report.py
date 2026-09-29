from __future__ import annotations

import importlib.util
import re
import sqlite3
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "powerfactory" / "gridlens_report.py"
SPEC = importlib.util.spec_from_file_location("gridlens_report", SCRIPT)
gl = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gl)


@pytest.fixture(autouse=True)
def _assess_every_element(monkeypatch):
    """Fake elements belong to no grid; only the scope tests use D7."""
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "")


class PFObject:
    def __init__(self, name, kind, **attributes):
        self.loc_name = name
        self.kind = kind
        self.desc = attributes.pop("desc", "")
        self.__dict__.update(attributes)

    def GetClassName(self):
        return self.kind

    def GetFullName(self):
        return "Project\\{}\\{}.{}".format(self.kind, self.loc_name, self.kind)

    def GetContents(self, *_args):
        return []


# The acceptance project's first outage: 2014-01-01 00:00:00 to 23:59:59 local.
OUTAGE_START = 1388530800
OUTAGE_END = 1388617199
# ComStatsim declares 2014-01-01 00:00 to 2014-01-05 00:00 for that project.
PERIOD_START = 1388530800
PERIOD_END = 1388876400


class PlannedOutage(PFObject):
    """IntPlannedout as PowerFactory 2026 exposes it: data, no Apply method."""

    def __init__(self, name, *, disabled=False, equipment=None,
                 starttime=OUTAGE_START, endtime=OUTAGE_END):
        super().__init__(name, "IntPlannedout", outserv=1 if disabled else 0)
        self.starttime = starttime
        self.endtime = endtime
        self.priority = 1
        self.components = list(equipment or ())


class ElmRes(PFObject):
    def __init__(self, name="Configured QDS Result"):
        super().__init__(name, "ElmRes")
        self.deleted = False
        self.time = PFObject("Time", "SetTime")
        self.line = PFObject("Line A", "ElmLne", outserv=0, uknom=110)
        self.term = PFObject("Bus A", "ElmTerm", outserv=0, uknom=110)
        self.variables = ("b:tnow", "c:loading", "m:u", "m:phiu")
        self.objects = (self.time, self.line, self.term, self.term)
        self.units = ("h", "%", "p.u.", "deg")
        self.columns = ([0.0, 1.0], [90.0, 110.0], [0.96, 0.94], [0.0, 2.0])

    def clone(self):
        return ElmRes(self.loc_name)

    def Load(self):
        return None

    def Release(self):
        return None

    def Delete(self):
        self.deleted = True
        return None

    def GetNumberOfRows(self):
        return 2

    def GetNumberOfColumns(self):
        return len(self.columns)

    def GetVariable(self, column):
        return self.variables[column]

    def GetObject(self, column):
        return self.objects[column]

    def GetUnit(self, column):
        return self.units[column]

    def GetColumnValues(self, column):
        return self.columns[column]

    def FindColumn(self, variable):
        return self.variables.index(variable)


class ImplicitTimeElmRes(ElmRes):
    """QDS result whose time scale is addressed through column -1."""

    def __init__(self):
        super().__init__()
        self.variables = ("c:loading", "m:u", "m:phiu")
        self.objects = (self.line, self.term, self.term)
        self.units = ("%", "p.u.", "deg")
        self.columns = ([90.0, 110.0], [0.96, 0.94], [0.0, 2.0])
        self.scale = [0.0, 1.0]

    def GetValue(self, row, column):
        if column == -1:
            return self.scale[row]
        return self.columns[column][row]

    def GetUnit(self, column):
        if column == -1:
            return "h"
        return super().GetUnit(column)

    def GetColumnValues(self, *_args):
        raise TypeError("PowerFactory requires an IntVec argument")

    def FindColumn(self, *_args):
        return -1


class StudyCase(PFObject):
    def __init__(self):
        super().__init__("Study", "IntCase")
        self.copies = []

    def AddCopy(self, result):
        copy = result.clone()
        self.copies.append(copy)
        return copy


class StudyTime(PFObject):
    def __init__(self):
        super().__init__("Study Time", "SetTime", cDate=20140501, cTime=0)


class QDS(PFObject):
    def __init__(self, result, study_time, failure=None):
        super().__init__(
            "Configured QDS", "ComStatsim", results=result,
            calcPeriod=2, stepSize=1, stepUnit=2,
            iopt_net=0, iopt_at=1, iopt_maint=0,
            startTime=PERIOD_START, endTime=PERIOD_END,
        )
        self.study_time = study_time
        self.failure = failure
        self.execute_calls = 0
        self.start_times = []
        self.outage_options = []

    def Execute(self):
        self.execute_calls += 1
        self.start_times.append((self.study_time.cDate, self.study_time.cTime))
        self.outage_options.append(self.iopt_maint)
        self.study_time.cDate = 20140531
        self.study_time.cTime = 23000000
        if self.failure:
            raise self.failure
        return 0


class Report(PFObject):
    def __init__(self):
        super().__init__("GridLens", "IntReport")
        self.reset_calls = 0
        self.tables = {}

    def Reset(self):
        self.reset_calls += 1
        self.tables = {}

    def CreateTable(self, name):
        self.tables[name] = {"fields": {}, "values": {}}

    def CreateField(self, table, field, field_type):
        self.tables[table]["fields"][field] = field_type

    def SetValue(self, table, field, row, value):
        self.tables[table]["values"][row, field] = value


class Script(PFObject):
    def __init__(self, parent):
        super().__init__("Run GridLens", "ComPython")
        self.parent = parent

    def GetParent(self):
        return self.parent


class App:
    def __init__(self, outages=(), qds_failure=None):
        self.study = StudyCase()
        self.report = Report()
        self.script = Script(self.report)
        self.original_result = ElmRes()
        self.study_time = StudyTime()
        self.qds = QDS(self.original_result, self.study_time, qds_failure)
        self.project = PFObject("Model", "IntPrj")
        self.outage_folder = PFObject("Outages", "IntPrjfolder")
        self.outages = list(outages)
        self.messages = []
        self.outage_folder.GetContents = self._outage_contents
        self.project.GetContents = self._outage_contents

    def _outage_contents(self, pattern, *_args):
        return [item for item in self.outages if pattern.endswith(item.kind)]

    def PrintPlain(self, message):
        self.messages.append(message)

    def GetCurrentScript(self):
        return self.script

    def GetActiveStudyCase(self):
        return self.study

    def GetActiveProject(self):
        return self.project

    def GetProjectFolder(self, key):
        return self.outage_folder if key == "outage" else None

    def GetFromStudyCase(self, name):
        if name == "ComStatsim":
            return self.qds
        if name == "SetTime":
            return self.study_time
        return None

    def GetCalcRelevantObjects(self, _pattern, *_args):
        return []


def test_table_contract_is_single_versioned_24_table_contract():
    assert gl.PUBLISHER_VERSION == "5.4.1"
    assert gl.TEMPLATE_VERSION == "3.4.0"
    assert gl.DATA_CONTRACT_VERSION == "3.4"
    assert len(gl.TABLES) == 24
    tables = dict(gl.TABLES)
    assert "ScriptedCases" in tables
    assert "ScriptedPlannedOutages" in tables
    assert "ScriptedCaseMatrix" in tables
    assert "generated_by" in dict(tables["ScriptedReportMeta"])
    assert "run_mode" in dict(tables["ScriptedReportMeta"])


def test_reference_runs_without_and_outage_run_with_planned_outages(monkeypatch):
    app = App((PlannedOutage("Outage A"), PlannedOutage("Outage B")))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)
    monkeypatch.setattr(gl.getpass, "getuser", lambda: "operator")

    counts = gl.execute_gridlens(app)

    assert app.qds.execute_calls == 2
    # The reference must be free of planned outages, the second run must not.
    assert app.qds.outage_options == [0, 1]
    assert app.qds.iopt_maint == 0, "the original option value must come back"
    assert app.qds.start_times == [(20140501, 0), (20140501, 0)]
    assert app.qds.results is app.original_result
    assert all(copy.deleted for copy in app.study.copies)
    assert (app.study_time.cDate, app.study_time.cTime) == (20140501, 0)
    assert app.report.reset_calls == 1
    assert counts["ScriptedCases"] == 2
    assert counts["ScriptedPlannedOutages"] == 2
    values = app.report.tables["ReportMeta"]["values"]
    assert values[0, "generated_by"] == "operator"
    assert values[0, "run_mode"] == "REFERENCE + PLANNED OUTAGES"
    assert any("blocking API call may take several minutes" in line
               for line in app.messages)
    assert any("Time period [calcPeriod] = 2" in line for line in app.messages)
    assert any("Step size [stepSize] = 1" in line for line in app.messages)
    assert any("Step unit [stepUnit] = 2" in line for line in app.messages)
    assert any("Calculation options: iopt_at=1, iopt_maint=0, iopt_net=0" in line
               for line in app.messages)
    assert any("Planned outages [iopt_maint] = 0" in line for line in app.messages)
    assert any("Simulated period [startTime..endTime] = 2014-01-01" in line
               for line in app.messages)
    assert any("Initial Study Case time: 2014-05-01 00:00:00" in line
               for line in app.messages)


def test_direct_mode_with_no_outage_in_scope_does_not_calculate(monkeypatch):
    app = App((PlannedOutage("Disabled", disabled=True),))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", False)

    counts = gl.execute_gridlens(app)

    assert app.qds.execute_calls == 0
    assert app.qds.results is app.original_result
    assert app.qds.iopt_maint == 0
    assert counts["ScriptedCases"] == 0
    assert counts["ScriptedPlannedOutages"] == 1
    values = app.report.tables["ReportMeta"]["values"]
    assert values[0, "run_mode"] == (
        "NO CALCULATION - NO PLANNED OUTAGE IN THE SIMULATED PERIOD")


def test_calculation_failure_still_restores_option_and_result_binding(monkeypatch):
    app = App((PlannedOutage("Outage"),), qds_failure=RuntimeError("solver stopped"))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", False)

    with pytest.raises(gl.GridLensError, match="solver stopped"):
        gl.execute_gridlens(app)

    assert app.qds.iopt_maint == 0
    assert app.qds.results is app.original_result
    assert (app.study_time.cDate, app.study_time.cTime) == (20140501, 0)
    assert all(copy.deleted for copy in app.study.copies)
    assert app.report.reset_calls == 0


def test_production_script_has_no_obsolete_runtime_dependencies():
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "gridlens_pf", "IntScenario", "IntScheme", "GetActiveScenario",
        "SCAN_VARIATIONS", ".Activate(", ".Deactivate(", "traceback",
    )
    assert not [value for value in forbidden if value in text]


def test_user_facing_runtime_text_is_english():
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "Zeitachse", "Auslastung", "Spannung", "Referenzfall",
        "Grenzwert", "Nicht konvergiert", "Freischaltung", "Ergebnisreihe",
    )
    assert not [value for value in forbidden if value in text]


def test_qds_result_reads_implicit_time_scale_from_column_minus_one():
    series, labels, plot_times, time_unit, absolute, _ = gl.collect_series(
        ImplicitTimeElmRes())

    assert absolute is False
    assert labels == ["00:00", "01:00"]
    assert plot_times == [0.0, 1.0]
    assert time_unit == "h"
    assert {item["category"] for item in series} == {
        "line", "voltage", "voltage_angle",
    }


def test_friendly_exception_respects_suppressed_context():
    try:
        try:
            raise RuntimeError("low-level failure")
        except RuntimeError:
            raise gl.GridLensError("Readable operator message") from None
    except gl.GridLensError as exc:
        message = gl._friendly_exception(exc)

    assert message == "GridLensError: Readable operator message"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None), (True, None), (False, None), (float("nan"), None),
        (float("inf"), None), ("", None), ("1,25", 1.25), ("2.5", 2.5),
        (7, 7.0), ((0, 5), None),
    ],
)
def test_finite_number_rejects_special_and_ambiguous_values(value, expected):
    assert gl.finite_number(value) == expected


@pytest.mark.parametrize(
    ("returned", "expected"),
    [(None, 0.0), (0, 0.0), ((0, "detail"), 0.0), (3, 3.0), ([], None)],
)
def test_powerfactory_return_code_normalization(returned, expected):
    assert gl.return_code(returned) == expected


def _series(category, key, values):
    kind = {"line": "ElmLne", "transformer": "ElmTr2",
            "voltage": "ElmTerm", "voltage_angle": "ElmTerm"}[category]
    obj = PFObject(key, kind, uknom=110)
    variable = {"line": "c:loading", "transformer": "c:loading",
                "voltage": "m:u", "voltage_angle": "m:phiu"}[category]
    unit = "%" if category in ("line", "transformer") else (
        "p.u." if category == "voltage" else "deg")
    return {
        "category": category, "object": obj, "key": obj.GetFullName(),
        "element_id": key, "element_name": key, "voltage_level": "110 kV",
        "variable_id": variable, "variable": variable, "unit": unit,
        "points": [("00:00", 0.0, values[0]), ("01:00", 1.0, values[1])],
    }


def test_thresholds_are_strict_at_exact_limits():
    line = _series("line", "Line", [99.0, 100.0])
    voltage = _series("voltage", "Bus", [0.95, 1.05])
    assert gl.is_critical(line, gl.statistics(line)) is False
    assert gl.is_critical(voltage, gl.statistics(voltage)) is False
    line["points"][1] = ("01:00", 1.0, 100.0001)
    voltage["points"][0] = ("00:00", 0.0, 0.9499)
    assert gl.is_critical(line, gl.statistics(line)) is True
    assert gl.is_critical(voltage, gl.statistics(voltage)) is True


def test_reference_delta_requires_same_internal_object_key():
    reference_item = _series("line", "Shared name", [80.0, 90.0])
    outage_item = _series("line", "Shared name", [90.0, 110.0])
    outage_item["key"] = "Project\\Other\\Shared name.ElmLne"
    reference = gl.case_result(
        {"id": "REF", "name": "Reference", "out_of_service": []},
        [reference_item], ["00:00", "01:00"], [0.0, 1.0], "h")
    outage = gl.case_result(
        {"id": "OUTAGE", "name": "Outage", "out_of_service": []},
        [outage_item], ["00:00", "01:00"], [0.0, 1.0], "h")

    gl.apply_reference([reference, outage])

    stats = outage["by_category"]["line"][0][1]
    assert stats["ref_max"] is None
    assert stats["delta_max"] is None


def test_outages_are_classified_against_the_simulated_period():
    inside = PlannedOutage("Inside")
    before = PlannedOutage("Before", starttime=PERIOD_START - 172800,
                           endtime=PERIOD_START - 3600)
    after = PlannedOutage("After", starttime=PERIOD_END + 3600,
                          endtime=PERIOD_END + 172800)
    disabled = PlannedOutage("Disabled", disabled=True)
    app = App((inside, before, after, disabled))

    records, candidates = gl.classify_planned_outages(
        app, gl.RunLogger(app), (PERIOD_START, PERIOD_END))

    assert [record["name"] for record in candidates] == ["Inside"]
    statuses = {record["name"]: (record["status"], record["skip_reason"])
                for record in records}
    assert statuses["Inside"] == (gl.OUTAGE_CONSIDERED, "")
    assert "disabled" in statuses["Disabled"][1]
    assert "outside the simulated period" in statuses["Before"][1]
    assert "outside the simulated period" in statuses["After"][1]


def test_outage_touching_the_period_boundary_stays_in_scope():
    touching = PlannedOutage("Touching", starttime=PERIOD_END,
                             endtime=PERIOD_END + 86400)
    app = App((touching,))

    _, candidates = gl.classify_planned_outages(
        app, gl.RunLogger(app), (PERIOD_START, PERIOD_END))

    assert [record["name"] for record in candidates] == ["Touching"]


def test_unknown_period_keeps_every_enabled_outage_in_scope():
    app = App((PlannedOutage("Enabled"), PlannedOutage("Disabled", disabled=True)))

    records, candidates = gl.classify_planned_outages(app, gl.RunLogger(app))

    assert [record["name"] for record in candidates] == ["Enabled"]
    statuses = {record["name"]: record["status"] for record in records}
    assert statuses == {"Enabled": gl.OUTAGE_CONSIDERED,
                        "Disabled": gl.OUTAGE_SKIPPED}


def test_outage_without_a_readable_window_is_reported_with_its_surface():
    unreadable = PlannedOutage("Unreadable")
    del unreadable.starttime
    del unreadable.endtime
    app = App((unreadable,))

    records, candidates = gl.classify_planned_outages(
        app, gl.RunLogger(app), (PERIOD_START, PERIOD_END))

    assert [record["name"] for record in candidates] == ["Unreadable"]
    assert "could not be compared" in records[0]["skip_reason"]
    diagnostics = [line for line in app.messages if "DIAGNOSTIC" in line]
    assert len(diagnostics) == 1
    assert "class=IntPlannedout" in diagnostics[0]


def test_outage_in_scope_produces_no_diagnostic_noise():
    app = App((PlannedOutage("Inside"),))

    gl.classify_planned_outages(app, gl.RunLogger(app), (PERIOD_START, PERIOD_END))

    assert [line for line in app.messages if "DIAGNOSTIC" in line] == []


def test_duplicate_outage_names_receive_distinct_short_ids():
    first = PlannedOutage("Duplicate")
    second = PlannedOutage("Duplicate")
    second.GetFullName = lambda: "Project\\Other\\Duplicate.IntPlannedout"
    app = App((first, second))

    records, _ = gl.classify_planned_outages(app, gl.RunLogger(app))

    assert len({record["id"] for record in records}) == 2
    assert all(record["id"].startswith("Duplicate (") for record in records)


def test_complete_outage_discovery_failure_is_not_reported_as_empty():
    app = App(())
    app.outage_folder.GetContents = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("folder unavailable"))
    app.project.GetContents = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("project unavailable"))

    with pytest.raises(gl.GridLensError, match="discovery could not query"):
        gl.classify_planned_outages(app, gl.RunLogger(app))


def test_equipment_is_read_from_the_components_attribute():
    line = PFObject("Line 09 - 39", "ElmLne", outserv=0)
    outage = PlannedOutage("Line 04 - 14", equipment=[line])

    equipment, kinds, _, start, end = gl._outage_details(outage)

    assert equipment == "Line 09 - 39"
    assert kinds == "ElmLne"
    assert start.startswith("2014-01-01")
    assert end.startswith("2014-01-01")


def test_qds_period_is_read_from_the_command():
    app = App(())

    assert gl.qds_period(app.qds) == (float(PERIOD_START), float(PERIOD_END))

    del app.qds.startTime
    assert gl.qds_period(app.qds) == (None, None)


def test_payload_validation_rejects_unknown_fields_and_booleans():
    payload = {name: [] for name, _ in gl.TABLES}
    payload["ScriptedReportMeta"] = [{
        "study_id": "S", "study_name": "S", "model_name": "M",
        "model_version": "PowerFactory 2026", "generation_date": "now",
        "generated_by": "user", "run_mode": "test",
        "template_name": gl.TEMPLATE_NAME,
        "template_version": gl.TEMPLATE_VERSION,
        "data_contract_version": gl.DATA_CONTRACT_VERSION,
        "result_name": "R", "assessment_scope": "test",
        "assessment_status": "test", "has_line_bars": "0",
        "has_transformer_bars": "0", "has_voltage_bars": "0",
        "has_angle_bars": "0", "unknown": "bad",
    }]
    with pytest.raises(ValueError, match="unknown fields"):
        gl.validate_payload(payload)
    payload["ScriptedReportMeta"][0].pop("unknown")
    payload["ScriptedCases"] = [{
        "case_id": "REF", "case_name": "Reference",
        "is_reference": True, "simulation_status": "CONVERGED",
    }]
    with pytest.raises(ValueError, match="boolean"):
        gl.validate_payload(payload)


class HostileObject(PFObject):
    """Outage whose attribute access fails the way a broken proxy would."""

    def __init__(self):
        super().__init__("Hostile", "IntPlannedout", outserv=0)

    def __getattr__(self, name):
        raise RuntimeError("attribute access exploded: " + name)


def test_api_description_separates_methods_from_parameters():
    description = gl.describe_object_api(PlannedOutage("Probe"))

    assert "class=IntPlannedout" in description
    methods, parameters = description.split("parameters:")
    assert "GetClassName" in methods
    assert "starttime" in parameters
    assert "endtime" in parameters
    assert "priority" in parameters
    assert "outserv" in parameters


def test_api_description_omits_methods_powerfactory_does_not_expose():
    # PowerFactory 2026 offers no Apply, Reset or Check on IntPlannedout.
    methods = gl.describe_object_api(
        PlannedOutage("Probe")).split("parameters:")[0]

    assert "Apply" not in methods
    assert "Reset" not in methods
    assert "IsInStudyTime" not in methods


def test_api_description_survives_objects_that_raise_on_access():
    description = gl.describe_object_api(HostileObject())

    assert isinstance(description, str)
    assert description


def test_api_description_reports_powerfactory_declared_attributes():
    outage = PlannedOutage("Probe")
    outage.GetAttributeNames = lambda: ["tEnd", "outserv"]
    outage.tEnd = 20140102

    description = gl.describe_object_api(outage)

    assert "declared attributes: outserv=0, tEnd=20140102" in description


def test_api_description_is_bounded_for_the_output_window():
    outage = PlannedOutage("Probe")
    for index in range(400):
        setattr(outage, "parameter_with_a_long_name_{}".format(index), index)

    assert len(gl.describe_object_api(outage)) <= gl.MAX_DIAGNOSTIC_LENGTH


def test_extraction_logs_the_time_axis_span(monkeypatch):
    app = App((PlannedOutage("Applicable"),))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)

    gl.execute_gridlens(app)

    spans = [line for line in app.messages if "Time axis" in line]
    assert spans
    assert "unit 'h'" in spans[0]
    assert "first 00:00" in spans[0]
    assert "last 01:00" in spans[0]


EPOCH_2014_06_15_12_UTC = 1402833600.0


class EpochTimeElmRes(ElmRes):
    """QDS result whose implicit time scale holds absolute epoch seconds.

    This is what PowerFactory 2026 returns for a quasi-dynamic run: the unit
    reads 's', but the values are not elapsed time since the simulation start.
    """

    def __init__(self, points=48):
        super().__init__()
        self.points = points
        self.variables = ("c:loading", "m:u", "m:phiu")
        self.objects = (self.line, self.term, self.term)
        self.units = ("%", "p.u.", "deg")
        self.scale = [EPOCH_2014_06_15_12_UTC + 3600.0 * index
                      for index in range(points)]
        self.columns = (
            [90.0 + index for index in range(points)],
            [0.96 for _ in range(points)],
            [0.0 for _ in range(points)],
        )

    def clone(self):
        return EpochTimeElmRes(self.points)

    def GetNumberOfRows(self):
        return self.points

    def GetValue(self, row, column):
        if column == -1:
            return self.scale[row]
        return self.columns[column][row]

    def GetUnit(self, column):
        return "s" if column == -1 else super().GetUnit(column)

    def GetColumnValues(self, *_args):
        raise TypeError("PowerFactory requires an IntVec argument")

    def FindColumn(self, *_args):
        return -1


def test_absolute_epoch_axis_is_detected():
    assert gl.is_absolute_time_axis([385703.0, 385704.0]) is True
    assert gl.is_absolute_time_axis([0.0, 1.0, 47.0]) is False
    assert gl.is_absolute_time_axis([]) is False


def test_epoch_axis_is_labelled_as_a_calendar_time():
    _, labels, _, _, absolute, _ = gl.collect_series(EpochTimeElmRes())

    assert absolute is True
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", labels[0])
    assert labels[0].startswith("2014-06-")
    assert "d " not in labels[0]


def test_epoch_axis_plot_times_are_relative_to_the_first_sample():
    _, _, plot_times, _, _, origin = gl.collect_series(EpochTimeElmRes())

    assert plot_times[0] == 0.0
    assert plot_times[-1] == pytest.approx(47.0)
    assert origin == pytest.approx(EPOCH_2014_06_15_12_UTC / 3600.0)


def test_relative_axis_keeps_elapsed_clock_labels():
    _, labels, plot_times, _, absolute, origin = gl.collect_series(ElmRes())

    assert absolute is False
    assert origin is None
    assert labels == ["00:00", "01:00"]
    assert plot_times == [0.0, 1.0]


def test_epoch_axis_span_is_reported_in_hours(monkeypatch):
    app = App((PlannedOutage("Applicable"),))
    app.original_result = EpochTimeElmRes()
    app.qds.startTime = EPOCH_2014_06_15_12_UTC
    app.qds.endTime = EPOCH_2014_06_15_12_UTC + 47 * 3600
    app.qds.results = app.original_result
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)

    gl.execute_gridlens(app)

    spans = [line for line in app.messages if "Time axis" in line]
    assert spans
    assert "span 47 h" in spans[0]
    assert "absolute" in spans[0]


def test_api_description_reads_attributes_through_getattributes():
    outage = PlannedOutage("Probe")
    outage.GetAttributes = lambda: ["tStart", "outserv"]
    outage.tStart = 20140101

    description = gl.describe_object_api(outage)

    assert "tStart=20140101" in description
    assert "outserv=0" in description


def test_study_time_renders_powerfactory_six_digit_clock():
    # PowerFactory stores SetTime.cTime as HHMMSS, so 230000 is 23:00:00.
    assert gl._format_study_time(20140102, 230000) == "2014-01-02 23:00:00"
    assert gl._format_study_time(20140102, 93000) == "2014-01-02 09:30:00"
    assert gl._format_study_time(20140102, 0) == "2014-01-02 00:00:00"
    assert gl._format_study_time("20140102", "230000") == "2014-01-02 23:00:00"


def test_study_time_rendering_survives_unreadable_values():
    assert "date=" in gl._format_study_time(None, 230000)


def test_outage_times_are_rendered_compactly_for_the_report():
    # The report cell is 3.1 cm wide; ISO with a timezone offset does not fit,
    # and the time-axis labels already read this way.
    assert gl._format_pf_time(OUTAGE_START) == "2014-01-01 00:00"
    assert gl._format_pf_time(OUTAGE_END) == "2014-01-01 23:59"


def test_outage_time_rendering_leaves_other_values_alone():
    assert gl._format_pf_time("2014-01-01") == "2014-01-01"
    assert gl._format_pf_time(None) == ""
    assert gl._format_pf_time(42) == "42"


def _window_series(category, name, unit, window_stats):
    item = {'category': category, 'key': name, 'element_id': name,
            'element_name': name, 'voltage_level': '345 kV', 'unit': unit,
            'variable': 'Loading', 'points': [('t', 0.0, 1.0)],
            'windows': window_stats}
    stats = {'min': 1.0, 'max': 1.0, 'mean': 1.0, 'p95': 1.0,
             'time_min': 't', 'time_max': 't'}
    for reference_key, delta_key, _ in gl.DELTA_KEYS:
        stats[reference_key] = None
        stats[delta_key] = None
    return item, stats


def _window_case(case_id, series):
    by_category = {category: [] for category in gl.VARIABLES}
    for item, stats in series:
        by_category[item['category']].append((item, stats))
    return {'id': case_id, 'name': case_id, 'kind': 'case', 'description': '',
            'status': gl.CONVERGED, 'error_code': 0, 'message': '',
            'out_of_service': [], 'is_reference': 1 if case_id == 'REF' else 0,
            'labels': ['t'], 'plot_times': [0.0], 'time_unit': 'h',
            'by_category': by_category, 'stats_by_key': {},
            'window': (None, None)}


def _window(minimum, maximum, time_max='2014-01-01 08:00'):
    return {'min': minimum, 'max': maximum, 'mean': (minimum + maximum) / 2,
            'time_min': '2014-01-01 03:00', 'time_max': time_max}


def test_window_statistics_are_confined_to_their_own_rows():
    values = [10.0, 20.0, 99.0, 30.0, 40.0]
    labels = ["h0", "h1", "h2", "h3", "h4"]
    hours = [0.0, 1.0, 2.0, 3.0, 4.0]
    bounds = gl.window_bounds(hours, [(0.0, 3600.0), (3 * 3600.0, 4 * 3600.0)])

    stats = gl.window_statistics(values, labels, bounds)

    assert stats[0]['max'] == 20.0, "the 99.0 spike at h2 is outside window 0"
    assert stats[0]['time_max'] == "h1"
    assert stats[1]['min'] == 30.0 and stats[1]['max'] == 40.0


def test_window_without_result_rows_is_left_out():
    bounds = gl.window_bounds([0.0, 1.0], [(10 * 3600.0, 12 * 3600.0)])

    assert gl.window_statistics([1.0, 2.0], ["a", "b"], bounds) == {}


def test_overload_inside_the_window_is_reported_with_its_element():
    results = [
        _window_case('REF', [_window_series('line', 'Line A', '%', {0: _window(50.0, 96.1)})]),
        _window_case('OUTAGE', [_window_series('line', 'Line A', '%', {0: _window(60.0, 112.4)})]),
    ]

    judged = gl.assess_outage_window(results, 0)

    assert judged['assessment'] == gl.ASSESSMENT_LOADING
    assert judged['violation'] == 1
    assert judged['max_loading'] == 112.4
    assert judged['max_loading_element'] == 'Line A'
    assert judged['reference_max_loading'] == 96.1
    detail = gl.assessment_detail(judged)
    assert "max 112.4 % on Line A at 2014-01-01 08:00" in detail
    assert "reference 96.1 %" in detail


def test_voltage_band_violation_is_reported_separately():
    results = [_window_case('OUTAGE', [
        _window_series('line', 'Line A', '%', {0: _window(50.0, 80.0)}),
        _window_series('voltage', 'Bus 7', 'p.u.', {0: _window(0.931, 1.01)}),
    ])]

    judged = gl.assess_outage_window(results, 0)

    assert judged['assessment'] == gl.ASSESSMENT_VOLTAGE
    assert judged['violation'] == 1
    assert judged['min_voltage'] == 0.931
    assert "voltage 0.931 to 1.010 p.u." in gl.assessment_detail(judged)


def test_both_kinds_of_violation_are_named_together():
    results = [_window_case('OUTAGE', [
        _window_series('line', 'Line A', '%', {0: _window(50.0, 130.0)}),
        _window_series('voltage', 'Bus 7', 'p.u.', {0: _window(0.90, 1.09)}),
    ])]

    assert gl.assess_outage_window(results, 0)['assessment'] == gl.ASSESSMENT_BOTH


def test_clean_window_is_reported_as_no_limit_exceeded():
    results = [_window_case('OUTAGE', [
        _window_series('line', 'Line A', '%', {0: _window(50.0, 100.0)}),
        _window_series('voltage', 'Bus 7', 'p.u.', {0: _window(0.95, 1.05)}),
    ])]

    judged = gl.assess_outage_window(results, 0)

    # Values exactly on the limit are not violations.
    assert judged['assessment'] == gl.ASSESSMENT_OK
    assert judged['violation'] == 0


def test_window_with_no_series_data_is_not_assessed():
    results = [_window_case('OUTAGE', [_window_series('line', 'Line A', '%', {})])]

    assert gl.assess_outage_window(results, 0) is None


def test_report_row_carries_the_verdict_for_each_outage(monkeypatch):
    app = App((PlannedOutage("Outage A"),))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)

    gl.execute_gridlens(app)

    values = app.report.tables["PlannedOutages"]["values"]
    assert values[0, "outage_name"] == "Outage A"
    assert values[0, "priority"] == 1
    assert values[0, "assessment"] in (
        gl.ASSESSMENT_OK, gl.ASSESSMENT_LOADING, gl.ASSESSMENT_VOLTAGE,
        gl.ASSESSMENT_BOTH, gl.ASSESSMENT_NO_DATA)
    assert (0, "assessment_detail") in values


def test_skipped_outage_shows_its_reason_as_the_detail(monkeypatch):
    app = App((PlannedOutage("Disabled", disabled=True),))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)

    gl.execute_gridlens(app)

    values = app.report.tables["PlannedOutages"]["values"]
    assert values[0, "assessment"] == gl.ASSESSMENT_SKIPPED
    assert values[0, "violation"] == 0
    assert "disabled" in values[0, "assessment_detail"]


def _publication_payload():
    payload = gl.build_cases_payload(
        PFObject("Study", "IntCase"), [], "Model", "Result", [],
        "operator", "TEST")
    payload["ScriptedCases"] = [
        {"case_id": "C{}".format(index), "case_name": "Case",
         "is_reference": 0, "simulation_status": "CONVERGED"}
        for index in range(10)
    ]
    return payload


def test_publication_heartbeat_reports_progress_without_changing_data(monkeypatch):
    payload = _publication_payload()
    expected = Report()
    gl.publish_report(expected, payload)
    clock = [0.0]
    monkeypatch.setattr(gl.time, "monotonic", lambda: clock[0])
    messages = []

    class SlowReport(Report):
        def CreateField(self, *args):
            clock[0] += 1.0
            return super().CreateField(*args)

        def SetValue(self, *args):
            clock[0] += 1.0
            return super().SetValue(*args)

    report = SlowReport()
    counts = gl.publish_report(
        report, payload,
        log=lambda message: messages.append((clock[0], message)))

    assert report.tables == expected.tables
    assert report.reset_calls == 1
    assert counts["ScriptedCases"] == 10
    heartbeats = [(stamp, message) for stamp, message in messages
                  if "Publication heartbeat:" in message]
    assert any("CREATE FIELDS" in message for _, message in heartbeats)
    assert any("WRITE CELLS" in message and "Cases" in message
               and "rows complete" in message for _, message in heartbeats)
    assert all(right[0] - left[0] >= 5.0
               for left, right in zip(heartbeats, heartbeats[1:]))
    for previous, current in zip(messages, messages[1:]):
        assert current[0] - previous[0] <= 5.0
    assert any("cells/s" in message for _, message in messages)
    assert "Publication finished:" in messages[-1][1]


def test_publication_times_reset_and_announces_it_before_blocking(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(gl.time, "monotonic", lambda: clock[0])
    messages = []

    class SlowResetReport(Report):
        def Reset(self):
            assert messages[-1] == "Resetting report database."
            clock[0] += 12.0
            return super().Reset()

    report = SlowResetReport()
    gl.publish_report(report, _publication_payload(), log=messages.append)

    assert "Report database reset completed in 12.0s." in messages
    assert report.reset_calls == 1


def test_publication_validation_failure_does_not_reset_or_claim_validated():
    report = Report()
    messages = []
    payload = _publication_payload()
    payload["ScriptedCases"][0]["is_reference"] = True

    with pytest.raises(ValueError, match="boolean"):
        gl.publish_report(report, payload, log=messages.append)

    assert report.reset_calls == 0
    assert messages == ["Validating report tables before publication."]


def test_publication_write_failure_keeps_cell_context_and_clears_partial_data():
    class FailingReport(Report):
        def SetValue(self, table, field, row, value):
            if table == "Cases" and row == 2:
                return 7
            return super().SetValue(table, field, row, value)

    report = FailingReport()
    messages = []
    with pytest.raises(RuntimeError, match=r"SetValue\(Cases.case_id, row 2\)"):
        gl.publish_report(report, _publication_payload(), log=messages.append)

    assert report.reset_calls == 2
    assert report.tables == {}
    assert not any("Publication finished:" in message for message in messages)


def _check_emitted_report_against_mrt(report):
    """Replay recorded IntReport writes into SQLite, not the TABLES constant.

    The host's single Scripted prefix and field type mapping are modeled here;
    this does not exercise PowerFactory's export/merge or Stimulsoft compiler.
    """
    root = ET.parse(ROOT / "powerfactory" / "MASTER_GRIDLENS.mrt").getroot()
    sources = list(root.find("./Dictionary/DataSources"))
    emitted = {"Scripted" + name: table
               for name, table in report.tables.items()}
    assert set(emitted) == {source.findtext("Name") for source in sources}
    sql_types = {0: "TEXT", 1: "INTEGER", 2: "REAL"}
    mrt_types = {"System.String": "TEXT", "System.Int32": "INTEGER",
                 "System.Double": "REAL"}

    def quote(identifier):
        return '"' + identifier.replace('"', '""') + '"'

    db = sqlite3.connect(":memory:")
    try:
        for name, table in emitted.items():
            fields = table["fields"]
            definition = ", ".join(
                "{} {}".format(quote(field), sql_types[kind])
                for field, kind in fields.items())
            db.execute("CREATE TABLE {} ({})".format(quote(name), definition))
            row_indices = sorted({index for index, _ in table["values"]})
            for index in row_indices:
                values = [table["values"].get((index, field)) for field in fields]
                db.execute("INSERT INTO {} VALUES ({})".format(
                    quote(name), ", ".join("?" for _ in fields)), values)

        for source in sources:
            name = source.findtext("Name")
            expected = []
            for column in source.findall("./Columns/value"):
                field, kind = column.text.split(",", 1)
                expected.append((field, mrt_types[kind]))
            actual = [(row[1], row[2]) for row in
                      db.execute("PRAGMA table_info({})".format(quote(name)))]
            assert actual == expected, "Emitted fields do not match MRT: " + name
            cursor = db.execute(source.findtext("SqlCommand"))
            assert [column[0] for column in cursor.description] == [
                field for field, _ in expected]
            cursor.fetchall()

        # Includes group conditions, chart expressions, encoded filters and
        # highlighting rules, not just visible Text components.
        for element in root.iter():
            decoded = re.sub(
                r"_x([0-9A-Fa-f]{4})_",
                lambda match: chr(int(match[1], 16)), element.text or "")
            for table, field in re.findall(r"\b(Scripted\w+)\.(\w+)\b", decoded):
                assert table in emitted, "Unknown expression table: " + table
                assert field in emitted[table]["fields"], (
                    "Unknown expression field: {}.{}".format(table, field))
            if element.tag == "DataSourceName" and decoded:
                assert decoded in emitted, "Unknown data band source: " + decoded

        sources_by_ref = {source.attrib["Ref"]: source.findtext("Name")
                          for source in sources}
        for relation in root.findall("./Dictionary/Relations/*"):
            for side in ("Parent", "Child"):
                reference = relation.find(side + "Source").attrib["isRef"]
                fields = emitted[sources_by_ref[reference]]["fields"]
                for column in relation.findall("./" + side + "Columns/value"):
                    assert column.text in fields
    finally:
        db.close()


@pytest.mark.parametrize("reference,enabled", [
    (True, True), (False, True), (True, False), (False, False),
])
def test_executed_publisher_output_matches_mrt_and_all_sql_queries(
        monkeypatch, reference, enabled):
    app = App((PlannedOutage("Outage A", disabled=not enabled),))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", reference)
    gl.execute_gridlens(app)

    _check_emitted_report_against_mrt(app.report)

    # Empty tables must still expose the full schema during rendering.
    assert app.report.tables["CaseMatrix"]["values"] == {}
    assert app.report.tables["CaseMatrix"]["fields"]["case_id"] == 0
    if not reference and not enabled:
        assert app.report.tables["CaseComparison"]["values"] == {}
        assert app.report.tables["CaseComparison"]["fields"]["metric_value"] == 2
    outage = app.report.tables["PlannedOutages"]
    assert outage["fields"]["priority"] == 1
    assert outage["fields"]["violation"] == 1
    assert outage["fields"]["assessment"] == 0
    assert outage["fields"]["assessment_detail"] == 0
    for field in ("priority", "violation", "assessment", "assessment_detail"):
        assert (0, field) in outage["values"]


@pytest.mark.parametrize("table,field", [
    ("PlannedOutages", "priority"),
    ("PlannedOutages", "violation"),
    ("PlannedOutages", "assessment"),
    ("PlannedOutages", "assessment_detail"),
    ("PlannedOutages", None),
    ("CaseMatrix", None),
    ("CaseComparison", None),
])
def test_emitted_schema_check_catches_missing_tables_and_fields_from_export_log(
        monkeypatch, table, field):
    app = App((PlannedOutage("Outage A"),))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)
    gl.execute_gridlens(app)
    if field is None:
        del app.report.tables[table]
    else:
        del app.report.tables[table]["fields"][field]

    with pytest.raises(AssertionError):
        _check_emitted_report_against_mrt(app.report)


class _CountingList(list):
    """A category list that counts how often it is scanned from the start."""

    scans = 0

    def __iter__(self):
        _CountingList.scans += 1
        return super().__iter__()


def test_statistics_rows_do_not_rescan_the_category_per_critical_element():
    # A 229 325-series network hung for minutes here: every critical element
    # triggered a linear search through the whole category, once per case.
    results = []
    for case_id in ("REF", "OUTAGE"):
        series = []
        for index in range(300):
            item, stats = _window_series(
                "voltage", "Bus {}".format(index), "p.u.", {})
            stats.update({'min': 0.90, 'max': 1.08})
            series.append((item, stats))
        result = gl.case_result(
            {'id': case_id, 'name': case_id}, [item for item, _ in series],
            ['t'], [0.0], 'h')
        for item, stats in series:
            result['stats_by_key'][('voltage', item['key'])].update(stats)
        result['by_category']['voltage'] = _CountingList(
            result['by_category']['voltage'])
        results.append(result)
    payload = gl.empty_payload()
    _CountingList.scans = 0

    gl._statistics_rows(payload, results, 'voltage',
                        'ScriptedVoltageStatistics', gl.VOLTAGE_FIELDS)

    assert len(payload['ScriptedVoltageStatistics']) == 600
    # critical_keys reads each case once; per-element lookups must not scan.
    assert _CountingList.scans <= len(results)


def test_leftover_temporary_result_is_used_as_configured_with_a_warning(monkeypatch):
    # A run aborted mid-calculation can leave ComStatsim.results bound to its
    # own temporary ElmRes. That object is a full copy of the variable
    # selection, and every run recalculates into a fresh copy, so GridLens
    # calculates with the stored settings instead of refusing to run.
    app = App((PlannedOutage("Outage"),))
    leftover = app.original_result
    leftover.loc_name = "GridLens_TMP_20260928145610059524_REF"
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)

    counts = gl.execute_gridlens(app)

    assert app.qds.execute_calls == 2
    assert counts["ScriptedCases"] == 2
    assert app.qds.results is leftover, "the stored binding must come back"
    assert leftover.deleted is False, "only this run's own copies are deleted"
    warnings = [line for line in app.messages
                if "WARNING" in line and "GridLens_TMP_20260928145610059524_REF" in line]
    assert len(warnings) == 1
    assert "not deleted" in warnings[0]



D7_GRID = PFObject("D7 Westnetz", "ElmNet")
FOREIGN_GRID = PFObject("NL TenneT", "ElmNet")


class ScopedElmRes(ElmRes):
    """One D7 line, one foreign line and one D7 bus; counts value reads.

    The names deliberately do not contain D7: the scope is decided by the
    element's grid (PowerFactory attribute cpGrid), not by its name.
    """

    def __init__(self):
        super().__init__()
        self.own = PFObject("Ltg Bollenacker", "ElmLne", outserv=0, uknom=110, cpGrid=D7_GRID)
        self.foreign = PFObject("Line 380", "ElmLne", outserv=0, uknom=380, cpGrid=FOREIGN_GRID)
        self.bus = PFObject("Sammelschiene 3", "ElmTerm", outserv=0, uknom=110, cpGrid=D7_GRID)
        self.variables = ("b:tnow", "c:loading", "c:loading", "m:u")
        self.objects = (self.time, self.own, self.foreign, self.bus)
        self.units = ("h", "%", "%", "p.u.")
        self.columns = ([0.0, 1.0], [90.0, 95.0], [383.4, 383.4], [0.99, 1.0])
        self.reads = []

    def clone(self):
        return ScopedElmRes()

    def GetColumnValues(self, column):
        self.reads.append(column)
        return super().GetColumnValues(column)


def test_scope_is_decided_by_the_grid_not_the_name(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "D7")

    assert gl.element_in_scope(PFObject("Ltg Bollenacker", "ElmLne", cpGrid=D7_GRID))
    assert not gl.element_in_scope(PFObject("D7_L12", "ElmLne", cpGrid=FOREIGN_GRID))
    assert gl.element_grid_name(PFObject("x", "ElmLne", cpGrid=D7_GRID)) == "D7 Westnetz"


def test_grid_falls_back_to_the_elmnet_in_the_element_path(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "D7")
    element = PFObject("Ltg 5", "ElmLne")
    element.GetFullName = lambda: ("\\User\\Model.IntPrj\\Network Model.IntPrjfolder\\"
                                   "Network Data.IntPrjfolder\\D7 Westnetz.ElmNet\\Ltg 5.ElmLne")

    assert gl.element_grid_name(element) == "D7 Westnetz"
    assert gl.element_in_scope(element)


def test_element_without_any_grid_is_out_of_scope(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "D7")

    assert gl.element_grid_name(PFObject("D7 orphan", "ElmLne")) == ""
    assert not gl.element_in_scope(PFObject("D7 orphan", "ElmLne"))


def test_empty_grid_filter_assesses_every_element(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "")

    assert gl.element_in_scope(PFObject("Line 380", "ElmLne", cpGrid=FOREIGN_GRID))


def test_foreign_elements_are_neither_assessed_nor_read(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "D7")
    result = ScopedElmRes()
    counters = {}

    series = gl.collect_series(result, counters=counters)[0]

    assert sorted(item["element_name"] for item in series) == [
        "Ltg Bollenacker", "Sammelschiene 3"]
    assert 2 not in result.reads, "the foreign line's values must not be read"
    assert counters["out_of_scope"] == 1


def test_no_element_in_scope_names_the_filter(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "D9")

    with pytest.raises(RuntimeError, match="GRID_NAME_FILTER"):
        gl.collect_series(ScopedElmRes())


def test_out_of_service_matrix_only_lists_elements_in_scope(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "D7")
    app = App(())
    own = PFObject("Ltg 12", "ElmLne", outserv=1, cpGrid=D7_GRID)
    foreign = PFObject("Line 380", "ElmLne", outserv=1, cpGrid=FOREIGN_GRID)
    app.GetCalcRelevantObjects = (
        lambda pattern, *_: [own, foreign] if pattern == "*.ElmLne" else [])

    names = [entry[1] for entry in gl._collect_out_of_service(app)]

    assert names == ["Ltg 12"]


def test_report_states_which_elements_were_assessed(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "D7")
    app = App(())
    app.original_result = ScopedElmRes()
    app.qds.results = app.original_result
    app.study.AddCopy = lambda result: ScopedElmRes()
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)

    gl.execute_gridlens(app)

    scope = app.report.tables["ReportMeta"]["values"][0, "assessment_scope"]
    assert "grids named *D7*" in scope
    assert any("Grid scope 'D7': 2 series assessed, 1 out of scope" in line
               for line in app.messages)


def _trend_results():
    """REF and OUTAGE with two lines and two buses, three hourly points."""
    def result(case_id, loading_a, loading_b, bus_low, bus_high):
        items = []
        for category, name, unit, values in (
                ('line', 'D7_L1', '%', loading_a),
                ('line', 'D7_L2', '%', loading_b),
                ('voltage', 'D7_B1', 'p.u.', bus_low),
                ('voltage', 'D7_B2', 'p.u.', bus_high)):
            item = {'category': category, 'key': name, 'element_id': name,
                    'element_name': name, 'voltage_level': '110 kV',
                    'unit': unit, 'variable': 'Loading',
                    'points': [('2014-01-01 0{}:00'.format(i), float(i), v)
                               for i, v in enumerate(values)],
                    'windows': {}}
            item['statistics'] = gl.statistics(item)
            items.append(item)
        return gl.case_result({'id': case_id, 'name': case_id}, items,
                              ['t0', 't1', 't2'], [0.0, 1.0, 2.0], 'h')
    return [
        result('REF', [60.0, 70.0, 80.0], [50.0, 50.0, 50.0],
               [0.97, 0.96, 0.97], [1.01, 1.02, 1.01]),
        result('OUTAGE', [90.0, 120.0, 95.0], [55.0, 50.0, 52.0],
               [0.93, 0.94, 0.96], [1.03, 1.06, 1.02]),
    ]


def test_each_trend_chart_gets_its_own_table_with_one_element():
    # The PowerFactory report engine ignored the plot-to-data relation and
    # drew every plot's points into one chart. Each chart now reads a table
    # that holds exactly the series it shows.
    payload = gl.empty_payload()

    gl._trends(payload, _trend_results())

    line = payload['ScriptedTrendLineLoading']
    assert {row['element_name'] for row in line} == {'D7_L1'}
    assert [row['time_label'] for row in line] == [
        '2014-01-01 00:00', '2014-01-01 01:00', '2014-01-01 02:00']
    assert [row['ref_value'] for row in line] == [60.0, 70.0, 80.0]
    assert [row['outage_value'] for row in line] == [90.0, 120.0, 95.0]

    assert {row['element_name'] for row in payload['ScriptedTrendVoltageMin']} == {'D7_B1'}
    assert {row['element_name'] for row in payload['ScriptedTrendVoltageMax']} == {'D7_B2'}
    assert payload['ScriptedTrendTransformerLoading'] == []


def test_trend_shows_the_most_loaded_element_even_within_limits():
    results = _trend_results()
    for result in results:
        for item, stats in result['by_category']['line']:
            stats['max'] = min(stats['max'], 99.0)
    payload = gl.empty_payload()

    gl._trends(payload, results)

    assert payload['ScriptedTrendLineLoading'], "the chart must not stay empty"


def _overview_results():
    """REF and OUTAGE over four lines, one transformer and three buses."""
    def result(case_id, loadings, trafo, voltages, windows=None):
        items = []
        for name, value in loadings.items():
            items.append(('line', name, '%', value))
        items.append(('transformer', 'D7_T1', '%', trafo))
        for name, (low, high) in voltages.items():
            items.append(('voltage', name, 'p.u.', (low, high)))
        series = []
        for category, name, unit, value in items:
            low, high = value if isinstance(value, tuple) else (value, value)
            item = {'category': category, 'key': name, 'element_id': name,
                    'element_name': name, 'voltage_level': '110 kV', 'unit': unit,
                    'variable': 'x', 'points': [('t0', 0.0, low), ('t1', 1.0, high)],
                    'windows': (windows or {}).get(name, {})}
            item['statistics'] = gl.statistics(item)
            series.append(item)
        return gl.case_result({'id': case_id, 'name': case_id}, series,
                              ['t0', 't1'], [0.0, 1.0], 'h')
    ref = result('REF', {'D7_L1': 50.0, 'D7_L2': 85.0, 'D7_L3': 101.0, 'D7_L4': 70.0},
                 60.0, {'D7_B1': (0.99, 1.01), 'D7_B2': (0.97, 1.02), 'D7_B3': (1.0, 1.04)})
    outage = result('OUTAGE', {'D7_L1': 50.0, 'D7_L2': 105.0, 'D7_L3': 120.0, 'D7_L4': 90.0},
                    60.0, {'D7_B1': (0.93, 1.0), 'D7_B2': (0.97, 1.02), 'D7_B3': (1.0, 1.07)},
                    windows={'D7_L2': {0: {'min': 80.0, 'max': 105.0, 'mean': 90.0,
                                           'time_min': 't0', 'time_max': 't1'}},
                             'D7_B1': {0: {'min': 0.93, 'max': 1.0, 'mean': 0.96,
                                           'time_min': 't0', 'time_max': 't1'}},
                             'D7_L1': {1: {'min': 40.0, 'max': 50.0, 'mean': 45.0,
                                           'time_min': 't0', 'time_max': 't1'}}})
    return [ref, outage]


def _counts(rows):
    return {row['class_label']: row['element_count'] for row in rows}


def test_overview_loading_pie_uses_three_classes_for_the_outage_case():
    payload = gl.empty_payload()

    gl._overview(payload, _overview_results(), [])

    # OUTAGE: 50, 105, 120, 90 plus a transformer at 60.
    assert _counts(payload['ScriptedOverviewLoadingClasses']) == {
        'up to 80 %': 2, '80 to 100 %': 1, 'above 100 %': 2}
    assert [row['sort_order'] for row in payload['ScriptedOverviewLoadingClasses']] == [1, 2, 3]


def test_overview_voltage_pie_partitions_every_node_once():
    payload = gl.empty_payload()

    gl._overview(payload, _overview_results(), [])

    assert _counts(payload['ScriptedOverviewVoltageClasses']) == {
        'below 0.95 p.u.': 1, '0.95 to 1.05 p.u.': 1, 'above 1.05 p.u.': 1}


def test_overview_compares_violations_between_ref_and_outage():
    payload = gl.empty_payload()

    gl._overview(payload, _overview_results(), [])

    rows = [(row['violation_type'], row['ref_count'], row['outage_count'])
            for row in payload['ScriptedOverviewViolationsByCase']]
    assert rows == [('Overload', 1, 2), ('Voltage band', 0, 2)]
    summary = payload['ScriptedOverview'][0]
    assert summary['chart_case_id'] == 'OUTAGE'
    assert summary['assessed_elements'] == 8
    assert summary['overload_text'] == '2 (+1 vs REF)'
    assert summary['voltage_text'] == '2 (+2 vs REF)'


def test_overview_counts_violations_inside_each_outage_window():
    outages = [
        {'name': 'Line 04 - 14', 'status': gl.OUTAGE_CONSIDERED, 'window_index': 0},
        {'name': 'Line 15 - 16', 'status': gl.OUTAGE_CONSIDERED, 'window_index': 1},
        {'name': 'March', 'status': gl.OUTAGE_SKIPPED, 'window_index': None},
    ]
    payload = gl.empty_payload()

    gl._overview(payload, _overview_results(), outages)

    rows = [(row['outage_name'], row['ref_count'], row['outage_count'])
            for row in payload['ScriptedOverviewViolationsByOutage']]
    # Window 0 in OUTAGE: D7_L2 at 105 % and D7_B1 at 0.93 p.u.; REF has no
    # window statistics in this fixture. Window 1 is clean.
    assert rows == [('Line 04 - 14', 0, 2), ('Line 15 - 16', 0, 0)]
    summary = payload['ScriptedOverview'][0]
    assert summary['outages_text'] == '2 / 3'


def test_overview_without_outages_says_so_instead_of_an_empty_chart():
    payload = gl.empty_payload()

    gl._overview(payload, _overview_results()[:1], [])

    rows = payload['ScriptedOverviewViolationsByOutage']
    assert [row['outage_name'] for row in rows] == ['No planned outage in scope']
    assert payload['ScriptedOverview'][0]['chart_case_id'] == 'REF'
    assert payload['ScriptedOverview'][0]['overload_text'] == '1'



def test_outage_chart_separates_existing_from_added_violations():
    # An element that is already overloaded without the outage must count in
    # the REF bar of that window, so the outage's own effect stays visible.
    results = _overview_results()
    window = {0: {'min': 80.0, 'max': 104.0, 'mean': 90.0,
                  'time_min': 't0', 'time_max': 't1'}}
    for item, _ in results[0]['by_category']['line']:
        if item['key'] == 'D7_L2':
            item['windows'] = window
    outages = [{'name': 'Line 04 - 14', 'status': gl.OUTAGE_CONSIDERED, 'window_index': 0}]
    payload = gl.empty_payload()

    gl._overview(payload, results, outages)

    row = payload['ScriptedOverviewViolationsByOutage'][0]
    assert (row['ref_count'], row['outage_count']) == (1, 2)


def test_ref_and_outage_are_sampled_at_identical_times():
    # Per-series extremes used to be added to the sample, so REF and OUTAGE
    # got different time points and the chart axis ran out of order.
    def item(peak_at):
        values = [50.0] * 500
        values[peak_at] = 140.0
        return {'points': [('t{}'.format(i), float(i), v) for i, v in enumerate(values)]}

    ref = gl.sampled_plot_points(item(17))
    outage = gl.sampled_plot_points(item(333))

    assert [point[0] for point in ref] == [point[0] for point in outage]
    assert len(ref) == gl.MAX_PLOT_POINTS
    assert ref[0][0] == 't0' and ref[-1][0] == 't499'


def test_short_studies_are_plotted_without_thinning():
    points = [('t{}'.format(i), float(i), 1.0) for i in range(168)]

    assert gl.sampled_plot_points({'points': points}) == points
