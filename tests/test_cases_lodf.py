"""Single outage cases, the LODF from PowerFactory and the case-based report tables."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "powerfactory" / "gridlens_report.py"
SPEC = importlib.util.spec_from_file_location("gridlens_cases", SCRIPT)
gl = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gl)


@pytest.fixture(autouse=True)
def _assess_every_element(monkeypatch):
    monkeypatch.setattr(gl, "GRID_NAME_FILTER", "")


class Obj:
    def __init__(self, name, kind="ElmLne", **attributes):
        self.loc_name = name
        self.kind = kind
        self.__dict__.update(attributes)

    def GetClassName(self):
        return self.kind

    def GetFullName(self):
        return "Project\\{}\\{}.{}".format(self.kind, self.loc_name, self.kind)


class Logger:
    def __init__(self):
        self.lines = []

    def write(self, stage, message, step=None, level="INFO"):
        self.lines.append((stage, level, message))

    def detail(self, message, level="INFO"):
        self.lines.append(("DETAIL", level, message))

    def table(self, header, rows, level="INFO"):
        for row in rows:
            self.lines.append(("TABLE", level, "  ".join(str(cell) for cell in row)))


# ---------------------------------------------------------------------------
# State guard
# ---------------------------------------------------------------------------
def test_state_guard_restores_in_reverse_order_and_verifies():
    flag = Obj("Outage", "IntPlannedout", outserv=0)
    with gl.StateGuard() as guard:
        assert guard.set(flag, "outserv", 1, "flag")
        assert flag.outserv == 1
    assert flag.outserv == 0


def test_state_guard_restores_after_a_failure_in_the_block():
    flag = Obj("Outage", "IntPlannedout", outserv=0)
    with pytest.raises(RuntimeError, match="boom"):
        with gl.StateGuard() as guard:
            guard.set(flag, "outserv", 1, "flag")
            raise RuntimeError("boom")
    assert flag.outserv == 0


def test_state_guard_names_the_value_it_could_not_put_back():
    class Locked(Obj):
        def __setattr__(self, name, value):
            if name == "outserv" and self.__dict__.get("locked"):
                return
            super().__setattr__(name, value)

    flag = Locked("Outage", "IntPlannedout", outserv=0)
    with pytest.raises(gl.StateRestoreError, match=r"flag: expected 0, read back 1"):
        with gl.StateGuard() as guard:
            guard.set(flag, "outserv", 1, "flag")
            flag.locked = True


def test_state_guard_refuses_an_attribute_it_cannot_read():
    with gl.StateGuard() as guard:
        assert guard.set(Obj("x", "IntPlannedout"), "outserv", 1, "flag") is False


# ---------------------------------------------------------------------------
# LODF
# ---------------------------------------------------------------------------
class Contingency(Obj):
    def __init__(self, name):
        super().__init__(name, "ComOutage")
        self.objects = []

    def SetObjs(self, objects):
        self.objects = list(objects)
        return 0

    def GetObject(self, index):
        return self.objects[index] if index < len(self.objects) else None


class Analysis(Obj):
    def __init__(self, name="GridLens LODF"):
        super().__init__(name, "ComSimoutage")
        self.contingencies = []
        self.deleted = False

    def CreateObject(self, kind, name):
        assert kind == "ComOutage"
        contingency = Contingency(name)
        self.contingencies.append(contingency)
        return contingency

    def ClearCont(self):
        self.contingencies = []

    def GetContents(self, pattern, *_args):
        return list(self.contingencies) if pattern.endswith("ComOutage") else []

    def Delete(self):
        self.deleted = True
        return 0


class LodfResult(Obj):
    def __init__(self, name, rows, lines):
        super().__init__(name, "ElmRes")
        self.rows, self.lines = rows, lines  # rows: [(contingency, {line: percent})]
        self.released = False

    def Load(self):
        return 0

    def Release(self):
        self.released = True

    def GetNumberOfRows(self):
        return len(self.rows)

    def GetNumberOfColumns(self):
        return 1 + len(self.lines)

    def GetVariable(self, column):
        return "b:outid" if column == 0 else "m:LODF:bus1"

    def GetObject(self, column):
        return self.lines[column - 1]

    def GetValue(self, row, column):
        contingency, values = self.rows[row]
        if column == 0:
            return (0, -float(row + 1))
        line = self.lines[column - 1]
        return (0, values[line.loc_name]) if line.loc_name in values else (3, 0.0)

    def GetObj(self, outage_id):
        return self.rows[-int(outage_id) - 1][0]


class ResultFolder(Obj):
    def __init__(self, result):
        super().__init__("Distribution Factors Results (SYM)", "IntPrjfolder")
        self.result = result

    def GetContents(self, pattern, *_args):
        return [self.result] if pattern.endswith("ElmRes") and self.result else []


class Distribution(Obj):
    def __init__(self, study):
        super().__init__("Sensitivities", "ComVstab", pComSimoutage=None, isContSens=0, calcLodf=0, lodflim=5,
                         pResult=ResultFolder(None))
        self.study = study
        self.code = 0
        self.seen = {}
        self.solutions = {}
        self.lines = []
        self.deleted = False

    def Execute(self):
        self.seen = {name: getattr(self, name) for name in ("isContSens", "calcLodf", "lodflim")}
        analysis = self.pComSimoutage
        rows = [(item, self.solutions[item.loc_name]) for item in analysis.contingencies if item.loc_name in self.solutions]
        self.pResult = ResultFolder(LodfResult("Results_LODF", rows, self.lines) if rows else None)
        return self.code

    def Delete(self):
        self.deleted = True
        return 0


class StudyCase(Obj):
    def __init__(self):
        super().__init__("Study", "IntCase")
        self.distribution = Distribution(self)
        self.has_distribution = True
        self.analyses = []

    def GetContents(self, pattern, *_args):
        if pattern.endswith("ComVstab"):
            return [self.distribution] if self.has_distribution else []
        if pattern.endswith("ComSimoutage"):
            return list(self.analyses)
        return []

    def CreateObject(self, kind, name):
        assert kind == "ComSimoutage"
        analysis = Analysis(name)
        self.analyses.append(analysis)
        return analysis


class LodfApp:
    def __init__(self, study):
        self.study = study

    def GetFromStudyCase(self, name):
        return self.study.distribution if name == "ComVstab" else None


def _record(name, *lines):
    return {"id": name, "name": name, "branches": list(lines), "equipment_keys": [gl.object_key(line) for line in lines]}


def _lodf_setup():
    study = StudyCase()
    outaged_a, outaged_b, outaged_c = Obj("Out A"), Obj("Out B"), Obj("Out C")
    rhein, hafen = Obj("L-380 Rhein"), Obj("L-110 Hafen")
    study.distribution.lines = [rhein, hafen]
    study.distribution.solutions = {
        "Out A": {"L-380 Rhein": 42.0, "L-110 Hafen": -31.0},
        "Out C": {"L-380 Rhein": 7.0},  # Hafen is not written: below the recording limit
    }
    records = [_record("Out A", outaged_a), _record("Out B", outaged_b), _record("Out C", outaged_c),
               {"id": "Bus only", "name": "Bus only", "branches": [], "equipment_keys": []}]
    return study, records, rhein, hafen


def test_lodf_is_read_per_outage_as_signed_fractions():
    study, records, rhein, hafen = _lodf_setup()
    logger = Logger()

    info = gl.calculate_lodf(LodfApp(study), study, records, logger)

    assert info["Out A"]["values"] == {gl.object_key(rhein): ("L-380 Rhein", 0.42), gl.object_key(hafen): ("L-110 Hafen", -0.31)}
    assert info["Out C"]["values"] == {gl.object_key(rhein): ("L-380 Rhein", 0.07)}
    assert info["Out A"]["reason"] == ""


def test_lodf_gives_every_missing_value_its_reason():
    study, records, *_ = _lodf_setup()

    info = gl.calculate_lodf(LodfApp(study), study, records, Logger())

    assert "no solution" in info["Out B"]["reason"]
    assert info["Out B"]["values"] == {}
    assert "switches no line" in info["Bus only"]["reason"]


def test_lodf_run_uses_its_own_settings_and_puts_everything_back():
    study, records, *_ = _lodf_setup()
    existing = Analysis("Users Analysis")
    study.distribution.pComSimoutage = existing

    gl.calculate_lodf(LodfApp(study), study, records, Logger())

    assert study.distribution.seen == {"isContSens": 1, "calcLodf": 1, "lodflim": 0}
    assert (study.distribution.isContSens, study.distribution.calcLodf, study.distribution.lodflim) == (0, 0, 5)
    assert study.distribution.pComSimoutage is existing
    assert existing.contingencies == [], "the user's own Contingency Analysis is not touched"
    assert study.analyses[0].deleted, "what the run created is deleted again"
    assert not study.distribution.deleted, "the user's own command is kept"


def test_lodf_creates_the_command_when_the_study_case_has_none_and_deletes_it():
    study, records, *_ = _lodf_setup()
    study.has_distribution = False

    gl.calculate_lodf(LodfApp(study), study, records, Logger())

    assert study.distribution.deleted


def test_lodf_error_code_becomes_the_reason_of_every_outage():
    study, records, *_ = _lodf_setup()
    study.distribution.code = 1
    logger = Logger()

    info = gl.calculate_lodf(LodfApp(study), study, records, logger)

    assert all("error code 1" in item["reason"] for item in info.values())
    assert any(level == "WARNING" for _, level, _ in logger.lines)
    assert (study.distribution.isContSens, study.distribution.calcLodf, study.distribution.lodflim) == (0, 0, 5)


def test_lodf_without_any_branch_is_reported_not_attempted():
    study = StudyCase()
    records = [{"id": "Bus only", "name": "Bus only", "branches": [], "equipment_keys": []}]

    info = gl.calculate_lodf(LodfApp(study), study, records, Logger())

    assert "None of the outages" in info["Bus only"]["reason"]
    assert study.distribution.seen == {}


def test_lodf_restore_failure_is_not_swallowed():
    study, records, *_ = _lodf_setup()

    class Stubborn(Distribution):
        def __setattr__(self, name, value):
            if name == "lodflim" and self.__dict__.get("locked"):
                return
            super().__setattr__(name, value)

        def Execute(self):
            self.locked = True
            return super().Execute()

    stubborn = Stubborn(study)
    stubborn.lines, stubborn.solutions = study.distribution.lines, study.distribution.solutions
    study.distribution = stubborn

    with pytest.raises(gl.StateRestoreError, match="ComVstab.lodflim"):
        gl.calculate_lodf(LodfApp(study), study, records, Logger())


# ---------------------------------------------------------------------------
# Case-based report tables
# ---------------------------------------------------------------------------
LABELS = ["2026-10-15 0{}:00".format(hour) for hour in range(6)]
TIMES = [float(hour) for hour in range(6)]
WINDOWS = [(0, 3), (2, 5), (1, 4), (0, 2), (3, 6), (1, 5), (0, 6), (2, 4)]
LINES = {"L-220 Nordring": [76, 80, 85, 82, 88, 84], "L-380 Rhein": [71, 74, 76, 75, 78, 77],
         "L-220 West 1": [78, 80, 82, 81, 84, 80], "L-110 Hafen": [60, 64, 66, 65, 70, 66]}
TRAFOS = {"TR-West T1": [95, 99, 102, 101, 104, 100]}
NODES = {"Busbar West 220 kV": [0.99, 0.98, 0.97, 0.975, 0.96, 0.97]}


def _item(category, name, values):
    obj = Obj(name, {"line": "ElmLne", "transformer": "ElmTr2", "voltage": "ElmTerm"}[category])
    points = [(LABELS[i], TIMES[i], value) for i, value in enumerate(values)]
    item = {"category": category, "object": obj, "key": obj.GetFullName(), "element_id": name, "element_name": name,
            "voltage_level": "220 kV", "nominal_kv": 220.0, "limits": gl.voltage_band(220.0) if category == "voltage" else None,
            "variable_id": "x", "variable": "Loading", "unit": "p.u." if category == "voltage" else "%", "points": points}
    item["statistics"] = gl.statistics(item)
    item["windows"] = gl.window_statistics(values, LABELS, [(lo, hi) for lo, hi in WINDOWS])
    return item


def _result(case_id, name, shift=None, outage=None):
    shift = shift or {}
    window = range(*WINDOWS[outage["window_index"]]) if outage else range(0)
    series = [_item("line", n, [v + (shift.get(n, 0) if i in window else 0) for i, v in enumerate(vals)]) for n, vals in LINES.items()]
    series += [_item("transformer", n, vals) for n, vals in TRAFOS.items()]
    series += [_item("voltage", n, vals) for n, vals in NODES.items()]
    return gl.case_result({"id": case_id, "name": name, "outage": outage}, series, LABELS, TIMES, "h")


def _record_for(index, name, equipment_keys=()):
    return {"id": name, "name": name, "source_class": "IntPlannedout", "status": gl.OUTAGE_CONSIDERED, "skip_reason": "",
            "equipment_name": "Equipment " + name, "equipment_type": "", "switching_actions": "", "start_time": "2026-10-15 00:00",
            "end_time": "2026-10-15 03:00", "priority": index + 1, "window": (0, 1), "window_index": index,
            "equipment_keys": list(equipment_keys), "case_id": "OUT{:02d}".format(index + 1)}


def _payload(cases=3, lodf=None, shifts=None):
    shifts = shifts or [{"L-380 Rhein": 18, "L-110 Hafen": 11}, {"L-220 West 1": 30, "L-380 Rhein": 25}, {"L-110 Hafen": 25}] + [{}] * 10
    records = [_record_for(index, "Outage {}".format(index + 1)) for index in range(cases)]
    results = [_result("REF", "Reference")]
    results += [_result(record["case_id"], record["name"], shifts[index], record) for index, record in enumerate(records)]
    gl.apply_reference(results)
    payload = gl.build_cases_payload(Obj("Europe", "IntCase"), results, "BDS", "Result", records, "operator", "REFERENCE + PLANNED OUTAGES", lodf)
    gl.validate_payload(payload)
    return payload, results, records


def test_every_case_is_compared_with_reference_inside_its_own_window():
    payload, results, _ = _payload()

    cases = {row["case_name"]: row for row in payload["ScriptedCases"]}
    assert cases["Reference"]["assessment"] == "BASELINE"
    assert cases["Outage 2"]["assessment"] == gl.ASSESSMENT_LOADING
    assert cases["Outage 2"]["violation"] == 1
    assert "L-220 West 1" in cases["Outage 2"]["assessment_detail"]
    assert cases["Outage 2"]["period_text"] == "2026-10-15 00:00 - 03:00"


def test_case_counts_follow_the_whole_period_of_each_case():
    payload, *_ = _payload()

    counts = {row["case_name"]: (row["line_count"], row["transformer_count"], row["node_count"]) for row in payload["ScriptedCaseCounts"]}
    assert counts["Reference"] == (0, 1, 0)
    assert counts["Outage 2"][0] == 2
    assert [row["case_order"] for row in payload["ScriptedCaseCounts"]] == [0, 1, 2, 3]


def test_matrix_tables_continue_in_blocks_of_six_cases():
    payload, *_ = _payload(cases=8, shifts=[{"L-380 Rhein": 20}] * 8)

    rows = payload["ScriptedAppendixLine"]
    assert {row["block"] for row in rows} == {1, 2}
    first = [row for row in rows if row["block"] == 1][0]
    last = [row for row in rows if row["block"] == 2][0]
    assert first["col_count"] == 6 and last["col_count"] == 2
    assert first["h6_name"] == "Outage 6" and last["h1_name"] == "Outage 7"
    assert last["c3_text"] == "" and last["h3_name"] == ""
    assert first["ref_text"].endswith(" %")


def test_matrix_without_outage_cases_shows_reference_only():
    payload, *_ = _payload(cases=0)

    rows = payload["ScriptedAppendixLine"]
    assert rows and all(row["col_count"] == 0 and row["h1_name"] == "" for row in rows)


def test_out_of_service_elements_read_n_a():
    payload, results, _ = _payload()
    del results[1]["item_by_key"]["line", "Project\\ElmLne\\L-110 Hafen.ElmLne"]
    results[1]["by_category"]["line"] = [entry for entry in results[1]["by_category"]["line"] if entry[0]["element_name"] != "L-110 Hafen"]
    records = [result["outage"] for result in results[1:]]

    payload = gl.build_cases_payload(Obj("Europe", "IntCase"), results, "BDS", "Result", records, "operator", "RUN", None)

    hafen = [row for row in payload["ScriptedAppendixLine"] if row["element_name"] == "L-110 Hafen"][0]
    assert hafen["c1_text"] == "n/a"


def test_lodf_ranking_orders_by_absolute_lodf_and_shows_the_measured_delta():
    lodf = {"Outage 1": {"values": {"Project\\ElmLne\\L-380 Rhein.ElmLne": ("L-380 Rhein", 0.42),
                                    "Project\\ElmLne\\L-110 Hafen.ElmLne": ("L-110 Hafen", -0.61),
                                    "Project\\ElmLne\\L-220 West 1.ElmLne": ("L-220 West 1", 0.05)}, "reason": ""}}
    payload, *_ = _payload(lodf=lodf)

    rows = [row for row in payload["ScriptedLodfRanking"] if row["case_name"] == "Outage 1"]
    assert [row["element_name"] for row in rows][:3] == ["L-110 Hafen", "L-380 Rhein", "L-220 West 1"]
    assert rows[0]["lodf_text"] == "-61.0 %"
    assert rows[0]["delta_text"] == "+11.0 pp"
    assert rows[1]["delta_text"] == "+18.0 pp"
    assert "Ranked by |LODF|" in rows[0]["basis_text"]
    assert len(rows) <= gl.TOP_N


def test_lodf_ranking_falls_back_to_the_measured_change_and_says_so():
    lodf = {"Outage 2": {"values": {}, "reason": "PowerFactory found no solution without this equipment."}}
    payload, *_ = _payload(lodf=lodf)

    rows = [row for row in payload["ScriptedLodfRanking"] if row["case_name"] == "Outage 2"]
    assert rows[0]["element_name"] == "L-220 West 1"
    assert rows[0]["lodf_text"] == "n/a"
    assert "measured loading change" in rows[0]["basis_text"]
    assert "no solution" in rows[0]["basis_text"]


def test_lodf_ranking_leaves_out_the_equipment_the_outage_switches_off():
    records_keys = ["Project\\ElmLne\\L-380 Rhein.ElmLne"]
    lodf = {"Outage 1": {"values": {key: (name, 0.9) for key, name in (
        ("Project\\ElmLne\\L-380 Rhein.ElmLne", "L-380 Rhein"), ("Project\\ElmLne\\L-110 Hafen.ElmLne", "L-110 Hafen"))}, "reason": ""}}
    records = [_record_for(0, "Outage 1", records_keys)]
    results = [_result("REF", "Reference"), _result("OUT01", "Outage 1", {"L-110 Hafen": 11}, records[0])]
    gl.apply_reference(results)

    payload = gl.build_cases_payload(Obj("Europe", "IntCase"), results, "BDS", "R", records, "operator", "RUN", lodf)

    assert [row["element_name"] for row in payload["ScriptedLodfRanking"]] == ["L-110 Hafen"]


def test_trend_charts_carry_reference_and_every_case_in_fixed_slots():
    payload, *_ = _payload()

    row = payload["ScriptedTrendMostLoaded"][0]
    assert [row["s{}_name".format(slot)] for slot in range(4)] == ["Reference", "Outage 1", "Outage 2", "Outage 3"]
    assert row["s4_name"] == " " and row["v4"] is None
    assert row["v0"] is not None and row["v3"] is not None
    assert payload["ScriptedReportMeta"][0]["chart_cases"] == "4"
    delta = payload["ScriptedTrendLargestDelta"]
    assert delta and "Largest delta" in delta[0]["chart_title"]


def test_charts_show_at_most_six_cases_and_say_so():
    payload, *_ = _payload(cases=8)

    meta = payload["ScriptedReportMeta"][0]
    assert meta["chart_cases"] == "7"
    assert "first 6 of 8" in meta["radar_note"]
    assert len(payload["ScriptedCaseCounts"]) == 9, "tables still list every case"


def test_reference_disclaimer_tables():
    payload, *_ = _payload()

    classes = {row["class_label"]: row["element_count"] for row in payload["ScriptedPieLines"]}
    assert classes == {"up to 80 %": 2, "80 to 100 %": 2, "above 100 %": 0}
    exceeded = payload["ScriptedReferenceExceeded"]
    assert [(row["type_label"], row["element_name"], row["max_text"]) for row in exceeded] == [("Transformer", "TR-West T1", "104.0 %")]


def test_metric_view_and_key_cards():
    payload, *_ = _payload()

    metrics = {row["case_name"]: row for row in payload["ScriptedCaseMetrics"]}
    assert metrics["Reference"]["largest_delta_text"] == "-"
    assert metrics["Outage 2"]["largest_delta_text"] == "+30.0 pp - L-220 West 1"
    kpi = payload["ScriptedKpis"][0]
    assert kpi["highest_text"].startswith("114.0 %")
    assert kpi["highest_violation"] == 1
    assert kpi["delta_text"] == "+30.0 pp · Outage 2"


def test_top_lines_by_case_rank_each_case_on_its_own():
    payload, *_ = _payload()

    first = payload["ScriptedTopLinesByCase"][0]
    assert first["element_name"] == "1"
    assert first["ref_text"] == "L-220 Nordring - 88.0 %"
    assert first["c2_text"].startswith("L-220 West 1")


def test_report_text_never_calls_the_data_synthetic():
    payload, *_ = _payload()

    text = " ".join(str(value) for rows in payload.values() for row in rows for value in row.values())
    assert "SYNTHETIC" not in text.upper()


def test_period_text_shortens_a_same_day_window():
    assert gl.period_text("2026-10-15 00:00", "2026-10-15 05:00") == "2026-10-15 00:00 - 05:00"
    assert gl.period_text("2026-10-15 22:00", "2026-10-16 05:00") == "2026-10-15 22:00 - 2026-10-16 05:00"
    assert gl.period_text("", "") == ""
