"""Adapter for plain record sequences (dicts).

This is the generic entry point: whatever the upstream transport is - CSV, JSON,
a PowerFactory export or an in-memory mock - it only has to produce dictionaries
matching ``contracts/input-data-v1.yaml``.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from gridlens.adapters.base import AdapterError, InputAdapter
from gridlens.adapters.normalization import (
    normalize_element_type,
    normalize_unit,
    normalize_variable,
)
from gridlens.canonical import (
    CanonicalDataset,
    Outage,
    QaCheck,
    ResultPoint,
    Scenario,
    StudyInfo,
)

Record = Mapping[str, Any]


def _require(record: Record, key: str, context: str) -> Any:
    if key not in record or record[key] is None or record[key] == "":
        raise AdapterError(f"{context}: required field '{key}' is missing or empty.")
    return record[key]


def _optional(record: Record, key: str) -> Any | None:
    value = record.get(key)
    if value is None or value == "":
        return None
    return value


def _as_float(value: Any, context: str, key: str) -> float:
    # NaN is preserved rather than replaced - validation reports it explicitly.
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AdapterError(f"{context}: '{key}' is not numeric (got {value!r}).") from exc


class RecordAdapter(InputAdapter):
    """Builds a :class:`CanonicalDataset` from iterables of records."""

    def __init__(
        self,
        study: StudyInfo,
        scenario_records: Iterable[Record],
        result_records: Iterable[Record],
        outage_records: Iterable[Record] = (),
        qa_records: Iterable[Record] = (),
    ) -> None:
        self._study = study
        self._scenario_records = list(scenario_records)
        self._result_records = list(result_records)
        self._outage_records = list(outage_records)
        self._qa_records = list(qa_records)

    def load(self) -> CanonicalDataset:
        return CanonicalDataset(
            study=self._study,
            scenarios=[self._scenario(r, i) for i, r in enumerate(self._scenario_records)],
            outages=[self._outage(r, i) for i, r in enumerate(self._outage_records)],
            qa_checks=[self._qa(r, i) for i, r in enumerate(self._qa_records)],
            results=[self._result(r, i) for i, r in enumerate(self._result_records)],
        )

    # -- record mappers ----------------------------------------------------

    def _scenario(self, record: Record, index: int) -> Scenario:
        context = f"I-SCENARIO row {index}"
        return Scenario(
            study_id=str(_require(record, "study_id", context)),
            scenario_id=str(_require(record, "scenario_id", context)),
            scenario_name=str(_require(record, "scenario_name", context)),
            is_reference=bool(int(_require(record, "is_reference", context))),
            description=str(_optional(record, "description") or ""),
            simulation_start=str(_require(record, "simulation_start", context)),
            simulation_end=str(_require(record, "simulation_end", context)),
            simulation_status=str(_require(record, "simulation_status", context)),
        )

    def _outage(self, record: Record, index: int) -> Outage:
        context = f"I-OUTAGE row {index}"
        return Outage(
            outage_id=str(_require(record, "outage_id", context)),
            scenario_id=str(_require(record, "scenario_id", context)),
            element_id=str(_require(record, "element_id", context)),
            element_name=str(_require(record, "element_name", context)),
            element_type=normalize_element_type(_require(record, "element_type", context)),
            start_time=str(_require(record, "start_time", context)),
            end_time=str(_require(record, "end_time", context)),
            action=str(_require(record, "action", context)),
        )

    def _qa(self, record: Record, index: int) -> QaCheck:
        context = f"I-QA row {index}"
        return QaCheck(
            model_id=str(_require(record, "model_id", context)),
            model_version=str(_require(record, "model_version", context)),
            check_id=str(_require(record, "check_id", context)),
            check_name=str(_require(record, "check_name", context)),
            status=str(_require(record, "status", context)),
            message=str(_optional(record, "message") or ""),
            affected_element=str(_optional(record, "affected_element") or ""),
        )

    def _result(self, record: Record, index: int) -> ResultPoint:
        context = f"I-RESULT row {index}"
        variable = normalize_variable(_require(record, "variable", context))

        # element_id must be present but may legitimately be absent in broken
        # upstream data; validation reports it, so we surface it as an error here
        # only when the key is entirely missing.
        element_id = record.get("element_id")
        if element_id is None or str(element_id).strip() == "":
            raise AdapterError(f"{context}: required field 'element_id' is missing or empty.")

        return ResultPoint(
            study_id=str(_require(record, "study_id", context)),
            scenario_id=str(_require(record, "scenario_id", context)),
            timestamp=str(_require(record, "timestamp", context)),
            element_id=str(element_id),
            element_name=str(_require(record, "element_name", context)),
            element_type=normalize_element_type(_require(record, "element_type", context)),
            variable=variable,
            value=_as_float(record.get("value"), context, "value"),
            unit=normalize_unit(record.get("unit"), variable),
            voltage_level=_opt_str(_optional(record, "voltage_level")),
            substation=_opt_str(_optional(record, "substation")),
            area=_opt_str(_optional(record, "area")),
        )


def _opt_str(value: Any | None) -> str | None:
    return None if value is None else str(value)
