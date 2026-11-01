"""Checks for the release gate's pinned compatibility inventory."""

from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.verify_cam_release_compatibility import _validate_entry, main


def test_compatible_release_entry_is_validated() -> None:
    """Accept a pinned workbench release identity and digest."""
    entry = {
        "tag": "robust-mcp-workbench-v1.0.0",
        "asset": "freecad-mcp-workbench-1.0.0.zip",
        "sha256": "a" * 64,
    }
    assert _validate_entry(entry, "workbench") == tuple(entry.values())


@pytest.mark.parametrize(
    "field,value",
    [("asset", "../evil.zip"), ("tag", "-bad"), ("sha256", "not-a-digest")],
)
def test_rejects_invalid_compatibility_entries(field: str, value: str) -> None:
    """Reject unpinned or unsafe release identifiers before downloading."""
    entry = {
        "tag": "robust-mcp-workbench-v1.0.0",
        "asset": "candidate.zip",
        "sha256": "a" * 64,
    }
    entry[field] = value
    with pytest.raises(ValueError, match="Invalid"):
        _validate_entry(entry, "workbench")


def test_empty_inventory_has_no_downloads(tmp_path: Path) -> None:
    """An empty initial inventory succeeds without fetching releases."""
    (tmp_path / "cam-compatibility.toml").write_text(
        "compatible_servers = []\ncompatible_workbenches = []\n"
    )
    with (
        patch("scripts.verify_cam_release_compatibility.ROOT", tmp_path),
        patch(
            "scripts.verify_cam_release_compatibility.shutil.which",
            return_value="/usr/bin/uv",
        ),
        patch("scripts.verify_cam_release_compatibility.subprocess.run") as run,
    ):
        main()
    run.assert_not_called()


def test_inventory_tests_each_independent_component(tmp_path: Path) -> None:
    """Each declared release is tested against the opposite candidate."""
    manifest = """
compatible_servers = [{ tag = "robust-mcp-server-v1.0.0", asset = "server.whl", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }]
compatible_workbenches = [{ tag = "robust-mcp-workbench-v1.0.0", asset = "bridge.zip", sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }]
"""
    (tmp_path / "cam-compatibility.toml").write_text(manifest)
    with (
        patch("scripts.verify_cam_release_compatibility.ROOT", tmp_path),
        patch(
            "scripts.verify_cam_release_compatibility.shutil.which",
            return_value="/usr/bin/uv",
        ),
        patch(
            "scripts.verify_cam_release_compatibility._download",
            side_effect=[tmp_path / "server.whl", tmp_path / "bridge.zip"],
        ) as download,
        patch("scripts.verify_cam_release_compatibility.subprocess.run"),
        patch("scripts.verify_cam_release_compatibility._run_test") as run_test,
    ):
        main()
    assert download.call_count == 2
    assert "FREECAD_MCP_TEST_PYTHON" in run_test.call_args_list[0].args[0]
    assert run_test.call_args_list[1].args[0] == {
        "FREECAD_RELEASE_WORKBENCH_ARCHIVE": str(tmp_path / "bridge.zip")
    }
