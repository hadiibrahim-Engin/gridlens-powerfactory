"""Duck-typed Zugriffe auf PowerFactory-Objekte und Zahlenumwandlung."""

import math

from .config import CLASS_CATEGORIES, VARIABLES


def safe_attr(obj, name, default=None):
    try:
        value = getattr(obj, name)
        return default if value is None else value
    except Exception:
        return default


def object_key(obj):
    """Stable internal key; never written to the report."""
    try:
        value = obj.GetFullName()
        if value:
            return str(value)
    except Exception:
        pass
    return str(safe_attr(obj, "loc_name", "unknown"))


def object_name(obj):
    value = safe_attr(obj, "loc_name", "")
    return str(value) if value else object_key(obj).rsplit("\\", 1)[-1]


def object_id(obj):
    """Short report identifier requested by the user: PowerFactory name only."""
    return object_name(obj)


def object_description(obj):
    value = safe_attr(obj, "desc", "")
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value if item)
    return str(value or "")


def class_name(obj):
    try:
        return str(obj.GetClassName())
    except Exception:
        return ""


def result_category(obj, variable):
    """Return the supported category for one object/result-variable pair."""
    for category in CLASS_CATEGORIES.get(class_name(obj), ()):
        if variable in VARIABLES[category]:
            return category
    return None


def finite_number(value):
    """Convert a PowerFactory result value to float or return None."""
    if isinstance(value, (tuple, list)):
        if len(value) >= 2:
            value = value[1]
        elif value:
            value = value[0]
        else:
            return None
    if value is None or type(value) is bool:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if "," in value and "." not in value and value.count(",") == 1:
            value = value.replace(",", ".")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def result_value(elmres, row, column):
    try:
        return finite_number(elmres.GetValue(row, column))
    except Exception:
        return None

