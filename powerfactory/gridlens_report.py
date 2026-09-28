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
MAX_PLOT_POINTS = 61
MAX_BAR_ITEMS = 12
LOADING_MAX = 100.0
VOLTAGE_MIN = 0.95
VOLTAGE_MAX = 1.05
TIME_UNIT_FALLBACK = 'h'
PUBLISHER_VERSION = '5.2.0'
TEMPLATE_NAME = 'MASTER_GRIDLENS'
TEMPLATE_VERSION = '3.2.0'
DATA_CONTRACT_VERSION = '3.2'
RUN_REFERENCE_CASE = True
# Only elements whose short name contains this text are assessed. The own grid
# is named D7...; everything else in the model is foreign network. An empty
# string assesses every element.
ELEMENT_NAME_FILTER = 'D7'
VARIABLES = {'line': ('c:loading', 'm:loading'), 'transformer': ('c:loading', 'm:loading'), 'voltage': ('m:u', 'm:u1'), 'voltage_angle': ('m:phiu', 'm:phiu1')}
CLASS_CATEGORIES = {'ElmLne': ('line',), 'ElmTr2': ('transformer',), 'ElmTr3': ('transformer',), 'ElmTerm': ('voltage', 'voltage_angle')}
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

def text_limit(field):
    if field in _LABEL_FIELDS or field.endswith(_LABEL_SUFFIXES):
        return MAX_LABEL_LENGTH
    return MAX_TEXT_LENGTH
TABLES = (('ScriptedReportMeta', (('study_id', 'string'), ('study_name', 'string'), ('study_description', 'string'), ('model_name', 'string'), ('model_version', 'string'), ('simulation_start', 'string'), ('simulation_end', 'string'), ('simulation_time_step', 'string'), ('generation_date', 'string'), ('generated_by', 'string'), ('run_mode', 'string'), ('template_name', 'string'), ('template_version', 'string'), ('data_contract_version', 'string'), ('result_name', 'string'), ('assessment_scope', 'string'), ('assessment_status', 'string'), ('has_line_bars', 'string'), ('has_transformer_bars', 'string'), ('has_voltage_bars', 'string'), ('has_angle_bars', 'string'))), ('ScriptedModelQuality', (('check_id', 'string'), ('check_name', 'string'), ('status', 'string'), ('message', 'string'), ('affected_element', 'string'))), ('ScriptedCases', (('case_id', 'string'), ('case_name', 'string'), ('is_reference', 'integer'), ('description', 'string'), ('simulation_status', 'string'), ('simulation_start', 'string'), ('simulation_end', 'string'))), ('ScriptedPlannedOutages', (('case_id', 'string'), ('outage_id', 'string'), ('outage_name', 'string'), ('source_class', 'string'), ('status', 'string'), ('skip_reason', 'string'), ('equipment_name', 'string'), ('equipment_type', 'string'), ('switching_actions', 'string'), ('start_time', 'string'), ('end_time', 'string'), ('priority', 'integer'), ('assessment', 'string'), ('assessment_detail', 'string'), ('violation', 'integer'), ('max_loading', 'number'), ('max_loading_element', 'string'), ('max_loading_time', 'string'), ('reference_max_loading', 'number'), ('min_voltage', 'number'), ('max_voltage', 'number'))), ('ScriptedCaseMatrix', (('element_id', 'string'), ('element_name', 'string'), ('element_type', 'string'), ('case_id', 'string'), ('is_out_of_service', 'integer'), ('status_label', 'string'))), ('ScriptedLineStatistics', (('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('voltage_level', 'string'), ('min_loading', 'number'), ('max_loading', 'number'), ('mean_loading', 'number'), ('p95_loading', 'number'), ('time_of_min_loading', 'string'), ('time_of_max_loading', 'string'), ('reference_max_loading', 'number'), ('delta_max_loading', 'number'))), ('ScriptedTransformerStatistics', (('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('voltage_level', 'string'), ('min_loading', 'number'), ('max_loading', 'number'), ('mean_loading', 'number'), ('p95_loading', 'number'), ('time_of_max_loading', 'string'), ('reference_max_loading', 'number'), ('delta_max_loading', 'number'))), ('ScriptedVoltageStatistics', (('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('voltage_level', 'string'), ('min_voltage', 'number'), ('max_voltage', 'number'), ('mean_voltage', 'number'), ('time_of_min_voltage', 'string'), ('time_of_max_voltage', 'string'), ('reference_min_voltage', 'number'), ('reference_max_voltage', 'number'), ('delta_min_voltage', 'number'), ('delta_max_voltage', 'number'))), ('ScriptedLineLoadingBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('max_loading', 'number'), ('unit', 'string'), ('event_time', 'string'))), ('ScriptedTransformerLoadingBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('max_loading', 'number'), ('unit', 'string'), ('event_time', 'string'))), ('ScriptedVoltageMagnitudeBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('min_voltage', 'number'), ('max_voltage', 'number'), ('mean_voltage', 'number'), ('deviation', 'number'), ('status_label', 'string'), ('unit', 'string'))), ('ScriptedVoltageAngleBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('min_angle', 'number'), ('max_angle', 'number'), ('mean_angle', 'number'), ('max_abs_angle', 'number'), ('angle_span', 'number'), ('event_time', 'string'), ('unit', 'string'))), ('ScriptedCaseComparison', (('metric_key', 'string'), ('metric_name', 'string'), ('unit', 'string'), ('case_id', 'string'), ('metric_value', 'number'), ('element_id', 'string'), ('element_name', 'string'))), ('ScriptedRankings', (('ranking_type', 'string'), ('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('element_type', 'string'), ('metric_name', 'string'), ('metric_value', 'number'), ('unit', 'string'), ('reference_value', 'number'), ('delta_value', 'number'), ('event_time', 'string'))), ('ScriptedRelevantTimePoints', (('timestamp', 'string'), ('case_id', 'string'), ('reason', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('metric_name', 'string'), ('metric_value', 'number'), ('unit', 'string'))), ('ScriptedTrendLineLoading', (('case_id', 'string'), ('series_label', 'string'), ('element_name', 'string'), ('time_label', 'string'), ('timestamp', 'number'), ('value', 'number'), ('unit', 'string'))), ('ScriptedTrendTransformerLoading', (('case_id', 'string'), ('series_label', 'string'), ('element_name', 'string'), ('time_label', 'string'), ('timestamp', 'number'), ('value', 'number'), ('unit', 'string'))), ('ScriptedTrendVoltageMin', (('case_id', 'string'), ('series_label', 'string'), ('element_name', 'string'), ('time_label', 'string'), ('timestamp', 'number'), ('value', 'number'), ('unit', 'string'))), ('ScriptedTrendVoltageMax', (('case_id', 'string'), ('series_label', 'string'), ('element_name', 'string'), ('time_label', 'string'), ('timestamp', 'number'), ('value', 'number'), ('unit', 'string'))))
REQUIRED_FIELDS = {'ScriptedReportMeta': ('study_id', 'study_name', 'model_name', 'model_version', 'generation_date', 'generated_by', 'run_mode', 'template_name', 'template_version', 'data_contract_version', 'result_name', 'assessment_scope', 'assessment_status', 'has_line_bars', 'has_transformer_bars', 'has_voltage_bars', 'has_angle_bars'), 'ScriptedModelQuality': ('check_id', 'check_name', 'status', 'message'), 'ScriptedCases': ('case_id', 'case_name', 'is_reference', 'simulation_status'), 'ScriptedPlannedOutages': ('case_id', 'outage_id', 'outage_name', 'source_class', 'status', 'assessment', 'assessment_detail', 'violation'), 'ScriptedCaseMatrix': ('element_id', 'element_name', 'element_type', 'case_id', 'is_out_of_service', 'status_label'), 'ScriptedLineStatistics': ('case_id', 'element_id', 'element_name', 'min_loading', 'max_loading', 'mean_loading', 'p95_loading'), 'ScriptedTransformerStatistics': ('case_id', 'element_id', 'element_name', 'min_loading', 'max_loading', 'mean_loading', 'p95_loading'), 'ScriptedVoltageStatistics': ('case_id', 'element_id', 'element_name', 'min_voltage', 'max_voltage', 'mean_voltage'), 'ScriptedLineLoadingBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'max_loading', 'unit'), 'ScriptedTransformerLoadingBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'max_loading', 'unit'), 'ScriptedVoltageMagnitudeBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'min_voltage', 'max_voltage', 'mean_voltage', 'deviation', 'status_label', 'unit'), 'ScriptedVoltageAngleBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'min_angle', 'max_angle', 'mean_angle', 'max_abs_angle', 'angle_span', 'unit'), 'ScriptedCaseComparison': ('metric_key', 'metric_name', 'case_id', 'metric_value'), 'ScriptedRankings': ('ranking_type', 'rank', 'case_id', 'element_id', 'element_name', 'element_type', 'metric_name', 'metric_value', 'unit'), 'ScriptedRelevantTimePoints': ('timestamp', 'case_id', 'reason', 'metric_name', 'metric_value', 'unit'), 'ScriptedTrendLineLoading': ('case_id', 'series_label', 'element_name', 'time_label', 'timestamp', 'value', 'unit'), 'ScriptedTrendTransformerLoading': ('case_id', 'series_label', 'element_name', 'time_label', 'timestamp', 'value', 'unit'), 'ScriptedTrendVoltageMin': ('case_id', 'series_label', 'element_name', 'time_label', 'timestamp', 'value', 'unit'), 'ScriptedTrendVoltageMax': ('case_id', 'series_label', 'element_name', 'time_label', 'timestamp', 'value', 'unit')}

def safe_attr(obj, name, default=None):
    try:
        value = getattr(obj, name)
        return default if value is None else value
    except Exception:
        return default

def clip_text(value, limit):
    text = str(value)
    if len(text) <= limit:
        return text
    marker = '~' + hashlib.sha256(text.encode('utf-8')).hexdigest()[:6]
    keep = max(0, limit - len(marker))
    return text[:keep] + marker[:limit]

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

def element_in_scope(obj):
    return not ELEMENT_NAME_FILTER or ELEMENT_NAME_FILTER in object_name(obj)

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

def voltage_level(obj):
    candidates = [obj]
    for attribute in ('bus1', 'bus2', 'bushv', 'buslv', 'busmv'):
        cubicle = safe_attr(obj, attribute)
        terminal = safe_attr(cubicle, 'cterm') if cubicle else None
        if terminal:
            candidates.append(terminal)
    for item in candidates:
        nominal = finite_number(safe_attr(item, 'uknom'))
        if nominal is not None:
            return '{:g} kV'.format(nominal)
    return ''

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
        key = (category, object_key(obj))
        priority = VARIABLES[category].index(variable)
        if key not in chosen or priority < chosen[key][0]:
            chosen[key] = (priority, column, obj, variable)
    if counters is not None:
        counters['out_of_scope'] = out_of_scope
    if not chosen and out_of_scope:
        raise RuntimeError(
            'No result series belongs to an element whose name contains {!r} '
            '({} series were out of scope). Set ELEMENT_NAME_FILTER at the top '
            'of gridlens_report.py, or to an empty string to assess every '
            'element.'.format(ELEMENT_NAME_FILTER, out_of_scope))
    cells = rows * len(chosen)
    if cells > MAX_RESULT_CELLS:
        raise RuntimeError('ElmRes contains {} evaluated cells ({} rows x {} series) and exceeds the limit of {} (MAX_RESULT_CELLS).'.format(cells, rows, len(chosen), MAX_RESULT_CELLS))
    series = []
    for (_, _), (_, column, obj, variable) in sorted(chosen.items()):
        points = []
        for row, value in enumerate(read_column(elmres, column, rows)):
            if value is None:
                raise RuntimeError('Invalid result value in ElmRes cell ({}, {}) for {} {}.'.format(row, column, object_name(obj), variable))
            points.append((labels[row], plot_times[row], value))
        category = result_category(obj, variable)
        try:
            unit = str(elmres.GetUnit(column) or '')
        except Exception:
            unit = ''
        if not unit:
            unit = {'voltage': 'p.u.', 'voltage_angle': 'deg'}.get(category, '%')
        values = [value for _, _, value in points]
        series.append({'category': category, 'object': obj, 'key': object_key(obj), 'element_id': object_id(obj), 'element_name': object_name(obj), 'voltage_level': voltage_level(obj), 'variable_id': variable, 'variable': {'voltage': 'Voltage magnitude', 'voltage_angle': 'Voltage angle'}.get(category, 'Loading'), 'unit': unit, 'points': points})
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
    points = item['points']
    if len(points) <= MAX_PLOT_POINTS:
        return points
    values = [point[2] for point in points]
    indices = {0, len(points) - 1, values.index(min(values)), values.index(max(values))}
    for sample in range(MAX_PLOT_POINTS):
        indices.add(int(round(sample * (len(points) - 1) / float(MAX_PLOT_POINTS - 1))))
    return [points[index] for index in sorted(indices)]

def percentile95(values):
    ordered = sorted(values)
    index = max(0, int(math.ceil(0.95 * len(ordered))) - 1)
    return ordered[index]

def window_bounds(hours, windows):
    """Row ranges of each outage window on a strictly increasing hour axis."""
    bounds = []
    for start, end in windows:
        lo = bisect.bisect_left(hours, start / 3600.0)
        hi = bisect.bisect_right(hours, end / 3600.0)
        bounds.append((lo, hi))
    return bounds

def window_statistics(values, labels, bounds):
    """Statistics per window, skipping windows without result rows."""
    result = {}
    for index, (lo, hi) in enumerate(bounds):
        chunk = values[lo:hi]
        if not chunk:
            continue
        minimum = min(chunk)
        maximum = max(chunk)
        result[index] = {
            'min': minimum, 'max': maximum,
            'mean': sum(chunk) / len(chunk),
            'time_min': labels[lo + chunk.index(minimum)],
            'time_max': labels[lo + chunk.index(maximum)],
        }
    return result

def statistics(series):
    values = [value for _, _, value in series['points']]
    minimum = min(values)
    maximum = max(values)
    return {'min': minimum, 'max': maximum, 'mean': sum(values) / len(values), 'p95': percentile95(values), 'time_min': next((label for label, _, value in series['points'] if value == minimum)), 'time_max': next((label for label, _, value in series['points'] if value == maximum))}

def format_limit(value):
    return '{:g}'.format(value)

def has_time_variation(item):
    values = [value for _, _, value in item['points']]
    if len(values) < 2:
        return False
    tolerance = {'line': 0.1, 'transformer': 0.1, 'voltage': 0.001, 'voltage_angle': 0.01}.get(item['category'], 1e-06)
    return max(values) - min(values) > tolerance

def empty_payload():
    return {name: [] for name, _ in TABLES}

def is_critical(item, stats):
    if item['category'] in ('line', 'transformer'):
        return stats['max'] > LOADING_MAX
    if item['category'] == 'voltage':
        return stats['min'] < VOLTAGE_MIN or stats['max'] > VOLTAGE_MAX
    return False

def maximum_absolute(stats):
    return max(abs(stats['min']), abs(stats['max']))

def voltage_deviation(stats):
    return max(abs(stats['min'] - 1.0), abs(stats['max'] - 1.0))
REFERENCE_ID = 'REF'
CONVERGED = 'CONVERGED'
AXIS_MISMATCH = 'NOT EVALUATED'
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
    return {'id': case['id'], 'name': case['name'], 'kind': case.get('kind', 'case'), 'description': case.get('description', ''), 'status': case.get('status', CONVERGED), 'error_code': case.get('error_code'), 'message': case.get('message', ''), 'out_of_service': list(case.get('out_of_service', ())), 'is_reference': 1 if case['id'] == REFERENCE_ID else 0, 'labels': list(labels), 'plot_times': list(plot_times), 'time_unit': time_unit, 'by_category': by_category, 'stats_by_key': stats_by_key, 'item_by_key': item_by_key}

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

def critical_keys(results, category):
    keys = set()
    for result in converged(results):
        for item, stats in result['by_category'][category]:
            if is_critical(item, stats):
                keys.add((category, item['key']))
    return keys

def bar_label(case_id, element_name):
    if case_id == 'AKTIV':
        return element_name
    return '{} · {}'.format(case_id, element_name)

def _collect(results, category, only_critical=True, predicate=None):
    entries = []
    for result in converged(results):
        for item, stats in result['by_category'][category]:
            if only_critical and (not is_critical(item, stats)):
                continue
            if predicate is not None and (not predicate(stats)):
                continue
            entries.append((result['id'], item, stats))
    return entries
LINE_FIELDS = (('min_loading', 'min'), ('max_loading', 'max'), ('mean_loading', 'mean'), ('p95_loading', 'p95'), ('time_of_min_loading', 'time_min'), ('time_of_max_loading', 'time_max'), ('reference_max_loading', 'ref_max'), ('delta_max_loading', 'delta_max'))
TRANSFORMER_FIELDS = tuple((entry for entry in LINE_FIELDS if entry[0] != 'time_of_min_loading'))
VOLTAGE_FIELDS = (('min_voltage', 'min'), ('max_voltage', 'max'), ('mean_voltage', 'mean'), ('time_of_min_voltage', 'time_min'), ('time_of_max_voltage', 'time_max'), ('reference_min_voltage', 'ref_min'), ('reference_max_voltage', 'ref_max'), ('delta_min_voltage', 'delta_min'), ('delta_max_voltage', 'delta_max'))

def _statistics_rows(payload, results, category, table, fields):
    for _, key in sorted(critical_keys(results, category)):
        for result in converged(results):
            stats = result['stats_by_key'].get((category, key))
            if stats is None:
                continue
            item = result['item_by_key'][category, key]
            row = {'case_id': result['id'], 'element_id': item['element_id'], 'element_name': item['element_name'], 'voltage_level': item['voltage_level']}
            row.update({name: stats[source] for name, source in fields})
            payload[table].append(row)

def _loading_bars(payload, results, category, table):
    entries = sorted(_collect(results, category), key=lambda entry: entry[2]['max'], reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        payload[table].append({'rank': rank, 'case_id': case_id, 'element_id': item['element_id'], 'element_name': item['element_name'], 'bar_label': bar_label(case_id, item['element_name']), 'voltage_level': item['voltage_level'], 'max_loading': stats['max'], 'unit': item['unit'], 'event_time': stats['time_max']})

def _voltage_bars(payload, results):
    entries = sorted(_collect(results, 'voltage'), key=lambda entry: voltage_deviation(entry[2]), reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        payload['ScriptedVoltageMagnitudeBars'].append({'rank': rank, 'case_id': case_id, 'element_id': item['element_id'], 'element_name': item['element_name'], 'bar_label': bar_label(case_id, item['element_name']), 'voltage_level': item['voltage_level'], 'min_voltage': stats['min'], 'max_voltage': stats['max'], 'mean_voltage': stats['mean'], 'deviation': voltage_deviation(stats), 'status_label': 'LIMIT VIOLATION', 'unit': item['unit']})

def _angle_bars(payload, results):
    entries = sorted(_collect(results, 'voltage_angle', only_critical=False), key=lambda entry: maximum_absolute(entry[2]), reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        event_time = stats['time_min'] if abs(stats['min']) >= abs(stats['max']) else stats['time_max']
        payload['ScriptedVoltageAngleBars'].append({'rank': rank, 'case_id': case_id, 'element_id': item['element_id'], 'element_name': item['element_name'], 'bar_label': bar_label(case_id, item['element_name']), 'voltage_level': item['voltage_level'], 'min_angle': stats['min'], 'max_angle': stats['max'], 'mean_angle': stats['mean'], 'max_abs_angle': maximum_absolute(stats), 'angle_span': stats['max'] - stats['min'], 'event_time': event_time, 'unit': item['unit']})

def _rankings(payload, results, ranking_type, category, metric_name, value_key, time_key, reverse, predicate=None):
    entries = sorted(_collect(results, category, predicate=predicate), key=lambda entry: entry[2][value_key], reverse=reverse)
    reference_key = 'ref_min' if value_key == 'min' else 'ref_max'
    delta_key = 'delta_min' if value_key == 'min' else 'delta_max'
    for rank, (case_id, item, stats) in enumerate(entries[:TOP_N], 1):
        payload['ScriptedRankings'].append({'ranking_type': ranking_type, 'rank': rank, 'case_id': case_id, 'element_id': item['element_id'], 'element_name': item['element_name'], 'element_type': item['category'], 'metric_name': metric_name, 'metric_value': stats[value_key], 'unit': item['unit'], 'reference_value': stats[reference_key], 'delta_value': stats[delta_key], 'event_time': stats[time_key]})
COMPARISON_METRICS = (('max_line_loading', 'Maximum line loading', 'line', 'max', True, None), ('max_transformer_loading', 'Maximum transformer loading', 'transformer', 'max', True, None), ('min_voltage', 'Minimum voltage', 'voltage', 'min', False, lambda stats: stats['min'] < VOLTAGE_MIN), ('max_voltage', 'Maximum voltage', 'voltage', 'max', True, lambda stats: stats['max'] > VOLTAGE_MAX))

def _case_comparison(payload, results):
    for key, name, category, value_key, reverse, predicate in COMPARISON_METRICS:
        for result in converged(results):
            entries = _collect([result], category, predicate=predicate)
            if not entries:
                continue
            _, item, stats = sorted(entries, key=lambda entry: entry[2][value_key], reverse=reverse)[0]
            payload['ScriptedCaseComparison'].append({'metric_key': key, 'metric_name': name, 'unit': item['unit'], 'case_id': result['id'], 'metric_value': stats[value_key], 'element_id': item['element_id'], 'element_name': item['element_name']})

def _relevant_time_points(payload, results):
    selected = []
    loading = sorted(_collect(results, 'line') + _collect(results, 'transformer'), key=lambda entry: entry[2]['max'], reverse=True)[:TOP_N]
    for case_id, item, stats in loading:
        reason = 'Maximum line loading' if item['category'] == 'line' else 'Maximum transformer loading'
        selected.append((case_id, item, stats, reason, 'max', 'time_max'))
    low = sorted(_collect(results, 'voltage', predicate=lambda s: s['min'] < VOLTAGE_MIN), key=lambda entry: entry[2]['min'])[:TOP_N]
    for case_id, item, stats in low:
        selected.append((case_id, item, stats, 'Minimum voltage', 'min', 'time_min'))
    high = sorted(_collect(results, 'voltage', predicate=lambda s: s['max'] > VOLTAGE_MAX), key=lambda entry: entry[2]['max'], reverse=True)[:TOP_N]
    for case_id, item, stats in high:
        selected.append((case_id, item, stats, 'Maximum voltage', 'max', 'time_max'))
    for case_id, item, stats, reason, value_key, time_key in selected:
        payload['ScriptedRelevantTimePoints'].append({'timestamp': stats[time_key], 'case_id': case_id, 'reason': reason, 'element_id': item['element_id'], 'element_name': item['element_name'], 'metric_name': item['variable'], 'metric_value': stats[value_key], 'unit': item['unit']})
# One table per chart. The report engine does not apply a data relation to a
# chart, so every chart must read a table that holds only its own series.
TREND_SLOTS = (('ScriptedTrendLineLoading', 'line', 'max', True), ('ScriptedTrendTransformerLoading', 'transformer', 'max', True), ('ScriptedTrendVoltageMin', 'voltage', 'min', False), ('ScriptedTrendVoltageMax', 'voltage', 'max', True))

def _trends(payload, results):
    for table, category, value_key, highest in TREND_SLOTS:
        entries = _collect(results, category, only_critical=False)
        if not entries:
            continue
        pick = max if highest else min
        key = pick(entries, key=lambda entry: entry[2][value_key])[1]['key']
        for result in converged(results):
            item = result['item_by_key'].get((category, key))
            if item is None:
                continue
            for label, timestamp, value in sampled_plot_points(item):
                payload[table].append({'case_id': result['id'], 'series_label': '{} · {}'.format(result['id'], item['element_name']), 'element_name': item['element_name'], 'time_label': label, 'timestamp': timestamp, 'value': value, 'unit': item['unit']})

def _element_type(element_class):
    categories = CLASS_CATEGORIES.get(element_class, ())
    return categories[0] if categories else element_class
CATEGORY_LABELS = (('line', 'Line loading'), ('transformer', 'Transformer loading'), ('voltage', 'Voltage magnitude'), ('voltage_angle', 'Voltage angle'))

def _model_quality(payload, results):
    ok = converged(results)
    total_series = sum((len(r['by_category'][c]) for r in ok for c, _ in CATEGORY_LABELS))
    cases_ok = bool(results) and len(ok) == len(results) and all((any((result['by_category'][category] for category, _ in CATEGORY_LABELS)) for result in ok))
    payload['ScriptedModelQuality'].append({'check_id': 'cases', 'check_name': 'Evaluated cases', 'status': 'PASS' if cases_ok else 'FAIL', 'message': '{} of {} cases converged; {} result series'.format(len(ok), len(results), total_series), 'affected_element': ''})
    for result in results:
        if result['status'] == CONVERGED:
            continue
        payload['ScriptedModelQuality'].append({'check_id': 'case_' + result['id'], 'check_name': 'Calculation ' + result['id'], 'status': 'FAIL', 'message': result['message'] or 'Calculation did not converge.', 'affected_element': result['name']})
    for category, label in CATEGORY_LABELS:
        total = sum((len(r['by_category'][category]) for r in ok))
        critical = len(critical_keys(results, category))
        if category == 'voltage_angle':
            message = '{} evaluated; informational, without a general limit.'.format(total) if total else 'No angle series; record m:phiu or m:phiu1 in ElmRes.'
        else:
            message = '{} evaluated; {} equipment items with a limit violation'.format(total, critical)
        payload['ScriptedModelQuality'].append({'check_id': 'series_' + category, 'check_name': label, 'status': 'PASS' if total else 'WARNING', 'message': message, 'affected_element': ''})
    varying = sum((1 for r in ok for c, _ in CATEGORY_LABELS for item, _ in r['by_category'][c] if has_time_variation(item)))
    payload['ScriptedModelQuality'].append({'check_id': 'time_variation', 'check_name': 'Time variation', 'status': 'PASS' if varying else 'WARNING', 'message': '{} of {} series change over the simulation period.'.format(varying, total_series) if varying else 'All {} series are constant; check QDS profiles and result recording.'.format(total_series), 'affected_element': ''})
    reference = find_reference(results)
    payload['ScriptedModelQuality'].append({'check_id': 'reference_comparison', 'check_name': 'Reference comparison', 'status': 'PASS' if reference is not None else 'WARNING', 'message': 'Reference case {} evaluated; deltas compare against the unchanged initial network state.'.format(reference['name']) if reference is not None else 'No converged reference case; reference columns remain empty.', 'affected_element': ''})
    payload['ScriptedModelQuality'].extend(({'check_id': 'security_scope', 'check_name': 'Assessment scope', 'status': 'WARNING', 'message': 'N-1 security, security of supply, protection coordination and safe isolation are not assessed.', 'affected_element': ''}, {'check_id': 'limit_loading', 'check_name': 'Loading limit', 'status': 'INFO', 'message': 'Limit violation when loading > {} %.'.format(format_limit(LOADING_MAX)), 'affected_element': ''}, {'check_id': 'limit_voltage', 'check_name': 'Voltage limits', 'status': 'INFO', 'message': 'Limit violation when voltage < {} p.u. or > {} p.u.'.format(format_limit(VOLTAGE_MIN), format_limit(VOLTAGE_MAX)), 'affected_element': ''}))

def _key_discriminator(key):
    digest = hashlib.sha256(str(key).encode('utf-8')).hexdigest()
    return digest[:6]

def _window_worst(result, categories, index, key, reverse):
    """The item with the most severe value of `key` inside one window."""
    best = None
    for category in categories:
        for item, _ in result['by_category'].get(category, ()):
            stats = item.get('windows', {}).get(index)
            if stats is None:
                continue
            if best is None or (stats[key] > best[1][key] if reverse
                                else stats[key] < best[1][key]):
                best = (item, stats)
    return best


def assess_outage_window(results, index):
    """Judge one planned outage by what happens inside its own time window."""
    outage = next((item for item in converged(results)
                   if item['id'] == OUTAGE_CASE_ID), None)
    if outage is None:
        return None
    loading = _window_worst(outage, LOADING_CATEGORIES, index, 'max', True)
    low = _window_worst(outage, ('voltage',), index, 'min', False)
    high = _window_worst(outage, ('voltage',), index, 'max', True)
    if loading is None and low is None:
        return None
    reference = next((item for item in converged(results)
                      if item['id'] == REFERENCE_ID), None)
    reference_loading = (_window_worst(reference, LOADING_CATEGORIES, index,
                                       'max', True)
                         if reference is not None else None)
    over = loading is not None and loading[1]['max'] > LOADING_MAX
    under_voltage = low is not None and low[1]['min'] < VOLTAGE_MIN
    over_voltage = high is not None and high[1]['max'] > VOLTAGE_MAX
    if over and (under_voltage or over_voltage):
        verdict = ASSESSMENT_BOTH
    elif over:
        verdict = ASSESSMENT_LOADING
    elif under_voltage or over_voltage:
        verdict = ASSESSMENT_VOLTAGE
    else:
        verdict = ASSESSMENT_OK
    return {
        'assessment': verdict,
        'violation': 1 if verdict != ASSESSMENT_OK else 0,
        'max_loading': loading[1]['max'] if loading else None,
        'max_loading_element': loading[0]['element_name'] if loading else '',
        'max_loading_time': loading[1]['time_max'] if loading else '',
        'reference_max_loading': (reference_loading[1]['max']
                                  if reference_loading else None),
        'min_voltage': low[1]['min'] if low else None,
        'max_voltage': high[1]['max'] if high else None,
    }


def assessment_detail(values):
    """One readable sentence with the numbers behind the verdict."""
    parts = []
    if values.get('max_loading') is not None:
        text = "max {:.1f} % on {} at {}".format(
            values['max_loading'], values['max_loading_element'],
            values['max_loading_time'])
        if values.get('reference_max_loading') is not None:
            text += " (reference {:.1f} %)".format(
                values['reference_max_loading'])
        parts.append(text)
    if values.get('min_voltage') is not None and values.get('max_voltage') is not None:
        parts.append("voltage {:.3f} to {:.3f} p.u.".format(
            values['min_voltage'], values['max_voltage']))
    return "; ".join(parts)


def outage_identity(results):
    keys_by_name = {}
    for result in results:
        for outage in result['out_of_service']:
            name = outage[1]
            key = outage[2] if len(outage) > 2 else name
            bucket = keys_by_name.setdefault(name, [])
            if key not in bucket:
                bucket.append(key)
    identity = {}
    for name, keys in keys_by_name.items():
        for key in keys:
            identity[key] = name if len(keys) == 1 else '{} ({})'.format(name, _key_discriminator(key))
    return identity
CHART_FLAGS = (('has_line_bars', 'ScriptedLineLoadingBars'), ('has_transformer_bars', 'ScriptedTransformerLoadingBars'), ('has_voltage_bars', 'ScriptedVoltageMagnitudeBars'), ('has_angle_bars', 'ScriptedVoltageAngleBars'))

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
        payload['ScriptedModelQuality'].append({'check_id': 'table_limit_' + name, 'check_name': 'Table limit ' + name, 'status': 'FAIL', 'message': '{} rows generated, {} published. The report is incomplete; reduce the number of cases or the model scope (MAX_TABLE_ROWS).'.format(total, limit), 'affected_element': ''})

def _render_flags(payload):
    meta = payload['ScriptedReportMeta'][0]
    for flag, table in CHART_FLAGS:
        meta[flag] = '1' if payload[table] else '0'

def build_cases_payload(study_case, results, project_name, result_name, planned_outages, generated_by, run_mode):
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
    payload['ScriptedReportMeta'].append({'study_id': object_name(study_case), 'study_name': object_name(study_case), 'study_description': object_description(study_case), 'model_name': project_name, 'model_version': 'PowerFactory 2026', 'simulation_start': start, 'simulation_end': end, 'simulation_time_step': time_step or 'ElmRes row interval', 'generation_date': datetime.now().astimezone().isoformat(timespec='seconds'), 'generated_by': generated_by, 'run_mode': run_mode, 'template_name': TEMPLATE_NAME, 'template_version': TEMPLATE_VERSION, 'data_contract_version': DATA_CONTRACT_VERSION, 'result_name': result_name, 'assessment_scope': '{} case(s); reference: {}; {}'.format(len(results), reference['id'] if reference else 'none', 'elements named *{}*'.format(ELEMENT_NAME_FILTER) if ELEMENT_NAME_FILTER else 'all elements'), 'assessment_status': 'PRE-ASSESSMENT - NOT AN OPERATIONAL RELEASE', 'has_line_bars': '0', 'has_transformer_bars': '0', 'has_voltage_bars': '0', 'has_angle_bars': '0'})
    identity = outage_identity(results)
    for result in results:
        payload['ScriptedCases'].append({'case_id': result['id'], 'case_name': result['name'], 'is_reference': result['is_reference'], 'description': result['description'], 'simulation_status': result['status'], 'simulation_start': result['labels'][0] if result['labels'] else '', 'simulation_end': result['labels'][-1] if result['labels'] else ''})
        for outage in result['out_of_service']:
            element_class, name = outage[:2]
            key = outage[2] if len(outage) > 2 else name
            label = identity.get(key, name)
            payload['ScriptedCaseMatrix'].append({'element_id': label, 'element_name': label, 'element_type': _element_type(element_class), 'case_id': result['id'], 'is_out_of_service': 1, 'status_label': 'OFF'})
    for outage in planned_outages:
        considered = outage['status'] == OUTAGE_CONSIDERED
        values = {'assessment': ASSESSMENT_SKIPPED, 'violation': 0}
        detail = outage.get('skip_reason', '')
        if considered:
            judged = assess_outage_window(results, outage.get('window_index'))
            if judged is None:
                values = {'assessment': ASSESSMENT_NO_DATA, 'violation': 0}
                detail = ('No result rows fall inside this outage window, so it '
                          'was not assessed.')
            else:
                values = judged
                detail = assessment_detail(judged)
        row = {'case_id': OUTAGE_CASE_ID if considered else 'N/A', 'outage_id': outage['id'], 'outage_name': outage['name'], 'source_class': outage['source_class'], 'status': outage['status'], 'skip_reason': outage.get('skip_reason', ''), 'equipment_name': outage.get('equipment_name', ''), 'equipment_type': outage.get('equipment_type', ''), 'switching_actions': outage.get('switching_actions', ''), 'start_time': outage.get('start_time', ''), 'end_time': outage.get('end_time', ''), 'priority': int(outage.get('priority') or 0), 'assessment_detail': detail}
        row.update({key: values.get(key) for key in (
            'assessment', 'violation', 'max_loading', 'max_loading_element',
            'max_loading_time', 'reference_max_loading', 'min_voltage',
            'max_voltage')})
        payload['ScriptedPlannedOutages'].append(row)
    considered = sum((item['status'] == OUTAGE_CONSIDERED for item in planned_outages))
    skipped = len(planned_outages) - considered
    outage_status = 'PASS' if considered and skipped == 0 else 'WARNING'
    payload['ScriptedModelQuality'].append({'check_id': 'planned_outages', 'check_name': 'Planned outage applicability', 'status': outage_status, 'message': '{} found; {} in scope; {} skipped.'.format(len(planned_outages), considered, skipped), 'affected_element': ''})
    _model_quality(payload, results)
    _statistics_rows(payload, results, 'line', 'ScriptedLineStatistics', LINE_FIELDS)
    _statistics_rows(payload, results, 'transformer', 'ScriptedTransformerStatistics', TRANSFORMER_FIELDS)
    _statistics_rows(payload, results, 'voltage', 'ScriptedVoltageStatistics', VOLTAGE_FIELDS)
    _loading_bars(payload, results, 'line', 'ScriptedLineLoadingBars')
    _loading_bars(payload, results, 'transformer', 'ScriptedTransformerLoadingBars')
    _voltage_bars(payload, results)
    _angle_bars(payload, results)
    _rankings(payload, results, 'highest_line_loading', 'line', 'Maximum loading', 'max', 'time_max', True)
    _rankings(payload, results, 'highest_transformer_loading', 'transformer', 'Maximum loading', 'max', 'time_max', True)
    _rankings(payload, results, 'lowest_voltage', 'voltage', 'Minimum voltage', 'min', 'time_min', False, predicate=lambda stats: stats['min'] < VOLTAGE_MIN)
    _rankings(payload, results, 'highest_voltage', 'voltage', 'Maximum voltage', 'max', 'time_max', True, predicate=lambda stats: stats['max'] > VOLTAGE_MAX)
    _case_comparison(payload, results)
    _relevant_time_points(payload, results)
    _trends(payload, results)
    _enforce_table_limits(payload)
    _render_flags(payload)
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
    known_cases = {row.get('case_id') for row in payload['ScriptedCases']}
    for table, _, _, _ in TREND_SLOTS:
        for index, row in enumerate(payload[table]):
            if row.get('case_id') not in known_cases:
                raise ValueError('{} row {} has an unknown case_id.'.format(table, index))

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
ASSESSMENT_LOADING = "OVERLOAD"
ASSESSMENT_VOLTAGE = "VOLTAGE BAND"
ASSESSMENT_BOTH = "OVERLOAD + VOLTAGE BAND"
ASSESSMENT_SKIPPED = "NOT SIMULATED"
ASSESSMENT_NO_DATA = "NO RESULT DATA IN WINDOW"
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
OUTAGE_CASE_ID = "OUTAGE"
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


def _outage_record(outage):
    equipment, equipment_type, actions, start, end = _outage_details(outage)
    return {
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


def _collect_out_of_service(app):
    found = {}
    for pattern in ("*.ElmLne", "*.ElmTr2", "*.ElmTr3", "*.ElmTerm"):
        try:
            objects = app.GetCalcRelevantObjects(pattern, 1) or []
        except TypeError:
            try:
                objects = app.GetCalcRelevantObjects(pattern) or []
            except Exception:
                objects = []
        except Exception:
            objects = []
        for item in objects:
            if not element_in_scope(item):
                continue
            if finite_number(safe_attr(item, "outserv", 0)) == 1.0:
                found[object_key(item)] = (
                    class_name(item), object_name(item), object_key(item))
    return [found[key] for key in sorted(found)]


def _run_calculation(app, study_case, qds, case_id, name, description,
                     original_result, logger, temporary_results, windows=()):
    snapshot = _temporary_result(study_case, original_result, case_id)
    temporary_results.append(snapshot)
    if not _set_attribute(qds, "results", snapshot):
        raise GridLensError(
            "PowerFactory did not bind ComStatsim.results to the temporary "
            "ElmRes. No calculation was started.")
    logger.write(
        "CALCULATION",
        "Starting {} with the active ComStatsim settings; only the "
        "'Planned Outages' option differs between the cases."
        .format(case_id), 4)
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
        if ELEMENT_NAME_FILTER:
            logger.write(
                "EXTRACTION",
                "Element scope {!r}: {} series assessed, {} out of scope and "
                "not read.".format(ELEMENT_NAME_FILTER, len(series),
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
        "out_of_service": _collect_out_of_service(app),
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
                "Switched the 'Planned Outages' option [{}] on; PowerFactory "
                "will apply {} planned outage(s) inside their own time "
                "windows.".format(PLANNED_OUTAGE_OPTION, len(candidates)), 4)
            results.append(_run_calculation(
                app, study_case, qds, OUTAGE_CASE_ID,
                "Planned outages",
                "Same period with the planned outages applied by PowerFactory.",
                original_result, logger, temporary_results, windows))
        else:
            logger.write(
                "CALCULATION",
                "No planned outage applies to the simulated period; the outage "
                "run was skipped.", 4, "WARNING")
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
        records, _generated_by(), run_mode)
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
