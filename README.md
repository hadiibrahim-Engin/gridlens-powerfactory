# OutageLens / GridLens

Das vollständige Zielbild, der aktuelle Implementierungsstand und der Weg vom
Netzmodell bis zum PDF stehen in [`BIG_PICTURE.md`](BIG_PICTURE.md).

Dieses Repository enthält einen direkt in PowerFactory 2026 verwendbaren
Auto-Report.

## Verbindlicher Betriebsleitfaden

**[`powerfactory/README.md`](powerfactory/README.md) ist die einzige gültige
Installations- und Betriebsanleitung.** Dort stehen Auslieferung, Anlage der
beiden ComPython-Objekte, Ausführungsreihenfolge, Wiederanlauf nach einem
Abbruch und die erwarteten Meldungen. Diese Seite bleibt bewusst kurz, damit
für den manuellen Rollout keine zweite, abweichende Anleitung existiert.

Die Laufzeit besteht aus **drei** gemeinsam auszuliefernden Bestandteilen unter
[`powerfactory/`](powerfactory):

- [`MASTER_GRIDLENS.mrt`](powerfactory/MASTER_GRIDLENS.mrt) – native
  Stimulsoft-Vorlage mit eingebettetem DIgSILENT-Branding
- [`gridlens_report.py`](powerfactory/gridlens_report.py) – dünner
  ComPython-Einstiegspunkt, der Runner- oder Report-Modus am Elternobjekt wählt
- [`gridlens_pf/`](powerfactory/gridlens_pf) – vollständiges Laufzeitpaket für
  Discovery, QDS-Berechnung, Snapshots, Auswertung und Tabellenpublikation

GridLens **startet Berechnungen**: Das Runner-ComPython im Study Case rechnet
den Referenzfall und jedes Operation Scenario über `ComStatsim` und legt je Fall
einen eigenen Snapshot `GridLens_<Fall-ID>` an. Erst danach publiziert das
Report-ComPython unter dem `IntReport` die 17 `Scripted*`-Tabellen für die
Vorlage. Beim Start prüft die Laufzeit anhand von
[`gridlens_pf/manifest.py`](powerfactory/gridlens_pf/manifest.py), dass alle
kopierten Bestandteile zu einem Release gehören; ein gemischtes Paket bricht ab.

Das Skript liest keine Mock-Payload und keine externe Schema-Datei. Es benötigt
nur die Python-Standardbibliothek und das in PowerFactory verfügbare Modul
`powerfactory`.

## Was ist `gridlens/`?

`gridlens/` ist eine PowerFactory-unabhängige Entwicklungsbibliothek aus der
früheren Prototypenphase. Sie normalisiert externe Datensätze und enthält
Statistik-, Ranking-, Vertrags- und Testlogik. PowerFactory importiert diesen
Ordner nicht. Der Ordner enthält zusätzlich die Testsuite, die sowohl die
Legacy-Bibliothek als auch das aktive Laufzeitpaket `powerfactory/gridlens_pf/`
prüft.

## Entwicklungswerkzeuge

Nicht Teil der Auslieferung:

| Werkzeug | Zweck |
|---|---|
| `powerfactory/tools/write_manifest.py` | Prüfsummen des Laufzeitpakets neu erzeugen; nach jeder Änderung an der Laufzeit ausführen |
| `powerfactory/tools/benchmark_reader.py` | Laufzeit und Spitzenspeicher des Ergebnislesers ohne PowerFactory messen |
| `powerfactory/tools/gridlens_probe.py` | Installations-Sonde im Zielsystem |

Die Legacy-Bibliothek `gridlens/` führt bewusst einen eigenen, eingefrorenen
Datenvertrag (2.0). Sie wird von der Produktion nicht importiert; ein Test
stellt das sicher. Produktionsregeln gehören in `powerfactory/gridlens_pf/`.

## Reifegrad und Verifikation

Der Stand ist eine **technische Vorprüfung** und keine Freigabeentscheidung.
Der offene Prüfumfang, die Befunde und die verbindliche
PowerFactory-2026-Abnahmematrix stehen in
[`docs/PRODUCTION_READINESS_REVIEW.md`](docs/PRODUCTION_READINESS_REVIEW.md).

Automatisiert geprüft werden Tabellendeklaration und Pflichtfelder,
`ElmRes`-Auswertung, Zeitachsenvalidierung, native `IntReport`-Aufrufe,
SQL-Datenquellen, Paketidentität und die eingebetteten Branding-Assets:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

`requirements-dev.txt` pinnt die Prüftoolchain exakt, damit eine
Release-Verifikation auf einem zweiten Rechner dasselbe Ergebnis liefert. Die
PowerFactory-Laufzeit benötigt nichts davon.

Der verbleibende Systemtest muss in deinem PowerFactory-2026-Build erfolgen,
weil nur dort der reale ComPython-Lifecycle, das echte `ElmRes`-Verhalten und
die interne SQLite-Verbindung verfügbar sind.
