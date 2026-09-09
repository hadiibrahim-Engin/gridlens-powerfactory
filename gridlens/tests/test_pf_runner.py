"""Tests fuer den Szenario-Runner."""

import sys
from pathlib import Path

import pytest

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import runner


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
    def __init__(self, cls, name, outserv, full_name=None):
        self._class_name = cls
        self.loc_name = name
        self.outserv = outserv
        self.full_name = full_name

    def GetClassName(self):
        return self._class_name

    def GetFullName(self):
        return self.full_name or "Net." + self.loc_name + "." + self._class_name


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
    assert [(cls, name) for cls, name, _ in runner.collect_outages(app)] == [
        ("ElmLne", "Leitung 17"), ("ElmTr2", "Trafo 1")
    ]


def test_same_short_name_keeps_both_physical_outages():
    elements = [
        Element("ElmLne", "Leitung 17", 1, "Net.A.Leitung 17.ElmLne"),
        Element("ElmLne", "Leitung 17", 1, "Net.B.Leitung 17.ElmLne"),
    ]
    app = make_app([], elements, QDS())
    outages = runner.collect_outages(app)
    assert len(outages) == 2
    assert {key for _, _, key in outages} == {
        "Net.A.Leitung 17.ElmLne", "Net.B.Leitung 17.ElmLne"
    }


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


def test_aborted_run_never_marks_any_snapshot_set_complete():
    class Exploding(QDS):
        def Execute(self):
            raise KeyboardInterrupt("user aborted")

    qds = Exploding()
    study = StudyCase()
    app = make_app([Scenario("A")], [], qds)
    with pytest.raises(KeyboardInterrupt):
        runner.run_cases(app, study, qds=qds)
    snapshots = list(study.GetContents("*.ElmRes"))
    assert {item.loc_name for item in snapshots} == {
        "GridLens_REF", "GridLens_S01"
    }
    assert {runner.read_snapshot_record(item)["run_state"]
            for item in snapshots} == {"in_progress"}


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


def test_binding_failure_does_not_execute_into_the_original_result():
    """A refused binding must fail before QDS can overwrite the original."""

    class Stubborn(QDS):
        def __setattr__(self, name, value):
            if name == "results" and getattr(self, "_locked", False):
                return  # assignment silently ignored
            object.__setattr__(self, name, value)

    qds = Stubborn()
    object.__setattr__(qds, "results", Snapshot("Quasi-Dynamic Simulation AC"))
    object.__setattr__(qds, "_locked", True)

    study = StudyCase()
    app = make_app([], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    assert records[0]["status"] == "NICHT KONVERGIERT"
    assert records[0]["error_code"] == -4
    assert qds.executed == []
    assert qds.results.loc_name == "Quasi-Dynamic Simulation AC"


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


def test_deactivation_rejects_a_different_remaining_active_scenario():
    original = Scenario("Original")
    unexpected = Scenario("Unexpected")
    qds = QDS()
    app = make_app([original, unexpected], [], qds, active=original)

    def switch_to_other():
        app.active = unexpected
        return 0

    original.Deactivate = switch_to_other
    ok, message = runner._deactivate_active_scenario(app, None)
    assert ok is False
    assert "weiterhin" in message or "aktiv" in message


def test_deactivation_fails_on_an_unreadable_return_value():
    """GL-PR-002: an error code must never be read as a measured number."""
    original = Scenario("Original")
    qds = QDS()
    app = make_app([original], [], qds, active=original)

    def deactivate_with_error_tuple():
        return (1, "Szenario ist gesperrt")

    original.Deactivate = deactivate_with_error_tuple
    ok, message = runner._deactivate_active_scenario(app, None)
    assert ok is False
    assert "Fehlercode" in message


def test_activation_fails_when_the_return_value_cannot_be_read():
    scenario = Scenario("S1")
    qds = QDS()
    app = make_app([scenario], [], qds)

    def activate_unreadable():
        scenario.active = True
        app.active = scenario
        return "unbekannt"

    scenario.Activate = activate_unreadable
    case = {"id": "S01", "name": "S1", "object": scenario}
    ok, message = runner._activate(app, case, None)
    assert ok is False


class Variation:
    """IntScheme double. PowerFactory reports it via GetActiveNetworkVariations."""

    def __init__(self, name):
        self.loc_name = name
        self.active = False

    def GetClassName(self):
        return "IntScheme"

    def GetFullName(self):
        return "Var." + self.loc_name + ".IntScheme"

    def Activate(self):
        self.active = True
        return 0

    def Deactivate(self):
        self.active = False
        return 0


def make_variation_app(variations, qds, active_variations=()):
    folders = {"scen": [], "scheme": list(variations)}

    class App:
        def __init__(self):
            self.active_variations = list(active_variations)

        def GetProjectFolder(self, key):
            return Folder(folders[key])

        def GetActiveScenario(self):
            return None

        def GetActiveNetworkVariations(self):
            return list(self.active_variations)

        def GetFromStudyCase(self, name):
            return qds

        def GetCalcRelevantObjects(self, pattern, *args):
            return []

    app = App()
    wired = list(variations) + [item for item in active_variations
                                if item not in variations]
    for variation in wired:
        original_activate = variation.Activate
        original_deactivate = variation.Deactivate

        def activate(variation=variation, original=original_activate):
            code = original()
            if variation not in app.active_variations:
                app.active_variations.append(variation)
            return code

        def deactivate(variation=variation, original=original_deactivate):
            code = original()
            if variation in app.active_variations:
                app.active_variations.remove(variation)
            return code

        variation.Activate = activate
        variation.Deactivate = deactivate
    return app


def test_a_variation_is_verified_against_the_active_variations():
    """GL-PR-016: an IntScheme never shows up in GetActiveScenario()."""
    variation = Variation("Ausbaustufe 1")
    app = make_variation_app([variation], QDS())
    case = {"id": "V01", "name": "Ausbaustufe 1", "kind": "variation",
            "object": variation}
    ok, message = runner._activate(app, case, None)
    assert ok is True, message


def test_a_variation_that_does_not_become_active_fails():
    variation = Variation("Ausbaustufe 1")
    app = make_variation_app([variation], QDS())
    variation.Activate = lambda: 0
    case = {"id": "V01", "name": "Ausbaustufe 1", "kind": "variation",
            "object": variation}
    ok, _ = runner._activate(app, case, None)
    assert ok is False


def test_the_original_variation_state_is_captured_and_restored():
    """GL-PR-016: a variation active before the run must survive the run."""
    preexisting = Variation("Bestand")
    extra = Variation("Ausbaustufe 1")
    qds = QDS()
    app = make_variation_app([extra], qds, active_variations=[preexisting])
    runner._restore_variations(app, [preexisting], None)
    assert app.active_variations == [preexisting]

    app.active_variations = [extra]
    errors = runner._restore_variations(app, [preexisting], None)
    assert errors == []
    assert app.active_variations == [preexisting]


def test_a_variation_that_cannot_be_restored_is_a_hard_error():
    preexisting = Variation("Bestand")
    qds = QDS()
    app = make_variation_app([], qds, active_variations=[])
    preexisting.Activate = lambda: 1
    errors = runner._restore_variations(app, [preexisting], None)
    assert errors


def test_the_run_restores_variations_before_reporting_success():
    """GL-PR-016: a run that leaves the variation state changed must fail."""
    preexisting = Variation("Bestand")
    qds = QDS()
    study = StudyCase()
    app = make_variation_app([], qds, active_variations=[preexisting])

    def drop_state():
        app.active_variations = []
        return 0

    preexisting.Deactivate = drop_state
    preexisting.Activate = lambda: 1
    app.active_variations = []
    with pytest.raises(RuntimeError, match="Variation"):
        runner.run_cases(app, study, qds=qds,
                         original_variations=[preexisting])
