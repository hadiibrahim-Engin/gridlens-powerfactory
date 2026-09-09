"""Zeiteinheit, Normierung auf Stunden und lesbare Zeitformate."""

from .config import TIME_UNIT_FALLBACK
from .pfutil import finite_number


def normalize_time_unit(unit):
    text = str(unit or "").strip().lower().replace(" ", "")
    aliases = {
        "s": "s", "sec": "s", "second": "s", "seconds": "s",
        "min": "min", "minute": "min", "minutes": "min",
        "h": "h", "hr": "h", "hour": "h", "hours": "h",
        "d": "d", "day": "d", "days": "d",
    }
    return aliases.get(text, text or TIME_UNIT_FALLBACK)


def time_in_hours(value, unit, row):
    numeric = finite_number(value)
    if numeric is None:
        return float(row)
    factor = {"s": 1.0 / 3600.0, "min": 1.0 / 60.0,
              "h": 1.0, "d": 24.0}.get(normalize_time_unit(unit), 1.0)
    return numeric * factor


def format_clock(hours):
    sign = "-" if hours < 0 else ""
    total_seconds = int(round(abs(hours) * 3600.0))
    days, remainder = divmod(total_seconds, 86400)
    hour, remainder = divmod(remainder, 3600)
    minute, second = divmod(remainder, 60)
    clock = "{:02d}:{:02d}".format(hour, minute)
    if second:
        clock += ":{:02d}".format(second)
    if days:
        return "{}{} d {}".format(sign, days, clock)
    return sign + clock


def format_time(value, row, unit):
    if isinstance(value, (tuple, list)):
        value = value[1] if len(value) >= 2 else (value[0] if value else None)
    if finite_number(value) is not None:
        return format_clock(time_in_hours(value, unit, row))
    if value is not None and str(value).strip():
        return str(value)
    return "Zeitschritt {}".format(row)


def format_time_step(hours):
    if hours < 1.0 / 60.0:
        return "{:g} s".format(hours * 3600.0)
    if hours < 1.0:
        return "{:g} min".format(hours * 60.0)
    if hours < 24.0:
        return "{:g} h".format(hours)
    return "{:g} d".format(hours / 24.0)


def time_column(elmres, column_count):
    candidates = ("b:tnow", "t", "time")
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
    return 0

