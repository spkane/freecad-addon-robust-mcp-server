"""Regression tests for safe container and bridge documentation."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTAINER_GUIDES = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs/getting-started/configuration.md",
    PROJECT_ROOT / "docs/guide/connection-modes.md",
)


def test_documentation_does_not_recommend_linux_host_gateway() -> None:
    """User documentation must not restore the nonfunctional Linux recipe."""
    markdown_files = (PROJECT_ROOT / "docs").rglob("*.md")
    paths = [PROJECT_ROOT / "README.md", *markdown_files]

    for path in paths:
        contents = path.read_text(encoding="utf-8")
        assert "--add-host=host.docker.internal:host-gateway" not in contents, path


@pytest.mark.parametrize("path", CONTAINER_GUIDES)
def test_container_guides_document_security_boundary(path: Path) -> None:
    """Container guidance must preserve the loopback execution boundary."""
    contents = path.read_text(encoding="utf-8")
    normalized_contents = " ".join(contents.split())

    assert "Docker Desktop" in contents
    assert "Docker Engine" in contents
    assert "loopback" in contents
    assert "unauthenticated Python execution" in normalized_contents


def test_workbench_troubleshooting_rejects_non_loopback_rebind() -> None:
    """Connection troubleshooting must not recommend exposing the bridge."""
    contents = (PROJECT_ROOT / "docs/guide/workbench.md").read_text(encoding="utf-8")

    assert "Do not rebind the bridge to `0.0.0.0`" in contents
    assert "run the MCP server directly on the host" in contents
