# Einzel-Cases, LODF und Template-Layout – Umsetzungsplan

> **For agentic workers:** Use superpowers:executing-plans. Schritte mit `- [ ]`.

**Goal:** `gridlens_report.py` rechnet REF plus je Außerbetriebnahme einen Case, ergänzt die LODF und publiziert die Tabellen des Datenvertrags 5.0; `MASTER_GRIDLENS.mrt` rendert das Template.

**Architecture:** Ein Skript, eine MRT. Die MRT wird von `tools/build_mrt.py` aus `gridlens_report.TABLES` und Bausteinen erzeugt (Entwicklungswerkzeug, nicht Teil der Auslieferung). Je Case gilt: `result['id']` ist `REF` oder `OUT01…`; ein Outage-Case trägt `result['outage']` (Record) und wird gegen REF gepaart.

**Tech Stack:** Python-Standardbibliothek + `powerfactory`; pytest; Stimulsoft 2025.3.5 (lokal, NuGet) zum Rendern.

## Global Constraints

- Code, Kommentare, Logs, Tabellenüberschriften und Berichtstexte Englisch.
- Runtime nur Standardbibliothek und `powerfactory`; Auslieferung = `powerfactory/gridlens_report.py` + `powerfactory/MASTER_GRIDLENS.mrt`.
- Außer `iopt_maint` (ComStatsim) wird nur `outserv` an `IntPlannedout` zeitweise geschrieben und verifiziert zurückgesetzt; kein `Apply`/`Reset`/`Check` auf `IntPlannedout`.
- Auslastungsverletzung strikt `> 100 %`; Spannungsbänder unverändert; NaN/None/Bool nie als Messwert.
- Keine Data Relation in Diagrammen; jedes Diagramm liest eine eigene Tabelle; feste Farben; keine kulturabhängigen Achsformate.
- Leere Listen in der MRT selbstschließend; `<ReportFile />` leer; keine lokalen Pfade; Logos, Bookmarks, klickbares Inhaltsverzeichnis, ein `PlotsChart` mit einem `Style`.
- `report.Reset()` genau einmal im erfolgreichen Publikationspfad.
- Versionen: Publisher `7.0.0`, MRT `5.0.0`, Datenvertrag `5.0`.
- „SYNTHETIC DUMMY DATA“ darf nirgends stehen.

## Dateien

| Datei | Verantwortung |
|---|---|
| `powerfactory/gridlens_report.py` | Rechnen, Zustand, LODF, Auswertung, Publikation |
| `powerfactory/MASTER_GRIDLENS.mrt` | erzeugt von `tools/build_mrt.py` |
| `tools/build_mrt.py` | MRT-Generator (Bausteine für Text, Tabellen, Diagramme) |
| `tests/test_gridlens_report.py`, `tests/test_mrt.py`, neu `tests/test_cases_lodf.py` | Prüfung |
| `AGENTS.md`, `BIG_PICTURE.md`, `powerfactory/README.md` | Dokumentation |

## Task 1: Zustandswächter und Einzel-Case-Lauf

**Files:** Modify `powerfactory/gridlens_report.py` (`execute_gridlens`, neue `StateGuard`, `run_outage_cases`); Test `tests/test_cases_lodf.py`.

**Interfaces – Produces:**
`class StateGuard` (`set(obj, attr, value, label) -> bool`, `restore() -> list[str]`, Kontextmanager, wirft `GridLensError` bei Rest);
`outage_case_id(index) -> 'OUT01'`; `execute_gridlens` ruft für jede `CONSIDERED`-Außerbetriebnahme `_run_calculation` mit `case_id`, `name=record['name']`, setzt `record['case_id']`, `result['outage'] = record`.

- [ ] Test: Attrappe mit 3 `IntPlannedout` (`outserv` 0/0/1), `ComStatsim` (`iopt_maint`, `Execute`, `results`), zwei laufende Outages; Prüfen, dass während der Läufe nur die jeweilige Outage `outserv=0` hat, `iopt_maint=1`, und dass danach alle Werte wie am Anfang sind – auch wenn Lauf 2 mit Code 1 endet.
- [ ] Test: Fehler beim Zurücksetzen (Attrappe verweigert `outserv`) → `GridLensError` nennt Soll und Ist.
- [ ] Implementieren, `pytest tests/test_cases_lodf.py -q` grün.
- [ ] Commit `feat: calculate every planned outage as its own case`.

## Task 2: LODF aus ComVstab

**Files:** Modify `powerfactory/gridlens_report.py` (Abschnitt `LODF`); Test `tests/test_cases_lodf.py`.

**Interfaces – Produces:**
`calculate_lodf(app, study_case, records, logger) -> dict` mit `{record_id: {'values': {line_key: (name, fraction)}, 'reason': ''}}`; Fehler → für alle Records `reason`, nie eine Exception nach außen außer `StateRestoreError`.

- [ ] Test (Attrappe von `ComVstab`/`ComSimoutage`/`ComOutage`/`ElmRes` mit `b:outid`, `m:LODF:bus1`): zwei Outages, eine ohne Lösung → Reason; Einstellungen `pComSimoutage`, `isContSens`, `calcLodf`, `lodflim` danach zurück; Hilfsobjekte gelöscht.
- [ ] Implementieren nach `nahriva-grid-analysis/powerfactory/lodf.py`, inline.
- [ ] Commit `feat: read line outage distribution factors from PowerFactory`.

## Task 3: Auswertung je Case und neue Tabellen

**Files:** Modify `powerfactory/gridlens_report.py` (`TABLES`, `REQUIRED_FIELDS`, `paired`, `build_cases_payload` und Helfer, Versionen); Test `tests/test_gridlens_report.py`.

**Interfaces – Produces:** `TABLES` laut Spec, Abschnitt 4; `case_columns(results) -> list[list[result]]` (Blöcke zu je 6 Outage-Cases); `MATRIX_FIELDS`; `paired(results, category, case_id=None, window=None)`.

- [ ] Tests: je Tabelle Inhalt für REF + 3 Outage-Cases (Zählungen, `n/a`, Blöcke bei 8 Outages, LODF-Ranking nach |LODF| mit Delta, Fallback-Beschriftung, Top-10 je Case, Anhang-Schwellen).
- [ ] Implementieren, bestehende Tests anpassen.
- [ ] Commit `feat: publish the case-based report tables (data contract 5.0)`.

## Task 4: MRT-Generator und Template

**Files:** Create `tools/build_mrt.py`; regenerate `powerfactory/MASTER_GRIDLENS.mrt`; Modify `tests/test_mrt.py`.

- [ ] Generator erzeugt Querformat A4, Kopf/Fuß, Titelseite, Inhaltsverzeichnis, alle Seiten des Templates; `python3 tools/build_mrt.py` schreibt die MRT.
- [ ] Tests: Datenquellen = `TABLES`; Referenzen, `ReportFile`, Pfade, `PlotsChart`, Logos, Bookmarks, selbstschließende Listen, kein „SYNTHETIC“, englische Texte.
- [ ] Lokal mit Stimulsoft laden und die Abschnitte als PDF rendern, mit dem Template vergleichen.
- [ ] Commit `feat: render the report in the template layout`.

## Task 5: Dokumentation, Gesamtprüfung, Merge

- [ ] `AGENTS.md`, `BIG_PICTURE.md`, `powerfactory/README.md`, `tools/probe_grid_filter.py`-Kopie prüfen; Versionen.
- [ ] `.venv/bin/pytest -q`, `python3 -m py_compile powerfactory/gridlens_report.py`, `git diff --check`.
- [ ] Merge `feat/template-lodf-cases` → `feat/report-loading-first` → `main` lokal (Fast-Forward), kein Push ohne Freigabe.
