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

PUBLISHER_VERSION = "4.0.0"
TEMPLATE_NAME = "MASTER_GRIDLENS"
TEMPLATE_VERSION = "2.1.0"
DATA_CONTRACT_VERSION = "2.1"

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

# Namenspraefix der Snapshot-Ergebnisobjekte im Study Case.
SNAPSHOT_PREFIX = "GridLens_"
