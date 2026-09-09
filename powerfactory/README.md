# GridLens direkt in PowerFactory 2026

Für die PowerFactory-Laufzeit werden die Einstiegsdatei, das Paket
`gridlens_pf/` und die Berichtsvorlage gemeinsam benötigt:

| Datei | Zweck |
|---|---|
| `MASTER_GRIDLENS.mrt` | Stimulsoft-XML-Vorlage mit eingebettetem DIgSILENT-Logo und PowerFactory-Layout |
| `gridlens_report.py` | Dünner ComPython-Einstiegspunkt; wählt Runner- oder Report-Modus anhand des Elternobjekts |
| `gridlens_pf/` | Laufzeitpaket für Discovery, QDS-Berechnung, Snapshots, Auswertung und Tabellenpublikation |
| `tools/gridlens_probe.py` | Optionale Installations-Sonde; gehört nicht zur Laufzeit |

Es gibt keine Mock-Payload und keine externe Schema-Datei. Das Python-Skript
liest keine JSON-Datei. Es benötigt nur die Python-Standardbibliothek und das in
PowerFactory verfügbare Modul `powerfactory`.

## Was das Skript macht

Dieselbe `gridlens_report.py` wird an zwei ComPython-Objekten verwendet. Liegt
das ComPython direkt im Study Case, läuft der Szenario-Runner. Liegt es unter
einem `IntReport`, liest es die gespeicherten Ergebnisse und publiziert die 18
Designer-Tabellen.

Der Runner findet die Operation Scenarios des aktiven Projekts, berechnet zuerst
den Referenzfall `REF` ohne aktives Operation Scenario und danach jedes
Szenario. Jeder Fall schreibt in ein eigenes `ElmRes` namens
`GridLens_<Fall-ID>`. Status, Szenarioname und die Betriebsmittel mit
`outserv=1` werden beim Snapshot gespeichert. Nach dem Lauf werden das zuvor
aktive Szenario und die ursprüngliche Ergebnisbindung von `ComStatsim`
wiederhergestellt.

Sind noch keine `GridLens_*`-Snapshots vorhanden, bleibt der bisherige
Einzelfallmodus verfügbar und wählt ein bereits gefülltes `ElmRes`. Bevorzugt
wird:

```python
RESULT_FILE_NAME = "Quasi-Dynamic Simulation AC.ElmRes"
```

Ist dieses Objekt nicht vorhanden, nimmt der Report-Modus das gefüllte `ElmRes`
mit den meisten unterstützten Ergebnisspalten.

Ausgelesen werden standardmäßig:

| Objekt | Ergebnisvariable |
|---|---|
| Leitung `ElmLne` | `c:loading`, ersatzweise `m:loading` |
| Transformator `ElmTr2`/`ElmTr3` | `c:loading`, ersatzweise `m:loading` |
| Knoten `ElmTerm` | `m:u`, ersatzweise `m:u1` |
| Knotenwinkel `ElmTerm` | `m:phiu`, ersatzweise `m:phiu1` |

Das Skript berechnet Minimum, Maximum, Mittelwert, P95, Extremzeitpunkte,
Rankings und bis zu vier Zeitreihendiagramme. Zusätzlich werden vier kompakte
Balkendiagramme für Leitungsbelastung, Transformatorbelastung,
Spannungsbeträge und Spannungswinkel vorbereitet. Pro Balkendiagramm werden
höchstens zwölf maßgebende Betriebsmittel gezeigt.

Die Qualitätsprüfung meldet ausdrücklich, wenn alle Ergebnisreihen über den
gesamten Zeitraum konstant sind. In diesem Fall sollten QDS-Profile,
Zeitabhängigkeiten und die Ergebnisaufzeichnung geprüft werden. Fehlen
Spannungswinkel, nennt der Bericht direkt die erforderlichen Variablen
`m:phiu` beziehungsweise `m:phiu1`.

In den fachlichen Grenzwerttabellen und den Balkendiagrammen für Auslastung und
Spannungsbetrag landen nur Verletzungen. Pro Diagramm werden höchstens die zwölf
größten Verletzungen gezeigt. Der Spannungswinkel ist informativ und besitzt
bewusst keinen pauschalen Freigabegrenzwert. Die Voreinstellungen sind:

| Größe | Aufnahmekriterium |
|---|---|
| Leitung/Transformator | maximale Auslastung `> 100 %` |
| Knotenspannung | Minimum `< 0,95 p.u.` oder Maximum `> 1,05 p.u.` |

Die Grenzwerte stehen in `gridlens_pf/config.py` als `LOADING_MAX`,
`VOLTAGE_MIN` und `VOLTAGE_MAX`. Die Vergleiche sind absichtlich strikt; ein
Wert von genau `100 %`, `0,95 p.u.` oder `1,05 p.u.` gilt nicht als Verletzung.

Study Case, Szenario und Elemente werden im Bericht nur mit ihrem
PowerFactory-Namen (`loc_name`) ausgegeben. Vollständige Objektpfade dienen
intern weiterhin zur sicheren Zuordnung. Die Szenario-Matrix und die
Freischaltungstabelle enthalten ausschließlich Elemente mit `outserv=1`; ON-
Zustände werden unterdrückt.

Im Mehrfallmodus werden Referenzwerte und Deltas gegen `REF` über den internen,
eindeutigen PowerFactory-Objektschlüssel berechnet. Im Bericht erscheinen
weiterhin nur kurze `loc_name`-Bezeichnungen. Fehlgeschlagene Fälle werden in
der Szenario- und Qualitätstabelle dokumentiert und aus sämtlichen Kennzahlen
ausgeschlossen. N-1, Versorgungssicherheit und sichere elektrische Trennung
bleiben ausdrücklich nicht bewertet.

`outserv=1` wird als „im Modell außer Betrieb“ ausgegeben. Dieser Modellzustand
ist kein Nachweis für eine arbeitssichere Freischaltung vor Ort.

## Szenarien vorbereiten

Das gespeicherte Grundnetz ohne aktives Operation Scenario ist die Referenz
`REF`. Es muss deshalb den fachlich richtigen Ausgangszustand enthalten. Für
jede zu bewertende Freischaltung ein eigenes Operation Scenario anlegen, dort
die betroffenen Leitungen oder Transformatoren auf `outserv=1` setzen und das
Szenario speichern. Alle Fälle müssen dieselben QDS-Einstellungen, Profile,
Zeiträume und aufgezeichneten Ergebnisvariablen verwenden.

Der Runner sortiert die Operation Scenarios alphabetisch nach `loc_name` und
vergibt daraus `S01`, `S02` usw. Vor der Berechnung zeigt `MAX_CASES`, wie viele
Fälle einschließlich `REF` zugelassen sind. Wird die Grenze überschritten,
startet kein Rechenlauf. Bei jedem Lauf werden ausschließlich Ergebnisobjekte
mit dem Präfix `GridLens_` ersetzt oder entfernt; andere `ElmRes` bleiben
unberührt.

## Installation und direkter Test

1. `MASTER_GRIDLENS.mrt`, `gridlens_report.py` und den vollständigen Ordner
   `gridlens_pf/` gemeinsam in einen Projektordner auf dem PowerFactory-Rechner
   kopieren. Die Verzeichnisstruktur muss erhalten bleiben.
2. Im aktiven Study Case ein `ComPython` anlegen und als externe Datei
   `gridlens_report.py` zuweisen. Dieses Objekt ist der Runner.
3. Unter dem gewünschten `IntReport` ein zweites `ComPython` anlegen und
   dieselbe externe Datei zuweisen. Dieses Objekt ist die Report-Erweiterung.
4. Im PowerFactory Report Designer `MASTER_GRIDLENS.mrt` laden und dem
   `IntReport` als Vorlage zuordnen.
5. Zuerst den Runner im Study Case ausführen. Danach den `IntReport` erzeugen
   und die Vorschau oder PDF-Ausgabe öffnen.

Die Ausgabe beginnt mit:

```text
GridLens publisher: 4.0.0
GridLens study case: ...
GridLens mode: runner
```

Der Reportlauf meldet anschließend:

```text
GridLens mode: report
GridLens: 18 Tabellen publiziert.
```

Fehlt `GridLens publisher: 4.0.0`, verwendet PowerFactory noch eine ältere
Kopie. Diese Datei dann durch die aktuelle `gridlens_report.py` ersetzen oder
die externe Verknüpfung korrigieren.

## Installations-Sonde

`tools/gridlens_probe.py` ist kein Bestandteil der Laufzeit und wird für den
Berichtslauf nicht benötigt. Das Skript ermittelt einmalig, welche
PowerFactory-API deine Installation bereitstellt: das Attribut, über das
`ComStatsim` an ein bestimmtes `ElmRes` gebunden wird, die Kopierfähigkeit des
`IntCase`, den Datentyp von `desc` sowie die Zeitattribute vorhandener
Expansion Stages.

Die Sonde ist **rein lesend**. Sie ruft weder `Activate` noch `Execute`,
`SetAttribute` oder `Delete` auf und verändert das Projekt nicht. Jeder
Einzelzugriff ist abgesichert; Meldungen wie `FEHLT` oder `FEHLER` sind
gewollte Befunde und kein Fehlschlag des Skripts.

Verwendung: Projekt und Study Case aktivieren, ein `ComPython` im Study Case
anlegen, `tools/gridlens_probe.py` als externe Datei zuweisen, ausführen und
die vollständige Konsolenausgabe sichern.

## Designer- und Tabellennamen

PowerFactory ergänzt den Präfix `Scripted` automatisch. Das Skript ruft zum
Beispiel auf:

```python
report.CreateTable("LineStatistics")
```

Die MRT liest entsprechend:

```sql
SELECT * FROM "ScriptedLineStatistics"
```

Die 18 vom Skript erstellten Designer-Datenquellen sind:

- `ScriptedReportMeta`
- `ScriptedModelQuality`
- `ScriptedScenarios`
- `ScriptedOutages`
- `ScriptedScenarioMatrix`
- `ScriptedLineStatistics`
- `ScriptedTransformerStatistics`
- `ScriptedVoltageStatistics`
- `ScriptedLineLoadingBars`
- `ScriptedTransformerLoadingBars`
- `ScriptedVoltageMagnitudeBars`
- `ScriptedVoltageAngleBars`
- `ScriptedReferenceComparison`
- `ScriptedScenarioComparison`
- `ScriptedRankings`
- `ScriptedRelevantTimePoints`
- `ScriptedPlots`
- `ScriptedPlotData`

Die MRT enthält die `StiSQLiteDatabase`-Verbindung aus dem gelieferten
PowerFactory-Beispiel. Falls dein konkreter PowerFactory-Build sie nicht auf die
interne Reporting-Datenbank auflöst, im Designer die SQLite-Verbindung eines
funktionierenden nativen Reports übernehmen und den Namen `SQLite` beibehalten.

## Anpassungen

Wenn das Ergebnisobjekt anders heißt, in `gridlens_pf/config.py`
`RESULT_FILE_NAME` ändern oder auf einen leeren String setzen, damit nur die
automatische Auswahl verwendet wird.

Wenn dein `ElmRes` andere Variablen enthält, diese in `VARIABLES` ergänzen:

```python
VARIABLES = {
    "line": ("c:loading", "deine_variable"),
    "transformer": ("c:loading", "deine_variable"),
    "voltage": ("m:u", "deine_variable"),
    "voltage_angle": ("m:phiu", "deine_variable"),
}
```

Die Reihenfolge bestimmt die Priorität. Pro Objekt und Kategorie wird nur eine
Spalte verwendet, damit dieselbe Zeitreihe nicht doppelt erscheint.

Der Runner wird ebenfalls in `gridlens_pf/config.py` gesteuert:

```python
SCAN_SCENARIOS = True
SCAN_VARIATIONS = False
MAX_CASES = 12
```

`MAX_CASES` umfasst den Referenzfall. Network Variations bleiben standardmäßig
ausgeschaltet, weil sie häufig Modellierungs- oder Ausbaustufen und keine
Freischaltungszustände darstellen. Sie dürfen nur aktiviert werden, wenn ihre
fachliche Bedeutung im konkreten Projekt geprüft wurde.

Die Zeitspalte wird anhand ihrer `ElmRes`-Einheit (`s`, `min`, `h` oder `d`)
in Stunden normalisiert. Tabellen zeigen lesbare Uhrzeiten wie `00:00` und
`23:00`. Diagramme verwenden numerische Stunden, höchstens 63 Stützpunkte pro
Kurve und wenige gleichmäßig verteilte Achsenlabels. Endpunkte sowie exaktes
Minimum und Maximum bleiben beim Reduzieren immer erhalten. Falls die
Zeitspalte keine Einheit liefert, steuert `TIME_UNIT_FALLBACK` die Annahme.

## Fehlerdiagnose

| Meldung | Bedeutung / nächster Schritt |
|---|---|
| `No module named 'gridlens_pf'` | Den vollständigen Ordner `gridlens_pf/` neben `gridlens_report.py` kopieren. |
| `No active study case` | Das gewünschte Study Case aktivieren. |
| `ComStatsim nicht ... gefunden` | Im aktiven Study Case die Quasi-Dynamic Simulation anlegen oder prüfen. |
| `Operation Scenario blieb ... aktiv` | Der Runner hat den verlangten Zustand nicht sicher hergestellt und den Fall deshalb nicht berechnet. |
| `No ElmRes found` | Ergebnisobjekt im aktiven Study Case prüfen. |
| `no populated ElmRes` | Simulation zuerst ausführen und Ergebnisse speichern. |
| `no supported ... columns` | Ergebnisvariablen im `ElmRes` und `VARIABLES` vergleichen. |
| `Run this ComPython as a child of an IntReport` | ComPython unter dem richtigen `IntReport` einordnen. |
| `no such table: Scripted...` | Prüfen, ob die Report-Erweiterung vor dem Rendern lief und dieselbe interne SQLite-Verbindung verwendet wird. |
| Fehler bei `SetValue(...)` | Die Meldung nennt Tabelle, Feld und Zeilenindex; diesen vollständigen Traceback weitergeben. |

Der frühere Fehler `math.isfinite(...): TypeError: must be real number, not str`
ist seit Version 2.0.0 abgefangen: Ergebniswerte werden vor der Statistik
und vor `SetValue` sicher in endliche `float`-Werte umgewandelt.

## Vorlage und Branding

`MASTER_GRIDLENS.mrt` ist direkt bearbeitbares Stimulsoft-XML. Das offizielle
DIgSILENT-Logo ist als PNG-Daten in vier `StiImage`-Komponenten eingebettet; zur
Laufzeit ist daher weder eine zusätzliche Bilddatei noch Internetzugriff nötig.
Die Vorlage verwendet Segoe UI sowie das DIgSILENT-Burgund `#B5123E`. Version
2.1.0 enthält ein klickbares Inhaltsverzeichnis, interne Bookmarks, eine
skalierte numerische Zeitachse, rot hervorgehobene Grenzwertverletzungen und
vier Balkendiagramme. Jedes fachliche Thema beginnt auf einer eigenen Seite.
Auf dem Deckblatt stehen Ergebnisquelle, Bewertungsumfang und der Status
„Vorprüfung – keine abschließende Freigabe“.

`MASTER_GRIDLENS.mrt` speichert keinen lokalen Dateipfad: `<ReportFile />` ist
leer. Logos sind eingebettet; die Produktion benötigt daher keine externe
Bilddatei und keine auf einen Arbeitsplatz verweisende Ressource.

Die Fallkennungen bleiben mit `REF`, `S01`, `S02` usw. kompakt; der vollständige
`loc_name` steht separat im Feld `Szenario`. Die Zeitreihendiagramme sind über
`plot_id` als Master-Detail-Daten gebunden und zeigen je Fall eine eigene Kurve.

Das eingebettete Logo stammt von
`https://www.digsilent.de/files/pictures/logo.svg` (abgerufen am 6. September
2026). DIgSILENT und PowerFactory sind Marken ihrer jeweiligen Rechteinhaber.
