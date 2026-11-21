"""Tests for path snapshots used by local file-operation review."""

import importlib
import os
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def file_review(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import the bundled module without starting the workbench."""
    addon = Path(__file__).parents[3] / "freecad/RobustMCPBridge"
    monkeypatch.syspath_prepend(str(addon))
    return importlib.import_module("freecad_mcp_bridge.file_review")


def test_read_detects_changed_and_replaced_file(
    file_review: Any, tmp_path: Path
) -> None:
    """A reviewed target cannot silently change before dispatch."""
    path = tmp_path / "model.FCStd"
    path.write_text("first")
    snapshot = file_review.snapshot_file(str(path), "read")
    assert snapshot.exists and snapshot.unchanged()
    path.write_text("different contents")
    assert not snapshot.unchanged()
    snapshot = file_review.snapshot_file(str(path), "read")
    path.unlink()
    path.write_text("replacement")
    assert not snapshot.unchanged()


def test_write_detects_new_file_and_parent_replacement(
    file_review: Any, tmp_path: Path
) -> None:
    """An absent output cannot turn into an unreviewed overwrite."""
    folder = tmp_path / "export"
    folder.mkdir()
    path = folder / "model.step"
    snapshot = file_review.snapshot_file(str(path), "write")
    assert not snapshot.exists and snapshot.unchanged()
    path.write_text("existing")
    assert not snapshot.unchanged()
    path.unlink()
    snapshot = file_review.snapshot_file(str(path), "write")
    folder.rename(tmp_path / "old-export")
    folder.mkdir()
    assert not snapshot.unchanged()


def test_relative_path_and_changed_working_directory(
    file_review: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative path is tied to the working directory used during review."""
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "model").write_text("first")
    (second / "model").write_text("second")
    monkeypatch.chdir(first)
    snapshot = file_review.snapshot_file("model", "read")
    assert snapshot.resolved_path == os.path.realpath(first / "model")
    assert snapshot.unchanged()
    monkeypatch.chdir(second)
    assert not snapshot.unchanged()


def test_symlink_retarget_and_dangling_target(file_review: Any, tmp_path: Path) -> None:
    """The resolved destination and the reviewed link both participate."""
    first, second, link = tmp_path / "a", tmp_path / "b", tmp_path / "link"
    first.write_text("first")
    second.write_text("second")
    try:
        link.symlink_to(first)
    except OSError:
        pytest.skip("Creating symbolic links is unavailable")
    snapshot = file_review.snapshot_file(str(link), "read")
    assert snapshot.is_symlink and snapshot.resolved_path == os.path.realpath(first)
    link.unlink()
    link.symlink_to(second)
    assert not snapshot.unchanged()
    link.unlink()
    link.symlink_to(tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        file_review.snapshot_file(str(link), "write")


def test_relative_parent_after_symlink_uses_filesystem_resolution(
    file_review: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Do not collapse '..' before resolving a preceding symbolic link."""
    working = tmp_path / "working"
    real = tmp_path / "real"
    (real / "nested").mkdir(parents=True)
    working.mkdir()
    (real / "model").write_text("real")
    (working / "model").write_text("other")
    try:
        (working / "link").symlink_to(real / "nested", target_is_directory=True)
    except OSError:
        pytest.skip("Creating symbolic links is unavailable")
    monkeypatch.chdir(working)
    snapshot = file_review.snapshot_file("link/../model", "read")
    assert snapshot.resolved_path == os.path.realpath(real / "model")
    assert snapshot.unchanged()


def test_unsupported_paths_fail_closed(file_review: Any, tmp_path: Path) -> None:
    """Only regular file targets and supported actions can be reviewed."""
    for path, action in (("", "read"), (str(tmp_path), "read"), ("x", "rename")):
        with pytest.raises(ValueError):
            file_review.snapshot_file(path, action)
    snapshot = file_review.snapshot_file(str(tmp_path / "missing" / "file"), "write")
    assert snapshot.existing_parent == str(tmp_path.resolve())
    assert snapshot.unchanged()
    (tmp_path / "missing").mkdir()
    assert not snapshot.unchanged()
