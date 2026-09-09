"""Report data model: processing output -> report data contract payload."""

from gridlens.report_model.builder import Payload, Row, build_report_payload
from gridlens.report_model.formatting import (
    round_for_unit,
    round_loading,
    round_voltage,
)

__all__ = [
    "Payload",
    "Row",
    "build_report_payload",
    "round_for_unit",
    "round_loading",
    "round_voltage",
]
