"""Ermittlung der zu rechnenden Faelle aus dem aktiven Projekt.

Die Reihenfolge ist bewusst deterministisch: S02 muss in zwei Berichtsstaenden
dasselbe Betriebsmittel meinen, sonst ist der Vergleich zweier Berichte
wertlos.
"""

from . import config
from .pfutil import finite_number, object_name, safe_attr

REFERENCE_ID = "REF"


def _project_folder(app, key):
    try:
        return app.GetProjectFolder(key)
    except Exception:
        return None


def _contents(container, pattern):
    if container is None:
        return []
    for args in ((pattern, 1), (pattern,)):
        try:
            found = container.GetContents(*args)
        except Exception:
            continue
        if found:
            return [item for item in found if item is not None]
    return []


def _reference_case():
    return {
        "id": REFERENCE_ID,
        "name": "Grundmodell ohne Freischaltung",
        "kind": "reference",
        "object": None,
        "description": "Referenzzustand; alle Operation Scenarios deaktiviert",
    }


def _activation_time(scheme):
    """Earliest stage activation time; 0.0 when the variation has no stage."""
    times = []
    for stage in _contents(scheme, "*.IntSstage"):
        value = finite_number(safe_attr(stage, "tAcTime", 0))
        times.append(0.0 if value is None else value)
    return min(times) if times else 0.0


def _variation_cases(app):
    schemes = _contents(_project_folder(app, "scheme"), "*.IntScheme")
    ordered = sorted(schemes, key=lambda s: (_activation_time(s), object_name(s)))
    cases = []
    for index, scheme in enumerate(ordered, 1):
        stages = len(_contents(scheme, "*.IntSstage"))
        cases.append({
            "id": "V{:02d}".format(index),
            "name": object_name(scheme),
            "kind": "variation",
            "object": scheme,
            "description": "Network Variation, {} Stufe(n)".format(stages),
        })
    return cases


def _scenario_cases(app):
    scenarios = _contents(_project_folder(app, "scen"), "*.IntScenario")
    ordered = sorted(scenarios, key=object_name)
    return [
        {
            "id": "S{:02d}".format(index),
            "name": object_name(scenario),
            "kind": "scenario",
            "object": scenario,
            "description": "Operation Scenario",
        }
        for index, scenario in enumerate(ordered, 1)
    ]


def discover_cases(app):
    """Return the ordered flat case list, reference first."""
    cases = [_reference_case()]
    if config.SCAN_VARIATIONS:
        cases.extend(_variation_cases(app))
    if config.SCAN_SCENARIOS:
        cases.extend(_scenario_cases(app))
    if len(cases) > config.MAX_CASES:
        listing = ", ".join(
            "{} ({})".format(case["id"], case["name"]) for case in cases)
        raise RuntimeError(
            "Discovery fand {} Faelle, erlaubt sind {} (MAX_CASES). "
            "Kein Rechenlauf gestartet. Gefunden: {}".format(
                len(cases), config.MAX_CASES, listing)
        )
    return cases
