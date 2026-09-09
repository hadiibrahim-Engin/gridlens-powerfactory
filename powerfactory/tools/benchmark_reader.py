"""Messe Laufzeit und Speicherbedarf des Ergebnislesers ohne PowerFactory.

Der Lauf verwendet ein synthetisches ElmRes und beantwortet die Frage aus dem
Produktionsreview: Was kostet ein Fall mit vielen Knoten und einer langen
QDS-Zeitreihe? Die Zahlen sind eine Untergrenze - im Zielsystem kommt der
Aufwand der echten PowerFactory-API hinzu.

Aufruf aus dem Repositoriumswurzelverzeichnis:

    python3 powerfactory/tools/benchmark_reader.py --elements 1000 --rows 8760

Dieses Werkzeug wird nicht mit ausgeliefert.
"""

import argparse
import sys
import time
import tracemalloc
from pathlib import Path

DEPLOYMENT = Path(__file__).resolve().parents[1]
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import config, payload, results


class Element:
    def __init__(self, class_name, name):
        self._class_name = class_name
        self.loc_name = name
        self.uknom = 110.0

    def GetClassName(self):
        return self._class_name

    def GetFullName(self):
        return "Grid." + self.loc_name + "." + self._class_name


class SyntheticResult:
    """ElmRes double with a realistic column layout and value range."""

    def __init__(self, elements, rows, block_reads=True):
        self.rows = rows
        self.block_reads = block_reads
        self._columns = [(None, "b:tnow", "h")]
        for index in range(elements):
            self._columns.append(
                (Element("ElmLne", "Leitung {:05d}".format(index)),
                 "c:loading", "%"))
            self._columns.append(
                (Element("ElmTerm", "Knoten {:05d}".format(index)),
                 "m:u", "p.u."))

    def GetNumberOfRows(self):
        return self.rows

    def GetNumberOfColumns(self):
        return len(self._columns)

    def GetObject(self, column):
        return self._columns[column][0]

    def GetVariable(self, column):
        return self._columns[column][1]

    def GetUnit(self, column):
        return self._columns[column][2]

    def _cell(self, row, column):
        if column == 0:
            return float(row)
        if self._columns[column][1] == "m:u":
            return 1.0 + ((row + column) % 11 - 5) / 500.0
        return 40.0 + ((row + column) % 70)

    def GetValue(self, row, column):
        return 0, self._cell(row, column)

    def GetColumnValues(self, column):
        if not self.block_reads:
            raise RuntimeError("block reads disabled for this measurement")
        return [self._cell(row, column) for row in range(self.rows)]


def measure(elements, rows, block_reads):
    elmres = SyntheticResult(elements, rows, block_reads)
    tracemalloc.start()
    started = time.perf_counter()
    series, labels, plot_times, time_unit = results.collect_series(elmres)
    read_seconds = time.perf_counter() - started

    started = time.perf_counter()
    case = {
        "id": "REF", "name": "Referenz", "kind": "reference",
        "description": "", "status": payload.CONVERGED, "error_code": 0,
        "message": "", "snapshot": None, "outages": [],
    }
    result = payload.scenario_result(case, series, labels, plot_times, time_unit)
    tables = payload.build_cases_payload(
        None, [result], "Benchmark", "SyntheticResult")
    payload_seconds = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "series": len(series),
        "read_seconds": read_seconds,
        "payload_seconds": payload_seconds,
        "peak_mib": peak / (1024 * 1024),
        "rows_total": sum(len(rows_) for rows_ in tables.values()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elements", type=int, default=1000,
                        help="Leitungen und Knoten je Kategorie")
    parser.add_argument("--rows", type=int, default=8760,
                        help="QDS-Zeitschritte")
    parser.add_argument("--cell-reads", action="store_true",
                        help="GetColumnValues abschalten und zellweise lesen")
    args = parser.parse_args()

    if args.rows > config.MAX_RESULT_ROWS:
        print("Hinweis: rows > MAX_RESULT_ROWS ({}), der Leser wird ablehnen."
              .format(config.MAX_RESULT_ROWS))
    stats = measure(args.elements, args.rows, not args.cell_reads)
    print("Elemente je Kategorie : {}".format(args.elements))
    print("Zeitschritte          : {}".format(args.rows))
    print("Zugriff               : {}".format(
        "zellweise" if args.cell_reads else "spaltenweise"))
    print("Ergebnisreihen        : {}".format(stats["series"]))
    print("Lesen                 : {:.2f} s".format(stats["read_seconds"]))
    print("Payload               : {:.2f} s".format(stats["payload_seconds"]))
    print("Tabellenzeilen        : {}".format(stats["rows_total"]))
    print("Spitzenspeicher       : {:.1f} MiB".format(stats["peak_mib"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
