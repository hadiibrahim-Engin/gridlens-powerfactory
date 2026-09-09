"""Moduswahl und Programmeinstieg für Runner und IntReport-Publisher."""

import os

from .config import PUBLISHER_VERSION, SNAPSHOT_PREFIX, TIME_UNIT_FALLBACK
from .discovery import discover_cases
from .manifest import RELEASE_VERSION, verify_runtime_package
from .payload import (
    CONVERGED, apply_reference, build_cases_payload, build_payload,
    scenario_result,
)
from .pfutil import class_name, object_name
from .publish import publish_report
from .results import check_run_budget, collect_series, select_result
from .runner import read_outages, read_snapshot_record, run_cases


def select_mode(parent):
    """Choose mode from the ComPython parent, without a runtime parameter."""
    return "report" if class_name(parent) == "IntReport" else "runner"


def load_snapshots(study_case):
    """Return ``(case_id, ElmRes)`` snapshots with the reference first."""
    try:
        found = study_case.GetContents("*.ElmRes") or []
    except Exception:
        return []
    snapshots = []
    for item in found:
        name = object_name(item)
        if not name.startswith(SNAPSHOT_PREFIX):
            continue
        case_id = name[len(SNAPSHOT_PREFIX):]
        if case_id:
            snapshots.append((case_id, item))
    return sorted(snapshots, key=lambda entry: (entry[0] != "REF", entry[0]))


def validate_snapshot_set(snapshots):
    """Reject legacy, partial or mixed runner generations fail-closed."""
    if not snapshots:
        return
    records = [(case_id, read_snapshot_record(elmres))
               for case_id, elmres in snapshots]
    required = ("id", "run_id", "run_state", "expected_cases", "status")
    for case_id, metadata in records:
        missing = [field for field in required if not metadata.get(field)]
        if missing:
            raise RuntimeError(
                "GridLens-Snapshot {} hat keine vollständigen Runner-Metadaten "
                "({}). Runner erneut ausführen.".format(
                    case_id, ", ".join(missing)))
        if metadata["id"] != case_id:
            raise RuntimeError(
                "GridLens-Snapshot {} enthält eine abweichende Fall-ID {}. "
                "Runner erneut ausführen.".format(case_id, metadata["id"]))

    run_ids = {metadata["run_id"] for _, metadata in records}
    expected_values = {metadata["expected_cases"] for _, metadata in records}
    states = {metadata["run_state"] for _, metadata in records}
    if len(run_ids) != 1 or len(expected_values) != 1:
        raise RuntimeError(
            "GridLens-Snapshots stammen aus gemischten Runner-Läufen. "
            "Runner erneut ausführen.")
    if states != {"complete"}:
        raise RuntimeError(
            "GridLens-Runner-Lauf ist unvollständig. Runner erneut ausführen.")

    expected = [value for value in next(iter(expected_values)).split(",") if value]
    actual = [case_id for case_id, _ in snapshots]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise RuntimeError(
            "GridLens-Snapshot-Satz ist unvollständig; erwartet {}, gefunden {}. "
            "Runner erneut ausführen.".format(
                ", ".join(expected), ", ".join(actual)))


def verify_runtime(root, log=None):
    """Refuse to run a runtime package that was not delivered as one release.

    Runner, report extension and template are copied by hand. A mixed set can
    still import cleanly and would then fill the tables of another data
    contract, so the mismatch has to stop the run rather than the report.
    """
    errors, warnings = verify_runtime_package(root)
    for message in warnings:
        if log:
            log("GridLens WARNUNG: " + message)
    if errors:
        raise RuntimeError(
            "GridLens-Laufzeitpaket {} ist nicht konsistent: {}".format(
                RELEASE_VERSION, " ".join(errors)))


def _case_catalog(app):
    """Best-effort names for snapshots produced before metadata was added."""
    try:
        return {case["id"]: case for case in discover_cases(app)}
    except Exception:
        return {}


def _snapshot_case(case_id, elmres, catalog):
    metadata = read_snapshot_record(elmres)
    fallback = catalog.get(case_id, {})
    return {
        # The object name is authoritative. A hand-edited desc must never move
        # a result into another case or create duplicate scenario ids.
        "id": case_id,
        "name": metadata.get("name") or fallback.get("name") or object_name(elmres),
        "kind": metadata.get("kind") or fallback.get("kind") or (
            "reference" if case_id == "REF" else "scenario"),
        "description": metadata.get("description") or fallback.get(
            "description", "GridLens-Ergebnissnapshot"),
        "status": metadata.get("status") or "NICHT KONVERGIERT",
        "error_code": metadata.get("error_code", 0),
        "message": metadata.get("message", ""),
        "outages": read_outages(elmres),
    }


def _read_snapshot(case_id, elmres, catalog, log):
    case = _snapshot_case(case_id, elmres, catalog)
    if case["status"] != CONVERGED:
        return scenario_result(case, [], [], [], TIME_UNIT_FALLBACK)
    try:
        elmres.Load()
        series, labels, plot_times, time_unit = collect_series(elmres)
        return scenario_result(case, series, labels, plot_times, time_unit)
    except Exception as exc:
        case["status"] = "NICHT KONVERGIERT"
        case["error_code"] = -3
        case["message"] = "Snapshot {} ist nicht auswertbar: {}".format(
            object_name(elmres), exc)
        if log:
            log("GridLens: " + case["message"])
        return scenario_result(case, [], [], [], TIME_UNIT_FALLBACK)
    finally:
        try:
            elmres.Release()
        except Exception:
            pass


def run_report_mode(app, study_case, report, log=None):
    """Publish stored case snapshots, or one active result as fallback."""
    snapshots = load_snapshots(study_case)
    if not snapshots:
        elmres = select_result(study_case)
        if log:
            log("GridLens result: " + object_name(elmres))
        try:
            elmres.Load()
            series, labels, plot_times, time_unit = collect_series(elmres)
            data = build_payload(
                app, study_case, elmres, series, labels, plot_times, time_unit)
        finally:
            try:
                elmres.Release()
            except Exception:
                pass
        return publish_report(report, data, log=log)

    validate_snapshot_set(snapshots)
    catalog = _case_catalog(app)
    results = [
        _read_snapshot(case_id, elmres, catalog, log)
        for case_id, elmres in snapshots
    ]
    check_run_budget(results)
    apply_reference(results)
    try:
        project = app.GetActiveProject()
    except Exception:
        project = None
    data = build_cases_payload(
        study_case,
        results,
        object_name(project) if project else "Aktives PowerFactory-Modell",
        ", ".join(object_name(item) for _, item in snapshots),
    )
    return publish_report(report, data, log=log)


def main():
    import powerfactory

    app = powerfactory.GetApplication()
    if app is None:
        raise RuntimeError("PowerFactory application is unavailable.")
    script = app.GetCurrentScript()
    study_case = app.GetActiveStudyCase()
    if script is None:
        raise RuntimeError("No active ComPython script.")
    if study_case is None:
        raise RuntimeError("No active study case.")

    verify_runtime(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        log=app.PrintPlain)
    app.PrintPlain("GridLens publisher: " + PUBLISHER_VERSION)
    app.PrintPlain("GridLens study case: " + object_name(study_case))

    parent = script.GetParent()
    if select_mode(parent) == "runner":
        app.PrintPlain("GridLens mode: runner")
        records = run_cases(app, study_case, log=app.PrintPlain)
        calculated = sum(1 for record in records if record["status"] == CONVERGED)
        app.PrintPlain(
            "GridLens: {} von {} Fällen erfolgreich berechnet; Bericht jetzt "
            "über den IntReport erzeugen.".format(calculated, len(records)))
        return

    app.PrintPlain("GridLens mode: report")
    counts = run_report_mode(app, study_case, parent, log=app.PrintPlain)
    app.PrintPlain("GridLens: {} Tabellen publiziert.".format(len(counts)))
