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
        with patch.object(helper, "_running", return_value=False):
            assert helper.start(profile, "other") == 0
        assert f"{helper.REPOSITORY} other" in (profile / "setup.FCMacro").read_text()
        assert sentinel.exists()


def test_cleanup_refuses_running_or_unrecognized_profile(tmp_path: Path) -> None:
    """Cleanup preserves unknown directories and a running FreeCAD profile."""
    profile = tmp_path / "profile"
    profile.mkdir()
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
    profile.mkdir()
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
