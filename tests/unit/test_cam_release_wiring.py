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
    gate_steps = jobs["cam-release-gate"]["steps"]
    assert any(
        step.get("uses") == "./.github/actions/test-cam-release" for step in gate_steps
    )


def test_workbench_archive_gate_precedes_release() -> None:
    """The archive is exercised before the release action can publish it."""
    steps = _workflow("mcp-workbench-release.yaml")["jobs"]["validate-and-release"][
        "steps"
    ]
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
