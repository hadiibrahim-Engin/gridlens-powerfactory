"""Tests gegen konkurrierende Versionswahrheiten im Repositorium."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

import gridlens
from gridlens_pf import config


def pyproject_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml declares no version"
    return match.group(1)


def test_the_distribution_version_is_the_publisher_version():
    """One repository, one release number for the shipped product."""
    assert pyproject_version() == config.PUBLISHER_VERSION


def test_the_template_and_the_runtime_name_the_same_release():
    text = (DEPLOYMENT / "MASTER_GRIDLENS.mrt").read_text(encoding="utf-8")
    assert "Template {}; data contract {}.".format(
        config.TEMPLATE_VERSION, config.DATA_CONTRACT_VERSION) in text


def test_the_legacy_library_is_marked_as_a_separate_lineage():
    """gridlens/ carries its own frozen contract and must say so.

    It is not imported by the PowerFactory runtime. Leaving it looking like
    the current contract is what produced competing version truths.
    """
    assert gridlens.LEGACY_DATA_CONTRACT_VERSION == gridlens.DATA_CONTRACT_VERSION
    assert gridlens.DATA_CONTRACT_VERSION != config.DATA_CONTRACT_VERSION
    assert gridlens.IS_LEGACY is True


def test_development_dependencies_are_pinned():
    """An unpinned test toolchain cannot reproduce a release verification."""
    lock = ROOT / "requirements-dev.txt"
    assert lock.is_file(), "requirements-dev.txt is missing"
    entries = [line.strip() for line in lock.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.startswith("#")]
    assert entries
    for entry in entries:
        assert "==" in entry, entry


def test_the_production_runtime_never_imports_the_legacy_library():
    for path in [DEPLOYMENT / "gridlens_report.py"] + sorted(
            (DEPLOYMENT / "gridlens_pf").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+gridlens\b", source,
                             re.MULTILINE), path
