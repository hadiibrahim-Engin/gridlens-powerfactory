# GridLens for PowerFactory 2026

GridLens erstellt direkt in DIgSILENT PowerFactory 2026 einen Bericht zur
technischen Vorprüfung geplanter Außerbetriebnahmen. Die produktive Auslieferung
besteht nur aus zwei gemeinsam zu versionierenden Dateien:

- [`powerfactory/gridlens_report.py`](powerfactory/gridlens_report.py) –
  eigenständiges ComPython-Skript für Berechnung, Auswertung und Publikation
- [`powerfactory/MASTER_GRIDLENS.mrt`](powerfactory/MASTER_GRIDLENS.mrt) –
  native Stimulsoft-Berichtsvorlage

Das Skript verwendet den bereits aktiven Study Case und dessen vorhandenes
`ComStatsim` einschließlich Zeitraum, Zeitschritt, Calculation Options,
Profile und Ergebnisvariablen. Standardmäßig berechnet es `REF` im unveränderten
Anfangszustand und danach genau einen Fall `OUTAGE`, der alle sicher anwendbaren
Planned Outages kombiniert. Es erzeugt keine Operation Scenarios, Network
Variations oder zusätzlichen Study Cases.

Installation, Bedienung, Fehlersuche und die noch erforderliche reale
PowerFactory-2026-Abnahme stehen in
[`powerfactory/README.md`](powerfactory/README.md).

Lokale Prüfung:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
python3 -m py_compile powerfactory/gridlens_report.py
git diff --check
```

Eine bestandene lokale Testsuite ersetzt nicht den realen End-to-End-Test in
PowerFactory 2026. Der Bericht ist keine abschließende betriebliche Freigabe und
kein Nachweis für N-1-Sicherheit, Schutzkoordination, Versorgungssicherheit oder
sichere elektrische Trennung.
