"""Auswahl des Ergebnisobjekts und Aufbereitung der Zeitreihen."""

import math

from .config import RESULT_FILE_NAME, TIME_UNIT_FALLBACK, VARIABLES
from .pfutil import (
    finite_number, object_id, object_key, object_name, result_category,
    result_value, safe_attr,
)
from .timeaxis import (
    format_time, normalize_time_unit, time_column, time_in_hours,
)


def result_objects(study_case):
    """Return all ElmRes objects reachable from the active study case."""
    found = []
    if RESULT_FILE_NAME:
        try:
            found.extend(study_case.GetContents(RESULT_FILE_NAME) or [])
        except Exception:
            pass
    for recursive in (1, None):
        try:
            values = (study_case.GetContents("*.ElmRes", recursive)
                      if recursive is not None else study_case.GetContents("*.ElmRes"))
            found.extend(values or [])
        except Exception:
            pass
    unique = []
    seen = set()
    for item in found:
        key = object_key(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def supported_column_count(elmres):
    try:
        elmres.Load()
        rows = int(elmres.GetNumberOfRows())
        columns = int(elmres.GetNumberOfColumns())
        supported = 0
        for column in range(columns):
            try:
                obj = elmres.GetObject(column)
                variable = str(elmres.GetVariable(column))
                category = result_category(obj, variable)
                if category:
                    supported += 1
            except Exception:
                pass
        return rows, supported
    except Exception:
        return 0, 0
    finally:
        try:
            elmres.Release()
        except Exception:
            pass


def select_result(study_case):
    candidates = result_objects(study_case)
    if not candidates:
        raise RuntimeError("No ElmRes found in the active study case.")
    scored = [(supported_column_count(item), index, item)
              for index, item in enumerate(candidates)]
    scored.sort(key=lambda entry: (entry[0][1], entry[0][0], -entry[1]), reverse=True)
    (rows, supported), _, selected = scored[0]
    if rows <= 0:
        raise RuntimeError("The active study case has no populated ElmRes.")
    if supported <= 0:
        raise RuntimeError(
            "ElmRes enthält keine unterstützten Spalten für Auslastung, "
            "Spannungsbetrag oder Spannungswinkel."
        )
    return selected


def voltage_level(obj):
    candidates = [obj]
    for attribute in ("bus1", "bus2", "bushv", "buslv", "busmv"):
        cubicle = safe_attr(obj, attribute)
        terminal = safe_attr(cubicle, "cterm") if cubicle else None
        if terminal:
            candidates.append(terminal)
    for item in candidates:
        nominal = finite_number(safe_attr(item, "uknom"))
        if nominal is not None:
            return "{:g} kV".format(nominal)
    return ""


def collect_series(elmres):
    rows = int(elmres.GetNumberOfRows())
    columns = int(elmres.GetNumberOfColumns())
    t_column = time_column(elmres, columns)
    try:
        time_unit = normalize_time_unit(elmres.GetUnit(t_column))
    except Exception:
        time_unit = TIME_UNIT_FALLBACK
    plot_times = []
    labels = []
    for row in range(rows):
        try:
            raw = elmres.GetValue(row, t_column)
        except Exception:
            raw = row
        plot_times.append(time_in_hours(raw, time_unit, row))
        labels.append(format_time(raw, row, time_unit))

    # Keep only the preferred supported variable for each object/category.
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

    series = []
    for (_, _), (_, column, obj, variable) in sorted(chosen.items()):
        points = []
        for row in range(rows):
            value = result_value(elmres, row, column)
            if value is not None:
                points.append((labels[row], plot_times[row], value))
        if not points:
            continue
        category = result_category(obj, variable)
        try:
            unit = str(elmres.GetUnit(column) or "")
        except Exception:
            unit = ""
        if not unit:
            unit = {
                "voltage": "p.u.",
                "voltage_angle": "deg",
            }.get(category, "%")
        series.append({
            "category": category,
            "object": obj,
            # Full PowerFactory path. Internal only: matches the same element
            # across cases, because loc_name is not project-wide unique.
            "key": object_key(obj),
            "element_id": object_id(obj),
            "element_name": object_name(obj),
            "voltage_level": voltage_level(obj),
            "variable_id": variable,
            "variable": {
                "voltage": "Spannungsbetrag",
                "voltage_angle": "Spannungswinkel",
            }.get(category, "Auslastung"),
            "unit": unit,
            "points": points,
        })
    return series, labels, plot_times, time_unit


def percentile95(values):
    ordered = sorted(values)
    index = max(0, int(math.ceil(0.95 * len(ordered))) - 1)
    return ordered[index]


def statistics(series):
    values = [value for _, _, value in series["points"]]
    minimum = min(values)
    maximum = max(values)
    return {
        "min": minimum,
        "max": maximum,
        "mean": sum(values) / len(values),
        "p95": percentile95(values),
        "time_min": next(label for label, _, value in series["points"]
                         if value == minimum),
        "time_max": next(label for label, _, value in series["points"]
                         if value == maximum),
    }
