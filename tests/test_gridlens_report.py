from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "powerfactory" / "gridlens_report.py"
SPEC = importlib.util.spec_from_file_location("gridlens_report", SCRIPT)
gl = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gl)


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


class PlannedOutage(PFObject):
    def __init__(self, name, *, active=False, disabled=False, in_time=True,
                 apply_code=None, reset_code=None, include_api=True):
        super().__init__(name, "IntPlannedout", outserv=1 if disabled else 0)
        self.active = active
        self.in_time = in_time
        self.apply_code = apply_code
        self.reset_code = reset_code
        self.apply_calls = 0
        self.reset_calls = 0
        if not include_api:
            self.Apply = None
            self.Reset = None
            self.Check = None

    def IsInStudyTime(self):
        return 1 if self.in_time else 0

    def Check(self):
        return 0 if self.active else 1

    def Apply(self):
        self.apply_calls += 1
        if self.apply_code not in (None, 0):
            return self.apply_code
        self.active = True
        return self.apply_code

    def Reset(self):
        self.reset_calls += 1
        if self.reset_code not in (None, 0):
            return self.reset_code
        self.active = False
        return self.reset_code


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


class StudyCase(PFObject):
    def __init__(self):
        super().__init__("Study", "IntCase")
        self.copies = []

    def AddCopy(self, result):
        copy = result.clone()
        self.copies.append(copy)
        return copy


class QDS(PFObject):
    def __init__(self, result, failure=None):
        super().__init__("Configured QDS", "ComStatsim", results=result)
        self.failure = failure
        self.execute_calls = 0

    def Execute(self):
        self.execute_calls += 1
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
        self.qds = QDS(self.original_result, qds_failure)
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
        return self.qds if name == "ComStatsim" else None

    def GetCalcRelevantObjects(self, _pattern, *_args):
        return []


def test_table_contract_is_single_versioned_17_table_contract():
    assert gl.PUBLISHER_VERSION == "5.0.0"
    assert gl.TEMPLATE_VERSION == "3.0.0"
    assert gl.DATA_CONTRACT_VERSION == "3.0"
    assert len(gl.TABLES) == 17
    tables = dict(gl.TABLES)
    assert "ScriptedCases" in tables
    assert "ScriptedPlannedOutages" in tables
    assert "ScriptedCaseMatrix" in tables
    assert "generated_by" in dict(tables["ScriptedReportMeta"])
    assert "run_mode" in dict(tables["ScriptedReportMeta"])


def test_outage_filter_applies_only_safe_candidate():
    applicable = PlannedOutage("Applicable")
    already_active = PlannedOutage("Already active", active=True)
    disabled = PlannedOutage("Disabled", disabled=True)
    outside = PlannedOutage("Outside", in_time=False)
    unsupported = PlannedOutage("Unsupported", include_api=False)
    app = App((applicable, already_active, disabled, outside, unsupported))
    records, applied = gl.apply_available_outages(app, gl.RunLogger(app))

    assert [record["name"] for record in applied] == ["Applicable"]
    assert applicable.active is True
    statuses = {record["name"]: (record["status"], record["skip_reason"])
                for record in records}
    assert statuses["Applicable"] == ("APPLIED", "")
    assert "already active" in statuses["Already active"][1]
    assert "disabled" in statuses["Disabled"][1]
    assert "outside" in statuses["Outside"][1]
    assert "unavailable" in statuses["Unsupported"][1]

    assert gl.restore_outages(applied, gl.RunLogger(app)) == []
    assert applicable.active is False


def test_standard_mode_runs_reference_then_one_combined_outage(monkeypatch):
    outage_a = PlannedOutage("Outage A")
    outage_b = PlannedOutage("Outage B")
    app = App((outage_a, outage_b))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", True)
    monkeypatch.setattr(gl.getpass, "getuser", lambda: "operator")

    counts = gl.execute_gridlens(app)

    assert app.qds.execute_calls == 2
    assert app.qds.results is app.original_result
    assert outage_a.active is False and outage_b.active is False
    assert all(copy.deleted for copy in app.study.copies)
    assert app.report.reset_calls == 1
    assert counts["ScriptedCases"] == 2
    assert counts["ScriptedPlannedOutages"] == 2
    values = app.report.tables["ReportMeta"]["values"]
    assert values[0, "generated_by"] == "operator"
    assert values[0, "run_mode"] == "REFERENCE + COMBINED PLANNED OUTAGES"
    assert any("blocking API call may take several minutes" in line
               for line in app.messages)


def test_direct_mode_with_no_applicable_outage_does_not_calculate(monkeypatch):
    app = App((PlannedOutage("Disabled", disabled=True),))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", False)

    counts = gl.execute_gridlens(app)

    assert app.qds.execute_calls == 0
    assert app.qds.results is app.original_result
    assert counts["ScriptedCases"] == 0
    assert counts["ScriptedPlannedOutages"] == 1
    values = app.report.tables["ReportMeta"]["values"]
    assert values[0, "run_mode"] == (
        "NO CALCULATION - NO APPLICABLE PLANNED OUTAGES")


def test_calculation_failure_still_restores_outage_and_result_binding(monkeypatch):
    outage = PlannedOutage("Outage")
    app = App((outage,), qds_failure=RuntimeError("solver stopped"))
    monkeypatch.setattr(gl, "RUN_REFERENCE_CASE", False)

    with pytest.raises(gl.GridLensError, match="solver stopped"):
        gl.execute_gridlens(app)

    assert outage.active is False
    assert outage.reset_calls == 1
    assert app.qds.results is app.original_result
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


def test_apply_failure_is_skipped_only_after_verified_reset():
    outage = PlannedOutage("Fails", apply_code=9)
    app = App((outage,))
    records, applied = gl.apply_available_outages(app, gl.RunLogger(app))
    assert applied == []
    assert records[0]["status"] == "SKIPPED"
    assert outage.reset_calls == 1
    assert outage.active is False


def test_unreadable_initial_outage_state_is_skipped_without_reset():
    outage = PlannedOutage("Unreadable")
    outage.Check = lambda: (_ for _ in ()).throw(RuntimeError("check failed"))
    app = App((outage,))

    records, applied = gl.apply_available_outages(app, gl.RunLogger(app))

    assert applied == []
    assert records[0]["status"] == "SKIPPED"
    assert "no change was attempted" in records[0]["skip_reason"]
    assert outage.apply_calls == 0
    assert outage.reset_calls == 0


def test_failed_immediate_reset_is_retried_by_final_restoration():
    outage = PlannedOutage("Unsafe", reset_code=8)
    outage.Apply = lambda: (setattr(outage, "active", True) or 7)
    app = App((outage,))
    applied = []

    with pytest.raises(gl.GridLensError, match="could not be reset immediately"):
        gl.apply_available_outages(app, gl.RunLogger(app), applied)

    assert applied and applied[0]["name"] == "Unsafe"
    errors = gl.restore_outages(applied, gl.RunLogger(app))
    assert errors and "Unsafe" in errors[0]


def test_duplicate_outage_names_receive_distinct_short_ids():
    first = PlannedOutage("Duplicate")
    second = PlannedOutage("Duplicate")
    second.GetFullName = lambda: "Project\\Other\\Duplicate.IntPlannedout"
    app = App((first, second))
    records, applied = gl.apply_available_outages(app, gl.RunLogger(app))
    assert len({record["id"] for record in records}) == 2
    assert all(record["id"].startswith("Duplicate (") for record in records)
    assert gl.restore_outages(applied, gl.RunLogger(app)) == []


def test_complete_outage_discovery_failure_is_not_reported_as_empty():
    app = App(())
    app.outage_folder.GetContents = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("folder unavailable"))
    app.project.GetContents = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("project unavailable"))

    with pytest.raises(gl.GridLensError, match="discovery could not query"):
        gl.apply_available_outages(app, gl.RunLogger(app))


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
