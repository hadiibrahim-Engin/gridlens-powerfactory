"""Aufbau der 18 Report-Tabellen aus ausgewerteten Ergebnisreihen."""

from datetime import datetime

from .config import (
    CLASS_CATEGORIES, DATA_CONTRACT_VERSION, LOADING_MAX, MAX_BAR_ITEMS,
    MAX_PLOTS, MAX_PLOT_POINTS, TEMPLATE_NAME, TEMPLATE_VERSION, TOP_N,
    VARIABLES, VOLTAGE_MAX, VOLTAGE_MIN,
)
from .pfutil import (
    class_name, finite_number, object_description, object_id, object_key,
    object_name, safe_attr,
)
from .results import statistics
from .tables import TABLES
from .timeaxis import format_time_step


def active_scenario(app, study_case):
    scenario = None
    try:
        scenario = app.GetActiveScenario()
    except Exception:
        pass
    if scenario:
        return "AKTIV", object_name(scenario), object_description(scenario)
    return "AKTIV", "Aktiver Modellzustand", object_description(study_case)


def decimal_comma(value):
    """Format configured engineering limits for the German report text."""
    return "{:g}".format(value).replace(".", ",")


def has_time_variation(item):
    """Return true when a series changes beyond its report precision."""
    values = [value for _, _, value in item["points"]]
    if len(values) < 2:
        return False
    tolerance = {
        "line": 0.1,
        "transformer": 0.1,
        "voltage": 0.001,
        "voltage_angle": 0.01,
    }.get(item["category"], 1e-6)
    return max(values) - min(values) > tolerance


def network_elements(app, series):
    objects = [item["object"] for item in series
               if item["category"] in ("line", "transformer")]
    for pattern in ("*.ElmLne", "*.ElmTr2", "*.ElmTr3"):
        try:
            objects.extend(app.GetCalcRelevantObjects(pattern, 1) or [])
        except TypeError:
            try:
                objects.extend(app.GetCalcRelevantObjects(pattern) or [])
            except Exception:
                pass
        except Exception:
            pass
    unique = {}
    for obj in objects:
        unique[object_key(obj)] = obj
    return [unique[key] for key in sorted(unique)]


def empty_payload():
    return {name: [] for name, _ in TABLES}


def is_critical(item, stats):
    if item["category"] in ("line", "transformer"):
        return stats["max"] > LOADING_MAX
    if item["category"] == "voltage":
        return stats["min"] < VOLTAGE_MIN or stats["max"] > VOLTAGE_MAX
    return False


def maximum_absolute(stats):
    return max(abs(stats["min"]), abs(stats["max"]))


def voltage_deviation(stats):
    return max(abs(stats["min"] - 1.0), abs(stats["max"] - 1.0))


REFERENCE_ID = "REF"
CONVERGED = "konvergiert"

# (reference field, delta field, source statistic)
DELTA_KEYS = (("ref_min", "delta_min", "min"),
              ("ref_max", "delta_max", "max"),
              ("ref_mean", "delta_mean", "mean"))


def scenario_result(case, series, labels, plot_times, time_unit):
    """Build the in-memory result of one case. Knows nothing about tables."""
    by_category = {category: [] for category in VARIABLES}
    stats_by_key = {}
    for item in series:
        stats = statistics(item)
        for reference_key, delta_key, _ in DELTA_KEYS:
            stats[reference_key] = None
            stats[delta_key] = None
        by_category[item["category"]].append((item, stats))
        stats_by_key[(item["category"], item["key"])] = stats
    return {
        "id": case["id"],
        "name": case["name"],
        "kind": case.get("kind", "scenario"),
        "description": case.get("description", ""),
        "status": case.get("status", CONVERGED),
        "error_code": case.get("error_code"),
        "message": case.get("message", ""),
        "outages": list(case.get("outages", ())),
        "is_reference": 1 if case["id"] == REFERENCE_ID else 0,
        "labels": list(labels),
        "plot_times": list(plot_times),
        "time_unit": time_unit,
        "by_category": by_category,
        "stats_by_key": stats_by_key,
    }


def find_reference(results, reference_id=REFERENCE_ID):
    """Return the converged reference case, or None."""
    for result in results:
        if result["id"] == reference_id and result["status"] == CONVERGED:
            return result
    return None


def apply_reference(results, reference_id=REFERENCE_ID):
    """Fill reference values and deltas. Never substitutes 0.0 for missing."""
    for result in results:
        result["is_reference"] = 1 if result["id"] == reference_id else 0
    reference = find_reference(results, reference_id)
    if reference is None:
        return results
    for result in results:
        for key, stats in result["stats_by_key"].items():
            reference_stats = reference["stats_by_key"].get(key)
            if reference_stats is None:
                continue
            for reference_key, delta_key, source in DELTA_KEYS:
                stats[reference_key] = reference_stats[source]
                stats[delta_key] = stats[source] - reference_stats[source]
    return results


def converged(results):
    return [result for result in results if result["status"] == CONVERGED]


def critical_keys(results, category):
    """Keys that violate a limit in at least one converged case."""
    keys = set()
    for result in converged(results):
        for item, stats in result["by_category"][category]:
            if is_critical(item, stats):
                keys.add((category, item["key"]))
    return keys


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


def bar_label(case_id, element_name):
    """Axis label that keeps the same element distinguishable across cases."""
    if case_id == "AKTIV":
        return element_name
    return "{} · {}".format(case_id, element_name)


def _collect(results, category, only_critical=True, predicate=None):
    """Flatten (case_id, item, stats) across every converged case."""
    entries = []
    for result in converged(results):
        for item, stats in result["by_category"][category]:
            if only_critical and not is_critical(item, stats):
                continue
            if predicate is not None and not predicate(stats):
                continue
            entries.append((result["id"], item, stats))
    return entries


LINE_FIELDS = (
    ("min_loading", "min"), ("max_loading", "max"),
    ("mean_loading", "mean"), ("p95_loading", "p95"),
    ("time_of_min_loading", "time_min"), ("time_of_max_loading", "time_max"),
    ("reference_max_loading", "ref_max"), ("delta_max_loading", "delta_max"),
)
TRANSFORMER_FIELDS = tuple(
    entry for entry in LINE_FIELDS if entry[0] != "time_of_min_loading")
VOLTAGE_FIELDS = (
    ("min_voltage", "min"), ("max_voltage", "max"), ("mean_voltage", "mean"),
    ("time_of_min_voltage", "time_min"), ("time_of_max_voltage", "time_max"),
    ("reference_min_voltage", "ref_min"), ("reference_max_voltage", "ref_max"),
    ("delta_min_voltage", "delta_min"), ("delta_max_voltage", "delta_max"),
)


def _statistics_rows(payload, results, category, table, fields):
    """Block comparison: one row per case for every element critical anywhere.

    Showing the same element in the cases where it stays within limits is the
    actual insight -- it says how much headroom the outage consumed.
    """
    for _, key in sorted(critical_keys(results, category)):
        for result in converged(results):
            stats = result["stats_by_key"].get((category, key))
            if stats is None:
                # Switched off in this case: no row at all. A 0.0 row would
                # read as "no load" instead of "not in service".
                continue
            item = next(entry[0] for entry in result["by_category"][category]
                        if entry[0]["key"] == key)
            row = {
                "scenario_id": result["id"],
                "element_id": item["element_id"],
                "element_name": item["element_name"],
                "voltage_level": item["voltage_level"],
            }
            row.update({name: stats[source] for name, source in fields})
            payload[table].append(row)


def _loading_bars(payload, results, category, table):
    entries = sorted(_collect(results, category),
                     key=lambda entry: entry[2]["max"], reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        payload[table].append({
            "rank": rank, "scenario_id": case_id,
            "element_id": item["element_id"],
            "element_name": item["element_name"],
            "bar_label": bar_label(case_id, item["element_name"]),
            "voltage_level": item["voltage_level"],
            "max_loading": stats["max"], "unit": item["unit"],
            "event_time": stats["time_max"],
        })


def _voltage_bars(payload, results):
    entries = sorted(_collect(results, "voltage"),
                     key=lambda entry: voltage_deviation(entry[2]), reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        payload["ScriptedVoltageMagnitudeBars"].append({
            "rank": rank, "scenario_id": case_id,
            "element_id": item["element_id"],
            "element_name": item["element_name"],
            "bar_label": bar_label(case_id, item["element_name"]),
            "voltage_level": item["voltage_level"],
            "min_voltage": stats["min"], "max_voltage": stats["max"],
            "mean_voltage": stats["mean"],
            "deviation": voltage_deviation(stats),
            "status_label": "GRENZWERTVERLETZUNG",
            "unit": item["unit"],
        })


def _angle_bars(payload, results):
    # Angles are informative and carry no blanket limit, so no critical filter.
    entries = sorted(_collect(results, "voltage_angle", only_critical=False),
                     key=lambda entry: maximum_absolute(entry[2]), reverse=True)
    for rank, (case_id, item, stats) in enumerate(entries[:MAX_BAR_ITEMS], 1):
        event_time = (stats["time_min"] if abs(stats["min"]) >= abs(stats["max"])
                      else stats["time_max"])
        payload["ScriptedVoltageAngleBars"].append({
            "rank": rank, "scenario_id": case_id,
            "element_id": item["element_id"],
            "element_name": item["element_name"],
            "bar_label": bar_label(case_id, item["element_name"]),
            "voltage_level": item["voltage_level"],
            "min_angle": stats["min"], "max_angle": stats["max"],
            "mean_angle": stats["mean"],
            "max_abs_angle": maximum_absolute(stats),
            "angle_span": stats["max"] - stats["min"],
            "event_time": event_time, "unit": item["unit"],
        })


def _rankings(payload, results, ranking_type, category, metric_name,
              value_key, time_key, reverse, predicate=None):
    entries = sorted(_collect(results, category, predicate=predicate),
                     key=lambda entry: entry[2][value_key], reverse=reverse)
    reference_key = "ref_min" if value_key == "min" else "ref_max"
    delta_key = "delta_min" if value_key == "min" else "delta_max"
    for rank, (case_id, item, stats) in enumerate(entries[:TOP_N], 1):
        payload["ScriptedRankings"].append({
            "ranking_type": ranking_type, "rank": rank,
            "scenario_id": case_id, "element_id": item["element_id"],
            "element_name": item["element_name"],
            "element_type": item["category"], "metric_name": metric_name,
            "metric_value": stats[value_key], "unit": item["unit"],
            # Real reference values. The previous version wrote metric_value
            # and 0.0 here, claiming a comparison that did not exist.
            "reference_value": stats[reference_key],
            "delta_value": stats[delta_key],
            "event_time": stats[time_key],
        })


COMPARISON_METRICS = (
    ("max_line_loading", "Maximale Leitungsauslastung", "line", "max", True, None),
    ("max_transformer_loading", "Maximale Transformatorauslastung",
     "transformer", "max", True, None),
    ("min_voltage", "Minimale Spannung", "voltage", "min", False,
     lambda stats: stats["min"] < VOLTAGE_MIN),
    ("max_voltage", "Maximale Spannung", "voltage", "max", True,
     lambda stats: stats["max"] > VOLTAGE_MAX),
)


def _scenario_comparison(payload, results):
    for key, name, category, value_key, reverse, predicate in COMPARISON_METRICS:
        for result in converged(results):
            entries = _collect([result], category, predicate=predicate)
            if not entries:
                continue
            _, item, stats = sorted(
                entries, key=lambda entry: entry[2][value_key], reverse=reverse)[0]
            payload["ScriptedScenarioComparison"].append({
                "metric_key": key, "metric_name": name, "unit": item["unit"],
                "scenario_id": result["id"], "metric_value": stats[value_key],
                "element_id": item["element_id"],
                "element_name": item["element_name"],
            })


def _reference_comparison(payload, results):
    reference = find_reference(results)
    if reference is None:
        return
    for result in converged(results):
        if result["id"] == reference["id"]:
            continue
        for category in ("line", "transformer", "voltage"):
            for _, key in sorted(critical_keys(results, category)):
                stats = result["stats_by_key"].get((category, key))
                reference_stats = reference["stats_by_key"].get((category, key))
                if stats is None or reference_stats is None:
                    continue
                item = next(entry[0] for entry in result["by_category"][category]
                            if entry[0]["key"] == key)
                payload["ScriptedReferenceComparison"].append({
                    "scenario_id": result["id"],
                    "element_id": item["element_id"],
                    "element_name": item["element_name"],
                    "element_type": category, "variable": item["variable"],
                    "unit": item["unit"],
                    "reference_min": reference_stats["min"],
                    "scenario_min": stats["min"], "delta_min": stats["delta_min"],
                    "reference_max": reference_stats["max"],
                    "scenario_max": stats["max"], "delta_max": stats["delta_max"],
                    "reference_mean": reference_stats["mean"],
                    "scenario_mean": stats["mean"],
                    "delta_mean": stats["delta_mean"],
                })


def _relevant_time_points(payload, results):
    selected = []
    loading = sorted(_collect(results, "line") + _collect(results, "transformer"),
                     key=lambda entry: entry[2]["max"], reverse=True)[:TOP_N]
    for case_id, item, stats in loading:
        reason = ("Maximale Leitungsauslastung" if item["category"] == "line"
                  else "Maximale Transformatorauslastung")
        selected.append((case_id, item, stats, reason, "max", "time_max"))
    low = sorted(_collect(results, "voltage",
                          predicate=lambda s: s["min"] < VOLTAGE_MIN),
                 key=lambda entry: entry[2]["min"])[:TOP_N]
    for case_id, item, stats in low:
        selected.append((case_id, item, stats, "Minimale Spannung", "min", "time_min"))
    high = sorted(_collect(results, "voltage",
                           predicate=lambda s: s["max"] > VOLTAGE_MAX),
                  key=lambda entry: entry[2]["max"], reverse=True)[:TOP_N]
    for case_id, item, stats in high:
        selected.append((case_id, item, stats, "Maximale Spannung", "max", "time_max"))
    for case_id, item, stats, reason, value_key, time_key in selected:
        payload["ScriptedRelevantTimePoints"].append({
            "timestamp": stats[time_key], "scenario_id": case_id,
            "reason": reason, "element_id": item["element_id"],
            "element_name": item["element_name"],
            "metric_name": item["variable"], "metric_value": stats[value_key],
            "unit": item["unit"],
        })


PLOT_SELECTORS = (
    ("line", False), ("transformer", False), ("voltage", True), ("voltage", False),
)


def _plots(payload, results):
    """Four charts chosen across all cases, one curve per case in each."""
    chosen = []
    for category, use_min in PLOT_SELECTORS:
        if use_min:
            predicate = lambda stats: stats["min"] < VOLTAGE_MIN
        elif category == "voltage":
            predicate = lambda stats: stats["max"] > VOLTAGE_MAX
        else:
            predicate = None
        entries = _collect(results, category, predicate=predicate)
        if not entries:
            continue
        best = (min(entries, key=lambda entry: entry[2]["min"]) if use_min
                else max(entries, key=lambda entry: entry[2]["max"]))[1]
        if any(existing[1] == best["key"] for existing in chosen):
            continue
        chosen.append((category, best["key"], best))

    for index, (category, key, item) in enumerate(chosen[:MAX_PLOTS], 1):
        plot_id = "P{:03d}".format(index)
        payload["ScriptedPlots"].append({
            "plot_id": plot_id,
            "plot_title": "{} - {}".format(item["element_name"], item["variable"]),
            "scenario_id": "", "element_id": item["element_id"],
            "element_name": item["element_name"],
            "variable": item["variable"], "unit": item["unit"],
        })
        for result in converged(results):
            match = next((entry[0] for entry in result["by_category"][category]
                          if entry[0]["key"] == key), None)
            if match is None:
                continue
            for _, timestamp, value in sampled_plot_points(match):
                payload["ScriptedPlotData"].append({
                    "plot_id": plot_id, "scenario_id": result["id"],
                    "series_role": result["id"], "timestamp": timestamp,
                    "value": value,
                })


def _element_type(element_class):
    """Readable category for the report; ElmTr2 means nothing to a reader."""
    categories = CLASS_CATEGORIES.get(element_class, ())
    return categories[0] if categories else element_class


CATEGORY_LABELS = (("line", "Leitungsauslastung"),
                   ("transformer", "Transformatorauslastung"),
                   ("voltage", "Spannungsbetrag"),
                   ("voltage_angle", "Spannungswinkel"))


def _model_quality(payload, results):
    ok = converged(results)
    total_series = sum(len(r["by_category"][c]) for r in ok
                       for c, _ in CATEGORY_LABELS)
    payload["ScriptedModelQuality"].append({
        "check_id": "cases",
        "check_name": "Ausgewertete Faelle",
        "status": "PASS" if ok else "FAIL",
        "message": "{} von {} Faellen konvergiert; {} Ergebnisreihen".format(
            len(ok), len(results), total_series),
        "affected_element": "",
    })
    for result in results:
        if result["status"] == CONVERGED:
            continue
        payload["ScriptedModelQuality"].append({
            "check_id": "case_" + result["id"],
            "check_name": "Rechenlauf " + result["id"],
            "status": "FAIL",
            "message": result["message"] or "Nicht konvergiert.",
            "affected_element": result["name"],
        })
    for category, label in CATEGORY_LABELS:
        total = sum(len(r["by_category"][category]) for r in ok)
        critical = len(critical_keys(results, category))
        if category == "voltage_angle":
            message = (
                "{} ausgewertet; informativ, ohne pauschalen Grenzwert.".format(total)
                if total else
                "Keine Winkelreihe; m:phiu oder m:phiu1 im ElmRes aufzeichnen."
            )
        else:
            message = "{} ausgewertet; {} Betriebsmittel mit Grenzwert" \
                      "verletzung".format(total, critical)
        payload["ScriptedModelQuality"].append({
            "check_id": "series_" + category,
            "check_name": label,
            "status": "PASS" if total else "WARNING",
            "message": message,
            "affected_element": "",
        })
    varying = sum(1 for r in ok for c, _ in CATEGORY_LABELS
                  for item, _ in r["by_category"][c] if has_time_variation(item))
    payload["ScriptedModelQuality"].append({
        "check_id": "time_variation",
        "check_name": "Zeitliche Variation",
        "status": "PASS" if varying else "WARNING",
        "message": (
            "{} von {} Reihen veraendern sich ueber den Simulationszeitraum.".format(
                varying, total_series) if varying else
            "Alle {} Reihen sind zeitlich konstant; QDS-Profile und "
            "Ergebnisaufzeichnung pruefen.".format(total_series)),
        "affected_element": "",
    })
    reference = find_reference(results)
    payload["ScriptedModelQuality"].append({
        "check_id": "reference_comparison",
        "check_name": "Referenzvergleich",
        "status": "PASS" if reference is not None else "WARNING",
        "message": (
            "Referenzfall {} ausgewertet; Deltas gegen den Zustand ohne "
            "Freischaltung.".format(reference["name"]) if reference is not None else
            "Kein konvergierter Referenzfall; Referenzspalten bleiben leer."),
        "affected_element": "",
    })
    payload["ScriptedModelQuality"].extend((
        {
            "check_id": "security_scope",
            "check_name": "Umfang der Freischaltungsbewertung",
            "status": "WARNING",
            "message": "N-1, Versorgungssicherheit und sichere Trennung sind "
                       "nicht bewertet.",
            "affected_element": "",
        },
        {
            "check_id": "limit_loading",
            "check_name": "Auslastungsgrenze",
            "status": "INFO",
            "message": "Grenzwertverletzung bei Auslastung > {} %".format(
                decimal_comma(LOADING_MAX)),
            "affected_element": "",
        },
        {
            "check_id": "limit_voltage",
            "check_name": "Spannungsgrenzen",
            "status": "INFO",
            "message": "Grenzwertverletzung bei Spannung < {} p.u. oder "
                       "> {} p.u.".format(decimal_comma(VOLTAGE_MIN),
                                          decimal_comma(VOLTAGE_MAX)),
            "affected_element": "",
        },
    ))


def build_cases_payload(study_case, results, project_name, result_name):
    """Build all 18 tables from an ordered list of case results."""
    payload = empty_payload()
    ok = converged(results)
    labels = ok[0]["labels"] if ok else (results[0]["labels"] if results else [])
    plot_times = ok[0]["plot_times"] if ok else []
    start = labels[0] if labels else ""
    end = labels[-1] if labels else ""
    time_step = ""
    if len(plot_times) >= 2:
        time_step = format_time_step(plot_times[1] - plot_times[0])
    reference = find_reference(results)

    payload["ScriptedReportMeta"].append({
        "study_id": object_name(study_case),
        "study_name": object_name(study_case),
        "study_description": object_description(study_case),
        "model_name": project_name,
        "model_version": "PowerFactory 2026",
        "simulation_start": start,
        "simulation_end": end,
        "simulation_time_step": time_step or "ElmRes row interval",
        "generation_date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "template_name": TEMPLATE_NAME,
        "template_version": TEMPLATE_VERSION,
        "data_contract_version": DATA_CONTRACT_VERSION,
        "result_name": result_name,
        "assessment_scope": "{} Fall/Faelle; Referenz: {}".format(
            len(results), reference["id"] if reference else "keine"),
        "assessment_status": "VORPRÜFUNG - KEINE ABSCHLIESSENDE FREIGABE",
    })

    for result in results:
        payload["ScriptedScenarios"].append({
            "scenario_id": result["id"],
            "scenario_name": result["name"],
            "is_reference": result["is_reference"],
            "description": result["description"],
            "simulation_status": result["status"],
            "simulation_start": result["labels"][0] if result["labels"] else "",
            "simulation_end": result["labels"][-1] if result["labels"] else "",
        })
        for element_class, name in result["outages"]:
            payload["ScriptedOutages"].append({
                "scenario_id": result["id"], "outage_id": name,
                "element_id": name, "element_name": name,
                "element_type": _element_type(element_class),
                "start_time": result["labels"][0] if result["labels"] else "",
                "end_time": result["labels"][-1] if result["labels"] else "",
                "action": "im Modell ausser Betrieb",
            })
            payload["ScriptedScenarioMatrix"].append({
                "element_id": name, "element_name": name,
                "element_type": _element_type(element_class),
                "scenario_id": result["id"],
                "is_out_of_service": 1, "status_label": "OFF",
            })

    _model_quality(payload, results)
    _statistics_rows(payload, results, "line",
                     "ScriptedLineStatistics", LINE_FIELDS)
    _statistics_rows(payload, results, "transformer",
                     "ScriptedTransformerStatistics", TRANSFORMER_FIELDS)
    _statistics_rows(payload, results, "voltage",
                     "ScriptedVoltageStatistics", VOLTAGE_FIELDS)
    _loading_bars(payload, results, "line", "ScriptedLineLoadingBars")
    _loading_bars(payload, results, "transformer",
                  "ScriptedTransformerLoadingBars")
    _voltage_bars(payload, results)
    _angle_bars(payload, results)
    _rankings(payload, results, "highest_line_loading", "line",
              "Maximale Auslastung", "max", "time_max", True)
    _rankings(payload, results, "highest_transformer_loading", "transformer",
              "Maximale Auslastung", "max", "time_max", True)
    _rankings(payload, results, "lowest_voltage", "voltage",
              "Minimale Spannung", "min", "time_min", False,
              predicate=lambda stats: stats["min"] < VOLTAGE_MIN)
    _rankings(payload, results, "highest_voltage", "voltage",
              "Maximale Spannung", "max", "time_max", True,
              predicate=lambda stats: stats["max"] > VOLTAGE_MAX)
    _scenario_comparison(payload, results)
    _reference_comparison(payload, results)
    _relevant_time_points(payload, results)
    _plots(payload, results)
    return payload


def build_payload(app, study_case, elmres, series, labels, plot_times, time_unit):
    """Single-state fallback: one case with the compact id AKTIV."""
    scenario_id, scenario_name, description = active_scenario(app, study_case)
    outages = []
    for obj in network_elements(app, series):
        if finite_number(safe_attr(obj, "outserv", 0)) == 1.0:
            outages.append((class_name(obj), object_name(obj)))
    case = {
        "id": scenario_id, "name": scenario_name, "kind": "active",
        "description": description, "status": CONVERGED, "error_code": 0,
        "message": "", "snapshot": None, "outages": outages,
    }
    result = scenario_result(case, series, labels, plot_times, time_unit)
    # Deliberately no apply_reference here. A single state is not its own
    # reference: that would report 0.0 deltas and claim a comparison that was
    # never made. Reference columns stay empty in the AKTIV fallback.
    project = None
    try:
        project = app.GetActiveProject()
    except Exception:
        pass
    return build_cases_payload(
        study_case, [result],
        object_name(project) if project else "Aktives PowerFactory-Modell",
        object_name(elmres))
