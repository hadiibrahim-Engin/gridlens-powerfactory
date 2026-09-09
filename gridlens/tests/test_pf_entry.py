"""Tests fuer Moduswahl, Report-Modus und Modul-Purge."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import entry  # noqa: E402


class Named:
    def __init__(self, cls, name):
        self._class_name = cls
        self.loc_name = name

    def GetClassName(self):
        return self._class_name

    def GetFullName(self):
        return self.loc_name + "." + self._class_name


def test_snapshots_are_ordered_with_the_reference_first():
    class Case:
        def GetContents(self, pattern, *args):
            return [Named("ElmRes", "GridLens_S02"),
                    Named("ElmRes", "GridLens_REF"),
                    Named("ElmRes", "GridLens_S01"),
                    Named("ElmRes", "Quasi-Dynamic Simulation AC")]

    assert [case_id for case_id, _ in entry.load_snapshots(Case())] == [
        "REF", "S01", "S02"
    ]


def test_no_snapshot_means_no_multi_case_run():
    class Case:
        def GetContents(self, pattern, *args):
            return [Named("ElmRes", "Quasi-Dynamic Simulation AC")]

    assert entry.load_snapshots(Case()) == []


def test_report_parent_selects_report_mode():
    assert entry.select_mode(Named("IntReport", "GridLens Report")) == "report"


def test_any_other_parent_selects_runner_mode():
    assert entry.select_mode(Named("IntCase", "Study Case")) == "runner"
    assert entry.select_mode(None) == "runner"


def test_main_uses_runner_mode_outside_an_intreport(monkeypatch):
    messages = []
    parent = Named("IntCase", "Study Case")
    app = SimpleNamespace(
        GetCurrentScript=lambda: SimpleNamespace(GetParent=lambda: parent),
        GetActiveStudyCase=lambda: parent,
        PrintPlain=messages.append,
    )
    monkeypatch.setitem(
        sys.modules, "powerfactory", SimpleNamespace(GetApplication=lambda: app)
    )
    called = []

    def fake_run_cases(actual_app, study_case, log=None):
        called.append((actual_app, study_case, log))
        return [{"status": "konvergiert"}, {"status": "NICHT KONVERGIERT"}]

    monkeypatch.setattr(entry, "run_cases", fake_run_cases)
    entry.main()
    assert called and called[0][:2] == (app, parent)
    assert "GridLens mode: runner" in messages
    assert messages[-1].startswith("GridLens: 1 von 2 Fällen")


def test_entry_file_purges_stale_submodules():
    """PowerFactory keeps sys.modules across runs. Without the purge an edited
    submodule would keep running its old version while the entry file already
    reports the new publisher number."""
    source = (DEPLOYMENT / "gridlens_report.py").read_text(encoding="utf-8")
    assert "del sys.modules[_name]" in source
    assert 'n.startswith("gridlens_pf.")' in source

    sys.modules["gridlens_pf.__probe__"] = object()
    namespace = {"__file__": str(DEPLOYMENT / "gridlens_report.py"),
                 "__name__": "not_main"}
    try:
        exec(compile(source, "gridlens_report.py", "exec"), namespace)
        assert "gridlens_pf.__probe__" not in sys.modules
    finally:
        sys.modules.pop("gridlens_pf.__probe__", None)


def test_multi_case_publication_resets_exactly_once():
    """One Reset for the whole run; a per-case reset would drop earlier cases."""
    from gridlens_pf import payload, publish

    class CountingReport:
        def __init__(self):
            self.resets = 0
            self.rows = {}

        def GetClassName(self):
            return "IntReport"

        def Reset(self):
            self.resets += 1
            self.rows = {}

        def CreateTable(self, name):
            self.rows[name] = 0

        def CreateField(self, table, field, kind):
            pass

        def SetValue(self, table, field, row, value):
            self.rows[table] = max(self.rows[table], row + 1)

    def make_case(case_id, values):
        points = [("00:00", 0.0, v) for v in values]
        item = {"category": "line", "object": None, "key": "L1",
                "element_id": "L1", "element_name": "L1",
                "voltage_level": "110 kV", "variable_id": "c:loading",
                "variable": "Auslastung", "unit": "%", "points": points}
        record = {"id": case_id, "name": case_id, "kind": "scenario",
                  "description": "", "status": "konvergiert", "error_code": 0,
                  "message": "", "outages": []}
        return payload.scenario_result(record, [item], ["00:00"], [0.0], "h")

    results = [make_case("REF", [118.0]), make_case("S01", [130.0])]
    payload.apply_reference(results)
    data = payload.build_cases_payload(None, results, "Projekt", "GridLens_REF")

    report = CountingReport()
    publish.publish_report(report, data)
    assert report.resets == 1
    assert report.rows["LineStatistics"] == 2
