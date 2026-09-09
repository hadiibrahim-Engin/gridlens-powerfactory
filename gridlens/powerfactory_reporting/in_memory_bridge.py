"""In-memory bridge.

Records everything a real IntReport bridge would do, so the publishing path is
fully testable without PowerFactory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gridlens.powerfactory_reporting.bridge import IntReportBridge


@dataclass(slots=True)
class RecordedTable:
    name: str
    fields: dict[str, str] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)

    def value(self, row_index: int, field_name: str) -> Any:
        return self.rows[row_index].get(field_name)


class InMemoryIntReportBridge(IntReportBridge):
    """Bridge that keeps the published tables in memory."""

    def __init__(self) -> None:
        self.tables: dict[str, RecordedTable] = {}

    def create_table(self, name: str) -> RecordedTable:
        table = RecordedTable(name=name)
        self.tables[name] = table
        return table

    def create_field(self, table: RecordedTable, name: str, field_type: str) -> str:
        table.fields[name] = field_type
        return name

    def set_value(
        self, table: RecordedTable, row_index: int, name: str, value: Any
    ) -> None:
        while len(table.rows) <= row_index:
            table.rows.append({})
        table.rows[row_index][name] = value

    # -- convenience for tests and diagnostics -----------------------------

    @property
    def table_names(self) -> list[str]:
        return list(self.tables)

    def row_count(self, table_name: str) -> int:
        return len(self.tables[table_name].rows)
