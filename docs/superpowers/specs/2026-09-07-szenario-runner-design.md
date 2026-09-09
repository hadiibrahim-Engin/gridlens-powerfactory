# Szenario-Runner für den GridLens-PowerFactory-Bericht

Stand: 7. September 2026 · Basis: Commit `c1fe416` · Publisher 3.0.1 · Template 2.0.1

Die offenen PowerFactory-API-Fragen sind durch einen Sondenlauf beantwortet
(Abschnitt 11). Abschnitt 5 nutzt das Ergebnis und kommt ohne den ursprünglich
geplanten Kopiermechanismus aus. Abschnitt 11.1 hält einen Befund fest, der
die Aussagekraft des Berichts betrifft, nicht seine Machbarkeit.

## 1. Ziel

Der Bericht wertet heute genau einen Zustand aus: das aktive Study Case mit
seinem vorhandenen `ElmRes`. Alle Referenz- und Deltaspalten der 18 Tabellen
bleiben leer, und ein zweiter Skriptlauf überschreibt den vorherigen Bericht
über `report.Reset()`.

Ziel dieser Änderung ist der Freischaltungsvergleich: Der Bericht soll mehrere
Netzzustände nebeneinanderstellen, jeden gegen einen Referenzzustand ohne
Freischaltung, und die Wirkung jeder Freischaltung auf Auslastung, Spannung und
Spannungswinkel belegen.

### Nicht im Umfang

Bewusst ausgeschlossen, damit der Umfang lieferbar bleibt:

- **N-1-Rechnung, Versorgungssicherheitsnachweis, Nachweis sicherer
  elektrischer Trennung.** Diese bleiben in `ScriptedModelQuality` ausdrücklich
  als nicht bewertet gekennzeichnet.
- **Kreuzprodukt aus Netzvariante × Szenario.** Fälle werden flach
  nacheinander abgearbeitet.
- **Der Berichtsstatus bleibt „Vorprüfung – keine abschließende Freigabe".**
  Ein Mehrszenariovergleich erweitert die fachliche Aussage, ersetzt aber keine
  Freigabe.

## 2. Entscheidungen

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| E1 | Wo läuft die Simulation? | Getrennter Runner-Modus, ein Snapshot-`ElmRes` je Fall | Die Report-Erweiterung bleibt rein lesend. Der Bericht ist jederzeit neu renderbar, ohne den QDS-Lauf zu wiederholen, und das Projekt wird während des Renderns nicht umgeschaltet. |
| E2 | Woher kommen die Szenarien? | Automatische Discovery, keine Namensliste | Keine Pflege im Skript, keine Namenskonvention im Projekt. |
| E3 | Was ist die Referenz? | Grundmodell mit deaktivierten Operation Scenarios | Physikalisch genau der Referenzzustand ohne Freischaltung. Braucht kein eigens angelegtes REF-Szenario. |
| E4 | Netzvarianten? | Unterstützt, hinter `SCAN_VARIATIONS`, Standard `False` | Varianten tragen in realen Projekten meist Modellierungstiefe oder Ausbaustufen, keine Schaltzustände (Abschnitt 11.1). Sie pauschal als Freischaltungsfälle zu fahren, erzeugt fachlich sinnlose Vergleiche. Der Szenarienvergleich ist ohne Varianten vollständig funktionsfähig. |
| E5 | Zeilen in den Grenzwerttabellen | Verletzt ein Element in irgendeinem Fall, erscheint es mit je einer Zeile pro Fall, in dem es eine Ergebnisreihe besitzt | Die Auslastung desselben Betriebsmittels in den übrigen Szenarien ist der eigentliche Erkenntnisgewinn. |
| E6 | Nicht konvergierte Fälle | Lauf fortsetzen, Fall dokumentieren, Werte aus allen Kennzahlen sperren | Numerisch ungültige Werte dürfen nie als Auslastung zitiert werden. Die Lücke muss aber sichtbar sein. |
| E7 | Zeitreihen | Vier Diagramme, je eine Kurve pro Fall | Der Freischaltungseffekt ist unmittelbar ablesbar, der Bericht bleibt kompakt. |
| E8 | Fallmetadaten und Freischaltungsliste | In `desc` des Snapshot-`ElmRes` | Der Report-Modus muss Name, Status und `outserv`-Elemente lesen können, ohne ein Szenario zu aktivieren (Abschnitt 6). |
| E9 | Codestruktur | Paket `gridlens_pf/` mit dünnem Einstiegspunkt | Die Fachlogik wird ohne PowerFactory testbar. |

## 3. Architektur

### 3.1 Zwei Modi, eine Einstiegsdatei

`gridlens_report.py` erkennt seinen Modus am Elternobjekt:

| `script.GetParent()` | Modus | Verhalten |
|---|---|---|
| `IntReport` | Report | rein lesend, publiziert die 18 Tabellen |
| alles andere | Runner | rechnet, publiziert nichts |

Dieselbe Datei wird zweimal in PowerFactory verknüpft: als `ComPython` im
Study Case (Runner) und als `ComPython` unter dem `IntReport`
(Report-Erweiterung). Keine Konfiguration, kein Moduswahlparameter.

### 3.2 Einstiegspunkt und Modul-Purge

```python
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

for _name in [n for n in sys.modules
              if n == "gridlens_pf" or n.startswith("gridlens_pf.")]:
    del sys.modules[_name]

from gridlens_pf import main
main()
```

Das Purge ist nicht optional. PowerFactory startet für einen Skriptlauf keinen
frischen Interpreter und behält `sys.modules` über Läufe hinweg. Ohne das Purge
würde nach einer Änderung an einem Untermodul weiterhin die alte Fassung
ausgeführt — und die Konsole zeigte trotzdem die neue Publisher-Version, weil
die Einstiegsdatei aktuell ist. Das ist genau der Fehlerfall, den die
Versionsmeldung heute abfangen soll, nur schwerer zu erkennen.

### 3.3 Modulschnitt

Ordnername `gridlens_pf`, nicht `gridlens`, sonst kollidiert das
Deployment-Paket mit dem bestehenden Top-Level-Paket `gridlens/` auf
`sys.path`.

| Modul | Verantwortung | PowerFactory |
|---|---|---|
| `config.py` | Grenzwerte, `VARIABLES`, Flags, Versionen | nein |
| `tables.py` | `TABLES`-Kontrakt, `FIELD_TYPES` | nein |
| `timeaxis.py` | Zeiteinheit, Normierung, Formatierung | nein |
| `payload.py` | `scenario_result`, `apply_reference`, `build_payload` | nein |
| `pfutil.py` | `safe_attr`, `object_key/name/id`, `class_name`, `finite_number` | duck-typed |
| `results.py` | `select_result`, `collect_series`, `statistics` | `ElmRes` |
| `discovery.py` | Fälle finden und ordnen | `app` |
| `runner.py` | Aktivieren, rechnen, Snapshot, `desc` schreiben | `app` |
| `publish.py` | `validate_payload`, `coerce_value`, `publish_report` | `IntReport` |

Die vier Module ohne PowerFactory-Abhängigkeit enthalten die gesamte
Fachlogik. Referenz- und Deltarechnung werden damit reiner Python-Code, der
ohne Attrappe getestet werden kann.

Deployment wird ein Ordner statt zwei Dateien: `gridlens_report.py` +
`gridlens_pf/` + `MASTER_GRIDLENS.mrt`.

## 4. Discovery

```python
SCAN_SCENARIOS  = True
SCAN_VARIATIONS = False
MAX_CASES       = 12
```

`discovery.py` liefert eine flache, deterministisch geordnete Fallliste:

| Reihenfolge | Fall | ID | Sortierung |
|---|---|---|---|
| 1 | Grundmodell, alle Szenarien deaktiviert | `REF` | immer, unabhängig von den Flags |
| 2… | Network Variations | `V01`, `V02`, … | Aktivierungszeitpunkt, dann `loc_name` |
| …n | Operation Scenarios | `S01`, `S02`, … | `loc_name` alphabetisch |

Die Sortierung dient der Reproduzierbarkeit, nicht der Bequemlichkeit: `S02`
muss in zwei Berichtsständen dasselbe Betriebsmittel meinen, sonst ist der
Vergleich zweier Berichte wertlos.

Der vollständige `loc_name` steht in `scenario_name`, die Art des Falls
(`Operation Scenario` / `Network Variation, Stufe X`) in `description`. Dadurch
keine Schemaänderung an `ScriptedScenarios`.

`MAX_CASES` begrenzt die Gesamtzahl der Rechenläufe **einschließlich REF**.
Bei `MAX_CASES = 12` sind also REF und elf weitere Fälle zulässig. Wird die
Grenze überschritten, bricht der Runner mit vollständiger Fallliste ab,
**bevor** der erste Rechenlauf startet.

## 5. Runner-Ablauf

1. Fälle über `discovery.py` ermitteln, Anzahl gegen `MAX_CASES` prüfen.
2. Ausgangszustand merken (aktives Szenario, aktive Variante).
3. Ausgangswert von `ComStatsim.results` merken.
4. Je Fall:
   1. Zustand herstellen — für `REF` das aktive Szenario `Deactivate()`.
   2. Freischaltungsliste einsammeln: alle `ElmLne`/`ElmTr2`/`ElmTr3` mit
      `outserv=1`.
   3. Snapshot-`ElmRes` `GridLens_<ID>` im Study Case bereitstellen;
      vorhandenes gleichnamiges Objekt vorher `Delete()`. Bevorzugt wird das
      ursprüngliche QDS-Ergebnisobjekt kopiert, damit dessen Variablenauswahl
      erhalten bleibt; falls `AddCopy` nicht greift, wird ein leeres `ElmRes`
      angelegt.
   4. `ComStatsim.results` auf den Snapshot setzen und **zurücklesen**. Zeigt
      das Attribut danach nicht auf den Snapshot, greift der Fallback: normal
      rechnen und das erzeugte Ergebnis anschließend per `AddCopy` unter dem
      Snapshotnamen ablegen.
   5. `ComStatsim.Execute()`; Rückgabewert prüfen.
   6. Fallname, Status und Freischaltungsliste nach `desc` schreiben.
   7. Bei Fehlercode ≠ 0: den frisch erzeugten, leeren Snapshot als
      Statusmarker behalten, keine Ergebniswerte auswerten und weitermachen.
5. Im `finally`-Zweig **beides** zurücksetzen: Ausgangszustand (aktives
   Szenario, aktive Variante) **und** `ComStatsim.results` auf den gemerkten
   Ausgangswert — auch bei Ausnahme oder Abbruch.
6. Zusammenfassung ausgeben: Fall, ID, Status, Fehlercode, Snapshotname.

Das Zurücksetzen von `ComStatsim.results` ist kein Schönheitsfehler. Bliebe das
QDS-Kommando auf `GridLens_S03` zeigen, schriebe jede spätere Handrechnung des
Anwenders unbemerkt in ein GridLens-Snapshotobjekt — und der nächste Bericht
läse ein Ergebnis, das nicht aus dem Runner stammt.

Der alte Snapshot wird vor jedem Fall gelöscht. Schlägt der neue Lauf fehl,
bleibt ausschließlich ein frisch erzeugter, leerer Statusmarker unter dem
Snapshotnamen zurück. So kann der Report den fehlgeschlagenen Fall zeigen,
ohne veraltete Ergebniswerte einzulesen.

Jeder Fall schreibt von vornherein in sein eigenes Objekt. Eine Kopie des
ursprünglichen Ergebnisobjekts dient dabei nur als konfigurierte Vorlage für
die Ergebnisvariablen; der neue QDS-Lauf ersetzt die Werte. Wenn die direkte
Bindung nicht greift, bleibt `AddCopy` zusätzlich die Rückfallebene nach dem
Rechenlauf.

## 6. Persistenz der Freischaltungsliste

`outserv` ist nur lesbar, solange der jeweilige Zustand aktiv ist. Im
Report-Modus ist aber nur ein Zustand aktiv — die Freischaltungen der übrigen
Fälle wären verloren.

Der Runner schreibt Fallmetadaten und Freischaltungen deshalb beim Rechnen in
das `desc`-Feld des Snapshot-`ElmRes`. Metadatenzeilen beginnen mit
`GridLensMeta.`, Freischaltungen stehen zeilenweise als `<Klasse>|<loc_name>`:

```
GridLensMeta.id=S01
GridLensMeta.name=Freischaltung Nord
GridLensMeta.status=konvergiert
ElmLne|Leitung 17
ElmTr2|Transformator 1
```

Der Report-Modus liest sie von dort zurück und speist daraus
`ScriptedOutages` und `ScriptedScenarioMatrix`. Damit bleibt alles im
PowerFactory-Projekt: kein JSON, keine externe Datei, keine
Szenario-Umschaltung während des Renderns.

`desc` ist durch den Sondenlauf als **Liste von Strings** belegt (Abschnitt 11,
Befund B3): `GetAttribute("desc")` liefert `[]` auf einem frischen `ElmRes`.
Der Runner schreibt entsprechend eine Liste, nicht einen Zeilenumbruch-String.
Das Zurücklesen toleriert dennoch beide Formen, damit ein von Hand gefülltes
`desc` den Bericht nicht zum Absturz bringt.

## 7. Report-Ablauf

1. Snapshots `GridLens_*` im aktiven Study Case suchen und nach ihrer
   Fall-ID ordnen: `REF` zuerst, danach `V*` und `S*` aufsteigend. Die
   Reihenfolge im Bericht ist damit unabhängig davon, in welcher Reihenfolge
   PowerFactory die Objekte zurückgibt.
2. **Keiner gefunden → Rückfall auf das heutige Verhalten:** ein aktives
   `ElmRes`, Fall-ID `AKTIV`, Referenzspalten leer. Nichts regressiert.
3. Je erfolgreichem Snapshot: `Load()` → `collect_series()` →
   `scenario_result()` → `Release()`. Fehlermarker liefern nur ihren Status
   und keine Kennwerte.
4. `apply_reference()` über alle Fälle.
5. `build_payload()` einmal über die gesamte Fallliste.
6. **Ein einziges** `publish_report()` mit genau einem `Reset()`.

## 8. Referenz und Deltas

`apply_reference()` ordnet Betriebsmittel über `object_key()` — den vollen
PowerFactory-Pfad — zu, **nicht** über `loc_name`. Namen sind projektweit nicht
zwingend eindeutig; eine Verwechslung zweier gleichnamiger Leitungen würde
falsche Deltas erzeugen, die im Bericht nicht als falsch erkennbar wären.

- Element in REF und Fall X vorhanden → Referenzwert und Delta gesetzt.
- Element in REF nicht vorhanden (etwa freigeschaltet) → Referenzspalten leer,
  Delta leer. Kein `0.0` als Ersatzwert.
- REF fehlt oder ist nicht konvergiert → alle Referenzspalten bleiben leer,
  `ScriptedReferenceComparison` bleibt leer, `ScriptedModelQuality` erhält eine
  Warnung.

**Mitzukorrigierender Fehler:** `append_ranking()` schreibt heute
`reference_value = metric_value` und `delta_value = 0.0`. Der Bericht behauptet
damit einen Referenzvergleich, den es nicht gibt. Beide Felder werden künftig
mit echten Werten gefüllt oder bleiben leer.

## 9. Auswirkung auf die 18 Tabellen

| Tabelle | Änderung |
|---|---|
| `ScriptedReportMeta` | `assessment_scope` nennt Fallzahl und Referenzfall |
| `ScriptedModelQuality` | je nicht konvergiertem Fall ein FAIL mit Fehlercode; Referenzvergleich nicht mehr pauschal „nicht bewertet" |
| `ScriptedScenarios` | eine Zeile je Fall, `is_reference=1` für REF, `simulation_status` `konvergiert` / `NICHT KONVERGIERT` |
| `ScriptedOutages` | je Fall aus `desc` gespeist |
| `ScriptedScenarioMatrix` | Element × Fall, weiterhin ausschließlich `outserv=1` / `OFF` |
| `ScriptedLineStatistics` | Blockvergleich nach E5, Referenz- und Deltaspalten gefüllt |
| `ScriptedTransformerStatistics` | wie oben |
| `ScriptedVoltageStatistics` | wie oben |
| `ScriptedLineLoadingBars` | Verletzungen über alle Fälle, Top 12; neues Feld `bar_label` |
| `ScriptedTransformerLoadingBars` | wie oben |
| `ScriptedVoltageMagnitudeBars` | wie oben |
| `ScriptedVoltageAngleBars` | wie oben |
| `ScriptedReferenceComparison` | erstmals gefüllt: je Element und Fall ≠ REF |
| `ScriptedScenarioComparison` | je Kennzahl eine Zeile pro Fall |
| `ScriptedRankings` | über alle Fälle, echte `reference_value` und `delta_value` |
| `ScriptedRelevantTimePoints` | über alle Fälle, mit Fallzuordnung |
| `ScriptedPlots` | vier Diagramme, über alle Fälle bestimmt |
| `ScriptedPlotData` | `series_role` trägt die Fall-ID statt `Referenz`/`Szenario` |

Ein freigeschaltetes Betriebsmittel besitzt in seinem Fall in der Regel keine
Ergebnisreihe im `ElmRes`. Für diesen Fall entsteht **keine Zeile mit
Nullwerten**, sondern gar keine Zeile; die Freischaltung selbst ist über
`ScriptedScenarioMatrix` und `ScriptedOutages` belegt. Eine Auslastung von
`0 %` wäre fachlich etwas anderes als „nicht in Betrieb" und darf im Bericht
nicht so aussehen.

`element_name` bleibt in allen Tabellen reiner `loc_name`. Das neue Feld
`bar_label` (`S02 · Leitung 17`) dient ausschließlich der Achsenbeschriftung,
damit gleiche Betriebsmittel aus verschiedenen Fällen unterscheidbar bleiben.
Im Rückfallmodus `AKTIV` enthält es nur den `loc_name`.

## 10. MRT-Änderungen

1. **Spaltenlisten** der vier Balkentabellen um `bar_label` erweitern; sonst
   schlägt `test_mrt_sources_match_embedded_table_contract` fehl.
2. **Balkenachsen** auf `bar_label` umstellen.
3. **Diagrammfarben.** Die Zeitreihenserie hat heute `AllowApplyStyle=False`
   mit fest verdrahteter `LineColor` 181,18,62, und der Chart besitzt keinen
   `<Style>`-Block. Stimulsoft erzeugt Auto-Series als Kopien der
   Vorlagenserie; ohne Style-Anwendung erbten alle Kopien dieselbe Farbe und
   REF, S01, S02 lägen als identisch burgunderrote Kurven übereinander. Das ist
   dieselbe Fehlerklasse, die Template 2.0.1 gerade behoben hat, eine Ebene
   höher. Behebung: `AllowApplyStyle=True`, keine fest verdrahtete
   `LineColor` und der bereits in der Vorlage verwendete eingebaute
   `StiStyle29`. Stimulsoft weist den Auto-Series damit die Stilfarben zu. Die
   Sortierung `ORDER BY plot_id, series_role, timestamp` hält die Zuordnung
   über Berichtsstände stabil.
4. **`validate_payload`** prüft `series_role` künftig gegen die Menge der
   Fall-IDs statt gegen `("Referenz", "Szenario")`.

Die Master-Detail-Bindung über `plot_id` und
`AutoSeriesKeyDataColumn = ScriptedPlotData.series_role` bleibt unverändert.
Stimulsoft erzeugt daraus je Fall eine Kurve samt Legende.

## 11. Befunde der Installations-Sonde

Ermittelt durch `powerfactory/tools/gridlens_probe.py` (Commit `c1fe416`), rein
lesend, auf PowerFactory 2026 mit Python 3.12.10.

| # | Frage | Befund | Wirkung |
|---|---|---|---|
| B1 | Attribut, das `ComStatsim` an ein `ElmRes` bindet | **`results`** — `GetAttribute("results")` liefert `ElmRes 'Quasi-Dynamic Simulation AC'` | Jeder Fall rechnet direkt in sein eigenes Objekt; kein Kopieren nötig (Abschnitt 5) |
| B2 | Containerfähigkeit des `IntCase` | `AddCopy`, `PasteCopy`, `CreateObject`, `Delete` alle vorhanden und aufrufbar | Snapshot anlegen und löschen ist abgedeckt; `AddCopy` bleibt Rückfallebene |
| B3 | Laufzeittyp von `desc` | **`list`** — leeres `ElmRes` liefert `[]` | Freischaltungsliste wird als Liste von Strings geschrieben |
| B4 | Zeitattribut der Expansion Stages | **`tAcTime`** als `int` in Sekunden (beobachtet: 0, 3600, 7200, 10800, 14400); zusätzlich `iSchemeStatus`, `cpHeadFold` | Sortierung der Varianten nach Aktivierungszeit ist umsetzbar |
| B5 | `Activate` / `Deactivate` | Auf `IntScenario` **und** `IntScheme` vorhanden | REF über `Deactivate()` ist umsetzbar |

Zwei Nebenbefunde, die den Entwurf bestätigen:

- `GetAttributes()` und `GetAttributeNames()` existieren **nicht**. Die
  Kandidatensondierung war also nicht nur bequem, sondern der einzige Weg —
  `dir()` hätte `results` nicht gezeigt.
- `app.GetActiveScenario()` liefert `None`. Der Referenzfall REF entspricht
  damit bereits dem gespeicherten Ausgangszustand des Projekts.

### 11.1 Befund zum Projektinhalt

Die Sonde lief gegen das Projekt `39 Bus New England System`, Study Case
`2.1 Simulation Fault Bus 16 Stable`. Der Inhalt ist für einen
Freischaltungsbericht nicht geeignet:

| Gefunden | Bewertung |
|---|---|
| Genau **ein** Operation Scenario: `EMT` | Es existiert kein Freischaltungsszenario. Der Runner erzeugte REF plus einen Fall. |
| Sechs Varianten: `EMT Load modelling`, `EMT General`, `EMT Generator modelling`, `EMT Transmission line modelling`, `Shunt Compensator`, `YNd Transformers` | Das sind **Modellierungsvarianten**, keine Schaltzustände. |
| `tAcTime` der Stufen: 0, 3600, 7200, 10800, 14400 s | Stundenraster eines Demoprojekts, keine Ausbautermine. |

Fachliche Konsequenz: Würde `SCAN_VARIATIONS` hier eingeschaltet, vergliche der
Bericht `EMT Generator modelling` gegen `EMT Load modelling`, als wären es
Freischaltungen. Das sind aber zwei **Modellierungstiefen desselben Netzes**,
keine zwei Betriebszustände. Die resultierenden Auslastungsdeltas beschrieben
den Unterschied zwischen zwei Modellansätzen und nicht die Wirkung einer
Freischaltung — eine Zahl, die im Berichtslayout korrekt aussähe und fachlich
wertlos wäre.

Für einen aussagekräftigen Bericht müssen daher zuerst die im Auftrag
beschriebenen Operation Scenarios im Projekt angelegt werden — je Szenario die
gewünschten Betriebsmittel mit `outserv=1` gespeichert, bei identischem
Simulationszeitraum, Zeitschritt und identischen Ergebnisvariablen. Ohne sie
ist der Runner lauffähig, der Vergleich aber inhaltsleer.

Dieser Befund betrifft die **Aussagekraft**, nicht die Machbarkeit. Die
Umsetzung kann unabhängig davon beginnen; die Tests decken den
Mehrszenariofall über die Attrappe ab.

### 11.2 Verbleibend offen

`IntCase.GetStudyTime` / `SetStudyTime`: Die Sondenausgabe brach vor diesen
beiden Zeilen ab. Damit ist weiterhin unbestätigt, ob `IntSstage.Activate()`
allein genügt oder die Study Time mitgesetzt werden muss. Das betrifft
ausschließlich `SCAN_VARIATIONS`, das nach Abschnitt 11.1 ohnehin ausgeschaltet
bleibt, und blockiert die Umsetzung nicht.

## 12. Tests

Die Attrappe in `gridlens/tests/test_native_reporting.py` wird um einen
Szenarioordner, mehrere `ElmRes` und ein `ComStatsim` mit steuerbarem
Fehlercode erweitert.

| Test | Sichert |
|---|---|
| Discovery-Reihenfolge | REF zuerst, dann Varianten nach Zeit, dann Szenarien alphabetisch |
| `MAX_CASES` | Abbruch vor dem ersten Rechenlauf |
| Zustandswiederherstellung | Ausgangszustand auch nach Ausnahme wiederhergestellt |
| Ergebnisbindung | `ComStatsim.results` zeigt nach dem Lauf wieder auf den Ausgangswert, auch nach Ausnahme |
| Bindungs-Fallback | greift das Setzen von `results` nicht, wird über `AddCopy` gesnapshottet |
| Nichtkonvergenz | Fall in `ScriptedScenarios` und `ScriptedModelQuality`, aber in keiner Kennzahltabelle |
| Veralteter Snapshot | wird vor dem Lauf gelöscht; Fehler hinterlassen nur einen frischen leeren Statusmarker |
| `desc`-Rundlauf | Freischaltungsliste schreiben und zurücklesen, beide `desc`-Formen |
| Referenzdeltas | korrekt gegen REF; leer, wenn Element in REF fehlt |
| Blockvergleich (E5) | Element mit einer Verletzung erzeugt Zeilen für alle Fälle |
| Rankings | echte `reference_value`, kein `delta_value = 0.0` mehr |
| Diagrammtrennung | je `plot_id` genau eine Kurve pro Fall, keine Elementvermischung |
| Ein `Reset()` | genau einmal für den Gesamtlauf |
| Rückfallmodus | ohne Snapshots weiterhin `AKTIV`-Verhalten |
| Modul-Purge | vorbelegtes `sys.modules` wird bereinigt |
| MRT-Vertrag | Spaltenlisten inklusive `bar_label` (bestehender Test) |

Der Test `test_runtime_package_is_two_files_and_has_no_mock_input` wird
umgeschrieben: Er prüft künftig „kein JSON, keine Mock-Payload, keine
Fremdpakete" über das gesamte Deployment-Paket statt die Dateianzahl.

## 13. Versionen

| Größe | alt | neu |
|---|---|---|
| Publisher | 3.0.1 | 4.0.0 |
| Template | 2.0.1 | 2.1.0 |
| Datenkontrakt | 2.0 | 2.1 |

Publisher 4.0.0 ist bewusst ein Hauptversionssprung: Deploymentform, Modus­
erkennung und `series_role`-Belegung ändern sich inkompatibel. Die
Konsolenmeldung `GridLens publisher: 4.0.0` bleibt der Prüfstein dafür, dass
PowerFactory die aktuelle Fassung ausführt.
