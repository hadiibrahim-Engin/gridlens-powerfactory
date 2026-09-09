"""Plot selection.

Not every piece of equipment deserves a chart. The selection is driven by the
rankings that were already computed, so the choice is traceable back to a number
rather than to a heuristic hidden in the template.

The result only says *what* to plot. Stimulsoft does the drawing.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridlens.canonical import CanonicalDataset, Variable
from gridlens.processing.rankings import RankingEntry, RankingType, entries_of

#: How many entries of each source ranking become a plot.
DEFAULT_PLOTS_PER_RANKING = 3


@dataclass(frozen=True, slots=True)
class PlotSelection:
    """One selected chart: a scenario curve against its reference curve."""

    plot_id: str
    plot_title: str
    scenario_id: str
    element_id: str
    element_name: str
    variable: Variable
    unit: str


@dataclass(frozen=True, slots=True)
class PlotSeriesPoint:
    """One sample of a selected plot, tagged with the curve it belongs to."""

    plot_id: str
    plot_title: str
    scenario_id: str
    element_id: str
    element_name: str
    variable: Variable
    unit: str
    series_role: str  # "reference" or "scenario"
    timestamp: str
    value: float


#: Rankings that feed plot selection: top absolute values plus top deltas.
_SOURCE_RANKINGS: tuple[RankingType, ...] = (
    RankingType.HIGHEST_LINE_LOADING,
    RankingType.HIGHEST_TRANSFORMER_LOADING,
    RankingType.LOWEST_VOLTAGE,
    RankingType.LARGEST_LINE_LOADING_DELTA,
    RankingType.LARGEST_TRANSFORMER_LOADING_DELTA,
    RankingType.LARGEST_VOLTAGE_DROP,
)

_VARIABLE_BY_RANKING: dict[RankingType, Variable] = {
    RankingType.HIGHEST_LINE_LOADING: Variable.LOADING,
    RankingType.HIGHEST_TRANSFORMER_LOADING: Variable.LOADING,
    RankingType.LOWEST_VOLTAGE: Variable.VOLTAGE,
    RankingType.LARGEST_LINE_LOADING_DELTA: Variable.LOADING,
    RankingType.LARGEST_TRANSFORMER_LOADING_DELTA: Variable.LOADING,
    RankingType.LARGEST_VOLTAGE_DROP: Variable.VOLTAGE,
}


def select_plots(
    rankings: list[RankingEntry],
    per_ranking: int = DEFAULT_PLOTS_PER_RANKING,
) -> list[PlotSelection]:
    """Choose the time series worth plotting, without duplicates.

    An element can top several rankings at once; it is plotted only once per
    scenario and variable.
    """
    if per_ranking <= 0:
        raise ValueError("per_ranking must be positive")

    selections: list[PlotSelection] = []
    seen: set[tuple[str, str, str]] = set()

    for ranking_type in _SOURCE_RANKINGS:
        variable = _VARIABLE_BY_RANKING[ranking_type]

        for entry in entries_of(rankings, ranking_type)[:per_ranking]:
            key = (entry.scenario_id, entry.element_id, variable.value)
            if key in seen:
                continue
            seen.add(key)

            selections.append(
                PlotSelection(
                    plot_id=f"{entry.scenario_id}_{entry.element_id}_{variable.value}",
                    plot_title=(
                        f"{entry.element_name} - {_variable_label(variable)} "
                        f"({entry.scenario_id} vs. Referenz)"
                    ),
                    scenario_id=entry.scenario_id,
                    element_id=entry.element_id,
                    element_name=entry.element_name,
                    variable=variable,
                    unit=entry.unit,
                )
            )

    return selections


def build_plot_series(
    dataset: CanonicalDataset,
    selections: list[PlotSelection],
    reference_scenario_id: str,
) -> list[PlotSeriesPoint]:
    """Expand each selection into its reference and scenario sample points."""
    by_series: dict[tuple[str, str, str], list] = {}
    for point in dataset.results:
        by_series.setdefault(
            (point.scenario_id, point.element_id, point.variable.value), []
        ).append(point)

    samples: list[PlotSeriesPoint] = []

    for selection in selections:
        for role, scenario_id in (
            ("reference", reference_scenario_id),
            ("scenario", selection.scenario_id),
        ):
            key = (scenario_id, selection.element_id, selection.variable.value)
            for point in sorted(by_series.get(key, []), key=lambda p: p.timestamp):
                samples.append(
                    PlotSeriesPoint(
                        plot_id=selection.plot_id,
                        plot_title=selection.plot_title,
                        scenario_id=scenario_id,
                        element_id=selection.element_id,
                        element_name=selection.element_name,
                        variable=selection.variable,
                        unit=selection.unit,
                        series_role=role,
                        timestamp=point.timestamp,
                        value=point.value,
                    )
                )

    return samples


def _variable_label(variable: Variable) -> str:
    return {"loading": "Auslastung", "voltage": "Spannung"}[variable.value]
