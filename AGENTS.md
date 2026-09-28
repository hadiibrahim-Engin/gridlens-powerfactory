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

Publisher-Version: `5.3.0`; MRT: `3.3.0`; Datenvertrag: `3.3`.

Das einzelne ComPython liegt direkt unter dem `IntReport`. Es verwendet das
aktive `ComStatsim` einschließlich Zeitraum, Zeitschritt, Profilen und
Calculation Options. **Genau eine Einstellung wird verändert:** die Option
`iopt_maint`, die PowerFactory selbst mit „Planned Outages“ beschriftet.
Berechnet wird:

1. `REF` mit `iopt_maint=0`, also ohne geplante Außerbetriebnahmen,
2. `OUTAGE` mit `iopt_maint=1`, sofern mindestens eine Außerbetriebnahme in
   den simulierten Zeitraum fällt.

Anschließend wird der ursprüngliche Wert wiederhergestellt und verifiziert.
Es werden keine Operation Scenarios, Network Variations oder zusätzlichen
Study Cases erzeugt. `RUN_REFERENCE_CASE=False` überspringt `REF`.

## Wie Außerbetriebnahmen angewendet werden

GridLens wendet **keine** Außerbetriebnahme selbst an. In PowerFactory 2026 ist
`IntPlannedout` ein reines Datenobjekt und besitzt weder `Apply` noch `Reset`
noch `Check`. Maßgeblich sind seine Attribute:

- `starttime` und `endtime` als Epoch-Sekunden,
- `components` mit den geschalteten Betriebsmitteln,
- `outserv` (von PowerFactory als „Ignored“ beschriftet),
- `priority`.

PowerFactory wendet eine Außerbetriebnahme während der Rechnung an, sobald
`iopt_maint` gesetzt ist und die Rechenzeit in ihr Zeitfenster fällt. Der
simulierte Zeitraum steht am `ComStatsim` in `startTime` und `endTime`.

GridLens vergleicht beide Fenster und meldet je Außerbetriebnahme `CONSIDERED`
oder `SKIPPED` mit Grund. Ist die Frage nicht entscheidbar, gilt `CONSIDERED`
und die Objektoberfläche wird als `DIAGNOSTIC` protokolliert. Fällt keine
Außerbetriebnahme in den Zeitraum, wird kein zweiter Lauf gestartet.

## Bewertung je Zeitfenster

`ScriptedPlannedOutages` ist die Bewertungsgrundlage und wird **pro Zeitfenster**
gefüllt, nicht über den gesamten Zeitraum. Das trennt Freischaltungen, die an
verschiedenen Tagen liegen; eine Gesamtstatistik würde für alle dasselbe zeigen.

`collect_series` berechnet die Fensterstatistik, solange die Reihe noch
vollständig ist, also vor dem Downsampling für `ScriptedPlotData`. Die Fenster
kommen aus der Klassifizierung, die vor dem ersten Rechenlauf steht.

`assessment` ist genau einer von: `NO LIMIT EXCEEDED`, `OVERLOAD`,
`VOLTAGE BAND`, `OVERLOAD + VOLTAGE BAND`, `NOT SIMULATED`,
`NO RESULT DATA IN WINDOW`. `violation` ist 1, sobald ein Grenzwert im Fenster
überschritten wird, und steuert die farbliche Hervorhebung in der MRT.
`assessment_detail` nennt die Zahlen dahinter, bei übersprungenen Einträgen den
Grund.

## Übersichtsseite und Elementumfang

Vor Kapitel 1 steht die Seite „Assessment Overview“: vier Kennzahlen, zwei
Kreisdiagramme (Auslastungsklassen bis 80 %, 80–100 %, über 100 % für
Leitungen und Transformatoren; Spannungsstatus der Knoten) und zwei
Balkendiagramme (Verletzungen REF gegen OUTAGE; Verletzungen je
Freischaltungsfenster). Alle Zahlen berechnet `_overview` in Python; die MRT
zeigt nur an. Jedes Diagramm liest eine eigene `ScriptedOverview*`-Tabelle.

`ELEMENT_NAME_FILTER` (Standard `'D7'`) begrenzt die Bewertung auf Elemente,
deren Kurzname den Text enthält; der übrige Modellteil ist Auslandsnetz. Der
Filter greift in `collect_series` vor dem Lesen der Werte.

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

PowerFactory ergänzt `Scripted` genau einmal. Python publiziert 24 Tabellen;
MRT und `TABLES` in `gridlens_report.py` müssen exakt übereinstimmen.
Vertragsänderungen erfordern synchrone Anpassungen von Code, MRT, Versionen und
Tests. `report.Reset()` läuft im erfolgreichen Publikationspfad genau einmal.

Kein Diagramm darf über eine Data Relation gefiltert werden: Die
PowerFactory-Berichtsengine wendet Relationen auf Diagramme nicht an und
zeichnet sonst die Daten aller Master-Zeilen in ein Diagramm. Jedes Diagramm
liest eine eigene Tabelle, die nur seine Reihen enthält (`ScriptedTrend*`).

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
   wieder einführen. Ebenso wenig `Apply`, `Reset` oder `Check` auf
   `IntPlannedout`: diese Methoden existieren in PowerFactory 2026 nicht.
   Außer `iopt_maint` darf keine ComStatsim-Einstellung verändert werden.
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

Offen bleibt der Nachweis, dass `iopt_maint=1` die Ergebnisse tatsächlich
verändert: dass also die Betriebsmittel aus `components` im Zeitfenster der
Außerbetriebnahme abweichende Werte liefern. Der REF/OUTAGE-Vergleich selbst
ist dieser Nachweis. Ebenso zu verifizieren sind `AddCopy`/`CopyObject`,
`ComStatsim.Execute`, `ElmRes` und `IntReport`. Die vollständige Abnahmematrix
steht in `powerfactory/README.md`.
