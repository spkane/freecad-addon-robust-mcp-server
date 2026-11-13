"""Verify macro snapshots bind review to immutable file bytes."""

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def snapshots(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the snapshot module independently of FreeCAD."""
    path = (
        Path(__file__).parents[3]
        / "freecad/RobustMCPBridge/freecad_mcp_bridge/macro_snapshot.py"
    )
    spec = importlib.util.spec_from_file_location("macro_snapshot_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_snapshot_is_unchanged_after_file_replacement(
    snapshots: ModuleType, tmp_path: Path
) -> None:
    """Replacing the file does not change the captured or hashed content."""
    path = tmp_path / "test.FCMacro"
    original = b"_result_ = 42\r\n"
    path.write_bytes(original)
    snapshot = snapshots.snapshot_macro(str(path))
    path.write_bytes(b"_result_ = 99\n")
    assert snapshot.path == str(path.resolve())
    assert snapshot.content == original
    assert snapshot.sha256 == hashlib.sha256(original).hexdigest()
    assert snapshots.snapshot_macro(str(path)).sha256 != snapshot.sha256


def test_snapshot_rejects_non_regular_and_oversized_files(
    snapshots: ModuleType, tmp_path: Path
) -> None:
    """Directories and oversized files cannot become review payloads."""
    with pytest.raises((ValueError, OSError)):
        snapshots.snapshot_macro(str(tmp_path))
    path = tmp_path / "large.FCMacro"
    path.write_bytes(b"x" * (snapshots.MAX_MACRO_BYTES + 1))
    with pytest.raises(ValueError, match="size"):
        snapshots.snapshot_macro(str(path))


def test_resolve_macro_prefers_user_directory(
    snapshots: ModuleType, tmp_path: Path
) -> None:
    """Capture the user macro when both directories contain the same name."""
    user = tmp_path / "user"
    system = tmp_path / "system"
    user.mkdir()
    system.mkdir()
    (user / "example.FCMacro").write_bytes(b"user")
    (system / "example.FCMacro").write_bytes(b"system")
    assert (
        snapshots.resolve_macro("example", (str(user), str(system))).content == b"user"
    )


def test_resolve_macro_refuses_path_traversal(
    snapshots: ModuleType, tmp_path: Path
) -> None:
    """An agent cannot choose a macro outside the configured locations by name."""
    with pytest.raises(ValueError):
        snapshots.resolve_macro("../example", (str(tmp_path),))
