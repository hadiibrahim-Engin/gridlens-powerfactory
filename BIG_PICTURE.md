# GridLens – Big Picture

Stand: **28. September 2026** · Publisher `5.2.0` · MRT `3.2.0` · Datenvertrag `3.2`

GridLens erzeugt in DIgSILENT PowerFactory 2026 einen Bericht zur technischen
Vorprüfung geplanter Außerbetriebnahmen (Freischaltungen). Ein Klick auf das
ComPython rechnet das Netz einmal ohne und einmal mit den Freischaltungen,
bewertet jede Freischaltung in ihrem eigenen Zeitfenster und füllt die
Tabellen, aus denen PowerFactory den Bericht rendert.

Der Bericht ist eine technische Vorprüfung. Er ist keine betriebliche Freigabe
und kein Nachweis für N-1-Sicherheit, Schutzkoordination,
Versorgungssicherheit oder sichere elektrische Trennung.

Dieses Dokument erklärt das Zusammenspiel. Die Betriebsanleitung steht in
[`powerfactory/README.md`](powerfactory/README.md), die verbindlichen Regeln
für Änderungen in [`AGENTS.md`](AGENTS.md).

---

## 1. Überblick

```mermaid
flowchart LR
    subgraph PF["PowerFactory 2026 – aktives Projekt"]
        SC["Study Case"]
        QDS["ComStatsim<br/>Zeitraum · Schrittweite · Profile"]
        OUT["Operational Library<br/>IntPlannedout"]
        RES["ElmRes<br/>Variablenauswahl"]
        REP["IntReport"]
        DB[("interne<br/>Reporting-DB")]
    end

    PY["gridlens_report.py<br/>ComPython unter dem IntReport"]
    MRT["MASTER_GRIDLENS.mrt<br/>Stimulsoft-Vorlage"]
    PDF["Bericht / PDF"]

    SC --> QDS
    QDS -- "rechnet REF und OUTAGE" --> PY
    OUT -- "Zeitfenster · Betriebsmittel" --> PY
    RES -- "Vorlage für temporäre Kopien" --> PY
    PY -- "CreateTable · CreateField · SetValue<br/>19 Tabellen" --> REP
    REP --> DB
    DB -- "19 Scripted*-Datenquellen" --> MRT
    MRT --> PDF
```

Ausgeliefert werden **genau zwei Dateien**, immer aus demselben Release:

| Datei | Aufgabe |
|---|---|
| `powerfactory/gridlens_report.py` | Rechnen, Auswerten, Zustand wiederherstellen, Tabellen publizieren. Nur Standardbibliothek und `powerfactory`. |
| `powerfactory/MASTER_GRIDLENS.mrt` | Berichtslayout mit 19 Datenquellen, Logos, Lesezeichen, Inhaltsverzeichnis. |

Zwei Dinge liegen bewusst **außerhalb** der Auslieferung:

- `tools/probe_planned_outages.py` – Read-only-Diagnose für offene
  PowerFactory-Fragen. Siehe Kapitel 8.
- `tests/` – lokale Prüfung, unter anderem der feldgenaue Abgleich zwischen
  Python-Tabellen und MRT-Datenquellen.

Das Skript startet **nicht** selbst das Rendern der Vorlage. Es publiziert die
Tabellen; das Erzeugen des Berichts bleibt ein eigener Schritt in PowerFactory.
So kann ein Fehler bei der Ausgabe keine validierte Berechnung überschreiben.

---

## 2. Ablauf eines Laufs

Die Schrittnummern entsprechen den Logzeilen `[GridLens][NN/7]`.

```mermaid
sequenceDiagram
    autonumber
    participant U as Anwender
    participant GL as gridlens_report.py
    participant Q as ComStatsim
    participant E as ElmRes (temporär)
    participant R as IntReport

    U->>GL: ComPython starten
    Note over GL: 01 STARTUP · 02 CONTEXT/SETTINGS<br/>Zeitraum, iopt_maint, Study Time erfassen
    Note over GL: 03 OUTAGES<br/>Freischaltungen finden und gegen den Zeitraum prüfen

    GL->>Q: iopt_maint = 0 · results → Kopie REF
    Q->>E: 04 CALCULATION REF
    GL->>E: 05 EXTRACTION<br/>Gesamt- und Fensterstatistik

    alt mindestens eine Freischaltung im Zeitraum
        GL->>Q: iopt_maint = 1 · results → Kopie OUTAGE
        Q->>E: 04 CALCULATION OUTAGE<br/>PowerFactory wendet Freischaltungen an
        GL->>E: 05 EXTRACTION
    end

    Note over GL,Q: 06 RESTORE / CLEANUP<br/>iopt_maint, results, Study Time zurück · Kopien löschen · verifizieren
    GL->>R: 07 REPORT<br/>Reset · 19 Tabellen · Heartbeat-Fortschritt
    GL-->>U: Report published successfully
    U->>R: Bericht erzeugen / exportieren
```

Kein Lauf erzeugt Operation Scenarios, Network Variations oder weitere Study
Cases. Gibt es keine Freischaltung im Zeitraum, entfällt `OUTAGE`; der Bericht
wird trotzdem mit QA- und Freischaltungsstatus publiziert.

---

## 3. Wie Freischaltungen wirken

In PowerFactory 2026 ist `IntPlannedout` ein **reines Datenobjekt**. Es hat
kein `Apply`, `Reset` oder `Check`. GridLens schaltet deshalb nichts selbst.
Es setzt am `ComStatsim` die Option `iopt_maint`, die PowerFactory mit
„Planned Outages“ beschriftet, und PowerFactory wendet jede Freischaltung
während der Rechnung **in ihrem eigenen Zeitfenster** an.

Das ist genauer als pauschales Schalten. Beispiel aus dem Abnahmeprojekt
„39 Bus New England System“:

```mermaid
gantt
    title Freischaltungsfenster im simulierten Zeitraum
    dateFormat YYYY-MM-DD HH:mm
    axisFormat %d.%m.
    tickInterval 1day

    section ComStatsim
    Simulierter Zeitraum 96 h :active, p, 2014-01-01 00:00, 2014-01-05 00:00

    section Freischaltungen
    Line 04 - 14 :crit, o1, 2014-01-01 00:00, 2014-01-01 23:59
    Line 15 - 16 :crit, o2, 2014-01-02 00:00, 2014-01-02 23:59
```

Die Freischaltung „Line 04 - 14“ schaltet `Line 08 - 09` und `Line 09 - 39`.
Eine dritte Freischaltung im März läge außerhalb des Zeitraums und würde als
`SKIPPED` geführt, ohne gerechnet zu werden.

Im `OUTAGE`-Lauf fehlen `Line 08 - 09` und `Line 09 - 39` nur am 01.01.,
`Line 15 - 16` nur am 02.01. Am 03. und 04.01. sind `REF` und `OUTAGE`
identisch. Der Name einer Freischaltung ist Freitext – welche Betriebsmittel
sie schaltet, steht ausschließlich in `components`.

Vor der ersten Rechnung ordnet GridLens jede Freischaltung ein:

```mermaid
flowchart TD
    A["IntPlannedout gefunden"] --> B{"outserv = 1<br/>(„Ignored“)?"}
    B -- ja --> S1["SKIPPED<br/>Outage object is disabled"]
    B -- nein --> C{"starttime/endtime<br/>lesbar?"}
    C -- nein --> D["CONSIDERED<br/>+ DIAGNOSTIC-Logzeile<br/>mit Objektoberfläche"]
    C -- ja --> E{"Fenster überlappt<br/>ComStatsim.startTime..endTime?"}
    E -- nein --> S2["SKIPPED<br/>outside the simulated period"]
    E -- ja --> F["CONSIDERED<br/>PowerFactory wendet sie an"]
    D --> G["zählt für den OUTAGE-Lauf"]
    F --> G
```

Weil der Zeitraum am `ComStatsim` steht, geschieht diese Einordnung **vor**
jedem Rechenlauf. Daraus entstehen auch die Zeitfenster, die die Extraktion
für die Bewertung braucht.

---

## 4. Bewertung je Zeitfenster

Die Tabelle **Planned Outages** (Kapitel 4 des Berichts) ist die
Bewertungsgrundlage. Jede Zeile beurteilt **nur ihr eigenes Zeitfenster**.
Eine Statistik über den ganzen Zeitraum wäre für alle Freischaltungen dieselbe
und könnte sie nicht unterscheiden.

```mermaid
flowchart TD
    X["Zeitreihe je Betriebsmittel<br/>vollständig, vor dem Downsampling"] --> W["Statistik je Fenster<br/>min · max · Zeitpunkt"]
    W --> L["höchste Auslastung<br/>Leitungen + Transformatoren"]
    W --> V["Spannungsband<br/>min und max aller Knoten"]
    W --> R["Referenzwert<br/>dasselbe Fenster in REF"]

    L --> Q1{"max > 100 %?"}
    V --> Q2{"min < 0.95 oder<br/>max > 1.05 p.u.?"}

    Q1 -- ja --> Q3{"Spannung auch<br/>verletzt?"}
    Q3 -- ja --> A3["OVERLOAD + VOLTAGE BAND"]
    Q3 -- nein --> A1["OVERLOAD"]
    Q1 -- nein --> Q2
    Q2 -- ja --> A2["VOLTAGE BAND"]
    Q2 -- nein --> A0["NO LIMIT EXCEEDED"]
```

Zusätzlich gibt es `NOT SIMULATED` (übersprungen, Grund in der letzten Spalte)
und `NO RESULT DATA IN WINDOW` (keine Ergebniszeile fällt ins Fenster).

Werte genau auf dem Grenzwert sind keine Verletzung. Zeilen mit Verletzung
werden in derselben roten Hervorhebung wie die Spannungstabellen dargestellt.

Die Tabelle hat sechs Spalten über 17 cm. Illustrative Zeile mit den Fenstern
des Abnahmeprojekts und synthetischen Messwerten:

| Planned outage | Period | Prio | Equipment out of service | Assessment | Worst values inside the window |
|---|---|---|---|---|---|
| Line 04 - 14 | 2014-01-01 00:00 - 23:59 | 1 | Line 08 - 09, Line 09 - 39 | **OVERLOAD** | max 111.0 % on Line 08 - 09 at 2014-01-01 03:00 (reference 74.0 %); voltage 1.000 to 1.000 p.u. |

Der **Referenzwert** ist der Kausalitätsnachweis. Liegt er bereits über
100 %, war das Netz schon ohne Freischaltung zu eng – die Überlastung ist dann
nicht der Freischaltung anzulasten.

---

## 5. Zustand verändern und zurücksetzen

GridLens verändert während eines Laufs genau vier Dinge und stellt alle vier
wieder her, bevor irgendetwas publiziert wird. Ein nicht verifizierter Restore
ist ein harter Fehler.

```mermaid
stateDiagram-v2
    [*] --> Erfasst: Ausgangszustand lesen
    Erfasst --> Verändert: Lauf beginnt
    state Verändert {
        state "iopt_maint = 0 bzw. 1" as Option
        state "results → temporäre ElmRes" as Bindung
        state "Study Time läuft durch den QDS-Zeitraum" as Uhr
        [*] --> Option
        Option --> Bindung
        Bindung --> Uhr
    }
    Verändert --> Restore: Ende oder Fehler (finally)
    state Restore {
        state "Study Time zurück" as R1
        state "iopt_maint zurück" as R2
        state "results zurück" as R3
        state "temporäre ElmRes löschen" as R4
        [*] --> R1
        R1 --> R2
        R2 --> R3
        R3 --> R4
    }
    Restore --> Publizieren: alles verifiziert
    Restore --> Fehler: etwas nicht verifiziert
    Publizieren --> [*]: 19 Tabellen im IntReport
    Fehler --> [*]: nichts publiziert · manuelle Prüfung
```

| Was | Während des Laufs | Danach |
|---|---|---|
| `ComStatsim.iopt_maint` | `0` für REF, `1` für OUTAGE | Ausgangswert, verifiziert |
| `ComStatsim.results` | temporäre Kopie `GridLens_TMP_…` | ursprüngliches `ElmRes`, verifiziert |
| Study Time (`SetTime.cDate/cTime`) | läuft durch den QDS-Zeitraum | Ausgangswert, verifiziert |
| temporäre `ElmRes` | je Fall eine Kopie | gelöscht |

Alle anderen `ComStatsim`-Einstellungen bleiben unberührt. Wird ein Lauf hart
abgebrochen, bevor der Restore greift, kann `ComStatsim.results` auf einer
temporären Kopie `GridLens_TMP_…` stehen bleiben. Der nächste Lauf rechnet
trotzdem mit den hinterlegten Einstellungen: Die Kopie enthält die vollständige
Variablenauswahl, und jeder Fall wird frisch in eine neue Kopie gerechnet.
GridLens meldet das als Warnung, stellt die Bindung danach wieder her und
löscht das Objekt nicht. Aufräumen heißt hier umbenennen, nicht löschen.

---

## 6. Vom Datenvertrag zum Bericht

Python publiziert 19 Tabellen. PowerFactory stellt jedem Namen `Scripted`
voran. Die Namen, Felder und Typen müssen exakt mit den Datenquellen der MRT
übereinstimmen – `tests/test_mrt.py` prüft das feldgenau.

```mermaid
flowchart LR
    subgraph T["19 Tabellen"]
        M["ReportMeta"]
        MQ["ModelQuality"]
        C["Cases"]
        PO["PlannedOutages"]
        CM["CaseMatrix"]
        CC["CaseComparison"]
        B["LineLoadingBars<br/>TransformerLoadingBars<br/>VoltageMagnitudeBars<br/>VoltageAngleBars"]
        RK["Rankings"]
        TP["RelevantTimePoints"]
        PL["TrendLineLoading · TrendTransformerLoading<br/>TrendVoltageMin · TrendVoltageMax"]
        ST["Line-/Transformer-/<br/>VoltageStatistics"]
    end

    M --> K0["Deckblatt · Inhalt · 2 Study Definition"]
    MQ --> K1["1 Model Quality Assurance"]
    C --> K3["3 Calculated Cases"]
    PO --> K4["4 Planned Outages<br/>(Bewertung)"]
    CM --> K5["5 Out-of-Service Matrix"]
    CC --> K6["6 Governing Results · 7 Metric Overview"]
    B --> K8["8–11 Balkendiagramme"]
    RK --> K8
    TP --> K12["12 Relevant Time Points"]
    PL --> K13["13 Time Series"]
    ST --> K14["14 Appendix"]
```

| Berichtskapitel | Datenquelle(n) |
|---|---|
| Deckblatt, Inhaltsverzeichnis, 2 Study Definition | `ReportMeta` |
| 1 Model Quality Assurance | `ModelQuality` |
| 3 Calculated Cases | `Cases` |
| 4 Planned Outages | `PlannedOutages` |
| 5 Out-of-Service Matrix | `CaseMatrix` |
| 6 Governing Results, 7 Metric Overview | `CaseComparison` |
| 8 Line Analysis | `LineLoadingBars` (Diagramm), `Rankings` |
| 9 Transformer Analysis | `TransformerLoadingBars` (Diagramm), `Rankings` |
| 10 Voltage Magnitudes | `VoltageMagnitudeBars` (Diagramm), `Rankings` |
| 11 Voltage Angles | `VoltageAngleBars` (Diagramm und Tabelle) |
| 12 Relevant Time Points | `RelevantTimePoints` |
| 13 Time Series | `TrendLineLoading`, `TrendTransformerLoading`, `TrendVoltageMin`, `TrendVoltageMax` – je ein Diagramm |
| 14 Appendix: Detailed Statistics | `LineStatistics`, `TransformerStatistics`, `VoltageStatistics` |

Jedes Diagramm liest eine **eigene** Tabelle. Bis 5.1.3 hingen die vier
Zeitreihen an einer Master-Detail-Relation `Plots → PlotData`. Die
PowerFactory-Berichtsengine wendet solche Relationen auf Diagramme nicht an und
hat die Punkte aller vier Plots in ein Diagramm gezeichnet: Leitung, Trafo und
zwei Spannungen je Zeitpunkt hintereinander, ein Sägezahn statt der
PowerFactory-Kurve. Seit 5.2.0 gibt es keine Relation mehr, und
`tests/test_mrt.py` verhindert, dass wieder eine eingeführt wird.

Die Zeitreihen zeigen dieselben Werte wie PowerFactory, aber als Linie zwischen
den Zeitpunkten. PowerFactory zeichnet QDS-Ergebnisse als Treppe. An den
Zeitpunkten selbst stimmen beide Darstellungen überein.

Jede Änderung an Feldern erfordert gleichzeitig Code, MRT, Versionsnummern und
Tests. Die Vorlage bindet ausschließlich über Platzhalter; Statuswerte wie
`CONSIDERED` oder `OVERLOAD` sind nirgends fest eingetragen.

---

## 7. Große Netze

Das Skript wurde an einem Netz mit **229 325 Ergebnisreihen** (Study Case
„Europe“) gemessen. Die Laufzeit verteilt sich so:

| Phase | Beobachtet | Ursache / Stand |
|---|---|---|
| QDS-Rechnung REF | 51 s | PowerFactory selbst |
| Extraktion REF | 90 s | `GetColumnValues` ist im Zielbuild nicht nutzbar, daher ein API-Aufruf je Zelle |
| Payload-Aufbau | hing | **behoben in 5.1.2**, siehe unten |
| Publikation | – | Heartbeat-Meldungen je Tabelle |

Der Hänger lag im Aufbau der Anhangstatistik: Für jedes kritische Element
wurde das zugehörige Objekt durch lineares Durchsuchen aller Elemente seiner
Kategorie gesucht, einmal pro Fall. Bei vielen Knoten außerhalb des
Spannungsbands wuchs das quadratisch. Seit 5.1.2 gibt es einen Index je Fall;
gemessen an einem synthetischen Modell derselben Größe mit zwei Fällen und
60 % kritischen Knoten dauert der Aufbau 2,8 s und wächst linear.

```mermaid
xychart-beta
    title "Payload-Aufbau bei 60 % kritischen Knoten (zwei Fälle)"
    x-axis "Reihen je Fall" [6400, 12800, 25600]
    y-axis "Sekunden" 0 --> 5
    line [0.29, 1.19, 4.75]
    line [0.08, 0.13, 0.23]
```

Obere Linie: bis 5.1.1, vervierfacht sich je Verdopplung. Untere Linie: ab
5.1.2.

Grenzen, die bei großen Netzen greifen:

| Konstante | Wert | Wirkung |
|---|---|---|
| `MAX_RESULT_ROWS` | 35 040 | Zeitpunkte je `ElmRes` |
| `MAX_RESULT_CELLS` | 20 000 000 | Zellen je Fall |
| `MAX_RUN_CELLS` | 120 000 000 | Zellen über alle Fälle |
| `MAX_TABLE_ROWS` | 5 000 | Zeilen je publizierter Tabelle; Überschreitung wird als `FAIL` in Model Quality gemeldet |
| `MAX_PLOT_POINTS` | 61 | Punkte je Zeitreihendiagramm |

---

## 8. Was wir über die PowerFactory-2026-API wissen

Diese Fakten wurden im Zielbuild direkt an den Objekten abgefragt – mit
`tools/probe_planned_outages.py`, nicht aus Dokumentation geschlossen.

| Objekt / Attribut | Befund |
|---|---|
| `ComStatsim.iopt_maint` | Beschriftung „Planned Outages“ – der Schalter. Im Feld bestätigt: REF und OUTAGE unterscheiden sich. |
| `ComStatsim.ciopt_maint` | berechnetes Verfügbarkeitsflag, **nicht** der Schalter |
| `ComStatsim.iopt_action`, `iopt_rep` | „Planned Outages: Processing Actions“ bzw. „Output“; von GridLens nicht verändert |
| `ComStatsim.startTime`, `endTime` | simulierter Zeitraum, Epoch-Sekunden |
| `IntPlannedout` | reines Datenobjekt; **kein** `Apply`, `Reset`, `Check`, `IsInStudyTime` |
| `IntPlannedout.starttime`, `endtime` | Epoch-Sekunden |
| `IntPlannedout.components` | die geschalteten Betriebsmittel („Components“) |
| `IntPlannedout.outserv` | „Ignored“ |
| `SetTime.cDate`, `cTime` | **Strings**, Format `YYYYMMDD` und `HHMMSS` |
| implizite QDS-Zeitskala (`ElmRes`, Spalte −1) | Einheit `s`, aber **absolute** Epoch-Sekunden |
| `DataObject.GetAttributes()` | wirft; Attributnamen kommen über `dir()` |
| `GetAttributeDescription(name)` | liefert PowerFactorys eigene Beschriftung – der sicherste Weg, eine Option zu identifizieren |

Arbeitsweise bei neuen Fragen: erst die Probe erweitern und einen Lauf im
Zielbuild machen, dann bauen. Raten hat in diesem Projekt zweimal zu Code
geführt, der auf nicht existierende Methoden setzte.

---

## 9. Offene Punkte

- **Fachliche Sichtprüfung des PDF** am Abnahmeprojekt: Hängen die Deltas an
  den Betriebsmitteln aus `components` und nur in deren Fenstern?
- **Extraktionsdauer bei großen Netzen**: 90 s für 229 325 Reihen und drei
  Zeitpunkte, weil jede Zelle einzeln gelesen wird. Ob `GetColumnValues` mit
  einem `IntVec`-Argument im Zielbuild schneller ist, ist eine Frage für die
  Probe.
- **Anhangtabellen bei großen Netzen**: Werden mehr als 5 000 Zeilen erzeugt,
  wird abgeschnitten – derzeit nach Pfad sortiert, nicht nach Schwere. Bei
  großen Netzen zeigt der Anhang damit eine beliebige Auswahl.
- **Layout der Freischaltungstabelle** mit echten, langen Betriebsmittelnamen.
- Die vollständige Abnahmematrix steht in
  [`powerfactory/README.md`](powerfactory/README.md).
