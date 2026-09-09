"""Report data model builder.

Turns a :class:`ProcessingResult` into the payload described by
``contracts/report-data-v1.yaml``: a dict of data source name -> list of rows.

This is the last GridLens-internal representation. Everything downstream - the
IntReport bridge and Stimulsoft - only sees these plain rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from gridlens import DATA_CONTRACT_VERSION, TEMPLATE_NAME, TEMPLATE_VERSION
from gridlens.canonical import ElementType, Variable
from gridlens.contracts.loader import DataContract, load_report_contract
from gridlens.processing.pipeline import ProcessingResult
from gridlens.processing.statistics import SeriesStatistics, filter_statistics
from gridlens.report_model.formatting import round_for_unit

Row = dict[str, Any]
Payload = dict[str, list[Row]]

#: Display labels for the service state in the scenario matrix.
IN_SERVICE_LABEL = "ON"
OUT_OF_SERVICE_LABEL = "OFF"
MAX_BAR_ITEMS = 12


def build_report_payload(
    result: ProcessingResult,
    generation_date: str,
    contract: DataContract | None = None,
) -> Payload:
    """Build the full report payload and validate it against the contract.

    ``generation_date`` is passed in rather than read from the clock so a build
    can be made reproducible in tests.
    """
    contract = contract or load_report_contract()
    contract.require_version(DATA_CONTRACT_VERSION)

    payload: Payload = {
        "ScriptedReportMeta": _report_meta(result, generation_date),
        "ScriptedModelQuality": _model_quality(result),
        "ScriptedScenarios": _scenarios(result),
        "ScriptedOutages": _outages(result),
        "ScriptedScenarioMatrix": _scenario_matrix(result),
        "ScriptedLineStatistics": _line_statistics(result),
        "ScriptedTransformerStatistics": _transformer_statistics(result),
        "ScriptedVoltageStatistics": _voltage_statistics(result),
        "ScriptedLineLoadingBars": _loading_bars(result, ElementType.LINE),
        "ScriptedTransformerLoadingBars": _loading_bars(
            result, ElementType.TRANSFORMER
        ),
        "ScriptedVoltageMagnitudeBars": _voltage_magnitude_bars(result),
        "ScriptedVoltageAngleBars": _voltage_angle_bars(result),
        "ScriptedReferenceComparison": _reference_comparison(result),
        "ScriptedScenarioComparison": _scenario_comparison(result),
        "ScriptedRankings": _rankings(result),
        "ScriptedRelevantTimePoints": _relevant_time_points(result),
        "ScriptedPlots": _plots(result),
        "ScriptedPlotData": _plot_data(result),
    }

    contract.validate_payload(payload)
    return payload


# -- individual data sources -------------------------------------------------


def _report_meta(result: ProcessingResult, generation_date: str) -> list[Row]:
    study = result.dataset.study
    scenarios = result.dataset.scenarios

    starts = sorted(s.simulation_start for s in scenarios) or [""]
    ends = sorted(s.simulation_end for s in scenarios) or [""]

    return [
        {
            "study_id": study.study_id,
            "study_name": study.study_name,
            "study_description": study.study_description,
            "model_name": study.model_name,
            "model_version": study.model_version,
            "simulation_start": starts[0],
            "simulation_end": ends[-1],
            "simulation_time_step": study.simulation_time_step,
            "generation_date": generation_date,
            "template_name": TEMPLATE_NAME,
            "template_version": TEMPLATE_VERSION,
            "data_contract_version": DATA_CONTRACT_VERSION,
            "result_name": "Upstream result dataset",
            "assessment_scope": "Multi-scenario result preparation",
            "assessment_status": "ENGINEERING REVIEW REQUIRED",
        }
    ]


def _model_quality(result: ProcessingResult) -> list[Row]:
    return [
        {
            "check_id": check.check_id,
            "check_name": check.check_name,
            "status": check.status,
            "message": check.message,
            "affected_element": check.affected_element,
        }
        for check in result.dataset.qa_checks
    ]


def _scenarios(result: ProcessingResult) -> list[Row]:
    return [
        {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.scenario_name,
            "is_reference": 1 if scenario.is_reference else 0,
            "description": scenario.description,
            "simulation_status": scenario.simulation_status,
            "simulation_start": scenario.simulation_start,
            "simulation_end": scenario.simulation_end,
        }
        for scenario in result.dataset.scenarios
    ]


def _outages(result: ProcessingResult) -> list[Row]:
    return [
        {
            "scenario_id": outage.scenario_id,
            "outage_id": outage.outage_id,
            "element_id": outage.element_id,
            "element_name": outage.element_name,
            "element_type": outage.element_type.value,
            "start_time": outage.start_time,
            "end_time": outage.end_time,
            "action": outage.action,
        }
        for outage in result.dataset.outages
    ]


def _scenario_matrix(result: ProcessingResult) -> list[Row]:
    """Service state per element and scenario, in long format.

    Only elements that are switched in at least one scenario appear, so the
    matrix stays about the outages under investigation.
    """
    dataset = result.dataset

    switched: dict[str, tuple[str, ElementType]] = {
        o.element_id: (o.element_name, o.element_type) for o in dataset.outages
    }
    out_of_service = {(o.scenario_id, o.element_id) for o in dataset.outages}

    rows: list[Row] = []
    for element_id in sorted(switched):
        element_name, element_type = switched[element_id]
        for scenario in dataset.scenarios:
            is_out = (scenario.scenario_id, element_id) in out_of_service
            rows.append(
                {
                    "element_id": element_id,
                    "element_name": element_name,
                    "element_type": element_type.value,
                    "scenario_id": scenario.scenario_id,
                    "is_out_of_service": 1 if is_out else 0,
                    "status_label": OUT_OF_SERVICE_LABEL if is_out else IN_SERVICE_LABEL,
                }
            )

    return rows


def _reference_max(
    result: ProcessingResult, stat: SeriesStatistics
) -> SeriesStatistics | None:
    for candidate in result.statistics:
        if (
            candidate.scenario_id == result.reference_scenario_id
            and candidate.element_id == stat.element_id
            and candidate.variable is stat.variable
        ):
            return candidate
    return None


def _loading_statistics(
    result: ProcessingResult, element_type: ElementType, include_min_time: bool
) -> list[Row]:
    rows: list[Row] = []

    for stat in filter_statistics(
        result.statistics, element_type=element_type, variable=Variable.LOADING
    ):
        reference = _reference_max(result, stat)
        reference_max = reference.maximum if reference else None
        delta_max = None if reference is None else stat.maximum - reference.maximum

        row: Row = {
            "scenario_id": stat.scenario_id,
            "element_id": stat.element_id,
            "element_name": stat.element_name,
            "voltage_level": stat.voltage_level or "",
            "min_loading": round_for_unit(stat.minimum, "%"),
            "max_loading": round_for_unit(stat.maximum, "%"),
            "mean_loading": round_for_unit(stat.mean, "%"),
            "p95_loading": round_for_unit(stat.p95, "%"),
            "time_of_max_loading": stat.time_of_max,
            "reference_max_loading": round_for_unit(reference_max, "%"),
            "delta_max_loading": round_for_unit(delta_max, "%"),
        }
        if include_min_time:
            row["time_of_min_loading"] = stat.time_of_min

        rows.append(row)

    return rows


def _line_statistics(result: ProcessingResult) -> list[Row]:
    return _loading_statistics(result, ElementType.LINE, include_min_time=True)


def _transformer_statistics(result: ProcessingResult) -> list[Row]:
    return _loading_statistics(result, ElementType.TRANSFORMER, include_min_time=False)


def _voltage_statistics(result: ProcessingResult) -> list[Row]:
    rows: list[Row] = []

    for stat in filter_statistics(
        result.statistics, element_type=ElementType.BUSBAR, variable=Variable.VOLTAGE
    ):
        reference = _reference_max(result, stat)

        rows.append(
            {
                "scenario_id": stat.scenario_id,
                "element_id": stat.element_id,
                "element_name": stat.element_name,
                "voltage_level": stat.voltage_level or "",
                "min_voltage": round_for_unit(stat.minimum, "p.u."),
                "max_voltage": round_for_unit(stat.maximum, "p.u."),
                "mean_voltage": round_for_unit(stat.mean, "p.u."),
                "time_of_min_voltage": stat.time_of_min,
                "time_of_max_voltage": stat.time_of_max,
                "reference_min_voltage": round_for_unit(
                    reference.minimum if reference else None, "p.u."
                ),
                "reference_max_voltage": round_for_unit(
                    reference.maximum if reference else None, "p.u."
                ),
                "delta_min_voltage": round_for_unit(
                    None if reference is None else stat.minimum - reference.minimum,
                    "p.u.",
                ),
                "delta_max_voltage": round_for_unit(
                    None if reference is None else stat.maximum - reference.maximum,
                    "p.u.",
                ),
            }
        )

    return rows


def _loading_bars(result: ProcessingResult, element_type: ElementType) -> list[Row]:
    statistics = filter_statistics(
        result.statistics, element_type=element_type, variable=Variable.LOADING
    )
    ordered = sorted(
        statistics,
        key=lambda stat: (-stat.maximum, stat.scenario_id, stat.element_id),
    )[:MAX_BAR_ITEMS]
    return [
        {
            "rank": rank,
            "scenario_id": stat.scenario_id,
            "element_id": stat.element_id,
            "element_name": stat.element_name,
            "voltage_level": stat.voltage_level or "",
            "max_loading": round_for_unit(stat.maximum, "%"),
            "unit": stat.unit,
            "event_time": stat.time_of_max,
        }
        for rank, stat in enumerate(ordered, 1)
    ]


def _voltage_magnitude_bars(result: ProcessingResult) -> list[Row]:
    statistics = filter_statistics(
        result.statistics, element_type=ElementType.BUSBAR, variable=Variable.VOLTAGE
    )
    statistics = [
        stat for stat in statistics
        if stat.minimum < 0.95 or stat.maximum > 1.05
    ]
    ordered = sorted(
        statistics,
        key=lambda stat: (
            -max(abs(stat.minimum - 1.0), abs(stat.maximum - 1.0)),
            stat.scenario_id,
            stat.element_id,
        ),
    )[:MAX_BAR_ITEMS]
    rows = []
    for rank, stat in enumerate(ordered, 1):
        deviation = max(abs(stat.minimum - 1.0), abs(stat.maximum - 1.0))
        rows.append({
            "rank": rank,
            "scenario_id": stat.scenario_id,
            "element_id": stat.element_id,
            "element_name": stat.element_name,
            "voltage_level": stat.voltage_level or "",
            "min_voltage": round_for_unit(stat.minimum, "p.u."),
            "max_voltage": round_for_unit(stat.maximum, "p.u."),
            "mean_voltage": round_for_unit(stat.mean, "p.u."),
            "deviation": round_for_unit(deviation, "p.u."),
            "status_label": "GRENZWERTVERLETZUNG" if (
                stat.minimum < 0.95 or stat.maximum > 1.05
            ) else "INNERHALB GRENZEN",
            "unit": stat.unit,
        })
    return rows


def _voltage_angle_bars(result: ProcessingResult) -> list[Row]:
    statistics = filter_statistics(
        result.statistics,
        element_type=ElementType.BUSBAR,
        variable=Variable.VOLTAGE_ANGLE,
    )
    ordered = sorted(
        statistics,
        key=lambda stat: (
            -max(abs(stat.minimum), abs(stat.maximum)),
            stat.scenario_id,
            stat.element_id,
        ),
    )[:MAX_BAR_ITEMS]
    rows = []
    for rank, stat in enumerate(ordered, 1):
        maximum_is_larger = abs(stat.maximum) > abs(stat.minimum)
        rows.append({
            "rank": rank,
            "scenario_id": stat.scenario_id,
            "element_id": stat.element_id,
            "element_name": stat.element_name,
            "voltage_level": stat.voltage_level or "",
            "min_angle": round_for_unit(stat.minimum, "deg"),
            "max_angle": round_for_unit(stat.maximum, "deg"),
            "mean_angle": round_for_unit(stat.mean, "deg"),
            "max_abs_angle": round_for_unit(
                max(abs(stat.minimum), abs(stat.maximum)), "deg"
            ),
            "angle_span": round_for_unit(stat.maximum - stat.minimum, "deg"),
            "event_time": stat.time_of_max if maximum_is_larger else stat.time_of_min,
            "unit": stat.unit,
        })
    return rows


def _reference_comparison(result: ProcessingResult) -> list[Row]:
    return [
        {
            "scenario_id": c.scenario_id,
            "element_id": c.element_id,
            "element_name": c.element_name,
            "element_type": c.element_type.value,
            "variable": c.variable.value,
            "unit": c.unit,
            "reference_min": round_for_unit(c.reference_min, c.unit),
            "scenario_min": round_for_unit(c.scenario_min, c.unit),
            "delta_min": round_for_unit(c.delta_min, c.unit),
            "reference_max": round_for_unit(c.reference_max, c.unit),
            "scenario_max": round_for_unit(c.scenario_max, c.unit),
            "delta_max": round_for_unit(c.delta_max, c.unit),
            "reference_mean": round_for_unit(c.reference_mean, c.unit),
            "scenario_mean": round_for_unit(c.scenario_mean, c.unit),
            "delta_mean": round_for_unit(c.delta_mean, c.unit),
        }
        for c in result.reference_comparisons
    ]


def _scenario_comparison(result: ProcessingResult) -> list[Row]:
    return [
        {
            "metric_key": m.metric_key,
            "metric_name": m.metric_name,
            "unit": m.unit,
            "scenario_id": m.scenario_id,
            "metric_value": round_for_unit(m.metric_value, m.unit),
            "element_id": m.element_id,
            "element_name": m.element_name,
        }
        for m in result.scenario_metrics
    ]


def _rankings(result: ProcessingResult) -> list[Row]:
    return [
        {
            "ranking_type": e.ranking_type.value,
            "rank": e.rank,
            "scenario_id": e.scenario_id,
            "element_id": e.element_id,
            "element_name": e.element_name,
            "element_type": e.element_type.value,
            "metric_name": e.metric_name,
            "metric_value": round_for_unit(e.metric_value, e.unit),
            "unit": e.unit,
            "reference_value": round_for_unit(e.reference_value, e.unit),
            "delta_value": round_for_unit(e.delta_value, e.unit),
            "event_time": e.event_time or "",
        }
        for e in result.rankings
    ]


def _relevant_time_points(result: ProcessingResult) -> list[Row]:
    # Coincidence markers carry no element or engineering value. Keep those in
    # the processing result, but omit them from the production report table.
    return [
        {
            "timestamp": p.timestamp,
            "scenario_id": p.scenario_id,
            "reason": p.reason,
            "element_id": p.element_id or "",
            "element_name": p.element_name or "",
            "metric_name": p.metric_name or "",
            "metric_value": round_for_unit(p.metric_value, p.unit or ""),
            "unit": p.unit or "",
        }
        for p in result.relevant_time_points
        if p.element_id and p.metric_value is not None
    ]


def _plots(result: ProcessingResult) -> list[Row]:
    """The master list: one row per chart to draw."""
    return [
        {
            "plot_id": plot.plot_id,
            "plot_title": plot.plot_title,
            "scenario_id": plot.scenario_id,
            "element_id": plot.element_id,
            "element_name": plot.element_name,
            "variable": plot.variable.value,
            "unit": plot.unit,
        }
        for plot in result.plots
    ]


def _plot_data(result: ProcessingResult) -> list[Row]:
    """The detail rows, joined to ScriptedPlots on plot_id."""
    timestamps = sorted({point.timestamp for point in result.dataset.results})
    index_by_timestamp = {value: float(index) for index, value in enumerate(timestamps)}
    parsed = {}
    for value in timestamps:
        try:
            parsed[value] = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            parsed = {}
            break
    start = min(parsed.values()) if parsed else None

    def numeric_timestamp(value: str) -> float:
        if start is not None:
            return (parsed[value] - start).total_seconds() / 3600.0
        return index_by_timestamp[value]

    return [
        {
            "plot_id": s.plot_id,
            "scenario_id": s.scenario_id,
            "series_role": s.series_role,
            "timestamp": numeric_timestamp(s.timestamp),
            "value": round_for_unit(s.value, s.unit),
        }
        for s in result.plot_series
    ]
