# Report-Datenvertrag

`gridlens/contracts/report-data-v1.yaml` ist die maßgebliche Schnittstelle
zwischen Datenaufbereitung, PowerFactory-`IntReport` und MRT.

- Vertragsversion: `2.0`
- Template: `MASTER_GRIDLENS` `2.0.0`

Der Offline-Python-Loader liest den YAML-Vertrag. Die eigenständige
PowerFactory-Erweiterung deklariert die von der MRT erwarteten Tabellen direkt
in `powerfactory/gridlens_report.py`. Tests vergleichen ihre Felder mit den
nativen MRT-Datenquellen.

## Datenquellen

| Datenquelle | Kardinalität | Zweck |
|---|---:|---|
| `ScriptedReportMeta` | genau 1 | Studie, Modell und Versionen |
| `ScriptedModelQuality` | viele | vorgelagerte QA-Ergebnisse |
| `ScriptedScenarios` | viele | Szenarien und Referenzkennzeichen |
| `ScriptedOutages` | viele | Schalthandlungen je Szenario |
| `ScriptedScenarioMatrix` | viele | Elementzustand je Szenario |
| `ScriptedLineStatistics` | viele | Leitungsstatistik |
| `ScriptedTransformerStatistics` | viele | Transformatorstatistik |
| `ScriptedVoltageStatistics` | viele | Spannungsstatistik |
| `ScriptedLineLoadingBars` | viele | Balkendiagramm Leitungsbelastung |
| `ScriptedTransformerLoadingBars` | viele | Balkendiagramm Transformatorbelastung |
| `ScriptedVoltageMagnitudeBars` | viele | Balkendiagramm Spannungsbetrag |
| `ScriptedVoltageAngleBars` | viele | Balkendiagramm Spannungswinkel |
| `ScriptedReferenceComparison` | viele | Szenario gegen Referenz |
| `ScriptedScenarioComparison` | viele | Kennzahlen je Szenario |
| `ScriptedRankings` | viele | vorsortierte Ranglisten |
| `ScriptedRelevantTimePoints` | viele | fachlich relevante Zeitpunkte |
| `ScriptedPlots` | viele | ein Datensatz je Diagramm |
| `ScriptedPlotData` | viele | Zeitreihenpunkte je `plot_id` |

Die vollständige Feldliste und Pflichtfeldkennzeichnung stehen ausschließlich
im Vertrag.

## Konventionen

- PowerFactory ergänzt bei `CreateTable("LineStatistics")` automatisch das
  Präfix `Scripted`; die MRT fragt `ScriptedLineStatistics` ab.
- Tabellenzeitstempel sind vorformatierte Strings. Diagrammzeitstempel sind
  numerische Stunden ab Simulationsbeginn.
- Auslastung ist eine Zahl in Prozent; `91.4` bedeutet `91.4 %`.
- Spannung wird in p.u. ausgegeben.
- Auslastungsdifferenzen sind Prozentpunkte (`%-Pkt.`).
- Rundung erfolgt zentral in `gridlens/report_model/formatting.py`.
- `ScriptedPlots` und `ScriptedPlotData` sind über `plot_id` verbunden.

`validate_payload()` prüft Tabellen, Felder und Datentypen. Numerische Strings
werden von der PowerFactory-Erweiterung vor Statistik und nativem Schreibaufruf
eindeutig in `int` oder `float` umgewandelt.

Optionale Felder können innerhalb Version 2.0 ergänzt werden. Entfernen,
Umbenennen oder Typänderungen erfordern einen neuen Vertrag und Versionswechsel.
