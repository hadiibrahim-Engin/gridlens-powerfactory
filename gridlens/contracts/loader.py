"""Loading and validating the YAML data contracts.

The YAML files in this directory are the single source of truth. The Python
processing layer and the portable PowerFactory schema are checked against them,
so a field cannot silently drift between the two sides.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable

import yaml

CONTRACTS_DIR = Path(__file__).resolve().parent

REPORT_CONTRACT_FILE = "report-data-v1.yaml"
INPUT_CONTRACT_FILE = "input-data-v1.yaml"

#: Contract version this build of GridLens speaks.
SUPPORTED_REPORT_VERSION = "2.0"

VALID_TYPES = {"string", "integer", "number"}
VALID_CARDINALITIES = {"single_row", "multi_row"}


class ContractError(Exception):
    """Raised when a contract file or the data offered against it is invalid."""


def _finite_number(value: int | float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True, slots=True)
class ContractField:
    name: str
    type: str
    required: bool = True

    @property
    def python_type(self) -> type:
        return {"string": str, "integer": int, "number": float}[self.type]


@dataclass(frozen=True, slots=True)
class ContractSource:
    """One data source of the contract."""

    name: str
    cardinality: str
    description: str
    fields: tuple[ContractField, ...]

    @property
    def single_row(self) -> bool:
        return self.cardinality == "single_row"

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    @property
    def required_fields(self) -> tuple[ContractField, ...]:
        return tuple(f for f in self.fields if f.required)

    def field(self, name: str) -> ContractField:
        for candidate in self.fields:
            if candidate.name == name:
                return candidate
        raise ContractError(
            f"Field '{name}' is not part of data source '{self.name}'. "
            f"Known fields: {', '.join(self.field_names)}."
        )

    def validate_rows(self, rows: list[dict[str, Any]]) -> None:
        """Check a list of report rows against this source.

        Reports every problem it can rather than stopping at the first, so a
        caller sees the full picture. Never repairs data silently.
        """
        if not isinstance(rows, list):
            raise ContractError(f"Data source '{self.name}' must be a list of rows.")
        if self.single_row and len(rows) != 1:
            raise ContractError(
                f"Data source '{self.name}' is declared single_row but carries "
                f"{len(rows)} row(s)."
            )

        problems: list[str] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                problems.append(f"row {index}: expected a dictionary")
                continue
            unknown = set(row) - set(self.field_names)
            if unknown:
                problems.append(
                    f"row {index}: unknown field(s) {', '.join(sorted(unknown))}"
                )
            for field_def in self.required_fields:
                if field_def.name not in row:
                    problems.append(f"row {index}: missing '{field_def.name}'")
                elif row[field_def.name] is None:
                    problems.append(f"row {index}: '{field_def.name}' is null")
            for field_def in self.fields:
                value = row.get(field_def.name)
                if value is None:
                    continue
                valid = (
                    isinstance(value, str) if field_def.type == "string"
                    else type(value) is int and -(2**31) <= value < 2**31
                    if field_def.type == "integer"
                    else type(value) in (int, float) and _finite_number(value)
                )
                if not valid:
                    problems.append(
                        f"row {index}: '{field_def.name}' must be {field_def.type} "
                        "(numbers must be finite and integers must fit Int32)"
                    )

        if problems:
            raise ContractError(
                f"Data source '{self.name}' violates the report data contract:\n  - "
                + "\n  - ".join(problems)
            )


@dataclass(frozen=True, slots=True)
class DataContract:
    version: str
    sources: tuple[ContractSource, ...]
    path: Path
    template_name: str = ""
    template_version: str = ""

    @property
    def source_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.sources)

    def source(self, name: str) -> ContractSource:
        for candidate in self.sources:
            if candidate.name == name:
                return candidate
        raise ContractError(
            f"Unknown data source '{name}'. Contract {self.version} defines: "
            f"{', '.join(self.source_names)}."
        )

    def require_version(self, expected: str) -> None:
        if self.version != expected:
            raise ContractError(
                f"Incompatible data contract version: file {self.path.name} declares "
                f"'{self.version}' but this build of GridLens requires '{expected}'."
            )

    def validate_payload(self, payload: dict[str, list[dict[str, Any]]]) -> None:
        """Validate a full report payload: every source present and well formed."""
        if not isinstance(payload, dict):
            raise ContractError("Report payload must be a dictionary of data sources.")
        missing = [name for name in self.source_names if name not in payload]
        if missing:
            raise ContractError(
                "Report payload is missing data source(s): " + ", ".join(missing)
            )

        extra = [name for name in payload if name not in self.source_names]
        if extra:
            raise ContractError(
                "Report payload carries data source(s) outside contract "
                f"{self.version}: {', '.join(sorted(extra))}."
            )

        for source in self.sources:
            source.validate_rows(payload[source.name])


def _parse_fields(raw_fields: Iterable[dict[str, Any]], source_name: str) -> tuple[ContractField, ...]:
    fields: list[ContractField] = []
    seen: set[str] = set()

    for raw in raw_fields:
        name = raw.get("name")
        if not name:
            raise ContractError(f"Data source '{source_name}' has a field without a name.")
        if name in seen:
            raise ContractError(
                f"Data source '{source_name}' declares duplicate field '{name}'."
            )
        seen.add(name)

        field_type = raw.get("type", "string")
        if field_type not in VALID_TYPES:
            raise ContractError(
                f"Field '{source_name}.{name}' has unsupported type '{field_type}'. "
                f"Allowed: {', '.join(sorted(VALID_TYPES))}."
            )

        fields.append(
            ContractField(name=name, type=field_type, required=bool(raw.get("required", True)))
        )

    if not fields:
        raise ContractError(f"Data source '{source_name}' declares no fields.")
    return tuple(fields)


def _parse_sources(raw_sources: Any, key: str, path: Path) -> tuple[ContractSource, ...]:
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ContractError(f"Contract {path.name} defines no '{key}'.")

    sources: list[ContractSource] = []
    seen: set[str] = set()

    for raw in raw_sources:
        name = raw.get("name")
        if not name:
            raise ContractError(f"Contract {path.name} has an entry without a name.")
        if name in seen:
            raise ContractError(
                f"Contract {path.name} declares duplicate data source '{name}'."
            )
        seen.add(name)

        cardinality = raw.get("cardinality", "multi_row")
        if cardinality not in VALID_CARDINALITIES:
            raise ContractError(
                f"Data source '{name}' has unsupported cardinality '{cardinality}'."
            )

        sources.append(
            ContractSource(
                name=name,
                cardinality=cardinality,
                description=(raw.get("description") or "").strip(),
                fields=_parse_fields(raw.get("fields", []), name),
            )
        )

    return tuple(sources)


def _load(path: Path, key: str) -> dict[str, Any]:
    if not path.exists():
        raise ContractError(f"Contract file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)

    if not isinstance(document, dict):
        raise ContractError(f"Contract {path.name} is not a YAML mapping.")
    if "version" not in document:
        raise ContractError(f"Contract {path.name} declares no version.")
    if key not in document:
        raise ContractError(f"Contract {path.name} has no '{key}' section.")

    return document


def load_report_contract(path: Path | None = None) -> DataContract:
    """Load the report data contract that feeds IntReport and Stimulsoft."""
    path = path or CONTRACTS_DIR / REPORT_CONTRACT_FILE
    document = _load(path, "data_sources")

    return DataContract(
        version=str(document["version"]),
        sources=_parse_sources(document["data_sources"], "data_sources", path),
        path=path,
        template_name=str(document.get("template_name", "")),
        template_version=str(document.get("template_version", "")),
    )


def load_input_contract(path: Path | None = None) -> DataContract:
    """Load the contract describing what upstream modules must deliver."""
    path = path or CONTRACTS_DIR / INPUT_CONTRACT_FILE
    document = _load(path, "inputs")

    return DataContract(
        version=str(document["version"]),
        sources=_parse_sources(document["inputs"], "inputs", path),
        path=path,
    )
