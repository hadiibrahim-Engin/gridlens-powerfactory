"""Validierung der Payload und Publikation der nativen IntReport-Tabellen."""

from .config import HOST_TABLE_PREFIX
from .pfutil import class_name, clip_text, finite_number
from .tables import (
    FIELD_TYPES, MAX_TEXT_LENGTH, REQUIRED_FIELDS, TABLES, text_limit,
)


def coerce_value(value, kind, where, field=None):
    """Convert one payload value to the type the IntReport field expects.

    `field` selects the length budget for text; without it the generous
    free-text budget applies.
    """
    if value is None:
        return None
    if kind == "string":
        return clip_text(value, text_limit(field) if field else MAX_TEXT_LENGTH)
    if type(value) is bool:
        raise ValueError(where + ": boolean is not a numeric value")
    if kind == "integer":
        numeric = finite_number(value)
        if numeric is None or not numeric.is_integer():
            raise ValueError(where + ": invalid integer " + repr(value))
        result = int(numeric)
        if not -(2 ** 31) <= result < 2 ** 31:
            raise ValueError(where + ": integer outside 32-bit range")
        return result
    if kind == "number":
        result = finite_number(value)
        if result is None:
            raise ValueError(where + ": invalid finite number " + repr(value))
        return result
    raise ValueError(where + ": unsupported type " + repr(kind))


def api_error_code(value):
    """Return a non-zero PowerFactory error code, or None when there is none.

    CreateTable, CreateField and SetValue may return nothing, an object handle
    or a numeric status depending on the build. Only a readable non-zero
    number counts as a failure, so that an object handle is never mistaken for
    an error code. Genuine API exceptions are handled by the caller.
    """
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
        raise ValueError("Internal table declaration and payload do not match.")
    if set(REQUIRED_FIELDS) != expected:
        raise ValueError("Required-field declaration does not cover all tables.")
    for name, fields in TABLES:
        rows = payload[name]
        if not isinstance(rows, list):
            raise ValueError(name + ": rows must be a list")
        if name == "ScriptedReportMeta" and len(rows) != 1:
            raise ValueError(name + ": exactly one row is required")
        field_names = {field for field, _ in fields}
        for index, row in enumerate(rows):
            unknown = set(row) - field_names
            if unknown:
                raise ValueError(name + ": unknown fields " + repr(sorted(unknown)))
            required = REQUIRED_FIELDS[name]
            for field, kind in fields:
                where = "{} row {}.{}".format(name, index, field)
                if field in row and row[field] is not None:
                    row[field] = coerce_value(
                        row[field], kind, where, field)
                if field not in required:
                    continue
                value = row.get(field)
                # A required field left empty would reach IntReport, SQL and
                # the rendered page as a silent blank instead of a visible
                # error, so it is rejected before report.Reset() runs.
                if value is None:
                    raise ValueError(where + ": required field is missing")
                if kind == "string" and not str(value).strip():
                    raise ValueError(where + ": required text is empty")
    plot_ids = [row.get("plot_id") for row in payload["ScriptedPlots"]]
    if len(plot_ids) != len(set(plot_ids)):
        raise ValueError("Duplicate plot_id would mix chart data.")
    known_plot_ids = set(plot_ids)
    # One curve per case: series_role carries the case id, so the valid set is
    # whatever ScriptedScenarios reported.
    known_roles = {row.get("scenario_id") for row in payload["ScriptedScenarios"]}
    for index, row in enumerate(payload["ScriptedPlotData"]):
        if row.get("plot_id") not in known_plot_ids:
            raise ValueError("ScriptedPlotData row {} has no parent plot.".format(index))
        if row.get("series_role") not in known_roles:
            raise ValueError("ScriptedPlotData row {} has invalid series_role.".format(index))


def _check(returned, context):
    code = api_error_code(returned)
    if code is not None:
        raise RuntimeError("{} lieferte Fehlercode {:g}".format(context, code))


def publish_report(report, payload, log=None):
    """Replace and publish all scripted tables owned by this IntReport."""
    validate_payload(payload)
    if report is None or class_name(report) != "IntReport":
        raise RuntimeError("Run this ComPython as a child of an IntReport.")
    for method in ("Reset", "CreateTable", "CreateField", "SetValue"):
        if not callable(getattr(report, method, None)):
            raise RuntimeError("IntReport is missing method " + method)
    context = "Reset"
    try:
        report.Reset()
        for name, fields in TABLES:
            if not name.startswith(HOST_TABLE_PREFIX):
                raise ValueError("Table lacks host prefix: " + name)
            native_name = name[len(HOST_TABLE_PREFIX):]
            context = "CreateTable({})".format(native_name)
            _check(report.CreateTable(native_name), context)
            for field, kind in fields:
                context = "CreateField({}.{})".format(native_name, field)
                _check(report.CreateField(
                    native_name, field, FIELD_TYPES[kind]), context)
            for index, row in enumerate(payload[name]):
                for field, _ in fields:
                    value = row.get(field)
                    if value is None:
                        continue
                    context = "SetValue({}.{}, row {})".format(native_name, field, index)
                    _check(report.SetValue(
                        native_name, field, index, value), context)
            if log:
                log("GridLens: {} -> {}: {} rows".format(
                    native_name, name, len(payload[name])))
    except Exception as exc:
        try:
            report.Reset()
        except Exception:
            pass
        raise RuntimeError("GridLens publication failed at " + context) from exc
    return {name: len(rows) for name, rows in payload.items()}
