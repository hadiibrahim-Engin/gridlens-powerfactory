"""Processing layer tests: statistics, comparisons, rankings, selection."""

from __future__ import annotations

import pytest

from gridlens.canonical import ElementType, Variable
from gridlens.processing import (
    build_rankings,
    collect_relevant_time_points,
    compare_scenarios,
    compare_to_reference,
    compute_statistics,
    percentile,
    run,
    select_plots,
    time_aligned_differences,
)
from gridlens.processing.rankings import RankingType, entries_of
from gridlens.tests.conftest import TIMES, build, result_record, scenario_record

# -- statistics ---------------------------------------------------------------


def test_percentile_matches_linear_interpolation():
    values = [float(v) for v in range(1, 11)]  # 1..10
    # position = 0.95 * 9 = 8.55 -> between 9 and 10
    assert percentile(values, 0.95) == pytest.approx(9.55)


def test_percentile_of_single_value():
    assert percentile([42.0], 0.95) == 42.0


def test_percentile_rejects_empty_series():
    with pytest.raises(ValueError):
        percentile([], 0.95)


def test_min_max_mean_are_exact(simple_dataset):
    stats = {s.scenario_id: s for s in compute_statistics(simple_dataset)}

    reference = stats["REF"]
    assert reference.minimum == 10.0
    assert reference.maximum == 40.0
    assert reference.mean == pytest.approx(25.0)

    scenario = stats["S01"]
    assert scenario.minimum == 20.0
    assert scenario.maximum == 60.0
    assert scenario.mean == pytest.approx(37.5)


def test_time_of_min_and_max_are_reported(simple_dataset):
    stats = {s.scenario_id: s for s in compute_statistics(simple_dataset)}

    assert stats["REF"].time_of_min == TIMES[0]  # value 10
    assert stats["REF"].time_of_max == TIMES[3]  # value 40


def test_time_of_max_uses_earliest_occurrence():
    scenarios = [scenario_record("REF", is_reference=True)]
    results = [
        result_record("REF", TIMES[0], "L1", 50.0),
        result_record("REF", TIMES[1], "L1", 80.0),
        result_record("REF", TIMES[2], "L1", 80.0),
    ]

    stat = compute_statistics(build(scenarios, results))[0]
    assert stat.time_of_max == TIMES[1]


def test_p95_of_known_series(simple_dataset):
    stats = {s.scenario_id: s for s in compute_statistics(simple_dataset)}
    # REF values 10,20,30,40 -> position 0.95*3 = 2.85 -> 30 + 0.85*10 = 38.5
    assert stats["REF"].p95 == pytest.approx(38.5)


def test_one_statistic_per_scenario_element_variable(mock_dataset):
    stats = compute_statistics(mock_dataset)
    keys = {(s.scenario_id, s.element_id, s.variable) for s in stats}
    assert len(keys) == len(stats)


# -- reference comparison -----------------------------------------------------


def test_reference_comparison_deltas_are_exact(simple_dataset):
    stats = compute_statistics(simple_dataset)
    comparison = compare_to_reference(stats, "REF")

    assert len(comparison) == 1
    entry = comparison[0]
    assert entry.scenario_id == "S01"
    assert entry.delta_min == pytest.approx(10.0)   # 20 - 10
    assert entry.delta_max == pytest.approx(20.0)   # 60 - 40
    assert entry.delta_mean == pytest.approx(12.5)  # 37.5 - 25


def test_reference_is_not_compared_against_itself(mock_result):
    assert all(c.scenario_id != "REF" for c in mock_result.reference_comparisons)


def test_time_aligned_difference_per_timestamp(simple_dataset):
    differences = time_aligned_differences(simple_dataset, "REF")

    assert len(differences) == len(TIMES)
    assert [d.delta for d in differences] == pytest.approx([10.0, 10.0, 10.0, 20.0])


def test_time_aligned_difference_skips_unmatched_timestamps():
    scenarios = [scenario_record("REF", is_reference=True), scenario_record("S01")]
    results = [
        result_record("REF", TIMES[0], "L1", 10.0),
        result_record("REF", TIMES[1], "L1", 20.0),
        # S01 only shares the second timestamp.
        result_record("S01", TIMES[1], "L1", 25.0),
        result_record("S01", TIMES[2], "L1", 30.0),
    ]

    differences = time_aligned_differences(build(scenarios, results), "REF")
    assert len(differences) == 1
    assert differences[0].timestamp == TIMES[1]
    assert differences[0].delta == pytest.approx(5.0)


# -- scenario comparison ------------------------------------------------------


def test_scenario_comparison_covers_every_scenario(mock_dataset, mock_result):
    metrics = compare_scenarios(mock_result.statistics, mock_dataset.scenario_ids)
    line_metric = [m for m in metrics if m.metric_key == "max_line_loading"]

    assert {m.scenario_id for m in line_metric} == set(mock_dataset.scenario_ids)


def test_scenario_comparison_picks_the_highest_line(simple_dataset):
    stats = compute_statistics(simple_dataset)
    metrics = compare_scenarios(stats, ["REF", "S01"])

    by_scenario = {
        m.scenario_id: m for m in metrics if m.metric_key == "max_line_loading"
    }
    assert by_scenario["REF"].metric_value == 40.0
    assert by_scenario["S01"].metric_value == 60.0


def test_scenario_comparison_is_not_limited_to_a_fixed_scenario_count():
    scenarios = [scenario_record("REF", is_reference=True)]
    results = [result_record("REF", TIMES[0], "L1", 10.0)]

    for index in range(1, 13):  # far more than the four mock scenarios
        scenario_id = f"S{index:02d}"
        scenarios.append(scenario_record(scenario_id))
        results.append(result_record(scenario_id, TIMES[0], "L1", 10.0 + index))

    stats = compute_statistics(build(scenarios, results))
    metrics = compare_scenarios(stats, [s["scenario_id"] for s in scenarios])

    assert len({m.scenario_id for m in metrics}) == 13


# -- rankings -----------------------------------------------------------------


def test_ranking_is_ordered_and_ranked_from_one(mock_result):
    entries = entries_of(mock_result.rankings, RankingType.HIGHEST_LINE_LOADING)

    assert entries
    assert [e.rank for e in entries] == list(range(1, len(entries) + 1))
    values = [e.metric_value for e in entries]
    assert values == sorted(values, reverse=True)


def test_lowest_voltage_ranking_is_ascending(mock_result):
    entries = entries_of(mock_result.rankings, RankingType.LOWEST_VOLTAGE)
    values = [e.metric_value for e in entries]
    assert values == sorted(values)


def test_absolute_rankings_exclude_the_reference(mock_result):
    for ranking_type in (
        RankingType.HIGHEST_LINE_LOADING,
        RankingType.HIGHEST_TRANSFORMER_LOADING,
        RankingType.LOWEST_VOLTAGE,
        RankingType.HIGHEST_VOLTAGE,
    ):
        entries = entries_of(mock_result.rankings, ranking_type)
        assert all(e.scenario_id != "REF" for e in entries)


def test_delta_rankings_only_list_the_requested_direction(mock_result):
    rises = entries_of(mock_result.rankings, RankingType.LARGEST_LINE_LOADING_DELTA)
    assert all(e.delta_value > 0 for e in rises)

    drops = entries_of(mock_result.rankings, RankingType.LARGEST_VOLTAGE_DROP)
    assert all(e.delta_value < 0 for e in drops)


def test_top_n_is_configurable(mock_result):
    few = build_rankings(
        mock_result.statistics,
        mock_result.reference_comparisons,
        mock_result.reference_scenario_id,
        top_n=2,
    )
    assert len(entries_of(few, RankingType.HIGHEST_LINE_LOADING)) <= 2

    many = build_rankings(
        mock_result.statistics,
        mock_result.reference_comparisons,
        mock_result.reference_scenario_id,
        top_n=20,
    )
    assert len(entries_of(many, RankingType.HIGHEST_LINE_LOADING)) >= len(
        entries_of(few, RankingType.HIGHEST_LINE_LOADING)
    )


def test_top_n_must_be_positive(mock_result):
    with pytest.raises(ValueError):
        build_rankings(
            mock_result.statistics,
            mock_result.reference_comparisons,
            mock_result.reference_scenario_id,
            top_n=0,
        )


# -- relevant time points -----------------------------------------------------


def test_relevant_time_points_carry_a_reason(mock_result):
    assert mock_result.relevant_time_points
    assert all(p.reason for p in mock_result.relevant_time_points)


def test_relevant_time_points_avoid_judgemental_wording(mock_result):
    forbidden = ("kritisch", "gefährlich", "unzulässig", "unsicher", "critical")
    for point in mock_result.relevant_time_points:
        assert not any(word in point.reason.lower() for word in forbidden)


def test_relevant_time_points_are_deduplicated(mock_result):
    keys = [
        (p.timestamp, p.scenario_id, p.reason, p.element_id)
        for p in mock_result.relevant_time_points
    ]
    assert len(keys) == len(set(keys))


def test_relevant_time_points_require_positive_window(mock_result):
    with pytest.raises(ValueError):
        collect_relevant_time_points(mock_result.rankings, per_ranking=0)


# -- plot selection -----------------------------------------------------------


def test_plot_selection_has_no_duplicates(mock_result):
    keys = [(p.scenario_id, p.element_id, p.variable) for p in mock_result.plots]
    assert len(keys) == len(set(keys))


def test_plot_ids_are_unique(mock_result):
    ids = [p.plot_id for p in mock_result.plots]
    assert len(ids) == len(set(ids))


def test_plot_series_contain_reference_and_scenario_curves(mock_result):
    roles_per_plot: dict[str, set[str]] = {}
    for point in mock_result.plot_series:
        roles_per_plot.setdefault(point.plot_id, set()).add(point.series_role)

    assert roles_per_plot
    for plot_id, roles in roles_per_plot.items():
        assert roles == {"reference", "scenario"}, plot_id


def test_plot_selection_respects_per_ranking_limit(mock_result):
    selections = select_plots(mock_result.rankings, per_ranking=1)
    assert len(selections) <= len(mock_result.plots)


def test_plot_selection_rejects_non_positive_limit(mock_result):
    with pytest.raises(ValueError):
        select_plots(mock_result.rankings, per_ranking=0)


# -- pipeline -----------------------------------------------------------------


def test_pipeline_is_reproducible(mock_dataset):
    first = run(mock_dataset)
    second = run(mock_dataset)

    assert [s.maximum for s in first.statistics] == [s.maximum for s in second.statistics]
    assert [e.element_id for e in first.rankings] == [e.element_id for e in second.rankings]
    assert [p.plot_id for p in first.plots] == [p.plot_id for p in second.plots]


def test_pipeline_reports_the_reference_scenario(mock_result):
    assert mock_result.reference_scenario_id == "REF"


def test_no_automatic_assessment_is_produced(mock_result):
    """GridLens must not emit verdicts anywhere in the processed output."""
    verdicts = ("zulässig", "unzulässig", "sicher", "unsicher", "ampel", "bestanden")

    texts = [p.reason for p in mock_result.relevant_time_points]
    texts += [m.metric_name for m in mock_result.scenario_metrics]
    texts += [e.metric_name for e in mock_result.rankings]

    for text in texts:
        assert not any(word in text.lower() for word in verdicts), text
