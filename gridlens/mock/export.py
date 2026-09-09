"""Export an optional development-only mock report payload as JSON.

The active-model PowerFactory publisher does not read this file. This utility is
kept only for offline development of the reusable processing library.

    python -m gridlens.mock.export
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gridlens.mock.mock_data import FIXED_GENERATION_DATE, build_dataset
from gridlens.processing import run
from gridlens.report_model import build_report_payload

DEFAULT_OUTPUT = Path.cwd() / "gridlens-mock-payload.json"


def export(output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Build the mock payload and write it as pretty-printed JSON."""
    payload = build_report_payload(
        run(build_dataset()), generation_date=FIXED_GENERATION_DATE
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        # sort_keys keeps the file stable so it does not churn in version control.
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    path = export(arguments.output)
    payload = json.loads(path.read_text(encoding="utf-8"))

    print(f"Mock payload written: {path}")
    for name in sorted(payload):
        print(f"  {name:34s} {len(payload[name]):5d} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
