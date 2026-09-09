# Szenario-Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der GridLens-PowerFactory-Bericht vergleicht mehrere Netzzustände gegen einen Referenzzustand ohne Freischaltung, statt nur den einen aktiven `ElmRes` auszuwerten.

**Architecture:** `powerfactory/gridlens_report.py` wird zur dünnen Einstiegsdatei über dem neuen Paket `powerfactory/gridlens_pf/`. Dieselbe Datei erkennt am Elternobjekt, ob sie als Runner (rechnet je Fall in ein eigenes Snapshot-`ElmRes`) oder als Report-Erweiterung (liest die Snapshots, publiziert einmal) läuft. Die Fachlogik liegt in vier Modulen ohne PowerFactory-Abhängigkeit und ist damit ohne Attrappe testbar.

**Tech Stack:** Python 3.12 (PowerFactory-intern), nur Standardbibliothek · pytest · Stimulsoft-MRT als bearbeitbares XML

## Global Constraints

Diese gelten für **jede** Aufgabe und werden nicht in jeder Aufgabe wiederholt:

- Kein `import json`, keine Mock-Payload, kein direkter SQLite-Zugriff, keine Fremdpakete im Deployment-Paket.
- Nur `math`, `datetime`, `os`, `sys` aus der Standardbibliothek; `powerfactory` ausschließlich in `gridlens_report.py:main()`.
- Es werden genau **18** Tabellen publiziert. Tabellennamen tragen im Skript kein Präfix; PowerFactory ergänzt `Scripted`.
- Grenzwerte: Auslastung `> 100.0` %, Spannung `< 0.95` oder `> 1.05` p.u. Vergleiche strikt.
- `element_name` und `element_id` sind **immer** nur `loc_name`. Vollständige PowerFactory-Pfade erscheinen nie im Bericht.
- Freischaltungstabellen enthalten ausschließlich `outserv=1` / `OFF`.
- Berichtsstatus bleibt `VORPRÜFUNG - KEINE ABSCHLIESSENDE FREIGABE`.
- Nicht konvergierte Fälle liefern **keine** Zeile in Kennzahl-, Ranking-, Balken- oder Vergleichstabellen.
- Ein freigeschaltetes Betriebsmittel ohne Ergebnisreihe erzeugt **keine** Zeile mit `0.0`, sondern gar keine Zeile.
- Nach jeder Aufgabe: `python3 -m pytest -q` läuft grün, dann committen.
- `Report.pdf` niemals löschen oder committen.

**Referenz:** `docs/superpowers/specs/2026-09-07-szenario-runner-design.md`

**Abweichung von der Spezifikation:** Der Modulschnitt in Abschnitt 3.3 nennt neun Module. Der Plan legt ein zehntes an, `entry.py`, das Moduswahl und `main()` aufnimmt. Ohne dieses Modul müsste die Einstiegsdatei die Moduswahl selbst enthalten und wäre nicht mehr dünn genug, um vom Modul-Purge sinnvoll ausgenommen zu sein.

---

### Task 1: Deployment-Paket und reine Basismodule

Mechanischer Umzug ohne Verhaltensänderung. Die bestehenden 103 Tests sind der Beweis der Äquivalenz.

**Files:**
- Create: `powerfactory/gridlens_pf/__init__.py`
- Create: `powerfactory/gridlens_pf/config.py`
- Create: `powerfactory/gridlens_pf/tables.py`
- Create: `powerfactory/gridlens_pf/pfutil.py`
- Create: `powerfactory/gridlens_pf/timeaxis.py`
- Modify: `powerfactory/gridlens_report.py` (Zeilen 15–345 entfernen, Importe einsetzen)
- Modify: `gridlens/tests/test_native_reporting.py:12-19` (Modullader), `:165-173` (Paket-Test)

**Interfaces:**
- Produces: `gridlens_pf.config` mit `RESULT_FILE_NAME`, `HOST_TABLE_PREFIX`, `TOP_N`, `MAX_PLOTS`, `MAX_PLOT_POINTS`, `MAX_BAR_ITEMS`, `LOADING_MAX`, `VOLTAGE_MIN`, `VOLTAGE_MAX`, `TIME_UNIT_FALLBACK`, `PUBLISHER_VERSION`, `TEMPLATE_NAME`, `TEMPLATE_VERSION`, `DATA_CONTRACT_VERSION`, `VARIABLES`, `CLASS_CATEGORIES`
- Produces: `gridlens_pf.tables` mit `TABLES`, `FIELD_TYPES`
- Produces: `gridlens_pf.pfutil` mit `safe_attr(obj, name, default=None)`, `object_key(obj)`, `object_name(obj)`, `object_id(obj)`, `object_description(obj)`, `class_name(obj)`, `result_category(obj, variable)`, `finite_number(value)`, `result_value(elmres, row, column)`
- Produces: `gridlens_pf.timeaxis` mit `normalize_time_unit(unit)`, `time_in_hours(value, unit, row)`, `format_clock(hours)`, `format_time(value, row, unit)`, `format_time_step(hours)`, `time_column(elmres, column_count)`
- Produces: `gridlens_pf` re-exportiert alles davon, damit Tests `native.X` weiter auflösen

- [ ] **Step 1: Paketordner anlegen und Konfiguration verschieben**

Erzeuge `powerfactory/gridlens_pf/config.py`. Übernimm aus `powerfactory/gridlens_report.py` **wörtlich** die Zeilen 13–15, 17–22, 24–28, 30–32, 35–38 und 40–55 (also alles außer `FIELD_TYPES` in Zeile 34). Voran ein Modul-Docstring:

```python
"""Konfiguration des GridLens-Publishers: Grenzwerte, Variablen, Versionen.

Dieses Modul hat keine PowerFactory-Abhängigkeit.
"""
```

Ergänze am Dateiende die neuen Flags aus Abschnitt 4 der Spezifikation:

```python
# Discovery des Runner-Modus. Varianten sind standardmaessig aus: sie tragen in
# realen Projekten meist Modellierungstiefe oder Ausbaustufen und keine
# Schaltzustaende (Spezifikation, Abschnitt 11.1).
SCAN_SCENARIOS = True
SCAN_VARIATIONS = False

# Obergrenze der Rechenlaeufe einschliesslich REF.
MAX_CASES = 12

# Namenspraefix der Snapshot-Ergebnisobjekte im Study Case.
SNAPSHOT_PREFIX = "GridLens_"
```

- [ ] **Step 2: Tabellenvertrag verschieben**

Erzeuge `powerfactory/gridlens_pf/tables.py` mit dem Docstring

```python
"""Vertrag der 18 Report-Tabellen. Muss zu MASTER_GRIDLENS.mrt passen."""
```

und darunter **wörtlich** Zeile 34 (`FIELD_TYPES = ...`) sowie die Zeilen 57–189 (`TABLES = (...)`) aus `gridlens_report.py`.

- [ ] **Step 3: PowerFactory-Hilfsfunktionen verschieben**

Erzeuge `powerfactory/gridlens_pf/pfutil.py`:

```python
"""Duck-typed Zugriffe auf PowerFactory-Objekte und Zahlenumwandlung."""

import math

from .config import CLASS_CATEGORIES, VARIABLES
```

Darunter **wörtlich** die Zeilen 191–271 aus `gridlens_report.py` (`safe_attr` bis einschliesslich `result_value`).

- [ ] **Step 4: Zeitachse verschieben**

Erzeuge `powerfactory/gridlens_pf/timeaxis.py`:

```python
"""Zeiteinheit, Normierung auf Stunden und lesbare Zeitformate."""

from .config import TIME_UNIT_FALLBACK
from .pfutil import finite_number
```

Darunter **wörtlich** die Zeilen 273–344 aus `gridlens_report.py` (`normalize_time_unit` bis einschliesslich `time_column`).

- [ ] **Step 5: `__init__.py` als Re-Export schreiben**

```python
"""GridLens-Laufzeitpaket fuer PowerFactory 2026.

Die Einstiegsdatei gridlens_report.py importiert ausschliesslich aus diesem
Paket. Das Re-Export haelt die bestehende Testschnittstelle stabil.
"""

from .config import (
    CLASS_CATEGORIES, DATA_CONTRACT_VERSION, HOST_TABLE_PREFIX, LOADING_MAX,
    MAX_BAR_ITEMS, MAX_CASES, MAX_PLOTS, MAX_PLOT_POINTS, PUBLISHER_VERSION,
    RESULT_FILE_NAME, SCAN_SCENARIOS, SCAN_VARIATIONS, SNAPSHOT_PREFIX,
    TEMPLATE_NAME, TEMPLATE_VERSION, TIME_UNIT_FALLBACK, TOP_N, VARIABLES,
    VOLTAGE_MAX, VOLTAGE_MIN,
)
from .pfutil import (
    class_name, finite_number, object_description, object_id, object_key,
    object_name, result_category, result_value, safe_attr,
)
from .tables import FIELD_TYPES, TABLES
from .timeaxis import (
    format_clock, format_time, format_time_step, normalize_time_unit,
    time_column, time_in_hours,
)

__all__ = [
    "CLASS_CATEGORIES", "DATA_CONTRACT_VERSION", "FIELD_TYPES",
    "HOST_TABLE_PREFIX", "LOADING_MAX", "MAX_BAR_ITEMS", "MAX_CASES",
    "MAX_PLOTS", "MAX_PLOT_POINTS", "PUBLISHER_VERSION", "RESULT_FILE_NAME",
    "SCAN_SCENARIOS", "SCAN_VARIATIONS", "SNAPSHOT_PREFIX", "TABLES",
    "TEMPLATE_NAME", "TEMPLATE_VERSION", "TIME_UNIT_FALLBACK", "TOP_N",
    "VARIABLES", "VOLTAGE_MAX", "VOLTAGE_MIN", "class_name", "finite_number",
    "format_clock", "format_time", "format_time_step", "normalize_time_unit",
    "object_description", "object_id", "object_key", "object_name",
    "result_category", "result_value", "safe_attr", "time_column",
    "time_in_hours",
]
```

- [ ] **Step 6: `gridlens_report.py` auf die Importe umstellen**

Entferne aus `powerfactory/gridlens_report.py` die Zeilen 13–345 (alle in Schritt 1–4 verschobenen Konstanten und Funktionen). Ersetze den Importblock am Dateikopf durch:

```python
import math
import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from gridlens_pf.config import (
    CLASS_CATEGORIES, DATA_CONTRACT_VERSION, HOST_TABLE_PREFIX, LOADING_MAX,
    MAX_BAR_ITEMS, MAX_PLOTS, MAX_PLOT_POINTS, PUBLISHER_VERSION,
    RESULT_FILE_NAME, TEMPLATE_NAME, TEMPLATE_VERSION, TIME_UNIT_FALLBACK,
    TOP_N, VARIABLES, VOLTAGE_MAX, VOLTAGE_MIN,
)
from gridlens_pf.pfutil import (
    class_name, finite_number, object_description, object_id, object_key,
    object_name, result_category, result_value, safe_attr,
)
from gridlens_pf.tables import FIELD_TYPES, TABLES
from gridlens_pf.timeaxis import (
    format_clock, format_time, format_time_step, normalize_time_unit,
    time_column, time_in_hours,
)
```

Der Rest der Datei (`result_objects` ab der alten Zeile 346 bis `main`) bleibt unverändert.

- [ ] **Step 7: Testlader auf das Paket umstellen**

Ersetze in `gridlens/tests/test_native_reporting.py` die Zeilen 12–19 durch:

```python
DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

spec = importlib.util.spec_from_file_location(
    "native_gridlens", DEPLOYMENT / "gridlens_report.py"
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
```

- [ ] **Step 8: Paket-Test umschreiben**

Ersetze `test_runtime_package_is_two_files_and_has_no_mock_input` (Zeilen 165–173) durch:

```python
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
    sources = [entry] + sorted(package.glob("*.py"))
    for path in sources:
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

    assert native.PUBLISHER_VERSION == "3.0.1"
```

Ergänze `import ast` im Importblock der Testdatei.

- [ ] **Step 9: Tests laufen lassen**

Run: `python3 -m pytest -q`
Expected: `103 passed`

- [ ] **Step 10: Commit**

```bash
git add powerfactory/gridlens_pf powerfactory/gridlens_report.py gridlens/tests/test_native_reporting.py
git commit -m "Extract configuration, tables and helpers into gridlens_pf"
```

---

### Task 2: Ergebnismodul und Publikationsmodul

**Files:**
- Create: `powerfactory/gridlens_pf/results.py`
- Create: `powerfactory/gridlens_pf/publish.py`
- Modify: `powerfactory/gridlens_report.py`
- Modify: `powerfactory/gridlens_pf/__init__.py`

**Interfaces:**
- Consumes: `gridlens_pf.config`, `gridlens_pf.pfutil`, `gridlens_pf.timeaxis`, `gridlens_pf.tables` (Task 1)
- Produces: `gridlens_pf.results` mit `result_objects(study_case)`, `supported_column_count(elmres)`, `select_result(study_case)`, `voltage_level(obj)`, `collect_series(elmres)`, `percentile95(values)`, `statistics(series)`
- Produces: `gridlens_pf.publish` mit `coerce_value(value, kind, where)`, `validate_payload(payload)`, `publish_report(report, payload, log=None)`

- [ ] **Step 1: `results.py` anlegen**

```python
"""Auswahl des Ergebnisobjekts und Aufbereitung der Zeitreihen."""

import math

from .config import RESULT_FILE_NAME, TIME_UNIT_FALLBACK, VARIABLES
from .pfutil import (
    finite_number, object_key, object_name, result_category, result_value,
    safe_attr,
)
from .timeaxis import format_time, normalize_time_unit, time_column, time_in_hours
```

Darunter **wörtlich** die Zeilen 346–518 aus dem heutigen `gridlens_report.py` (`result_objects` bis einschliesslich `statistics`).

- [ ] **Step 2: `publish.py` anlegen**

```python
"""Validierung der Payload und Publikation der nativen IntReport-Tabellen."""

from .pfutil import class_name, finite_number
from .tables import FIELD_TYPES, TABLES
from .config import HOST_TABLE_PREFIX
```

Darunter **wörtlich** die Zeilen 969–1059 aus dem heutigen `gridlens_report.py` (`coerce_value`, `validate_payload`, `publish_report`).

- [ ] **Step 3: Entfernen und importieren**

Entferne die verschobenen Zeilenbereiche aus `gridlens_report.py`. Ergänze im Importblock:

```python
from gridlens_pf.publish import coerce_value, publish_report, validate_payload
from gridlens_pf.results import (
    collect_series, percentile95, result_objects, select_result, statistics,
    supported_column_count, voltage_level,
)
```

- [ ] **Step 4: Re-Export ergänzen**

Ergänze in `powerfactory/gridlens_pf/__init__.py` die entsprechenden `from .results import ...` und `from .publish import ...` Zeilen sowie die Namen in `__all__`.

- [ ] **Step 5: Tests laufen lassen**

Run: `python3 -m pytest -q`
Expected: `103 passed`

- [ ] **Step 6: Commit**

```bash
git add powerfactory/gridlens_pf powerfactory/gridlens_report.py
git commit -m "Extract result reading and report publication into gridlens_pf"
```

---

### Task 3: Payload-Modul

Nach dieser Aufgabe ist `gridlens_report.py` die dünne Einstiegsdatei.

**Files:**
- Create: `powerfactory/gridlens_pf/payload.py`
- Modify: `powerfactory/gridlens_report.py`
- Modify: `powerfactory/gridlens_pf/__init__.py`

**Interfaces:**
- Produces: `gridlens_pf.payload` mit `empty_payload()`, `is_critical(item, stats)`, `maximum_absolute(stats)`, `voltage_deviation(stats)`, `decimal_comma(value)`, `has_time_variation(item)`, `active_scenario(app, study_case)`, `network_elements(app, series)`, `append_loading_bars(payload, table, items, scenario_id)`, `sampled_plot_points(item)`, `append_ranking(...)`, `build_payload(app, study_case, elmres, series, labels, plot_times, time_unit)`

- [ ] **Step 1: `payload.py` anlegen**

```python
"""Aufbau der 18 Report-Tabellen aus ausgewerteten Ergebnisreihen."""

from datetime import datetime

from .config import (
    CLASS_CATEGORIES, DATA_CONTRACT_VERSION, LOADING_MAX, MAX_BAR_ITEMS,
    MAX_PLOTS, MAX_PLOT_POINTS, TEMPLATE_NAME, TEMPLATE_VERSION, TOP_N,
    VARIABLES, VOLTAGE_MAX, VOLTAGE_MIN,
)
from .pfutil import (
    class_name, finite_number, object_description, object_id, object_key,
    object_name, safe_attr,
)
from .results import statistics
from .tables import TABLES
from .timeaxis import format_time_step
```

Darunter **wörtlich** aus dem heutigen `gridlens_report.py`: Zeilen 520–535 (`active_scenario`, `decimal_comma`), 536–567 (`has_time_variation`, `network_elements`), 569–636 (`empty_payload` bis `append_ranking`) und 638–967 (`build_payload`).

- [ ] **Step 2: Einstiegsdatei auf ihr Endmaß bringen**

`powerfactory/gridlens_report.py` besteht danach vollständig aus:

```python
"""PowerFactory 2026 IntReport extension for MASTER_GRIDLENS.mrt.

The script reads existing ElmRes snapshots in the active study case, prepares
report variables in memory and publishes native IntReport tables. It does not
read a mock payload, write SQLite directly or need third-party packages.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# PowerFactory keeps sys.modules across script runs. Without this purge an edit
# to a submodule would not take effect while the entry file still reports the
# new publisher version -- exactly the failure the version banner should catch.
for _name in [n for n in sys.modules
              if n == "gridlens_pf" or n.startswith("gridlens_pf.")]:
    del sys.modules[_name]

from gridlens_pf.entry import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: `entry.py` mit der heutigen `main()` anlegen**

Erzeuge `powerfactory/gridlens_pf/entry.py` mit dem Docstring `"""Moduswahl und Programmeinstieg."""` und **wörtlich** der heutigen `main()` aus `gridlens_report.py` (Zeilen 1061–1090), ergänzt um die nötigen Importe:

```python
from .config import PUBLISHER_VERSION
from .payload import build_payload
from .pfutil import object_name
from .publish import publish_report
from .results import collect_series, select_result
```

- [ ] **Step 4: Testlader anpassen**

`native.build_payload` und `native.collect_series` werden über das Paket-Re-Export aufgelöst. Ergänze in `gridlens_pf/__init__.py` die `from .payload import ...` und `from .entry import main` Zeilen und erweitere `__all__`.

Ersetze in `gridlens/tests/test_native_reporting.py` den Modullader durch:

```python
DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

import gridlens_pf as native  # noqa: E402
```

Passe `test_external_compython_entry_point` (Zeile 374) so an, dass es `native.main` statt `native.main` über die Einstiegsdatei prüft — die Funktion liegt nun in `gridlens_pf.entry`.

- [ ] **Step 5: Tests laufen lassen**

Run: `python3 -m pytest -q`
Expected: `103 passed`

- [ ] **Step 6: Commit**

```bash
git add powerfactory gridlens/tests/test_native_reporting.py
git commit -m "Reduce gridlens_report.py to a thin entry point"
```

---

### Task 4: Discovery der Fälle

**Files:**
- Create: `powerfactory/gridlens_pf/discovery.py`
- Test: `gridlens/tests/test_pf_discovery.py`

**Interfaces:**
- Consumes: `gridlens_pf.config` (`SCAN_SCENARIOS`, `SCAN_VARIATIONS`, `MAX_CASES`), `gridlens_pf.pfutil`
- Produces: `discover_cases(app)` → `list[dict]`. Jeder Fall: `{"id": str, "name": str, "kind": "reference"|"scenario"|"variation", "object": obj|None, "description": str}`. Erster Eintrag ist immer `id == "REF"` mit `object is None`.

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

Erzeuge `gridlens/tests/test_pf_discovery.py`:

```python
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
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_pf_discovery.py -q`
Expected: FAIL mit `ImportError: cannot import name 'discovery'`

- [ ] **Step 3: `discovery.py` implementieren**

```python
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
```

Beachte: `config` wird als Modul importiert, nicht die Einzelwerte. Nur so wirkt `monkeypatch.setattr(config, ...)` in den Tests.

- [ ] **Step 4: Tests ausführen**

Run: `python3 -m pytest gridlens/tests/test_pf_discovery.py -q`
Expected: `7 passed`

- [ ] **Step 5: Gesamtsuite und Commit**

```bash
python3 -m pytest -q
git add powerfactory/gridlens_pf/discovery.py gridlens/tests/test_pf_discovery.py
git commit -m "Discover runner cases with deterministic ordering"
```

---

### Task 5: Runner

**Files:**
- Create: `powerfactory/gridlens_pf/runner.py`
- Test: `gridlens/tests/test_pf_runner.py`

**Interfaces:**
- Consumes: `discovery.discover_cases(app)` (Task 4)
- Produces: `collect_outages(app)` → `list[tuple[str, str]]` als `(class_name, loc_name)`
- Produces: `write_outages(snapshot, outages)`, `read_outages(snapshot)` → `list[tuple[str, str]]`
- Produces: `run_cases(app, study_case, log=None)` → `list[dict]`; jeder Eintrag ist der Fall aus `discover_cases` erweitert um `"status"` (`"konvergiert"` / `"NICHT KONVERGIERT"`), `"error_code"` (`int|None`), `"message"` (`str`), `"snapshot"` (`str|None`), `"outages"` (`list[tuple[str, str]]`)

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

Erzeuge `gridlens/tests/test_pf_runner.py`:

```python
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
    def __init__(self, name, outages=()):
        self.loc_name = name
        self.outages = list(outages)
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
        suffix = pattern.split(".")[-1]
        if suffix == "ElmRes":
            return list(self.objects.values())
        name = pattern.rsplit(".", 1)[0]
        return [self.objects[name]] if name in self.objects else []

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
        self.bindings = []

    def GetClassName(self):
        return "ComStatsim"

    def Execute(self):
        name = self.results.loc_name
        self.executed.append(name)
        self.bindings.append(name)
        return self.codes.get(name, 0)


def make_app(scenarios, elements, qds, active=None):
    folders = {"scen": scenarios, "scheme": []}

    class Folder:
        def __init__(self, items):
            self.items = items

        def GetContents(self, pattern, *args):
            suffix = pattern.split(".")[-1]
            return [i for i in self.items if i.GetClassName() == suffix]

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

    return App()


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
            raise RuntimeError("solver crashed")

    qds = Exploding()
    qds.results = original
    study = StudyCase()
    app = make_app([], [], qds)
    with pytest.raises(RuntimeError):
        runner.run_cases(app, study, qds=qds)
    assert qds.results is original


def test_non_converged_case_is_recorded_and_its_snapshot_deleted():
    qds = QDS(codes={"GridLens_S01": 1})
    study = StudyCase()
    app = make_app([Scenario("Schwierig")], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    failed = records[1]
    assert failed["status"] == "NICHT KONVERGIERT"
    assert failed["error_code"] == 1
    assert failed["snapshot"] is None
    assert study.objects["GridLens_S01"].deleted is True


def test_the_run_continues_after_a_non_converged_case():
    qds = QDS(codes={"GridLens_S01": 1})
    study = StudyCase()
    app = make_app([Scenario("A Schwierig"), Scenario("B Gut")], [], qds)
    records = runner.run_cases(app, study, qds=qds)
    assert [r["status"] for r in records] == [
        "konvergiert", "NICHT KONVERGIERT", "konvergiert"
    ]


def test_binding_fallback_copies_when_the_write_does_not_take():
    """Some builds may refuse the results assignment. Then the run must still
    produce a snapshot instead of silently reporting the default result."""

    class Stubborn(QDS):
        def __setattr__(self, name, value):
            if name == "results" and getattr(self, "_locked", False):
                return  # assignment silently ignored
            object.__setattr__(self, name, value)

    qds = Stubborn()
    fixed = Snapshot("Quasi-Dynamic Simulation AC")
    object.__setattr__(qds, "results", fixed)
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
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_pf_runner.py -q`
Expected: FAIL mit `ImportError: cannot import name 'runner'`

- [ ] **Step 3: `runner.py` implementieren**

```python
"""Rechnet jeden Fall in ein eigenes Snapshot-ElmRes.

Der Runner laeuft niemals als Report-Erweiterung. Er veraendert den
Projektzustand und stellt ihn im finally-Zweig wieder her.
"""

from . import config
from .discovery import REFERENCE_ID, discover_cases
from .pfutil import class_name, finite_number, object_name, safe_attr

OUTAGE_SEPARATOR = "|"
OUTAGE_CLASSES = ("ElmLne", "ElmTr2", "ElmTr3")


def snapshot_name(case_id):
    return config.SNAPSHOT_PREFIX + case_id


def collect_outages(app):
    """Return (class, loc_name) for every switched-off branch element."""
    found = []
    seen = set()
    for pattern in ("*.ElmLne", "*.ElmTr2", "*.ElmTr3"):
        objects = []
        for args in ((pattern, 1), (pattern,)):
            try:
                objects = app.GetCalcRelevantObjects(*args) or []
            except Exception:
                continue
            break
        for obj in objects:
            if finite_number(safe_attr(obj, "outserv", 0)) != 1.0:
                continue
            entry = (class_name(obj), object_name(obj))
            if entry not in seen:
                seen.add(entry)
                found.append(entry)
    return found


def write_outages(snapshot, outages):
    """Persist the outage list in the snapshot description."""
    lines = [
        "{}{}{}".format(element_class, OUTAGE_SEPARATOR, name)
        for element_class, name in outages
    ]
    try:
        snapshot.desc = lines
    except Exception:
        try:
            snapshot.SetAttribute("desc", lines)
        except Exception:
            pass


def read_outages(snapshot):
    """Read the outage list back, tolerating a hand-written string."""
    raw = safe_attr(snapshot, "desc", [])
    if isinstance(raw, str):
        raw = raw.splitlines()
    result = []
    for line in raw or []:
        text = str(line).strip()
        if OUTAGE_SEPARATOR not in text:
            continue
        element_class, name = text.split(OUTAGE_SEPARATOR, 1)
        if element_class.strip() and name.strip():
            result.append((element_class.strip(), name.strip()))
    return result


def _existing(study_case, name):
    for pattern in (name + ".ElmRes", "*.ElmRes"):
        try:
            found = study_case.GetContents(pattern) or []
        except Exception:
            continue
        for item in found:
            if object_name(item) == name:
                return item
    return None


def _prepare_snapshot(study_case, case_id):
    """Return a fresh, empty snapshot ElmRes for one case."""
    name = snapshot_name(case_id)
    stale = _existing(study_case, name)
    if stale is not None:
        try:
            stale.Delete()
        except Exception:
            pass
    return study_case.CreateObject("ElmRes", name)


def _bind_results(qds, snapshot):
    """Point ComStatsim at the snapshot and verify the write took."""
    try:
        qds.results = snapshot
    except Exception:
        try:
            qds.SetAttribute("results", snapshot)
        except Exception:
            return False
    return safe_attr(qds, "results") is snapshot


def _copy_into_snapshot(study_case, produced, case_id):
    """Fallback when the result binding did not take: copy afterwards."""
    name = snapshot_name(case_id)
    try:
        copy = study_case.AddCopy(produced)
    except Exception:
        return None
    if copy is None:
        return None
    try:
        copy.loc_name = name
    except Exception:
        return None
    return copy


def _activate(case, log):
    obj = case["object"]
    if obj is None:
        return
    try:
        obj.Activate()
    except Exception as exc:
        if log:
            log("GridLens: Aktivierung von {} fehlgeschlagen: {}".format(
                case["name"], exc))


def _deactivate_all_scenarios(app, log):
    try:
        active = app.GetActiveScenario()
    except Exception:
        active = None
    if active is None:
        return
    try:
        active.Deactivate()
    except Exception as exc:
        if log:
            log("GridLens: Deaktivierung fehlgeschlagen: {}".format(exc))


def _run_one_case(app, study_case, qds, case, log):
    record = dict(case)
    record.update({"status": "NICHT KONVERGIERT", "error_code": None,
                   "message": "", "snapshot": None, "outages": []})

    _deactivate_all_scenarios(app, log)
    if case["id"] != REFERENCE_ID:
        _activate(case, log)

    record["outages"] = collect_outages(app)
    snapshot = _prepare_snapshot(study_case, case["id"])
    bound = _bind_results(qds, snapshot)

    try:
        code = int(qds.Execute())
    except Exception as exc:
        record["error_code"] = -1
        record["message"] = "ComStatsim.Execute() warf {}: {}".format(
            type(exc).__name__, exc)
        try:
            snapshot.Delete()
        except Exception:
            pass
        return record

    record["error_code"] = code
    if code != 0:
        record["message"] = (
            "ComStatsim.Execute() lieferte Fehlercode {}; Werte werden "
            "nicht ausgewertet.".format(code))
        try:
            snapshot.Delete()
        except Exception:
            pass
        return record

    if not bound:
        produced = safe_attr(qds, "results")
        replacement = _copy_into_snapshot(study_case, produced, case["id"])
        if replacement is None:
            record["message"] = (
                "Ergebnis konnte weder gebunden noch kopiert werden.")
            return record
        snapshot = replacement

    write_outages(snapshot, record["outages"])
    record["status"] = "konvergiert"
    record["message"] = "{} Freischaltung(en)".format(len(record["outages"]))
    record["snapshot"] = snapshot_name(case["id"])
    return record


def run_cases(app, study_case, log=None, qds=None):
    """Compute every discovered case into its own snapshot ElmRes."""
    cases = discover_cases(app)
    if qds is None:
        try:
            qds = app.GetFromStudyCase("ComStatsim")
        except Exception:
            qds = None
    if qds is None:
        raise RuntimeError(
            "ComStatsim nicht im aktiven Study Case gefunden.")

    original_results = safe_attr(qds, "results")
    try:
        original_scenario = app.GetActiveScenario()
    except Exception:
        original_scenario = None

    records = []
    try:
        for case in cases:
            record = _run_one_case(app, study_case, qds, case, log)
            records.append(record)
            if log:
                log("GridLens: {} {} -> {} ({})".format(
                    record["id"], record["name"], record["status"],
                    record["message"]))
    finally:
        # Leaving the QDS command bound to a GridLens snapshot would make every
        # later manual run write into it unnoticed.
        if original_results is not None:
            try:
                qds.results = original_results
            except Exception:
                pass
        _deactivate_all_scenarios(app, log)
        if original_scenario is not None:
            try:
                original_scenario.Activate()
            except Exception:
                pass
    return records
```

- [ ] **Step 4: Tests ausführen**

Run: `python3 -m pytest gridlens/tests/test_pf_runner.py -q`
Expected: `10 passed`

- [ ] **Step 5: Gesamtsuite und Commit**

```bash
python3 -m pytest -q
git add powerfactory/gridlens_pf/runner.py gridlens/tests/test_pf_runner.py
git commit -m "Add scenario runner with per-case result snapshots"
```

---

### Task 6: Fallergebnis und Referenzdeltas

Reine Fachlogik, ohne PowerFactory-Attrappe testbar.

**Files:**
- Modify: `powerfactory/gridlens_pf/payload.py`
- Test: `gridlens/tests/test_pf_reference.py`

**Interfaces:**
- Produces: `scenario_result(case, series, labels, plot_times, time_unit)` → `dict` mit `id`, `name`, `kind`, `description`, `status`, `is_reference`, `labels`, `plot_times`, `time_unit`, `outages`, `by_category` (`{"line"|"transformer"|"voltage"|"voltage_angle": [(item, stats)]}`), `stats_by_key` (`{(category, key): stats}`)
- Produces: `apply_reference(results, reference_id="REF")` — setzt in jedem `stats`-Dict die Schlüssel `ref_min`, `ref_max`, `ref_mean`, `delta_min`, `delta_max`, `delta_mean`; `None`, wenn kein Referenzwert existiert
- Produces: `critical_keys(results, category)` → `set` der `(category, key)` mit Verletzung in mindestens einem konvergierten Fall

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

Erzeuge `gridlens/tests/test_pf_reference.py`:

```python
"""Tests fuer Fallergebnis, Referenzdeltas und Blockvergleich."""

import sys
from pathlib import Path

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import payload  # noqa: E402


def series_item(key, category, values, unit="%"):
    points = [("{:02d}:00".format(i), float(i), v) for i, v in enumerate(values)]
    return {
        "category": category, "object": None, "key": key,
        "element_id": key, "element_name": key, "voltage_level": "110 kV",
        "variable_id": "c:loading", "variable": "Auslastung",
        "unit": unit, "points": points,
    }


def case(case_id, items, status="konvergiert"):
    record = {
        "id": case_id, "name": "Fall " + case_id, "kind": "scenario",
        "description": "", "status": status, "error_code": 0,
        "message": "", "snapshot": None, "outages": [],
    }
    return payload.scenario_result(
        record, items, ["00:00", "01:00", "02:00"], [0.0, 1.0, 2.0], "h")


def test_scenario_result_groups_by_category_and_computes_statistics():
    result = case("REF", [series_item("L1", "line", [10.0, 40.0, 20.0])])
    item, stats = result["by_category"]["line"][0]
    assert item["element_name"] == "L1"
    assert stats["min"] == 10.0 and stats["max"] == 40.0
    assert result["stats_by_key"][("line", "L1")] is stats


def test_reference_flag_is_set_only_for_the_reference_case():
    ref = case("REF", [])
    other = case("S01", [])
    payload.apply_reference([ref, other])
    assert ref["is_reference"] == 1
    assert other["is_reference"] == 0


def test_deltas_are_computed_against_the_reference():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0, 80.0])])
    s01 = case("S01", [series_item("L1", "line", [110.0, 118.0, 112.0])])
    payload.apply_reference([ref, s01])
    stats = s01["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] == 82.0
    assert stats["delta_max"] == 36.0


def test_element_missing_from_the_reference_gets_no_substitute_zero():
    ref = case("REF", [])
    s01 = case("S01", [series_item("L1", "line", [110.0])])
    payload.apply_reference([ref, s01])
    stats = s01["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] is None
    assert stats["delta_max"] is None


def test_a_non_converged_reference_leaves_all_deltas_empty():
    ref = case("REF", [series_item("L1", "line", [80.0])], status="NICHT KONVERGIERT")
    s01 = case("S01", [series_item("L1", "line", [110.0])])
    payload.apply_reference([ref, s01])
    stats = s01["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] is None and stats["delta_max"] is None


def test_reference_case_keeps_zero_delta_against_itself():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0])])
    payload.apply_reference([ref])
    stats = ref["stats_by_key"][("line", "L1")]
    assert stats["ref_max"] == 82.0
    assert stats["delta_max"] == 0.0


def test_critical_keys_span_every_case():
    ref = case("REF", [series_item("L1", "line", [80.0])])
    s01 = case("S01", [series_item("L1", "line", [118.0])])
    assert payload.critical_keys([ref, s01], "line") == {("line", "L1")}


def test_a_non_converged_case_never_makes_an_element_critical():
    ref = case("REF", [series_item("L1", "line", [80.0])])
    bad = case("S01", [series_item("L1", "line", [118.0])],
               status="NICHT KONVERGIERT")
    assert payload.critical_keys([ref, bad], "line") == set()
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_pf_reference.py -q`
Expected: FAIL mit `AttributeError: module 'gridlens_pf.payload' has no attribute 'scenario_result'`

- [ ] **Step 3: Implementieren**

Ergänze in `powerfactory/gridlens_pf/payload.py`:

```python
REFERENCE_ID = "REF"
CONVERGED = "konvergiert"

DELTA_KEYS = (("ref_min", "delta_min", "min"),
              ("ref_max", "delta_max", "max"),
              ("ref_mean", "delta_mean", "mean"))


def scenario_result(case, series, labels, plot_times, time_unit):
    """Build the in-memory result of one case. Knows nothing about tables."""
    by_category = {category: [] for category in VARIABLES}
    stats_by_key = {}
    for item in series:
        stats = statistics(item)
        for reference_key, delta_key, _ in DELTA_KEYS:
            stats[reference_key] = None
            stats[delta_key] = None
        by_category[item["category"]].append((item, stats))
        stats_by_key[(item["category"], item["key"])] = stats
    return {
        "id": case["id"],
        "name": case["name"],
        "kind": case.get("kind", "scenario"),
        "description": case.get("description", ""),
        "status": case.get("status", CONVERGED),
        "error_code": case.get("error_code"),
        "message": case.get("message", ""),
        "outages": list(case.get("outages", ())),
        "is_reference": 1 if case["id"] == REFERENCE_ID else 0,
        "labels": list(labels),
        "plot_times": list(plot_times),
        "time_unit": time_unit,
        "by_category": by_category,
        "stats_by_key": stats_by_key,
    }


def find_reference(results, reference_id=REFERENCE_ID):
    """Return the converged reference case, or None."""
    for result in results:
        if result["id"] == reference_id and result["status"] == CONVERGED:
            return result
    return None


def apply_reference(results, reference_id=REFERENCE_ID):
    """Fill reference values and deltas. Never substitutes 0.0 for missing."""
    for result in results:
        result["is_reference"] = 1 if result["id"] == reference_id else 0
    reference = find_reference(results, reference_id)
    if reference is None:
        return results
    for result in results:
        for key, stats in result["stats_by_key"].items():
            reference_stats = reference["stats_by_key"].get(key)
            if reference_stats is None:
                continue
            for reference_key, delta_key, source in DELTA_KEYS:
                stats[reference_key] = reference_stats[source]
                stats[delta_key] = stats[source] - reference_stats[source]
    return results


def critical_keys(results, category):
    """Keys that violate a limit in at least one converged case."""
    keys = set()
    for result in results:
        if result["status"] != CONVERGED:
            continue
        for item, stats in result["by_category"][category]:
            if is_critical(item, stats):
                keys.add((category, item["key"]))
    return keys
```

- [ ] **Step 4: `collect_series` um den stabilen Schlüssel erweitern**

In `powerfactory/gridlens_pf/results.py` erhält jedes Element des `series`-Dicts einen zusätzlichen Eintrag. Ergänze im `series.append({...})`-Block direkt nach `"category": category,`:

```python
            "key": object_key(obj),
```

Der Schlüssel ist der volle PowerFactory-Pfad und dient ausschliesslich der internen Zuordnung; er erscheint nie im Bericht.

- [ ] **Step 5: Tests ausführen**

Run: `python3 -m pytest gridlens/tests/test_pf_reference.py -q`
Expected: `8 passed`

- [ ] **Step 6: Gesamtsuite und Commit**

```bash
python3 -m pytest -q
git add powerfactory/gridlens_pf gridlens/tests/test_pf_reference.py
git commit -m "Compute per-case results and real reference deltas"
```

---

### Task 7: Mehrfall-Payload mit Blockvergleich

**Files:**
- Modify: `powerfactory/gridlens_pf/payload.py`
- Modify: `powerfactory/gridlens_pf/tables.py` (Feld `bar_label`)
- Test: `gridlens/tests/test_pf_reference.py` (ergänzen)

**Interfaces:**
- Produces: `build_cases_payload(study_case, results, project_name, result_name)` → `dict` mit allen 18 Tabellen
- Ersetzt: das bisherige `build_payload(app, study_case, elmres, series, labels, plot_times, time_unit)` — dieses bleibt als Rückfall für den `AKTIV`-Modus erhalten und ruft intern `build_cases_payload` mit einer einelementigen Fallliste auf

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

Ergänze in `gridlens/tests/test_pf_reference.py`:

```python
def build(results):
    payload.apply_reference(results)
    return payload.build_cases_payload(
        None, results, "Projekt", "GridLens_REF")


def test_block_comparison_emits_a_row_for_every_case():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0])])
    s01 = case("S01", [series_item("L1", "line", [110.0, 118.0])])
    s02 = case("S02", [series_item("L1", "line", [94.0, 96.0])])
    rows = build([ref, s01, s02])["ScriptedLineStatistics"]
    assert [(r["scenario_id"], r["max_loading"]) for r in rows] == [
        ("REF", 82.0), ("S01", 118.0), ("S02", 96.0)
    ]
    assert [r["reference_max_loading"] for r in rows] == [82.0, 82.0, 82.0]
    assert [r["delta_max_loading"] for r in rows] == [0.0, 36.0, 14.0]


def test_an_element_critical_nowhere_produces_no_row():
    ref = case("REF", [series_item("L1", "line", [80.0])])
    s01 = case("S01", [series_item("L1", "line", [82.0])])
    assert build([ref, s01])["ScriptedLineStatistics"] == []


def test_a_switched_off_element_gets_no_zero_row():
    ref = case("REF", [series_item("L1", "line", [118.0])])
    s01 = case("S01", [])
    rows = build([ref, s01])["ScriptedLineStatistics"]
    assert [r["scenario_id"] for r in rows] == ["REF"]


def test_non_converged_case_appears_only_in_scenarios_and_quality():
    ref = case("REF", [series_item("L1", "line", [118.0])])
    bad = case("S01", [series_item("L1", "line", [900.0])],
               status="NICHT KONVERGIERT")
    result = build([ref, bad])
    assert [r["scenario_id"] for r in result["ScriptedLineStatistics"]] == ["REF"]
    assert [r["scenario_id"] for r in result["ScriptedRankings"]] == ["REF"]
    assert [r["scenario_id"] for r in result["ScriptedLineLoadingBars"]] == ["REF"]
    assert "S01" in {r["scenario_id"] for r in result["ScriptedScenarios"]}
    assert any(r["status"] == "FAIL" for r in result["ScriptedModelQuality"])


def test_bar_label_carries_the_case_id():
    ref = case("REF", [series_item("L1", "line", [118.0])])
    bars = build([ref])["ScriptedLineLoadingBars"]
    assert bars[0]["bar_label"] == "REF · L1"
    assert bars[0]["element_name"] == "L1"


def test_outages_and_matrix_come_from_the_case_record():
    ref = case("REF", [])
    s01 = case("S01", [])
    s01["outages"] = [("ElmLne", "Leitung 17")]
    result = build([ref, s01])
    assert [(r["scenario_id"], r["element_name"])
            for r in result["ScriptedOutages"]] == [("S01", "Leitung 17")]
    assert result["ScriptedScenarioMatrix"][0]["status_label"] == "OFF"
    assert result["ScriptedScenarioMatrix"][0]["is_out_of_service"] == 1
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_pf_reference.py -q`
Expected: FAIL mit `AttributeError: ... has no attribute 'build_cases_payload'`

- [ ] **Step 3: `bar_label` in den Tabellenvertrag aufnehmen**

Ergänze in `powerfactory/gridlens_pf/tables.py` in allen **vier** Balkentabellen `ScriptedLineLoadingBars`, `ScriptedTransformerLoadingBars`, `ScriptedVoltageMagnitudeBars`, `ScriptedVoltageAngleBars` direkt nach `("element_name", "string"),` das Feld:

```python
        ("bar_label", "string"),
```

- [ ] **Step 4: `build_cases_payload` implementieren**

Ersetze in `powerfactory/gridlens_pf/payload.py` die bisherige `build_payload`-Funktion durch die folgenden Funktionen. Die Metadaten-, Qualitäts- und Grenzwerttexte werden aus der alten Funktion übernommen, nur die Schleife über die Fälle ist neu.

```python
def bar_label(case_id, element_name):
    """Axis label that keeps the same element distinguishable across cases."""
    if case_id == "AKTIV":
        return element_name
    return "{} · {}".format(case_id, element_name)


def converged(results):
    return [result for result in results if result["status"] == CONVERGED]


def _statistics_rows(payload, results, category, table, fields):
    """Block comparison: one row per case for every element critical anywhere."""
    keys = critical_keys(results, category)
    if not keys:
        return
    ordered = sorted(keys, key=lambda entry: entry[1])
    for _, key in ordered:
        for result in converged(results):
            stats = result["stats_by_key"].get((category, key))
            if stats is None:
                continue  # switched off in this case: no row, never a 0.0 row
            item = next(entry[0] for entry in result["by_category"][category]
                        if entry[0]["key"] == key)
            row = {
                "scenario_id": result["id"],
                "element_id": item["element_id"],
                "element_name": item["element_name"],
                "voltage_level": item["voltage_level"],
            }
            row.update({name: stats[source] for name, source in fields})
            payload[table].append(row)


LINE_FIELDS = (
    ("min_loading", "min"), ("max_loading", "max"),
    ("mean_loading", "mean"), ("p95_loading", "p95"),
    ("time_of_min_loading", "time_min"), ("time_of_max_loading", "time_max"),
    ("reference_max_loading", "ref_max"), ("delta_max_loading", "delta_max"),
)
TRANSFORMER_FIELDS = tuple(
    entry for entry in LINE_FIELDS if entry[0] != "time_of_min_loading")
VOLTAGE_FIELDS = (
    ("min_voltage", "min"), ("max_voltage", "max"), ("mean_voltage", "mean"),
    ("time_of_min_voltage", "time_min"), ("time_of_max_voltage", "time_max"),
    ("reference_min_voltage", "ref_min"), ("reference_max_voltage", "ref_max"),
    ("delta_min_voltage", "delta_min"), ("delta_max_voltage", "delta_max"),
)
```

Die Aufrufe im Hauptteil lauten:

```python
    _statistics_rows(payload, results, "line",
                     "ScriptedLineStatistics", LINE_FIELDS)
    _statistics_rows(payload, results, "transformer",
                     "ScriptedTransformerStatistics", TRANSFORMER_FIELDS)
    _statistics_rows(payload, results, "voltage",
                     "ScriptedVoltageStatistics", VOLTAGE_FIELDS)
```

Fälle, Freischaltungen und Matrix:

```python
    for result in results:
        payload["ScriptedScenarios"].append({
            "scenario_id": result["id"],
            "scenario_name": result["name"],
            "is_reference": result["is_reference"],
            "description": result["description"],
            "simulation_status": result["status"],
            "simulation_start": result["labels"][0] if result["labels"] else "",
            "simulation_end": result["labels"][-1] if result["labels"] else "",
        })
        if result["status"] != CONVERGED:
            payload["ScriptedModelQuality"].append({
                "check_id": "case_" + result["id"],
                "check_name": "Rechenlauf " + result["id"],
                "status": "FAIL",
                "message": result["message"] or "Nicht konvergiert.",
                "affected_element": result["name"],
            })
        for element_class, name in result["outages"]:
            payload["ScriptedOutages"].append({
                "scenario_id": result["id"], "outage_id": name,
                "element_id": name, "element_name": name,
                "element_type": element_class,
                "start_time": result["labels"][0] if result["labels"] else "",
                "end_time": result["labels"][-1] if result["labels"] else "",
                "action": "im Modell ausser Betrieb",
            })
            payload["ScriptedScenarioMatrix"].append({
                "element_id": name, "element_name": name,
                "element_type": element_class, "scenario_id": result["id"],
                "is_out_of_service": 1, "status_label": "OFF",
            })
```

Balken, Rankings und Vergleichstabellen sammeln jetzt über alle konvergierten Fälle. `append_loading_bars` und `append_ranking` aus der alten Fassung werden durch diese Funktionen **ersetzt**:

```python
def _collect(results, category, only_critical=True, predicate=None):
    """Flatten (case_id, item, stats) across every converged case."""
    entries = []
    for result in converged(results):
        for item, stats in result["by_category"][category]:
            if only_critical and not is_critical(item, stats):
                continue
            if predicate is not None and not predicate(stats):
                continue
            entries.append((result["id"], item, stats))
    return entries


def _loading_bars(payload, results, category, table):
    entries = sorted(_collect(results, category),
                     key=lambda entry: entry[2]["max"], reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        payload[table].append({
            "rank": rank, "scenario_id": case_id,
            "element_id": item["element_id"],
            "element_name": item["element_name"],
            "bar_label": bar_label(case_id, item["element_name"]),
            "voltage_level": item["voltage_level"],
            "max_loading": stats["max"], "unit": item["unit"],
            "event_time": stats["time_max"],
        })


def _voltage_bars(payload, results):
    entries = sorted(_collect(results, "voltage"),
                     key=lambda entry: voltage_deviation(entry[2]), reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        payload["ScriptedVoltageMagnitudeBars"].append({
            "rank": rank, "scenario_id": case_id,
            "element_id": item["element_id"],
            "element_name": item["element_name"],
            "bar_label": bar_label(case_id, item["element_name"]),
            "voltage_level": item["voltage_level"],
            "min_voltage": stats["min"], "max_voltage": stats["max"],
            "mean_voltage": stats["mean"],
            "deviation": voltage_deviation(stats),
            "status_label": "GRENZWERTVERLETZUNG",
            "unit": item["unit"],
        })


def _angle_bars(payload, results):
    # Angles are informative and have no blanket limit, so no critical filter.
    entries = sorted(_collect(results, "voltage_angle", only_critical=False),
                     key=lambda entry: maximum_absolute(entry[2]), reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        event_time = (stats["time_min"] if abs(stats["min"]) >= abs(stats["max"])
                      else stats["time_max"])
        payload["ScriptedVoltageAngleBars"].append({
            "rank": rank, "scenario_id": case_id,
            "element_id": item["element_id"],
            "element_name": item["element_name"],
            "bar_label": bar_label(case_id, item["element_name"]),
            "voltage_level": item["voltage_level"],
            "min_angle": stats["min"], "max_angle": stats["max"],
            "mean_angle": stats["mean"],
            "max_abs_angle": maximum_absolute(stats),
            "angle_span": stats["max"] - stats["min"],
            "event_time": event_time, "unit": item["unit"],
        })


def _rankings(payload, results, ranking_type, category, metric_name,
              value_key, time_key, reverse, predicate=None):
    entries = sorted(_collect(results, category, predicate=predicate),
                     key=lambda entry: entry[2][value_key], reverse=reverse)
    reference_key = "ref_min" if value_key == "min" else "ref_max"
    delta_key = "delta_min" if value_key == "min" else "delta_max"
    for rank, (case_id, item, stats) in enumerate(entries[:TOP_N], 1):
        payload["ScriptedRankings"].append({
            "ranking_type": ranking_type, "rank": rank,
            "scenario_id": case_id, "element_id": item["element_id"],
            "element_name": item["element_name"],
            "element_type": item["category"], "metric_name": metric_name,
            "metric_value": stats[value_key], "unit": item["unit"],
            # Real reference values now. The old code wrote metric_value and
            # 0.0 here, which claimed a comparison that did not exist.
            "reference_value": stats[reference_key],
            "delta_value": stats[delta_key],
            "event_time": stats[time_key],
        })


def _reference_comparison(payload, results):
    reference = find_reference(results)
    if reference is None:
        return
    for result in converged(results):
        if result["id"] == reference["id"]:
            continue
        for category in ("line", "transformer", "voltage"):
            for _, key in sorted(critical_keys(results, category)):
                stats = result["stats_by_key"].get((category, key))
                reference_stats = reference["stats_by_key"].get((category, key))
                if stats is None or reference_stats is None:
                    continue
                item = next(entry[0] for entry in result["by_category"][category]
                            if entry[0]["key"] == key)
                payload["ScriptedReferenceComparison"].append({
                    "scenario_id": result["id"],
                    "element_id": item["element_id"],
                    "element_name": item["element_name"],
                    "element_type": category, "variable": item["variable"],
                    "unit": item["unit"],
                    "reference_min": reference_stats["min"],
                    "scenario_min": stats["min"], "delta_min": stats["delta_min"],
                    "reference_max": reference_stats["max"],
                    "scenario_max": stats["max"], "delta_max": stats["delta_max"],
                    "reference_mean": reference_stats["mean"],
                    "scenario_mean": stats["mean"],
                    "delta_mean": stats["delta_mean"],
                })


COMPARISON_METRICS = (
    ("max_line_loading", "Maximale Leitungsauslastung", "line", "max", True, None),
    ("max_transformer_loading", "Maximale Transformatorauslastung",
     "transformer", "max", True, None),
    ("min_voltage", "Minimale Spannung", "voltage", "min", False,
     lambda stats: stats["min"] < VOLTAGE_MIN),
    ("max_voltage", "Maximale Spannung", "voltage", "max", True,
     lambda stats: stats["max"] > VOLTAGE_MAX),
)


def _scenario_comparison(payload, results):
    for key, name, category, value_key, reverse, predicate in COMPARISON_METRICS:
        for result in converged(results):
            entries = _collect([result], category, predicate=predicate)
            if not entries:
                continue
            _, item, stats = sorted(
                entries, key=lambda entry: entry[2][value_key], reverse=reverse)[0]
            payload["ScriptedScenarioComparison"].append({
                "metric_key": key, "metric_name": name, "unit": item["unit"],
                "scenario_id": result["id"], "metric_value": stats[value_key],
                "element_id": item["element_id"],
                "element_name": item["element_name"],
            })


def _relevant_time_points(payload, results):
    selected = []
    loading = sorted(_collect(results, "line") + _collect(results, "transformer"),
                     key=lambda entry: entry[2]["max"], reverse=True)[:TOP_N]
    for case_id, item, stats in loading:
        reason = ("Maximale Leitungsauslastung" if item["category"] == "line"
                  else "Maximale Transformatorauslastung")
        selected.append((case_id, item, stats, reason, "max", "time_max"))
    low = sorted(_collect(results, "voltage",
                          predicate=lambda s: s["min"] < VOLTAGE_MIN),
                 key=lambda entry: entry[2]["min"])[:TOP_N]
    for case_id, item, stats in low:
        selected.append((case_id, item, stats, "Minimale Spannung", "min", "time_min"))
    high = sorted(_collect(results, "voltage",
                           predicate=lambda s: s["max"] > VOLTAGE_MAX),
                  key=lambda entry: entry[2]["max"], reverse=True)[:TOP_N]
    for case_id, item, stats in high:
        selected.append((case_id, item, stats, "Maximale Spannung", "max", "time_max"))
    for case_id, item, stats, reason, value_key, time_key in selected:
        payload["ScriptedRelevantTimePoints"].append({
            "timestamp": stats[time_key], "scenario_id": case_id,
            "reason": reason, "element_id": item["element_id"],
            "element_name": item["element_name"],
            "metric_name": item["variable"], "metric_value": stats[value_key],
            "unit": item["unit"],
        })
```

Die Aufrufe im Hauptteil von `build_cases_payload`:

```python
    _loading_bars(payload, results, "line", "ScriptedLineLoadingBars")
    _loading_bars(payload, results, "transformer",
                  "ScriptedTransformerLoadingBars")
    _voltage_bars(payload, results)
    _angle_bars(payload, results)
    _rankings(payload, results, "highest_line_loading", "line",
              "Maximale Auslastung", "max", "time_max", True)
    _rankings(payload, results, "highest_transformer_loading", "transformer",
              "Maximale Auslastung", "max", "time_max", True)
    _rankings(payload, results, "lowest_voltage", "voltage",
              "Minimale Spannung", "min", "time_min", False,
              predicate=lambda stats: stats["min"] < VOLTAGE_MIN)
    _rankings(payload, results, "highest_voltage", "voltage",
              "Maximale Spannung", "max", "time_max", True,
              predicate=lambda stats: stats["max"] > VOLTAGE_MAX)
    _scenario_comparison(payload, results)
    _reference_comparison(payload, results)
    _relevant_time_points(payload, results)
```

- [ ] **Step 5: `build_payload` als Rückfall erhalten**

```python
def build_payload(app, study_case, elmres, series, labels, plot_times, time_unit):
    """Single-state fallback: one case with the compact id AKTIV."""
    scenario_id, scenario_name, description = active_scenario(app, study_case)
    outages = []
    for obj in network_elements(app, series):
        if finite_number(safe_attr(obj, "outserv", 0)) == 1.0:
            outages.append((class_name(obj), object_name(obj)))
    case = {
        "id": scenario_id, "name": scenario_name, "kind": "active",
        "description": description, "status": CONVERGED, "error_code": 0,
        "message": "", "snapshot": None, "outages": outages,
    }
    result = scenario_result(case, series, labels, plot_times, time_unit)
    apply_reference([result], reference_id=scenario_id)
    project = None
    try:
        project = app.GetActiveProject()
    except Exception:
        pass
    return build_cases_payload(
        study_case, [result],
        object_name(project) if project else "Aktives PowerFactory-Modell",
        object_name(elmres))
```

Im Rückfallmodus liefert `bar_label()` nur den `element_name` — der Zweig ist dort bereits enthalten.

- [ ] **Step 6: Tests ausführen**

Run: `python3 -m pytest gridlens/tests/test_pf_reference.py -q`
Expected: `14 passed`

- [ ] **Step 7: Gesamtsuite und Commit**

```bash
python3 -m pytest -q
git add powerfactory/gridlens_pf gridlens/tests/test_pf_reference.py
git commit -m "Build the report payload from a list of cases"
```

---

### Task 8: Zeitreihen über alle Fälle

**Files:**
- Modify: `powerfactory/gridlens_pf/payload.py`
- Modify: `powerfactory/gridlens_pf/publish.py`
- Test: `gridlens/tests/test_pf_reference.py` (ergänzen)

**Interfaces:**
- `ScriptedPlotData.series_role` trägt die Fall-ID statt `"Referenz"`/`"Szenario"`
- `validate_payload` prüft `series_role` gegen die in `ScriptedScenarios` gemeldeten IDs

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

```python
def test_each_plot_carries_one_curve_per_case_and_only_its_own_element():
    ref = case("REF", [series_item("L1", "line", [80.0, 82.0]),
                       series_item("L2", "line", [10.0, 12.0])])
    s01 = case("S01", [series_item("L1", "line", [110.0, 118.0]),
                       series_item("L2", "line", [11.0, 13.0])])
    result = build([ref, s01])
    plots = result["ScriptedPlots"]
    assert len(plots) == 1
    assert plots[0]["element_name"] == "L1"
    roles = {r["series_role"] for r in result["ScriptedPlotData"]
             if r["plot_id"] == plots[0]["plot_id"]}
    assert roles == {"REF", "S01"}


def test_plot_data_never_mixes_two_elements():
    ref = case("REF", [series_item("L1", "line", [118.0]),
                       series_item("T1", "transformer", [130.0])])
    result = build([ref])
    by_plot = {}
    for row in result["ScriptedPlotData"]:
        by_plot.setdefault(row["plot_id"], set()).add(row["value"])
    assert by_plot == {"P001": {118.0}, "P002": {130.0}}


def test_validate_payload_accepts_case_ids_as_series_role():
    ref = case("REF", [series_item("L1", "line", [118.0])])
    s01 = case("S01", [series_item("L1", "line", [120.0])])
    from gridlens_pf import publish
    publish.validate_payload(build([ref, s01]))


def test_validate_payload_rejects_an_unknown_series_role():
    from gridlens_pf import publish
    ref = case("REF", [series_item("L1", "line", [118.0])])
    data = build([ref])
    data["ScriptedPlotData"][0]["series_role"] = "Phantom"
    with pytest.raises(ValueError, match="series_role"):
        publish.validate_payload(data)
```

Ergänze `import pytest` in der Testdatei.

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_pf_reference.py -q`
Expected: FAIL — `roles == {"Szenario"}` statt `{"REF", "S01"}`

- [ ] **Step 3: Diagrammauswahl über alle Fälle implementieren**

In `build_cases_payload`:

```python
    plot_keys = []
    for category, use_min in (("line", False), ("transformer", False),
                              ("voltage", True), ("voltage", False)):
        candidates = []
        for result in converged(results):
            for item, stats in result["by_category"][category]:
                if not is_critical(item, stats):
                    continue
                if category == "voltage":
                    if use_min and stats["min"] >= VOLTAGE_MIN:
                        continue
                    if not use_min and stats["max"] <= VOLTAGE_MAX:
                        continue
                candidates.append((stats["min"] if use_min else stats["max"],
                                   item))
        if not candidates:
            continue
        best = (min(candidates, key=lambda e: e[0]) if use_min
                else max(candidates, key=lambda e: e[0]))[1]
        entry = (category, best["key"], best)
        if not any(existing[1] == best["key"] for existing in plot_keys):
            plot_keys.append(entry)

    for index, (category, key, item) in enumerate(plot_keys[:MAX_PLOTS], 1):
        plot_id = "P{:03d}".format(index)
        payload["ScriptedPlots"].append({
            "plot_id": plot_id,
            "plot_title": "{} - {}".format(item["element_name"], item["variable"]),
            "scenario_id": "", "element_id": item["element_id"],
            "element_name": item["element_name"],
            "variable": item["variable"], "unit": item["unit"],
        })
        for result in converged(results):
            match = next((entry[0] for entry in result["by_category"][category]
                          if entry[0]["key"] == key), None)
            if match is None:
                continue
            for _, timestamp, value in sampled_plot_points(match):
                payload["ScriptedPlotData"].append({
                    "plot_id": plot_id, "scenario_id": result["id"],
                    "series_role": result["id"], "timestamp": timestamp,
                    "value": value,
                })
```

- [ ] **Step 4: `validate_payload` anpassen**

Ersetze in `powerfactory/gridlens_pf/publish.py` den Block

```python
        if row.get("series_role") not in ("Referenz", "Szenario"):
```

durch:

```python
    known_roles = {row.get("scenario_id") for row in payload["ScriptedScenarios"]}
```

vor der Schleife, und in der Schleife:

```python
        if row.get("series_role") not in known_roles:
```

Die Fehlermeldung bleibt: `"ScriptedPlotData row {} has invalid series_role."`

- [ ] **Step 5: Tests ausführen**

Run: `python3 -m pytest gridlens/tests/test_pf_reference.py -q`
Expected: `18 passed`

- [ ] **Step 6: Gesamtsuite und Commit**

```bash
python3 -m pytest -q
git add powerfactory/gridlens_pf gridlens/tests/test_pf_reference.py
git commit -m "Draw one time-series curve per case in each chart"
```

---

### Task 9: MRT-Anpassungen

**Files:**
- Modify: `powerfactory/MASTER_GRIDLENS.mrt`
- Test: `gridlens/tests/test_native_reporting.py` (Diagrammtest ergänzen)

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

Ergänze in `gridlens/tests/test_native_reporting.py`:

```python
def test_time_series_auto_series_can_show_distinct_colours():
    """Auto-series copy the template series. With AllowApplyStyle=False and a
    hard-coded LineColor every case curve would render in the same burgundy."""
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    series = root.find(".//*[@type='Stimulsoft.Report.Chart.StiLineSeries']")
    assert series is not None
    assert series.findtext("AllowApplyStyle") == "True"
    assert series.findtext("AutoSeriesKeyDataColumn") == "ScriptedPlotData.series_role"
    assert series.findtext("AutoSeriesColorDataColumn") in (None, "")
    chart = root.find(".//*[@type='Stimulsoft.Report.Chart.StiChart']")
    assert chart.findtext("Style") is not None


def test_bar_charts_are_labelled_with_the_case_id():
    root = ET.parse(DEPLOYMENT / "MASTER_GRIDLENS.mrt").getroot()
    bars = root.findall(".//*[@type='Stimulsoft.Report.Chart.StiClusteredBarSeries']")
    assert bars
    for series in bars:
        argument = series.findtext("ArgumentDataColumn") or ""
        assert argument.endswith(".bar_label"), argument
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_native_reporting.py -q -k "auto_series or bar_charts"`
Expected: FAIL — `AllowApplyStyle` ist `False`, `ArgumentDataColumn` endet auf `.element_name`

- [ ] **Step 3: Spaltenlisten der vier Balkenquellen erweitern**

In `powerfactory/MASTER_GRIDLENS.mrt` bei jeder der vier `StiSQLiteSource`-Definitionen `ScriptedLineLoadingBars`, `ScriptedTransformerLoadingBars`, `ScriptedVoltageMagnitudeBars`, `ScriptedVoltageAngleBars`:

- `<value>bar_label,System.String</value>` direkt nach der `element_name`-Zeile einfügen
- das `count`-Attribut von `<Columns isList="true" count="N">` um eins erhöhen

`test_mrt_sources_match_embedded_table_contract` prüft diese Übereinstimmung.

- [ ] **Step 4: Balkenachsen umstellen**

In allen sechs `StiClusteredBarSeries`-Blöcken `ArgumentDataColumn` von `<Quelle>.element_name` auf `<Quelle>.bar_label` ändern.

- [ ] **Step 5: Diagrammfarben reparieren**

Im `StiLineSeries`-Block der Zeitreihe (`PlotsChart`):

- `<AllowApplyStyle>False</AllowApplyStyle>` → `True`
- Die Zeilen `<LineColor>181, 18, 62</LineColor>`, den `StiLineMarker`-Block und den `StiMarker`-Block entfernen, damit die Palette greift.

Im `StiChart`-Block `PlotsChart` unmittelbar vor `<Series ...>` einfügen:

```xml
              <Style Ref="900" type="Stimulsoft.Report.Chart.StiStyleFB01" isKey="true">
                <Chart isRef="349" />
                <StyleColors isList="true" count="6">
                  <value>128, 128, 128</value>
                  <value>181, 18, 62</value>
                  <value>0, 112, 192</value>
                  <value>0, 143, 92</value>
                  <value>222, 138, 0</value>
                  <value>112, 48, 160</value>
                </StyleColors>
              </Style>
```

Die erste Farbe ist neutrales Grau. Weil `ScriptedPlotData` nach `plot_id, series_role, timestamp` sortiert ist und `REF` alphabetisch vor `S01` und `V01` liegt, erhält der Referenzfall stabil das Grau und die Szenarien die Signalfarben.

- [ ] **Step 6: Tests ausführen**

Run: `python3 -m pytest -q`
Expected: alle Tests grün, einschliesslich `test_mrt_sources_match_embedded_table_contract`

- [ ] **Step 7: Commit**

```bash
git add powerfactory/MASTER_GRIDLENS.mrt gridlens/tests/test_native_reporting.py
git commit -m "Give each case curve its own colour and label bars by case"
```

---

### Task 10: Moduswahl und Report-Modus

**Files:**
- Modify: `powerfactory/gridlens_pf/entry.py`
- Test: `gridlens/tests/test_pf_entry.py`

**Interfaces:**
- Produces: `main()` — wählt Modus über `script.GetParent()`
- Produces: `run_report_mode(app, study_case, report, log=None)` → `dict` der Zeilenzahlen
- Produces: `load_snapshots(study_case)` → `list[tuple[str, obj]]`, nach Fall-ID sortiert (`REF` zuerst)

- [ ] **Step 1: Den fehlschlagenden Test schreiben**

Erzeuge `gridlens/tests/test_pf_entry.py`:

```python
"""Tests fuer Moduswahl und Report-Modus."""

import sys
from pathlib import Path

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
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_pf_entry.py -q`
Expected: FAIL mit `AttributeError: module 'gridlens_pf.entry' has no attribute 'load_snapshots'`

- [ ] **Step 3: Implementieren**

```python
def select_mode(parent):
    """The parent object decides the mode; no configuration parameter."""
    return "report" if class_name(parent) == "IntReport" else "runner"


def load_snapshots(study_case):
    """Return (case_id, elmres) for every GridLens snapshot, reference first."""
    try:
        found = study_case.GetContents("*.ElmRes") or []
    except Exception:
        return []
    snapshots = []
    for item in found:
        name = object_name(item)
        if not name.startswith(SNAPSHOT_PREFIX):
            continue
        snapshots.append((name[len(SNAPSHOT_PREFIX):], item))
    return sorted(snapshots, key=lambda entry: (entry[0] != "REF", entry[0]))


def run_report_mode(app, study_case, report, log=None):
    snapshots = load_snapshots(study_case)
    if not snapshots:
        elmres = select_result(study_case)
        if log:
            log("GridLens result: " + object_name(elmres))
        try:
            elmres.Load()
            series, labels, plot_times, time_unit = collect_series(elmres)
            data = build_payload(app, study_case, elmres, series, labels,
                                 plot_times, time_unit)
        finally:
            try:
                elmres.Release()
            except Exception:
                pass
        return publish_report(report, data, log=log)

    results = []
    for case_id, elmres in snapshots:
        try:
            elmres.Load()
            series, labels, plot_times, time_unit = collect_series(elmres)
            case = {
                "id": case_id,
                "name": object_name(elmres),
                "kind": "reference" if case_id == "REF" else "scenario",
                "description": "Snapshot " + object_name(elmres),
                "status": CONVERGED,
                "error_code": 0,
                "message": "",
                "outages": read_outages(elmres),
            }
            results.append(scenario_result(
                case, series, labels, plot_times, time_unit))
        finally:
            try:
                elmres.Release()
            except Exception:
                pass
    apply_reference(results)
    project = None
    try:
        project = app.GetActiveProject()
    except Exception:
        pass
    data = build_cases_payload(
        study_case, results,
        object_name(project) if project else "Aktives PowerFactory-Modell",
        ", ".join(object_name(item) for _, item in snapshots))
    return publish_report(report, data, log=log)


def main():
    import powerfactory

    app = powerfactory.GetApplication()
    if app is None:
        raise RuntimeError("PowerFactory application is unavailable.")
    script = app.GetCurrentScript()
    study_case = app.GetActiveStudyCase()
    if script is None:
        raise RuntimeError("No active ComPython script.")
    if study_case is None:
        raise RuntimeError("No active study case.")

    app.PrintPlain("GridLens publisher: " + PUBLISHER_VERSION)
    app.PrintPlain("GridLens study case: " + object_name(study_case))

    parent = script.GetParent()
    if select_mode(parent) == "runner":
        app.PrintPlain("GridLens mode: runner")
        records = run_cases(app, study_case, log=app.PrintPlain)
        converged_count = sum(
            1 for record in records if record["status"] == CONVERGED)
        app.PrintPlain(
            "GridLens: {} von {} Faellen konvergiert; Bericht jetzt ueber den "
            "IntReport erzeugen.".format(converged_count, len(records)))
        return

    app.PrintPlain("GridLens mode: report")
    counts = run_report_mode(app, study_case, parent, log=app.PrintPlain)
    app.PrintPlain(
        "GridLens: {} active-model tables published.".format(len(counts)))
```

Ergänze die nötigen Importe am Modulkopf von `entry.py`:

```python
from .config import PUBLISHER_VERSION, SNAPSHOT_PREFIX
from .payload import (
    CONVERGED, apply_reference, build_cases_payload, build_payload,
    scenario_result,
)
from .pfutil import class_name, object_name
from .publish import publish_report
from .results import collect_series, select_result
from .runner import read_outages, run_cases
```

- [ ] **Step 4: Tests ausführen**

Run: `python3 -m pytest gridlens/tests/test_pf_entry.py -q`
Expected: `4 passed`

- [ ] **Step 5: Gesamtsuite und Commit**

```bash
python3 -m pytest -q
git add powerfactory/gridlens_pf gridlens/tests/test_pf_entry.py
git commit -m "Select runner or report mode from the parent object"
```

---

### Task 11: Modul-Purge und einmalige Publikation

Beides steht in der Testliste der Spezifikation (Abschnitt 12) und hat noch keine Aufgabe.

**Files:**
- Test: `gridlens/tests/test_pf_entry.py` (ergänzen)

- [ ] **Step 1: Die fehlschlagenden Tests schreiben**

```python
def test_entry_file_purges_stale_submodules():
    """PowerFactory keeps sys.modules across runs. Without the purge an edited
    submodule would keep running its old version while the entry file already
    reports the new publisher number."""
    source = (DEPLOYMENT / "gridlens_report.py").read_text(encoding="utf-8")
    assert "del sys.modules[_name]" in source
    assert 'n.startswith("gridlens_pf.")' in source

    sentinel = object()
    sys.modules["gridlens_pf.__probe__"] = sentinel
    namespace = {"__file__": str(DEPLOYMENT / "gridlens_report.py"),
                 "__name__": "not_main"}
    exec(compile(source, "gridlens_report.py", "exec"), namespace)
    assert "gridlens_pf.__probe__" not in sys.modules


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

    def case(case_id, values):
        points = [("00:00", 0.0, v) for v in values]
        item = {"category": "line", "object": None, "key": "L1",
                "element_id": "L1", "element_name": "L1",
                "voltage_level": "110 kV", "variable_id": "c:loading",
                "variable": "Auslastung", "unit": "%", "points": points}
        record = {"id": case_id, "name": case_id, "kind": "scenario",
                  "description": "", "status": "konvergiert", "error_code": 0,
                  "message": "", "outages": []}
        return payload.scenario_result(record, [item], ["00:00"], [0.0], "h")

    results = [case("REF", [118.0]), case("S01", [130.0])]
    payload.apply_reference(results)
    data = payload.build_cases_payload(None, results, "Projekt", "GridLens_REF")

    report = CountingReport()
    publish.publish_report(report, data)
    assert report.resets == 1
    assert report.rows["LineStatistics"] == 2
```

- [ ] **Step 2: Tests ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_pf_entry.py -q -k "purges or exactly_once"`
Expected: FAIL, solange Task 3 die Purge-Zeilen noch nicht enthält beziehungsweise `build_cases_payload` fehlt

- [ ] **Step 3: Tests grün bekommen**

Beide Tests prüfen bereits implementiertes Verhalten aus Task 3 und Task 7. Schlägt einer fehl, liegt der Fehler dort — nicht im Test. Purge-Block in `gridlens_report.py` beziehungsweise die Schleifenführung in `build_cases_payload` korrigieren, bis beide bestehen.

- [ ] **Step 4: Gesamtsuite und Commit**

```bash
python3 -m pytest -q
git add gridlens/tests/test_pf_entry.py
git commit -m "Cover the module purge and the single-reset publication"
```

---

### Task 12: Versionen, Dokumentation, Abschluss

**Files:**
- Modify: `powerfactory/gridlens_pf/config.py`
- Modify: `powerfactory/README.md`
- Modify: `gridlens/tests/test_native_reporting.py`

- [ ] **Step 1: Versionstest anpassen**

Ändere in `gridlens/tests/test_native_reporting.py` in `test_runtime_package_is_self_contained_and_has_no_mock_input` die letzte Zeile zu:

```python
    assert native.PUBLISHER_VERSION == "4.0.0"
    assert native.TEMPLATE_VERSION == "2.1.0"
    assert native.DATA_CONTRACT_VERSION == "2.1"
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `python3 -m pytest gridlens/tests/test_native_reporting.py -q -k self_contained`
Expected: FAIL — `assert '3.0.1' == '4.0.0'`

- [ ] **Step 3: Versionen anheben**

In `powerfactory/gridlens_pf/config.py`:

```python
PUBLISHER_VERSION = "4.0.0"
TEMPLATE_VERSION = "2.1.0"
DATA_CONTRACT_VERSION = "2.1"
```

- [ ] **Step 4: README aktualisieren**

In `powerfactory/README.md`:

- Dateitabelle um `gridlens_pf/` ergänzen; Einleitung von „die zwei Dateien" auf „die Einstiegsdatei, das Paket `gridlens_pf/` und die Vorlage" ändern.
- Neuen Abschnitt „Szenarienvergleich" einfügen: Runner als `ComPython` **im Study Case** anlegen, Report-Erweiterung wie bisher unter dem `IntReport`; dieselbe Datei für beide. Ablauf: erst Runner ausführen, dann Bericht erzeugen.
- Die Konsolenmeldungen aktualisieren auf `GridLens publisher: 4.0.0`, `GridLens mode: runner` beziehungsweise `GridLens mode: report`.
- Den Absatz „Da nur ein aktiver Ergebniszustand ausgewertet wird, erzeugt das Skript keinen künstlichen Referenzvergleich" durch die Beschreibung des Referenzfalls REF ersetzen; N-1, Versorgungssicherheit und sichere Trennung bleiben als nicht bewertet benannt.
- Flags `SCAN_SCENARIOS`, `SCAN_VARIATIONS`, `MAX_CASES` im Abschnitt „Anpassungen" dokumentieren, samt Begründung aus Spezifikation 11.1, warum `SCAN_VARIATIONS` standardmässig aus ist.

- [ ] **Step 5: Gesamtsuite ausführen**

Run: `python3 -m pytest -q`
Expected: alle Tests grün

- [ ] **Step 6: Commit und Push**

```bash
git add powerfactory gridlens/tests
git commit -m "Raise publisher to 4.0.0 and document the scenario comparison"
git push origin main
```

---

## Abnahme in PowerFactory

Nach Task 12 auf dem PowerFactory-Rechner:

1. `gridlens_report.py`, den Ordner `gridlens_pf/` und `MASTER_GRIDLENS.mrt` kopieren.
2. Ein `ComPython` **im Study Case** anlegen, `gridlens_report.py` zuweisen, ausführen. Erwartet: `GridLens publisher: 4.0.0`, `GridLens mode: runner`, je Fall eine Statuszeile.
3. Im Data Manager prüfen: je konvergiertem Fall ein `GridLens_<ID>.ElmRes`, und `Quasi-Dynamic Simulation.ComStatsim` zeigt wieder auf sein ursprüngliches Ergebnisobjekt.
4. Den `IntReport` ausführen. Erwartet: `GridLens mode: report`, `GridLens: 18 active-model tables published.`
5. PDF prüfen: Zeitreihen mit einer Kurve je Fall in unterschiedlichen Farben, Balken mit `S01 · <Name>`, gefüllte Referenz- und Deltaspalten.

**Voraussetzung für einen aussagekräftigen Bericht** (Spezifikation 11.1): Das Projekt braucht echte Freischaltungsszenarien mit `outserv=1`. Ohne sie läuft der Runner durch und erzeugt REF plus die vorhandenen Modellierungsszenarien — technisch korrekt, fachlich ohne Aussage.
