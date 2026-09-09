"""GridLens-Laufzeitpaket fuer PowerFactory 2026.

Die Einstiegsdatei gridlens_report.py importiert ausschliesslich aus diesem
Paket. Das Re-Export haelt die Testschnittstelle stabil.
"""

from .config import (
    CLASS_CATEGORIES, DATA_CONTRACT_VERSION, HOST_TABLE_PREFIX, LOADING_MAX,
    MAX_BAR_ITEMS, MAX_CASES, MAX_PLOTS, MAX_PLOT_POINTS, PUBLISHER_VERSION,
    RESULT_FILE_NAME, SCAN_SCENARIOS, SCAN_VARIATIONS, SNAPSHOT_PREFIX,
    TEMPLATE_NAME, TEMPLATE_VERSION, TIME_UNIT_FALLBACK, TOP_N, VARIABLES,
    VOLTAGE_MAX, VOLTAGE_MIN,
)
from .entry import main
from .payload import (
    active_scenario, apply_reference, bar_label, build_cases_payload,
    build_payload, converged, critical_keys, decimal_comma, empty_payload,
    find_reference, has_time_variation, is_critical, maximum_absolute,
    network_elements, sampled_plot_points, scenario_result, voltage_deviation,
)
from .pfutil import (
    class_name, finite_number, object_description, object_id, object_key,
    object_name, result_category, result_value, safe_attr,
)
from .publish import coerce_value, publish_report, validate_payload
from .results import (
    collect_series, percentile95, result_objects, select_result,
    statistics, supported_column_count, voltage_level,
)
from .tables import FIELD_TYPES, TABLES
from .timeaxis import (
    format_clock, format_time, format_time_step, normalize_time_unit,
    time_column, time_in_hours,
)

__all__ = [
    "CLASS_CATEGORIES", "DATA_CONTRACT_VERSION", "FIELD_TYPES",
    "HOST_TABLE_PREFIX", "LOADING_MAX", "MAX_BAR_ITEMS", "MAX_CASES",
    "MAX_PLOTS", "MAX_PLOT_POINTS", "PUBLISHER_VERSION", "RESULT_FILE_NAME",
    "SCAN_SCENARIOS", "SCAN_VARIATIONS", "SNAPSHOT_PREFIX", "TABLES",
    "TEMPLATE_NAME", "TEMPLATE_VERSION", "TIME_UNIT_FALLBACK", "TOP_N",
    "VARIABLES", "VOLTAGE_MAX", "VOLTAGE_MIN", "class_name", "finite_number",
    "format_clock", "format_time", "format_time_step", "normalize_time_unit",
    "object_description", "object_id", "object_key", "object_name",
    "result_category", "result_value", "safe_attr", "time_column",
    "time_in_hours", "coerce_value", "publish_report",
    "validate_payload", "collect_series", "percentile95",
    "result_objects", "select_result", "statistics",
    "supported_column_count", "voltage_level", "main",
    "active_scenario", "apply_reference", "bar_label", "build_cases_payload",
    "build_payload", "converged", "critical_keys", "decimal_comma",
    "empty_payload", "find_reference", "has_time_variation", "is_critical",
    "maximum_absolute", "network_elements", "sampled_plot_points",
    "scenario_result", "voltage_deviation",
]
