# Agent Context: OutageLens / GridLens

Diese Datei gilt für das gesamte Repository. Sie ist der kurze Einstieg für
neue Agents. Stand: **9. September 2026**.

## Ziel des Projekts

GridLens erzeugt direkt in **DIgSILENT PowerFactory 2026** einen wiederholbaren
Bericht zur technischen Vorprüfung von Freischaltungen im elektrischen Netz.
PowerFactory bleibt die Quelle für Netzmodell, Operation Scenarios, QDS,
Ergebnisse, interne SQLite-Reporting-Datenbank und PDF-Ausgabe.

Python erzeugt keine Berichtsvorlage und keine Mock-Payload. Python liest reale
PowerFactory-Objekte und `ElmRes`-Ergebnisse, berechnet Kennwerte und publiziert
18 Tabellen über die `IntReport`-API. Die Darstellung liegt direkt in
`MASTER_GRIDLENS.mrt`, einer Stimulsoft-XML-Datei.

Der Bericht ist eine **Vorprüfung**. Er ist kein Nachweis für N-1-Sicherheit,
Versorgungssicherheit, Schutzkoordination, sichere elektrische Trennung oder
eine abschließende betriebliche Freigabe.

## Aktueller Stand

- Standardbranch: `main`
- Aktuellen geprüften Commit mit `git log -1 --oneline` ermitteln; Commit-IDs
  können sich bei einer notwendigen Historienbereinigung ändern.
- Repository: <https://github.com/hadiibrahim-Engin/gridlens-powerfactory>
- Publisher: `4.0.0`
- MRT-Template: `2.1.0`
- Datenvertrag: `2.1`
- Lokale Prüfung: **154 Tests bestanden**
- Python-Kompilierung und XML-Strukturprüfung bestanden
- Noch offen: realer End-to-End-Test in der PowerFactory-2026-Zielinstallation

`Report.pdf` ist eine lokale Datei des Anwenders und absichtlich unversioniert.
Nicht löschen, verändern oder committen, sofern der Anwender das nicht
ausdrücklich verlangt.

## Implementierter PowerFactory-Ablauf

Dieselbe `gridlens_report.py` besitzt zwei Modi. Der Parent des aktuellen
ComPython entscheidet automatisch:

| Parent | Modus | Verhalten |
|---|---|---|
| `IntReport` | Report | Liest Snapshots, baut alle 18 Tabellen und publiziert einmal in den Report |
| jedes andere Objekt | Runner | Aktiviert die Fälle, startet `ComStatsim` und erzeugt Ergebnis-Snapshots |

Der Runner berechnet:

1. `REF`: gespeichertes Grundmodell ohne aktives Operation Scenario.
2. Alle gefundenen `IntScenario` alphabetisch nach `loc_name` als `S01`,
   `S02`, usw.

Jeder Fall besitzt ein eigenes `ElmRes` namens `GridLens_<Fall-ID>`. Der Runner
kopiert bevorzugt das ursprüngliche QDS-Ergebnisobjekt, damit dessen
Variablenauswahl erhalten bleibt, bindet `ComStatsim.results` an den Snapshot
und führt QDS aus. Fallname, Status und `outserv=1`-Elemente werden im
`desc`-Feld des Snapshots gespeichert.

Szenarioaktivierungen werden kontrolliert. Ein Fall, dessen Zustand nicht
sicher hergestellt oder dessen QDS nicht erfolgreich ausgeführt wurde, liefert
keine Kennwerte. Er bleibt als frischer, leerer Status-Snapshot erhalten und
erscheint in `ScriptedScenarios` und `ScriptedModelQuality`. Nach dem Lauf
werden das ursprüngliche Szenario und die ursprüngliche
`ComStatsim.results`-Bindung wiederhergestellt.

Wenn keine `GridLens_*`-Snapshots existieren, arbeitet der Report weiterhin im
Einzelfallmodus mit einem vorhandenen, gefüllten `ElmRes` und der Fall-ID
`AKTIV`.

## Fachliche Regeln

- Im Bericht dürfen Study Case, Szenario, Ergebnisobjekt und Betriebsmittel nur
  als kurze PowerFactory-Namen (`loc_name`) erscheinen.
- Volle PowerFactory-Pfade sind nur als interne Schlüssel zum eindeutigen
  Abgleich desselben Elements zwischen Fällen erlaubt.
- Die Szenario-Matrix zeigt ausschließlich freigeschaltete Elemente:
  `outserv=1`, Status `OFF`. Der normale ON-Zustand wird nicht aufgelistet.
- Ein Element, das in einem Fall ausgeschaltet ist und deshalb keine
  Ergebnisreihe besitzt, erhält keine künstliche Zeile mit `0.0`.
- Referenzwerte und Deltas werden nur berechnet, wenn dasselbe Element in `REF`
  und im Vergleichsfall vorhanden ist.
- Fachliche Ergebnistabellen enthalten nur Grenzwertverletzungen:
  - Leitung/Transformator: maximale Auslastung `> 100 %`
  - Spannung: Minimum `< 0,95 p.u.` oder Maximum `> 1,05 p.u.`
- Spannungswinkel sind informativ und besitzen derzeit keinen pauschalen
  Freigabegrenzwert.
- Jedes fachliche Thema beginnt im MRT auf einer eigenen Seite.
- Das Inhaltsverzeichnis bleibt klickbar; Bookmarks dürfen nicht entfernt
  werden.
- Das DIgSILENT-Logo bleibt im MRT eingebettet.
- `<ReportFile />` muss leer bleiben. Keine lokalen Windows-, macOS- oder
  Linux-Pfade in Produktionsdateien speichern.

## Ergebnisvariablen

Die aktuelle Konfiguration in `powerfactory/gridlens_pf/config.py` liest:

| PowerFactory-Objekt | Variablen nach Priorität |
|---|---|
| `ElmLne` | `c:loading`, `m:loading` |
| `ElmTr2`, `ElmTr3` | `c:loading`, `m:loading` |
| `ElmTerm` Spannungsbetrag | `m:u`, `m:u1` |
| `ElmTerm` Spannungswinkel | `m:phiu`, `m:phiu1` |

Pro Objekt und Kategorie wird nur die höchst priorisierte vorhandene Variable
verwendet. Nicht numerische, unendliche und NaN-Werte werden nicht ausgewertet.

## Wichtige Dateien

| Pfad | Verantwortung |
|---|---|
| `powerfactory/MASTER_GRIDLENS.mrt` | Produktive Stimulsoft-Vorlage, Layout, SQL-Datenquellen, Logos, Diagramme |
| `powerfactory/gridlens_report.py` | Dünner externer ComPython-Einstiegspunkt und Modul-Reload |
| `powerfactory/gridlens_pf/config.py` | Versionen, Grenzwerte, Variablen, Discovery-Flags |
| `powerfactory/gridlens_pf/discovery.py` | Ermittelt und sortiert REF, Operation Scenarios und optional Variationen |
| `powerfactory/gridlens_pf/runner.py` | Zustandswechsel, QDS, Snapshots, Metadaten und Wiederherstellung |
| `powerfactory/gridlens_pf/results.py` | Auswahl und Auslesen von `ElmRes`-Zeitreihen |
| `powerfactory/gridlens_pf/payload.py` | Statistik, Kritikalität, Referenzdeltas, Rankings und Diagrammdaten |
| `powerfactory/gridlens_pf/tables.py` | Vertrag der 18 `Scripted*`-Tabellen |
| `powerfactory/gridlens_pf/publish.py` | Validierung und `IntReport`-Publikation |
| `powerfactory/gridlens_pf/entry.py` | Moduswahl und Orchestrierung |
| `powerfactory/README.md` | Aktuelle Installations-, Betriebs- und Fehleranleitung |
| `gridlens/tests/` | Unit-, Integrations-, MRT- und Vertragsprüfungen |
| `docs/superpowers/specs/2026-09-07-szenario-runner-design.md` | Detaillierter Entwurf des Szenario-Runners |

Der Ordner `gridlens/` ist eine PowerFactory-unabhängige Bibliothek aus der
Prototypenphase. Die PowerFactory-Produktion importiert ihn nicht. Für die
PowerFactory-Laufzeit müssen `gridlens_report.py`, der vollständige Ordner
`gridlens_pf/` und `MASTER_GRIDLENS.mrt` gemeinsam ausgeliefert werden.

Die Root-Dateien `README.md`, `BIG_PICTURE.md` und `BIG_PICTURE2.md` enthalten
teilweise noch Aussagen aus dem früheren Einzelfallstand. Bis zu ihrer
Aktualisierung ist `powerfactory/README.md` für den aktuellen Laufzeitstand
maßgeblich. Alte Aussagen wie „das Skript startet keine Berechnung“ oder „nur
zwei Laufzeitdateien“ nicht übernehmen.

## Regeln für Änderungen

1. Vor Änderungen `git status`, aktuellen Branch und die letzten Commits
   prüfen. Unversionierte Benutzerdateien nicht anfassen.
2. PowerFactory-Laufzeitcode darf nur die Python-Standardbibliothek und das
   Modul `powerfactory` benötigen. Keine externe JSON-Payload, keine externe
   Schema-Datei und keine zusätzliche Datenbank einführen.
3. Das Präfix `Scripted` wird von PowerFactory ergänzt. Python erzeugt zum
   Beispiel `LineStatistics`; das MRT liest `ScriptedLineStatistics`.
4. Änderungen an Tabellenfeldern müssen synchron in `tables.py`, Payload,
   MRT-Datenquellen, SQL-Bindungen, Versionsnummern und Tests erfolgen.
5. `report.Reset()` darf bei einer Publikation nur einmal vor dem Aufbau aller
   Fälle laufen. Ein Reset je Szenario würde vorherige Fälle löschen.
6. Eine fehlgeschlagene Aktivierung, Ergebnisbindung oder Berechnung darf nie
   unter einem alten Zustand weiterlaufen und nie alte Werte als aktuell
   ausgeben.
7. Network Variations sind mit `SCAN_VARIATIONS=False` ausgeschaltet. Nicht
   aktivieren, bevor Aktivierungszeit, Stufenverhalten und Wiederherstellung in
   der konkreten PowerFactory-Installation fachlich und technisch geprüft sind.
8. Bei visuellen MRT-Änderungen die vorhandenen DIgSILENT-Farben, Segoe UI,
   Bookmarks, Seitenumbrüche und die eingebetteten Logos erhalten.
9. Änderungen auf einem eigenen Feature-Branch entwickeln und über einen PR
   nach `main` übernehmen. Eine Produktionsfreigabe erst nach dem realen
   PowerFactory-Systemtest kennzeichnen.

## Lokale Verifikation

Aus dem Repository-Root ausführen:

```bash
.venv/bin/pytest -q
python3 -m py_compile powerfactory/gridlens_report.py powerfactory/gridlens_pf/*.py
git diff --check
```

Zusätzlich vor jeder MRT-Auslieferung prüfen:

- `MASTER_GRIDLENS.mrt` lässt sich mit `xml.etree.ElementTree` parsen.
- Alle `Ref`-IDs sind eindeutig.
- `PlotsChart` besitzt genau einen `Style`.
- `<ReportFile />` ist leer.
- Keine Pfade wie `/Users/`, `/home/`, `file://`, `C:\\` oder `C:/` kommen in
  Produktionsartefakten vor.
- Die 18 MRT-Datenquellen stimmen exakt mit `TABLES` überein.

## Noch offene PowerFactory-Abnahme

Der nächste entscheidende Schritt findet auf dem PowerFactory-2026-Rechner
statt:

1. `MASTER_GRIDLENS.mrt`, `gridlens_report.py` und `gridlens_pf/` mit erhaltener
   Verzeichnisstruktur kopieren.
2. Ein ComPython direkt im Study Case als Runner anlegen.
3. Ein zweites ComPython unter dem `IntReport` als Report-Erweiterung anlegen.
4. Im Grundnetz sicherstellen, dass kein Operation Scenario aktiv ist und dass
   dieser Zustand wirklich die fachliche Referenz darstellt.
5. Echte Freischaltungsszenarien mit den gewünschten `outserv=1`-Elementen
   anlegen. Alle Fälle müssen dieselben QDS-Einstellungen, Profile, Zeiträume
   und Ergebnisvariablen verwenden.
6. Runner ausführen. Erwartet werden `GridLens_REF`, `GridLens_S01`, usw. sowie
   die Meldungen `GridLens publisher: 4.0.0` und `GridLens mode: runner`.
7. Prüfen, dass das vorher aktive Szenario und `ComStatsim.results` danach
   wiederhergestellt sind.
8. Report erzeugen. Erwartet werden `GridLens mode: report` und
   `GridLens: 18 Tabellen publiziert.`
9. PDF fachlich und visuell prüfen: kurze IDs, korrekte Zeitachse, nur kritische
   Werte, hervorgehobene Grenzwertverletzungen, gefüllte Referenzdeltas,
   unterschiedliche Szenariokurven, Balkendiagramme, Seitenumbrüche,
   Inhaltsverzeichnis und Branding.

Erst nach dieser Abnahme gilt Version 4.0.0 als produktionsbereit und darf als
entsprechende Release-Version gekennzeichnet werden.
