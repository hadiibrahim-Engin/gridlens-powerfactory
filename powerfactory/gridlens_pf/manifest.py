"""Paketidentitaet der GridLens-Laufzeit und Pruefung auf dem Zielrechner.

Runner, Report-Erweiterung und Vorlage werden von Hand kopiert. Ohne Pruefung
koennen dabei Bestandteile verschiedener Staende zusammenkommen: eine alte
`gridlens_pf/` mit einer neuen Einstiegsdatei oder eine Vorlage aus einem
anderen Release. Das Ergebnis waere ein Bericht, der sich korrekt nennt, aber
Tabellen eines anderen Datenvertrags fuellt.

Dieses Modul hat keine PowerFactory-Abhaengigkeit. Die Hashwerte erzeugt
`powerfactory/tools/write_manifest.py` neu; `test_pf_manifest.py` haelt sie
gegen den Repositoriumsstand aktuell.
"""

import hashlib
import os

from .config import DATA_CONTRACT_VERSION, PUBLISHER_VERSION, TEMPLATE_VERSION

RELEASE_VERSION = PUBLISHER_VERSION

TEMPLATE_FILE = "MASTER_GRIDLENS.mrt"

# Eine lokal angepasste config.py ist ein dokumentierter Betriebsfall
# (Zeiteinheit, Ergebnisvariablen, Grenzwerte). Sie wird gemeldet, blockiert
# den Lauf aber nicht.
TUNABLE_FILES = ("gridlens_pf/config.py",)

# manifest.py selbst kann seinen eigenen Hash nicht enthalten.
RUNTIME_HASHES = {
    "gridlens_report.py":
        "e30831ab3db2d68426738d460d0a6e480d0bb02577c8766e67c80fed657376fe",
    "gridlens_pf/__init__.py":
        "af588efcc93407fc5e18ae763b3ce77ed0681eefeda8fba9338b37b53cfd8f81",
    "gridlens_pf/config.py":
        "6e48b4bcc856814610b4fa03626f09855f8ae833c7bb68ea7c5d2186cb270836",
    "gridlens_pf/discovery.py":
        "fb31998afca169fc2a49d1936274dbd2c50102ae4a3df1b1aaa0596850642a48",
    "gridlens_pf/entry.py":
        "e3523fc68d8ea278d709d6099daaa83d30126524724cfea9abc6f07a6b89ee6d",
    "gridlens_pf/payload.py":
        "38b2ff11e63f86d5dbe09a247f0c4b1524c6c70eebc99303a8dbaa3fcf18ed82",
    "gridlens_pf/pfutil.py":
        "70ca1b556f51df29a98fc52047de8447dbeeb92fc553583dc2ec55773cdacfe6",
    "gridlens_pf/publish.py":
        "3a2cf27b4192b686f31f4697d8a756ff502488068825d2837908bd4bb54b0551",
    "gridlens_pf/results.py":
        "50aeb34d977bb83638005ec18a164dad474737ab32c8a46a1e362baaf5ba640c",
    "gridlens_pf/runner.py":
        "40d585e3b3a6100c54303101d11d5f4fcc374c38cf0eb5fb81d6eb3f03ee84a6",
    "gridlens_pf/tables.py":
        "dbe8b301d7ff43fca8806f5f30e4a4a70771f4c7b99af08c2f3d94346d18bc23",
    "gridlens_pf/timeaxis.py":
        "62a4015ed37e56ebfffb98de06c76105c7f76fb1ffcf9d1ffdaee2b82c5dd45d",
}


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


def file_digest(path):
    return hashlib.sha256(_read(path)).hexdigest()


def _template_problem(root):
    path = os.path.join(root, TEMPLATE_FILE)
    if not os.path.isfile(path):
        return "{} fehlt im Laufzeitpaket.".format(TEMPLATE_FILE)
    expected = "Template {}; data contract {}.".format(
        TEMPLATE_VERSION, DATA_CONTRACT_VERSION)
    try:
        text = _read(path).decode("utf-8", "replace")
    except OSError as exc:
        return "{} ist nicht lesbar: {}".format(TEMPLATE_FILE, exc)
    if expected not in text:
        return (
            "{} gehoert nicht zu diesem Release; erwartet wird '{}'. "
            "Vorlage und Laufzeit gemeinsam neu kopieren.".format(
                TEMPLATE_FILE, expected)
        )
    return None


def verify_runtime_package(root):
    """Pruefe ein kopiertes Laufzeitpaket und liefere (Fehler, Warnungen).

    Fehler bedeuten: nicht ausfuehren. Warnungen bedeuten: bewusst angepasst.
    """
    errors = []
    warnings = []
    for name in sorted(RUNTIME_HASHES):
        path = os.path.join(root, *name.split("/"))
        if not os.path.isfile(path):
            errors.append("{} fehlt im Laufzeitpaket.".format(name))
            continue
        try:
            actual = file_digest(path)
        except OSError as exc:
            errors.append("{} ist nicht lesbar: {}".format(name, exc))
            continue
        if actual == RUNTIME_HASHES[name]:
            continue
        message = "{} weicht vom Release {} ab.".format(name, RELEASE_VERSION)
        if name in TUNABLE_FILES:
            warnings.append(message + " Projektanpassung wird angenommen.")
        else:
            errors.append(
                message + " Laufzeitpaket vollstaendig neu kopieren.")
    problem = _template_problem(root)
    if problem:
        errors.append(problem)
    return errors, warnings
