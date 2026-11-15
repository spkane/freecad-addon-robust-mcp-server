"""Tests for private scratch directories used by FreeCAD and the MCP server."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from freecad_mcp.bridge import private_scratch
from freecad_mcp.bridge.private_scratch import private_scratch_directory


def test_workbench_and_server_helpers_are_identical() -> None:
    """Both distributions must execute the same scratch-directory policy."""
    root = Path(__file__).parents[2]
    server = root / "src/freecad_mcp/bridge/private_scratch.py"
    workbench = root / "freecad/RobustMCPBridge/freecad_mcp_bridge/private_scratch.py"
    assert server.read_bytes() == workbench.read_bytes()


@pytest.mark.parametrize("prefix", ["", ".", "..", "nested/path"])
def test_scratch_rejects_non_component_prefix(prefix: str) -> None:
    """The scratch creator does not interpret a prefix as a path."""
    with pytest.raises(ValueError, match="single path component"):
        with private_scratch_directory(prefix):
            pass


def test_windows_refuses_filesystem_without_persistent_acls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Windows filesystem without ACL support must not receive scratch data."""
    kernel = MagicMock()
    advapi = MagicMock()
    kernel.GetVolumePathNameW.return_value = True
    kernel.GetVolumeInformationW.return_value = True
    monkeypatch.setattr(
        private_scratch.ctypes,
        "WinDLL",
        lambda name, **_kwargs: kernel if name == "kernel32" else advapi,
        raising=False,
    )
    monkeypatch.setattr(
        private_scratch.ctypes, "get_last_error", lambda: 0, raising=False
    )
    monkeypatch.setattr(private_scratch.ctypes, "WinError", OSError, raising=False)
    with pytest.raises(OSError, match="persistent ACLs"):
        private_scratch._windows_private_directory("C:\\home", "scratch-")
    kernel.CreateDirectoryW.assert_not_called()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ACL verification")
def test_macos_scratch_removes_inherited_acl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broad inheritable parent ACL is removed before artifacts are written."""
    result = subprocess.run(  # noqa: S603
        [
            "/bin/chmod",
            "+a",
            "everyone allow list,search,file_inherit,directory_inherit",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    original_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda path: str(tmp_path) if path == "~" else original_expanduser(path),
    )
    with private_scratch_directory("scratch-") as path:
        listing = subprocess.run(  # noqa: S603
            ["/bin/ls", "-lde", path], capture_output=True, text=True, check=True
        ).stdout
        assert "inherited" not in listing
        assert len(listing.splitlines()) == 1
        (Path(path) / "artifact").write_text("private")
    assert not Path(path).exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ACL verification")
def test_macos_rechecks_permissions_after_acl_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A permission change during ACL removal prevents use of the directory."""
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    real_fstat = os.fstat
    calls = 0

    def changed_fstat(fd: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 2:
            os.fchmod(fd, 0o755)
        return real_fstat(fd)

    monkeypatch.setattr(os, "fstat", changed_fstat)
    with pytest.raises(OSError, match="permissions changed"):
        private_scratch._darwin_clear_inherited_acl(str(scratch))


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ACL verification")
def test_macos_acl_failure_prevents_artifact_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ACL failure never yields a directory and cleans up the empty one."""
    original_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda path: str(tmp_path) if path == "~" else original_expanduser(path),
    )

    def fail(_path: str) -> None:
        raise OSError("ACL failure")

    monkeypatch.setattr(private_scratch, "_darwin_clear_inherited_acl", fail)
    with pytest.raises(OSError, match="ACL failure"):
        with private_scratch_directory("scratch-"):
            pytest.fail("Directory was exposed after an ACL failure")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL verification")
def test_windows_scratch_directory_has_protected_acl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real Windows ACL excludes inherited broad-access principals."""
    original_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path,
        "expanduser",
        lambda path: str(tmp_path) if path == "~" else original_expanduser(path),
    )
    with private_scratch_directory("scratch-") as path:
        (Path(path) / "test.txt").write_text("private", encoding="utf-8")
        env = os.environ.copy()
        env["FREECAD_TEST_SCRATCH_DIRECTORY"] = path
        script = (
            "$ErrorActionPreference = 'Stop'; "
            "$acl = [System.IO.Directory]::GetAccessControl("
            "$env:FREECAD_TEST_SCRATCH_DIRECTORY); "
            "Write-Output ('Protected=' + $acl.AreAccessRulesProtected); "
            "Write-Output ('SDDL=' + $acl.Sddl); "
            "$acl.GetAccessRules($true,$true,"
            "[System.Security.Principal.SecurityIdentifier]) | "
            "ForEach-Object { $_.IdentityReference.Value }"
        )
        result = subprocess.run(  # noqa: S603
            [
                str(
                    Path(os.environ["SYSTEMROOT"])
                    / "System32/WindowsPowerShell/v1.0/powershell.exe"
                ),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        lines = result.stdout.splitlines()
        assert "Protected=True" in lines, (result.stdout, result.stderr)
        sids = {line for line in lines if line.startswith("S-")}
        assert sids <= {"S-1-5-18", "S-1-5-32-544", "S-1-3-4"}, result.stdout
        assert "S-1-3-4" in sids, result.stdout
    assert not Path(path).exists()
