"""Duck-typed Zugriffe auf PowerFactory-Objekte und Zahlenumwandlung."""

import hashlib
import math

from .config import CLASS_CATEGORIES, VARIABLES


def safe_attr(obj, name, default=None):
    try:
        value = getattr(obj, name)
        return default if value is None else value
    except Exception:
        return default


def clip_text(value, limit):
    """Shorten a report string to `limit` characters, keeping it unique.

    A truncated name would otherwise merge two different elements into one
    row or one chart series, so the clipped value carries a short stable
    marker derived from the full text.
    """
    text = str(value)
    if len(text) <= limit:
        return text
    marker = "~" + hashlib.sha256(
        text.encode("utf-8")).hexdigest()[:6]
    keep = max(0, limit - len(marker))
    return text[:keep] + marker[:limit]


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
    """Convert a single PowerFactory value to float or return None.

    Sequences are rejected on purpose. A PowerFactory call that returns a
    ``(code, value)`` pair must be normalised by ``return_code`` or
    ``result_value`` first, so that an error code can never be mistaken for a
    measured quantity.
    """
    if isinstance(value, (tuple, list)):
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


def return_code(value):
    """Normalise the return value of a PowerFactory command to an error code.

    ``None`` is the usual success shape of a command that returns nothing.
    A sequence is read as ``(code, ...)``. An unreadable return value yields
    ``None`` so that callers fail closed instead of assuming success.
    """
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
    """Read one ElmRes cell and reject non-zero PowerFactory error codes."""
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
