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

Publisher-Version: `7.0.0`; MRT: `5.0.0`; Datenvertrag: `5.0`.

Die MRT wird von `tools/build_mrt.py` aus `gridlens_report.TABLES` und den
Seitenbausteinen erzeugt (Entwicklungswerkzeug, nicht Teil der Auslieferung).
Wer die MRT ändert, ändert den Generator und führt ihn aus; ein Test prüft
Datenquellen, Ausdrücke und SQL gegen den Datenvertrag.

Das einzelne ComPython liegt direkt unter dem `IntReport`. Es verwendet das
aktive `ComStatsim` einschließlich Zeitraum, Zeitschritt, Profilen und
Calculation Options. Berechnet wird:

1. `REF` mit `iopt_maint=0`, also ohne geplante Außerbetriebnahmen,
2. je Außerbetriebnahme im Zeitraum **ein eigener Case** `OUT01 …` mit
   `iopt_maint=1`, in dem nur diese eine Außerbetriebnahme aktiv ist.

Jeder Case wird gegen `REF` verglichen. Verändert werden zeitweise genau
zwei Dinge, beide danach vollständig und verifiziert zurückgesetzt
(`StateGuard`): die `ComStatsim`-Option `iopt_maint`, die PowerFactory selbst
mit „Planned Outages“ beschriftet, und das Attribut `outserv` („Ignored“) der
übrigen `IntPlannedout`. Es werden keine Operation Scenarios, Network Variations
oder zusätzlichen Study Cases erzeugt. `RUN_REFERENCE_CASE=False` überspringt
`REF`. Schlägt ein Outage-Case fehl, steht er als `NOT EVALUATED` mit Grund im
Bericht und die übrigen laufen weiter; ein nicht rücksetzbarer Zustand
(`StateRestoreError`) stoppt den Lauf.

## Wie Außerbetriebnahmen angewendet werden

GridLens wendet **keine** Außerbetriebnahme selbst an. In PowerFactory 2026 ist
`IntPlannedout` ein reines Datenobjekt und besitzt weder `Apply` noch `Reset`
noch `Check`. Maßgeblich sind seine Attribute:

- `starttime` und `endtime` als Epoch-Sekunden,
- `components` mit den geschalteten Betriebsmitteln,
- `outserv` (von PowerFactory als „Ignored“ beschriftet),
- `priority`.

PowerFactory wendet eine Außerbetriebnahme während der Rechnung an, sobald
`iopt_maint` gesetzt ist, ihr `outserv` 0 ist und die Rechenzeit in ihr
Zeitfenster fällt. GridLens wählt über `outserv` nur aus, **welche** gilt.
Der simulierte Zeitraum steht am `ComStatsim` in `startTime` und `endTime`.

GridLens vergleicht beide Fenster und meldet je Außerbetriebnahme `CONSIDERED`
oder `SKIPPED` mit Grund. Ist die Frage nicht entscheidbar, gilt `CONSIDERED`,
das Fenster wird über die ganze Zeitachse bewertet und die Objektoberfläche als
`DIAGNOSTIC` protokolliert. Fällt keine Außerbetriebnahme in den Zeitraum,
läuft kein Outage-Case.

## LODF

`calculate_lodf` führt einmal vor dem ersten Rechenlauf PowerFactorys
*Sensitivities / Distribution Factors* (`ComVstab`) aus. Vorbild ist
`nahriva-grid-analysis` (`powerfactory/lodf.py`, `docs/LODF.md`). GridLens legt
eine eigene Contingency Analysis (`GridLens LODF`) mit einer `ComOutage` je
Außerbetriebnahme an, verweist `ComVstab.pComSimoutage` darauf, setzt
`isContSens=1`, `calcLodf=1`, `lodflim=0`, liest das `…_LODF`-`ElmRes`
(`b:outid`, `m:LODF:bus1`, Prozent → Bruchteil) und setzt alles zurück; die
angelegten Objekte werden gelöscht (`LODF_CLEAN_UP`). Überwacht werden nur
Leitungen; ein Contingency ohne Lösung (z. B. Generator abgeschnitten) hat
keine LODF. Fehler sind Warnungen: der Grund steht im Bericht und das Ranking
fällt sichtbar beschriftet auf die gemessene Laständerung zurück. Nur ein nicht
rücksetzbarer Zustand stoppt den Lauf. Ende-zu-Ende in PowerFactory ist das
noch nicht geprüft.

## Bewertung

Die Bewertung einer Außerbetriebnahme (`assess_case`) vergleicht ihren Case mit
`REF` **im eigenen Zeitfenster**. Das gilt für die Tabelle „Calculated Cases“,
die Metric View, die Kennzahlenkarten und das LODF-Ranking. Die Tabellen
mit einer gemeinsamen `REF`-Spalte (Case-Zählungen, Radar, Top-10 je Case,
Anhänge, Balkendiagramm) zeigen dagegen die Maxima des **ganzen** simulierten
Zeitraums, so wie das Template es beschreibt.

Jedes Element wird mit sich selbst in `REF` verglichen (`limit_status`):
`NEW` (nur im Case verletzt), `WORSENED` (in beiden verletzt, im Case
schlimmer als die Toleranz), `PRE-EXISTING` (in beiden verletzt, nicht
schlimmer), `RESOLVED` (nur in REF verletzt), `EXCEEDED` (verletzt, aber kein
Vergleichsfall vorhanden), `OK`. Einer Außerbetriebnahme wird nur zugerechnet,
was sie verursacht oder verschärft.

`assessment` je Case ist genau einer von: `BASELINE` (nur REF),
`NO LIMIT EXCEEDED`, `NO ADDITIONAL VIOLATION`, `OVERLOAD`, `VOLTAGE BAND`,
`OVERLOAD + VOLTAGE BAND` (jeweils neu oder verschärft), `NOT SIMULATED`,
`NOT EVALUATED`, `NO RESULT DATA IN WINDOW`. `violation` ist 1 nur für die drei
verursachten Fälle und färbt die Zeile rot; `NO ADDITIONAL VIOLATION` färbt die
Zeile gelb. `assessment_detail` nennt zuerst die Auslastung (das Element, das die
Außerbetriebnahme über die Grenze bringt, mit seinem REF-Wert, dazu den größten
Anstieg), dann die Spannung, bei übersprungenen Einträgen den Grund.

## Aufbau des Berichts

Eine **Querformat**-Seite (A4) mit den Kapiteln des Templates
`GridLens_Template_Optimiert_v2.pdf`, jedes auf eigener Seite (`DataBand` über
`ScriptedReportMeta` mit `NewPageBefore`, damit es auch ohne Datenzeilen
erscheint): Titelseite, Inhaltsverzeichnis (klickbar), Model Quality Assurance,
Calculated Cases and Planned Outages, Reference Case (Kreise, Elemente über
100 %), Metric View (Tabelle, zwei Karten), Case Comparison (drei
Linienplots), Radar Comparison, Top 10 Maximum Loaded Lines, Most Loaded Line
und Largest Delta (Zeitplots mit REF und allen Cases), Line Impact Ranking
(LODF), Top 10 Strongly Loaded Lines by Case, Anhang A Leitungen, B
Transformatoren, C Knotenspannungen. Anhang „Generatoren“ des Templates gibt es
nicht (keine Daten, Scope offen).

Tabellen mit Case-Spalten zeigen `REF` und bis zu `CASE_SLOTS = 6` Cases; weitere
Cases folgen als neuer Block (`block`, `col_count`). Die MRT enthält je Spaltenzahl
(0…6) ein Band-Paar, das auf `col_count` filtert; absteigend angeordnet. Diagramme
mit einer Serie je Case (Radar, Zeitplots) gibt es ebenso je Anzahl gezeichneter
Cases (1…7, Filter `ScriptedReportMeta.chart_cases`), damit die Legende nur
vorhandene Cases nennt. Gezeichnet werden REF und die ersten sechs Cases; ein Hinweis
nennt das. Farbe ist nur Identität: REF grau, danach feste Palette.

Der Report zeigt für jedes Betriebsmittel nur seinen Namen (`loc_name`), ohne
Fallpräfix, Pfad, Hash oder Kürzel. Zu lange Texte enden mit „…“. Der Bericht
trägt keinen Hinweis auf „synthetische Daten“; Fußzeile und Banner lauten
`PRE-ASSESSMENT | NOT FOR OPERATIONAL USE`.

`GRID_NAME_FILTER` ist **optional** (Standard `''`: alle Elemente werden bewertet). Mit einem Text, z. B. `'D7'` für das Europa-Modell, begrenzt er die Bewertung auf Elemente,
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
  Messwerte akzeptiert. Eine Knotenspannung, die PowerFactory als NaN schreibt
  (ein Knoten, den die Außerbetriebnahme abtrennt), gilt wie 0 als spannungslos
  und ist kein Wert; eine Auslastung als NaN stoppt den Case weiterhin.
- Vollständige PowerFactory-Pfade dienen nur als interne Identität; der Report
  zeigt kurze Namen.
- Deltas entstehen nur für dasselbe Objekt in `REF` und `OUTAGE`.
- Ausgeschaltete oder fehlende Reihen erhalten keine künstlichen Nullwerte.

## Datenvertrag und MRT

PowerFactory ergänzt `Scripted` genau einmal. Python publiziert 18 Tabellen;
MRT und `TABLES` in `gridlens_report.py` müssen exakt übereinstimmen.
Vertragsänderungen erfordern synchrone Anpassungen von Code, MRT-Generator, Versionen
und Tests. `report.Reset()` läuft im erfolgreichen Publikationspfad genau einmal.

Kein Diagramm darf über eine Data Relation gefiltert werden: Die
PowerFactory-Berichtsengine wendet Relationen auf Diagramme nicht an und
zeichnet sonst die Daten aller Master-Zeilen in ein Diagramm. Jedes Diagramm
liest eine eigene Tabelle, die nur seine Reihen enthält (`ScriptedTrend*`,
`ScriptedRadar`, `ScriptedCaseCounts`, `ScriptedPie*`).

Diagramme mit REF und mehreren Cases lesen Tabellen im Breitformat
(`s0_name…s6_name` und `v0…v6`): Slot 0 ist REF grau `[140:150:160]`, Slot 1 bis 6
haben feste Farben. Kreise färben ihre Klassen über `Conditions` auf dem
Argument; die Legende zeigt über `LegendValueType=Argument` die Klassennamen.
Die Palette des Diagrammstils darf keine Bedeutung tragen. Kategorien bleiben in
Datenreihenfolge (`SortBy=None`, `ORDER BY` in der Datenquelle).

Die MRT setzt `Culture=en-US`; Zahlenformate verwenden
`UseLocalSetting=False`. Diagramme zeichnet die Engine erst beim Export mit der
Windows-Kultur, die `Culture` nicht erreicht. Keine Achse darf deshalb ein
kulturabhängiges Dezimalzeichen drucken: Auslastungsachsen ganzzahlig
(`0;-0;0`), Zählachsen ohne Beschriftung (die Werte stehen an den Punkten).

Datenzellen einer Tabellenzeile tragen `GrowToHeight=True`, damit ein
umbrechender Name das Zeilenraster nicht zerreißt.

Leere Listen werden selbstschließend geschrieben
(`<Components isList="true" count="0" />`): Stimulsoft 2025.3 liest den
Leerraum zwischen Öffnungs- und Schluss-Tag als String-Eintrag, und der
Designer bricht mit `InvalidCastException` ab.

Zeitreihen werden bis `MAX_PLOT_POINTS = 200` ungekürzt geplottet, darüber auf
einem Raster, das nur von der Punktzahl abhängt. REF und alle Cases haben so
immer dieselben Zeitpunkte; eigene Extremwerte pro Reihe werden nicht ergänzt.

`<ReportFile />` bleibt leer. Keine lokalen Pfade, Mock-Daten oder externen
Payload-/Schema-Abhängigkeiten dürfen in die Auslieferung gelangen. Eingebettete
Logos, Bookmarks, klickbares Inhaltsverzeichnis, Seitenumbrüche und genau ein
`Style` je Diagramm bleiben erhalten.

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
   An `ComStatsim` darf nur `iopt_maint` verändert werden, an
   `IntPlannedout` zeitweise nur `outserv`; beides wird verifiziert
   zurückgesetzt.
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

Neu offen seit Version 7.0.0, noch nie in PowerFactory gelaufen:

- Ob `outserv=1` an einer `IntPlannedout` sie bei gesetztem `iopt_maint` wirklich
  ausschließt, sodass je Case nur die eine Außerbetriebnahme wirkt.
- Der LODF-Ablauf im Bericht (Contingency Analysis anlegen, `ComVstab` ausführen,
  `…_LODF` lesen, Zustand und Hilfsobjekte zurücksetzen). In nahriva-grid-analysis
  ist nur die Probe `lodf_probe.py` in PowerFactory gelaufen.
- Die Laufzeit mit 1+N Rechenläufen und ihr Speicherbedarf.
- Das Rendern der neuen MRT in PowerFactory (Variantenbänder, Gruppenköpfe,
  Querformat); lokal ist sie nur mit Stimulsoft 2025.3.5 geprüft, dessen Testversion
  nur die erste Seite voll rendert.
