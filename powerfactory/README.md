# GridLens in DIgSILENT PowerFactory 2026

## Auslieferung

Kopiere immer diese beiden Dateien aus demselben Release auf den
PowerFactory-Rechner:

| Datei | Aufgabe |
|---|---|
| `gridlens_report.py` | Einzeldatei für Planned-Outage-Discovery, LODF, QDS-Läufe je Außerbetriebnahme, Ergebnisprüfung und `IntReport`-Publikation |
| `MASTER_GRIDLENS.mrt` | Reportlayout (Querformat) und 18 `Scripted*`-Datenquellen; erzeugt von `tools/build_mrt.py` |

Weitere Python-Pakete, JSON-Payloads, Schemas oder Datenbanken werden nicht
benötigt. Die PowerFactory-Laufzeit verwendet nur die Python-Standardbibliothek
und das von PowerFactory bereitgestellte Modul `powerfactory`.

## Voraussetzungen

Vor dem Start müssen im aktiven Study Case vorhanden sein:

- ein vollständig konfiguriertes `ComStatsim`,
- ein in `ComStatsim.results` gebundenes `ElmRes`, dessen Variablenauswahl
  kopiert werden kann,
- die benötigten Ergebnisvariablen:
  - `ElmLne`: `c:loading`, ersatzweise `m:loading`,
  - `ElmTr2`/`ElmTr3`: `c:loading`, ersatzweise `m:loading`,
  - `ElmTerm`: `m:u`, ersatzweise `m:u1` (Winkel werden nicht mehr gelesen),
- die zu prüfenden Planned Outages in der Operational Library,
- ein `IntReport`, das `MASTER_GRIDLENS.mrt` verwendet.

GridLens ändert an `ComStatsim` **genau eine** Option: `iopt_maint`, in PowerFactory
mit „Planned Outages“ beschriftet. Zeitraum, Zeitschritt, Profile und alle
weiteren Einstellungen stammen unverändert aus dem aktiven `ComStatsim`.
Zusätzlich setzt GridLens für jeden Outage-Case zeitweise das Attribut `outserv`
(„Ignored“) der übrigen `IntPlannedout` und bindet `ComStatsim.results` an
temporäre, aus dem konfigurierten `ElmRes` kopierte Ergebnisobjekte um. Die
LODF-Berechnung stellt ihre `ComVstab`-Einstellungen ebenfalls zurück. Alles wird
nach dem Lauf wiederhergestellt und verifiziert.

## Installation und Ausführung

1. Lege genau ein ComPython direkt unter dem Ziel-`IntReport` an.
2. Weise diesem ComPython `gridlens_report.py` als externe Python-Datei zu.
3. Aktiviere Projekt und Study Case und prüfe die `ComStatsim`-Konfiguration.
4. Starte das ComPython einmal. Berechnung, Auswertung, Zustandswiederherstellung
   und Tabellenpublikation erfolgen in diesem Lauf.
5. Erzeuge beziehungsweise exportiere den Bericht erst nach der Meldung
   `Report published successfully`.

Die Standardreihenfolge ist:

1. Discovery aller `IntPlannedout`-Objekte; `IntOutage` wird nur als
   Legacy-Kompatibilität erkannt.
2. Vergleich jedes Outage-Fensters (`starttime`/`endtime`) mit dem simulierten
   Zeitraum (`ComStatsim.startTime`/`endTime`).
3. **LODF:** einmal `Sensitivities / Distribution Factors` (`ComVstab`) für alle
   Außerbetriebnahmen im Zeitraum (siehe unten).
4. `REF`: Lauf mit `iopt_maint=0`, also ohne geplante Außerbetriebnahmen.
5. Je Außerbetriebnahme im Zeitraum **ein eigener Case** `OUT01`, `OUT02` …: `iopt_maint=1`,
   `outserv=1` an allen anderen `IntPlannedout`, ein QDS-Lauf, Ergebnisse lesen,
   `outserv` zurücksetzen. Die Läufe folgen einander; die Laufzeit ist
   ungefähr (1 + Anzahl Außerbetriebnahmen) mal die eines Laufs.
6. Wiederherstellung von `iopt_maint`, `ComStatsim.results` und Studienzeit,
   Löschen der temporären Ergebnisse.
7. Publikation aller 18 Tabellen in das `IntReport`.

Schlägt ein Outage-Case fehl, erscheint er als `NOT EVALUATED` mit der Ursache im Bericht
und in der QA, und die übrigen Cases laufen weiter. Schlägt `REF` fehl, endet der Lauf.

## Warum GridLens die Außerbetriebnahmen nicht selbst anwendet

In PowerFactory 2026 ist `IntPlannedout` ein reines Datenobjekt. Es bietet
weder `Apply` noch `Reset` noch `Check`; abgefragt wurde das im Zielbuild
direkt an den Objekten. Relevant sind stattdessen `starttime`, `endtime`,
`components` (die geschalteten Betriebsmittel), `outserv` und `priority`.

PowerFactory wendet eine Außerbetriebnahme während der Rechnung selbst an,
sobald `iopt_maint` gesetzt ist und ihr `outserv` 0 ist. Das ist genauer als ein
pauschales Schalten: bei einem mehrtägigen QDS-Lauf wirkt jede Außerbetriebnahme exakt
in ihren eigenen Zeitschritten. GridLens wählt über `outserv` nur aus, welche gilt, damit
sich überlappende Zeitfenster nicht gegenseitig beeinflussen.

Deaktivierte (`outserv=1`) und außerhalb des simulierten Zeitraums liegende
Außerbetriebnahmen werden als `SKIPPED` mit Grund ausgewiesen, alle übrigen als
`CONSIDERED`. Gibt es keine im Zeitraum, entfallen die Outage-Läufe.

## LODF (Line Outage Distribution Factors)

Die LODF zeigt, um wie viel sich der Fluss einer Leitung ändert, wenn die
Außerbetriebnahme das Betriebsmittel abschaltet, bezogen auf dessen Fluss davor
(vorzeichenbehaftet, am bus1-Ende). Das Line Impact Ranking sortiert je
Außerbetriebnahme danach und zeigt daneben die gemessene Änderung gegenüber
`REF` (Delta in %-Punkten, im Fenster der Außerbetriebnahme).

GridLens legt dafür die Contingency Analysis `GridLens LODF` mit einer
`ComOutage` je Außerbetriebnahme an, verweist `ComVstab.pComSimoutage` darauf, setzt
`isContSens=1`, `calcLodf=1` und `lodflim=0`, führt `ComVstab` aus, liest das
`ElmRes` mit der Endung `_LODF` und stellt alles wieder her. Die angelegten Objekte werden
gelöscht (`LODF_CLEAN_UP = False` lässt sie zur Ansicht stehen; `CALCULATE_LODF =
False` überspringt den Schritt). Grenzen: nur Leitungen werden überwacht; eine
Außerbetriebnahme ohne Leitung, Transformator oder Kuppler und ein Contingency
ohne Lösung (z. B. Generator abgeschnitten) haben keine LODF. Dann steht der Grund
im Bericht, und das Ranking ist als „nach gemessener Laständerung“ beschriftet.

## Die Tabelle „Calculated Cases and Planned Outages“

Sie ist die Bewertungsgrundlage für die Freischaltung. Je Case eine Zeile mit
sechs Spalten:

| Spalte | Inhalt |
|---|---|
| Case | `Reference` oder der Name der Außerbetriebnahme |
| Period | simulierter Zeitraum bzw. Zeitfenster aus `starttime`/`endtime` |
| Prio | `priority` aus PowerFactory |
| Equipment out of service | die Betriebsmittel aus `components` |
| Assessment | das Urteil für dieses Fenster |
| Worst values inside the window | die Zahlen dahinter |

Entscheidend ist, dass jede Zeile **nur ihr eigenes Zeitfenster** bewertet; ihr
Case enthält dank Einzel-Lauf nur diese eine Außerbetriebnahme. Die Tabellen
mit gemeinsamer `REF`-Spalte (Zählungen, Radar, Top 10 je Case, Anhänge)
zeigen dagegen die Maxima des ganzen simulierten Zeitraums.

Jedes Betriebsmittel wird dabei mit sich selbst in `REF` verglichen. Eine
Verletzung ist `NEW`, wenn sie nur mit der Außerbetriebnahme auftritt,
`WORSENED`, wenn sie schon in `REF` besteht und sich verschärft, und
`PRE-EXISTING`, wenn sie in `REF` genauso besteht. Der Außerbetriebnahme wird
nur angelastet, was neu oder verschärft ist.

Mögliche Urteile:

| Assessment | Bedeutung |
|---|---|
| `BASELINE` | die Zeile von `REF` |
| `NO LIMIT EXCEEDED` | im Fenster keine Überlastung und keine Spannung außerhalb ihres Bands |
| `NO ADDITIONAL VIOLATION` | Verletzungen im Fenster bestehen alle schon in `REF` (gelb) |
| `OVERLOAD` | die Außerbetriebnahme verursacht oder verschärft eine Überlastung (rot) |
| `VOLTAGE BAND` | sie verursacht oder verschärft eine Bandverletzung (rot) |
| `OVERLOAD + VOLTAGE BAND` | beides (rot) |
| `NOT SIMULATED` | übersprungen; der Grund steht in der letzten Spalte |
| `NOT EVALUATED` | der Case ist nicht gerechnet oder nicht vergleichbar; Ursache in der letzten Spalte |
| `NO RESULT DATA IN WINDOW` | keine Ergebniszeile fällt in das Fenster |

Die letzte Spalte beginnt mit der Auslastung: das Betriebsmittel, das die
Außerbetriebnahme über 100 % bringt (sonst das höchstbelastete), mit Wert,
Uhrzeit und seinem Wert in `REF`, dem größten Anstieg, danach der Zahl der Überlastungen
nach neu, verschärft und vorbestehend. Es folgen Spannungsspanne und Bandverletzungen.

## Aufbau des Berichts

Querformat, ein Kapitel je Seite, in der Reihenfolge des Templates
`GridLens_Template_Optimiert_v2.pdf` (ohne den Generator-Anhang):

1. Titelseite und klickbares Inhaltsverzeichnis.
2. **Model Quality Assurance** und **Calculated Cases and Planned Outages**.
3. **Reference Case – Base State Disclaimer** – Kreise für Leitungen und
   Transformatoren (bis 80 %, 80–100 %, über 100 %) und die Elemente über 100 % in `REF`.
4. **Metric View** – je Case höchste Leitungsauslastung, größter Anstieg, Spannungsspanne
   und zwei Kennzahlenkarten.
5. **Case Comparison** (drei Linienplots) und **Radar Comparison** mit Zähltabelle.
6. **Top 10 Maximum Loaded Lines**, **Most Loaded Line** und **Largest Delta**
   (Zeitplots mit REF und allen Cases).
7. **Line Impact Ranking** nach |LODF| je Außerbetriebnahme und **Top 10 Strongly
   Loaded Lines by Case**.
8. **Anhang A–C** – Leitungen und Transformatoren ab 80 % oder mit einer Änderung ab
   1 %-Punkt, Knoten außerhalb ihres Bands oder mit einer Änderung ab 0.005 p.u.; je
   Case eine Spalte, `n/a` für ausgeschaltete oder fehlende Reihen.

Tabellen zeigen `REF` und bis zu sechs Cases nebeneinander, weitere Cases folgen
darunter; Radar und Zeitplots zeichnen REF und die ersten sechs Cases.
Jedes Betriebsmittel erscheint nur mit seinem Namen aus PowerFactory
(`loc_name`).

## Elementumfang

Am Anfang von `gridlens_report.py` steht:

```python
GRID_NAME_FILTER = ''   # optional; z. B. 'D7' für das Europa-Modell
```

Ohne Text (Standard) werden alle Elemente bewertet. Mit einem Text werden nur Elemente
bewertet, deren Grid (Attribut „Grid“, `cpGrid`) diesen Text im Namen trägt. Alle übrigen
Reihen im `ElmRes` werden weder gelesen noch berichtet. Das Log nennt je Fall,
wie viele Reihen bewertet und wie viele ausgelassen wurden; der Bericht nennt
den Filter im Feld „Assessment scope“. Ein leerer Text bewertet alle Elemente.
Gehört kein Element zu einem passenden Grid, bricht der Lauf mit einem
Hinweis auf die Konstante ab.

Was der Filter im eigenen Projekt auswählt, zeigt `tools/probe_grid_filter.py`.
Das Skript ist eigenständig und braucht nur PowerFactory: als eigenes
ComPython anlegen, starten und die Ausgabe lesen. Den Filter trägt es als
Kopie in sich; `tests/test_probe_grid_filter.py` stellt sicher, dass er sich
genauso verhält wie der im Bericht. Sie listet alle Grids mit `IN`/`out`, zeigt für Beispiele,
woher das Grid kam, zählt bewertete und ignorierte Elemente je Klasse und
Grid und nennt für das gebundene Ergebnisobjekt genau die Reihen, die der
Bericht lesen würde. Das Skript ändert nichts am Projekt.

## Run Mode

Am Anfang von `gridlens_report.py` steht:

```python
RUN_REFERENCE_CASE = True
```

- `True`: zuerst `REF`, danach – falls möglich – je Außerbetriebnahme ein Case.
- `False`: nur die Outage-Cases; ohne anwendbare Außerbetriebnahme wird gar keine
  Berechnung gestartet, aber ein Bericht mit QA- und Outage-Status publiziert.
  Ohne `REF` gibt es keine Vergleiche, Deltas und LODF-Delta.

Der gewählte Modus erscheint auf dem Deckblatt. Dort steht außerdem der aktuelle
Windows-/System-Benutzer als `Generated by`.

## Fortschritt und Fehler

Die Ausgabe ist in Abschnitte gegliedert (`STEP n/7 · …` zwischen Doppellinien, je Case eine
Punktlinie `.. Case OUT01 · Name ....`) und enthält Tabellen: die gefundenen Außerbetriebnahmen
mit Status und Fenster, die LODF je Außerbetriebnahme (stärkste Leitungen oder Grund), je Case
die gelesenen Reihen mit Extremwert und Verletzungen, die Grids im Ergebnisobjekt mit
`assessed`/`ignored`, danach eine Ergebnistabelle je Case, die QA-Befunde und die publizierten
Tabellen. Die Zeilen im Format `[GridLens][NN/7][LEVEL][PHASE]` bleiben als Fortschrittsmeldungen
erhalten. Die Schritte 4 und 5 laufen je Case ineinander und stehen im Abschnitt 4.

Der Filter `GRID_NAME_FILTER` ist optional und standardmäßig aus. Ist er gesetzt und findet sich kein
Element in einem passenden Grid, bricht der Lauf nach `REF` ab und nennt die Grids des Ergebnisobjekts.

Jede Meldung enthält Schritt, Level, Phase und verstrichene Zeit, zum Beispiel:

```text
[GridLens][02/7][INFO][SETTINGS][    0.0s] Active ComStatsim settings; GridLens changes only the 'Planned Outages' option and restores it:
[GridLens][02/7][INFO][SETTINGS][    0.0s] Time period [calcPeriod] = 2
[GridLens][02/7][INFO][SETTINGS][    0.0s] Step size [stepSize] = 1
[GridLens][02/7][INFO][SETTINGS][    0.0s] Step unit [stepUnit] = 2
[GridLens][02/7][INFO][SETTINGS][    0.0s] Calculation options: iopt_maint=0, iopt_net=0, ...
[GridLens][02/7][INFO][SETTINGS][    0.0s] Simulated period [startTime..endTime] = 2014-01-01 .. 2014-01-05
[GridLens][02/7][INFO][SETTINGS][    0.0s] Planned outages [iopt_maint] = 0
[GridLens][02/7][INFO][SETTINGS][    0.0s] Result object [results] = 'Quasi-Dynamic Simulation AC' (ElmRes)
[GridLens][02/7][INFO][SETTINGS][    0.0s] Initial Study Case time: 2014-01-02 23:00:00
[GridLens][04/7][INFO][CALCULATION][   12.3s] PowerFactory is calculating REF ...
```

Nur Einstellungen, die das aktive PowerFactory-Objekt bereitstellt, werden
ausgegeben. Enum-Einstellungen behalten ihren exakten numerischen
PowerFactory-Wert. Bis auf `iopt_maint` verändert GridLens keinen dieser
Werte.

`ComStatsim.Execute()` ist ein blockierender PowerFactory-API-Aufruf. Während
dieses Aufrufs kann Python keinen feineren Fortschritt melden; vor und nach jedem
Lauf werden deshalb Fall, Status und Dauer eindeutig ausgegeben.

Die Publikation protokolliert die Dauer der Validierung, des Datenbank-Resets
und je Tabelle die Erstellung der Tabelle, die Erstellung ihrer Felder und das
Schreiben der Zellen. Vor dem Reset und vor jeder Tabelle steht eine Startmeldung.
Die Abschlussmeldung je Tabelle enthält zusätzlich die Schreibrate in Zellen pro
Sekunde. Damit lässt sich erkennen, welcher Teil der Publikation Zeit benötigt.

Während der Felderstellung und der Zellschreibvorgänge erscheint ungefähr alle
fünf Sekunden eine `Publication heartbeat`-Meldung mit dem aktuellen Fortschritt
und der seit Publikationsbeginn vergangenen Zeit. Beim Schreiben nennt sie auch
die vollständig abgeschlossenen Zeilen; die gerade geschriebene Zeile zählt erst
nach ihrem Abschluss dazu. Das Intervall steht in
`PUBLICATION_LOG_INTERVAL_SECONDS` am Anfang des Skripts. Schnelle Tabellen
benötigen keine zusätzliche Heartbeat-Meldung.

Der Heartbeat läuft zwischen den PowerFactory-API-Aufrufen auf demselben Thread.
Blockiert ein einzelner Aufruf, etwa `Reset()` oder `SetValue()`, kann Python bis
zu dessen Rückkehr keine weitere Fortschrittsmeldung ausgeben. Das Intervall ist
deshalb keine garantierte Frist und keine unabhängige Erkennung eines Hängers.
Diese Zeitmessungen verändern die publizierten Daten nicht und sind noch kein
Nachweis einer schnelleren Publikation auf dem PowerFactory-Rechner.

Bei Fehlern zeigt GridLens eine kurze, handlungsorientierte Meldung ohne
ungefilterten Traceback. Suche immer nach den Phasen `FAILED`, `ABORTED` und
`RESTORE`. Wenn die Wiederherstellung nicht verifiziert werden konnte:

1. keine weitere Netzberechnung starten,
2. Planned-Outage-Zustände im aktiven Study Case manuell prüfen,
3. Datum und Uhrzeit des aktiven Study Case mit dem Ausgangszustand vergleichen,
4. `ComStatsim.results` mit dem ursprünglichen Ergebnisobjekt vergleichen,
5. `iopt_maint` am `ComStatsim` gegen den Ausgangswert prüfen und die
   `outserv`-Werte („Ignored“) aller Planned Outages gegen den Ausgangszustand,
6. verbliebene Objekte mit Präfix `GridLens_TMP_` prüfen und gegebenenfalls
   kontrolliert entfernen – nicht aber das Objekt, auf das
   `ComStatsim.results` zeigt; das lieber umbenennen,
7. Ursache beheben und den vollständigen Lauf wiederholen.

GridLens löscht ausschließlich die temporären `ElmRes`, die es im aktuellen
Lauf selbst erzeugt. Bestehende Ergebnisse und Benutzerdateien werden nicht
bereinigt.

## Ergebnisregeln

- Auslastungsverletzung: strikt `> 100 %`.
- Spannungsverletzung: strikt außerhalb des Bands der Nennspannung. Oben in
  `gridlens_report.py` steht `VOLTAGE_LIMITS_KV`:

  | Nennspannung | zulässiges Band |
  |---|---|
  | 300 bis unter 450 kV | 360–420 kV |
  | 200 bis unter 300 kV | 198–245 kV |
  | 100 bis unter 150 kV | 99–123 kV |
  | jede andere | 0.95–1.05 p.u. |

  Diese Werte sind ein Vorschlag und vor dem Einsatz fachlich zu bestätigen.
- Werte genau auf dem Grenzwert gelten nicht als Verletzung.
- Spannungen unter 0.1 p.u. gelten als spannungslos und sind kein Messwert.
  Knoten, die nie Spannung haben, und DC-Knoten (`systype = 1`) werden nicht
  bewertet; die QA nennt ihre Anzahl.
- Nichtnumerische Werte, `None`, Booleans, NaN und Infinity werden abgelehnt.
- Pro Objekt/Kategorie gilt die erste vorhandene Variable der oben genannten
  Priorität.
- Deltas werden nur für dasselbe physische Objekt in `REF` und im Case
  berechnet; vollständige PowerFactory-Pfade bleiben interne Schlüssel.
- Ausgeschaltete Elemente erhalten keine künstlichen Nullwerte.

## PowerFactory-2026-Abnahme vor Produktion

Die lokale Testsuite kann nicht bestätigen, dass `iopt_maint=1` die Ergebnisse
tatsächlich verändert. Auf dem Zielrechner sind mindestens folgende Tests
erforderlich:

| Test | Erwartetes Ergebnis | Abbruchkriterium |
|---|---|---|
| Outage im Zeitraum | `REF` und ein Case; die Betriebsmittel aus `components` weichen im Outage-Fenster ab | identische Ergebnisse in beiden Fällen |
| Kein Outage im Zeitraum | `REF` einmal, kein Outage-Case; sauberer Report | zusätzlicher Lauf oder irreführender PASS |
| Mehrere Outages | je Außerbetriebnahme ein Case; in jedem wirkt nur sie (`outserv` der übrigen = 1), in ihrem Fenster | zwei Outages wirken im selben Case, oder `outserv` bleibt verstellt |
| Deaktivierter Outage (`outserv=1`) | `SKIPPED` mit Grund | als `CONSIDERED` geführt |
| Outage vor/nach dem Zeitraum | `SKIPPED` mit Fenster und Zeitraum im Text | als `CONSIDERED` geführt |
| `iopt_maint` war vorher 1 | `REF` trotzdem ohne Outages; Wert danach wieder 1 | Referenz enthält Outages oder Wert bleibt verstellt |
| QDS-Fehler oder Abbruch | `iopt_maint` und Resultbindung wiederhergestellt | irgendein unbestimmter Zustand |
| Extraction-/Reportfehler | Zustand bereits wiederhergestellt; klare Fehlermeldung | alte/teilweise Daten wirken aktuell |
| `RUN_REFERENCE_CASE=False` | nur Outage-Cases; keine Referenzdeltas | versteckter Referenzlauf |
| `outserv` zurück | nach dem Lauf stehen alle `IntPlannedout` wieder wie vorher | ein verstellter Wert |
| LODF | `Sensitivities / Distribution Factors` liefert je Outage-Equipment Werte; `ComVstab` und `pComSimoutage` danach wie vorher; Hilfsobjekte gelöscht | Fehler, Reste oder verstellte Einstellungen |
| Querformat-Rendering | Variantenbänder (Tabellen mit 0–6 Case-Spalten, Diagramme mit 1–7 Serien) zeigen genau eine Variante; Gruppenköpfe wiederholen sich je Block | doppelte oder fehlende Tabellen |
| Zeitachse | absolute Zeitstempel, Spanne gleich dem konfigurierten Zeitraum | `NNNNN d HH:MM` statt Datum |
| Fensterlage | `REF` und `OUTAGE` unterscheiden sich in den Zeitschritten **innerhalb** des Outage-Fensters | Abweichung erst im Schritt nach dem Fensterende (so im Testbericht vom 29.09.2026) |
| Spannungsbänder | die Bänder in `VOLTAGE_LIMITS_KV` entsprechen den eigenen Betriebsgrenzen | abweichende Grenzen |
| PDF-Sichtprüfung | lesbare QA-/Outage-Tabellen, Navigation, Diagramme und englische Inhalte | abgeschnittene oder falsch gebundene Inhalte |

Erst wenn diese Fälle im eingesetzten PowerFactory-2026-Build bestanden sind,
kann der Stand betrieblich weiterqualifiziert werden. Auch dann bleibt GridLens
eine technische Vorprüfung und keine Freigabeentscheidung.
