"""Rechnet jeden Fall in ein eigenes Snapshot-ElmRes.

Der Runner laeuft niemals als Report-Erweiterung. Er veraendert den
Projektzustand und stellt ihn im finally-Zweig wieder her.
"""

from . import config
from .discovery import REFERENCE_ID, discover_cases
from .pfutil import class_name, finite_number, object_key, object_name, safe_attr

OUTAGE_SEPARATOR = "|"
OUTAGE_PATTERNS = ("*.ElmLne", "*.ElmTr2", "*.ElmTr3")
METADATA_PREFIX = "GridLensMeta."
METADATA_FIELDS = (
    "id", "name", "kind", "description", "status", "error_code", "message",
)


def _encode_metadata(value):
    """Escape one metadata value without an external file or JSON dependency."""
    text = "" if value is None else str(value)
    return (text.replace("%", "%25").replace("\r", "%0D")
            .replace("\n", "%0A").replace("=", "%3D"))


def _decode_metadata(value):
    # Reverse order matters because a literal "%0A" was encoded as "%250A".
    return (value.replace("%3D", "=").replace("%0A", "\n")
            .replace("%0D", "\r").replace("%25", "%"))


def _description_lines(snapshot):
    raw = safe_attr(snapshot, "desc", [])
    if isinstance(raw, str):
        return raw.splitlines()
    return [str(line) for line in (raw or [])]


def _set_description(snapshot, lines):
    try:
        snapshot.desc = list(lines)
        return True
    except Exception:
        try:
            snapshot.SetAttribute("desc", list(lines))
            return True
        except Exception:
            return False


def snapshot_name(case_id):
    return config.SNAPSHOT_PREFIX + case_id


def collect_outages(app):
    """Return (class, loc_name) for every switched-off branch element."""
    found = []
    seen = set()
    for pattern in OUTAGE_PATTERNS:
        objects = []
        for args in ((pattern, 1), (pattern,)):
            try:
                objects = app.GetCalcRelevantObjects(*args) or []
            except Exception:
                continue
            break
        for obj in objects:
            if finite_number(safe_attr(obj, "outserv", 0)) != 1.0:
                continue
            entry = (class_name(obj), object_name(obj))
            if entry not in seen:
                seen.add(entry)
                found.append(entry)
    return found


def write_outages(snapshot, outages):
    """Persist the outage list in the snapshot description."""
    lines = [
        "{}{}{}".format(element_class, OUTAGE_SEPARATOR, name)
        for element_class, name in outages
    ]
    _set_description(snapshot, lines)


def read_outages(snapshot):
    """Read the outage list back, tolerating a hand-written string."""
    result = []
    for line in _description_lines(snapshot):
        text = str(line).strip()
        if text.startswith(METADATA_PREFIX):
            continue
        if OUTAGE_SEPARATOR not in text:
            continue
        element_class, name = text.split(OUTAGE_SEPARATOR, 1)
        if element_class.strip() and name.strip():
            result.append((element_class.strip(), name.strip()))
    return result


def write_snapshot_record(snapshot, record):
    """Persist identity, status and outages with the result object itself."""
    lines = []
    for field in METADATA_FIELDS:
        lines.append("{}{}={}".format(
            METADATA_PREFIX, field, _encode_metadata(record.get(field))))
    lines.extend(
        "{}{}{}".format(element_class, OUTAGE_SEPARATOR, name)
        for element_class, name in record.get("outages", ())
    )
    if not _set_description(snapshot, lines):
        raise RuntimeError("Snapshot-Metadaten konnten nicht geschrieben werden.")


def read_snapshot_record(snapshot):
    """Read persisted case metadata; return an empty dict for legacy snapshots."""
    values = {}
    for line in _description_lines(snapshot):
        text = str(line)
        if not text.startswith(METADATA_PREFIX) or "=" not in text:
            continue
        field, encoded = text[len(METADATA_PREFIX):].split("=", 1)
        if field in METADATA_FIELDS:
            values[field] = _decode_metadata(encoded)
    if "error_code" in values:
        try:
            values["error_code"] = int(values["error_code"])
        except (TypeError, ValueError):
            values["error_code"] = None
    return values


def _existing(study_case, name):
    try:
        found = study_case.GetContents("*.ElmRes") or []
    except Exception:
        return None
    for item in found:
        if object_name(item) == name:
            return item
    return None


def _remove_obsolete_snapshots(study_case, case_ids):
    """Delete prefixed results that do not belong to the current discovery."""
    expected = {snapshot_name(case_id) for case_id in case_ids}
    try:
        found = study_case.GetContents("*.ElmRes") or []
    except Exception as exc:
        raise RuntimeError("Vorhandene Snapshots konnten nicht geprüft werden: {}".format(exc))
    for item in found:
        name = object_name(item)
        if not name.startswith(config.SNAPSHOT_PREFIX) or name in expected:
            continue
        try:
            item.Delete()
        except Exception as exc:
            raise RuntimeError(
                "Veralteter Snapshot {} konnte nicht gelöscht werden: {}".format(
                    name, exc))
    leftovers = []
    try:
        leftovers = [
            object_name(item) for item in (study_case.GetContents("*.ElmRes") or [])
            if object_name(item).startswith(config.SNAPSHOT_PREFIX)
            and object_name(item) not in expected
        ]
    except Exception:
        pass
    if leftovers:
        raise RuntimeError(
            "Veraltete Snapshots sind nach Delete noch vorhanden: {}".format(
                ", ".join(sorted(leftovers))))


def _as_object(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _prepare_snapshot(study_case, case_id, result_template=None):
    """Return a fresh snapshot, preferably with the QDS variable selection."""
    name = snapshot_name(case_id)
    stale = _existing(study_case, name)
    if stale is not None:
        try:
            stale.Delete()
        except Exception as exc:
            raise RuntimeError(
                "Vorhandener Snapshot {} konnte nicht gelöscht werden: {}".format(
                    name, exc))
        remaining = _existing(study_case, name)
        if remaining is stale:
            raise RuntimeError(
                "Vorhandener Snapshot {} ist nach Delete noch vorhanden.".format(name))
    snapshot = None
    if result_template is not None:
        try:
            snapshot = _as_object(study_case.AddCopy(result_template))
        except Exception:
            snapshot = None
        if snapshot is not None:
            try:
                snapshot.loc_name = name
            except Exception:
                _discard(snapshot)
                snapshot = None
            if snapshot is not None and object_name(snapshot) != name:
                _discard(snapshot)
                snapshot = None
    if snapshot is None:
        snapshot = study_case.CreateObject("ElmRes", name)
    if snapshot is None:
        raise RuntimeError("Snapshot {} konnte nicht angelegt werden.".format(name))
    if object_name(snapshot) != name:
        _discard(snapshot)
        raise RuntimeError("Snapshot erhielt nicht den Namen {}.".format(name))
    return snapshot


def _bind_results(qds, snapshot):
    """Point ComStatsim at the snapshot and verify the write took."""
    try:
        qds.results = snapshot
    except Exception:
        try:
            qds.SetAttribute("results", snapshot)
        except Exception:
            return False
    current = safe_attr(qds, "results")
    if current is snapshot:
        return True
    try:
        if current == snapshot:
            return True
    except Exception:
        pass
    return current is not None and object_key(current) == object_key(snapshot)


def _copy_into_snapshot(study_case, produced, case_id):
    """Fallback when the result binding did not take: copy afterwards."""
    if produced is None:
        return None
    try:
        copy = _as_object(study_case.AddCopy(produced))
    except Exception:
        return None
    if copy is None:
        return None
    try:
        copy.loc_name = snapshot_name(case_id)
    except Exception:
        return None
    return copy if object_name(copy) == snapshot_name(case_id) else None


def _active_scenario(app):
    try:
        return app.GetActiveScenario()
    except Exception:
        return None


def _same_object(left, right):
    if left is right:
        return True
    if left is None or right is None:
        return False
    return object_key(left) == object_key(right)


def _deactivate_active_scenario(app, log):
    active = _active_scenario(app)
    if active is None:
        return True, ""
    try:
        code = finite_number(active.Deactivate())
    except Exception as exc:
        message = "Deaktivierung fehlgeschlagen: {}".format(exc)
        if log:
            log("GridLens: " + message)
        return False, message
    if code not in (None, 0.0):
        message = "Deactivate() lieferte Fehlercode {:g}.".format(code)
        if log:
            log("GridLens: " + message)
        return False, message
    remaining = _active_scenario(app)
    if remaining is not None and _same_object(remaining, active):
        message = "Operation Scenario blieb nach Deactivate() aktiv."
        if log:
            log("GridLens: " + message)
        return False, message
    return True, ""


def _activate(app, case, log):
    obj = case["object"]
    if obj is None:
        return True, ""
    try:
        code = finite_number(obj.Activate())
    except Exception as exc:
        message = "Aktivierung von {} fehlgeschlagen: {}".format(
            case["name"], exc)
        if log:
            log("GridLens: " + message)
        return False, message
    if code not in (None, 0.0):
        message = "Activate() für {} lieferte Fehlercode {:g}.".format(
            case["name"], code)
        if log:
            log("GridLens: " + message)
        return False, message
    current = _active_scenario(app)
    if not _same_object(current, obj):
        message = "{} ist nach Activate() nicht das aktive Szenario.".format(
            case["name"])
        if log:
            log("GridLens: " + message)
        return False, message
    return True, ""


def _discard(snapshot):
    try:
        snapshot.Delete()
    except Exception:
        pass


def _run_one_case(app, study_case, qds, case, log, result_template=None):
    record = dict(case)
    record.update({"status": "NICHT KONVERGIERT", "error_code": None,
                   "message": "", "snapshot": None, "outages": []})

    state_ok, state_message = _deactivate_active_scenario(app, log)
    if case["id"] != REFERENCE_ID:
        state_ok, state_message = _activate(app, case, log)

    snapshot = _prepare_snapshot(study_case, case["id"], result_template)
    if not state_ok:
        record["error_code"] = -2
        record["message"] = state_message
        write_snapshot_record(snapshot, record)
        return record

    record["outages"] = collect_outages(app)
    bound = _bind_results(qds, snapshot)

    try:
        code = int(qds.Execute())
    except Exception as exc:
        record["error_code"] = -1
        record["message"] = "ComStatsim.Execute() warf {}: {}".format(
            type(exc).__name__, exc)
        write_snapshot_record(snapshot, record)
        return record

    record["error_code"] = code
    if code != 0:
        record["message"] = (
            "ComStatsim.Execute() lieferte Fehlercode {}; Werte werden nicht "
            "ausgewertet.".format(code))
        write_snapshot_record(snapshot, record)
        return record

    if not bound:
        _discard(snapshot)
        replacement = _copy_into_snapshot(
            study_case, safe_attr(qds, "results"), case["id"])
        if replacement is None:
            record["message"] = (
                "Ergebnis konnte weder gebunden noch kopiert werden.")
            return record
        snapshot = replacement

    record["status"] = "konvergiert"
    record["message"] = "{} Freischaltung(en)".format(len(record["outages"]))
    record["snapshot"] = snapshot_name(case["id"])
    write_snapshot_record(snapshot, record)
    return record


def run_cases(app, study_case, log=None, qds=None):
    """Compute every discovered case into its own snapshot ElmRes."""
    cases = discover_cases(app)
    if qds is None:
        try:
            qds = app.GetFromStudyCase("ComStatsim")
        except Exception:
            qds = None
    if qds is None:
        raise RuntimeError("ComStatsim nicht im aktiven Study Case gefunden.")
    _remove_obsolete_snapshots(study_case, [case["id"] for case in cases])

    original_results = safe_attr(qds, "results")
    try:
        original_scenario = app.GetActiveScenario()
    except Exception:
        original_scenario = None

    records = []
    try:
        for case in cases:
            record = _run_one_case(
                app, study_case, qds, case, log, result_template=original_results)
            records.append(record)
            if log:
                log("GridLens: {} {} -> {} ({})".format(
                    record["id"], record["name"], record["status"],
                    record["message"]))
    finally:
        # Leaving the QDS command bound to a GridLens snapshot would make every
        # later manual run write into it unnoticed, and the next report would
        # read a result the runner never produced.
        restore_error = None
        try:
            qds.results = original_results
        except Exception as exc:
            restore_error = exc
            try:
                qds.SetAttribute("results", original_results)
            except Exception as exc:
                restore_error = exc
        if not _same_object(safe_attr(qds, "results"), original_results) and log:
            detail = ": {}".format(restore_error) if restore_error else ""
            log("GridLens WARNUNG: ursprüngliches Ergebnisobjekt konnte nicht "
                "wiederhergestellt werden" + detail)
        _deactivate_active_scenario(app, log)
        if original_scenario is not None:
            try:
                code = finite_number(original_scenario.Activate())
                if code not in (None, 0.0):
                    raise RuntimeError("Activate() lieferte Fehlercode {:g}".format(code))
                if not _same_object(_active_scenario(app), original_scenario):
                    raise RuntimeError("Szenario ist nach Activate() nicht aktiv")
            except Exception as exc:
                if log:
                    log("GridLens WARNUNG: ursprüngliches Szenario konnte nicht "
                        "wiederhergestellt werden: {}".format(exc))
    return records
