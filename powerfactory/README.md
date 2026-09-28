# GridLens in DIgSILENT PowerFactory 2026

## Auslieferung

Kopiere immer diese beiden Dateien aus demselben Release auf den
PowerFactory-Rechner:

| Datei | Aufgabe |
|---|---|
| `gridlens_report.py` | Einzeldatei für Planned-Outage-Discovery, QDS-Läufe, Ergebnisprüfung und `IntReport`-Publikation |
| `MASTER_GRIDLENS.mrt` | Reportlayout und 17 `Scripted*`-Datenquellen |

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
  - `ElmTerm`: `m:u`, ersatzweise `m:u1`,
  - `ElmTerm`: `m:phiu`, ersatzweise `m:phiu1`,
- die zu prüfenden Planned Outages in der Operational Library,
- ein `IntReport`, das `MASTER_GRIDLENS.mrt` verwendet.

GridLens ändert **genau eine** QDS-Option: `iopt_maint`, in PowerFactory mit
„Planned Outages“ beschriftet. Zeitraum, Zeitschritt, Profile und alle
weiteren Einstellungen stammen unverändert aus dem aktiven `ComStatsim`.
Zusätzlich wird dessen `results`-Bindung für temporäre, aus dem konfigurierten
`ElmRes` kopierte Ergebnisobjekte umgebunden. Beides wird nach dem Lauf
wiederhergestellt und verifiziert.

## Installation und Ausführung

1. Lege genau ein ComPython direkt unter dem Ziel-`IntReport` an.
2. Weise diesem ComPython `gridlens_report.py` als externe Python-Datei zu.
3. Aktiviere Projekt und Study Case und prüfe die `ComStatsim`-Konfiguration.
4. Starte das ComPython einmal. Berechnung, Auswertung, Zustandswiederherstellung
   und Tabellenpublikation erfolgen in diesem Lauf.
5. Erzeuge beziehungsweise exportiere den Bericht erst nach der Meldung
   `Report published successfully`.

Die Standardreihenfolge ist:

1. `REF`: Lauf mit `iopt_maint=0`, also ohne geplante Außerbetriebnahmen.
2. Discovery aller `IntPlannedout`-Objekte; `IntOutage` wird nur als
   Legacy-Kompatibilität erkannt.
3. Vergleich jedes Outage-Fensters (`starttime`/`endtime`) mit dem simulierten
   Zeitraum (`ComStatsim.startTime`/`endTime`).
4. `OUTAGE`: ein einziger QDS-Lauf mit `iopt_maint=1`. PowerFactory wendet
   jede Außerbetriebnahme in ihrem eigenen Zeitfenster an.
5. Wiederherstellung von `iopt_maint` und `ComStatsim.results`, Löschen der
   temporären Ergebnisse.
6. Publikation aller 17 Tabellen in das `IntReport`.

## Warum GridLens die Außerbetriebnahmen nicht selbst anwendet

In PowerFactory 2026 ist `IntPlannedout` ein reines Datenobjekt. Es bietet
weder `Apply` noch `Reset` noch `Check`; abgefragt wurde das im Zielbuild
direkt an den Objekten. Relevant sind stattdessen `starttime`, `endtime`,
`components` (die geschalteten Betriebsmittel), `outserv` und `priority`.

PowerFactory wendet eine Außerbetriebnahme während der Rechnung selbst an,
sobald `iopt_maint` gesetzt ist. Das ist genauer als ein pauschales Schalten:
bei einem mehrtägigen QDS-Lauf wirkt jede Außerbetriebnahme exakt in ihren
eigenen Zeitschritten.

Deaktivierte (`outserv=1`) und außerhalb des simulierten Zeitraums liegende
Außerbetriebnahmen werden als `SKIPPED` mit Grund ausgewiesen, alle übrigen als
`CONSIDERED`. Gibt es keine im Zeitraum, entfällt der zweite Rechenlauf.

## Die Tabelle „Planned Outages“

Sie ist die Bewertungsgrundlage für die Freischaltung und hat sechs Spalten:

| Spalte | Inhalt |
|---|---|
| Planned outage | Name der Außerbetriebnahme |
| Period | Zeitfenster aus `starttime`/`endtime` |
| Prio | `priority` aus PowerFactory |
| Equipment out of service | die Betriebsmittel aus `components` |
| Assessment | das Urteil für dieses Fenster |
| Worst values inside the window | die Zahlen dahinter |

Entscheidend ist, dass jede Zeile **nur ihr eigenes Zeitfenster** bewertet. Zwei
Freischaltungen an verschiedenen Tagen bekommen dadurch verschiedene Urteile; die
Kennzahlen der übrigen Kapitel gelten dagegen über den ganzen Zeitraum.

Mögliche Urteile:

| Assessment | Bedeutung |
|---|---|
| `NO LIMIT EXCEEDED` | im Fenster keine Auslastung > 100 % und Spannung im Band 0.95–1.05 |
| `OVERLOAD` | Auslastung überschreitet 100 % |
| `VOLTAGE BAND` | Spannung verlässt das Band |
| `OVERLOAD + VOLTAGE BAND` | beides |
| `NOT SIMULATED` | übersprungen; der Grund steht in der letzten Spalte |
| `NO RESULT DATA IN WINDOW` | keine Ergebniszeile fällt in das Fenster |

Zeilen mit Grenzwertverletzung werden rot auf hellrot hervorgehoben. Die letzte
Spalte nennt die höchste Auslastung mit Betriebsmittel und Uhrzeit, den
Referenzwert desselben Fensters ohne Freischaltung und das Spannungsband. Der
Referenzwert ist der Kausalitätsnachweis: liegt er bereits über dem Grenzwert,
ist die Überlastung nicht der Freischaltung anzulasten.

## Run Mode

Am Anfang von `gridlens_report.py` steht:

```python
RUN_REFERENCE_CASE = True
```

- `True`: zuerst `REF`, danach – falls möglich – `OUTAGE`.
- `False`: nur `OUTAGE`; ohne anwendbaren Outage wird gar keine Berechnung
  gestartet, aber ein Bericht mit QA- und Outage-Status publiziert.

Der gewählte Modus erscheint auf dem Deckblatt. Dort steht außerdem der aktuelle
Windows-/System-Benutzer als `Generated by`.

## Fortschritt und Fehler

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

Bei Fehlern zeigt GridLens eine kurze, handlungsorientierte Meldung ohne
ungefilterten Traceback. Suche immer nach den Phasen `FAILED`, `ABORTED` und
`RESTORE`. Wenn die Wiederherstellung nicht verifiziert werden konnte:

1. keine weitere Netzberechnung starten,
2. Planned-Outage-Zustände im aktiven Study Case manuell prüfen,
3. Datum und Uhrzeit des aktiven Study Case mit dem Ausgangszustand vergleichen,
4. `ComStatsim.results` mit dem ursprünglichen Ergebnisobjekt vergleichen,
5. `iopt_maint` am `ComStatsim` gegen den Ausgangswert prüfen,
6. verbliebene Objekte mit Präfix `GridLens_TMP_` prüfen und gegebenenfalls
   kontrolliert entfernen,
7. Ursache beheben und den vollständigen Lauf wiederholen.

GridLens löscht ausschließlich die temporären `ElmRes`, die es im aktuellen
Lauf selbst erzeugt. Bestehende Ergebnisse und Benutzerdateien werden nicht
bereinigt.

## Ergebnisregeln

- Auslastungsverletzung: strikt `> 100 %`.
- Spannungsverletzung: strikt `< 0.95 p.u.` oder `> 1.05 p.u.`.
- Werte genau auf dem Grenzwert gelten nicht als Verletzung.
- Nichtnumerische Werte, `None`, Booleans, NaN und Infinity werden abgelehnt.
- Pro Objekt/Kategorie gilt die erste vorhandene Variable der oben genannten
  Priorität.
- Deltas werden nur für dasselbe physische Objekt in `REF` und `OUTAGE`
  berechnet; vollständige PowerFactory-Pfade bleiben interne Schlüssel.
- Ausgeschaltete Elemente erhalten keine künstlichen Nullwerte.
- Spannungswinkel sind informativ und haben keinen pauschalen Freigabegrenzwert.

## PowerFactory-2026-Abnahme vor Produktion

Die lokale Testsuite kann nicht bestätigen, dass `iopt_maint=1` die Ergebnisse
tatsächlich verändert. Auf dem Zielrechner sind mindestens folgende Tests
erforderlich:

| Test | Erwartetes Ergebnis | Abbruchkriterium |
|---|---|---|
| Outage im Zeitraum | `REF` und `OUTAGE`; die Betriebsmittel aus `components` weichen im Outage-Fenster ab | identische Ergebnisse in beiden Fällen |
| Kein Outage im Zeitraum | `REF` einmal, kein `OUTAGE`; sauberer Report | zweiter Lauf oder irreführender PASS |
| Mehrere Outages | genau ein `OUTAGE`-Lauf; jede Außerbetriebnahme wirkt in ihrem Fenster | ein Lauf je Outage oder unvollständige Liste |
| Deaktivierter Outage (`outserv=1`) | `SKIPPED` mit Grund | als `CONSIDERED` geführt |
| Outage vor/nach dem Zeitraum | `SKIPPED` mit Fenster und Zeitraum im Text | als `CONSIDERED` geführt |
| `iopt_maint` war vorher 1 | `REF` trotzdem ohne Outages; Wert danach wieder 1 | Referenz enthält Outages oder Wert bleibt verstellt |
| QDS-Fehler oder Abbruch | `iopt_maint` und Resultbindung wiederhergestellt | irgendein unbestimmter Zustand |
| Extraction-/Reportfehler | Zustand bereits wiederhergestellt; klare Fehlermeldung | alte/teilweise Daten wirken aktuell |
| `RUN_REFERENCE_CASE=False` | nur `OUTAGE`; keine Referenzdeltas | versteckter Referenzlauf |
| Zeitachse | absolute Zeitstempel, Spanne gleich dem konfigurierten Zeitraum | `NNNNN d HH:MM` statt Datum |
| PDF-Sichtprüfung | lesbare QA-/Outage-Tabellen, Navigation, Diagramme und englische Inhalte | abgeschnittene oder falsch gebundene Inhalte |

Erst wenn diese Fälle im eingesetzten PowerFactory-2026-Build bestanden sind,
kann der Stand betrieblich weiterqualifiziert werden. Auch dann bleibt GridLens
eine technische Vorprüfung und keine Freigabeentscheidung.
