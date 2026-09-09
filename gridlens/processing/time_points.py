"""Relevant time points.

Identifies moments that are informative to look at. The reason is stated as a
factual observation ("time of the highest line loading"), never as a judgement.
Nothing here is called critical, dangerous or unacceptable.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridlens.processing.rankings import RankingEntry, RankingType, entries_of

#: How many leading entries of each ranking contribute a time point.
DEFAULT_TIME_POINTS_PER_RANKING = 3

#: Number of coinciding observations that makes a timestamp noteworthy.
DEFAULT_COINCIDENCE_THRESHOLD = 2


@dataclass(frozen=True, slots=True)
class RelevantTimePoint:
    timestamp: str
    scenario_id: str
    reason: str
    element_id: str | None = None
    element_name: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    unit: str | None = None


#: Neutral, descriptive reason texts.
_REASONS: dict[RankingType, str] = {
    RankingType.HIGHEST_LINE_LOADING: "Zeitpunkt der höchsten Leitungsauslastung",
    RankingType.HIGHEST_TRANSFORMER_LOADING: "Zeitpunkt der höchsten Trafoauslastung",
    RankingType.LOWEST_VOLTAGE: "Zeitpunkt der niedrigsten Spannung",
    RankingType.HIGHEST_VOLTAGE: "Zeitpunkt der höchsten Spannung",
}

_COINCIDENCE_REASON = "Mehrere Spitzenwerte fallen auf diesen Zeitpunkt"


def collect_relevant_time_points(
    rankings: list[RankingEntry],
    per_ranking: int = DEFAULT_TIME_POINTS_PER_RANKING,
    coincidence_threshold: int = DEFAULT_COINCIDENCE_THRESHOLD,
) -> list[RelevantTimePoint]:
    """Derive relevant time points from the ranking lists.

    Two kinds of entry are produced: the time of each leading extreme value, and
    timestamps at which several of those extremes coincide.
    """
    if per_ranking <= 0:
        raise ValueError("per_ranking must be positive")

    points: list[RelevantTimePoint] = []
    seen: set[tuple[str, str, str]] = set()

    for ranking_type, reason in _REASONS.items():
        for entry in entries_of(rankings, ranking_type)[:per_ranking]:
            if not entry.event_time:
                continue

            key = (entry.event_time, entry.scenario_id, reason)
            if key in seen:
                continue
            seen.add(key)

            points.append(
                RelevantTimePoint(
                    timestamp=entry.event_time,
                    scenario_id=entry.scenario_id,
                    reason=reason,
                    element_id=entry.element_id,
                    element_name=entry.element_name,
                    metric_name=entry.metric_name,
                    metric_value=entry.metric_value,
                    unit=entry.unit,
                )
            )

    points += _coincidences(points, coincidence_threshold)

    points.sort(key=lambda p: (p.timestamp, p.scenario_id, p.reason))
    return points


def _coincidences(
    points: list[RelevantTimePoint], threshold: int
) -> list[RelevantTimePoint]:
    """Flag timestamps carrying several independent observations at once."""
    if threshold <= 1:
        return []

    grouped: dict[tuple[str, str], int] = {}
    for point in points:
        grouped[(point.timestamp, point.scenario_id)] = (
            grouped.get((point.timestamp, point.scenario_id), 0) + 1
        )

    return [
        RelevantTimePoint(
            timestamp=timestamp,
            scenario_id=scenario_id,
            reason=f"{_COINCIDENCE_REASON} ({count})",
        )
        for (timestamp, scenario_id), count in sorted(grouped.items())
        if count >= threshold
    ]
