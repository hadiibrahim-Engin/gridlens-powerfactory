"""Tests fuer Paketidentitaet und Laufzeitpruefung der Runtime-Bestandteile."""

import hashlib
import shutil
import sys
from pathlib import Path

import pytest

DEPLOYMENT = Path(__file__).resolve().parents[2] / "powerfactory"
if str(DEPLOYMENT) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT))

from gridlens_pf import config, manifest


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def runtime_copy(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir()
    shutil.copy2(DEPLOYMENT / "gridlens_report.py", root / "gridlens_report.py")
    shutil.copy2(DEPLOYMENT / "MASTER_GRIDLENS.mrt", root / "MASTER_GRIDLENS.mrt")
    shutil.copytree(DEPLOYMENT / "gridlens_pf", root / "gridlens_pf")
    return root


def test_manifest_covers_every_delivered_runtime_module():
    expected = {"gridlens_report.py"}
    expected |= {
        "gridlens_pf/" + path.name
        for path in sorted((DEPLOYMENT / "gridlens_pf").glob("*.py"))
        # A file cannot carry its own hash.
        if path.name != "manifest.py"
    }
    assert set(manifest.RUNTIME_HASHES) == expected


def test_manifest_hashes_match_the_repository_state():
    """A stale manifest would certify the wrong package on the target machine."""
    stale = [name for name, value in manifest.RUNTIME_HASHES.items()
             if digest(DEPLOYMENT / name) != value]
    assert stale == [], (
        "Manifest ist veraltet. Neu erzeugen mit: "
        "python3 powerfactory/tools/write_manifest.py")


def test_an_intact_package_reports_no_problem(runtime_copy):
    errors, warnings = manifest.verify_runtime_package(runtime_copy)
    assert errors == []
    assert warnings == []


def test_a_modified_runtime_module_is_a_hard_error(runtime_copy):
    target = runtime_copy / "gridlens_pf" / "payload.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# fremd\n",
                      encoding="utf-8")
    errors, _ = manifest.verify_runtime_package(runtime_copy)
    assert any("payload.py" in message for message in errors)


def test_a_missing_runtime_file_is_a_hard_error(runtime_copy):
    (runtime_copy / "gridlens_pf" / "results.py").unlink()
    errors, _ = manifest.verify_runtime_package(runtime_copy)
    assert any("results.py" in message for message in errors)


def test_a_template_from_another_release_is_a_hard_error(runtime_copy):
    mrt = runtime_copy / "MASTER_GRIDLENS.mrt"
    text = mrt.read_text(encoding="utf-8")
    current = "Template {}; data contract {}.".format(
        config.TEMPLATE_VERSION, config.DATA_CONTRACT_VERSION)
    assert current in text
    mrt.write_text(
        text.replace(current, "Template 0.9.0; data contract 0.9."),
        encoding="utf-8")
    errors, _ = manifest.verify_runtime_package(runtime_copy)
    assert any("MASTER_GRIDLENS.mrt" in message for message in errors)


def test_a_locally_tuned_config_is_only_a_warning(runtime_copy):
    """config.py documents project tuning, so it must not block a run."""
    target = runtime_copy / "gridlens_pf" / "config.py"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            'TIME_UNIT_FALLBACK = "h"', 'TIME_UNIT_FALLBACK = "min"'),
        encoding="utf-8")
    errors, warnings = manifest.verify_runtime_package(runtime_copy)
    assert errors == []
    assert any("config.py" in message for message in warnings)


def test_manifest_release_matches_the_publisher_version():
    assert manifest.RELEASE_VERSION == config.PUBLISHER_VERSION


def test_entry_script_puts_its_own_directory_first_on_sys_path(tmp_path):
    """GL-PR-013: a same-named module found earlier must never shadow us."""
    import subprocess
    decoy = tmp_path / "decoy"
    (decoy / "gridlens_pf").mkdir(parents=True)
    (decoy / "gridlens_pf" / "__init__.py").write_text(
        "raise AssertionError('decoy package was imported')\n",
        encoding="utf-8")
    script = (
        "import runpy, sys\n"
        "sys.path.insert(0, {decoy!r})\n"
        "sys.path.append({runtime!r})\n"
        "runpy.run_path({entry!r}, run_name='gridlens_report')\n"
        "import gridlens_pf\n"
        "print(gridlens_pf.__file__)\n"
    ).format(
        decoy=str(decoy),
        runtime=str(DEPLOYMENT),
        entry=str(DEPLOYMENT / "gridlens_report.py"),
    )
    done = subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert str(DEPLOYMENT) in done.stdout


def test_runtime_verification_refuses_a_mixed_package(runtime_copy):
    from gridlens_pf import entry
    target = runtime_copy / "gridlens_pf" / "runner.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# alt\n",
                      encoding="utf-8")
    with pytest.raises(RuntimeError, match="runner.py"):
        entry.verify_runtime(runtime_copy)


def test_runtime_verification_passes_an_intact_package(runtime_copy):
    from gridlens_pf import entry
    messages = []
    entry.verify_runtime(runtime_copy, log=messages.append)
    assert messages == []
