"""Safety and configuration checks for the manual Addon Manager helper."""

from __future__ import annotations

import json
import runpy
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from scripts import addon_manager_manual as helper

if TYPE_CHECKING:
    from pathlib import Path


def test_start_configures_isolated_profile_and_reuses_it(tmp_path: Path) -> None:
    """Restarts retain the profile, repository ref, and isolated FreeCAD paths."""
    profile = tmp_path / "profile"
    with (
        patch.object(helper, "_binary", return_value="freecad"),
        patch.object(helper.subprocess, "Popen") as popen,
    ):
        popen.return_value.pid = 12345
        assert helper.start(profile, "main") == 0
        args, kwargs = popen.call_args
        assert args[0][0] == "freecad"
        assert kwargs["env"]["FREECAD_USER_DATA"] == str(profile / "data")
        macro = (profile / "setup.FCMacro").read_text()
        assert f"{helper.REPOSITORY} main" in macro
        assert "is_relative_to(expected)" in macro
        sentinel = profile / "data" / "keep"
        sentinel.touch()
        with patch.object(helper, "_running", return_value=False):
            assert helper.start(profile, "main") == 0
        assert sentinel.exists()
        with pytest.raises(ValueError, match="Only main"):
            helper.start(profile, "other")
        assert sentinel.exists()


def test_cleanup_refuses_running_or_unrecognized_profile(tmp_path: Path) -> None:
    """Cleanup preserves unknown directories and a running FreeCAD profile."""
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    marker = profile / "state.json"
    marker.write_text(json.dumps({"marker": "wrong"}))
    with pytest.raises(ValueError, match="recognized"):
        helper.clean(profile)
    marker.write_text(json.dumps({"marker": helper.MARKER, "pid": 123}))
    with patch.object(helper, "_running", return_value=True):
        with pytest.raises(ValueError, match="Close"):
            helper.clean(profile)
    assert profile.exists()
    with patch.object(helper, "_running", return_value=False):
        helper.clean(profile)
    assert not profile.exists()


def test_cleanup_refuses_symlink(tmp_path: Path) -> None:
    """A symlink cannot redirect cleanup to another directory."""
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "profile"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="safe"):
        helper.clean(link)
    assert target.exists()


def test_setup_macro_checks_profile_before_setting_repository(tmp_path: Path) -> None:
    """The FreeCAD macro refuses to modify preferences outside the test profile."""
    profile = tmp_path / "profile"
    with (
        patch.object(helper, "_binary", return_value="freecad"),
        patch.object(helper.subprocess, "Popen") as popen,
    ):
        popen.return_value.pid = 12345
        helper.start(profile, "main")
    freecad = MagicMock()
    freecad.getUserAppDataDir.return_value = str(tmp_path / "ordinary-profile")
    with patch.dict("sys.modules", {"FreeCAD": freecad}):
        with pytest.raises(RuntimeError, match="Unsafe Addon Manager test profile"):
            runpy.run_path(str(profile / "setup.FCMacro"))
        freecad.ParamGet.assert_not_called()
        freecad.getUserAppDataDir.return_value = str(profile / "data")
        runpy.run_path(str(profile / "setup.FCMacro"))
    freecad.ParamGet.return_value.SetString.assert_called_once_with(
        "CustomRepositories", f"{helper.REPOSITORY} main"
    )
    assert (profile / "setup-ready").is_file()


def test_start_refuses_live_pid_and_replaces_stale_pid(tmp_path: Path) -> None:
    """A live test process is preserved; a stopped process gets a new PID."""
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    marker = profile / "state.json"
    marker.write_text(json.dumps({"marker": helper.MARKER, "ref": "main", "pid": 123}))
    with (
        patch.object(helper, "_binary", return_value="freecad"),
        patch.object(helper.subprocess, "Popen") as popen,
    ):
        with patch.object(helper, "_running", return_value=True):
            with pytest.raises(ValueError, match="still running"):
                helper.start(profile, "main")
        popen.assert_not_called()
        assert json.loads(marker.read_text())["pid"] == 123
        popen.return_value.pid = 456
        with patch.object(helper, "_running", return_value=False):
            assert helper.start(profile, "main") == 0
        assert json.loads(marker.read_text())["pid"] == 456
        popen.return_value.wait.assert_not_called()
        assert popen.call_args.kwargs["stdin"] == helper.subprocess.DEVNULL
        assert popen.call_args.kwargs["stderr"] == helper.subprocess.STDOUT


@pytest.mark.skipif(helper.os.name == "nt", reason="Unix permissions")
def test_cleanup_rejects_shared_profile(tmp_path: Path) -> None:
    """A readable or writable profile owned by another account is not trusted."""
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    (profile / "state.json").write_text(json.dumps({"marker": helper.MARKER}))
    profile.chmod(0o755)
    with pytest.raises(ValueError, match="owned by you and private"):
        helper.clean(profile)
    assert profile.exists()


def test_cleanup_waits_for_start_to_record_process(tmp_path: Path) -> None:
    """Cleanup cannot remove the profile while startup is launching FreeCAD."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    profile = tmp_path / "profile"
    launching = Event()
    release = Event()
    process = MagicMock(pid=12345)

    def launch(*_args: object, **_kwargs: object) -> MagicMock:
        """Pause startup until the cleanup attempt has begun."""
        launching.set()
        if not release.wait(5):
            raise TimeoutError("Test did not release launch")
        return process

    with (
        patch.object(helper, "_binary", return_value="freecad"),
        patch.object(helper.subprocess, "Popen", side_effect=launch),
        patch.object(helper, "_running", return_value=True),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        starting = executor.submit(helper.start, profile, "main")
        assert launching.wait(5)
        cleaning = executor.submit(helper.clean, profile)
        try:
            with pytest.raises(TimeoutError):
                cleaning.result(timeout=0.2)
        finally:
            release.set()
        assert starting.result(timeout=5) == 0
        with pytest.raises(ValueError, match="Close"):
            cleaning.result(timeout=5)
    assert profile.exists()


@pytest.mark.parametrize("ref", ["", "with space", "two\nlines", "feature#example"])
def test_start_rejects_invalid_refs(tmp_path: Path, ref: str) -> None:
    """Malformed repository refs never launch FreeCAD."""
    with pytest.raises(ValueError, match="repository ref"):
        helper.start(tmp_path / "profile", ref)


def test_binary_honors_explicit_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """The configured FreeCAD executable takes precedence over discovery."""
    monkeypatch.setenv("FREECAD_ADDON_GUI_COMMAND", "/test/freecad")
    assert helper._binary() == "/test/freecad"


def test_clean_missing_profile_is_a_noop(tmp_path: Path) -> None:
    """Cleanup may be run repeatedly after the profile has been removed."""
    helper.clean(tmp_path / "missing")


def test_main_reports_configuration_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Invalid startup configuration is presented as an actionable CLI error."""
    monkeypatch.setattr(helper, "profile_path", lambda: tmp_path / "profile")
    monkeypatch.setattr(helper.sys, "argv", ["addon-test", "start", "bad ref"])
    assert helper.main() == 1
    assert "repository ref" in capsys.readouterr().err


def test_cleanup_preserves_marker_when_removal_fails(tmp_path: Path) -> None:
    """A failed partial cleanup remains recognizable and can be retried."""
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    marker = profile / "state.json"
    marker.write_text(json.dumps({"marker": helper.MARKER}))
    (profile / "addon").mkdir()
    with patch.object(helper.shutil, "rmtree", side_effect=PermissionError("blocked")):
        with pytest.raises(PermissionError):
            helper.clean(profile)
    assert marker.is_file()
    helper.clean(profile)
    assert not profile.exists()


def test_start_stops_process_if_pid_cannot_be_saved(tmp_path: Path) -> None:
    """A failed state write cannot leave an untracked FreeCAD process."""
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    marker = profile / "state.json"
    marker.write_text(json.dumps({"marker": helper.MARKER, "ref": "main"}))
    process = MagicMock(pid=12345)
    with (
        patch.object(helper, "_binary", return_value="freecad"),
        patch.object(helper.subprocess, "Popen", return_value=process),
        patch.object(helper.os, "replace", side_effect=PermissionError("blocked")),
        pytest.raises(PermissionError, match="blocked"),
    ):
        helper.start(profile, "main")
    process.terminate.assert_called_once_with()
    process.wait.assert_called_once_with()


@pytest.mark.skipif(helper.os.name != "nt", reason="Windows read-only behavior")
def test_cleanup_removes_windows_readonly_file(tmp_path: Path) -> None:
    """Cleanup handles read-only files installed by Git on Windows."""
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    (profile / "state.json").write_text(json.dumps({"marker": helper.MARKER}))
    addon = profile / "addon"
    addon.mkdir()
    entry = addon / "readonly"
    entry.write_text("content")
    entry.chmod(0o444)
    helper.clean(profile)
    assert not profile.exists()


def test_initial_state_failure_removes_new_profile(tmp_path: Path) -> None:
    """A failed first marker write does not leave an unrecognizable profile."""
    profile = tmp_path / "profile"
    with (
        patch.object(helper, "_binary", return_value="freecad"),
        patch.object(helper.os, "replace", side_effect=PermissionError("blocked")),
        pytest.raises(PermissionError, match="blocked"),
    ):
        helper.start(profile, "main")
    assert not profile.exists()


def test_failed_pid_write_preserves_previous_marker(tmp_path: Path) -> None:
    """An interrupted replacement leaves the prior marker intact."""
    profile = tmp_path / "profile"
    profile.mkdir(mode=0o700)
    previous = {"marker": helper.MARKER, "ref": "main"}
    (profile / "state.json").write_text(json.dumps(previous))
    with (
        patch.object(helper, "_binary", return_value="freecad"),
        patch.object(helper.subprocess, "Popen", return_value=MagicMock(pid=12345)),
        patch.object(helper.os, "replace", side_effect=PermissionError("blocked")),
        pytest.raises(PermissionError),
    ):
        helper.start(profile, "main")
    assert json.loads((profile / "state.json").read_text()) == previous


@pytest.mark.parametrize("legacy", [True, False])
def test_readonly_callback_supports_both_shutil_formats(
    tmp_path: Path, legacy: bool
) -> None:
    """Both onerror and onexc remove a Windows read-only file."""
    target = tmp_path / "file"
    target.touch()
    failure = PermissionError("read only")
    error = (PermissionError, failure, None) if legacy else failure
    retry = MagicMock()
    with patch.object(helper, "os", wraps=helper.os) as platform:
        platform.name = "nt"
        helper._remove_readonly(retry, str(target), error)
    retry.assert_called_once_with(str(target))


@pytest.mark.parametrize("legacy", [True, False])
def test_readonly_callback_propagates_other_failures(legacy: bool) -> None:
    """Unexpected errors are never hidden by the removal callback."""
    failure = OSError("unexpected")
    error = (OSError, failure, None) if legacy else failure
    with pytest.raises(OSError, match="unexpected"):
        helper._remove_readonly(MagicMock(), "unused", error)


def test_running_detects_current_and_invalid_pid() -> None:
    """PID checks identify the current process and reject zero on every platform."""
    assert helper._running(helper.os.getpid())
    with pytest.raises(ValueError, match="Invalid"):
        helper._running(0)


@pytest.mark.skipif(helper.os.name == "nt", reason="Windows may retain process handles")
def test_running_detects_reaped_process() -> None:
    """Unix PID checks recognize a subprocess after it has been reaped."""
    process = helper.subprocess.Popen([helper.sys.executable, "-c", "pass"])
    process.wait(timeout=10)
    assert not helper._running(process.pid)
