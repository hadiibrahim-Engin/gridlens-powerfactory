"""GridLens single-file runtime for DIgSILENT PowerFactory 2026."""

from __future__ import annotations

import getpass
import hashlib
import math
import os
import time
from datetime import datetime

HOST_TABLE_PREFIX = 'Scripted'
TOP_N = 10
MAX_PLOTS = 4
MAX_PLOT_POINTS = 61
MAX_BAR_ITEMS = 12
LOADING_MAX = 100.0
VOLTAGE_MIN = 0.95
VOLTAGE_MAX = 1.05
TIME_UNIT_FALLBACK = 'h'
PUBLISHER_VERSION = '5.0.0'
TEMPLATE_NAME = 'MASTER_GRIDLENS'
TEMPLATE_VERSION = '3.0.0'
DATA_CONTRACT_VERSION = '3.0'
RUN_REFERENCE_CASE = True
VARIABLES = {'line': ('c:loading', 'm:loading'), 'transformer': ('c:loading', 'm:loading'), 'voltage': ('m:u', 'm:u1'), 'voltage_angle': ('m:phiu', 'm:phiu1')}
CLASS_CATEGORIES = {'ElmLne': ('line',), 'ElmTr2': ('transformer',), 'ElmTr3': ('transformer',), 'ElmTerm': ('voltage', 'voltage_angle')}
MAX_RESULT_ROWS = 35040
MAX_RESULT_CELLS = 20000000
MAX_RUN_CELLS = 120000000
MAX_TABLE_ROWS = 5000
SNAPSHOT_PREFIX = 'GridLens_'

FIELD_TYPES = {'string': 0, 'integer': 1, 'number': 2}
MAX_LABEL_LENGTH = 80
MAX_TEXT_LENGTH = 500
_LABEL_SUFFIXES = ('_id', '_name', '_label', '_type', '_level', '_time')
_LABEL_FIELDS = ('unit', 'variable', 'status', 'reason', 'action', 'timestamp', 'metric_name', 'check_name', 'ranking_type', 'simulation_status', 'simulation_start', 'simulation_end', 'simulation_time_step', 'generation_date', 'assessment_status')

def text_limit(field):
    if field in _LABEL_FIELDS or field.endswith(_LABEL_SUFFIXES):
        return MAX_LABEL_LENGTH
    return MAX_TEXT_LENGTH
TABLES = (('ScriptedReportMeta', (('study_id', 'string'), ('study_name', 'string'), ('study_description', 'string'), ('model_name', 'string'), ('model_version', 'string'), ('simulation_start', 'string'), ('simulation_end', 'string'), ('simulation_time_step', 'string'), ('generation_date', 'string'), ('generated_by', 'string'), ('run_mode', 'string'), ('template_name', 'string'), ('template_version', 'string'), ('data_contract_version', 'string'), ('result_name', 'string'), ('assessment_scope', 'string'), ('assessment_status', 'string'), ('has_line_bars', 'string'), ('has_transformer_bars', 'string'), ('has_voltage_bars', 'string'), ('has_angle_bars', 'string'))), ('ScriptedModelQuality', (('check_id', 'string'), ('check_name', 'string'), ('status', 'string'), ('message', 'string'), ('affected_element', 'string'))), ('ScriptedCases', (('case_id', 'string'), ('case_name', 'string'), ('is_reference', 'integer'), ('description', 'string'), ('simulation_status', 'string'), ('simulation_start', 'string'), ('simulation_end', 'string'))), ('ScriptedPlannedOutages', (('case_id', 'string'), ('outage_id', 'string'), ('outage_name', 'string'), ('source_class', 'string'), ('status', 'string'), ('skip_reason', 'string'), ('equipment_name', 'string'), ('equipment_type', 'string'), ('switching_actions', 'string'), ('start_time', 'string'), ('end_time', 'string'))), ('ScriptedCaseMatrix', (('element_id', 'string'), ('element_name', 'string'), ('element_type', 'string'), ('case_id', 'string'), ('is_out_of_service', 'integer'), ('status_label', 'string'))), ('ScriptedLineStatistics', (('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('voltage_level', 'string'), ('min_loading', 'number'), ('max_loading', 'number'), ('mean_loading', 'number'), ('p95_loading', 'number'), ('time_of_min_loading', 'string'), ('time_of_max_loading', 'string'), ('reference_max_loading', 'number'), ('delta_max_loading', 'number'))), ('ScriptedTransformerStatistics', (('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('voltage_level', 'string'), ('min_loading', 'number'), ('max_loading', 'number'), ('mean_loading', 'number'), ('p95_loading', 'number'), ('time_of_max_loading', 'string'), ('reference_max_loading', 'number'), ('delta_max_loading', 'number'))), ('ScriptedVoltageStatistics', (('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('voltage_level', 'string'), ('min_voltage', 'number'), ('max_voltage', 'number'), ('mean_voltage', 'number'), ('time_of_min_voltage', 'string'), ('time_of_max_voltage', 'string'), ('reference_min_voltage', 'number'), ('reference_max_voltage', 'number'), ('delta_min_voltage', 'number'), ('delta_max_voltage', 'number'))), ('ScriptedLineLoadingBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('max_loading', 'number'), ('unit', 'string'), ('event_time', 'string'))), ('ScriptedTransformerLoadingBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('max_loading', 'number'), ('unit', 'string'), ('event_time', 'string'))), ('ScriptedVoltageMagnitudeBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('min_voltage', 'number'), ('max_voltage', 'number'), ('mean_voltage', 'number'), ('deviation', 'number'), ('status_label', 'string'), ('unit', 'string'))), ('ScriptedVoltageAngleBars', (('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('bar_label', 'string'), ('voltage_level', 'string'), ('min_angle', 'number'), ('max_angle', 'number'), ('mean_angle', 'number'), ('max_abs_angle', 'number'), ('angle_span', 'number'), ('event_time', 'string'), ('unit', 'string'))), ('ScriptedCaseComparison', (('metric_key', 'string'), ('metric_name', 'string'), ('unit', 'string'), ('case_id', 'string'), ('metric_value', 'number'), ('element_id', 'string'), ('element_name', 'string'))), ('ScriptedRankings', (('ranking_type', 'string'), ('rank', 'integer'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('element_type', 'string'), ('metric_name', 'string'), ('metric_value', 'number'), ('unit', 'string'), ('reference_value', 'number'), ('delta_value', 'number'), ('event_time', 'string'))), ('ScriptedRelevantTimePoints', (('timestamp', 'string'), ('case_id', 'string'), ('reason', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('metric_name', 'string'), ('metric_value', 'number'), ('unit', 'string'))), ('ScriptedPlots', (('plot_id', 'string'), ('plot_title', 'string'), ('case_id', 'string'), ('element_id', 'string'), ('element_name', 'string'), ('variable', 'string'), ('unit', 'string'))), ('ScriptedPlotData', (('plot_id', 'string'), ('case_id', 'string'), ('series_role', 'string'), ('timestamp', 'number'), ('value', 'number'))))
REQUIRED_FIELDS = {'ScriptedReportMeta': ('study_id', 'study_name', 'model_name', 'model_version', 'generation_date', 'generated_by', 'run_mode', 'template_name', 'template_version', 'data_contract_version', 'result_name', 'assessment_scope', 'assessment_status', 'has_line_bars', 'has_transformer_bars', 'has_voltage_bars', 'has_angle_bars'), 'ScriptedModelQuality': ('check_id', 'check_name', 'status', 'message'), 'ScriptedCases': ('case_id', 'case_name', 'is_reference', 'simulation_status'), 'ScriptedPlannedOutages': ('case_id', 'outage_id', 'outage_name', 'source_class', 'status'), 'ScriptedCaseMatrix': ('element_id', 'element_name', 'element_type', 'case_id', 'is_out_of_service', 'status_label'), 'ScriptedLineStatistics': ('case_id', 'element_id', 'element_name', 'min_loading', 'max_loading', 'mean_loading', 'p95_loading'), 'ScriptedTransformerStatistics': ('case_id', 'element_id', 'element_name', 'min_loading', 'max_loading', 'mean_loading', 'p95_loading'), 'ScriptedVoltageStatistics': ('case_id', 'element_id', 'element_name', 'min_voltage', 'max_voltage', 'mean_voltage'), 'ScriptedLineLoadingBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'max_loading', 'unit'), 'ScriptedTransformerLoadingBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'max_loading', 'unit'), 'ScriptedVoltageMagnitudeBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'min_voltage', 'max_voltage', 'mean_voltage', 'deviation', 'status_label', 'unit'), 'ScriptedVoltageAngleBars': ('rank', 'case_id', 'element_id', 'element_name', 'bar_label', 'min_angle', 'max_angle', 'mean_angle', 'max_abs_angle', 'angle_span', 'unit'), 'ScriptedCaseComparison': ('metric_key', 'metric_name', 'case_id', 'metric_value'), 'ScriptedRankings': ('ranking_type', 'rank', 'case_id', 'element_id', 'element_name', 'element_type', 'metric_name', 'metric_value', 'unit'), 'ScriptedRelevantTimePoints': ('timestamp', 'case_id', 'reason', 'metric_name', 'metric_value', 'unit'), 'ScriptedPlots': ('plot_id', 'plot_title', 'element_id', 'element_name', 'variable', 'unit'), 'ScriptedPlotData': ('plot_id', 'case_id', 'series_role', 'timestamp', 'value')}

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

def time_column(elmres, column_count):
    candidates = ('b:tnow', 't', 'time')
    for column in range(column_count):
        try:
            variable = str(elmres.GetVariable(column)).lower()
        except Exception:
            continue
        if variable in candidates:
            return column
    for candidate in candidates:
        try:
            column = elmres.FindColumn(candidate)
            if isinstance(column, int) and column >= 0:
                return column
        except Exception:
            pass
    raise RuntimeError('ElmRes has no unambiguous time column (b:tnow, t or time).')

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

def collect_series(elmres):
    rows = int(elmres.GetNumberOfRows())
    columns = int(elmres.GetNumberOfColumns())
    if rows <= 0:
        raise RuntimeError('ElmRes contains no result rows.')
    if columns <= 0:
        raise RuntimeError('ElmRes contains no result columns.')
    if rows > MAX_RESULT_ROWS:
        raise RuntimeError('ElmRes has {} rows and exceeds the limit of {} (MAX_RESULT_ROWS).'.format(rows, MAX_RESULT_ROWS))
    t_column = time_column(elmres, columns)
    try:
        time_unit = normalize_time_unit(elmres.GetUnit(t_column))
    except Exception as exc:
        raise RuntimeError('The ElmRes time-column unit could not be read: {}'.format(exc)) from exc
    if time_unit not in {'s', 'min', 'h', 'd'}:
        raise RuntimeError('Unsupported ElmRes time-column unit: {}'.format(time_unit or TIME_UNIT_FALLBACK))
    plot_times = []
    labels = []
    for row, raw in enumerate(read_column(elmres, t_column, rows)):
        if raw is None:
            raise RuntimeError('Invalid time value in ElmRes cell ({}, {}).'.format(row, t_column))
        plot_times.append(time_in_hours(raw, time_unit, row))
        labels.append(format_time(raw, row, time_unit))
    if any((current <= previous for previous, current in zip(plot_times, plot_times[1:]))):
        raise RuntimeError('The ElmRes time axis is not strictly increasing.')
    chosen = {}
    for column in range(columns):
        try:
            obj = elmres.GetObject(column)
            variable = str(elmres.GetVariable(column))
            category = result_category(obj, variable)
        except Exception:
            continue
        if not category or variable not in VARIABLES[category]:
            continue
        key = (category, object_key(obj))
        priority = VARIABLES[category].index(variable)
        if key not in chosen or priority < chosen[key][0]:
            chosen[key] = (priority, column, obj, variable)
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
        series.append({'category': category, 'object': obj, 'key': object_key(obj), 'element_id': object_id(obj), 'element_name': object_name(obj), 'voltage_level': voltage_level(obj), 'variable_id': variable, 'variable': {'voltage': 'Voltage magnitude', 'voltage_angle': 'Voltage angle'}.get(category, 'Loading'), 'unit': unit, 'points': points})
        item = series[-1]
        item['statistics'] = statistics(item)
        item['points'] = sampled_plot_points(item)
    if not series:
        raise RuntimeError('ElmRes contains no completely readable supported result series.')
    return (series, labels, plot_times, time_unit)

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
    for item in series:
        stats = dict(item.get('statistics') or statistics(item))
        for reference_key, delta_key, _ in DELTA_KEYS:
            stats[reference_key] = None
            stats[delta_key] = None
        by_category[item['category']].append((item, stats))
        stats_by_key[item['category'], item['key']] = stats
    return {'id': case['id'], 'name': case['name'], 'kind': case.get('kind', 'case'), 'description': case.get('description', ''), 'status': case.get('status', CONVERGED), 'error_code': case.get('error_code'), 'message': case.get('message', ''), 'out_of_service': list(case.get('out_of_service', ())), 'is_reference': 1 if case['id'] == REFERENCE_ID else 0, 'labels': list(labels), 'plot_times': list(plot_times), 'time_unit': time_unit, 'by_category': by_category, 'stats_by_key': stats_by_key}

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
            item = next((entry[0] for entry in result['by_category'][category] if entry[0]['key'] == key))
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
PLOT_SELECTORS = (('line', False), ('transformer', False), ('voltage', True), ('voltage', False))

def _plots(payload, results):
    chosen = []
    for category, use_min in PLOT_SELECTORS:
        if use_min:
            predicate = lambda stats: stats['min'] < VOLTAGE_MIN
        elif category == 'voltage':
            predicate = lambda stats: stats['max'] > VOLTAGE_MAX
        else:
            predicate = None
        entries = _collect(results, category, predicate=predicate)
        if not entries:
            continue
        best = (min(entries, key=lambda entry: entry[2]['min']) if use_min else max(entries, key=lambda entry: entry[2]['max']))[1]
        if any((existing[1] == best['key'] for existing in chosen)):
            continue
        chosen.append((category, best['key'], best))
    for index, (category, key, item) in enumerate(chosen[:MAX_PLOTS], 1):
        plot_id = 'P{:03d}'.format(index)
        payload['ScriptedPlots'].append({'plot_id': plot_id, 'plot_title': '{} - {}'.format(item['element_name'], item['variable']), 'case_id': '', 'element_id': item['element_id'], 'element_name': item['element_name'], 'variable': item['variable'], 'unit': item['unit']})
        for result in converged(results):
            match = next((entry[0] for entry in result['by_category'][category] if entry[0]['key'] == key), None)
            if match is None:
                continue
            for _, timestamp, value in sampled_plot_points(match):
                payload['ScriptedPlotData'].append({'plot_id': plot_id, 'case_id': result['id'], 'series_role': result['id'], 'timestamp': timestamp, 'value': value})

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
    payload['ScriptedReportMeta'].append({'study_id': object_name(study_case), 'study_name': object_name(study_case), 'study_description': object_description(study_case), 'model_name': project_name, 'model_version': 'PowerFactory 2026', 'simulation_start': start, 'simulation_end': end, 'simulation_time_step': time_step or 'ElmRes row interval', 'generation_date': datetime.now().astimezone().isoformat(timespec='seconds'), 'generated_by': generated_by, 'run_mode': run_mode, 'template_name': TEMPLATE_NAME, 'template_version': TEMPLATE_VERSION, 'data_contract_version': DATA_CONTRACT_VERSION, 'result_name': result_name, 'assessment_scope': '{} case(s); reference: {}'.format(len(results), reference['id'] if reference else 'none'), 'assessment_status': 'PRE-ASSESSMENT - NOT AN OPERATIONAL RELEASE', 'has_line_bars': '0', 'has_transformer_bars': '0', 'has_voltage_bars': '0', 'has_angle_bars': '0'})
    identity = outage_identity(results)
    for result in results:
        payload['ScriptedCases'].append({'case_id': result['id'], 'case_name': result['name'], 'is_reference': result['is_reference'], 'description': result['description'], 'simulation_status': result['status'], 'simulation_start': result['labels'][0] if result['labels'] else '', 'simulation_end': result['labels'][-1] if result['labels'] else ''})
        for outage in result['out_of_service']:
            element_class, name = outage[:2]
            key = outage[2] if len(outage) > 2 else name
            label = identity.get(key, name)
            payload['ScriptedCaseMatrix'].append({'element_id': label, 'element_name': label, 'element_type': _element_type(element_class), 'case_id': result['id'], 'is_out_of_service': 1, 'status_label': 'OFF'})
    for outage in planned_outages:
        payload['ScriptedPlannedOutages'].append({'case_id': 'OUTAGE' if outage['status'] == 'APPLIED' else 'N/A', 'outage_id': outage['id'], 'outage_name': outage['name'], 'source_class': outage['source_class'], 'status': outage['status'], 'skip_reason': outage.get('skip_reason', ''), 'equipment_name': outage.get('equipment_name', ''), 'equipment_type': outage.get('equipment_type', ''), 'switching_actions': outage.get('switching_actions', ''), 'start_time': outage.get('start_time', ''), 'end_time': outage.get('end_time', '')})
    applied = sum((item['status'] == 'APPLIED' for item in planned_outages))
    skipped = len(planned_outages) - applied
    outage_status = 'PASS' if applied and skipped == 0 else 'WARNING'
    payload['ScriptedModelQuality'].append({'check_id': 'planned_outages', 'check_name': 'Planned outage applicability', 'status': outage_status, 'message': '{} found; {} applied; {} skipped.'.format(len(planned_outages), applied, skipped), 'affected_element': ''})
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
    _plots(payload, results)
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
    plot_ids = [row.get('plot_id') for row in payload['ScriptedPlots']]
    if len(plot_ids) != len(set(plot_ids)):
        raise ValueError('Duplicate plot_id would mix chart data.')
    known_plot_ids = set(plot_ids)
    known_roles = {row.get('case_id') for row in payload['ScriptedCases']}
    for index, row in enumerate(payload['ScriptedPlotData']):
        if row.get('plot_id') not in known_plot_ids:
            raise ValueError('ScriptedPlotData row {} has no parent plot.'.format(index))
        if row.get('series_role') not in known_roles:
            raise ValueError('ScriptedPlotData row {} has invalid series_role.'.format(index))

def _check(returned, context):
    code = api_error_code(returned)
    if code is not None:
        raise RuntimeError('{} returned error code {:g}'.format(context, code))

def publish_report(report, payload, log=None):
    validate_payload(payload)
    if report is None or class_name(report) != 'IntReport':
        raise RuntimeError('Run this ComPython as a child of an IntReport.')
    for method in ('Reset', 'CreateTable', 'CreateField', 'SetValue'):
        if not callable(getattr(report, method, None)):
            raise RuntimeError('IntReport is missing method ' + method)
    context = 'Reset'
    try:
        report.Reset()
        for name, fields in TABLES:
            if not name.startswith(HOST_TABLE_PREFIX):
                raise ValueError('Table lacks host prefix: ' + name)
            native_name = name[len(HOST_TABLE_PREFIX):]
            context = 'CreateTable({})'.format(native_name)
            _check(report.CreateTable(native_name), context)
            for field, kind in fields:
                context = 'CreateField({}.{})'.format(native_name, field)
                _check(report.CreateField(native_name, field, FIELD_TYPES[kind]), context)
            for index, row in enumerate(payload[name]):
                for field, _ in fields:
                    value = row.get(field)
                    if value is None:
                        continue
                    context = 'SetValue({}.{}, row {})'.format(native_name, field, index)
                    _check(report.SetValue(native_name, field, index, value), context)
            if log:
                log('GridLens: {} -> {}: {} rows'.format(native_name, name, len(payload[name])))
    except Exception as exc:
        try:
            report.Reset()
        except Exception:
            pass
        raise RuntimeError('GridLens publication failed at ' + context) from exc
    return {name: len(rows) for name, rows in payload.items()}


TOTAL_STEPS = 7
OUTAGE_CLASSES = ("IntPlannedout", "IntOutage")
REFERENCE_CASE_ID = "REF"
OUTAGE_CASE_ID = "OUTAGE"


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
        try:
            return datetime.fromtimestamp(numeric).astimezone().isoformat(
                timespec="seconds")
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
    for attribute in (
            "p_target", "pTarget", "pObject", "p_object", "obj_id",
            "pDevice", "cpObject", "pElm", "p_target1", "p_target2"):
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
        for attribute in (
                "p_target", "pTarget", "pObject", "p_object", "obj_id",
                "pDevice", "cpObject", "pElm"):
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
    start = _first_attribute(
        outage, ("tStart", "t_start", "start_time", "date_start", "time_start"))
    end = _first_attribute(
        outage, ("tEnd", "t_end", "end_time", "date_end", "time_end"))
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
        "_object": outage,
        "_reset": None,
        "_check": None,
    }


def _check_is_applied(record):
    method = record.get("_check")
    if not callable(method):
        return None
    try:
        value = _call_without_or_with_zero(method)
    except Exception as exc:
        raise GridLensError(
            "Could not verify planned outage '{}': {}".format(
                record["name"], _friendly_exception(exc))) from None
    if str(safe_attr(method, "__name__", "")).lower().startswith("is"):
        numeric = finite_number(value)
        return bool(numeric) if numeric is not None else bool(value)
    code = return_code(value)
    if code is None:
        raise GridLensError(
            "Planned outage '{}' returned an unreadable Check value.".format(
                record["name"]))
    return code == 0.0


def _method(outage, names):
    for name in names:
        value = getattr(outage, name, None)
        if callable(value):
            return value
    return None


def _study_time_allows(outage):
    method = _method(outage, ("IsInStudyTime", "IsWithinStudyTime"))
    if method is None:
        return None
    value = _call_without_or_with_zero(method)
    numeric = finite_number(value)
    return bool(numeric) if numeric is not None else bool(value)


def apply_available_outages(app, logger, applied=None):
    """Apply every safely verifiable outage and return records and handles."""
    objects = _find_project_outages(app)
    records = [_outage_record(item) for item in objects]
    applied = applied if applied is not None else []
    names = {}
    for record in records:
        names[record["name"]] = names.get(record["name"], 0) + 1
    for record in records:
        if names[record["name"]] > 1:
            record["id"] = "{} ({})".format(
                record["name"], _key_discriminator(object_key(record["_object"])))
    logger.write(
        "OUTAGES", "Found {} planned outage object(s).".format(len(records)), 3)
    for index, record in enumerate(records, 1):
        outage = record["_object"]
        prefix = "Outage {}/{} '{}': ".format(index, len(records), record["name"])
        if finite_number(safe_attr(outage, "outserv", 0)) == 1.0:
            record["status"] = "SKIPPED"
            record["skip_reason"] = "Outage object is disabled (outserv=1)."
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        apply_method = _method(outage, ("Apply", "ApplyOutage"))
        reset_method = _method(outage, ("Reset", "ResetOutage"))
        check_method = _method(outage, ("Check", "IsApplied"))
        record["_reset"] = reset_method
        record["_check"] = check_method
        missing = []
        if apply_method is None:
            missing.append("Apply")
        if reset_method is None:
            missing.append("Reset")
        if check_method is None:
            missing.append("Check/IsApplied")
        if missing:
            record["status"] = "SKIPPED"
            record["skip_reason"] = (
                "Required PowerFactory API method(s) unavailable: {}."
                .format(", ".join(missing)))
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        try:
            in_study_time = _study_time_allows(outage)
        except Exception as exc:
            record["status"] = "SKIPPED"
            record["skip_reason"] = "Study-time check failed: {}".format(
                _friendly_exception(exc))
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        if in_study_time is False:
            record["status"] = "SKIPPED"
            record["skip_reason"] = "Outage is outside the active study time."
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        try:
            initially_applied = _check_is_applied(record)
        except Exception as exc:
            record["status"] = "SKIPPED"
            record["skip_reason"] = (
                "Initial state could not be verified; no change was attempted: {}"
                .format(_friendly_exception(exc)))
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        if initially_applied is True:
            record["status"] = "SKIPPED"
            record["skip_reason"] = "Outage is already active."
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        try:
            returned = _call_without_or_with_zero(apply_method)
            code = return_code(returned)
            if code is None or code != 0.0:
                raise GridLensError(
                    "Apply returned {}.".format(
                        "an unreadable value" if code is None
                        else "error code {:g}".format(code)))
            if _check_is_applied(record) is not True:
                raise GridLensError("application could not be verified by Check.")
        except Exception as exc:
            reset_error = None
            try:
                reset_returned = _call_without_or_with_zero(reset_method)
                reset_code = return_code(reset_returned)
                if reset_code is None or reset_code != 0.0:
                    raise GridLensError("immediate Reset returned an error")
                if _check_is_applied(record) is not False:
                    raise GridLensError("immediate Reset could not be verified")
            except Exception as cleanup_exc:
                reset_error = cleanup_exc
            if reset_error is not None:
                if record not in applied:
                    applied.append(record)
                raise GridLensError(
                    "Planned outage '{}' failed during Apply and could not be "
                    "reset immediately: {}. The final restoration pass will "
                    "retry.".format(record["name"],
                                     _friendly_exception(reset_error))) from None
            record["status"] = "SKIPPED"
            record["skip_reason"] = "Could not apply safely: {}".format(
                _friendly_exception(exc))
            logger.write("OUTAGES", prefix + record["skip_reason"], 3, "WARNING")
            continue
        record["status"] = "APPLIED"
        record["skip_reason"] = ""
        applied.append(record)
        logger.write("OUTAGES", prefix + "applied and verified.", 3)
    return records, applied


def restore_outages(applied, logger):
    errors = []
    for record in reversed(applied):
        try:
            returned = _call_without_or_with_zero(record["_reset"])
            code = return_code(returned)
            if code is None or code != 0.0:
                raise GridLensError(
                    "Reset returned {}".format(
                        "an unreadable value" if code is None
                        else "error code {:g}".format(code)))
            if _check_is_applied(record) is not False:
                raise GridLensError("reset could not be verified by Check")
            logger.write(
                "RESTORE", "Reset planned outage '{}'.".format(record["name"]), 6)
        except Exception as exc:
            errors.append("{}: {}".format(record["name"], _friendly_exception(exc)))
    return errors


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
            if finite_number(safe_attr(item, "outserv", 0)) == 1.0:
                found[object_key(item)] = (
                    class_name(item), object_name(item), object_key(item))
    return [found[key] for key in sorted(found)]


def _run_calculation(app, study_case, qds, case_id, name, description,
                     original_result, logger, temporary_results):
    snapshot = _temporary_result(study_case, original_result, case_id)
    temporary_results.append(snapshot)
    if not _set_attribute(qds, "results", snapshot):
        raise GridLensError(
            "PowerFactory did not bind ComStatsim.results to the temporary "
            "ElmRes. No calculation was started.")
    logger.write(
        "CALCULATION",
        "Starting {} with the active ComStatsim settings unchanged."
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
        series, labels, plot_times, unit = collect_series(snapshot)
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
    return case_result(case, series, labels, plot_times, unit)


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
        current = current.__cause__ or current.__context__
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
    logger.write(
        "CONTEXT",
        "Study case '{}'; QDS '{}'; result '{}'; reference flag {}."
        .format(object_name(study_case), object_name(qds),
                object_name(original_result), RUN_REFERENCE_CASE), 2)
    results = []
    records = []
    applied = []
    temporary_results = []
    state_errors = []
    try:
        if RUN_REFERENCE_CASE:
            results.append(_run_calculation(
                app, study_case, qds, REFERENCE_CASE_ID, "Reference",
                "Initial network state before GridLens applies planned outages.",
                original_result, logger, temporary_results))
        records, _ = apply_available_outages(app, logger, applied)
        if applied:
            results.append(_run_calculation(
                app, study_case, qds, OUTAGE_CASE_ID,
                "Combined planned outages",
                "All planned outages that GridLens safely applied together.",
                original_result, logger, temporary_results))
        else:
            logger.write(
                "CALCULATION",
                "No applicable planned outage was found; the outage run was skipped.",
                4, "WARNING")
    finally:
        logger.write("RESTORE", "Restoring the original PowerFactory state.", 6)
        state_errors.extend(restore_outages(applied, logger))
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
    if applied and RUN_REFERENCE_CASE:
        run_mode = "REFERENCE + COMBINED PLANNED OUTAGES"
    elif applied:
        run_mode = "COMBINED PLANNED OUTAGES ONLY"
    elif RUN_REFERENCE_CASE:
        run_mode = "REFERENCE ONLY - NO APPLICABLE PLANNED OUTAGES"
    else:
        run_mode = "NO CALCULATION - NO APPLICABLE PLANNED OUTAGES"
    payload = build_cases_payload(
        study_case, results,
        object_name(project) if project else "Active PowerFactory model",
        "Temporary QDS results removed after validated extraction"
        if temporary_results else "No calculation executed",
        records, _generated_by(), run_mode)
    logger.write(
        "REPORT", "Publishing {} validated report tables.".format(len(TABLES)), 7)
    counts = publish_report(report, payload, log=lambda message: logger.write(
        "REPORT", message, 7))
    logger.write(
        "COMPLETE",
        "Report published successfully: {} table(s), {} applied outage(s), "
        "{} calculated case(s).".format(len(counts), len(applied), len(results)), 7)
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
