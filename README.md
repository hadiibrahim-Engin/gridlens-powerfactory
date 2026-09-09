# OutageLens / GridLens

Das vollständige Zielbild, der aktuelle Implementierungsstand und der Weg vom
Netzmodell bis zum PDF stehen in [`BIG_PICTURE.md`](BIG_PICTURE.md).

Dieses Repository enthält einen direkt in PowerFactory 2026 verwendbaren
Auto-Report. Die beiden Laufzeitdateien liegen unter [`powerfactory/`](powerfactory):

- [`MASTER_GRIDLENS.mrt`](powerfactory/MASTER_GRIDLENS.mrt) – native
  Stimulsoft-Vorlage mit eingebettetem DIgSILENT-Branding
- [`gridlens_report.py`](powerfactory/gridlens_report.py) – eigenständige
  ComPython-Erweiterung für das aktive Study Case und dessen vorhandenes `ElmRes`
- [`Installations- und Testanleitung`](powerfactory/README.md)

Das PowerFactory-Skript liest keine Mock-Payload und keine externe Schema-Datei.
Es startet keine Berechnung. Es bereitet die vorhandenen Leitungs-, Trafo-,
Spannungsbetrags- und Spannungswinkelergebnisse im Speicher auf und
veröffentlicht sie als 18 `Scripted*`-Tabellen für die MRT. Die
Produktionsvorlage 2.0 trennt jedes fachliche Thema auf eine eigene Seite und
enthält Balkendiagramme für die maßgebenden Netzgrößen.

## Was ist `gridlens/`?

`gridlens/` ist eine PowerFactory-unabhängige Entwicklungsbibliothek aus der
früheren Prototypenphase. Sie normalisiert externe Datensätze und enthält
Statistik-, Ranking-, Vertrags- und Testlogik. PowerFactory importiert diesen
Ordner nicht; für den direkten Reportlauf werden ausschließlich die beiden
Dateien in `powerfactory/` kopiert.

Die Bibliothek bleibt im Repository als geprüfte Referenz für eine spätere
Mehrszenario-Auswertung. Der neue aktive-Modell-Publisher funktioniert ohne sie
und ohne zusätzliche Python-Pakete.

## Verifikation

Die MRT wurde mit Stimulsoft 2026.3.3 geladen, mit Testdaten auf 13 Seiten
gerendert und visuell geprüft. Für den Publisher werden die interne
Tabellendeklaration, `ElmRes`-Auswertung, native `IntReport`-Aufrufe,
SQL-Datenquellen und eingebetteten Branding-Assets automatisiert geprüft.

Der verbleibende Systemtest muss in deinem PowerFactory-2026-Build erfolgen,
weil nur dort der reale ComPython-Lifecycle und die interne SQLite-Verbindung
verfügbar sind.
