"""Erzeuge die Hashwerte in gridlens_pf/manifest.py neu.

Aufruf aus dem Repositoriumswurzelverzeichnis:

    python3 powerfactory/tools/write_manifest.py

Nach jeder Aenderung an der Laufzeit ausfuehren. `test_pf_manifest.py`
schlaegt fehl, solange das Manifest den Repositoriumsstand nicht abbildet.
Dieses Werkzeug wird nicht mit ausgeliefert.
"""

import hashlib
import re
import sys
from pathlib import Path

DEPLOYMENT = Path(__file__).resolve().parents[1]
MANIFEST = DEPLOYMENT / "gridlens_pf" / "manifest.py"
BLOCK = re.compile(r"RUNTIME_HASHES = \{.*?\n\}\n", re.DOTALL)


def runtime_files():
    yield "gridlens_report.py"
    for path in sorted((DEPLOYMENT / "gridlens_pf").glob("*.py")):
        if path.name == "manifest.py":
            continue
        yield "gridlens_pf/" + path.name


def main():
    lines = ["RUNTIME_HASHES = {"]
    for name in runtime_files():
        digest = hashlib.sha256((DEPLOYMENT / name).read_bytes()).hexdigest()
        lines.append('    "{}":\n        "{}",'.format(name, digest))
    lines.append("}\n")
    block = "\n".join(lines)

    source = MANIFEST.read_text(encoding="utf-8")
    if not BLOCK.search(source):
        print("RUNTIME_HASHES block not found in manifest.py", file=sys.stderr)
        return 1
    MANIFEST.write_text(BLOCK.sub(block, source, count=1), encoding="utf-8")
    print("manifest.py updated ({} files)".format(len(list(runtime_files()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
