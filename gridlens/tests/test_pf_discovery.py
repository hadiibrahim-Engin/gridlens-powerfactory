"""Tests fuer die Fall-Discovery des Szenario-Runners."""

import sys
from pathlib import Path

import pytest

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import config, discovery  # noqa: E402


class Obj:
    def __init__(self, cls, name, children=(), **attributes):
        self._class_name = cls
        self.loc_name = name
        self._children = list(children)
        for key, value in attributes.items():
            setattr(self, key, value)

    def GetClassName(self):
        return self._class_name

    def GetFullName(self):
        return "Net." + self.loc_name + "." + self._class_name

    def GetContents(self, pattern, *args):
        suffix = pattern.split(".")[-1]
        return [c for c in self._children if c.GetClassName() == suffix]


def make_app(scenarios=(), schemes=()):
    folders = {
        "scen": Obj("IntPrjfolder", "Operation Scenarios", scenarios),
        "scheme": Obj("IntPrjfolder", "Variations", schemes),
    }

    class App:
        def GetProjectFolder(self, key):
            return folders[key]

    return App()


def test_reference_is_always_first_and_needs_no_object():
    cases = discovery.discover_cases(make_app())
    assert [case["id"] for case in cases] == ["REF"]
    assert cases[0]["object"] is None
    assert cases[0]["kind"] == "reference"


def test_scenarios_are_numbered_alphabetically_for_reproducibility():
    scenarios = [
        Obj("IntScenario", "Zeta Freischaltung"),
        Obj("IntScenario", "Alpha Freischaltung"),
        Obj("IntScenario", "Mitte Freischaltung"),
    ]
    cases = discovery.discover_cases(make_app(scenarios=scenarios))
    assert [(c["id"], c["name"]) for c in cases[1:]] == [
        ("S01", "Alpha Freischaltung"),
        ("S02", "Mitte Freischaltung"),
        ("S03", "Zeta Freischaltung"),
    ]


def test_variations_are_ignored_while_the_flag_is_off(monkeypatch):
    schemes = [Obj("IntScheme", "Ausbau 2027",
                   children=[Obj("IntSstage", "Stufe 1", tAcTime=3600)])]
    monkeypatch.setattr(config, "SCAN_VARIATIONS", False)
    cases = discovery.discover_cases(make_app(schemes=schemes))
    assert [case["id"] for case in cases] == ["REF"]


def test_variations_are_ordered_by_activation_time_when_enabled(monkeypatch):
    schemes = [
        Obj("IntScheme", "Spaet", children=[Obj("IntSstage", "s", tAcTime=10800)]),
        Obj("IntScheme", "Frueh", children=[Obj("IntSstage", "s", tAcTime=3600)]),
    ]
    monkeypatch.setattr(config, "SCAN_VARIATIONS", True)
    cases = discovery.discover_cases(make_app(schemes=schemes))
    assert [(c["id"], c["name"]) for c in cases[1:]] == [
        ("V01", "Frueh"), ("V02", "Spaet")
    ]


def test_variations_precede_scenarios(monkeypatch):
    monkeypatch.setattr(config, "SCAN_VARIATIONS", True)
    app = make_app(
        scenarios=[Obj("IntScenario", "Freischaltung")],
        schemes=[Obj("IntScheme", "Ausbau",
                     children=[Obj("IntSstage", "s", tAcTime=0)])],
    )
    assert [c["id"] for c in discovery.discover_cases(app)] == ["REF", "V01", "S01"]


def test_too_many_cases_abort_before_any_calculation(monkeypatch):
    monkeypatch.setattr(config, "MAX_CASES", 3)
    scenarios = [Obj("IntScenario", "S{}".format(i)) for i in range(5)]
    with pytest.raises(RuntimeError) as excinfo:
        discovery.discover_cases(make_app(scenarios=scenarios))
    message = str(excinfo.value)
    assert "6" in message and "3" in message
    assert "S0" in message


def test_unreadable_folder_yields_only_the_reference():
    class BrokenApp:
        def GetProjectFolder(self, key):
            raise RuntimeError("no such folder")

    assert [c["id"] for c in discovery.discover_cases(BrokenApp())] == ["REF"]
