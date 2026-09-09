"""Tests fuer den Szenario-Runner."""

import sys
from pathlib import Path

import pytest

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import runner  # noqa: E402


class Snapshot:
    def __init__(self, name):
        self.loc_name = name
        self.desc = []
        self.deleted = False

    def GetClassName(self):
        return "ElmRes"

    def GetFullName(self):
        return "SC." + self.loc_name + ".ElmRes"

    def Delete(self):
        self.deleted = True


class Element:
    def __init__(self, cls, name, outserv):
        self._class_name = cls
        self.loc_name = name
        self.outserv = outserv

    def GetClassName(self):
        return self._class_name

    def GetFullName(self):
        return "Net." + self.loc_name + "." + self._class_name


class Scenario:
    def __init__(self, name):
        self.loc_name = name
        self.active = False

    def GetClassName(self):
        return "IntScenario"

    def GetFullName(self):
        return "Scen." + self.loc_name + ".IntScenario"

    def Activate(self):
        self.active = True
        return 0

    def Deactivate(self):
        self.active = False
        return 0


class StudyCase:
    def __init__(self):
        self.objects = {}
        self.created = []

    def GetClassName(self):
        return "IntCase"

    def GetContents(self, pattern, *args):
        return [item for item in self.objects.values() if not item.deleted]

    def CreateObject(self, class_name, name):
        snapshot = Snapshot(name)
        self.objects[name] = snapshot
        self.created.append(name)
        return snapshot


class QDS:
    def __init__(self, codes=None):
        self.loc_name = "Quasi-Dynamic Simulation"
        self.results = Snapshot("Quasi-Dynamic Simulation AC")
        self.codes = dict(codes or {})
        self.executed = []

    def GetClassName(self):
        return "ComStatsim"

    def Execute(self):
        name = self.results.loc_name
        self.executed.append(name)
        return self.codes.get(name, 0)


class Folder:
    def __init__(self, items):
        self.items = list(items)

    def GetContents(self, pattern, *args):
        suffix = pattern.split(".")[-1]
        return [i for i in self.items if i.GetClassName() == suffix]


def make_app(scenarios, elements, qds, active=None):
    folders = {"scen": scenarios, "scheme": []}

    class App:
        def __init__(self):
            self.active = active

        def GetProjectFolder(self, key):
            return Folder(folders[key])

        def GetActiveScenario(self):
            return self.active

        def GetFromStudyCase(self, name):
            return qds

        def GetCalcRelevantObjects(self, pattern, *args):
            suffix = pattern.split(".")[-1]
            return [e for e in elements if e.GetClassName() == suffix]

    app = App()
    for scenario in scenarios:
        original_activate = scenario.Activate
        original_deactivate = scenario.Deactivate

        def activate(scenario=scenario, original=original_activate):
            code = original()
            app.active = scenario
            return code

        def deactivate(scenario=scenario, original=original_deactivate):
            code = original()
            if app.active is scenario:
                app.active = None
            return code

        scenario.Activate = activate
        scenario.Deactivate = deactivate
    return app


def test_outage_roundtrip_through_desc_uses_a_list():
    snapshot = Snapshot("GridLens_S01")
    runner.write_outages(snapshot, [("ElmLne", "Leitung 17"), ("ElmTr2", "Trafo 1")])
    assert isinstance(snapshot.desc, list)
    assert runner.read_outages(snapshot) == [
        ("ElmLne", "Leitung 17"), ("ElmTr2", "Trafo 1")
    ]


def test_outage_reading_tolerates_a_hand_written_string():
    snapshot = Snapshot("GridLens_S01")
    snapshot.desc = "ElmLne|Leitung 17\nkaputte Zeile\nElmTr2|Trafo 1"
    assert runner.read_outages(snapshot) == [
        ("ElmLne", "Leitung 17"), ("ElmTr2", "Trafo 1")
    ]


def test_only_out_of_service_elements_are_collected():
    elements = [
        Element("ElmLne", "Leitung 17", 1),
        Element("ElmLne", "Leitung 18", 0),
        Element("ElmTr2", "Trafo 1", 1),
    ]
    app = make_app([], elements, QDS())
    assert runner.collect_outages(app) == [
        ("ElmLne", "Leitung 17"), ("ElmTr2", "Trafo 1")
    ]


def test_every_case_computes_into_its_own_snapshot():
    scenario = Scenario("Freischaltung Nord")
    qds = QDS()
    study = StudyCase()
    app = make_app([scenario], [], qds, active=scenario)
    records = runner.run_cases(app, study, qds=qds)
    assert [r["id"] for r in records] == ["REF", "S01"]
    assert qds.executed == ["GridLens_REF", "GridLens_S01"]
    assert [r["snapshot"] for r in records] == ["GridLens_REF", "GridLens_S01"]
    assert all(r["status"] == "konvergiert" for r in records)


def test_snapshot_prefers_a_copy_of_the_original_result_configuration():
    original = Snapshot("Quasi-Dynamic Simulation AC")
    qds = QDS()
    qds.results = original

    class CopyingStudyCase(StudyCase):
        def __init__(self):
            super().__init__()
            self.templates = []

        def AddCopy(self, template):
            self.templates.append(template)
            snapshot = Snapshot("Kopie")
            self.objects[snapshot.loc_name] = snapshot
            return snapshot

    study = CopyingStudyCase()
    app = make_app([], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    assert study.templates[0] is original
    assert records[0]["snapshot"] == "GridLens_REF"


def test_result_binding_is_restored_after_the_run():
    original = Snapshot("Quasi-Dynamic Simulation AC")
    qds = QDS()
    qds.results = original
    study = StudyCase()
    app = make_app([Scenario("A")], [], qds)
    runner.run_cases(app, study, qds=qds)
    assert qds.results is original


def test_result_binding_is_restored_even_after_an_exception():
    original = Snapshot("Quasi-Dynamic Simulation AC")

    class Exploding(QDS):
        def Execute(self):
            raise KeyboardInterrupt("user aborted")

    qds = Exploding()
    qds.results = original
    study = StudyCase()
    app = make_app([], [], qds)
    with pytest.raises(KeyboardInterrupt):
        runner.run_cases(app, study, qds=qds)
    assert qds.results is original


def test_non_converged_case_is_recorded_in_a_fresh_empty_snapshot():
    qds = QDS(codes={"GridLens_S01": 1})
    study = StudyCase()
    app = make_app([Scenario("Schwierig")], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    failed = records[1]
    assert failed["status"] == "NICHT KONVERGIERT"
    assert failed["error_code"] == 1
    assert failed["snapshot"] is None
    marker = study.objects["GridLens_S01"]
    assert marker.deleted is False
    assert runner.read_snapshot_record(marker)["status"] == "NICHT KONVERGIERT"


def test_the_run_continues_after_a_non_converged_case():
    qds = QDS(codes={"GridLens_S01": 1})
    study = StudyCase()
    app = make_app([Scenario("A Schwierig"), Scenario("B Gut")], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    assert [r["status"] for r in records] == [
        "konvergiert", "NICHT KONVERGIERT", "konvergiert"
    ]


def test_binding_fallback_copies_when_the_write_does_not_take():
    """Some builds may refuse the results assignment. The run must still
    produce a snapshot instead of silently reporting the default result."""

    class Stubborn(QDS):
        def __setattr__(self, name, value):
            if name == "results" and getattr(self, "_locked", False):
                return  # assignment silently ignored
            object.__setattr__(self, name, value)

    qds = Stubborn()
    object.__setattr__(qds, "results", Snapshot("Quasi-Dynamic Simulation AC"))
    object.__setattr__(qds, "_locked", True)

    copies = []

    class CopyingStudyCase(StudyCase):
        def AddCopy(self, produced):
            copy = Snapshot("copy of " + produced.loc_name)
            copies.append(copy)
            self.objects[copy.loc_name] = copy
            return copy

    study = CopyingStudyCase()
    app = make_app([], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    assert records[0]["status"] == "konvergiert"
    assert records[0]["snapshot"] == "GridLens_REF"
    assert copies and copies[0].loc_name == "GridLens_REF"


def test_reference_case_deactivates_the_active_scenario():
    scenario = Scenario("Freischaltung")
    scenario.active = True
    qds = QDS()
    study = StudyCase()
    app = make_app([scenario], [], qds, active=scenario)
    order = []
    original_deactivate = scenario.Deactivate

    def tracking_deactivate():
        order.append("deactivate")
        return original_deactivate()

    scenario.Deactivate = tracking_deactivate
    runner.run_cases(app, study, qds=qds)
    assert order and order[0] == "deactivate"


def test_a_stale_snapshot_is_replaced_not_reused():
    study = StudyCase()
    stale = Snapshot("GridLens_REF")
    study.objects["GridLens_REF"] = stale
    qds = QDS()
    app = make_app([], [], qds)
    runner.run_cases(app, study, qds=qds)
    assert stale.deleted is True
    assert study.objects["GridLens_REF"] is not stale


def test_snapshots_for_removed_scenarios_are_deleted_before_the_run():
    study = StudyCase()
    obsolete = Snapshot("GridLens_S09")
    study.objects[obsolete.loc_name] = obsolete
    qds = QDS()
    app = make_app([], [], qds)
    runner.run_cases(app, study, qds=qds)
    assert obsolete.deleted is True
    assert "GridLens_REF" in study.objects


def test_snapshot_metadata_roundtrip_keeps_name_status_and_outages():
    snapshot = Snapshot("GridLens_S01")
    record = {
        "id": "S01", "name": "Freischaltung = Nord%1",
        "kind": "scenario", "description": "Zeile 1\nZeile 2",
        "status": "konvergiert", "error_code": 0, "message": "",
        "outages": [("ElmLne", "Leitung 17")],
    }
    runner.write_snapshot_record(snapshot, record)
    restored = runner.read_snapshot_record(snapshot)
    assert restored["name"] == record["name"]
    assert restored["description"] == record["description"]
    assert restored["error_code"] == 0
    assert runner.read_outages(snapshot) == [("ElmLne", "Leitung 17")]


def test_original_empty_result_binding_is_restored():
    qds = QDS()
    qds.results = None
    study = StudyCase()
    app = make_app([], [], qds)
    runner.run_cases(app, study, qds=qds)
    assert qds.results is None


def test_failed_activation_is_not_calculated_under_the_wrong_state():
    scenario = Scenario("Nicht aktivierbar")

    def fail_activation():
        return 4

    scenario.Activate = fail_activation
    qds = QDS()
    study = StudyCase()
    app = make_app([scenario], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    assert records[1]["error_code"] == -2
    assert records[1]["status"] == "NICHT KONVERGIERT"
    assert qds.executed == ["GridLens_REF"]
