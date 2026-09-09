"""Konfiguration des GridLens-Publishers: Grenzwerte, Variablen, Versionen.

Dieses Modul hat keine PowerFactory-Abhaengigkeit.
"""

# Prefer this result object. If it is absent, the populated ElmRes with the most
# supported columns in the active study case is selected automatically.
RESULT_FILE_NAME = "Quasi-Dynamic Simulation AC.ElmRes"

# PowerFactory exposes CreateTable("Name") to the designer as ScriptedName.
HOST_TABLE_PREFIX = "Scripted"
TOP_N = 10
MAX_PLOTS = 4
MAX_PLOT_POINTS = 61
MAX_BAR_ITEMS = 12

# Only violations of these limits are included in the technical result tables.
# The comparison is strict, matching the supplied DIgSILENT verification report.
LOADING_MAX = 100.0
VOLTAGE_MIN = 0.95
VOLTAGE_MAX = 1.05

# Used only when the ElmRes time column has no unit. QDS results commonly expose
# hours; change this to "s", "min" or "d" for another project convention.
TIME_UNIT_FALLBACK = "h"

PUBLISHER_VERSION = "4.1.0"
TEMPLATE_NAME = "MASTER_GRIDLENS"
TEMPLATE_VERSION = "2.2.0"
DATA_CONTRACT_VERSION = "2.2"

# Candidate variables are ordered by preference. Add a project-specific result
# variable here when the active ElmRes uses another PowerFactory identifier.
VARIABLES = {
    "line": ("c:loading", "m:loading"),
    "transformer": ("c:loading", "m:loading"),
    "voltage": ("m:u", "m:u1"),
    "voltage_angle": ("m:phiu", "m:phiu1"),
}
CLASS_CATEGORIES = {
    "ElmLne": ("line",),
    "ElmTr2": ("transformer",),
    "ElmTr3": ("transformer",),
    "ElmTerm": ("voltage", "voltage_angle"),
}

# The MRT expects these tables and fields. Keeping the declaration here makes

# Discovery des Runner-Modus. Varianten sind standardmaessig aus: sie tragen in
# realen Projekten meist Modellierungstiefe oder Ausbaustufen und keine
# Schaltzustaende (Spezifikation, Abschnitt 11.1).
SCAN_SCENARIOS = True
SCAN_VARIATIONS = False

# Obergrenze der Rechenlaeufe einschliesslich REF.
MAX_CASES = 12

# Groessengrenzen eines einzelnen ElmRes je Fall. Sie begrenzen Laufzeit und
# Speicher und machen ein zu grosses Ergebnis zu einem sichtbaren Fehler statt
# zu einem blockierten PowerFactory. MAX_RESULT_ROWS entspricht einem Jahr in
# 15-Minuten-Schritten; MAX_RESULT_CELLS begrenzt Zeilen mal ausgewertete
# Reihen. Fuer groessere Studien hier bewusst anheben und die Laufzeit messen
# (powerfactory/tools/benchmark_reader.py).
# Gemessen mit powerfactory/tools/benchmark_reader.py auf einem Entwickler-
# rechner (CPython 3.13, spaltenweises Lesen): rund 1,7 s je 1.000.000 Zellen.
# Der Leser haelt je Reihe nur die Diagrammstichprobe (MAX_PLOT_POINTS), nicht
# die volle Zeitreihe; der Speicher waechst daher mit der Zahl der Reihen und
# nicht mit der Zahl der Zeitschritte. Massgeblich ist die Laufzeit.
# 20.000.000 Zellen je Fall entsprechen rund 33 s und decken 1.000 Leitungen
# plus 1.000 Knoten ueber ein Jahr in Stundenschritten ab.
MAX_RESULT_ROWS = 35040
MAX_RESULT_CELLS = 20000000

# Der Report haelt alle Faelle eines Laufs gleichzeitig, weil Rangfolgen,
# Referenzdeltas und Diagrammauswahl fallübergreifend gebildet werden. Der
# Vorgabewert entspricht grob 3,5 Minuten Lesezeit und einigen hundert MiB.
MAX_RUN_CELLS = 120000000

# Obergrenze der Zeilen je publizierter Tabelle. Balken, Rangfolgen und
# Diagramme sind bereits durch MAX_BAR_ITEMS, TOP_N und MAX_PLOTS begrenzt;
# die Anhangstabellen und die Szenariomatrix waren es nicht. Ein Modell mit
# sehr vielen Grenzwertverletzungen erzeugt sonst einen unbrauchbar langen
# Bericht. Eine Kuerzung ist nie still: sie erscheint als FAIL in
# ScriptedModelQuality.
MAX_TABLE_ROWS = 5000

# Namenspraefix der Snapshot-Ergebnisobjekte im Study Case.
SNAPSHOT_PREFIX = "GridLens_"
