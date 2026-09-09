"""Reference comparison.

Every scenario is compared against the single reference state. The comparison is
purely arithmetic: GridLens reports the difference and never labels it.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridlens.canonical import CanonicalDataset, ElementType, Variable
from gridlens.processing.statistics import SeriesKey, SeriesStatistics, index_statistics


@dataclass(frozen=True, slots=True)
class ReferenceComparison:
    """Scenario versus reference for one element and variable."""

    scenario_id: str
    element_id: str
    element_name: str
    element_type: ElementType
    variable: Variable
    unit: str

    reference_min: float
    scenario_min: float
    delta_min: float

    reference_max: float
    scenario_max: float
    delta_max: float

    reference_mean: float
    scenario_mean: float
    delta_mean: float


@dataclass(frozen=True, slots=True)
class TimeAlignedDifference:
    """scenario(t) - reference(t) for one element, variable and timestamp."""

    scenario_id: str
    element_id: str
    element_name: str
    variable: Variable
    unit: str
    timestamp: str
    reference_value: float
    scenario_value: float
    delta: float


def compare_to_reference(
    statistics: list[SeriesStatistics],
    reference_scenario_id: str,
) -> list[ReferenceComparison]:
    """Compare every non-reference series against its reference counterpart.

    Series that have no reference counterpart are skipped rather than compared
    against a substituted value: an invented baseline would be worse than a gap.
    """
    indexed = index_statistics(statistics)
    comparisons: list[ReferenceComparison] = []

    for stat in statistics:
        if stat.scenario_id == reference_scenario_id:
            continue

        reference_key = SeriesKey(reference_scenario_id, stat.element_id, stat.variable)
        reference = indexed.get(reference_key)
        if reference is None:
            continue

        comparisons.append(
            ReferenceComparison(
                scenario_id=stat.scenario_id,
                element_id=stat.element_id,
                element_name=stat.element_name,
                element_type=stat.element_type,
                variable=stat.variable,
                unit=stat.unit,
                reference_min=reference.minimum,
                scenario_min=stat.minimum,
                delta_min=stat.minimum - reference.minimum,
                reference_max=reference.maximum,
                scenario_max=stat.maximum,
                delta_max=stat.maximum - reference.maximum,
                reference_mean=reference.mean,
                scenario_mean=stat.mean,
                delta_mean=stat.mean - reference.mean,
            )
        )

    comparisons.sort(key=lambda c: (c.scenario_id, c.element_id, c.variable.value))
    return comparisons


def time_aligned_differences(
    dataset: CanonicalDataset,
    reference_scenario_id: str,
) -> list[TimeAlignedDifference]:
    """Compute scenario(t) - reference(t) where the time axes line up.

    Only timestamps present in both series are used. Nothing is interpolated:
    a differing time axis yields fewer rows, not invented ones.
    """
    reference_values: dict[tuple[str, str, str], tuple[float, str]] = {}
    for point in dataset.results:
        if point.scenario_id != reference_scenario_id:
            continue
        key = (point.element_id, point.variable.value, point.timestamp)
        reference_values[key] = (point.value, point.unit)

    differences: list[TimeAlignedDifference] = []
    for point in dataset.results:
        if point.scenario_id == reference_scenario_id:
            continue

        key = (point.element_id, point.variable.value, point.timestamp)
        match = reference_values.get(key)
        if match is None:
            continue

        reference_value, unit = match
        differences.append(
            TimeAlignedDifference(
                scenario_id=point.scenario_id,
                element_id=point.element_id,
                element_name=point.element_name,
                variable=point.variable,
                unit=unit,
                timestamp=point.timestamp,
                reference_value=reference_value,
                scenario_value=point.value,
                delta=point.value - reference_value,
            )
        )

    differences.sort(
        key=lambda d: (d.scenario_id, d.element_id, d.variable.value, d.timestamp)
    )
    return differences
