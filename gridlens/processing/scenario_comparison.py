"""Scenario comparison.

Condenses each scenario - including the reference - into a handful of headline
metrics so they can be put side by side. The number of scenarios is never fixed:
the result is long format (one row per metric and scenario) and the template
spreads it dynamically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gridlens.canonical import ElementType, Variable
from gridlens.processing.statistics import SeriesStatistics, filter_statistics


@dataclass(frozen=True, slots=True)
class ScenarioMetric:
    """One headline metric of one scenario."""

    metric_key: str
    metric_name: str
    unit: str
    scenario_id: str
    metric_value: float
    element_id: str
    element_name: str


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """How one headline metric is extracted from a scenario's statistics."""

    key: str
    name: str
    unit: str
    element_type: ElementType
    variable: Variable
    #: Picks the driving series out of the scenario's candidates.
    select: Callable[[list[SeriesStatistics]], SeriesStatistics | None]
    #: Reads the reported number off that series.
    read: Callable[[SeriesStatistics], float]


def _highest_max(series: list[SeriesStatistics]) -> SeriesStatistics | None:
    return max(series, key=lambda s: s.maximum) if series else None


def _lowest_min(series: list[SeriesStatistics]) -> SeriesStatistics | None:
    return min(series, key=lambda s: s.minimum) if series else None


#: The standard comparison metrics. Extend this list to add a row to the
#: comparison table - no template change required.
DEFAULT_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        key="max_line_loading",
        name="Max. Leitungsauslastung",
        unit="%",
        element_type=ElementType.LINE,
        variable=Variable.LOADING,
        select=_highest_max,
        read=lambda s: s.maximum,
    ),
    MetricDefinition(
        key="max_transformer_loading",
        name="Max. Trafoauslastung",
        unit="%",
        element_type=ElementType.TRANSFORMER,
        variable=Variable.LOADING,
        select=_highest_max,
        read=lambda s: s.maximum,
    ),
    MetricDefinition(
        key="min_voltage",
        name="Min. Spannung",
        unit="p.u.",
        element_type=ElementType.BUSBAR,
        variable=Variable.VOLTAGE,
        select=_lowest_min,
        read=lambda s: s.minimum,
    ),
    MetricDefinition(
        key="max_voltage",
        name="Max. Spannung",
        unit="p.u.",
        element_type=ElementType.BUSBAR,
        variable=Variable.VOLTAGE,
        select=_highest_max,
        read=lambda s: s.maximum,
    ),
)


def compare_scenarios(
    statistics: list[SeriesStatistics],
    scenario_ids: list[str],
    metrics: tuple[MetricDefinition, ...] = DEFAULT_METRICS,
) -> list[ScenarioMetric]:
    """Headline metrics for every scenario, in long format.

    A scenario that has no series for a metric simply produces no row for it.
    """
    rows: list[ScenarioMetric] = []

    for metric in metrics:
        for scenario_id in scenario_ids:
            candidates = filter_statistics(
                statistics,
                element_type=metric.element_type,
                variable=metric.variable,
                scenario_id=scenario_id,
            )
            chosen = metric.select(candidates)
            if chosen is None:
                continue

            rows.append(
                ScenarioMetric(
                    metric_key=metric.key,
                    metric_name=metric.name,
                    unit=metric.unit,
                    scenario_id=scenario_id,
                    metric_value=metric.read(chosen),
                    element_id=chosen.element_id,
                    element_name=chosen.element_name,
                )
            )

    return rows


def reference_state_summary(
    statistics: list[SeriesStatistics],
    reference_scenario_id: str,
    metrics: tuple[MetricDefinition, ...] = DEFAULT_METRICS,
) -> list[ScenarioMetric]:
    """The same headline metrics, restricted to the reference state."""
    return compare_scenarios(statistics, [reference_scenario_id], metrics)
