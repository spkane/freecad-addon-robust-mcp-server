"""Verify CAM candidate checks cannot be bypassed by publication jobs."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _workflow(name: str) -> dict:
    """Read a repository-owned GitHub Actions workflow."""
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text())


def test_server_publication_depends_on_cam_artifact_gate() -> None:
    """Image publication and PyPI publication wait for the artifact gate."""
    jobs = _workflow("mcp-server-release.yaml")["jobs"]
    assert "cam-release-gate" in jobs["container-candidate"]["needs"]
    assert "container-candidate" in jobs["docker-release"]["needs"]
    for publication in ("publish-pypi", "publish-testpypi"):
        assert "container-candidate" in jobs[publication]["needs"]
    assert not jobs["cam-release-gate"].get("continue-on-error", False)
    gate_steps = jobs["cam-release-gate"]["steps"]
    gate = next(
        step
        for step in gate_steps
        if step.get("uses") == "./.github/actions/test-cam-release"
    )
    assert not gate.get("continue-on-error", False)


def test_workbench_archive_gate_precedes_release() -> None:
    """The archive is exercised before the release action can publish it."""
    job = _workflow("mcp-workbench-release.yaml")["jobs"]["validate-and-release"]
    assert not job.get("continue-on-error", False)
    steps = job["steps"]
    gate = next(
        i
        for i, step in enumerate(steps)
        if step.get("uses") == "./.github/actions/test-cam-release"
    )
    publish = next(
        i
        for i, step in enumerate(steps)
        if str(step.get("uses", "")).startswith("softprops/action-gh-release@")
    )
    assert gate < publish
    assert not steps[gate].get("continue-on-error", False)


def test_component_releases_share_serial_publication_group() -> None:
    """Both component workflows serialize all publication and inventory work."""
    server = _workflow("mcp-server-release.yaml")
    workbench = _workflow("mcp-workbench-release.yaml")
    assert server["concurrency"]["group"] == workbench["concurrency"]["group"]
    assert server["concurrency"].get("cancel-in-progress") is False
    assert workbench["concurrency"].get("cancel-in-progress") is False


def test_staging_and_inventory_reconciliation_precede_publication() -> None:
    """Reconciliation and durable staging happen before external publication."""
    server = _workflow("mcp-server-release.yaml")["jobs"]
    assert "stage-server-release" in server["docker-release"]["needs"]
    assert "container-candidate" in server["stage-server-release"]["needs"]
    gate_steps = server["cam-release-gate"]["steps"]
    check = next(
        i
        for i, step in enumerate(gate_steps)
        if "manage_cam_inventory check" in step.get("run", "")
    )
    exercise = next(
        i
        for i, step in enumerate(gate_steps)
        if step.get("uses") == "./.github/actions/test-cam-release"
    )
    assert gate_steps[check]["run"].startswith("python3 ")
    assert check < exercise
    stage_steps = server["stage-server-release"]["steps"]
    stage_check = next(
        i
        for i, step in enumerate(stage_steps)
        if "manage_cam_inventory check" in step.get("run", "")
    )
    stage = next(
        i
        for i, step in enumerate(stage_steps)
        if "gh release create" in step.get("run", "")
    )
    assert stage_check < stage
    assert server["update-cam-inventory"]["needs"] == ["create-github-release"]
    workbench = _workflow("mcp-workbench-release.yaml")["jobs"]
    steps = workbench["validate-and-release"]["steps"]
    positions = {step.get("name"): i for i, step in enumerate(steps)}
    assert (
        positions["Reconcile published CAM releases with reviewed inventory"]
        < positions["Stage GitHub Release"]
        < positions["Create GitHub Release"]
    )
    assert workbench["update-cam-inventory"]["needs"] == ["validate-and-release"]
    for job in (server["update-cam-inventory"], workbench["update-cam-inventory"]):
        assert job["permissions"] == {"contents": "write", "pull-requests": "write"}


def test_reviewed_inventory_rechecked_before_each_publication() -> None:
    """Inventory changes during a release stop each publication step."""
    server = _workflow("mcp-server-release.yaml")["jobs"]
    for job_name, publication in (
        ("docker-release", "Promote the tested digest"),
        ("publish-pypi", "Publish to PyPI"),
        ("publish-testpypi", "Publish to TestPyPI"),
        ("create-github-release", "Create GitHub Release"),
    ):
        steps = server[job_name]["steps"]
        check = next(
            i
            for i, step in enumerate(steps)
            if "manage_cam_inventory check-current" in step.get("run", "")
        )
        publish = next(
            i for i, step in enumerate(steps) if step.get("name") == publication
        )
        assert check < publish
    steps = _workflow("mcp-workbench-release.yaml")["jobs"]["validate-and-release"][
        "steps"
    ]
    check = next(
        i
        for i, step in enumerate(steps)
        if "manage_cam_inventory check-current" in step.get("run", "")
    )
    publish = next(
        i for i, step in enumerate(steps) if step.get("name") == "Create GitHub Release"
    )
    assert check < publish
