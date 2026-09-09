"""Auswahl des Ergebnisobjekts und Aufbereitung der Zeitreihen."""

import math

from . import config
from .config import (
    MAX_PLOT_POINTS, RESULT_FILE_NAME, TIME_UNIT_FALLBACK, VARIABLES,
)
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


def read_column(elmres, column, rows):
    """Read one full ElmRes column, preferring the block access API.

    DIgSILENT recommends GetColumnValues over cell-by-cell GetValue for large
    result files. Not every build exposes it, so a failure falls back to the
    cell reader. A column of the wrong length is refused rather than padded:
    a silently shortened series would misplace every later time point.
    """
    reader = getattr(elmres, "GetColumnValues", None)
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
                raise RuntimeError(
                    "ElmRes-Spalte {} liefert {} statt {} Werten.".format(
                        column, len(raw), rows))
            else:
                return [finite_number(value) for value in raw]
    return [result_value(elmres, row, column) for row in range(rows)]


def _is_sequence(value):
    return isinstance(value, (list, tuple))


def collect_series(elmres):
    rows = int(elmres.GetNumberOfRows())
    columns = int(elmres.GetNumberOfColumns())
    if rows <= 0:
        raise RuntimeError("ElmRes enthält keine Ergebniszeilen.")
    if columns <= 0:
        raise RuntimeError("ElmRes enthält keine Ergebnisspalten.")
    if rows > config.MAX_RESULT_ROWS:
        raise RuntimeError(
            "ElmRes hat {} Zeilen und überschreitet die Grenze von {} "
            "(MAX_RESULT_ROWS in config.py).".format(
                rows, config.MAX_RESULT_ROWS))
    t_column = time_column(elmres, columns)
    try:
        time_unit = normalize_time_unit(elmres.GetUnit(t_column))
    except Exception as exc:
        raise RuntimeError(
            "Zeiteinheit der ElmRes-Zeitspalte konnte nicht gelesen werden: "
            "{}".format(exc)) from exc
    if time_unit not in {"s", "min", "h", "d"}:
        raise RuntimeError(
            "Nicht unterstützte Zeiteinheit der ElmRes-Zeitspalte: {}".format(
                time_unit or TIME_UNIT_FALLBACK))
    plot_times = []
    labels = []
    for row, raw in enumerate(read_column(elmres, t_column, rows)):
        if raw is None:
            raise RuntimeError(
                "Ungültiger Zeitwert in ElmRes-Zelle ({}, {}).".format(
                    row, t_column))
        plot_times.append(time_in_hours(raw, time_unit, row))
        labels.append(format_time(raw, row, time_unit))
    if any(current <= previous
           for previous, current in zip(plot_times, plot_times[1:])):
        raise RuntimeError(
            "ElmRes-Zeitachse ist nicht streng monoton steigend.")

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

    cells = rows * len(chosen)
    if cells > config.MAX_RESULT_CELLS:
        raise RuntimeError(
            "ElmRes ergibt {} auszuwertende Zellen ({} Zeilen x {} Reihen) "
            "und überschreitet die Grenze von {} (MAX_RESULT_CELLS in "
            "config.py).".format(
                cells, rows, len(chosen), config.MAX_RESULT_CELLS))

    series = []
    for (_, _), (_, column, obj, variable) in sorted(chosen.items()):
        points = []
        for row, value in enumerate(read_column(elmres, column, rows)):
            if value is None:
                raise RuntimeError(
                    "Ungültiger Ergebniswert in ElmRes-Zelle ({}, {}) für "
                    "{} {}.".format(row, column, object_name(obj), variable))
            points.append((labels[row], plot_times[row], value))
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
        # Statistics need every value; the chart never shows more than
        # MAX_PLOT_POINTS. Computing one and keeping the other turns the
        # per-case memory from O(series x rows) into O(series).
        item = series[-1]
        item["statistics"] = statistics(item)
        item["points"] = sampled_plot_points(item)
    if not series:
        raise RuntimeError(
            "ElmRes enthält keine vollständig lesbare unterstützte Ergebnisreihe.")
    return series, labels, plot_times, time_unit


def check_run_budget(results):
    """Refuse a report run whose cases do not fit the documented budget.

    Rankings, reference deltas and plot selection are formed across cases, so
    every case stays in memory until the tables are built. Without this check
    a large project would only show up as a stalled or killed PowerFactory.
    """
    cells = 0
    for result in results:
        rows = len(result["labels"])
        for category in result["by_category"]:
            cells += rows * len(result["by_category"][category])
    if cells > config.MAX_RUN_CELLS:
        raise RuntimeError(
            "Der Lauf umfasst {} Ergebniszellen über {} Fälle und "
            "überschreitet die Grenze von {} (MAX_RUN_CELLS in config.py). "
            "Fallzahl, Zeitbereich oder Elementumfang reduzieren.".format(
                cells, len(results), config.MAX_RUN_CELLS))
    return cells


def sampled_plot_points(item):
    """Bound chart size while retaining endpoints and exact extrema."""
    points = item["points"]
    if len(points) <= MAX_PLOT_POINTS:
        return points
    values = [point[2] for point in points]
    indices = {0, len(points) - 1,
               values.index(min(values)), values.index(max(values))}
    for sample in range(MAX_PLOT_POINTS):
        indices.add(int(round(sample * (len(points) - 1)
                              / float(MAX_PLOT_POINTS - 1))))
    return [points[index] for index in sorted(indices)]


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
