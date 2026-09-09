# Processing Layer

PowerFactory-independent. Everything here works on the canonical model and
produces figures - never verdicts.

```text
Input  →  Normalization  →  Validation  →  Statistics  →  Comparisons
       →  Rankings  →  Time points  →  Plot selection  →  Report Data Model
```

Entry point: `gridlens.processing.run(dataset, options)`.

## 1. Adapter and normalization

`gridlens/adapters/record_adapter.py` turns dictionaries matching
`contracts/input-data-v1.yaml` into the canonical model.

`normalization.py` is the only module that knows PowerFactory vocabulary:

- `ElmLne → line`, `ElmTr2`/`ElmTr3 → transformer`, `ElmTerm → busbar`
- `c:loading`/`m:loading → loading`, `m:u`/`m:u1 → voltage`,
  `m:phiu`/`m:phiu1 → voltage_angle`

An **unknown element type** becomes `other`: unfamiliar equipment is not a data
defect, it just gets no specialised analysis. An **unknown variable** is
rejected: silently reinterpreting a measured quantity would corrupt every
statistic derived from it.

## 2. Validation

`validate()` runs every rule and returns **all** findings at once, so one run
shows the full picture instead of the first problem only. Nothing is repaired
silently.

| Code | Severity |
|---|---|
| `MISSING_REFERENCE`, `MULTIPLE_REFERENCES` | ERROR |
| `NO_SCENARIOS`, `SCENARIO_WITHOUT_RESULTS` | ERROR |
| `MISSING_TIMESTAMPS`, `MISSING_ELEMENT_ID` | ERROR |
| `DUPLICATE_ELEMENT_ID`, `DUPLICATE_RESULT_POINT` | ERROR |
| `MISSING_UNIT`, `INCONSISTENT_UNIT` | ERROR |
| `NON_FINITE_VALUE` (NaN, infinity, null) | ERROR |
| `INCONSISTENT_TIME_AXIS` | WARNING |

A differing time axis is a warning, not an error: the report is still valid, it
simply skips time-aligned differences for that scenario.

`run()` calls `raise_for_errors()` before computing anything, so no statistic is
ever derived from data known to be inconsistent.

## 3. Statistics

Per `scenario × element × variable`: `min`, `max`, `mean`, `p95`,
`time_of_min`, `time_of_max`.

`p95` uses linear interpolation, matching numpy's default method, implemented
directly so the processing layer stays dependency free. Series are sorted by
timestamp first, so a value occurring more than once reports its **earliest**
timestamp - which makes the output reproducible.

## 4. Reference comparison

Every scenario against the single reference, per element and variable:
`reference_*`, `scenario_*` and `delta_*` for min, max and mean.

A series with no reference counterpart is **skipped**, not compared against a
substituted value - an invented baseline is worse than a gap.

`time_aligned_differences()` computes `scenario(t) − reference(t)` for the
timestamps present in **both** series. Nothing is interpolated.

## 5. Scenario comparison

Each scenario, reference included, condensed to headline metrics: highest line
loading, highest transformer loading, lowest voltage, highest voltage.

The result is long format (one row per metric and scenario) so the number of
scenarios stays free. Extend `DEFAULT_METRICS` to add a row - no template change
is needed.

## 6. Rankings

Eight lists, pre-sorted and pre-ranked (1-based). Absolute rankings exclude the
reference state, which the report shows separately. Delta rankings list only
movements in the requested direction, so a "largest rise" list is never padded
with unchanged or falling entries.

`highest_line_loading`, `highest_transformer_loading`, `lowest_voltage`,
`highest_voltage`, `largest_line_loading_delta`,
`largest_transformer_loading_delta`, `largest_voltage_drop`,
`largest_voltage_rise`.

The entry count is configurable: `ProcessingOptions(top_n=20)`.

## 7. Relevant time points

The time of each leading extreme, plus timestamps where several of those
extremes coincide.

Reasons are stated as observations - "Zeitpunkt der höchsten Leitungsauslastung"
- never as a judgement. A test asserts that no reason contains `kritisch`,
`gefährlich`, `unzulässig` or `unsicher`.

## 8. Plot selection

Driven by the rankings already computed, so every chart traces back to a number
rather than to a heuristic hidden in the template. Top N absolute values plus
top N reference deltas, deduplicated per scenario, element and variable.

The output only says *what* to plot. Stimulsoft draws it.

## Determinism

Every stage sorts its output by stable keys and breaks ties explicitly. Running
the pipeline twice on the same input yields identical results
(`test_pipeline_is_reproducible`).
