# GridLens-Architektur

GridLens beginnt nach der Netzberechnung und bereitet vorhandene Ergebnisse für
den PowerFactory Report Designer auf.

```text
QA + Szenarien + Simulationsergebnisse
                 │
                 ▼
Adapter → Normalisierung → kanonisches Modell → Validierung
                 │
                 ▼
Statistik → Vergleiche → Rankings → relevante Zeitpunkte → Plotauswahl
                 │
                 ▼
Report-Payload → IntReport-Publisher → Scripted*-Tabellen
                 │
                 ▼
PowerFactory-SQLite → MASTER_GRIDLENS.mrt → PDF
```

| Schicht | Ort | PowerFactory-spezifisch |
|---|---|---|
| Adapter | `gridlens/adapters` | Elementklassen und Variablencodes |
| Kanonisches Modell | `gridlens/canonical.py` | nein |
| Verarbeitung | `gridlens/processing` | nein |
| Reportmodell | `gridlens/report_model` | nein |
| IntReport-Bridge | `gridlens/powerfactory_reporting` | native Tabellen-API |
| Portable Erweiterung | `powerfactory/gridlens_report.py` | ComPython-Einstieg |
| Vorlage | `powerfactory/MASTER_GRIDLENS.mrt` | SQLite-Datenquellen und Layout |

Python trägt den gesamten Datenpfad. Die MRT ist die direkt gepflegte
Stimulsoft-XML-Vorlage; ein Generator gehört nicht zum System.

GridLens führt keine Netzrechnung aus, ändert kein Modell und trifft keine
technische Freigabeentscheidung. Es stellt Ausgangszustand, Szenarien,
Unterschiede, Extremwerte, Zeitreihen und Metadaten für die fachliche Beurteilung
durch den Ingenieur dar.

Der Offline-Vertrag liegt unter `gridlens/contracts/report-data-v1.yaml`. Der
eigenständige aktive-Modell-Publisher deklariert dieselben MRT-Tabellen direkt in
`powerfactory/gridlens_report.py`; eine zusätzliche Laufzeitdatei ist nicht nötig.
