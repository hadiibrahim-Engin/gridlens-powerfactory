"""Vertrag der 17 Report-Tabellen. Muss zu MASTER_GRIDLENS.mrt passen."""

FIELD_TYPES = {"string": 0, "integer": 1, "number": 2}

# Maximale Zeichenzahl je Textfeld. Bezeichner und Beschriftungen stehen in
# Tabellenzellen und Diagrammlegenden; ueberlange Werte verengen die Tabelle
# oder zerstoeren das Layout. Freitext darf laenger sein. Wird gekuerzt, haengt
# der Publisher ein stabiles Kuerzel an, damit zwei verschiedene lange Namen
# im Bericht verschieden bleiben.
MAX_LABEL_LENGTH = 80
MAX_TEXT_LENGTH = 500

_LABEL_SUFFIXES = ("_id", "_name", "_label", "_type", "_level", "_time")
_LABEL_FIELDS = (
    "unit", "variable", "status", "reason", "action", "timestamp",
    "metric_name", "check_name", "ranking_type", "simulation_status",
    "simulation_start", "simulation_end", "simulation_time_step",
    "generation_date", "assessment_status",
)


def text_limit(field):
    """Return the maximum length allowed for one string field."""
    if field in _LABEL_FIELDS or field.endswith(_LABEL_SUFFIXES):
        return MAX_LABEL_LENGTH
    return MAX_TEXT_LENGTH

TABLES = (
    ("ScriptedReportMeta", (
        ("study_id", "string"), ("study_name", "string"),
        ("study_description", "string"), ("model_name", "string"),
        ("model_version", "string"), ("simulation_start", "string"),
        ("simulation_end", "string"), ("simulation_time_step", "string"),
        ("generation_date", "string"), ("template_name", "string"),
        ("template_version", "string"), ("data_contract_version", "string"),
        ("result_name", "string"), ("assessment_scope", "string"),
        ("assessment_status", "string"),
        # Renderflags: sie steuern, ob ein Diagrammband gezeichnet wird. Ohne
        # sie zeichnet Stimulsoft ein leeres Diagramm, das wie ein Messergebnis
        # ohne Verletzung aussieht statt wie eine fehlende Datenreihe.
        ("has_line_bars", "string"), ("has_transformer_bars", "string"),
        ("has_voltage_bars", "string"), ("has_angle_bars", "string"),
    )),
    ("ScriptedModelQuality", (
        ("check_id", "string"), ("check_name", "string"),
        ("status", "string"), ("message", "string"),
        ("affected_element", "string"),
    )),
    ("ScriptedScenarios", (
        ("scenario_id", "string"), ("scenario_name", "string"),
        ("is_reference", "integer"), ("description", "string"),
        ("simulation_status", "string"), ("simulation_start", "string"),
        ("simulation_end", "string"),
    )),
    ("ScriptedOutages", (
        ("scenario_id", "string"), ("outage_id", "string"),
        ("element_id", "string"), ("element_name", "string"),
        ("element_type", "string"), ("start_time", "string"),
        ("end_time", "string"), ("action", "string"),
    )),
    ("ScriptedScenarioMatrix", (
        ("element_id", "string"), ("element_name", "string"),
        ("element_type", "string"), ("scenario_id", "string"),
        ("is_out_of_service", "integer"), ("status_label", "string"),
    )),
    ("ScriptedLineStatistics", (
        ("scenario_id", "string"), ("element_id", "string"),
        ("element_name", "string"), ("voltage_level", "string"),
        ("min_loading", "number"), ("max_loading", "number"),
        ("mean_loading", "number"), ("p95_loading", "number"),
        ("time_of_min_loading", "string"),
        ("time_of_max_loading", "string"),
        ("reference_max_loading", "number"),
        ("delta_max_loading", "number"),
    )),
    ("ScriptedTransformerStatistics", (
        ("scenario_id", "string"), ("element_id", "string"),
        ("element_name", "string"), ("voltage_level", "string"),
        ("min_loading", "number"), ("max_loading", "number"),
        ("mean_loading", "number"), ("p95_loading", "number"),
        ("time_of_max_loading", "string"),
        ("reference_max_loading", "number"),
        ("delta_max_loading", "number"),
    )),
    ("ScriptedVoltageStatistics", (
        ("scenario_id", "string"), ("element_id", "string"),
        ("element_name", "string"), ("voltage_level", "string"),
        ("min_voltage", "number"), ("max_voltage", "number"),
        ("mean_voltage", "number"), ("time_of_min_voltage", "string"),
        ("time_of_max_voltage", "string"),
        ("reference_min_voltage", "number"),
        ("reference_max_voltage", "number"),
        ("delta_min_voltage", "number"), ("delta_max_voltage", "number"),
    )),
    ("ScriptedLineLoadingBars", (
        ("rank", "integer"), ("scenario_id", "string"),
        ("element_id", "string"), ("element_name", "string"),
        ("bar_label", "string"),
        ("voltage_level", "string"), ("max_loading", "number"),
        ("unit", "string"), ("event_time", "string"),
    )),
    ("ScriptedTransformerLoadingBars", (
        ("rank", "integer"), ("scenario_id", "string"),
        ("element_id", "string"), ("element_name", "string"),
        ("bar_label", "string"),
        ("voltage_level", "string"), ("max_loading", "number"),
        ("unit", "string"), ("event_time", "string"),
    )),
    ("ScriptedVoltageMagnitudeBars", (
        ("rank", "integer"), ("scenario_id", "string"),
        ("element_id", "string"), ("element_name", "string"),
        ("bar_label", "string"),
        ("voltage_level", "string"), ("min_voltage", "number"),
        ("max_voltage", "number"), ("mean_voltage", "number"),
        ("deviation", "number"), ("status_label", "string"),
        ("unit", "string"),
    )),
    ("ScriptedVoltageAngleBars", (
        ("rank", "integer"), ("scenario_id", "string"),
        ("element_id", "string"), ("element_name", "string"),
        ("bar_label", "string"),
        ("voltage_level", "string"), ("min_angle", "number"),
        ("max_angle", "number"), ("mean_angle", "number"),
        ("max_abs_angle", "number"), ("angle_span", "number"),
        ("event_time", "string"), ("unit", "string"),
    )),
    ("ScriptedScenarioComparison", (
        ("metric_key", "string"), ("metric_name", "string"),
        ("unit", "string"), ("scenario_id", "string"),
        ("metric_value", "number"), ("element_id", "string"),
        ("element_name", "string"),
    )),
    ("ScriptedRankings", (
        ("ranking_type", "string"), ("rank", "integer"),
        ("scenario_id", "string"), ("element_id", "string"),
        ("element_name", "string"), ("element_type", "string"),
        ("metric_name", "string"), ("metric_value", "number"),
        ("unit", "string"), ("reference_value", "number"),
        ("delta_value", "number"), ("event_time", "string"),
    )),
    ("ScriptedRelevantTimePoints", (
        ("timestamp", "string"), ("scenario_id", "string"),
        ("reason", "string"), ("element_id", "string"),
        ("element_name", "string"), ("metric_name", "string"),
        ("metric_value", "number"), ("unit", "string"),
    )),
    ("ScriptedPlots", (
        ("plot_id", "string"), ("plot_title", "string"),
        ("scenario_id", "string"), ("element_id", "string"),
        ("element_name", "string"), ("variable", "string"),
        ("unit", "string"),
    )),
    ("ScriptedPlotData", (
        ("plot_id", "string"), ("scenario_id", "string"),
        ("series_role", "string"), ("timestamp", "number"),
        ("value", "number"),
    )),
)



# Pflichtfelder je Tabelle. Ein Pflichtfeld darf niemals fehlen, None sein
# oder - bei Textfeldern - nur aus Leerzeichen bestehen.
#
# Bewusst NICHT Pflicht sind alle reference_*- und delta_*-Felder sowie
# Zeitstempel einzelner Extrema: fehlt der Vergleichspartner, bleibt die
# Zelle leer. Ein erfundener Wert 0.0 waere eine falsche Aussage.
REQUIRED_FIELDS = {
    "ScriptedReportMeta": (
        "study_id", "study_name", "model_name", "model_version",
        "generation_date", "template_name", "template_version",
        "data_contract_version", "result_name", "assessment_scope",
        "assessment_status", "has_line_bars", "has_transformer_bars",
        "has_voltage_bars", "has_angle_bars",
    ),
    "ScriptedModelQuality": ("check_id", "check_name", "status", "message"),
    "ScriptedScenarios": (
        "scenario_id", "scenario_name", "is_reference", "simulation_status",
    ),
    "ScriptedOutages": (
        "scenario_id", "outage_id", "element_id", "element_name",
        "element_type", "action",
    ),
    "ScriptedScenarioMatrix": (
        "element_id", "element_name", "element_type", "scenario_id",
        "is_out_of_service", "status_label",
    ),
    "ScriptedLineStatistics": (
        "scenario_id", "element_id", "element_name", "min_loading",
        "max_loading", "mean_loading", "p95_loading",
    ),
    "ScriptedTransformerStatistics": (
        "scenario_id", "element_id", "element_name", "min_loading",
        "max_loading", "mean_loading", "p95_loading",
    ),
    "ScriptedVoltageStatistics": (
        "scenario_id", "element_id", "element_name", "min_voltage",
        "max_voltage", "mean_voltage",
    ),
    "ScriptedLineLoadingBars": (
        "rank", "scenario_id", "element_id", "element_name", "bar_label",
        "max_loading", "unit",
    ),
    "ScriptedTransformerLoadingBars": (
        "rank", "scenario_id", "element_id", "element_name", "bar_label",
        "max_loading", "unit",
    ),
    "ScriptedVoltageMagnitudeBars": (
        "rank", "scenario_id", "element_id", "element_name", "bar_label",
        "min_voltage", "max_voltage", "mean_voltage", "deviation",
        "status_label", "unit",
    ),
    "ScriptedVoltageAngleBars": (
        "rank", "scenario_id", "element_id", "element_name", "bar_label",
        "min_angle", "max_angle", "mean_angle", "max_abs_angle",
        "angle_span", "unit",
    ),
    "ScriptedScenarioComparison": (
        "metric_key", "metric_name", "scenario_id", "metric_value",
    ),
    "ScriptedRankings": (
        "ranking_type", "rank", "scenario_id", "element_id", "element_name",
        "element_type", "metric_name", "metric_value", "unit",
    ),
    "ScriptedRelevantTimePoints": (
        "timestamp", "scenario_id", "reason", "metric_name", "metric_value",
        "unit",
    ),
    # scenario_id ist hier bewusst kein Pflichtfeld: eine Plotdefinition gilt
    # fuer alle Faelle, die Fallzuordnung steht in ScriptedPlotData.
    "ScriptedPlots": (
        "plot_id", "plot_title", "element_id", "element_name", "variable",
        "unit",
    ),
    "ScriptedPlotData": (
        "plot_id", "scenario_id", "series_role", "timestamp", "value",
    ),
}
