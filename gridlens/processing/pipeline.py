"""Processing pipeline.

Runs the processing stages in order and returns everything the report model needs:

    validate -> statistics -> reference comparison -> scenario comparison
             -> rankings -> relevant time points -> plot selection
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gridlens.canonical import CanonicalDataset
from gridlens.processing.plot_selection import (
    DEFAULT_PLOTS_PER_RANKING,
    PlotSelection,
    PlotSeriesPoint,
    build_plot_series,
    select_plots,
)
from gridlens.processing.rankings import DEFAULT_TOP_N, RankingEntry, build_rankings
from gridlens.processing.reference import (
    ReferenceComparison,
    TimeAlignedDifference,
    compare_to_reference,
    time_aligned_differences,
)
from gridlens.processing.scenario_comparison import (
    ScenarioMetric,
    compare_scenarios,
    reference_state_summary,
)
from gridlens.processing.statistics import SeriesStatistics, compute_statistics
from gridlens.processing.validation import ValidationReport, validate


@dataclass(slots=True)
class ProcessingOptions:
    """Knobs the engineer may turn without touching the template."""

    top_n: int = DEFAULT_TOP_N
    plots_per_ranking: int = DEFAULT_PLOTS_PER_RANKING
    include_time_aligned_differences: bool = True


@dataclass(slots=True)
class ProcessingResult:
    """Everything the report model is built from."""

    dataset: CanonicalDataset
    validation: ValidationReport
    reference_scenario_id: str

    statistics: list[SeriesStatistics] = field(default_factory=list)
    reference_comparisons: list[ReferenceComparison] = field(default_factory=list)
    time_differences: list[TimeAlignedDifference] = field(default_factory=list)
    scenario_metrics: list[ScenarioMetric] = field(default_factory=list)
    reference_summary: list[ScenarioMetric] = field(default_factory=list)
    rankings: list[RankingEntry] = field(default_factory=list)
    relevant_time_points: list = field(default_factory=list)
    plots: list[PlotSelection] = field(default_factory=list)
    plot_series: list[PlotSeriesPoint] = field(default_factory=list)


def run(
    dataset: CanonicalDataset,
    options: ProcessingOptions | None = None,
) -> ProcessingResult:
    """Execute the full processing chain.

    Validation runs first and raises on ERROR level findings, so no statistic is
    ever computed on data that is known to be inconsistent.
    """
    # Imported here to keep the module import graph free of a cycle between
    # rankings and time_points at load time.
    from gridlens.processing.time_points import collect_relevant_time_points

    options = options or ProcessingOptions()

    report = validate(dataset)
    report.raise_for_errors()

    reference = dataset.reference_scenario
    if reference is None:
        # validate() already guarantees this cannot happen; kept as a guard so a
        # future caller that skips validation still fails loudly.
        raise ValueError("Dataset has no unique reference scenario.")

    statistics = compute_statistics(dataset)
    comparisons = compare_to_reference(statistics, reference.scenario_id)
    rankings = build_rankings(
        statistics, comparisons, reference.scenario_id, top_n=options.top_n
    )
    plots = select_plots(rankings, per_ranking=options.plots_per_ranking)

    return ProcessingResult(
        dataset=dataset,
        validation=report,
        reference_scenario_id=reference.scenario_id,
        statistics=statistics,
        reference_comparisons=comparisons,
        time_differences=(
            time_aligned_differences(dataset, reference.scenario_id)
            if options.include_time_aligned_differences
            else []
        ),
        scenario_metrics=compare_scenarios(statistics, dataset.scenario_ids),
        reference_summary=reference_state_summary(statistics, reference.scenario_id),
        rankings=rankings,
        relevant_time_points=collect_relevant_time_points(rankings),
        plots=plots,
        plot_series=build_plot_series(dataset, plots, reference.scenario_id),
    )
