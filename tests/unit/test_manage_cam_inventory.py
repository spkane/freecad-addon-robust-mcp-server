"""Release inventory reconciliation and failure-mode tests."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from scripts.manage_cam_inventory import discover, inventory, marker, reconcile, render

SERVER = "robust-mcp-server-v1.0.0"
BENCH = "robust-mcp-workbench-v1.0.0"
DIGEST = "a" * 64


def empty() -> dict:
    """Construct an empty supported and retired inventory."""
    return {
        "compatible_servers": [],
        "compatible_workbenches": [],
        "retired_servers": [],
        "retired_workbenches": [],
    }


def release(tag: str = SERVER, draft: bool = False) -> dict:
    """Create a representative gated release response."""
    return {
        "tag_name": tag,
        "draft": draft,
        "assets": [
            {"name": "cam-gate-v1.json", "id": 1},
            {"name": "server.whl", "digest": f"sha256:{DIGEST}"},
        ],
    }


def test_discover_requires_matching_gate_receipt() -> None:
    """A published asset is included only when its gate receipt matches."""
    receipt = {"version": 1, "tag": SERVER, "asset": "server.whl", "sha256": DIGEST}
    with patch(
        "scripts.manage_cam_inventory.gh", return_value=json.dumps(receipt).encode()
    ):
        found = discover([release()])
    assert found["server"][SERVER] == {
        key: value for key, value in receipt.items() if key != "version"
    }
    receipt["sha256"] = "b" * 64
    with (
        patch(
            "scripts.manage_cam_inventory.gh", return_value=json.dumps(receipt).encode()
        ),
        pytest.raises(ValueError, match="does not match"),
    ):
        discover([release()])


def test_discover_rejects_invalid_release_asset_name() -> None:
    """A release with an unsafe asset name cannot enter the inventory."""
    invalid = release()
    invalid["assets"][1]["name"] = "../server.whl"
    with pytest.raises(ValueError, match="Invalid server release"):
        discover([invalid])


def test_incomplete_draft_blocks_next_release() -> None:
    """An interrupted publication is resolved before another release begins."""
    with pytest.raises(RuntimeError, match="Incomplete staged CAM release"):
        discover([release(draft=True)])


def test_older_release_without_marker_is_ignored() -> None:
    """Historical pre-CAM releases do not enter the support inventory."""
    old = release()
    old["assets"] = old["assets"][1:]
    with patch("scripts.manage_cam_inventory.source_has_cam", return_value=False):
        assert discover([old]) == {"server": {}, "workbench": {}}
    with patch("scripts.manage_cam_inventory.source_has_cam", return_value=True):
        with pytest.raises(RuntimeError, match="has no gate receipt"):
            discover([old])


def test_reconcile_requires_missing_releases_and_rejects_changed_pins() -> None:
    """New releases are reported and replaced assets fail closed."""
    entry = {"tag": SERVER, "asset": "server.whl", "sha256": DIGEST}
    releases = {"server": {SERVER: entry}, "workbench": {}}
    manifest = empty()
    assert reconcile(manifest, releases) == [SERVER]
    manifest["compatible_servers"].append({**entry, "sha256": "b" * 64})
    with pytest.raises(ValueError, match="missing or changed"):
        reconcile(manifest, releases)


def test_retired_release_stays_out_and_requires_reason() -> None:
    """Deliberately retired releases cannot silently return to the matrix."""
    manifest = empty()
    manifest["retired_servers"].append({"tag": SERVER, "reason": "Support ended"})
    validated = inventory(render(manifest).encode())
    assert reconcile(validated, {"server": {SERVER: {}}, "workbench": {}}) == []
    manifest["retired_servers"][0]["reason"] = ""
    with pytest.raises(ValueError, match="retired"):
        inventory(render(manifest).encode())


def test_receipt_contains_exact_artifact_digest(tmp_path: Path) -> None:
    """The marker binds a release tag to the tested candidate bytes."""
    artifact = tmp_path / "server.whl"
    artifact.write_bytes(b"candidate")
    output = tmp_path / "receipt.json"
    marker(SERVER, artifact, output)
    assert (
        json.loads(output.read_text())
        == {
            "version": 1,
            "tag": SERVER,
            "asset": "server.whl",
            "sha256": "dda18a0e21ae47c53b4309434cbc02ae8bf764fa83a6defbb719431242722aa7",  # pragma: allowlist secret
        }
    )


def test_check_rejects_stale_tag_and_missing_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A release cannot use a stale or incomplete reviewed inventory."""
    from scripts.manage_cam_inventory import main

    manifest = empty()
    entry = {"tag": SERVER, "asset": "server.whl", "sha256": DIGEST}
    releases = {"server": {SERVER: entry}, "workbench": {}}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["manage_cam_inventory", "check"])
    (tmp_path / "cam-compatibility.toml").write_text(render(manifest))
    with (
        patch(
            "scripts.manage_cam_inventory.main_inventory",
            return_value=render(manifest).encode(),
        ),
        patch("scripts.manage_cam_inventory.published_releases", return_value=[]),
        patch("scripts.manage_cam_inventory.discover", return_value=releases),
    ):
        with pytest.raises(RuntimeError, match="inventory update required"):
            main()
    manifest["compatible_servers"].append(entry)
    with (
        patch(
            "scripts.manage_cam_inventory.main_inventory",
            return_value=render(manifest).encode(),
        ),
        patch("scripts.manage_cam_inventory.published_releases", return_value=[]),
        patch("scripts.manage_cam_inventory.discover", return_value=releases),
    ):
        with pytest.raises(RuntimeError, match="differs from main"):
            main()


def test_update_records_exact_published_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The generated inventory pins the actual published asset and digest."""
    from scripts.manage_cam_inventory import main

    manifest = empty()
    entry = {"tag": SERVER, "asset": "server.whl", "sha256": DIGEST}
    releases = {"server": {SERVER: entry}, "workbench": {}}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["manage_cam_inventory", "update", "--tag", SERVER])
    with (
        patch(
            "scripts.manage_cam_inventory.main_inventory",
            return_value=render(manifest).encode(),
        ),
        patch("scripts.manage_cam_inventory.published_releases", return_value=[]),
        patch("scripts.manage_cam_inventory.discover", return_value=releases),
    ):
        main()
    updated = inventory((tmp_path / "cam-compatibility.toml").read_bytes())
    assert updated["compatible_servers"] == [entry]
    assert not updated["compatible_workbenches"]


def test_final_inventory_check_detects_policy_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changed support policy stops publication after a release is staged."""
    from scripts.manage_cam_inventory import main

    old = empty()
    newer = empty()
    newer["retired_servers"].append({"tag": SERVER, "reason": "Support ended"})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["manage_cam_inventory", "check-current"])
    (tmp_path / "cam-compatibility.toml").write_text(render(old))
    with patch(
        "scripts.manage_cam_inventory.main_inventory",
        return_value=render(newer).encode(),
    ):
        with pytest.raises(RuntimeError, match="changed during this release"):
            main()


def test_update_already_recorded_release_preserves_inventory_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry does not rewrite comments or open a formatting-only PR."""
    from scripts.manage_cam_inventory import main

    entry = {"tag": SERVER, "asset": "server.whl", "sha256": DIGEST}
    manifest = empty()
    manifest["compatible_servers"].append(entry)
    original = "# Maintainer comment\n" + render(manifest)
    releases = {"server": {SERVER: entry}, "workbench": {}}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["manage_cam_inventory", "update", "--tag", SERVER])
    path = tmp_path / "cam-compatibility.toml"
    path.write_text(original)
    with (
        patch(
            "scripts.manage_cam_inventory.main_inventory",
            return_value=original.encode(),
        ),
        patch("scripts.manage_cam_inventory.published_releases", return_value=[]),
        patch("scripts.manage_cam_inventory.discover", return_value=releases),
    ):
        main()
    assert path.read_text() == original


def test_github_queries_have_a_bounded_timeout() -> None:
    """A stalled GitHub query cannot block a release job indefinitely."""
    import subprocess

    from scripts.manage_cam_inventory import GH_TIMEOUT_SECONDS, gh

    with (
        patch("scripts.manage_cam_inventory.shutil.which", return_value="/usr/bin/gh"),
        patch(
            "scripts.manage_cam_inventory.subprocess.check_output",
            side_effect=subprocess.TimeoutExpired("gh", GH_TIMEOUT_SECONDS),
        ) as command,
        pytest.raises(subprocess.TimeoutExpired),
    ):
        gh("api", "repos/example")
    assert command.call_args.kwargs["timeout"] == GH_TIMEOUT_SECONDS


def test_render_marks_public_hashes_for_secret_scanner() -> None:
    """Generated public digest entries include a narrow inline scanner exemption."""
    manifest = empty()
    manifest["compatible_servers"].append(
        {"tag": SERVER, "asset": "server.whl", "sha256": DIGEST}
    )
    manifest["retired_workbenches"].append({"tag": BENCH, "reason": "Unsupported"})
    text = render(manifest)
    assert text.count("# pragma: allowlist secret") == 1
    assert inventory(text.encode()) == manifest
