"""Processing layer.

PowerFactory-independent. Everything here operates on the canonical model and
produces figures - never verdicts.
"""

from gridlens.processing.pipeline import ProcessingOptions, ProcessingResult, run
from gridlens.processing.plot_selection import (
    PlotSelection,
    PlotSeriesPoint,
    build_plot_series,
    select_plots,
)
from gridlens.processing.rankings import (
    RankingEntry,
    RankingType,
    build_rankings,
    entries_of,
)
from gridlens.processing.reference import (
    ReferenceComparison,
    TimeAlignedDifference,
    compare_to_reference,
    time_aligned_differences,
)
from gridlens.processing.scenario_comparison import (
    MetricDefinition,
    ScenarioMetric,
    compare_scenarios,
    reference_state_summary,
)
from gridlens.processing.statistics import (
    SeriesKey,
    SeriesStatistics,
    compute_statistics,
    percentile,
)
from gridlens.processing.time_points import (
    RelevantTimePoint,
    collect_relevant_time_points,
)
from gridlens.processing.validation import (
    Severity,
    ValidationCode,
    ValidationError,
    ValidationFinding,
    ValidationReport,
    validate,
)

__all__ = [
    "MetricDefinition",
    "PlotSelection",
    "PlotSeriesPoint",
    "ProcessingOptions",
    "ProcessingResult",
    "RankingEntry",
    "RankingType",
    "ReferenceComparison",
    "RelevantTimePoint",
    "ScenarioMetric",
    "SeriesKey",
    "SeriesStatistics",
    "Severity",
    "TimeAlignedDifference",
    "ValidationCode",
    "ValidationError",
    "ValidationFinding",
    "ValidationReport",
    "build_plot_series",
    "build_rankings",
    "collect_relevant_time_points",
    "compare_scenarios",
    "compare_to_reference",
    "compute_statistics",
    "entries_of",
    "percentile",
    "reference_state_summary",
    "run",
    "select_plots",
    "time_aligned_differences",
    "validate",
]
