"""Adapters: raw upstream records -> canonical data model.

This is the only layer that is allowed to know PowerFactory vocabulary such as
``ElmLne`` or ``m:u1``. Everything above works on the canonical model.
"""

from gridlens.adapters.base import AdapterError, InputAdapter
from gridlens.adapters.normalization import (
    normalize_element_type,
    normalize_unit,
    normalize_variable,
)
from gridlens.adapters.record_adapter import RecordAdapter

__all__ = [
    "AdapterError",
    "InputAdapter",
    "RecordAdapter",
    "normalize_element_type",
    "normalize_unit",
    "normalize_variable",
]
