"""IntReport bridge interface.

GridLens hands the report payload to PowerFactory through this narrow interface.
No PowerFactory API is called anywhere else in the code base, so the whole
integration can be exercised without PowerFactory installed.

Target architecture:

    Report Data Model
        -> ComPython IntReport extension
        -> CreateTable / CreateField / SetValue
        -> Scripted Data Sources
        -> Stimulsoft

The native implementation follows the user's IntReport script example. All
three methods belong to IntReport. Actual execution in the user's PowerFactory
2026 installation is the remaining integration check.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from gridlens.contracts.loader import ContractSource, DataContract


class IntReportBridge(ABC):
    """Publishes contract data sources into a report host."""

    @abstractmethod
    def create_table(self, name: str) -> Any:
        """Create (or reset) a table named after the contract data source."""

    @abstractmethod
    def create_field(self, table: Any, name: str, field_type: str) -> Any:
        """Declare one column on a table."""

    @abstractmethod
    def set_value(self, table: Any, row_index: int, name: str, value: Any) -> None:
        """Write one cell."""

    def publish(
        self,
        payload: dict[str, list[dict[str, Any]]],
        contract: DataContract,
    ) -> None:
        """Publish a validated payload through this bridge.

        The contract drives the iteration, so a table is always created with the
        contract's fields even when the payload has no rows: the template binds
        to the schema, not to the data.
        """
        contract.validate_payload(payload)

        for source in contract.sources:
            self._publish_source(source, payload[source.name])

    def _publish_source(self, source: ContractSource, rows: list[dict[str, Any]]) -> None:
        table = self.create_table(source.name)

        for field in source.fields:
            self.create_field(table, field.name, field.type)

        for row_index, row in enumerate(rows):
            for field in source.fields:
                self.set_value(table, row_index, field.name, row.get(field.name))
