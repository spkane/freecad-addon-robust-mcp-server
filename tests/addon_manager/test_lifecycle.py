"""Real Addon Manager lifecycle checks for a disposable FreeCAD GUI profile."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parents[2]
MACRO = Path(__file__).with_name("lifecycle.FCMacro")
REPOSITORY = "https://github.com/spkane/freecad-addon-robust-mcp-server.git"
BASELINE = "robust-mcp-workbench-v0.7.0-rc.4"


@pytest.fixture
def isolated_windows_credential() -> Iterator[dict]:
    """Protect existing Windows credentials and remove only the one we created."""
    state: dict = {}
    if os.name != "nt":
        yield state
        return
    if os.environ.get("FREECAD_ADDON_DISPOSABLE_WINDOWS") != "1":
        pytest.fail("Windows requires an explicitly disposable user account")
    from freecad_mcp.bridge.credential_store import read_credential

    try:
        read_credential()
    except FileNotFoundError:
        pass
    else:
        pytest.fail("Refusing to replace an existing Windows bridge pairing")
    try:
        yield state
    finally:
        if "credential" in state:
            import ctypes
            from ctypes import wintypes

            from freecad_mcp.bridge import windows_credential_store

            with windows_credential_store._pairing_lock():
                if read_credential() == state["credential"]:
                    api = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined]
                    api.CredDeleteW.argtypes = [
                        wintypes.LPCWSTR,
                        wintypes.DWORD,
                        wintypes.DWORD,
                    ]
                    api.CredDeleteW.restype = wintypes.BOOL
                    if not api.CredDeleteW(windows_credential_store._TARGET, 1, 0):
                        raise OSError("Could not remove disposable Windows pairing")


def _git(cwd: Path, *args: str) -> None:
    """Run Git in the disposable fixture repository."""
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _manifest_version(path: Path) -> str:
    """Read the declared version from an addon manifest."""
    root = ET.parse(path).getroot()  # noqa: S314 - test fixture from this checkout
    version = root.find("{*}version")
    assert version is not None and version.text
    return version.text


def _wait_for_owned_process(process: subprocess.Popen) -> None:
    """Wait for our FreeCAD process, escalating if it does not exit."""
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def test_owned_process_is_killed_and_reaped_after_timeouts() -> None:
    """A process that ignores termination cannot leak into subsequent tests."""
    process = MagicMock()
    process.wait.side_effect = [
        subprocess.TimeoutExpired("freecad", 30),
        subprocess.TimeoutExpired("freecad", 10),
        0,
    ]
    _wait_for_owned_process(process)
    process.terminate.assert_called_once_with()
    process.kill.assert_called_once_with()
    assert process.wait.call_args_list == [
        call(timeout=30),
        call(timeout=10),
        call(timeout=10),
    ]


@contextmanager
def _cleanup_owned_process(process: subprocess.Popen, stop: Path) -> Iterator[None]:
    """Signal and reap the test-owned process even when an assertion fails."""
    try:
        yield
    finally:
        stop.touch()
        _wait_for_owned_process(process)


def test_owned_process_is_reaped_after_test_failure(tmp_path: Path) -> None:
    """Readiness or ping failures still stop and reap the owned process."""
    process = MagicMock()
    stop = tmp_path / "stop"
    with pytest.raises(AssertionError), _cleanup_owned_process(process, stop):
        raise AssertionError("readiness failed")
    assert stop.exists()
    process.wait.assert_called_once_with(timeout=30)


@pytest.mark.skipif(
    os.environ.get("FREECAD_ADDON_LIFECYCLE_DISPOSABLE") != "1",
    reason="requires an explicitly disposable GUI environment",
)
def test_addon_manager_install_upgrade_disable_and_uninstall(
    tmp_path: Path, isolated_windows_credential: dict
) -> None:
    """Use FreeCAD's own installer and addon objects across GUI restarts."""
    binary = os.environ.get("FREECAD_ADDON_GUI_COMMAND") or shutil.which("freecad")
    assert binary, "freecad GUI executable is required"
    fixture = tmp_path / "repository"
    _git(
        tmp_path,
        "clone",
        "--depth",
        "1",
        "--branch",
        BASELINE,
        REPOSITORY,
        str(fixture),
    )
    _git(fixture, "checkout", "-b", "test-lifecycle")
    old_version = _manifest_version(fixture / "package.xml")
    expected_version = _manifest_version(ROOT / "package.xml")
    assert old_version != expected_version, "upgrade requires two distinct versions"

    home = tmp_path / "profile"
    home.mkdir()
    result = tmp_path / "result.json"
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "FREECAD_USER_HOME": str(home),
        "FREECAD_USER_DATA": str(home),
        "FREECAD_USER_TEMP": str(home / "temp"),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "ADDON_TEST_ROOT": str(home),
        "ADDON_TEST_REPO": fixture.as_uri(),
        "ADDON_TEST_METADATA": str(ROOT / "package.xml"),
        "ADDON_TEST_RESULT": str(result),
    }
    (home / "temp").mkdir()
    if os.name == "nt":
        # Avoid relying on an interactive desktop on hosted Windows runners.
        env["QT_QPA_PLATFORM"] = "offscreen"

    def phase(name: str) -> dict:
        """Run one lifecycle phase in a fresh FreeCAD process."""
        result.unlink(missing_ok=True)
        try:
            completed = subprocess.run(  # noqa: S603
                [binary, "--user-cfg", str(home / "user.cfg"), str(MACRO)],
                env={**env, "ADDON_TEST_PHASE": name},
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            details = (
                result.read_text(encoding="utf-8") if result.exists() else "no result"
            )
            pytest.fail(
                f"FreeCAD {name} timed out: {details}; stdout={error.stdout!r}; stderr={error.stderr!r}"
            )
        output = completed.stdout + completed.stderr
        assert completed.returncode == 0, output
        assert result.is_file(), output
        data = json.loads(result.read_text(encoding="utf-8"))
        assert data["ok"], data.get("error", output)
        return data

    first = phase("install")
    installed = Path(first["data"]) / "Mod" / "freecad-addon-robust-mcp-server"
    assert (
        first["installed"]
        and _manifest_version(installed / "package.xml") == old_version
    )
    sentinel = installed.parent / "UnrelatedAddon" / "keep.txt"
    sentinel.parent.mkdir()
    sentinel.write_text("preserve", encoding="utf-8")
    assert phase("disable")["disabled"]
    assert not phase("enable")["disabled"]
    assert phase("verify")["present"]

    pairing = subprocess.run(
        [sys.executable, "-m", "freecad_mcp.server", "--pair-bridge"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert pairing.returncode == 0, pairing.stderr
    if os.name == "nt":
        from freecad_mcp.bridge.credential_store import read_credential

        isolated_windows_credential["credential"] = read_credential()

    def check_paired_bridge() -> None:
        """Verify the installed bridge accepts an authenticated ping."""
        stop = tmp_path / "stop"
        stop.unlink(missing_ok=True)
        result.unlink(missing_ok=True)
        log = tmp_path / "paired.log"
        with log.open("w+", encoding="utf-8") as output:
            process = subprocess.Popen(  # noqa: S603
                [binary, "--user-cfg", str(home / "user.cfg"), str(MACRO)],
                env={**env, "ADDON_TEST_PHASE": "paired", "ADDON_TEST_STOP": str(stop)},
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            with _cleanup_owned_process(process, stop):
                deadline = time.monotonic() + 90
                while (
                    not result.exists()
                    and process.poll() is None
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.1)
                output.flush()
                assert result.exists(), log.read_text(encoding="utf-8")
                ready = json.loads(result.read_text(encoding="utf-8"))
                assert ready["ok"], ready.get("error")
                ping = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "from tests.integration.auth_support import integration_proxy; assert integration_proxy().ping()['pong']",
                    ],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                assert ping.returncode == 0, ping.stdout + ping.stderr
            assert process.returncode == 0, log.read_text(encoding="utf-8")

    check_paired_bridge()

    # Update the same local branch with the actual checkout's workbench sources.
    shutil.rmtree(fixture / "freecad")
    shutil.copytree(
        ROOT / "freecad",
        fixture / "freecad",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    shutil.copy2(ROOT / "package.xml", fixture / "package.xml")
    _git(
        fixture,
        "-c",
        "user.name=Addon Test",
        "-c",
        "user.email=addon-test@example.invalid",
        "add",
        "freecad",
        "package.xml",
    )
    _git(
        fixture,
        "-c",
        "user.name=Addon Test",
        "-c",
        "user.email=addon-test@example.invalid",
        "commit",
        "-m",
        "Update test candidate",
    )
    assert phase("upgrade")["installed"]
    assert _manifest_version(installed / "package.xml") == expected_version
    assert phase("verify")["present"]
    check_paired_bridge()
    assert phase("uninstall")["removed"]
    assert sentinel.read_text(encoding="utf-8") == "preserve"
    if os.name != "nt":
        assert (home / ".freecad-robust-mcp").is_dir()
    phase("absent")
    assert phase("reinstall")["installed"]
    assert phase("verify")["present"]
    check_paired_bridge()
