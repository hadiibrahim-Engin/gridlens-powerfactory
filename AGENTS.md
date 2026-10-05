# Agent Context: GridLens

Diese Datei gilt für das gesamte Repository. Stand: **29. September 2026**.

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

Publisher-Version: `6.0.0`; MRT: `4.0.0`; Datenvertrag: `4.0`.

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
vollständig ist, also vor dem Downsampling für die Zeitreihen. Die Fenster
kommen aus der Klassifizierung, die vor dem ersten Rechenlauf steht.

Jedes Element wird mit sich selbst in `REF` verglichen (`limit_status`):
`NEW` (nur in OUTAGE verletzt), `WORSENED` (in beiden verletzt, in OUTAGE
schlimmer als die Toleranz), `PRE-EXISTING` (in beiden verletzt, nicht
schlimmer), `RESOLVED` (nur in REF verletzt), `EXCEEDED` (verletzt, aber kein
Vergleichsfall vorhanden), `OK`. Einer Außerbetriebnahme wird nur zugerechnet,
was sie verursacht oder verschärft.

`assessment` ist genau einer von: `NO LIMIT EXCEEDED`,
`NO ADDITIONAL VIOLATION` (nur Verletzungen, die schon in REF bestehen),
`OVERLOAD`, `VOLTAGE BAND`, `OVERLOAD + VOLTAGE BAND` (jeweils neu oder
verschärft), `NOT SIMULATED`, `NO RESULT DATA IN WINDOW`. `violation` ist 1
nur für die drei verursachten Fälle und färbt die Zeile rot;
`NO ADDITIONAL VIOLATION` färbt die MRT gelb. `assessment_detail` nennt zuerst
die Auslastung (das Element, das die Außerbetriebnahme über die Grenze bringt,
mit seinem REF-Wert), dann die Spannung, bei übersprungenen Einträgen den
Grund.

## Übersichtsseite und Elementumfang

## Aufbau des Berichts

Eine Hochformatseite mit festen Kapiteln, Auslastung vor Spannung:
1 Assessment Overview, 2 Planned Outages, 3 Line Loading, 4 Transformer
Loading, 5 Voltage, 6 Time Series, 7 Model Quality Assurance, 8 Study
Definition and Calculated Cases, 9 Appendix. Jede Kapitelüberschrift ist ein
`HeaderBand`, dem ein Band auf `ScriptedReportMeta` mit einem Satz folgt
(`line_summary`, `transformer_summary`, `voltage_summary`). So erscheint jedes
Kapitel auch ohne Datenzeilen, statt eine leere Seite zu hinterlassen.

Die Auslastungskapitel zeigen immer die zehn höchsten Werte (auch ohne
Verletzung) und die zehn größten Anstiege, jeweils REF und OUTAGE
nebeneinander mit Delta und Status (`ScriptedLoadingRanking`), dazu ein
Balkendiagramm mit 100-%-Linie. Die Zeitreihe zeigt das Element mit dem
größten Anstieg, sonst das höchstbelastete. Der Anhang enthält Elemente ab
`LOADING_WARNING` oder mit einer Änderung ab `LOADING_APPENDIX_DELTA`
bzw. `VOLTAGE_APPENDIX_DELTA`.

Der Report zeigt für jedes Betriebsmittel nur seinen Namen (`loc_name`), ohne
Fallpräfix, Pfad, Hash oder Kürzel. Zu lange Texte enden mit „…“.

Kapitel 1 „Assessment Overview“ zeigt vier Kennzahlen (Überlastungen mit
Anzahl neuer, höchste Auslastung, Spannungsverletzungen mit Anzahl neuer,
Außerbetriebnahmen im Zeitraum), zwei
Kreisdiagramme (Auslastungsklassen bis 80 %, 80–100 %, über 100 % für
Leitungen und Transformatoren; Knoten unter, im und über ihrem Band) und zwei
Balkendiagramme (Verletzungen REF gegen OUTAGE; Verletzungen je
Freischaltungsfenster). Alle Zahlen berechnet `_overview` in Python; die MRT
zeigt nur an. Jedes Diagramm liest eine eigene `ScriptedOverview*`-Tabelle.

`GRID_NAME_FILTER` (Standard `'D7'`) begrenzt die Bewertung auf Elemente,
deren Grid den Text im Namen trägt; der übrige Modellteil ist Auslandsnetz.
Das Grid kommt aus dem Attribut `cpGrid` („Grid“), ersatzweise aus dem
`ElmNet` im Ablagepfad des Elements. `cpGrid` hat Vorrang, weil Elemente aus
Varianten in einer Ausbaustufe liegen und ihr Pfad kein Grid enthält. Der
Filter greift in `collect_series` vor dem Lesen der Werte.
`tools/probe_grid_filter.py` zeigt im Zielprojekt, was der Filter auswählt.
Es ist eigenständig und enthält eine Kopie des Filters; wer den Filter in
`gridlens_report.py` ändert, muss die Kopie mitziehen, sonst schlägt
`tests/test_probe_grid_filter.py` fehl.

## Fachliche Regeln

- Priorisierte Variablen: `c:loading`/`m:loading`, `m:u`/`m:u1`. Winkel
  werden nicht gelesen.
- Auslastungsverletzung strikt `> 100 %`.
- Spannungsverletzung strikt unter bzw. über dem Band der Nennspannung
  (`VOLTAGE_LIMITS_KV`): 360–420 kV für Nennspannungen von 300 bis unter
  450 kV, 198–245 kV von 200 bis unter 300 kV, 99–123 kV von 100 bis unter
  150 kV; jede andere Nennspannung `0.95`–`1.05 p.u.`. Diese Werte sind ein
  Vorschlag und fachlich zu bestätigen.
- Werte genau auf dem Grenzwert sind keine Verletzung.
- Spannungen unter `ENERGIZED_MIN_PU` (0,1 p.u.) gelten als spannungslos und
  sind kein Messwert; Knoten ohne einen einzigen Wert und DC-Knoten
  (`ElmTerm.systype == 1`) werden nicht bewertet und in der QA gezählt.
- NaN, Infinity, `None`, Booleans und unlesbare API-Rückgaben werden nicht als
  Messwerte akzeptiert.
- Vollständige PowerFactory-Pfade dienen nur als interne Identität; der Report
  zeigt kurze Namen.
- Deltas entstehen nur für dasselbe Objekt in `REF` und `OUTAGE`.
- Ausgeschaltete oder fehlende Reihen erhalten keine künstlichen Nullwerte.

## Datenvertrag und MRT

PowerFactory ergänzt `Scripted` genau einmal. Python publiziert 20 Tabellen;
MRT und `TABLES` in `gridlens_report.py` müssen exakt übereinstimmen.
Vertragsänderungen erfordern synchrone Anpassungen von Code, MRT, Versionen und
Tests. `report.Reset()` läuft im erfolgreichen Publikationspfad genau einmal.

Kein Diagramm darf über eine Data Relation gefiltert werden: Die
PowerFactory-Berichtsengine wendet Relationen auf Diagramme nicht an und
zeichnet sonst die Daten aller Master-Zeilen in ein Diagramm. Jedes Diagramm
liest eine eigene Tabelle, die nur seine Reihen enthält (`ScriptedTrend*`).

Diagramme, die REF und OUTAGE vergleichen, lesen Tabellen im Breitformat
(`ref_value`/`outage_value` bzw. `ref_count`/`outage_count`) und haben zwei
feste Serien: REF grau `[140:150:160]`, OUTAGE rot `[181:18:62]`. Kreise färben
ihre Klassen über `Conditions` auf dem Argument; die Legende zeigt über
`LegendValueType=Argument` die Klassennamen. Die Palette des Diagrammstils
darf keine Bedeutung tragen.

Die MRT setzt `Culture=en-US`; Zahlenformate verwenden
`UseLocalSetting=False`. Diagramme zeichnet die Engine erst beim Export mit der
Windows-Kultur, die `Culture` nicht erreicht. Keine Achse darf deshalb ein
kulturabhängiges Dezimalzeichen drucken: Auslastungsachsen ganzzahlig
(`0;-0;0`), Zählachsen ohne Beschriftung, Spannungsachsen über die Spalten
`ref_mpu`/`outage_mpu` (tausendstel p.u.) mit dem Format `0'.'000`.

Datenzellen einer Tabellenzeile tragen `GrowToHeight=True`, damit ein
umbrechender Name das Zeilenraster nicht zerreißt.

Leere Listen werden selbstschließend geschrieben
(`<Components isList="true" count="0" />`): Stimulsoft 2025.3 liest den
Leerraum zwischen Öffnungs- und Schluss-Tag als String-Eintrag, und der
Designer bricht mit `InvalidCastException` ab.

Zeitreihen werden bis `MAX_PLOT_POINTS = 200` ungekürzt geplottet, darüber auf
einem Raster, das nur von der Punktzahl abhängt. REF und OUTAGE haben so immer
dieselben Zeitpunkte; eigene Extremwerte pro Reihe werden nicht ergänzt.

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
ist dieser Nachweis. Im Testbericht vom 29. September 2026 unterschieden sich
REF und OUTAGE nur im Zeitschritt direkt nach dem Fensterende (02:00 bei einem
Fenster 00:00–01:59). Ob PowerFactory das Fenster versetzt anwendet oder ein
`ElmRes`-Zeitstempel das Intervallende markiert, ist offen; bis dahin kann die
Fensterbewertung die falschen Zeilen treffen. Ebenso zu verifizieren sind `AddCopy`/`CopyObject`,
`ComStatsim.Execute`, `ElmRes` und `IntReport`. Die vollständige Abnahmematrix
steht in `powerfactory/README.md`.
