"""Tests for private scratch directories used by FreeCAD and the MCP server."""

import ctypes
import errno
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
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


@pytest.mark.parametrize(
    ("valid", "entry_result", "entry_errno", "expected"),
    [
        (0, -1, errno.EINVAL, None),
        (0, 0, 0, "still has an access control list"),
        (0, -1, errno.EIO, "Input/output error"),
        (-1, -1, errno.EIO, "Input/output error"),
    ],
)
def test_darwin_acl_verification_handles_empty_and_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    valid: int,
    entry_result: int,
    entry_errno: int,
    expected: str | None,
) -> None:
    """A valid empty ACL is accepted; entries and unexpected errors fail closed."""
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    libc = MagicMock()
    libc.acl_init.return_value = 1
    libc.acl_set_fd_np.return_value = 0
    libc.acl_get_fd_np.return_value = 2

    def validate(_acl: object) -> int:
        ctypes.set_errno(errno.EIO if valid else 0)
        return valid

    def get_entry(_acl: object, _index: int, _entry: object) -> int:
        ctypes.set_errno(entry_errno)
        return entry_result

    libc.acl_valid.side_effect = validate
    libc.acl_get_entry.side_effect = get_entry
    monkeypatch.setattr(private_scratch.ctypes, "CDLL", lambda *_a, **_kw: libc)
    if expected is None:
        private_scratch._darwin_clear_inherited_acl(str(scratch))
    else:
        with pytest.raises(OSError, match=expected):
            private_scratch._darwin_clear_inherited_acl(str(scratch))
    assert [call.args[0] for call in libc.acl_free.call_args_list] == [1, 2]


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ACL verification")
@pytest.mark.parametrize("with_entry", [False, True])
def test_darwin_real_acl_entry_enumeration(with_entry: bool) -> None:
    """Exercise Darwin's actual empty and nonempty ACL iterator semantics."""
    libc = ctypes.CDLL(None, use_errno=True)
    libc.acl_init.argtypes = [ctypes.c_int]
    libc.acl_init.restype = ctypes.c_void_p
    libc.acl_create_entry.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    libc.acl_create_entry.restype = ctypes.c_int
    libc.acl_valid.argtypes = [ctypes.c_void_p]
    libc.acl_valid.restype = ctypes.c_int
    libc.acl_get_entry.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    libc.acl_get_entry.restype = ctypes.c_int
    libc.acl_free.argtypes = [ctypes.c_void_p]
    libc.acl_free.restype = ctypes.c_int
    acl = ctypes.c_void_p(libc.acl_init(1))
    assert acl.value
    if with_entry:
        entry = ctypes.c_void_p()
        assert libc.acl_create_entry(ctypes.byref(acl), ctypes.byref(entry)) == 0
    get_acl = SimpleNamespace(
        acl_get_fd_np=lambda _fd, _type: acl.value,
        acl_valid=libc.acl_valid,
        acl_get_entry=libc.acl_get_entry,
        acl_free=libc.acl_free,
    )
    if with_entry:
        with pytest.raises(OSError, match="still has an access control list"):
            private_scratch._darwin_verify_empty_acl(get_acl, 0)  # type: ignore[arg-type]
    else:
        private_scratch._darwin_verify_empty_acl(get_acl, 0)  # type: ignore[arg-type]


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
