"""Tests fuer die Zahlen- und Rueckgabecode-Normalisierung."""

import sys
from pathlib import Path

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import pfutil


class Result:
    def __init__(self, values):
        self._values = values

    def GetValue(self, row, column):
        return self._values[row][column]


def test_finite_number_accepts_plain_numbers_and_numeric_strings():
    assert pfutil.finite_number(3) == 3.0
    assert pfutil.finite_number("4,5") == 4.5


def test_finite_number_rejects_non_numbers():
    assert pfutil.finite_number(None) is None
    assert pfutil.finite_number(True) is None
    assert pfutil.finite_number(float("nan")) is None
    assert pfutil.finite_number(float("inf")) is None


def test_finite_number_never_unwraps_a_sequence():
    """GL-PR-002: a (code, value) pair must not become a measured value."""
    assert pfutil.finite_number((7, -999.0)) is None
    assert pfutil.finite_number((1, 0.0)) is None
    assert pfutil.finite_number([0, 42.0]) is None


def test_return_code_treats_a_missing_return_value_as_success():
    assert pfutil.return_code(None) == 0.0


def test_return_code_reads_the_code_from_a_number_or_a_sequence():
    assert pfutil.return_code(0) == 0.0
    assert pfutil.return_code(1) == 1.0
    assert pfutil.return_code((1, "Fehler")) == 1.0


def test_return_code_reports_an_unreadable_return_value_as_none():
    assert pfutil.return_code(()) is None
    assert pfutil.return_code("nicht lesbar") is None


def test_result_value_reads_a_plain_cell():
    assert pfutil.result_value(Result([[12.5]]), 0, 0) == 12.5


def test_result_value_rejects_a_cell_with_a_non_zero_error_code():
    assert pfutil.result_value(Result([[(7, -999.0)]]), 0, 0) is None


def test_result_value_accepts_a_cell_with_a_zero_error_code():
    assert pfutil.result_value(Result([[(0, 42.0)]]), 0, 0) == 42.0
