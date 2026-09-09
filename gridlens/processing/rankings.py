"""Rankings.

Turns statistics and reference comparisons into ordered, report-ready lists.
A ranking states *what is highest or lowest*; it never states what is acceptable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from gridlens.canonical import ElementType, Variable
from gridlens.processing.reference import ReferenceComparison
from gridlens.processing.statistics import SeriesStatistics, filter_statistics

#: Default number of entries per ranking list. Configurable per call.
DEFAULT_TOP_N = 10


class RankingType(str, Enum):
    HIGHEST_LINE_LOADING = "highest_line_loading"
    HIGHEST_TRANSFORMER_LOADING = "highest_transformer_loading"
    LOWEST_VOLTAGE = "lowest_voltage"
    HIGHEST_VOLTAGE = "highest_voltage"
    LARGEST_LINE_LOADING_DELTA = "largest_line_loading_delta"
    LARGEST_TRANSFORMER_LOADING_DELTA = "largest_transformer_loading_delta"
    LARGEST_VOLTAGE_DROP = "largest_voltage_drop"
    LARGEST_VOLTAGE_RISE = "largest_voltage_rise"


@dataclass(frozen=True, slots=True)
class RankingEntry:
    ranking_type: RankingType
    rank: int
    scenario_id: str
    element_id: str
    element_name: str
    element_type: ElementType
    metric_name: str
    metric_value: float
    unit: str
    reference_value: float | None = None
    delta_value: float | None = None
    event_time: str | None = None


def _absolute_ranking(
    statistics: list[SeriesStatistics],
    ranking_type: RankingType,
    element_type: ElementType,
    variable: Variable,
    metric_name: str,
    unit: str,
    *,
    highest: bool,
    top_n: int,
    exclude_scenario_id: str | None = None,
) -> list[RankingEntry]:
    candidates = filter_statistics(
        statistics,
        element_type=element_type,
        variable=variable,
        exclude_scenario_id=exclude_scenario_id,
    )

    def value_of(stat: SeriesStatistics) -> float:
        return stat.maximum if highest else stat.minimum

    def time_of(stat: SeriesStatistics) -> str:
        return stat.time_of_max if highest else stat.time_of_min

    # Ties are broken by scenario then element so the order is reproducible.
    ordered = sorted(
        candidates,
        key=lambda s: (-value_of(s) if highest else value_of(s), s.scenario_id, s.element_id),
    )

    return [
        RankingEntry(
            ranking_type=ranking_type,
            rank=index + 1,
            scenario_id=stat.scenario_id,
            element_id=stat.element_id,
            element_name=stat.element_name,
            element_type=stat.element_type,
            metric_name=metric_name,
            metric_value=value_of(stat),
            unit=unit,
            event_time=time_of(stat),
        )
        for index, stat in enumerate(ordered[:top_n])
    ]


def _delta_ranking(
    comparisons: list[ReferenceComparison],
    ranking_type: RankingType,
    element_type: ElementType,
    variable: Variable,
    metric_name: str,
    unit: str,
    *,
    largest_increase: bool,
    top_n: int,
    use_min: bool = False,
) -> list[RankingEntry]:
    candidates = [
        c for c in comparisons if c.element_type is element_type and c.variable is variable
    ]

    def delta_of(c: ReferenceComparison) -> float:
        return c.delta_min if use_min else c.delta_max

    def scenario_of(c: ReferenceComparison) -> float:
        return c.scenario_min if use_min else c.scenario_max

    def reference_of(c: ReferenceComparison) -> float:
        return c.reference_min if use_min else c.reference_max

    ordered = sorted(
        candidates,
        key=lambda c: (
            -delta_of(c) if largest_increase else delta_of(c),
            c.scenario_id,
            c.element_id,
        ),
    )

    # A "largest rise" list must not be padded with unchanged or opposite
    # entries, so only movements in the requested direction are listed.
    if largest_increase:
        ordered = [c for c in ordered if delta_of(c) > 0.0]
    else:
        ordered = [c for c in ordered if delta_of(c) < 0.0]

    return [
        RankingEntry(
            ranking_type=ranking_type,
            rank=index + 1,
            scenario_id=c.scenario_id,
            element_id=c.element_id,
            element_name=c.element_name,
            element_type=c.element_type,
            metric_name=metric_name,
            metric_value=scenario_of(c),
            unit=unit,
            reference_value=reference_of(c),
            delta_value=delta_of(c),
        )
        for index, c in enumerate(ordered[:top_n])
    ]


def build_rankings(
    statistics: list[SeriesStatistics],
    comparisons: list[ReferenceComparison],
    reference_scenario_id: str,
    top_n: int = DEFAULT_TOP_N,
) -> list[RankingEntry]:
    """Build every standard ranking list.

    Absolute rankings exclude the reference state, which is reported separately
    in the reference-state section; delta rankings exclude it by construction.
    """
    if top_n <= 0:
        raise ValueError("top_n must be positive")

    entries: list[RankingEntry] = []

    entries += _absolute_ranking(
        statistics, RankingType.HIGHEST_LINE_LOADING, ElementType.LINE, Variable.LOADING,
        "Max. Auslastung", "%", highest=True, top_n=top_n,
        exclude_scenario_id=reference_scenario_id,
    )
    entries += _absolute_ranking(
        statistics, RankingType.HIGHEST_TRANSFORMER_LOADING, ElementType.TRANSFORMER,
        Variable.LOADING, "Max. Auslastung", "%", highest=True, top_n=top_n,
        exclude_scenario_id=reference_scenario_id,
    )
    entries += _absolute_ranking(
        statistics, RankingType.LOWEST_VOLTAGE, ElementType.BUSBAR, Variable.VOLTAGE,
        "Min. Spannung", "p.u.", highest=False, top_n=top_n,
        exclude_scenario_id=reference_scenario_id,
    )
    entries += _absolute_ranking(
        statistics, RankingType.HIGHEST_VOLTAGE, ElementType.BUSBAR, Variable.VOLTAGE,
        "Max. Spannung", "p.u.", highest=True, top_n=top_n,
        exclude_scenario_id=reference_scenario_id,
    )

    entries += _delta_ranking(
        comparisons, RankingType.LARGEST_LINE_LOADING_DELTA, ElementType.LINE,
        Variable.LOADING, "Max. Auslastung", "%", largest_increase=True, top_n=top_n,
    )
    entries += _delta_ranking(
        comparisons, RankingType.LARGEST_TRANSFORMER_LOADING_DELTA,
        ElementType.TRANSFORMER, Variable.LOADING, "Max. Auslastung", "%",
        largest_increase=True, top_n=top_n,
    )
    entries += _delta_ranking(
        comparisons, RankingType.LARGEST_VOLTAGE_DROP, ElementType.BUSBAR,
        Variable.VOLTAGE, "Min. Spannung", "p.u.", largest_increase=False,
        top_n=top_n, use_min=True,
    )
    entries += _delta_ranking(
        comparisons, RankingType.LARGEST_VOLTAGE_RISE, ElementType.BUSBAR,
        Variable.VOLTAGE, "Max. Spannung", "p.u.", largest_increase=True,
        top_n=top_n,
    )

    return entries


def entries_of(
    rankings: list[RankingEntry], ranking_type: RankingType
) -> list[RankingEntry]:
    return [e for e in rankings if e.ranking_type is ranking_type]
