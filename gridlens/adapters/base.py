"""Adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gridlens.canonical import CanonicalDataset


class AdapterError(Exception):
    """Raised when raw input cannot be mapped onto the canonical model."""


class InputAdapter(ABC):
    """Converts one concrete input representation into the canonical model.

    Implementations may know the quirks of their source format. They must not
    invent, infer or repair data: anything questionable is left for the
    validation stage so that it surfaces as an explicit finding.
    """

    @abstractmethod
    def load(self) -> CanonicalDataset:
        """Read the source and return the normalized dataset."""
