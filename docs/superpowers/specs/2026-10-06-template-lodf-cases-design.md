# GridLens: Einzel-Cases, LODF und Template-Layout

Stand: 6. Oktober 2026 · Branch `feat/template-lodf-cases` · Publisher `7.0.0` · MRT `5.0.0` · Datenvertrag `5.0`

Alle Bezeichner, Logs und Berichtstexte bleiben Englisch (AGENTS.md); dieses Dokument ist Betriebsdokumentation.

## Ziel

1. GridLens rechnet `REF` ohne Außerbetriebnahmen und danach **jede Außerbetriebnahme einzeln als eigenen Case**,
   anschließend wird jeder Case mit `REF` verglichen.
2. Die **LODF** aus PowerFactorys *Sensitivities / Distribution Factors* (`ComVstab`) zeigt je Außerbetriebnahme, welche
   Leitung sich wie stark ändert. Das Ranking im Bericht richtet sich danach. Vorbild: `nahriva-grid-analysis`
   (`powerfactory/lodf.py`, `docs/LODF.md`, `analysis_worker._run_cases`).
3. Der Bericht folgt dem Template `GridLens_Template_Optimiert_v2.pdf`.
4. Alles wird nach `main` übernommen (lokal; ein Push nur nach Freigabe).

## 1. Rechenablauf: ein Lauf je Außerbetriebnahme

- `REF`: `iopt_maint=0` wie heute.
- Je Außerbetriebnahme im Zeitraum (`CONSIDERED`) ein Case `OUT01 … OUTnn`: `iopt_maint=1`, an **allen anderen**
  `IntPlannedout` wird `outserv=1` gesetzt, an der geprüften bleibt `outserv=0`. PowerFactory wendet nur sie an.
  GridLens ruft weiterhin kein `Apply`/`Reset`/`Check` auf.
- Jeder Case bekommt ein eigenes temporäres `ElmRes` (wie bisher), wird sofort reduziert (Statistik je Element, Statistik
  im eigenen Zeitfenster, Zeitreihen) und freigegeben.
- Wiederherstellung am Ende **und nach jedem Fehler**: `iopt_maint`, alle `outserv`, `ComStatsim.results`, Studienzeit,
  temporäre Results. Jeder Wert wird nach dem Zurückschreiben gelesen und verglichen; ein Rest führt zu einem Fehler mit
  dem Soll- und dem Ist-Wert (`StateGuard`, aus nahriva-grid-analysis `pf_state.py`).
- Läuft ein Case nicht (Rückgabecode ≠ 0), wird er als `NOT EVALUATED` mit Grund geführt, die übrigen Cases laufen weiter
  und der Bericht erscheint mit Warnung in der QA; der Zustand wird trotzdem wiederhergestellt.
- Vorteil: überlappende Zeitfenster beeinflussen sich nicht mehr; jede Zeile gehört genau einer Außerbetriebnahme.
- Budget: `MAX_RUN_CELLS` gilt über alle Cases; Rohreihen werden je Case verworfen.

**Änderung an AGENTS.md:** Regel 4 und „Aktueller Produktionspfad“ nennen künftig `iopt_maint` an `ComStatsim` und
zeitweise `outserv` an `IntPlannedout` (vollständig wiederhergestellt). „Genau ein OUTAGE-Lauf“ entfällt.

## 2. LODF

- Der Code von `lodf.py` kommt **inline** in `gridlens_report.py` (Auslieferung bleibt: ein Skript, eine MRT).
- Einmal vor dem ersten Rechenlauf: eigene Contingency Analysis (`ComSimoutage`) mit einer `ComOutage` je Außerbetriebnahme
  (`SetObjs` mit den geschalteten Zweigen; nur `ElmLne`, `ElmTr2`, `ElmTr3`, `ElmCoup`), `ComVstab` mit `pComSimoutage`,
  `isContSens=1`, `calcLodf=1`, `lodflim=0`; danach alles zurück und verifiziert; die Hilfsobjekte werden gelöscht.
- Ergebnis: je Außerbetriebnahme und Leitung ein vorzeichenbehafteter Bruchteil am bus1-Ende (73,6 % → 0,736).
- Grenzen (wie `docs/LODF.md`): nur Leitungen werden überwacht; ein Contingency ohne Lösung (z. B. Generator
  abgeschnitten) hat keine LODF; eine Außerbetriebnahme ohne Zweig hat keine LODF. In beiden Fällen steht der Grund im
  Bericht.
- **Line Impact Ranking:** je Außerbetriebnahme die zehn Leitungen mit dem größten |LODF|; je Zeile LODF in %, `REF`-
  Maximum, Case-Maximum und gemessenes Delta in pp. Ausgeschaltete Leitungen stehen als `n/a`.
- Fehlt die LODF, steht im Bericht der Grund, und das Ranking fällt **sichtbar beschriftet** auf „ranked by measured
  delta“ zurück. Ein LODF-Fehler stoppt den Lauf nicht.
- Offen und im README zu vermerken: Der Ablauf ist in nahriva-grid-analysis nur als Probe in PowerFactory geprüft, nicht
  Ende-zu-Ende; in GridLens ebenfalls nur gegen eine PowerFactory-Attrappe getestet.

## 3. Bericht (Template)

Reihenfolge und Inhalt folgen dem Template; **Anhang C (Generatoren) entfällt**.

| Seite | Inhalt | Datenquelle |
|---|---|---|
| Titel | Titel, Untertitel, Metadatenblock, Banner `PRE-ASSESSMENT - NOT AN OPERATIONAL RELEASE` | `ScriptedReportMeta` |
| Contents | klickbares Inhaltsverzeichnis, passt auf eine Seite | Bookmarks |
| Model Quality Assurance | Check / Status / Details / Equipment | `ScriptedModelQuality` |
| Calculated Cases and Planned Outages | je Case Zeitraum, Priorität, Betriebsmittel, Bewertung, schlimmste Werte | `ScriptedCases` |
| Reference Case – Base State | Kreise Leitungen/Transformatoren (bis 80 %, 80–100 %, über 100 %), Tabelle der Elemente über 100 % in `REF` | `ScriptedOverview…`, `ScriptedReferenceExceeded` |
| Metric View | Tabelle je Case, zwei Kennzahlenkarten | `ScriptedCaseMetrics` |
| Case Comparison | drei Linienplots: Leitungen > 100 %, Transformatoren > 100 %, Knoten außerhalb des Bandes | `ScriptedCaseCounts` |
| Radar Comparison | Radar mit einer Serie je Case, darunter Zähltabelle | `ScriptedCaseCounts` |
| Top 10 Maximum Loaded Lines | Balken, 100-%-Linie | `ScriptedLineLoadingBars` |
| Most Loaded Line / Largest Delta | je ein Zeitplot mit `REF` und allen Cases | `ScriptedTrendMostLoaded`, `ScriptedTrendLargestDelta` |
| Line Impact Ranking | Top 10 je Case nach |LODF|, Erläuterung | `ScriptedLodfRanking` |
| Top 10 Strongly Loaded Lines by Case | Top-10-Tabelle je Case | `ScriptedTopLinesByCase` |
| Appendix Overview, A, B, D | Leitungen, Transformatoren, Knotenspannungen (Minimum) je Case | `ScriptedAppendixLine/Transformer/Voltage` |

Konventionen:

- **Spalten:** `REF` plus bis zu **6** Cases je Tabellenblock; weitere Cases folgen als neue Blöcke (Gruppen-Header-Band
  über `block`). Die Spaltenüberschriften stehen als `h1…h6` in jeder Datenzeile, sodass keine Data Relation nötig ist.
- **Diagramme:** keine Data Relation. Jedes Diagramm liest eine eigene Tabelle. Festes Farbschema je Spalten-Slot
  (`REF` grau, danach feste Palette); kein kulturabhängiges Dezimalzeichen auf Achsen (AGENTS.md, Datenvertrag).
- Mängel des Templates, die nicht übernommen werden: „Page 0“ auf der Titelseite, Inhaltsverzeichnis läuft in die
  Fußzeile, überlagerte Titel auf den Seiten Reference und Radar, Rohname `element_name` als Spaltenkopf, der Satz
  „Linienplot statt Radar“ (beide Seiten bleiben). **„SYNTHETIC DUMMY DATA“ entfällt** in Fußzeile und Banner; die Fußzeile
  lautet `PRE-ASSESSMENT | NOT FOR OPERATIONAL USE`.
- Transformatoren und Spannung bleiben über Kreise, Kennzahlen, Radar, Anhang B und D erhalten. Die heutigen Kapitel
  „Transformer Loading“, „Voltage“ und „Time Series“ entfallen, weil das Template sie nicht enthält.
- Bewertung (`NEW`, `WORSENED`, `PRE-EXISTING`, …) und Grenzwerte bleiben unverändert; jeder Case wird gegen `REF`
  gepaart. `assessment` je Case bleibt einer der bekannten Werte.
- `n/a` steht für ausgeschaltete oder fehlende Reihen; es werden keine künstlichen Nullwerte erzeugt.

## 4. Datenvertrag 5.0

Python (`TABLES`) und MRT müssen exakt übereinstimmen. Neu/geändert (Feldlisten stehen als Quelle der Wahrheit im Code):

- `ScriptedCases`: eine Zeile je Case mit `case_order`, `case_name`, Zeitraum, Priorität, Betriebsmittel, Bewertung,
  Detailtext.
- `ScriptedCaseMetrics`, `ScriptedCaseCounts`, `ScriptedReferenceExceeded`, `ScriptedTopLinesByCase`,
  `ScriptedLodfRanking`, `ScriptedAppendixLine`, `ScriptedAppendixTransformer`, `ScriptedAppendixVoltage`,
  `ScriptedTrendMostLoaded`, `ScriptedTrendLargestDelta`.
- Entfallen oder umgebaut: `ScriptedPlannedOutages`, `ScriptedOverview*`, `ScriptedLoadingRanking`,
  `ScriptedLine/TransformerStatistics`, `ScriptedVoltage*`, die vier `ScriptedTrend*`.
- `report.Reset()` läuft weiter genau einmal im erfolgreichen Pfad; Leere Listen werden selbstschließend geschrieben;
  `<ReportFile />` bleibt leer; keine lokalen Pfade.

## 5. Prüfung und Merge

- Lokal: `.venv/bin/pytest -q`, `python3 -m py_compile`, `git diff --check`. Neue Tests für Einzel-Case-Ablauf mit
  Wiederherstellung auch im Fehlerfall, LODF-Ablauf gegen eine Attrappe, Datenvertrag, Spaltenblöcke, MRT/Tabellen-Abgleich,
  englische Texte, Ausschluss von „SYNTHETIC“.
- Lokal gerendert mit Stimulsoft 2025.3.5 (siehe Memory `stimulsoft-local-verification`) und mit dem Template verglichen;
  die Testversion rendert nur Seite 1 vollständig, deshalb Abschnitt für Abschnitt.
- Es wird **keine** Produktionsfreigabe behauptet: der echte PowerFactory-2026-Test (Einzel-Cases mit `outserv`, LODF im
  Assessment, `ElmRes`-Zeitstempel am Fensterende) steht aus und wird in `powerfactory/README.md` vermerkt.
- Merge: Feature-Branch → `main` lokal; Push nach Rückfrage.
