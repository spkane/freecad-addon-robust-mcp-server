"""Tests for private scratch directories used by FreeCAD and the MCP server."""

import os
import subprocess
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
            "$acl = Get-Acl -LiteralPath $env:FREECAD_TEST_SCRATCH_DIRECTORY; "
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
