"""Statistics engine.

Computes per scenario x element x variable aggregates. All statistical work
happens here - never in the report template.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from gridlens.canonical import CanonicalDataset, ElementType, ResultPoint, Variable


@dataclass(frozen=True, slots=True)
class SeriesKey:
    scenario_id: str
    element_id: str
    variable: Variable


@dataclass(frozen=True, slots=True)
class SeriesStatistics:
    """Aggregates of one time series."""

    key: SeriesKey
    element_name: str
    element_type: ElementType
    unit: str
    voltage_level: str | None

    minimum: float
    maximum: float
    mean: float
    p95: float

    time_of_min: str
    time_of_max: str

    count: int

    @property
    def scenario_id(self) -> str:
        return self.key.scenario_id

    @property
    def element_id(self) -> str:
        return self.key.element_id

    @property
    def variable(self) -> Variable:
        return self.key.variable


def percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolation percentile, matching numpy's default method.

    Implemented directly so the processing layer stays dependency free.
    """
    if not values:
        raise ValueError("percentile of an empty series is undefined")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be within [0, 1]")

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    position = fraction * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - lower_index

    return ordered[lower_index] * (1.0 - weight) + ordered[upper_index] * weight


def _series_statistics(points: list[ResultPoint]) -> SeriesStatistics:
    # Sorting by timestamp keeps time_of_min/max deterministic when a value
    # occurs more than once: the earliest occurrence wins.
    ordered = sorted(points, key=lambda p: p.timestamp)
    values = [p.value for p in ordered]

    # min()/max() over the time-ordered list return the first extreme they meet,
    # so a value occurring repeatedly reports its earliest timestamp.
    min_point = min(ordered, key=lambda p: p.value)
    max_point = max(ordered, key=lambda p: p.value)

    first = ordered[0]
    return SeriesStatistics(
        key=SeriesKey(first.scenario_id, first.element_id, first.variable),
        element_name=first.element_name,
        element_type=first.element_type,
        unit=first.unit,
        voltage_level=first.voltage_level,
        minimum=min(values),
        maximum=max_point.value,
        mean=sum(values) / len(values),
        p95=percentile(values, 0.95),
        time_of_min=min_point.timestamp,
        time_of_max=max_point.timestamp,
        count=len(values),
    )


def compute_statistics(dataset: CanonicalDataset) -> list[SeriesStatistics]:
    """One :class:`SeriesStatistics` per scenario x element x variable."""
    grouped: dict[SeriesKey, list[ResultPoint]] = {}

    for point in dataset.results:
        key = SeriesKey(point.scenario_id, point.element_id, point.variable)
        grouped.setdefault(key, []).append(point)

    stats = [_series_statistics(points) for points in grouped.values()]
    stats.sort(key=lambda s: (s.scenario_id, s.element_id, s.variable.value))
    return stats


def index_statistics(
    stats: Iterable[SeriesStatistics],
) -> dict[SeriesKey, SeriesStatistics]:
    """Index statistics for fast lookup during comparison."""
    return {s.key: s for s in stats}


def filter_statistics(
    stats: Iterable[SeriesStatistics],
    *,
    element_type: ElementType | None = None,
    variable: Variable | None = None,
    scenario_id: str | None = None,
    exclude_scenario_id: str | None = None,
) -> list[SeriesStatistics]:
    """Convenience filter used by the ranking and report builders."""
    result = list(stats)
    if element_type is not None:
        result = [s for s in result if s.element_type is element_type]
    if variable is not None:
        result = [s for s in result if s.variable is variable]
    if scenario_id is not None:
        result = [s for s in result if s.scenario_id == scenario_id]
    if exclude_scenario_id is not None:
        result = [s for s in result if s.scenario_id != exclude_scenario_id]
    return result
