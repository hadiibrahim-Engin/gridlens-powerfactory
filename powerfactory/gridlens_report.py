"""GridLens single-file runtime for DIgSILENT PowerFactory 2026."""

from __future__ import annotations

import bisect
import getpass
import hashlib
import math
import os
import time
from datetime import datetime

HOST_TABLE_PREFIX = 'Scripted'
TOP_N = 10
MAX_PLOT_POINTS = 200
MAX_VOLTAGE_ROWS = 30
LOADING_MAX = 100.0
# Loading classes and the appendix start here.
LOADING_WARNING = 80.0
# Smaller changes count as unchanged: %-points for loading, p.u. for voltage.
LOADING_DELTA_TOLERANCE = 0.1
VOLTAGE_DELTA_TOLERANCE = 0.001
# The appendix also lists elements that change at least this much.
LOADING_APPENDIX_DELTA = 1.0
VOLTAGE_APPENDIX_DELTA = 0.005
# Permitted voltage band per nominal voltage, in kV:
# (lowest nominal, nominal below which the row applies, minimum, maximum).
# Any other nominal voltage uses VOLTAGE_MIN to VOLTAGE_MAX in p.u.
VOLTAGE_LIMITS_KV = ((300.0, 450.0, 360.0, 420.0), (200.0, 300.0, 198.0, 245.0), (100.0, 150.0, 99.0, 123.0))
VOLTAGE_MIN = 0.95
VOLTAGE_MAX = 1.05
# Below this a node counts as de-energised at that time step, not as a value.
ENERGIZED_MIN_PU = 0.1
TIME_UNIT_FALLBACK = 'h'
PUBLISHER_VERSION = '7.0.0'
TEMPLATE_NAME = 'MASTER_GRIDLENS'
TEMPLATE_VERSION = '5.0.0'
DATA_CONTRACT_VERSION = '5.0'
RUN_REFERENCE_CASE = True
# Only elements whose grid (PowerFactory attribute "Grid", cpGrid) has a name
# containing this text are assessed; every other element in the model is
# foreign network and ignored. An empty string assesses every element.
GRID_NAME_FILTER = 'D7'
VARIABLES = {'line': ('c:loading', 'm:loading'), 'transformer': ('c:loading', 'm:loading'), 'voltage': ('m:u', 'm:u1')}
CLASS_CATEGORIES = {'ElmLne': ('line',), 'ElmTr2': ('transformer',), 'ElmTr3': ('transformer',), 'ElmTerm': ('voltage',)}
MAX_RESULT_ROWS = 35040
MAX_RESULT_CELLS = 20000000
MAX_RUN_CELLS = 120000000
MAX_TABLE_ROWS = 5000
PUBLICATION_LOG_INTERVAL_SECONDS = 5.0
SNAPSHOT_PREFIX = 'GridLens_'

FIELD_TYPES = {'string': 0, 'integer': 1, 'number': 2}
MAX_LABEL_LENGTH = 80
MAX_TEXT_LENGTH = 500
MAX_DIAGNOSTIC_LENGTH = 4000
ABSOLUTE_TIME_THRESHOLD_HOURS = 87600.0
_LABEL_SUFFIXES = ('_id', '_name', '_label', '_type', '_level', '_time')
_LABEL_FIELDS = ('unit', 'variable', 'status', 'reason', 'action', 'timestamp', 'metric_name', 'check_name', 'ranking_type', 'simulation_status', 'simulation_start', 'simulation_end', 'simulation_time_step', 'generation_date', 'assessment_status')

# Lists of names that must stay readable in full.
_LONG_LABEL_FIELDS = ('equipment_name',)

def text_limit(field):
    if field in _LONG_LABEL_FIELDS:
        return MAX_TEXT_LENGTH
    if field in _LABEL_FIELDS or field.endswith(_LABEL_SUFFIXES):
        return MAX_LABEL_LENGTH
    return MAX_TEXT_LENGTH
CASE_SLOTS = 6
SERIES_SLOTS = CASE_SLOTS + 1


def _slot_fields(pattern, kind, first=1, last=CASE_SLOTS):
    return tuple((pattern.format(index), kind) for index in range(first, last + 1))


# Tables that compare REF with up to CASE_SLOTS cases side by side. Further cases
# continue in the next block; the headers travel with every row so that no data
# relation is needed.
MATRIX_FIELDS = (
    (("block", "integer"), ("row_order", "integer"), ("element_name", "string"), ("ref_text", "string"))
    + _slot_fields("c{}_text", "string") + _slot_fields("h{}_name", "string") + (("col_count", "integer"), ("violation", "integer")))
# Charts that draw REF and up to CASE_SLOTS cases: one fixed series per slot.
SERIES_NAME_FIELDS = _slot_fields("s{}_name", "string", 0)
SERIES_VALUE_FIELDS = _slot_fields("v{}", "number", 0)
TREND_FIELDS = (
    (("time_label", "string"), ("timestamp", "number"), ("element_name", "string"), ("chart_title", "string"),
     ("unit", "string")) + SERIES_NAME_FIELDS + SERIES_VALUE_FIELDS)

TABLES = (
    ("ScriptedReportMeta", (
        ("study_id", "string"), ("study_name", "string"), ("study_description", "string"),
        ("model_name", "string"), ("model_version", "string"), ("simulation_start", "string"),
        ("simulation_end", "string"), ("simulation_time_step", "string"), ("generation_date", "string"),
        ("generated_by", "string"), ("run_mode", "string"), ("template_name", "string"),
        ("template_version", "string"), ("data_contract_version", "string"), ("result_name", "string"),
        ("assessment_scope", "string"), ("assessment_status", "string"), ("voltage_limits", "string"),
        ("has_cases", "string"), ("chart_cases", "string"), ("lodf_text", "string"), ("radar_note", "string"))),
    ("ScriptedModelQuality", (
        ("check_id", "string"), ("check_name", "string"), ("status", "string"), ("message", "string"),
        ("affected_element", "string"))),
    ("ScriptedCases", (
        ("case_order", "integer"), ("case_id", "string"), ("case_name", "string"), ("is_reference", "integer"),
        ("simulation_status", "string"), ("period_text", "string"), ("priority", "integer"),
        ("equipment_name", "string"), ("assessment", "string"), ("assessment_detail", "string"),
        ("violation", "integer"))),
    ("ScriptedCaseMetrics", (
        ("case_order", "integer"), ("case_name", "string"), ("max_line_text", "string"),
        ("max_line_element", "string"), ("largest_delta_text", "string"), ("voltage_range_text", "string"))),
    ("ScriptedKpis", (
        ("highest_text", "string"), ("highest_caption", "string"), ("highest_violation", "integer"),
        ("delta_text", "string"), ("delta_caption", "string"))),
    ("ScriptedPieLines", (("sort_order", "integer"), ("class_label", "string"), ("element_count", "integer"))),
    ("ScriptedPieTransformers", (
        ("sort_order", "integer"), ("class_label", "string"), ("element_count", "integer"))),
    ("ScriptedReferenceExceeded", (
        ("rank", "integer"), ("type_label", "string"), ("element_name", "string"), ("grid_name", "string"),
        ("max_text", "string"))),
    ("ScriptedCaseCounts", (
        ("case_order", "integer"), ("case_name", "string"), ("line_count", "integer"),
        ("transformer_count", "integer"), ("node_count", "integer"))),
    ("ScriptedRadar", (
        (("metric_order", "integer"), ("metric_label", "string"), ("note", "string"))
        + SERIES_NAME_FIELDS + SERIES_VALUE_FIELDS)),
    ("ScriptedLineLoadingBars", (
        ("rank", "integer"), ("element_name", "string"), ("max_value", "number"), ("case_name", "string"))),
    ("ScriptedTrendMostLoaded", TREND_FIELDS),
    ("ScriptedTrendLargestDelta", TREND_FIELDS),
    ("ScriptedLodfRanking", (
        ("case_order", "integer"), ("case_name", "string"), ("basis_text", "string"), ("rank", "integer"),
        ("element_name", "string"), ("voltage_level", "string"), ("lodf_text", "string"),
        ("ref_text", "string"), ("outage_text", "string"), ("delta_text", "string"),
        ("status_label", "string"), ("violation", "integer"))),
    ("ScriptedTopLinesByCase", MATRIX_FIELDS),
    ("ScriptedAppendixLine", MATRIX_FIELDS),
    ("ScriptedAppendixTransformer", MATRIX_FIELDS),
    ("ScriptedAppendixVoltage", MATRIX_FIELDS),
)
REQUIRED_FIELDS = {
    "ScriptedReportMeta": (
        "study_id", "study_name", "model_name", "model_version", "generation_date", "generated_by", "run_mode",
        "template_name", "template_version", "data_contract_version", "result_name", "assessment_scope",
        "assessment_status", "voltage_limits", "has_cases", "chart_cases", "lodf_text"),
    "ScriptedModelQuality": ("check_id", "check_name", "status", "message"),
    "ScriptedCases": ("case_order", "case_id", "case_name", "is_reference", "simulation_status", "assessment",
                      "violation"),
    "ScriptedCaseMetrics": ("case_order", "case_name", "max_line_text", "largest_delta_text",
                            "voltage_range_text"),
    "ScriptedKpis": ("highest_text", "highest_caption", "delta_text", "delta_caption"),
    "ScriptedPieLines": ("sort_order", "class_label", "element_count"),
    "ScriptedPieTransformers": ("sort_order", "class_label", "element_count"),
    "ScriptedReferenceExceeded": ("rank", "type_label", "element_name", "max_text"),
    "ScriptedCaseCounts": ("case_order", "case_name", "line_count", "transformer_count", "node_count"),
    "ScriptedRadar": ("metric_order", "metric_label", "s0_name"),
    "ScriptedLineLoadingBars": ("rank", "element_name", "max_value"),
    "ScriptedTrendMostLoaded": ("time_label", "timestamp", "element_name", "chart_title", "unit", "s0_name"),
    "ScriptedTrendLargestDelta": ("time_label", "timestamp", "element_name", "chart_title", "unit", "s0_name"),
    "ScriptedLodfRanking": ("case_order", "case_name", "basis_text", "rank", "element_name", "status_label",
                            "violation"),
    "ScriptedTopLinesByCase": ("block", "row_order", "element_name", "ref_text", "col_count", "violation"),
    "ScriptedAppendixLine": ("block", "row_order", "element_name", "ref_text", "col_count", "violation"),
    "ScriptedAppendixTransformer": ("block", "row_order", "element_name", "ref_text", "col_count", "violation"),
    "ScriptedAppendixVoltage": ("block", "row_order", "element_name", "ref_text", "col_count", "violation"),
}
# One table per chart: every table below feeds exactly one chart, which reads it without a data relation.
TREND_TABLES = ("ScriptedTrendMostLoaded", "ScriptedTrendLargestDelta")

def safe_attr(obj, name, default=None):
    try:
        value = getattr(obj, name)
        return default if value is None else value
    except Exception:
        return default

def clip_text(value, limit):
    """Shorten to `limit` characters with a visible ellipsis, nothing else."""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:max(0, limit - 1)] + '\u2026'

def object_key(obj):
    try:
        value = obj.GetFullName()
        if value:
            return str(value)
    except Exception:
        pass
    return str(safe_attr(obj, 'loc_name', 'unknown'))

def object_name(obj):
    value = safe_attr(obj, 'loc_name', '')
    return str(value) if value else object_key(obj).rsplit('\\', 1)[-1]

def object_id(obj):
    return object_name(obj)

def object_description(obj):
    value = safe_attr(obj, 'desc', '')
    if isinstance(value, (list, tuple)):
        return ' '.join((str(item) for item in value if item))
    return str(value or '')

def class_name(obj):
    try:
        return str(obj.GetClassName())
    except Exception:
        return ''

def element_grid_name(obj):
    """Name of the grid an element belongs to; '' when it has none.

    PowerFactory shows the grid as the attribute "Grid" (cpGrid). Where that is
    not readable, the ElmNet folder in the element's own path is used.
    """
    grid = safe_attr(obj, 'cpGrid')
    if grid is not None and not isinstance(grid, (str, int, float, bool)):
        name = object_name(grid)
        if name:
            return name
    for part in reversed(object_key(obj).split('\\')):
        if part.endswith('.ElmNet'):
            return part[:-len('.ElmNet')]
    return ''

def element_in_scope(obj):
    return not GRID_NAME_FILTER or GRID_NAME_FILTER in element_grid_name(obj)

def result_category(obj, variable):
    for category in CLASS_CATEGORIES.get(class_name(obj), ()):
        if variable in VARIABLES[category]:
            return category
    return None

def finite_number(value):
    if isinstance(value, (tuple, list)):
        return None
    if value is None or type(value) is bool:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if ',' in value and '.' not in value and (value.count(',') == 1):
            value = value.replace(',', '.')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None

def return_code(value):
    if value is None:
        return 0.0
    if isinstance(value, (tuple, list)):
        if not value:
            return None
        value = value[0]
    if isinstance(value, (tuple, list)):
        return None
    return finite_number(value)

def result_value(elmres, row, column):
    try:
        raw = elmres.GetValue(row, column)
    except Exception:
        return None
    if isinstance(raw, (tuple, list)):
        if len(raw) < 2:
            return None
        error_code = finite_number(raw[0])
        if error_code is None or error_code != 0.0:
            return None
        raw = raw[1]
    return finite_number(raw)

def normalize_time_unit(unit):
    text = str(unit or '').strip().lower().replace(' ', '')
    aliases = {'s': 's', 'sec': 's', 'second': 's', 'seconds': 's', 'min': 'min', 'minute': 'min', 'minutes': 'min', 'h': 'h', 'hr': 'h', 'hour': 'h', 'hours': 'h', 'd': 'd', 'day': 'd', 'days': 'd'}
    return aliases.get(text, text or TIME_UNIT_FALLBACK)

def time_in_hours(value, unit, row):
    numeric = finite_number(value)
    if numeric is None:
        return float(row)
    factor = {'s': 1.0 / 3600.0, 'min': 1.0 / 60.0, 'h': 1.0, 'd': 24.0}.get(normalize_time_unit(unit), 1.0)
    return numeric * factor

def format_clock(hours):
    sign = '-' if hours < 0 else ''
    total_seconds = int(round(abs(hours) * 3600.0))
    days, remainder = divmod(total_seconds, 86400)
    hour, remainder = divmod(remainder, 3600)
    minute, second = divmod(remainder, 60)
    clock = '{:02d}:{:02d}'.format(hour, minute)
    if second:
        clock += ':{:02d}'.format(second)
    if days:
        return '{}{} d {}'.format(sign, days, clock)
    return sign + clock

def is_absolute_time_axis(hours):
    """True when the axis holds absolute epoch time instead of elapsed time.

    PowerFactory 2026 reports the implicit quasi-dynamic time scale in 's'
    but fills it with absolute epoch seconds. No quasi-dynamic study spans
    the decade that separates the two interpretations.
    """
    return bool(hours) and hours[0] >= ABSOLUTE_TIME_THRESHOLD_HOURS

def format_absolute_time(hours):
    try:
        return time.strftime('%Y-%m-%d %H:%M', time.localtime(hours * 3600.0))
    except (ValueError, OverflowError, OSError):
        return format_clock(hours)

def format_time(value, row, unit):
    if isinstance(value, (tuple, list)):
        value = value[1] if len(value) >= 2 else value[0] if value else None
    if finite_number(value) is not None:
        return format_clock(time_in_hours(value, unit, row))
    if value is not None and str(value).strip():
        return str(value)
    return 'Time step {}'.format(row)

def format_time_step(hours):
    if hours < 1.0 / 60.0:
        return '{:g} s'.format(hours * 3600.0)
    if hours < 1.0:
        return '{:g} min'.format(hours * 60.0)
    if hours < 24.0:
        return '{:g} h'.format(hours)
    return '{:g} d'.format(hours / 24.0)

def time_column(elmres, column_count, row_count):
    candidates = ('b:tnow', 't', 'time')
    inspected = []
    for column in range(column_count):
        try:
            variable = str(elmres.GetVariable(column)).lower()
        except Exception:
            continue
        inspected.append(variable)
        if variable in candidates:
            return column
    for candidate in candidates:
        try:
            column = elmres.FindColumn(candidate)
            if isinstance(column, int) and column >= 0:
                return column
        except Exception:
            pass
    scale_rows = [0] if row_count == 1 else [0, row_count - 1]
    scale_values = [result_value(elmres, row, -1) for row in scale_rows]
    if all(value is not None for value in scale_values):
        if len(scale_values) == 1 or scale_values[1] > scale_values[0]:
            return -1
    variables = ', '.join(inspected) if inspected else 'unreadable'
    raise RuntimeError(
        'ElmRes exposes neither an explicit time column (b:tnow, t or time) '
        'nor a readable implicit time scale at column -1. Inspected result '
        'variables: {}.'.format(variables))

def nominal_voltage(obj):
    """Nominal voltage in kV of the element or of the terminal it connects to."""
    candidates = [obj]
    for attribute in ('bus1', 'bus2', 'bushv', 'buslv', 'busmv'):
        cubicle = safe_attr(obj, attribute)
        terminal = safe_attr(cubicle, 'cterm') if cubicle else None
        if terminal:
            candidates.append(terminal)
    for item in candidates:
        nominal = finite_number(safe_attr(item, 'uknom'))
        if nominal is not None and nominal > 0:
            return nominal
    return None

def voltage_level(obj):
    nominal = nominal_voltage(obj)
    return '{:g} kV'.format(nominal) if nominal is not None else ''

def is_dc_terminal(obj):
    """ElmTerm.systype 1 marks a DC terminal; its voltage is no AC magnitude."""
    return class_name(obj) == 'ElmTerm' and finite_number(safe_attr(obj, 'systype')) == 1.0

def read_column(elmres, column, rows):
    reader = getattr(elmres, 'GetColumnValues', None)
    if reader is not None:
        try:
            raw = reader(column)
        except Exception:
            raw = None
        if raw is not None:
            if isinstance(raw, tuple) and len(raw) == 2 and _is_sequence(raw[1]):
                code = finite_number(raw[0])
                raw = raw[1] if code == 0.0 else None
        if raw is not None:
            if not _is_sequence(raw):
                raw = None
            elif len(raw) != rows:
                raise RuntimeError('ElmRes column {} returned {} values instead of {}.'.format(column, len(raw), rows))
            else:
                return [finite_number(value) for value in raw]
    return [result_value(elmres, row, column) for row in range(rows)]

def _is_sequence(value):
    return isinstance(value, (list, tuple))

def collect_series(elmres, windows=(), counters=None):
    rows = int(elmres.GetNumberOfRows())
    columns = int(elmres.GetNumberOfColumns())
    if rows <= 0:
        raise RuntimeError('ElmRes contains no result rows.')
    if columns <= 0:
        raise RuntimeError('ElmRes contains no result columns.')
    if rows > MAX_RESULT_ROWS:
        raise RuntimeError('ElmRes has {} rows and exceeds the limit of {} (MAX_RESULT_ROWS).'.format(rows, MAX_RESULT_ROWS))
    t_column = time_column(elmres, columns, rows)
    try:
        time_unit = normalize_time_unit(elmres.GetUnit(t_column))
    except Exception as exc:
        raise RuntimeError('The ElmRes time-column unit could not be read: {}'.format(exc)) from exc
    if time_unit not in {'s', 'min', 'h', 'd'}:
        raise RuntimeError('Unsupported ElmRes time-column unit: {}'.format(time_unit or TIME_UNIT_FALLBACK))
    raw_times = []
    hours = []
    for row, raw in enumerate(read_column(elmres, t_column, rows)):
        if raw is None:
            raise RuntimeError('Invalid time value in ElmRes cell ({}, {}).'.format(row, t_column))
        raw_times.append(raw)
        hours.append(time_in_hours(raw, time_unit, row))
    if any((current <= previous for previous, current in zip(hours, hours[1:]))):
        raise RuntimeError('The ElmRes time axis is not strictly increasing.')
    absolute = is_absolute_time_axis(hours)
    origin = hours[0] if absolute else None
    if absolute:
        labels = [format_absolute_time(value) for value in hours]
        plot_times = [value - hours[0] for value in hours]
    else:
        labels = [format_time(raw, row, time_unit) for row, raw in enumerate(raw_times)]
        plot_times = list(hours)
    bounds = window_bounds(hours, windows) if absolute and windows else []
    chosen = {}
    out_of_scope = 0
    dc_nodes = set()
    for column in range(columns):
        try:
            obj = elmres.GetObject(column)
            variable = str(elmres.GetVariable(column))
            category = result_category(obj, variable)
        except Exception:
            continue
        if not category or variable not in VARIABLES[category]:
            continue
        # Before the full path is fetched and before any value is read.
        if not element_in_scope(obj):
            out_of_scope += 1
            continue
        if category == 'voltage' and is_dc_terminal(obj):
            dc_nodes.add(object_key(obj))
            continue
        key = (category, object_key(obj))
        priority = VARIABLES[category].index(variable)
        if key not in chosen or priority < chosen[key][0]:
            chosen[key] = (priority, column, obj, variable)
    if counters is not None:
        counters['out_of_scope'] = out_of_scope
        counters['dc_nodes'] = len(dc_nodes)
        counters['deenergized_nodes'] = 0
        counters['deenergized_steps'] = 0
    if not chosen and out_of_scope:
        raise RuntimeError(
            'No result series belongs to an element whose grid name contains '
            '{!r} ({} series were out of scope). Set GRID_NAME_FILTER at the top '
            'of gridlens_report.py, or to an empty string to assess every '
            'element.'.format(GRID_NAME_FILTER, out_of_scope))
    cells = rows * len(chosen)
    if cells > MAX_RESULT_CELLS:
        raise RuntimeError('ElmRes contains {} evaluated cells ({} rows x {} series) and exceeds the limit of {} (MAX_RESULT_CELLS).'.format(cells, rows, len(chosen), MAX_RESULT_CELLS))
    series = []
    for (_, _), (_, column, obj, variable) in sorted(chosen.items()):
        points = []
        category = result_category(obj, variable)
        dark = 0
        for row, value in enumerate(read_column(elmres, column, rows)):
            if value is None:
                raise RuntimeError('Invalid result value in ElmRes cell ({}, {}) for {} {}.'.format(row, column, object_name(obj), variable))
            if category == 'voltage' and value < ENERGIZED_MIN_PU:
                # PowerFactory reports 0 for a de-energised node: no value.
                value = None
                dark += 1
            points.append((labels[row], plot_times[row], value))
        if counters is not None:
            counters['deenergized_steps'] += dark
        if dark == len(points):
            if counters is not None:
                counters['deenergized_nodes'] += 1
            continue
        try:
            unit = str(elmres.GetUnit(column) or '')
        except Exception:
            unit = ''
        if not unit:
            unit = 'p.u.' if category == 'voltage' else '%'
        nominal = nominal_voltage(obj)
        values = [value for _, _, value in points]
        series.append({'category': category, 'object': obj, 'key': object_key(obj), 'element_id': object_id(obj), 'element_name': object_name(obj), 'voltage_level': voltage_level(obj), 'nominal_kv': nominal, 'limits': voltage_band(nominal) if category == 'voltage' else None, 'variable_id': variable, 'variable': 'Voltage magnitude' if category == 'voltage' else 'Loading', 'unit': unit, 'points': points})
        item = series[-1]
        item['statistics'] = statistics(item)
        item['windows'] = window_statistics(values, labels, bounds)
        item['points'] = sampled_plot_points(item)
    if not series:
        raise RuntimeError('ElmRes contains no completely readable supported result series.')
    return (series, labels, plot_times, time_unit, absolute, origin)

def check_run_budget(results):
    cells = 0
    for result in results:
        rows = len(result['labels'])
        for category in result['by_category']:
            cells += rows * len(result['by_category'][category])
    if cells > MAX_RUN_CELLS:
        raise RuntimeError('The run contains {} result cells across {} cases and exceeds the limit of {} (MAX_RUN_CELLS). Reduce cases, time range or model scope.'.format(cells, len(results), MAX_RUN_CELLS))
    return cells

def sampled_plot_points(item):
    """Every point up to MAX_PLOT_POINTS, otherwise an evenly spaced grid.

    The grid depends only on the number of points, so REF and OUTAGE on the
    same time axis are sampled at identical times. Per-series extremes are not
    added: they differ between the cases and gave the two lines different
    axes. Exact extremes remain in the statistics.
    """
    points = item['points']
    count = len(points)
    if count <= MAX_PLOT_POINTS:
        return points
    indices = {int(round(sample * (count - 1) / float(MAX_PLOT_POINTS - 1))) for sample in range(MAX_PLOT_POINTS)}
    return [points[index] for index in sorted(indices)]

def percentile95(values):
    ordered = sorted(values)
    index = max(0, int(math.ceil(0.95 * len(ordered))) - 1)
    return ordered[index]

def window_bounds(hours, windows):
    """Row ranges of each outage window on a strictly increasing hour axis."""
    bounds = []
    for start, end in windows:
        # A window PowerFactory does not expose is judged over the whole axis.
        lo = 0 if start is None else bisect.bisect_left(hours, start / 3600.0)
        hi = len(hours) if end is None else bisect.bisect_right(hours, end / 3600.0)
        bounds.append((lo, hi))
    return bounds

def window_statistics(values, labels, bounds):
    """Statistics per window, skipping windows without result rows."""
    result = {}
    for index, (lo, hi) in enumerate(bounds):
        chunk = [(labels[row], values[row]) for row in range(lo, hi) if values[row] is not None]
        if not chunk:
            continue
        minimum = min(value for _, value in chunk)
        maximum = max(value for _, value in chunk)
        result[index] = {
            'min': minimum, 'max': maximum,
            'mean': sum(value for _, value in chunk) / len(chunk),
            'time_min': next(label for label, value in chunk if value == minimum),
            'time_max': next(label for label, value in chunk if value == maximum),
        }
    return result

def statistics(series):
    points = [(label, value) for label, _, value in series['points'] if value is not None]
    if not points:
        return None
    values = [value for _, value in points]
    minimum = min(values)
    maximum = max(values)
    return {'min': minimum, 'max': maximum, 'mean': sum(values) / len(values), 'p95': percentile95(values), 'time_min': next((label for label, value in points if value == minimum)), 'time_max': next((label for label, value in points if value == maximum))}

def format_limit(value):
    return '{:g}'.format(value)

def has_time_variation(item):
    stats = item.get('statistics')
    if stats is not None:
        spread = stats['max'] - stats['min']
    else:
        values = [value for _, _, value in item['points'] if value is not None]
        if len(values) < 2:
            return False
        spread = max(values) - min(values)
    tolerance = {'line': 0.1, 'transformer': 0.1, 'voltage': 0.001}.get(item['category'], 1e-06)
    return spread > tolerance

def empty_payload():
    return {name: [] for name, _ in TABLES}

def voltage_band(nominal_kv):
    """Permitted voltage in p.u. of the nominal voltage (lower, upper)."""
    if nominal_kv:
        for lowest, highest, minimum, maximum in VOLTAGE_LIMITS_KV:
            if lowest <= nominal_kv < highest:
                return minimum / nominal_kv, maximum / nominal_kv
    return VOLTAGE_MIN, VOLTAGE_MAX

def voltage_limits(item):
    return item.get('limits') or (VOLTAGE_MIN, VOLTAGE_MAX)

def is_critical(item, stats):
    if stats is None:
        return False
    if item['category'] in ('line', 'transformer'):
        return stats['max'] > LOADING_MAX
    if item['category'] == 'voltage':
        lower, upper = voltage_limits(item)
        return stats['min'] < lower or stats['max'] > upper
    return False
REFERENCE_ID = 'REF'
CONVERGED = 'CONVERGED'
AXIS_MISMATCH = 'NOT EVALUATED'
CASE_FAILED = 'FAILED'
DELTA_KEYS = (('ref_min', 'delta_min', 'min'), ('ref_max', 'delta_max', 'max'), ('ref_mean', 'delta_mean', 'mean'))

def case_result(case, series, labels, plot_times, time_unit):
    by_category = {category: [] for category in VARIABLES}
    stats_by_key = {}
    item_by_key = {}
    for item in series:
        stats = dict(item.get('statistics') or statistics(item))
        for reference_key, delta_key, _ in DELTA_KEYS:
            stats[reference_key] = None
            stats[delta_key] = None
        by_category[item['category']].append((item, stats))
        stats_by_key[item['category'], item['key']] = stats
        item_by_key[item['category'], item['key']] = item
    return {'id': case['id'], 'name': case['name'], 'kind': case.get('kind', 'case'), 'description': case.get('description', ''), 'status': case.get('status', CONVERGED), 'error_code': case.get('error_code'), 'message': case.get('message', ''), 'counters': dict(case.get('counters') or {}), 'is_reference': 1 if case['id'] == REFERENCE_ID else 0, 'labels': list(labels), 'plot_times': list(plot_times), 'time_unit': time_unit, 'by_category': by_category, 'stats_by_key': stats_by_key, 'item_by_key': item_by_key, 'outage': case.get('outage')}

def failed_case(case, message):
    """A case that produced no usable result; it stays in the report with its reason."""
    result = case_result(dict(case, status=CASE_FAILED, error_code=-1, message=message), [], [], [], '')
    return result

def find_reference(results, reference_id=REFERENCE_ID):
    for result in results:
        if result['id'] == reference_id and result['status'] == CONVERGED:
            return result
    return None

def _same_time_axis(anchor, result):
    if anchor['time_unit'] != result['time_unit']:
        return False
    if anchor['labels'] != result['labels']:
        return False
    left = anchor['plot_times']
    right = result['plot_times']
    return len(left) == len(right) and all((abs(a - b) <= 1e-09 for a, b in zip(left, right)))

def enforce_common_time_axis(results, reference_id=REFERENCE_ID):
    ok = converged(results)
    if len(ok) < 2:
        return results
    anchor = find_reference(results, reference_id) or ok[0]
    for result in ok:
        if result is anchor or _same_time_axis(anchor, result):
            continue
        result['status'] = AXIS_MISMATCH
        result['error_code'] = -4
        result['message'] = 'Time axis differs from case {}; metrics and deltas were not evaluated.'.format(anchor['id'])
    return results

def apply_reference(results, reference_id=REFERENCE_ID):
    for result in results:
        result['is_reference'] = 1 if result['id'] == reference_id else 0
    enforce_common_time_axis(results, reference_id)
    reference = find_reference(results, reference_id)
    if reference is None:
        return results
    for result in converged(results):
        for key, stats in result['stats_by_key'].items():
            reference_stats = reference['stats_by_key'].get(key)
            if reference_stats is None:
                continue
            for reference_key, delta_key, source in DELTA_KEYS:
                stats[reference_key] = reference_stats[source]
                stats[delta_key] = stats[source] - reference_stats[source]
    return results

def converged(results):
    return [result for result in results if result['status'] == CONVERGED]

def outage_cases(results):
    """The calculated planned-outage cases in run order."""
    return [result for result in converged(results) if result['id'] != REFERENCE_ID]

def case_blocks(cases):
    """Cases in groups of CASE_SLOTS; always at least one (possibly empty) block."""
    return [cases[start:start + CASE_SLOTS] for start in range(0, len(cases), CASE_SLOTS)] or [[]]

def critical_keys(results, category):
    keys = set()
    for result in converged(results):
        for item, stats in result['by_category'][category]:
            if is_critical(item, stats):
                keys.add((category, item['key']))
    return keys

def evaluated_keys(results, category):
    return {item['key'] for result in converged(results) for item, _ in result['by_category'][category]}

# Each element once, REF and one case side by side. Deltas and the status below
# only ever compare the same element (same full PowerFactory path).
STATUS_NEW = 'NEW'
STATUS_WORSENED = 'WORSENED'
STATUS_PREEXISTING = 'PRE-EXISTING'
STATUS_RESOLVED = 'RESOLVED'
STATUS_EXCEEDED = 'EXCEEDED'
STATUS_OK = 'OK'
CAUSED_STATUSES = (STATUS_NEW, STATUS_WORSENED, STATUS_EXCEEDED)
EXCEEDED_STATUSES = CAUSED_STATUSES + (STATUS_PREEXISTING,)

def paired(results, category, case=None, windowed=False):
    """One record per element with its REF and case statistics.

    `windowed` reads the statistics inside the case's own outage window for both
    sides; otherwise they cover the complete simulated period. Without a case
    only REF is read.
    """
    reference = find_reference(results)
    index = case['outage'].get('window_index') if windowed and case is not None and case.get('outage') else None
    records = {}
    for side, result in (('ref', reference), ('outage', case)):
        if result is None or result['status'] != CONVERGED:
            continue
        for item, stats in result['by_category'].get(category, ()):
            if windowed and case is not None:
                stats = item.get('windows', {}).get(index)
            if stats is None:
                continue
            record = records.setdefault(item['key'], {'item': item, 'ref': None, 'outage': None})
            record[side] = stats
    return list(records.values())

def primary(record):
    """The case where it was calculated, otherwise REF."""
    return record['outage'] if record['outage'] is not None else record['ref']

def _worse(item, ref, outage):
    if item['category'] in LOADING_CATEGORIES:
        return outage['max'] - ref['max'] > LOADING_DELTA_TOLERANCE
    lower, upper = voltage_limits(item)
    return ((outage['min'] < lower and outage['min'] < ref['min'] - VOLTAGE_DELTA_TOLERANCE)
            or (outage['max'] > upper and outage['max'] > ref['max'] + VOLTAGE_DELTA_TOLERANCE))

def limit_status(record):
    """What the planned outage did to this element's limit."""
    item, ref, outage = record['item'], record['ref'], record['outage']
    in_ref = is_critical(item, ref)
    in_outage = is_critical(item, outage)
    if ref is None or outage is None:
        return STATUS_EXCEEDED if in_ref or in_outage else STATUS_OK
    if in_outage and not in_ref:
        return STATUS_NEW
    if in_outage:
        return STATUS_WORSENED if _worse(item, ref, outage) else STATUS_PREEXISTING
    return STATUS_RESOLVED if in_ref else STATUS_OK

def highlight(status):
    """1 marks a violation caused or worsened by the outage, 2 one already in REF."""
    return 1 if status in CAUSED_STATUSES else 2 if status == STATUS_PREEXISTING else 0

def _by_name(record):
    return record['item']['element_name'].casefold()

def _loading_delta(record):
    if record['ref'] is None or record['outage'] is None:
        return None
    return record['outage']['max'] - record['ref']['max']

def loading_text(value):
    return 'n/a' if value is None else '{:.1f} %'.format(value)

def voltage_text(value):
    return 'n/a' if value is None else '{:.3f}'.format(value)

def delta_text(value):
    return '-' if value is None else '{:+.1f} pp'.format(value)

def _counted(count, singular, plural):
    return '{} {}'.format(count, singular if count == 1 else plural)

def _status_breakdown(statuses, both_cases):
    """'1 new, 2 already in REF' for the exceeded statuses."""
    if not both_cases:
        return ''
    parts = []
    for status, label in ((STATUS_NEW, 'new'), (STATUS_WORSENED, 'worsened'), (STATUS_PREEXISTING, 'already in REF')):
        count = statuses.count(status)
        if count:
            parts.append('{} {}'.format(count, label))
    return ': ' + ', '.join(parts) if parts else ''

def _voltage_excess(record):
    lower, upper = voltage_limits(record['item'])
    stats = primary(record)
    return max(lower - stats['min'], stats['max'] - upper)

def _primary_counters(results):
    reference = find_reference(results)
    return reference.get('counters', {}) if reference else {}

LOADING_CLASSES = (('up to 80 %', lambda value: value <= LOADING_WARNING), ('80 to 100 %', lambda value: value <= LOADING_MAX), ('above 100 %', lambda value: True))
CATEGORY_LABELS = (('line', 'Line loading', 'line', 'lines'), ('transformer', 'Transformer loading', 'transformer', 'transformers'), ('voltage', 'Voltage magnitude', 'node', 'nodes'))
REFERENCE_NAME = 'Reference'
MAX_REFERENCE_ROWS = 30

def voltage_limits_text():
    bands = ['{} to {} kV for a nominal voltage from {} kV up to {} kV'.format(format_limit(minimum), format_limit(maximum), format_limit(lowest), format_limit(highest)) for lowest, highest, minimum, maximum in VOLTAGE_LIMITS_KV]
    return 'Permitted voltage band: {}; {} to {} p.u. for any other nominal voltage. Values on the band limit are no violation.'.format('; '.join(bands), format_limit(VOLTAGE_MIN), format_limit(VOLTAGE_MAX))

def _result_name(result):
    return REFERENCE_NAME if result['id'] == REFERENCE_ID else result['name']

def _matrix_tables(payload, results, table, entries):
    """Write entries (name, REF text, {case id: text}, violation) as blocks of CASE_SLOTS cases."""
    cases = outage_cases(results)
    for block_number, block in enumerate(case_blocks(cases), 1):
        for order, (name, ref_text, texts, violation) in enumerate(entries, 1):
            row = {'block': block_number, 'row_order': order, 'element_name': name, 'ref_text': ref_text, 'col_count': len(block), 'violation': violation}
            for slot in range(1, CASE_SLOTS + 1):
                case = block[slot - 1] if slot <= len(block) else None
                row['h{}_name'.format(slot)] = case['name'] if case else ''
                row['c{}_text'.format(slot)] = texts.get(case['id'], 'n/a') if case else ''
            payload[table].append(row)

def _stats_by_result(results, category):
    """{result id: {element key: (item, stats)}} for REF and every calculated case."""
    ok = converged(results)
    return {result['id']: {item['key']: (item, stats) for item, stats in result['by_category'][category]} for result in ok}

def _violation_flag(item, ref_stats, case_stats_list):
    flags = [highlight(limit_status({'item': item, 'ref': ref_stats, 'outage': stats})) for stats in case_stats_list]
    if not flags:
        flags = [highlight(limit_status({'item': item, 'ref': ref_stats, 'outage': None}))]
    return 1 if 1 in flags else 2 if 2 in flags else 0

def _loading_appendix(payload, results, category, table):
    by_result = _stats_by_result(results, category)
    reference = by_result.get(REFERENCE_ID, {})
    cases = outage_cases(results)
    keys = {key for entries in by_result.values() for key in entries}
    listed = []
    for key in keys:
        found = [(case_id, entries[key]) for case_id, entries in by_result.items() if key in entries]
        item = found[0][1][0]
        ref_stats = reference.get(key, (None, None))[1]
        peaks = [stats['max'] for _, (_, stats) in found]
        deltas = [stats['max'] - ref_stats['max'] for case_id, (_, stats) in found if ref_stats is not None and case_id != REFERENCE_ID]
        if max(peaks) < LOADING_WARNING and not any(abs(delta) >= LOADING_APPENDIX_DELTA for delta in deltas):
            continue
        case_stats = [by_result[case['id']][key][1] for case in cases if key in by_result[case['id']]]
        texts = {case['id']: loading_text(by_result[case['id']][key][1]['max']) if key in by_result[case['id']] else 'n/a' for case in cases}
        listed.append((-max(peaks), item['element_name'].casefold(), item['element_name'], loading_text(ref_stats['max'] if ref_stats else None), texts, _violation_flag(item, ref_stats, case_stats)))
    _matrix_tables(payload, results, table, [entry[2:] for entry in sorted(listed, key=lambda entry: entry[:2])])

def _voltage_appendix(payload, results):
    by_result = _stats_by_result(results, 'voltage')
    reference = by_result.get(REFERENCE_ID, {})
    cases = outage_cases(results)
    keys = {key for entries in by_result.values() for key in entries}
    listed = []
    for key in keys:
        found = [entries[key] for entries in by_result.values() if key in entries]
        item = found[0][0]
        ref_stats = reference.get(key, (None, None))[1]
        case_stats = [by_result[case['id']][key][1] for case in cases if key in by_result[case['id']]]
        statuses = [limit_status({'item': item, 'ref': ref_stats, 'outage': stats}) for stats in case_stats] or [limit_status({'item': item, 'ref': ref_stats, 'outage': None})]
        change = max([abs(stats['min'] - ref_stats['min']) for stats in case_stats] or [0.0]) if ref_stats is not None else 0.0
        if all(status == STATUS_OK for status in statuses) and change < VOLTAGE_APPENDIX_DELTA:
            continue
        lower, upper = voltage_limits(item)
        excess = max(max(lower - stats['min'], stats['max'] - upper) for _, stats in found)
        texts = {case['id']: voltage_text(by_result[case['id']][key][1]['min']) if key in by_result[case['id']] else 'n/a' for case in cases}
        listed.append((-excess, item['element_name'].casefold(), item['element_name'], voltage_text(ref_stats['min'] if ref_stats else None), texts, _violation_flag(item, ref_stats, case_stats)))
    _matrix_tables(payload, results, 'ScriptedAppendixVoltage', [entry[2:] for entry in sorted(listed, key=lambda entry: entry[:2])])

def _top_lines_by_case(payload, results):
    by_result = _stats_by_result(results, 'line')
    ranked = {}
    for result_id, entries in by_result.items():
        ordered = sorted(entries.values(), key=lambda entry: (-entry[1]['max'], entry[0]['element_name'].casefold()))[:TOP_N]
        ranked[result_id] = ['{} - {}'.format(item['element_name'], loading_text(stats['max'])) for item, stats in ordered]
    cases = outage_cases(results)
    rows = []
    for rank in range(1, TOP_N + 1):
        reference = ranked.get(REFERENCE_ID, [])
        texts = {case['id']: ranked[case['id']][rank - 1] if rank <= len(ranked.get(case['id'], [])) else 'n/a' for case in cases}
        if rank > len(reference) and all(text == 'n/a' for text in texts.values()):
            break
        rows.append((str(rank), reference[rank - 1] if rank <= len(reference) else 'n/a', texts, 0))
    _matrix_tables(payload, results, 'ScriptedTopLinesByCase', rows)

def _violation_counts(result):
    lines = sum(1 for item, stats in result['by_category']['line'] if is_critical(item, stats))
    transformers = sum(1 for item, stats in result['by_category']['transformer'] if is_critical(item, stats))
    nodes = sum(1 for item, stats in result['by_category']['voltage'] if is_critical(item, stats))
    return lines, transformers, nodes

def _case_counts(payload, results):
    reference = find_reference(results)
    ordered = ([reference] if reference else []) + outage_cases(results)
    for order, result in enumerate(ordered):
        lines, transformers, nodes = _violation_counts(result)
        payload['ScriptedCaseCounts'].append({'case_order': order, 'case_name': _result_name(result), 'line_count': lines, 'transformer_count': transformers, 'node_count': nodes})

def _radar(payload, results):
    reference = find_reference(results)
    cases = outage_cases(results)
    shown = ([reference] if reference else []) + cases[:CASE_SLOTS]
    if not shown:
        return
    counts = [_violation_counts(result) for result in shown]
    note = 'Axes use their own maximum; the table lists the absolute counts.'
    if len(cases) > CASE_SLOTS:
        note = 'The first {} of {} cases are drawn. '.format(CASE_SLOTS, len(cases)) + note
    for metric, label in enumerate(('Lines > 100 %', 'Transformers > 100 %', 'Nodes outside band')):
        values = [count[metric] for count in counts]
        peak = max(values) or 1
        row = {'metric_order': metric + 1, 'metric_label': label, 'note': note}
        for slot in range(SERIES_SLOTS):
            row['s{}_name'.format(slot)] = _result_name(shown[slot]) if slot < len(shown) else ' '
            row['v{}'.format(slot)] = 100.0 * values[slot] / peak if slot < len(shown) else None
        payload['ScriptedRadar'].append(row)

def _pies(payload, results):
    reference = find_reference(results)
    for category, table in (('line', 'ScriptedPieLines'), ('transformer', 'ScriptedPieTransformers')):
        counts = [0] * len(LOADING_CLASSES)
        if reference is not None:
            for _, stats in reference['by_category'][category]:
                counts[next(index for index, (_, fits) in enumerate(LOADING_CLASSES) if fits(stats['max']))] += 1
        for order, ((label, _), count) in enumerate(zip(LOADING_CLASSES, counts), 1):
            payload[table].append({'sort_order': order, 'class_label': label, 'element_count': count})

def _reference_exceeded(payload, results):
    reference = find_reference(results)
    if reference is None:
        return
    rows = []
    for category, label in (('line', 'Line'), ('transformer', 'Transformer')):
        for item, stats in reference['by_category'][category]:
            if is_critical(item, stats):
                rows.append((-stats['max'], item['element_name'].casefold(), label, item['element_name'], element_grid_name(item['object']), stats['max']))
    for rank, (_, _, label, name, grid, value) in enumerate(sorted(rows)[:MAX_REFERENCE_ROWS], 1):
        payload['ScriptedReferenceExceeded'].append({'rank': rank, 'type_label': label, 'element_name': name, 'grid_name': grid or '-', 'max_text': loading_text(value)})

def _line_bars(payload, results):
    best = {}
    for result in converged(results):
        for item, stats in result['by_category']['line']:
            current = best.get(item['key'])
            if current is None or stats['max'] > current[1]:
                best[item['key']] = (item['element_name'], stats['max'], _result_name(result))
    for rank, (name, value, case_name) in enumerate(sorted(best.values(), key=lambda entry: (-entry[1], entry[0].casefold()))[:TOP_N], 1):
        payload['ScriptedLineLoadingBars'].append({'rank': rank, 'element_name': name, 'max_value': value, 'case_name': case_name})

def _trend_rows(payload, table, results, key, title):
    reference = find_reference(results)
    shown = ([reference] if reference else []) + outage_cases(results)[:CASE_SLOTS]
    items = [result['item_by_key'].get(('line', key)) for result in shown]
    axis = next((item for item in items if item is not None), None)
    if axis is None:
        return
    series = [{label: value for label, _, value in sampled_plot_points(item)} if item is not None else {} for item in items]
    for label, timestamp, _ in sampled_plot_points(axis):
        row = {'time_label': label, 'timestamp': timestamp, 'element_name': axis['element_name'], 'chart_title': title, 'unit': axis['unit']}
        for slot in range(SERIES_SLOTS):
            row['s{}_name'.format(slot)] = _result_name(shown[slot]) if slot < len(shown) else ' '
            row['v{}'.format(slot)] = series[slot].get(label) if slot < len(shown) else None
        payload[table].append(row)

def _trends(payload, results):
    best = None
    for result in converged(results):
        for item, stats in result['by_category']['line']:
            if best is None or stats['max'] > best[0]:
                best = (stats['max'], item['key'], item['element_name'])
    if best is not None:
        _trend_rows(payload, 'ScriptedTrendMostLoaded', results, best[1], 'Most loaded line: {}'.format(best[2]))
    largest = None
    for case in outage_cases(results):
        for record in paired(results, 'line', case, True):
            delta = _loading_delta(record)
            if delta is not None and (largest is None or delta > largest[0]):
                largest = (delta, record['item']['key'], record['item']['element_name'], case['name'])
    if largest is not None and largest[0] > LOADING_DELTA_TOLERANCE:
        _trend_rows(payload, 'ScriptedTrendLargestDelta', results, largest[1], 'Largest delta: {} ({:+.1f} pp, {})'.format(largest[2], largest[0], largest[3]))

def _line_pairs(results, case):
    return [record for record in paired(results, 'line', case, True) if record['ref'] is not None and record['outage'] is not None]

def _case_metrics(payload, results):
    reference = find_reference(results)
    rows = []
    if reference is not None and reference['by_category']['line']:
        top = max(reference['by_category']['line'], key=lambda entry: (entry[1]['max'], -len(entry[0]['element_name'])))
        voltages = [stats for _, stats in reference['by_category']['voltage']]
        rows.append((0, REFERENCE_NAME, top[1]['max'], top[0]['element_name'], None, None, voltages and (min(s['min'] for s in voltages), max(s['max'] for s in voltages))))
    for order, case in enumerate(outage_cases(results), 1):
        pairs = _line_pairs(results, case)
        lines = [record for record in paired(results, 'line', case, True) if record['outage'] is not None]
        top = max(lines, key=lambda record: (record['outage']['max'], -len(_by_name(record))), default=None)
        rising = max(pairs, key=lambda record: _loading_delta(record), default=None)
        nodes = [record['outage'] for record in paired(results, 'voltage', case, True) if record['outage'] is not None]
        rows.append((order, case['name'], top['outage']['max'] if top else None, top['item']['element_name'] if top else '-', _loading_delta(rising) if rising else None, rising['item']['element_name'] if rising else '', nodes and (min(s['min'] for s in nodes), max(s['max'] for s in nodes))))
    for order, name, maximum, element, delta, delta_element, voltage in rows:
        payload['ScriptedCaseMetrics'].append({
            'case_order': order, 'case_name': name, 'max_line_text': loading_text(maximum), 'max_line_element': element,
            'largest_delta_text': '-' if delta is None else '{} - {}'.format(delta_text(delta), delta_element),
            'voltage_range_text': '{:.3f}-{:.3f} p.u.'.format(*voltage) if voltage else 'n/a'})
    named = [row for row in rows if row[2] is not None]
    if named:
        top = max(named, key=lambda row: row[2])
        pair = max((row for row in rows if row[4] is not None and row[4] > LOADING_DELTA_TOLERANCE), key=lambda row: row[4], default=None)
        payload['ScriptedKpis'].append({
            'highest_text': '{} · {}'.format(loading_text(top[2]), top[3]), 'highest_caption': 'Highest observed line loading across all cases',
            'highest_violation': 1 if top[2] > LOADING_MAX else 0,
            'delta_text': '{} · {}'.format(delta_text(pair[4]), pair[1]) if pair else 'no increase',
            'delta_caption': 'Largest loading increase compared with Reference' if pair else 'No line loads more than in Reference'})

def _lodf_ranking(payload, results, lodf):
    for order, case in enumerate(outage_cases(results), 1):
        record = case['outage']
        info = (lodf or {}).get(record['id']) or {}
        values = info.get('values') or {}
        out_of_service = set(record.get('equipment_keys') or ())
        pairs = [pair for pair in _line_pairs(results, case) if pair['item']['key'] not in out_of_service]
        if values:
            ranked = sorted((pair for pair in pairs if pair['item']['key'] in values), key=lambda pair: (-abs(values[pair['item']['key']][1]), _by_name(pair)))
            basis = 'Ranked by |LODF| from PowerFactory Sensitivities / Distribution Factors; delta = case maximum minus REF maximum inside the outage window.'
        else:
            ranked = sorted(pairs, key=lambda pair: (-_loading_delta(pair), _by_name(pair)))
            basis = 'Ranked by measured loading change because the LODF is not available: {}'.format(info.get('reason') or 'it was not calculated.')
        for rank, pair in enumerate(ranked[:TOP_N], 1):
            item = pair['item']
            status = limit_status(pair)
            fraction = values.get(item['key'], (None, None))[1]
            payload['ScriptedLodfRanking'].append({
                'case_order': order, 'case_name': case['name'], 'basis_text': basis, 'rank': rank, 'element_name': item['element_name'], 'voltage_level': item['voltage_level'],
                'lodf_text': 'n/a' if fraction is None else '{:+.1f} %'.format(fraction * 100.0), 'ref_text': loading_text(pair['ref']['max']), 'outage_text': loading_text(pair['outage']['max']),
                'delta_text': delta_text(_loading_delta(pair)), 'status_label': status, 'violation': highlight(status)})

def _model_quality(payload, results, lodf):
    ok = converged(results)
    total_series = sum((len(r['by_category'][c]) for r in ok for c, _, _, _ in CATEGORY_LABELS))
    cases_ok = bool(results) and len(ok) == len(results) and all((any((result['by_category'][category] for category, _, _, _ in CATEGORY_LABELS)) for result in ok))
    payload['ScriptedModelQuality'].append({'check_id': 'cases', 'check_name': 'Evaluated cases', 'status': 'PASS' if cases_ok else 'FAIL', 'message': '{} of {} cases converged; {} result series.'.format(len(ok), len(results), total_series), 'affected_element': '-'})
    for result in results:
        if result['status'] == CONVERGED:
            continue
        payload['ScriptedModelQuality'].append({'check_id': 'case_' + result['id'], 'check_name': 'Calculation ' + result['id'], 'status': 'FAIL', 'message': result['message'] or 'Calculation did not converge.', 'affected_element': result['name']})
    for category, label, singular, plural in CATEGORY_LABELS:
        evaluated = len(evaluated_keys(results, category))
        exceeded = len(critical_keys(results, category))
        message = '{} evaluated; {} the limit in at least one case.'.format(_counted(evaluated, singular, plural), _counted(exceeded, 'exceeds', 'exceed')) if evaluated else 'No {} evaluated.'.format(singular)
        payload['ScriptedModelQuality'].append({'check_id': 'series_' + category, 'check_name': label, 'status': 'PASS' if evaluated else 'WARNING', 'message': message, 'affected_element': _counted(exceeded, singular, plural) if exceeded else '-'})
    counters = _primary_counters(results)
    if counters.get('dc_nodes') or counters.get('deenergized_nodes') or counters.get('deenergized_steps'):
        payload['ScriptedModelQuality'].append({'check_id': 'voltage_data', 'check_name': 'Voltage data', 'status': 'INFO', 'message': '{} and {} left out; {} below {} p.u. ignored as de-energised.'.format(_counted(counters.get('dc_nodes', 0), 'DC node', 'DC nodes'), _counted(counters.get('deenergized_nodes', 0), 'node without voltage', 'nodes without voltage'), _counted(counters.get('deenergized_steps', 0), 'time step', 'time steps'), format_limit(ENERGIZED_MIN_PU)), 'affected_element': '-'})
    varying = sum((1 for r in ok for c, _, _, _ in CATEGORY_LABELS for item, _ in r['by_category'][c] if has_time_variation(item)))
    payload['ScriptedModelQuality'].append({'check_id': 'time_variation', 'check_name': 'Time variation', 'status': 'PASS' if varying else 'WARNING', 'message': '{} of {} series change over the simulation period.'.format(varying, total_series) if varying else 'All {} series are constant; check QDS profiles and result recording.'.format(total_series), 'affected_element': '-'})
    reference = find_reference(results)
    payload['ScriptedModelQuality'].append({'check_id': 'reference_comparison', 'check_name': 'Reference comparison', 'status': 'PASS' if reference is not None else 'WARNING', 'message': 'Every outage case is compared with Reference; deltas compare each element with itself.' if reference is not None else 'No converged reference case; violations cannot be split into new and pre-existing.', 'affected_element': '-'})
    if lodf is not None:
        defined = sum(1 for info in lodf.values() if info.get('values'))
        payload['ScriptedModelQuality'].append({'check_id': 'lodf', 'check_name': 'Line outage distribution factors', 'status': 'PASS' if lodf and defined == len(lodf) else 'WARNING', 'message': 'LODF for {} of {} outages; the ranking falls back to the measured loading change for the others.'.format(defined, len(lodf)), 'affected_element': '-'})
    payload['ScriptedModelQuality'].extend(({'check_id': 'security_scope', 'check_name': 'Assessment scope', 'status': 'WARNING', 'message': 'N-1 security, security of supply, protection coordination and safe isolation are not assessed.', 'affected_element': '-'}, {'check_id': 'limit_loading', 'check_name': 'Loading limit', 'status': 'INFO', 'message': 'Violation when loading > {} %.'.format(format_limit(LOADING_MAX)), 'affected_element': '-'}, {'check_id': 'limit_voltage', 'check_name': 'Voltage limits', 'status': 'INFO', 'message': voltage_limits_text(), 'affected_element': '-'}))

def _key_discriminator(key):
    digest = hashlib.sha256(str(key).encode('utf-8')).hexdigest()
    return digest[:6]

def assess_case(results, case):
    """Judge one planned outage by what its own case changes inside its time window."""
    loading = [record for category in LOADING_CATEGORIES for record in paired(results, category, case, True)]
    voltage = paired(results, 'voltage', case, True)
    in_outage = [record for record in loading if record['outage'] is not None]
    nodes = [record for record in voltage if record['outage'] is not None]
    if not in_outage and not nodes:
        return None
    loading_statuses = [limit_status(record) for record in loading]
    voltage_statuses = [limit_status(record) for record in voltage]
    over = any(status in CAUSED_STATUSES for status in loading_statuses)
    band = any(status in CAUSED_STATUSES for status in voltage_statuses)
    if over and band:
        verdict = ASSESSMENT_BOTH
    elif over:
        verdict = ASSESSMENT_LOADING
    elif band:
        verdict = ASSESSMENT_VOLTAGE
    elif STATUS_PREEXISTING in loading_statuses + voltage_statuses:
        verdict = ASSESSMENT_PREEXISTING
    else:
        verdict = ASSESSMENT_OK
    # Name the element the outage pushes over the limit, not one that was
    # already overloaded in REF; fall back to the most loaded element.
    caused = [record for record, status in zip(loading, loading_statuses)
              if status in CAUSED_STATUSES and record['outage'] is not None]
    worst = max(caused or in_outage, key=lambda record: record['outage']['max'], default=None)
    low = min(nodes, key=lambda record: record['outage']['min'], default=None)
    high = max(nodes, key=lambda record: record['outage']['max'], default=None)
    rising = max((record for record in in_outage if record['ref'] is not None), key=lambda record: _loading_delta(record), default=None)
    return {
        'assessment': verdict,
        'violation': 1 if verdict in (ASSESSMENT_LOADING, ASSESSMENT_VOLTAGE, ASSESSMENT_BOTH) else 0,
        'max_loading': worst['outage']['max'] if worst else None,
        'max_loading_element': worst['item']['element_name'] if worst else '',
        'max_loading_time': worst['outage']['time_max'] if worst else '',
        'reference_max_loading': worst['ref']['max'] if worst and worst['ref'] else None,
        'delta': _loading_delta(rising) if rising else None,
        'delta_element': rising['item']['element_name'] if rising else '',
        'min_voltage': low['outage']['min'] if low else None,
        'max_voltage': high['outage']['max'] if high else None,
        'loading_statuses': loading_statuses,
        'voltage_statuses': voltage_statuses,
        'both_cases': True,
    }

def _violation_text(statuses, singular, plural, both):
    exceeded = [status for status in statuses if status in EXCEEDED_STATUSES]
    if not exceeded:
        return 'no {}'.format(singular)
    return _counted(len(exceeded), singular, plural) + _status_breakdown(statuses, both)

def assessment_detail(values):
    """Readable sentences with the numbers behind the verdict, loading first."""
    parts = []
    both = values.get('both_cases', False)
    if values.get('max_loading') is not None:
        text = "Loading max {:.1f} % on {} at {}".format(
            values['max_loading'], values['max_loading_element'],
            values['max_loading_time'])
        if values.get('reference_max_loading') is not None:
            text += " (REF {:.1f} %)".format(values['reference_max_loading'])
        if values.get('delta') is not None and values['delta'] > LOADING_DELTA_TOLERANCE:
            text += ", largest increase {:+.1f} pp on {}".format(values['delta'], values['delta_element'])
        text += "; " + _violation_text(values.get('loading_statuses', []), 'overload', 'overloads', both)
        parts.append(text)
    if values.get('min_voltage') is not None and values.get('max_voltage') is not None:
        parts.append("Voltage {:.3f} to {:.3f} p.u.; {}".format(
            values['min_voltage'], values['max_voltage'],
            _violation_text(values.get('voltage_statuses', []), 'node outside the band', 'nodes outside the band', both)))
    return ". ".join(parts) + "." if parts else ""

def _reference_detail(reference):
    lines = reference['by_category']['line']
    nodes = [stats for _, stats in reference['by_category']['voltage']]
    parts = []
    if lines:
        top = max(lines, key=lambda entry: entry[1]['max'])
        parts.append('max line {:.1f} % on {}'.format(top[1]['max'], top[0]['element_name']))
    if nodes:
        parts.append('node voltage {:.3f}-{:.3f} p.u'.format(min(s['min'] for s in nodes), max(s['max'] for s in nodes)))
    return '; '.join(parts) + '.' if parts else ''

def period_text(start, end):
    """'2026-10-15 00:00 - 05:00' when both ends lie on the same day."""
    if not start and not end:
        return ''
    if start[:10] and start[:10] == end[:10] and len(end) > 11:
        return '{} - {}'.format(start, end[11:])
    return '{} - {}'.format(start, end)

def _case_rows(payload, results, planned_outages):
    reference = find_reference(results)
    reference_result = next((result for result in results if result['id'] == REFERENCE_ID), None)
    if reference_result is not None:
        labels = reference_result['labels']
        payload['ScriptedCases'].append({'case_order': 0, 'case_id': REFERENCE_ID, 'case_name': REFERENCE_NAME, 'is_reference': 1, 'simulation_status': reference_result['status'], 'period_text': period_text(labels[0], labels[-1]) if labels else '', 'priority': 0, 'equipment_name': 'No planned outage', 'assessment': 'BASELINE' if reference is not None else ASSESSMENT_NO_DATA, 'assessment_detail': _reference_detail(reference) if reference is not None else reference_result['message'], 'violation': 0})
    by_case = {result['id']: result for result in results}
    for order, outage in enumerate(planned_outages, 1):
        result = by_case.get(outage.get('case_id'))
        values = {'assessment': ASSESSMENT_SKIPPED, 'violation': 0}
        detail = outage.get('skip_reason', '')
        status = outage['status']
        if outage['status'] == OUTAGE_CONSIDERED and result is not None:
            status = result['status']
            if result['status'] != CONVERGED:
                values = {'assessment': AXIS_MISMATCH if result['status'] == AXIS_MISMATCH else ASSESSMENT_NOT_EVALUATED, 'violation': 0}
                detail = result['message']
            else:
                judged = assess_case(results, result)
                if judged is None:
                    values = {'assessment': ASSESSMENT_NO_DATA, 'violation': 0}
                    detail = 'No result rows fall inside this outage window, so it was not assessed.'
                else:
                    values = judged
                    detail = assessment_detail(judged)
        payload['ScriptedCases'].append({'case_order': order, 'case_id': outage.get('case_id') or 'N/A', 'case_name': outage['name'], 'is_reference': 0, 'simulation_status': status, 'period_text': period_text(outage.get('start_time', ''), outage.get('end_time', '')), 'priority': int(outage.get('priority') or 0), 'equipment_name': outage.get('equipment_name') or '-', 'assessment': values['assessment'], 'assessment_detail': detail, 'violation': values.get('violation', 0)})

def _enforce_table_limits(payload):
    for name in sorted(payload):
        if name == 'ScriptedModelQuality':
            continue
        rows = payload[name]
        limit = MAX_TABLE_ROWS
        if len(rows) <= limit:
            continue
        total = len(rows)
        del rows[limit:]
        payload['ScriptedModelQuality'].append({'check_id': 'table_limit_' + name, 'check_name': 'Table limit ' + name, 'status': 'FAIL', 'message': '{} rows generated, {} published. The report is incomplete; reduce the number of cases or the model scope (MAX_TABLE_ROWS).'.format(total, limit), 'affected_element': '-'})

def _lodf_text(results, lodf):
    cases = outage_cases(results)
    if not cases:
        return 'No planned outage case was calculated.'
    if lodf is None:
        return 'The line outage distribution factors were not requested.'
    defined = sum(1 for case in cases if (lodf.get(case['outage']['id']) or {}).get('values'))
    return 'LODF from PowerFactory for {} of {} outage cases.'.format(defined, len(cases))

def build_cases_payload(study_case, results, project_name, result_name, planned_outages, generated_by, run_mode, lodf=None):
    payload = empty_payload()
    enforce_common_time_axis(results)
    ok = converged(results)
    labels = ok[0]['labels'] if ok else results[0]['labels'] if results else []
    plot_times = ok[0]['plot_times'] if ok else []
    start = labels[0] if labels else ''
    end = labels[-1] if labels else ''
    time_step = ''
    if len(plot_times) >= 2:
        time_step = format_time_step(plot_times[1] - plot_times[0])
    reference = find_reference(results)
    cases = outage_cases(results)
    radar_note = ''
    if len(cases) > CASE_SLOTS:
        radar_note = 'Charts show the first {} of {} outage cases.'.format(CASE_SLOTS, len(cases))
    payload['ScriptedReportMeta'].append({'study_id': object_name(study_case), 'study_name': object_name(study_case), 'study_description': object_description(study_case), 'model_name': project_name, 'model_version': 'PowerFactory 2026', 'simulation_start': start, 'simulation_end': end, 'simulation_time_step': time_step or 'ElmRes row interval', 'generation_date': datetime.now().astimezone().strftime('%Y-%m-%d %H:%M'), 'generated_by': generated_by, 'run_mode': run_mode, 'template_name': TEMPLATE_NAME, 'template_version': TEMPLATE_VERSION, 'data_contract_version': DATA_CONTRACT_VERSION, 'result_name': result_name, 'assessment_scope': '{} case(s); reference: {}; {}'.format(len(results), reference['name'] if reference else 'none', 'elements in grids named *{}*'.format(GRID_NAME_FILTER) if GRID_NAME_FILTER else 'all elements'), 'assessment_status': 'PRE-ASSESSMENT - NOT AN OPERATIONAL RELEASE', 'voltage_limits': voltage_limits_text(), 'has_cases': '1' if cases else '0', 'chart_cases': str(1 + min(len(cases), CASE_SLOTS) if reference is not None else min(len(cases), CASE_SLOTS)), 'lodf_text': _lodf_text(results, lodf), 'radar_note': radar_note})
    _case_rows(payload, results, planned_outages)
    considered = sum((item['status'] == OUTAGE_CONSIDERED for item in planned_outages))
    skipped = len(planned_outages) - considered
    outage_status = 'PASS' if considered and skipped == 0 else 'WARNING'
    payload['ScriptedModelQuality'].append({'check_id': 'planned_outages', 'check_name': 'Planned outage applicability', 'status': outage_status, 'message': '{} found; {} in scope; {} skipped.'.format(len(planned_outages), considered, skipped), 'affected_element': '-'})
    _model_quality(payload, results, lodf)
    _case_metrics(payload, results)
    _pies(payload, results)
    _reference_exceeded(payload, results)
    _case_counts(payload, results)
    _radar(payload, results)
    _line_bars(payload, results)
    _trends(payload, results)
    _lodf_ranking(payload, results, lodf)
    _top_lines_by_case(payload, results)
    _loading_appendix(payload, results, 'line', 'ScriptedAppendixLine')
    _loading_appendix(payload, results, 'transformer', 'ScriptedAppendixTransformer')
    _voltage_appendix(payload, results)
    _enforce_table_limits(payload)
    return payload

def coerce_value(value, kind, where, field=None):
    if value is None:
        return None
    if kind == 'string':
        return clip_text(value, text_limit(field) if field else MAX_TEXT_LENGTH)
    if type(value) is bool:
        raise ValueError(where + ': boolean is not a numeric value')
    if kind == 'integer':
        numeric = finite_number(value)
        if numeric is None or not numeric.is_integer():
            raise ValueError(where + ': invalid integer ' + repr(value))
        result = int(numeric)
        if not -2 ** 31 <= result < 2 ** 31:
            raise ValueError(where + ': integer outside 32-bit range')
        return result
    if kind == 'number':
        result = finite_number(value)
        if result is None:
            raise ValueError(where + ': invalid finite number ' + repr(value))
        return result
    raise ValueError(where + ': unsupported type ' + repr(kind))

def api_error_code(value):
    if value is None:
        return None
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    code = finite_number(value)
    if code is None or code == 0.0:
        return None
    return code

def validate_payload(payload):
    expected = {name for name, _ in TABLES}
    if set(payload) != expected:
        raise ValueError('Internal table declaration and payload do not match.')
    if set(REQUIRED_FIELDS) != expected:
        raise ValueError('Required-field declaration does not cover all tables.')
    for name, fields in TABLES:
        rows = payload[name]
        if not isinstance(rows, list):
            raise ValueError(name + ': rows must be a list')
        if name == 'ScriptedReportMeta' and len(rows) != 1:
            raise ValueError(name + ': exactly one row is required')
        field_names = {field for field, _ in fields}
        for index, row in enumerate(rows):
            unknown = set(row) - field_names
            if unknown:
                raise ValueError(name + ': unknown fields ' + repr(sorted(unknown)))
            required = REQUIRED_FIELDS[name]
            for field, kind in fields:
                where = '{} row {}.{}'.format(name, index, field)
                if field in row and row[field] is not None:
                    row[field] = coerce_value(row[field], kind, where, field)
                if field not in required:
                    continue
                value = row.get(field)
                if value is None:
                    raise ValueError(where + ': required field is missing')
                if kind == 'string' and (not str(value).strip()):
                    raise ValueError(where + ': required text is empty')
    for table in TREND_TABLES:
        if len({row.get('element_name') for row in payload[table]}) > 1:
            raise ValueError('{} mixes several elements in one chart.'.format(table))

def _check(returned, context):
    code = api_error_code(returned)
    if code is not None:
        raise RuntimeError('{} returned error code {:g}'.format(context, code))

def publish_report(report, payload, log=None):
    started = time.monotonic()
    last_message = started

    def emit(message):
        nonlocal last_message
        if log:
            log(message)
        last_message = time.monotonic()

    def heartbeat(phase, table, completed, total, unit, rows=None):
        # Stay on the PowerFactory thread. A blocking API call must return
        # before progress can be reported; this is not a background timer.
        if not log:
            return
        now = time.monotonic()
        if now - last_message < PUBLICATION_LOG_INTERVAL_SECONDS:
            return
        row_progress = '{} / {} rows complete; '.format(*rows) if rows else ''
        emit('Publication heartbeat: {} [{}]; {}{} / {} {}; '
             '{:.1f}s since publication started.'.format(
                 table, phase, row_progress, completed, total, unit,
                 now - started))

    emit('Validating report tables before publication.')
    validate_payload(payload)
    emit('Report table validation completed in {:.1f}s.'.format(
        time.monotonic() - started))
    if report is None or class_name(report) != 'IntReport':
        raise RuntimeError('Run this ComPython as a child of an IntReport.')
    for method in ('Reset', 'CreateTable', 'CreateField', 'SetValue'):
        if not callable(getattr(report, method, None)):
            raise RuntimeError('IntReport is missing method ' + method)
    cell_counts = {
        name: sum(row.get(field) is not None
                  for row in payload[name] for field, _ in fields)
        for name, fields in TABLES
    }
    total_cells = sum(cell_counts.values())
    total_rows = sum(len(rows) for rows in payload.values())
    emit('Publishing {} validated report tables: {} rows, {} cell writes. '
         'Progress interval: {:g}s between API calls; a blocking call can '
         'delay the next message.'.format(
             len(TABLES), total_rows, total_cells,
             PUBLICATION_LOG_INTERVAL_SECONDS))
    context = 'Reset'
    try:
        emit('Resetting report database.')
        reset_started = time.monotonic()
        report.Reset()
        emit('Report database reset completed in {:.1f}s.'.format(
            time.monotonic() - reset_started))
        for table_index, (name, fields) in enumerate(TABLES, 1):
            if not name.startswith(HOST_TABLE_PREFIX):
                raise ValueError('Table lacks host prefix: ' + name)
            native_name = name[len(HOST_TABLE_PREFIX):]
            row_count = len(payload[name])
            cell_count = cell_counts[name]
            emit('Table {}/{}: {} -> {}: {} rows, {} cell writes; '
                 'creating table.'.format(
                     table_index, len(TABLES), native_name, name,
                     row_count, cell_count))
            table_started = time.monotonic()
            context = 'CreateTable({})'.format(native_name)
            _check(report.CreateTable(native_name), context)
            emit('Table {} created in {:.1f}s; creating {} fields.'.format(
                native_name, time.monotonic() - table_started, len(fields)))
            fields_started = time.monotonic()
            for field_index, (field, kind) in enumerate(fields, 1):
                context = 'CreateField({}.{})'.format(native_name, field)
                _check(report.CreateField(native_name, field, FIELD_TYPES[kind]), context)
                heartbeat('CREATE FIELDS', native_name, field_index,
                          len(fields), 'fields')
            emit('Table {} fields created in {:.1f}s; writing {} cells.'.format(
                native_name, time.monotonic() - fields_started, cell_count))
            write_started = time.monotonic()
            written = 0
            for index, row in enumerate(payload[name]):
                for field, _ in fields:
                    value = row.get(field)
                    if value is None:
                        continue
                    context = 'SetValue({}.{}, row {})'.format(native_name, field, index)
                    _check(report.SetValue(native_name, field, index, value), context)
                    written += 1
                    heartbeat('WRITE CELLS', native_name, written, cell_count,
                              'cells', rows=(index, row_count))
            write_seconds = time.monotonic() - write_started
            rate = '{:.1f} cells/s'.format(written / write_seconds) if written and write_seconds > 0 else 'n/a'
            emit('GridLens: {} -> {}: {} rows, {} cells; writes {:.1f}s '
                 '({}); table total {:.1f}s.'.format(
                     native_name, name, row_count, written, write_seconds,
                     rate, time.monotonic() - table_started))
    except Exception as exc:
        try:
            report.Reset()
        except Exception:
            pass
        raise RuntimeError('GridLens publication failed at ' + context) from exc
    emit('Publication finished: {} tables, {} rows, {} cells in {:.1f}s.'.format(
        len(TABLES), total_rows, total_cells, time.monotonic() - started))
    return {name: len(rows) for name, rows in payload.items()}


TOTAL_STEPS = 7
OUTAGE_CLASSES = ("IntPlannedout", "IntOutage")
# PowerFactory describes this ComStatsim option as "Planned Outages". Setting
# it is how planned outages are applied; IntPlannedout exposes no Apply method.
PLANNED_OUTAGE_OPTION = "iopt_maint"
OUTAGE_CONSIDERED = "CONSIDERED"
ASSESSMENT_OK = "NO LIMIT EXCEEDED"
ASSESSMENT_PREEXISTING = "NO ADDITIONAL VIOLATION"
ASSESSMENT_LOADING = "OVERLOAD"
ASSESSMENT_VOLTAGE = "VOLTAGE BAND"
ASSESSMENT_BOTH = "OVERLOAD + VOLTAGE BAND"
ASSESSMENT_SKIPPED = "NOT SIMULATED"
ASSESSMENT_NO_DATA = "NO RESULT DATA IN WINDOW"
ASSESSMENT_NOT_EVALUATED = "NOT EVALUATED"
LOADING_CATEGORIES = ("line", "transformer")
OUTAGE_SKIPPED = "SKIPPED"
OUTAGE_START_ATTRIBUTES = (
    "starttime", "tStart", "t_start", "date_start", "time_start")
OUTAGE_END_ATTRIBUTES = (
    "endtime", "tEnd", "t_end", "date_end", "time_end")
# PowerFactory labels IntPlannedout.components "Components"; it holds the
# equipment the outage switches. The remaining names are legacy fallbacks.
OUTAGE_EQUIPMENT_ATTRIBUTES = (
    "components", "p_target", "pTarget", "pObject", "p_object", "obj_id",
    "pDevice", "cpObject", "pElm", "p_target1", "p_target2")
# ComStatsim carries the simulated period as epoch seconds.
QDS_PERIOD_ATTRIBUTES = (("startTime", "endTime"), ("starttime", "endtime"))
REFERENCE_CASE_ID = "REF"
OUTAGE_CASE_PREFIX = "OUT"
QDS_CORE_SETTINGS = (
    ("Time period", "calcPeriod"),
    ("Step size", "stepSize"),
    ("Step unit", "stepUnit"),
)
QDS_OPTION_ATTRIBUTES = (
    "iopt_asht", "iopt_at", "iopt_circ", "iopt_cont", "iopt_ctrl",
    "iopt_event", "iopt_fast", "iopt_lim", "iopt_lod", "iopt_method",
    "iopt_net", "iopt_plim", "iopt_pq", "iopt_prot", "iopt_show",
    "iopt_stamode", "iopt_tem", "iopt_time",
)


class GridLensError(RuntimeError):
    """Expected runtime error with an actionable user-facing message."""


class RunLogger:
    """Structured progress output for the PowerFactory output window."""

    def __init__(self, app):
        self.app = app
        self.started = time.monotonic()

    def write(self, stage, message, step=None, level="INFO"):
        position = "--/{}".format(TOTAL_STEPS)
        if step is not None:
            position = "{:02d}/{}".format(step, TOTAL_STEPS)
        elapsed = time.monotonic() - self.started
        line = "[GridLens][{}][{}][{}][{:7.1f}s] {}".format(
            position, level, stage, elapsed, message)
        printer = getattr(self.app, "PrintPlain", None)
        if callable(printer):
            try:
                printer(line)
                return
            except Exception:
                pass
        print(line, flush=True)


def _call_without_or_with_zero(method):
    try:
        return method()
    except TypeError:
        return method(0)


def _declared_attributes(obj):
    """Name and value of every attribute the object itself declares."""
    names = []
    for getter_name in ("GetAttributes", "GetAttributeNames"):
        getter = safe_attr(obj, getter_name)
        if not callable(getter):
            continue
        try:
            returned = _call_without_or_with_zero(getter)
        except Exception:
            continue
        names = sorted({str(item).strip() for item in returned or ()
                        if str(item).strip()})
        if names:
            break
    described = []
    for name in names:
        value = safe_attr(obj, name)
        if callable(value):
            continue
        described.append("{}={}".format(
            name, clip_text(value, MAX_LABEL_LENGTH) if value is not None else ""))
    return described


def describe_object_api(obj):
    """Report which callables and parameters a PowerFactory object exposes."""
    methods = []
    parameters = []
    try:
        names = sorted(dir(obj))
    except Exception:
        names = []
    for name in names:
        if name.startswith("_"):
            continue
        member = safe_attr(obj, name)
        if member is None:
            continue
        target = methods if callable(member) else parameters
        target.append(name)
    parts = [
        "class={}".format(class_name(obj) or "unknown"),
        "methods: {}".format(", ".join(methods) or "none visible"),
        "parameters: {}".format(", ".join(parameters) or "none visible"),
    ]
    declared = _declared_attributes(obj)
    if declared:
        parts.append("declared attributes: {}".format(", ".join(declared)))
    return clip_text("; ".join(parts), MAX_DIAGNOSTIC_LENGTH)


def _same_object(left, right):
    if left is right:
        return True
    if left is None or right is None:
        return False
    return object_key(left) == object_key(right)


def _set_attribute(obj, name, value):
    try:
        setattr(obj, name, value)
    except Exception:
        setter = getattr(obj, "SetAttribute", None)
        if not callable(setter):
            return False
        setter(name, value)
    return _same_object(safe_attr(obj, name), value)


def _as_objects(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item is not None]
    return [value]


def _format_pf_time(value):
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value.strip()
    numeric = finite_number(value)
    if numeric is None:
        return str(value)
    if numeric > 315532800:
        # Compact local time: the report cells are narrow and the time-axis
        # labels already read this way.
        try:
            return datetime.fromtimestamp(numeric).strftime("%Y-%m-%d %H:%M")
        except (OSError, OverflowError, ValueError):
            pass
    return "{:g}".format(numeric)


def _first_attribute(obj, names):
    for name in names:
        value = safe_attr(obj, name)
        if value not in (None, "", []):
            return value
    return None


def _outage_details(outage):
    """Collect display-only outage context without exposing full PF paths."""
    related = []
    for attribute in OUTAGE_EQUIPMENT_ATTRIBUTES:
        related.extend(_as_objects(safe_attr(outage, attribute)))
    try:
        children = outage.GetContents("*", 1) or []
    except TypeError:
        try:
            children = outage.GetContents("*") or []
        except Exception:
            children = []
    except Exception:
        children = []
    actions = []
    for child in children:
        child_class = class_name(child)
        child_name = object_name(child)
        if child_class.startswith(("Evt", "Sta", "Int")):
            actions.append("{} {}".format(child_class, child_name).strip())
        for attribute in OUTAGE_EQUIPMENT_ATTRIBUTES:
            related.extend(_as_objects(safe_attr(child, attribute)))
    equipment = []
    seen = set()
    for item in related:
        if isinstance(item, (str, int, float, bool)):
            continue
        key = object_key(item)
        if key in seen or item is outage:
            continue
        seen.add(key)
        equipment.append((class_name(item), object_name(item)))
    equipment.sort(key=lambda entry: (entry[1].casefold(), entry[0]))
    equipment_names = ", ".join(name for _, name in equipment)
    equipment_types = ", ".join(sorted({kind for kind, _ in equipment if kind}))
    action_text = "; ".join(sorted(set(actions)))
    if not action_text:
        action_text = object_description(outage)
    start = _first_attribute(outage, OUTAGE_START_ATTRIBUTES)
    end = _first_attribute(outage, OUTAGE_END_ATTRIBUTES)
    return equipment_names, equipment_types, action_text, _format_pf_time(start), _format_pf_time(end)


def _find_project_outages(app):
    """Return unique planned outages from the operational-library folder."""
    roots = []
    getter = getattr(app, "GetProjectFolder", None)
    if callable(getter):
        for key in ("outage", "outages"):
            try:
                roots.extend(_as_objects(getter(key)))
            except Exception:
                pass
    try:
        roots.extend(_as_objects(app.GetActiveProject()))
    except Exception:
        pass
    found = []
    successful_queries = 0
    for root in roots:
        for outage_class in OUTAGE_CLASSES:
            pattern = "*.{}".format(outage_class)
            try:
                values = root.GetContents(pattern, 1) or []
                successful_queries += 1
            except TypeError:
                try:
                    values = root.GetContents(pattern) or []
                    successful_queries += 1
                except Exception:
                    values = []
            except Exception:
                values = []
            found.extend(values)
    if successful_queries == 0:
        raise GridLensError(
            "Planned-outage discovery could not query the operational library "
            "or active project. No calculation was started.")
    unique = {}
    for outage in found:
        if class_name(outage) in OUTAGE_CLASSES:
            unique[object_key(outage)] = outage
    return sorted(unique.values(), key=lambda item: (
        object_name(item).casefold(), class_name(item), object_key(item)))


BRANCH_CLASSES = ("ElmLne", "ElmTr2", "ElmTr3", "ElmCoup")


def outage_branches(outage):
    """Branches an outage switches off, from its components and its actions."""
    related = []
    holders = [outage]
    try:
        holders += list(outage.GetContents("*", 1) or [])
    except Exception:
        pass
    for holder in holders:
        for attribute in OUTAGE_EQUIPMENT_ATTRIBUTES:
            related.extend(_as_objects(safe_attr(holder, attribute)))
    unique = {}
    for item in related:
        if class_name(item) in BRANCH_CLASSES:
            unique[object_key(item)] = item
    return list(unique.values())


def _outage_record(outage):
    equipment, equipment_type, actions, start, end = _outage_details(outage)
    branches = outage_branches(outage)
    return {
        "branches": branches,
        "equipment_keys": [object_key(item) for item in branches],
        "id": object_name(outage),
        "name": object_name(outage),
        "source_class": class_name(outage),
        "status": "PENDING",
        "skip_reason": "",
        "equipment_name": equipment,
        "equipment_type": equipment_type,
        "switching_actions": actions,
        "start_time": start,
        "end_time": end,
        "priority": finite_number(safe_attr(outage, "priority", 0)) or 0,
        "window": outage_window(outage),
        "window_index": None,
        "_object": outage,
    }


def outage_window(outage):
    """The outage's (start, end) in epoch seconds, where PowerFactory has them."""
    start = finite_number(_first_attribute(outage, OUTAGE_START_ATTRIBUTES))
    end = finite_number(_first_attribute(outage, OUTAGE_END_ATTRIBUTES))
    return start, end


def window_overlaps_period(window, period):
    """True or False when both are readable, None when the answer is unknown."""
    start, end = window
    begin, finish = period
    if begin is None or finish is None:
        return None
    if start is None and end is None:
        return None
    if start is not None and start > finish:
        return False
    if end is not None and end < begin:
        return False
    return True


def classify_planned_outages(app, logger, period=(None, None)):
    """Report which planned outages PowerFactory will apply for this period.

    GridLens never applies an outage itself. PowerFactory does that during the
    calculation once PLANNED_OUTAGE_OPTION is set, driven by each outage's own
    time window. This pass only decides what to tell the reader, and whether an
    outage run is worth starting at all.
    """
    objects = _find_project_outages(app)
    records = [_outage_record(item) for item in objects]
    names = {}
    for record in records:
        names[record["name"]] = names.get(record["name"], 0) + 1
    for record in records:
        if names[record["name"]] > 1:
            record["id"] = "{} ({})".format(
                record["name"], _key_discriminator(object_key(record["_object"])))
    logger.write(
        "OUTAGES", "Found {} planned outage object(s).".format(len(records)), 3)
    candidates = []
    for index, record in enumerate(records, 1):
        outage = record["_object"]
        prefix = "Outage {}/{} '{}': ".format(index, len(records), record["name"])
        if finite_number(safe_attr(outage, "outserv", 0)) == 1.0:
            record["status"] = OUTAGE_SKIPPED
            record["skip_reason"] = "Outage object is disabled (outserv=1)."
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        window = outage_window(outage)
        overlap = window_overlaps_period(window, period)
        if overlap is False:
            record["status"] = OUTAGE_SKIPPED
            record["skip_reason"] = (
                "Outage window {} to {} lies outside the simulated period "
                "{} to {}.".format(
                    _format_pf_time(window[0]), _format_pf_time(window[1]),
                    _format_pf_time(period[0]), _format_pf_time(period[1])))
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        record["status"] = OUTAGE_CONSIDERED
        if overlap is True:
            record["skip_reason"] = ""
            logger.write(
                "OUTAGES",
                prefix + "window {} to {} overlaps the simulated period; "
                "PowerFactory will apply it.".format(
                    _format_pf_time(window[0]), _format_pf_time(window[1])), 3)
        else:
            record["skip_reason"] = (
                "The outage window could not be compared with the simulated "
                "period; PowerFactory decides whether it applies.")
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            logger.write(
                "DIAGNOSTIC", prefix + describe_object_api(outage), 3, "WARNING")
        record["window_index"] = len(candidates)
        candidates.append(record)
    return records, candidates


def qds_period(qds):
    """The simulated period in epoch seconds, as ComStatsim declares it."""
    for start_name, end_name in QDS_PERIOD_ATTRIBUTES:
        start = finite_number(safe_attr(qds, start_name))
        end = finite_number(safe_attr(qds, end_name))
        if start is not None and end is not None and end >= start:
            return start, end
    return None, None


def _restore_planned_outage_option(qds, original, logger):
    if not _set_scalar_attribute(qds, PLANNED_OUTAGE_OPTION, original):
        return ["the 'Planned Outages' option ({}) could not be restored to {}"
                .format(PLANNED_OUTAGE_OPTION, _format_setting_value(original))]
    logger.write(
        "RESTORE", "Restored the 'Planned Outages' option [{}] to {}.".format(
            PLANNED_OUTAGE_OPTION, _format_setting_value(original)), 6)
    return []


def _temporary_result(study_case, template, case_id):
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    name = "{}TMP_{}_{}".format(SNAPSHOT_PREFIX, stamp, case_id)
    snapshot = None
    if template is not None:
        copier = getattr(study_case, "AddCopy", None)
        if callable(copier):
            try:
                copies = _as_objects(copier(template))
                snapshot = copies[0] if copies else None
            except Exception:
                snapshot = None
        if snapshot is None:
            copier = getattr(study_case, "CopyObject", None)
            if callable(copier):
                try:
                    copies = _as_objects(copier(template, name))
                    snapshot = copies[0] if copies else None
                except Exception:
                    snapshot = None
    if snapshot is None:
        raise GridLensError(
            "PowerFactory could not copy the configured ElmRes for case {}. "
            "The calculation was not started because a new empty ElmRes would "
            "lose the configured result-variable selection.".format(case_id))
    try:
        snapshot.loc_name = name
    except Exception:
        try:
            snapshot.SetAttribute("loc_name", name)
        except Exception as exc:
            try:
                snapshot.Delete()
            except Exception:
                pass
            raise GridLensError(
                "PowerFactory could not name the temporary ElmRes: {}".format(
                    _friendly_exception(exc))) from None
    if object_name(snapshot) != name:
        try:
            snapshot.Delete()
        except Exception:
            pass
        raise GridLensError("PowerFactory did not retain the temporary ElmRes name.")
    return snapshot


def _run_calculation(app, study_case, qds, case_id, name, description,
                     original_result, logger, temporary_results, windows=(),
                     outage=None):
    snapshot = _temporary_result(study_case, original_result, case_id)
    temporary_results.append(snapshot)
    if not _set_attribute(qds, "results", snapshot):
        raise GridLensError(
            "PowerFactory did not bind ComStatsim.results to the temporary "
            "ElmRes. No calculation was started.")
    logger.write(
        "CALCULATION",
        "Starting {} with the active ComStatsim settings; only the "
        "'Planned Outages' option and the outage's own 'Ignored' flag "
        "differ between the cases.".format(case_id), 4)
    logger.write(
        "CALCULATION",
        "PowerFactory is calculating {}. This blocking API call may take "
        "several minutes; intermediate progress is controlled by PowerFactory."
        .format(case_id), 4)
    started = time.monotonic()
    try:
        returned = qds.Execute()
    except Exception as exc:
        raise GridLensError(
            "{} calculation was interrupted or failed: {}".format(
                case_id, _friendly_exception(exc))) from None
    elapsed = time.monotonic() - started
    code = return_code(returned)
    if code is None or code != 0.0:
        raise GridLensError(
            "{} calculation ended after {:.1f}s with {}. Review the "
            "PowerFactory calculation messages and QDS configuration.".format(
                case_id, elapsed,
                "an unreadable return value" if code is None
                else "error code {:g}".format(code)))
    if not _same_object(safe_attr(qds, "results"), snapshot):
        raise GridLensError(
            "ComStatsim.results changed during {}. Results were rejected."
            .format(case_id))
    logger.write(
        "CALCULATION", "{} completed successfully in {:.1f}s.".format(
            case_id, elapsed), 4)
    logger.write("EXTRACTION", "Reading and validating {} results.".format(case_id), 5)
    try:
        snapshot.Load()
        counters = {}
        series, labels, plot_times, unit, absolute, origin = collect_series(
            snapshot, windows, counters)
        if GRID_NAME_FILTER:
            logger.write(
                "EXTRACTION",
                "Grid scope {!r}: {} series assessed, {} out of scope and "
                "not read.".format(GRID_NAME_FILTER, len(series),
                                   counters.get('out_of_scope', 0)), 5)
        logger.write(
            "EXTRACTION",
            "Validated {} supported series across {} time point(s); time unit '{}'."
            .format(len(series), len(labels), unit), 5)
        logger.write(
            "EXTRACTION",
            "Time axis: {} scale, unit '{}'; first {}; last {}; span {}."
            .format("absolute" if absolute else "relative",
                    unit, labels[0], labels[-1],
                    '{:g} h'.format(plot_times[-1] - plot_times[0])), 5)
    except Exception as exc:
        raise GridLensError(
            "{} completed, but its ElmRes could not be evaluated: {}".format(
                case_id, _friendly_exception(exc))) from None
    finally:
        try:
            snapshot.Release()
        except Exception:
            pass
    case = {
        "id": case_id,
        "name": name,
        "kind": "reference" if case_id == REFERENCE_CASE_ID else "planned_outage",
        "description": description,
        "status": CONVERGED,
        "error_code": 0,
        "message": "Completed in {:.1f}s.".format(elapsed),
        "counters": counters,
        "outage": outage,
    }
    result = case_result(case, series, labels, plot_times, unit)
    result["window"] = ((None, None) if origin is None else
                        (origin * 3600.0, (origin + plot_times[-1]) * 3600.0))
    return result


def _delete_temporary_results(temporary_results, logger):
    errors = []
    for result in reversed(temporary_results):
        name = object_name(result)
        try:
            returned = result.Delete()
            code = return_code(returned)
            if code is None or code != 0.0:
                raise GridLensError(
                    "Delete returned {}".format(
                        "an unreadable value" if code is None
                        else "error code {:g}".format(code)))
            logger.write("CLEANUP", "Deleted temporary result '{}'.".format(name), 6)
        except Exception as exc:
            errors.append("{}: {}".format(name, _friendly_exception(exc)))
    return errors


def _restore_results_binding(qds, original_result):
    if not _set_attribute(qds, "results", original_result):
        return ["ComStatsim.results could not be restored to its original object."]
    return []


def _read_setting(obj, attribute):
    try:
        return True, getattr(obj, attribute)
    except Exception:
        getter = getattr(obj, "GetAttribute", None)
        if callable(getter):
            try:
                return True, getter(attribute)
            except Exception:
                pass
    return False, None


def _format_setting_value(value):
    if type(value) is bool:
        return "true" if value else "false"
    numeric = finite_number(value)
    if numeric is not None:
        return "{:g}".format(numeric)
    if class_name(value):
        return "'{}' ({})".format(object_name(value), class_name(value))
    if isinstance(value, (list, tuple)):
        return "[{}]".format(
            ", ".join(_format_setting_value(item) for item in value))
    return str(value)


def _format_study_time(date_value, time_value):
    date_number = finite_number(date_value)
    time_number = finite_number(time_value)
    if date_number is None or time_number is None:
        return "date={}, time={}".format(date_value, time_value)
    date_text = "{:08d}".format(int(date_number))
    # PowerFactory stores SetTime.cTime as HHMMSS: 230000 is 23:00:00.
    time_text = "{:06d}".format(int(time_number))
    return "{}-{}-{} {}:{}:{}".format(
        date_text[0:4], date_text[4:6], date_text[6:8],
        time_text[0:2], time_text[2:4], time_text[4:6])


def _capture_study_time(app):
    try:
        study_time = app.GetFromStudyCase("SetTime")
    except Exception as exc:
        raise GridLensError(
            "The initial Study Case date/time could not be accessed: {}. No "
            "calculation was started.".format(_friendly_exception(exc))) from None
    if study_time is None:
        raise GridLensError(
            "No SetTime object was found in the active Study Case. GridLens "
            "cannot guarantee restoration of the Study Case clock, so no "
            "calculation was started.")
    date_found, date_value = _read_setting(study_time, "cDate")
    time_found, time_value = _read_setting(study_time, "cTime")
    if not date_found or not time_found:
        raise GridLensError(
            "SetTime.cDate or SetTime.cTime is unavailable. GridLens cannot "
            "guarantee restoration of the Study Case clock, so no calculation "
            "was started.")
    return {
        "object": study_time,
        "date": date_value,
        "time": time_value,
    }


def _set_scalar_attribute(obj, attribute, value):
    try:
        setattr(obj, attribute, value)
    except Exception:
        setter = getattr(obj, "SetAttribute", None)
        if not callable(setter):
            return False
        try:
            setter(attribute, value)
        except Exception:
            return False
    found, restored = _read_setting(obj, attribute)
    if not found:
        return False
    left = finite_number(restored)
    right = finite_number(value)
    if left is not None and right is not None:
        return left == right
    return restored == value


def _restore_study_time(state, logger, stage="RESTORE", step=6):
    errors = []
    study_time = state["object"]
    if not _set_scalar_attribute(study_time, "cDate", state["date"]):
        errors.append("SetTime.cDate could not be restored and verified.")
    if not _set_scalar_attribute(study_time, "cTime", state["time"]):
        errors.append("SetTime.cTime could not be restored and verified.")
    if not errors:
        logger.write(
            stage,
            "Restored Study Case time to {}.".format(
                _format_study_time(state["date"], state["time"])), step)
    return errors


def _log_qds_settings(qds, result, study_time_state, logger):
    logger.write(
        "SETTINGS",
        "Active ComStatsim settings; GridLens changes only the 'Planned "
        "Outages' option and restores it:", 2)
    for label, attribute in QDS_CORE_SETTINGS:
        found, value = _read_setting(qds, attribute)
        rendered = _format_setting_value(value) if found else "<not exposed>"
        logger.write(
            "SETTINGS",
            "{} [{}] = {}".format(label, attribute, rendered), 2)
    option_names = set(QDS_OPTION_ATTRIBUTES)
    try:
        option_names.update(
            name for name in dir(qds) if name.startswith("iopt_"))
    except Exception:
        pass
    options = []
    for attribute in sorted(option_names):
        found, value = _read_setting(qds, attribute)
        if found:
            options.append("{}={}".format(
                attribute, _format_setting_value(value)))
    logger.write(
        "SETTINGS",
        "Calculation options: {}".format(
            ", ".join(options) if options else "<no exposed iopt_* attributes>"),
        2)
    period_start, period_end = qds_period(qds)
    if period_start is not None:
        logger.write(
            "SETTINGS",
            "Simulated period [startTime..endTime] = {} .. {}".format(
                _format_pf_time(period_start), _format_pf_time(period_end)), 2)
    else:
        logger.write(
            "SETTINGS",
            "Simulated period is not exposed by this ComStatsim; planned "
            "outages will be judged against the reference time axis.", 2)
    for attribute in ("iopt_maint", "ciopt_maint", "iopt_action", "iopt_rep"):
        found, value = _read_setting(qds, attribute)
        if found:
            logger.write(
                "SETTINGS", "Planned outages [{}] = {}".format(
                    attribute, _format_setting_value(value)), 2)
    logger.write(
        "SETTINGS",
        "Result object [results] = '{}' ({})".format(
            object_name(result), class_name(result) or "ElmRes"), 2)
    logger.write(
        "SETTINGS",
        "Initial Study Case time: {}".format(_format_study_time(
            study_time_state["date"], study_time_state["time"])), 2)


def _friendly_exception(exc):
    if exc is None:
        return "unknown error"
    messages = []
    current = exc
    seen = set()
    while current is not None and id(current) not in seen and len(messages) < 3:
        seen.add(id(current))
        text = str(current).strip()
        label = type(current).__name__
        messages.append("{}: {}".format(label, text) if text else label)
        if current.__cause__ is not None:
            current = current.__cause__
        elif not current.__suppress_context__:
            current = current.__context__
        else:
            current = None
    return " -> ".join(messages)


def _generated_by():
    try:
        value = getpass.getuser()
    except Exception:
        value = ""
    return value or os.environ.get("USERNAME") or os.environ.get("USER") or "Unknown user"


class StateRestoreError(GridLensError):
    """A setting changed by GridLens could not be put back."""


def _same_setting(current, original):
    left, right = finite_number(current), finite_number(original)
    return left == right if left is not None and right is not None else current == original


class StateGuard:
    """Change PowerFactory settings temporarily and always put them back.

    Every value is recorded before it is written. Leaving the block restores
    all of them in reverse order and reads each one back; a setting that cannot
    be restored raises StateRestoreError naming the expected and the found value.
    """

    def __init__(self):
        self._changes = []

    def set(self, obj, attribute, value, label):
        """Write `value`; False when it cannot be written and read back."""
        known, original = _read_setting(obj, attribute)
        if not known:
            return False
        self._changes.append((obj, attribute, original, label))
        return _set_scalar_attribute(obj, attribute, value)

    def restore(self):
        errors = []
        for obj, attribute, original, label in reversed(self._changes):
            known, current = _read_setting(obj, attribute)
            if known and _same_setting(current, original):
                continue
            if not _set_scalar_attribute(obj, attribute, original):
                known, current = _read_setting(obj, attribute)
                errors.append("{}: expected {}, read back {}".format(
                    label, _format_setting_value(original),
                    _format_setting_value(current) if known else "unreadable"))
        self._changes = []
        return errors

    def __enter__(self):
        return self

    def __exit__(self, kind, failure, _unused):
        errors = self.restore()
        if errors:
            message = ("PowerFactory state restoration failed. Verify the Study Case manually: "
                       + "; ".join(errors))
            if failure is not None:
                message += ". The calculation had stopped before with: " + _friendly_exception(failure)
            raise StateRestoreError(message) from failure
        return False


# ---------------------------------------------------------------------------
# Line outage distribution factors (LODF)
#
# PowerFactory's own tool "Sensitivities / Distribution Factors" (ComVstab)
# calculates them. For every contingency (ComOutage) of a Contingency Analysis
# (ComSimoutage) it writes, per line, by how much the line's flow changes related
# to the flow the switched equipment carried before. The result is one row per
# contingency with a solution in the ElmRes whose name ends with _LODF:
#   b:outid        negative number; ElmRes.GetObj(outid) is the contingency
#   m:LODF:bus1    LODF of one line in %, at its bus1 side
# GridLens creates its own Contingency Analysis, links the command to it for the
# run, restores every setting and deletes what it created. A failure is a
# warning: the ranking then uses the measured loading change.
# ---------------------------------------------------------------------------
LODF_VARIABLE = "m:LODF:bus1"
LODF_OUTAGE_ID_VARIABLE = "b:outid"
LODF_RESULT_SUFFIX = "_LODF"
LODF_RECORD_ALL = 0
LODF_RUN_SETTINGS = (("isContSens", 1), ("calcLodf", 1), ("lodflim", LODF_RECORD_ALL))
LODF_OPTIONAL_SETTINGS = ("isContSens",)
LODF_ANALYSIS_NAME = "GridLens LODF"
LODF_MAX_TABLE_ROWS = 50
CALCULATE_LODF = True
LODF_CLEAN_UP = True


class LodfError(RuntimeError):
    """The LODF could not be calculated; PowerFactory settings were restored."""


def _contents(holder, class_pattern):
    try:
        return list(holder.GetContents("*." + class_pattern, 1) or [])
    except Exception:
        return []


def _lodf_create(parent, class_pattern, name):
    try:
        created = parent.CreateObject(class_pattern, name)
    except Exception as exc:
        raise LodfError("PowerFactory could not create '{}.{}' in '{}': {}".format(
            name, class_pattern, object_name(parent), exc)) from None
    if created is None:
        raise LodfError("PowerFactory could not create '{}.{}' in '{}'.".format(
            name, class_pattern, object_name(parent)))
    return created


def contingency_keys(contingency):
    """Keys of the equipment a contingency switches off, read from its table."""
    found = []
    getter = getattr(contingency, "GetObject", None)
    for line in range(LODF_MAX_TABLE_ROWS if callable(getter) else 0):
        try:
            item = getter(line)
        except Exception:
            break
        if item is None:
            break
        found.append(item)
    if not found:
        found = [item for item in _as_objects(safe_attr(contingency, "Elms"))
                 if not isinstance(item, (str, int, float, bool))]
    return frozenset(object_key(item) for item in found)


def _prepare_lodf(app, study_case, records, logger):
    """The command, our Contingency Analysis and one ComOutage per outage; returns them with what was created."""
    created = []
    distribution = next(iter(_contents(study_case, "ComVstab")), None)
    if distribution is None:
        distribution = app.GetFromStudyCase("ComVstab")
        if distribution is None:
            raise LodfError("PowerFactory could not provide the 'Sensitivities / Distribution Factors' "
                            "command (ComVstab) in Study Case '{}'.".format(object_name(study_case)))
        created.append(distribution)
    analysis = next((item for item in _contents(study_case, "ComSimoutage")
                     if object_name(item) == LODF_ANALYSIS_NAME), None)
    if analysis is None:
        analysis = _lodf_create(study_case, "ComSimoutage", LODF_ANALYSIS_NAME)
        created.append(analysis)
    else:
        try:
            analysis.ClearCont()
        except Exception as exc:
            raise LodfError("Contingency Analysis '{}' of an earlier run could not be emptied: {}".format(
                LODF_ANALYSIS_NAME, exc)) from None
    wanted = {}
    for record in records:
        keys = frozenset(record["equipment_keys"])
        if keys and keys not in wanted:
            wanted[keys] = record
    for keys, record in wanted.items():
        contingency = _lodf_create(analysis, "ComOutage", record["name"])
        try:
            code = contingency.SetObjs(list(record["branches"]))
        except Exception as exc:
            raise LodfError("The equipment of '{}' could not be put into its contingency: {}".format(
                record["name"], exc)) from None
        if finite_number(code) not in (0, None) or contingency_keys(contingency) != keys:
            raise LodfError("Contingency '{}' does not list its equipment after SetObjs.".format(record["name"]))
    logger.write("LODF", "Created {} contingenc{} in '{}'.".format(
        len(wanted), "y" if len(wanted) == 1 else "ies", LODF_ANALYSIS_NAME), 3)
    return distribution, analysis, created


def _lodf_result(distribution):
    known, result = _read_setting(distribution, "pResult")
    if not known or result is None or isinstance(result, (str, int, float, bool)):
        return None
    for child in _contents(result, "ElmRes"):
        if object_name(child).endswith(LODF_RESULT_SUFFIX):
            return child
    return None


def _read_lodf_matrix(result):
    """[(contingency, {line key: (line name, LODF as fraction)})] for every contingency with a solution."""
    try:
        result.Load()
        rows, columns = int(result.GetNumberOfRows()), int(result.GetNumberOfColumns())
    except Exception as exc:
        raise LodfError("The LODF result file could not be read: {}".format(exc)) from None
    try:
        outage_column, lines = None, {}
        for column in range(columns):
            variable = str(result.GetVariable(column))
            if variable == LODF_OUTAGE_ID_VARIABLE:
                outage_column = column
            elif variable == LODF_VARIABLE:
                lines[column] = result.GetObject(column)
        if outage_column is None or not lines:
            raise LodfError("The LODF result file has no '{}' column or no '{}' columns ({} columns found)."
                            .format(LODF_OUTAGE_ID_VARIABLE, LODF_VARIABLE, columns))
        table = []
        for row in range(rows):
            outage_id = result_value(result, row, outage_column)
            try:
                contingency = result.GetObj(int(outage_id)) if outage_id is not None else None
            except Exception:
                contingency = None
            if contingency is None:
                continue
            values = {}
            for column, line in lines.items():
                value = result_value(result, row, column)
                if value is not None:
                    values[object_key(line)] = (object_name(line), value / 100.0)
            table.append((contingency, values))
        return table
    finally:
        try:
            result.Release()
        except Exception:
            pass


def _execute_lodf(distribution):
    """Run the command with LODF on and every value recorded, then put its settings back."""
    with StateGuard() as guard:
        for attribute, value in LODF_RUN_SETTINGS:
            if attribute in LODF_OPTIONAL_SETTINGS and not _read_setting(distribution, attribute)[0]:
                continue
            if not guard.set(distribution, attribute, value, "ComVstab." + attribute):
                raise LodfError("ComVstab.{} cannot be read or written; the LODF was not calculated.".format(attribute))
        try:
            code = distribution.Execute()
        except Exception as exc:
            raise LodfError("'Sensitivities / Distribution Factors' failed: {}".format(exc)) from None
        if return_code(code) != 0.0:
            raise LodfError("'Sensitivities / Distribution Factors' ended with error code {}.".format(code))
        result = _lodf_result(distribution)
        if result is None:
            raise LodfError("'Sensitivities / Distribution Factors' left no result file ending with '{}' "
                            "in ComVstab.pResult.".format(LODF_RESULT_SUFFIX))
        return _read_lodf_matrix(result)


def _clean_up_lodf(created, logger):
    for item in reversed(created):
        name = object_name(item)
        try:
            item.Delete()
        except Exception as exc:
            logger.write("LODF", "'{}' could not be deleted: {}".format(name, exc), 3, "WARNING")


def calculate_lodf(app, study_case, records, logger):
    """{outage id: {'values': {line key: (name, fraction)}, 'reason': text}} for every outage record.

    The LODF depends only on the topology, so it is calculated once before the
    first simulation. Whatever goes wrong is returned as the reason of every
    outage; only a setting that cannot be restored stops the run.
    """
    info = {record["id"]: {"values": {}, "reason": ""} for record in records}
    if not records:
        return info
    created = []
    try:
        if not any(record["equipment_keys"] for record in records):
            raise LodfError("None of the outages switches a line, transformer or coupler.")
        distribution, analysis, created = _prepare_lodf(app, study_case, records, logger)
        defined = {contingency_keys(item) for item in _contents(analysis, "ComOutage")} - {frozenset()}
        original = safe_attr(distribution, "pComSimoutage")
        if not _set_attribute(distribution, "pComSimoutage", analysis):
            raise LodfError("ComVstab.pComSimoutage cannot be set to '{}'.".format(LODF_ANALYSIS_NAME))
        solved = {}
        try:
            for contingency, values in _execute_lodf(distribution):
                keys = contingency_keys(contingency)
                if keys:
                    solved[keys] = values
        finally:
            if original is not None and not _same_object(original, analysis):
                if not _set_attribute(distribution, "pComSimoutage", original):
                    raise StateRestoreError("ComVstab.pComSimoutage could not be restored to '{}'. Verify the "
                                            "Study Case manually.".format(object_name(original)))
        for record in records:
            wanted = frozenset(record["equipment_keys"])
            if not wanted:
                info[record["id"]]["reason"] = "The outage switches no line, transformer or coupler."
            elif solved.get(wanted):
                info[record["id"]]["values"] = solved[wanted]
            elif wanted in solved:
                info[record["id"]]["reason"] = "PowerFactory recorded no value for this outage."
            elif wanted in defined:
                info[record["id"]]["reason"] = ("PowerFactory found no solution without this equipment "
                                                "(typically a generator or part of the grid is cut off).")
            else:
                info[record["id"]]["reason"] = "The outage is not part of the calculated contingencies."
    except LodfError as exc:
        for item in info.values():
            item["reason"] = str(exc)
        logger.write("LODF", "{} The ranking uses the measured loading change.".format(exc), 3, "WARNING")
    finally:
        if LODF_CLEAN_UP:
            _clean_up_lodf(created, logger)
    with_values = sum(1 for item in info.values() if item["values"])
    logger.write("LODF", "LODF available for {} of {} outage(s).".format(with_values, len(info)), 3)
    return info


def _isolate_outage(guard, active, records):
    """Let PowerFactory apply only `active`: every other outage gets its 'Ignored' flag (outserv) set."""
    for record in records:
        outage = record["_object"]
        wanted = 0 if outage is active else 1
        if not guard.set(outage, "outserv", wanted, "'Ignored' flag of outage '{}'".format(record["name"])):
            raise GridLensError(
                "The 'Ignored' flag (outserv) of outage '{}' could not be set, so '{}' cannot be "
                "calculated on its own.".format(record["name"], object_name(active)))


def _run_outage_case(app, study_case, qds, record, case_id, records,
                     original_result, logger, temporary_results, windows,
                     study_time_state):
    """One planned outage as its own case; a failure becomes a failed case, a restore failure stops the run."""
    case = {"id": case_id, "name": record["name"], "kind": "planned_outage",
            "description": "Only outage '{}' applied by PowerFactory.".format(record["name"]),
            "outage": record}
    logger.write("CALCULATION", "Case {} of {}: outage '{}'.".format(
        case_id, len(records), record["name"]), 4)
    try:
        with StateGuard() as guard:
            _isolate_outage(guard, record["_object"], records)
            result = _run_calculation(
                app, study_case, qds, case_id, record["name"], case["description"],
                original_result, logger, temporary_results, windows, record)
    except StateRestoreError:
        raise
    except GridLensError as exc:
        logger.write("CALCULATION", "{} could not be evaluated: {}".format(case_id, exc), 4, "ERROR")
        result = failed_case(case, str(exc))
    clock_errors = _restore_study_time(study_time_state, logger, "CALCULATION", 4)
    if clock_errors:
        raise GridLensError(
            "The initial Study Case time could not be restored after {}: {}. "
            "The next case was not started.".format(case_id, "; ".join(clock_errors)))
    return result


def execute_gridlens(app):
    logger = RunLogger(app)
    logger.write(
        "STARTUP", "GridLens publisher {} started.".format(PUBLISHER_VERSION), 1)
    script = app.GetCurrentScript()
    study_case = app.GetActiveStudyCase()
    if script is None:
        raise GridLensError("No active ComPython script was found.")
    if study_case is None:
        raise GridLensError(
            "No active study case was found. Activate a study case and retry.")
    report = script.GetParent()
    if report is None or class_name(report) != "IntReport":
        raise GridLensError(
            "Place this ComPython directly below the target IntReport and retry.")
    qds = app.GetFromStudyCase("ComStatsim")
    if qds is None:
        raise GridLensError(
            "No ComStatsim was found in the active study case. Configure the "
            "quasi-dynamic simulation before running GridLens.")
    original_result = safe_attr(qds, "results")
    if original_result is None:
        raise GridLensError(
            "ComStatsim.results is empty. Configure a result object and the "
            "required variables before running GridLens.")
    if object_name(original_result).startswith(SNAPSHOT_PREFIX + "TMP_"):
        # An aborted run can leave this binding behind. The object still holds
        # the full variable selection and every case recalculates into a fresh
        # copy, so the stored settings are used as they are.
        logger.write(
            "CONTEXT",
            "ComStatsim.results is bound to '{}', a temporary result left "
            "behind by an earlier GridLens run that was aborted. GridLens uses "
            "it as the configured result object and restores this binding "
            "afterwards; it is not deleted. To tidy up, rename it or bind "
            "ComStatsim.results to the intended ElmRes.".format(
                object_name(original_result)), 2, "WARNING")
    option_found, original_option = _read_setting(qds, PLANNED_OUTAGE_OPTION)
    if not option_found:
        raise GridLensError(
            "The active ComStatsim does not expose the 'Planned Outages' "
            "option [{}]. GridLens cannot control whether PowerFactory applies "
            "planned outages, so no calculation was started.".format(
                PLANNED_OUTAGE_OPTION))
    study_time_state = _capture_study_time(app)
    logger.write(
        "CONTEXT",
        "Study case '{}'; QDS '{}'; result '{}'; reference flag {}."
        .format(object_name(study_case), object_name(qds),
                object_name(original_result), RUN_REFERENCE_CASE), 2)
    _log_qds_settings(qds, original_result, study_time_state, logger)
    results = []
    records = []
    candidates = []
    temporary_results = []
    state_errors = []
    period = qds_period(qds)
    records, candidates = classify_planned_outages(app, logger, period)
    windows = tuple(record["window"] for record in candidates)
    lodf = None
    if CALCULATE_LODF and candidates:
        lodf = calculate_lodf(app, study_case, candidates, logger)
    try:
        if RUN_REFERENCE_CASE:
            if not _set_scalar_attribute(qds, PLANNED_OUTAGE_OPTION, 0):
                raise GridLensError(
                    "The 'Planned Outages' option [{}] could not be switched "
                    "off, so a reference free of planned outages could not be "
                    "guaranteed. No calculation was started.".format(
                        PLANNED_OUTAGE_OPTION))
            results.append(_run_calculation(
                app, study_case, qds, REFERENCE_CASE_ID, "Reference",
                "Network state without planned outages.",
                original_result, logger, temporary_results, windows))
            clock_errors = _restore_study_time(
                study_time_state, logger, "CALCULATION", 4)
            if clock_errors:
                raise GridLensError(
                    "The initial Study Case time could not be restored after "
                    "REF: {}. The outage run was not started.".format(
                        "; ".join(clock_errors)))
        if candidates:
            if not _set_scalar_attribute(qds, PLANNED_OUTAGE_OPTION, 1):
                raise GridLensError(
                    "The 'Planned Outages' option [{}] could not be switched "
                    "on, so no outage run was started.".format(
                        PLANNED_OUTAGE_OPTION))
            logger.write(
                "CALCULATION",
                "Switched the 'Planned Outages' option [{}] on; every planned "
                "outage is calculated as its own case, one after the other."
                .format(PLANNED_OUTAGE_OPTION), 4)
            for number, record in enumerate(candidates, 1):
                case_id = "{}{:02d}".format(OUTAGE_CASE_PREFIX, number)
                record["case_id"] = case_id
                results.append(_run_outage_case(
                    app, study_case, qds, record, case_id, records,
                    original_result, logger, temporary_results, windows,
                    study_time_state))
        else:
            logger.write(
                "CALCULATION",
                "No planned outage applies to the simulated period; the outage "
                "runs were skipped.", 4, "WARNING")
    finally:
        logger.write("RESTORE", "Restoring the original PowerFactory state.", 6)
        state_errors.extend(_restore_study_time(study_time_state, logger))
        state_errors.extend(
            _restore_planned_outage_option(qds, original_option, logger))
        state_errors.extend(_restore_results_binding(qds, original_result))
        state_errors.extend(_delete_temporary_results(temporary_results, logger))
    if state_errors:
        raise GridLensError(
            "GridLens could not fully restore PowerFactory state: {}. Stop and "
            "verify the study case manually before continuing.".format(
                "; ".join(state_errors)))
    logger.write("RESTORE", "Original PowerFactory state restored and verified.", 6)
    check_run_budget(results)
    apply_reference(results)
    try:
        project = app.GetActiveProject()
    except Exception:
        project = None
    if candidates and RUN_REFERENCE_CASE:
        run_mode = "REFERENCE + PLANNED OUTAGES"
    elif candidates:
        run_mode = "PLANNED OUTAGES ONLY"
    elif RUN_REFERENCE_CASE:
        run_mode = "REFERENCE ONLY - NO PLANNED OUTAGE IN THE SIMULATED PERIOD"
    else:
        run_mode = "NO CALCULATION - NO PLANNED OUTAGE IN THE SIMULATED PERIOD"
    payload = build_cases_payload(
        study_case, results,
        object_name(project) if project else "Active PowerFactory model",
        "Temporary QDS results removed after validated extraction"
        if temporary_results else "No calculation executed",
        records, _generated_by(), run_mode, lodf)
    logger.write(
        "REPORT", "Preparing publication of {} report tables.".format(len(TABLES)), 7)
    counts = publish_report(report, payload, log=lambda message: logger.write(
        "REPORT", message, 7))
    logger.write(
        "COMPLETE",
        "Report published successfully: {} table(s), {} planned outage(s) in "
        "scope, {} calculated case(s).".format(
            len(counts), len(candidates), len(results)), 7)
    return counts


def main():
    try:
        import powerfactory
    except ImportError:
        print(
            "[GridLens][ERROR][STARTUP] The PowerFactory Python module is not "
            "available. Run this file from DIgSILENT PowerFactory 2026.",
            flush=True)
        return False
    app = powerfactory.GetApplication()
    if app is None:
        print(
            "[GridLens][ERROR][STARTUP] PowerFactory did not return an "
            "application object.", flush=True)
        return False
    logger = RunLogger(app)
    try:
        execute_gridlens(app)
        return True
    except KeyboardInterrupt:
        logger.write(
            "ABORTED",
            "The run was cancelled. GridLens attempted to restore all state; "
            "review the RESTORE messages above before continuing.",
            level="ERROR")
    except BaseException as exc:
        logger.write(
            "FAILED",
            "{} Recommended action: correct the reported condition, verify the "
            "active study case, and run GridLens again.".format(
                _friendly_exception(exc)), level="ERROR")
    return False


if __name__ == "__main__":
    main()
