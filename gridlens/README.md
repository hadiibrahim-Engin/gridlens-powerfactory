# GridLens-Datenaufbereitung

Dieses optionale Entwicklungspaket verarbeitet externe, bereits berechnete
Ergebnisdatensätze. Es normalisiert Eingabedaten, prüft sie und berechnet
Statistiken und Vergleiche. Der aktive PowerFactory-Publisher importiert dieses
Paket nicht; er enthält seinen direkten `ElmRes`-Pfad selbst.

GridLens bewertet keine Freischaltung. Es erzeugt keine Aussagen wie
`zulässig`, `unzulässig`, `sicher` oder `unsicher`.

## Aufbau

```text
gridlens/
├── contracts/               Eingabe- und Reportvertrag
├── adapters/                Rohdaten zum kanonischen Modell
├── canonical.py             kanonisches Datenmodell
├── processing/              Validierung, Statistik, Vergleich und Ranking
├── report_model/            Verarbeitungsergebnis zum Report-Payload
├── powerfactory_reporting/  IntReport-Bridge
├── mock/                    synthetische Testdaten und Export
├── tests/                   Python-Tests
└── docs/                    Architektur, Verarbeitung und Datenvertrag
```

## Installation und Tests

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

## Payload erzeugen

```python
from gridlens.mock import build_dataset, FIXED_GENERATION_DATE
from gridlens.processing import run
from gridlens.report_model import build_report_payload

payload = build_report_payload(
    run(build_dataset()), generation_date=FIXED_GENERATION_DATE
)
```

Für echte Daten wird `build_dataset()` durch einen `RecordAdapter` über die
vorbereiteten eigenen Datensätze ersetzt. Das Ergebnis kann als JSON gespeichert
oder direkt mit `publish_report(...)` publiziert werden.

## PowerFactory-Ausgabe

Der portable Einstiegspunkt ist
[`../powerfactory/gridlens_report.py`](../powerfactory/gridlens_report.py). Er
veröffentlicht die 18 Tabellen über `CreateTable`, `CreateField` und `SetValue`.
PowerFactory ergänzt das Präfix `Scripted`; die MRT liest die vollständigen
Tabellennamen über ihre SQLite-Datenquellen.

Der ausführliche Offline-Vertrag steht in `contracts/report-data-v1.yaml`. Die
PowerFactory-Laufzeit hält ihre für die MRT benötigten Tabellenfelder direkt in
`gridlens_report.py`, damit sie ohne zusätzliche Datei funktioniert.

Weitere Details:

- [Architektur](docs/architecture.md)
- [Verarbeitung](docs/processing.md)
- [Report-Datenvertrag](docs/report-data-contract.md)
- [PowerFactory-Einrichtung](../powerfactory/README.md)
