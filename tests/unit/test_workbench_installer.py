"""Verify profile selection and safe installation into disposable directories."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.install_workbench import (
    default_mod_directory,
    install_workbench,
    select_mod_directory,
)

ROOT = Path(__file__).resolve().parents[2]


def test_selects_highest_numeric_version(tmp_path: Path) -> None:
    """Profile versions compare numerically and unrelated names are ignored."""
    for name in ("v1-9", "v1-10", "v2-0", "v99-test"):
        (tmp_path / name).mkdir()
    assert select_mod_directory(tmp_path) == tmp_path / "v2-0" / "Mod"


def test_unversioned_profile_is_fallback(tmp_path: Path) -> None:
    """Use the legacy profile when no versioned profile exists."""
    assert select_mod_directory(tmp_path) == tmp_path / "Mod"


def test_windows_profile_uses_appdata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows selection honors APPDATA and versioned FreeCAD profiles."""
    (tmp_path / "FreeCAD" / "v1-1").mkdir(parents=True)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_mod_directory() == tmp_path / "FreeCAD" / "v1-1" / "Mod"


def test_existing_installation_is_replaced(tmp_path: Path) -> None:
    """A successful upgrade replaces the old package without leftover backups."""
    mod = tmp_path / "Mod"
    target = mod / "RobustMCPBridge"
    target.mkdir(parents=True)
    (target / "old-version").write_text("old", encoding="utf-8")
    assert install_workbench(mod) == target
    assert (target / "package.xml").is_file()
    assert not (target / "old-version").exists()
    assert list(mod.iterdir()) == [target]


def test_installs_package_using_explicit_mod_directory(tmp_path: Path) -> None:
    """The portable command installs the real package into the selected profile."""
    mod = tmp_path / "selected profile" / "Mod"
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [
            sys.executable,
            str(ROOT / "scripts/install_workbench.py"),
            "--mod-dir",
            str(mod),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    target = mod / "RobustMCPBridge"
    assert (target / "package.xml").is_file()
    assert (target / "freecad/RobustMCPBridge/__init__.py").is_file()
    assert (target / "LICENSE-CODE").is_file()
    assert str(target) in result.stdout


def test_existing_installation_is_restored_if_replacement_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do not lose a previously installed workbench if the final rename fails."""
    mod = tmp_path / "Mod"
    target = mod / "RobustMCPBridge"
    target.mkdir(parents=True)
    (target / "original").write_text("preserve", encoding="utf-8")
    rename = Path.rename

    def fail_new_package(path: Path, destination: Path) -> Path:
        if path.name == "new":
            raise OSError("replacement failed")
        return rename(path, destination)

    monkeypatch.setattr(Path, "rename", fail_new_package)
    with pytest.raises(OSError, match="replacement failed"):
        install_workbench(mod)
    assert (target / "original").read_text(encoding="utf-8") == "preserve"
    assert list(mod.iterdir()) == [target]


def test_rejects_symlink_installation_target(tmp_path: Path) -> None:
    """Never replace an installation target that is a symlink."""
    mod = tmp_path / "Mod"
    mod.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    try:
        (mod / "RobustMCPBridge").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks unavailable on this host")
    with pytest.raises(ValueError, match="not a regular directory"):
        install_workbench(mod)


def test_successful_install_removes_only_legacy_workbenches(tmp_path: Path) -> None:
    """Clean legacy layouts after installing while retaining other addons."""
    mod = tmp_path / "Mod"
    old = mod / "FreecadRobustMCPBridge"
    misplaced = mod / "freecad" / "RobustMCPBridge"
    other = mod / "freecad" / "OtherWorkbench"
    for path in (old, misplaced, other):
        path.mkdir(parents=True)
        (path / "marker").write_text("keep", encoding="utf-8")
    install_workbench(mod)
    assert not old.exists()
    assert not misplaced.exists()
    assert (other / "marker").is_file()


def test_failed_install_preserves_legacy_workbench(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed package build does not remove a previously usable legacy addon."""
    legacy = tmp_path / "Mod" / "FreecadRobustMCPBridge"
    legacy.mkdir(parents=True)

    def fail(_destination: Path) -> None:
        raise OSError("build failed")

    monkeypatch.setattr("scripts.install_workbench.prepare_package", fail)
    with pytest.raises(OSError, match="build failed"):
        install_workbench(legacy.parent)
    assert legacy.is_dir()


def test_install_does_not_follow_legacy_namespace_symlink(tmp_path: Path) -> None:
    """A symlinked namespace must not cause deletion outside the selected Mod."""
    mod = tmp_path / "Mod"
    mod.mkdir()
    external = tmp_path / "external"
    (external / "RobustMCPBridge").mkdir(parents=True)
    try:
        (mod / "freecad").symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks unavailable on this host")
    install_workbench(mod)
    assert (external / "RobustMCPBridge").is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions require Windows")
@pytest.mark.parametrize(
    "link_name", ["freecad", "FreecadRobustMCPBridge", "RobustMCPBridge"]
)
def test_windows_junctions_preserve_external_directories(
    tmp_path: Path, link_name: str
) -> None:
    """Junctions cannot redirect legacy cleanup or replacement outside Mod."""
    mod = tmp_path / "Mod"
    mod.mkdir()
    external = tmp_path / "external"
    (external / "RobustMCPBridge").mkdir(parents=True)
    marker = external / "RobustMCPBridge" / "marker"
    marker.write_text("preserve", encoding="utf-8")
    cmd = shutil.which("cmd")
    assert cmd is not None
    result = subprocess.run(  # noqa: S603 - fixed cmd and temporary directories
        [cmd, "/c", "mklink", "/J", str(mod / link_name), str(external)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    if link_name == "RobustMCPBridge":
        with pytest.raises(ValueError, match="not a regular directory"):
            install_workbench(mod)
    else:
        install_workbench(mod)
    assert marker.read_text(encoding="utf-8") == "preserve"
