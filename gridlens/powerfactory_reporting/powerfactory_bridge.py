"""IntReport publishing based on the user's PowerFactory script example.

Table/field/value operations belong to IntReport itself. CreateTable's return
value is not a table object. Native execution still needs a PowerFactory test.
"""

from __future__ import annotations

from typing import Any

from gridlens.powerfactory_reporting.bridge import IntReportBridge
from gridlens.contracts.loader import DataContract


class PowerFactoryUnavailableError(RuntimeError):
    """Raised when the PowerFactory Python API cannot be imported."""


def import_powerfactory() -> Any:
    """Import the PowerFactory Python module, failing with a clear message.

    Kept as a function so the rest of GridLens never imports PowerFactory at
    module load time.
    """
    try:
        import powerfactory  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on the host
        raise PowerFactoryUnavailableError(
            "The PowerFactory Python module is not importable. This bridge only "
            "requires a configured PowerFactory Python environment."
        ) from exc
    return powerfactory


class PowerFactoryIntReportBridge(IntReportBridge):
    """Publishes contract tables into a PowerFactory ``IntReport`` object.

    Every PowerFactory call is confined to the three methods below.
    """

    FIELD_TYPES = {"string": 0, "integer": 1, "number": 2}

    def __init__(self, int_report: Any, *, host_table_prefix: str = "Scripted") -> None:
        if int_report is None:
            raise ValueError("An IntReport object is required.")
        self._int_report = int_report
        # The user's designer confirms that PowerFactory adds "Scripted".
        # Contract names and SQL table names always retain their full spelling.
        self._host_table_prefix = host_table_prefix

    def publish(self, payload: dict[str, list[dict[str, Any]]], contract: DataContract) -> None:
        # Validate before Reset: bad input must not clear an existing report.
        contract.validate_payload(payload)
        for source in contract.sources:
            self._table_name(source.name)
            for field in source.fields:
                if field.type not in self.FIELD_TYPES:
                    raise ValueError(f"Unsupported field type: {field.type}")
        self._int_report.Reset()
        try:
            super().publish(payload, contract)
        except Exception:
            # Clear a partial publication; preserve the original exception.
            try:
                self._int_report.Reset()
            except Exception:
                pass
            raise

    def _table_name(self, name: str) -> str:
        prefix = self._host_table_prefix
        if prefix and (not name.startswith(prefix) or name == prefix):
            raise ValueError(f"Table {name!r} must start with host prefix {prefix!r}.")
        return name[len(prefix):] if prefix else name

    def create_table(self, name: str) -> Any:
        table_name = self._table_name(name)
        self._int_report.CreateTable(table_name)
        return table_name

    def create_field(self, table: Any, name: str, field_type: str) -> Any:
        return self._int_report.CreateField(table, name, self.FIELD_TYPES[field_type])

    def set_value(self, table: Any, row_index: int, name: str, value: Any) -> None:
        # The supplied example leaves missing cells unwritten instead of
        # substituting zero or passing None across the native interface.
        if value is not None:
            self._int_report.SetValue(table, name, row_index, value)
