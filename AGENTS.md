# Agent Context: GridLens

Diese Datei gilt für das gesamte Repository. Stand: **11. September 2026**.

## Produktziel

GridLens erzeugt in **DIgSILENT PowerFactory 2026** einen wiederholbaren Bericht
zur technischen Vorprüfung von Planned Outages. PowerFactory bleibt Quelle für
Netzmodell, Operational Library, QDS-Konfiguration, `ElmRes`, interne
Reporting-Datenbank und PDF-Ausgabe.

Der Bericht ist keine abschließende Freigabe und kein Nachweis für
N-1-Sicherheit, Versorgungssicherheit, Schutzkoordination oder sichere
elektrische Trennung.

## Aktueller Produktionspfad

Die gemeinsam auszuliefernde Laufzeit besteht ausschließlich aus:

- `powerfactory/gridlens_report.py`
- `powerfactory/MASTER_GRIDLENS.mrt`

Publisher-Version: `5.0.2`; MRT: `3.0.0`; Datenvertrag: `3.0`.

Das einzelne ComPython liegt direkt unter dem `IntReport`. Es verwendet das
aktive `ComStatsim` unverändert, kopiert dessen gebundenes Ergebnisobjekt und
berechnet standardmäßig:

1. `REF` im unveränderten Zustand beim Skriptstart,
2. `OUTAGE` mit allen gemeinsam sicher anwendbaren Planned Outages.

Es erzeugt oder aktiviert keine Operation Scenarios, Network Variations oder
zusätzlichen Study Cases. `RUN_REFERENCE_CASE=False` überspringt `REF`. Gibt es
keinen anwendbaren Outage, wird kein sinnloser `OUTAGE`-Lauf gestartet.

Planned Outages werden bevorzugt als `IntPlannedout`, zusätzlich als Legacy-
`IntOutage`, gesucht. GridLens verändert nur Objekte, deren Apply-, Reset- und
Check-Pfad verfügbar ist. Bereits aktive, deaktivierte, zeitlich unpassende,
ungültige oder nicht sicher prüfbare Outages werden mit Grund übersprungen.

Vor jeder Mutation werden die ursprüngliche `ComStatsim.results`-Bindung und
die selbst aktivierten Outages verfolgt. Reset erfolgt in umgekehrter
Reihenfolge. Zustand und temporäre Ergebnisse werden vor der Reportpublikation
wiederhergestellt beziehungsweise entfernt. Ein nicht verifizierter Restore ist
ein harter Fehler.

## Fachliche Regeln

- Priorisierte Variablen: `c:loading`/`m:loading`, `m:u`/`m:u1`,
  `m:phiu`/`m:phiu1`.
- Auslastungsverletzung strikt `> 100 %`.
- Spannungsverletzung strikt `< 0.95 p.u.` oder `> 1.05 p.u.`.
- Werte genau auf dem Grenzwert sind keine Verletzung.
- NaN, Infinity, `None`, Booleans und unlesbare API-Rückgaben werden nicht als
  Messwerte akzeptiert.
- Vollständige PowerFactory-Pfade dienen nur als interne Identität; der Report
  zeigt kurze Namen.
- Deltas entstehen nur für dasselbe Objekt in `REF` und `OUTAGE`.
- Ausgeschaltete oder fehlende Reihen erhalten keine künstlichen Nullwerte.
- Winkel sind informativ und besitzen keinen pauschalen Grenzwert.

## Datenvertrag und MRT

PowerFactory ergänzt `Scripted` genau einmal. Python publiziert 17 Tabellen;
MRT und `TABLES` in `gridlens_report.py` müssen exakt übereinstimmen.
Vertragsänderungen erfordern synchrone Anpassungen von Code, MRT, Versionen und
Tests. `report.Reset()` läuft im erfolgreichen Publikationspfad genau einmal.

`<ReportFile />` bleibt leer. Keine lokalen Pfade, Mock-Daten oder externen
Payload-/Schema-Abhängigkeiten dürfen in die Auslieferung gelangen. Eingebettete
Logos, Bookmarks, klickbares Inhaltsverzeichnis, Seitenumbrüche und der einzelne
`PlotsChart`-Style bleiben erhalten.

Code, Kommentare, Variablennamen, Logs, Fehlermeldungen, Tabellenüberschriften
und Report-Inhalte bleiben Englisch. Die deutsche Betriebsdokumentation ist
davon ausgenommen.

## Änderungsregeln

1. Vor Änderungen `git status`, Branch und letzten Commit prüfen.
2. `Report.pdf` und sonstige unversionierte Benutzerdateien niemals verändern
   oder löschen.
3. PowerFactory-Laufzeitcode darf nur Standardbibliothek und `powerfactory`
   benötigen.
4. Keine alten modularen, Scenario-, Variation-, Mock- oder Manifest-Pfade
   wieder einführen.
5. Fehler dürfen weder einen alten Resultstand als aktuell publizieren noch
   einen unbestimmten Outage-Zustand verschweigen.
6. Änderungen auf einem Feature-Branch entwickeln; keine Produktionsfreigabe
   ohne realen PowerFactory-2026-End-to-End-Test behaupten.

## Lokale Verifikation

```bash
.venv/bin/pytest -q
python3 -m py_compile powerfactory/gridlens_report.py
git diff --check
```

Zusätzlich prüfen die Tests XML-Parsing, Referenzen, ReportFile, Pfade,
`PlotsChart`, Datenvertrag, Logos, Bookmarks, englische Reporttexte und das
QA-Layout.

## Offene PowerFactory-Abnahme

Die konkreten Rückgabewerte und die Fehlersemantik von `IntPlannedout.Apply`,
`Reset`, `Check`, `IsInStudyTime`, `AddCopy`/`CopyObject`, `ComStatsim.Execute`,
`ElmRes` und `IntReport` müssen im Ziel-Build verifiziert werden. Die vollständige
Abnahmematrix steht in `powerfactory/README.md`.
