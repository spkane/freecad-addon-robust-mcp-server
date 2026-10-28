"""Regression tests for safe container and bridge documentation."""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTAINER_GUIDES = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs/getting-started/configuration.md",
    PROJECT_ROOT / "docs/guide/connection-modes.md",
)


def _markdown_section(markdown: str, heading: str) -> str:
    """Return the body of a Markdown section below the requested heading."""
    match = re.search(
        rf"^{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^#{{1,3}}\s|\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"Missing documentation section: {heading}"
    return match.group("body")


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
    assert "pairing" in normalized_contents
    assert (
        "Python execution" in normalized_contents
        or "execute Python" in normalized_contents
    )
    assert "unauthenticated Python execution" not in normalized_contents
    assert (
        "requires pairing before accepting Python execution" in normalized_contents
        or "require pairing with the MCP server before accepting requests"
        in normalized_contents
    )


def test_workbench_troubleshooting_rejects_non_loopback_rebind() -> None:
    """Connection troubleshooting must not recommend exposing the bridge."""
    contents = (PROJECT_ROOT / "docs/guide/workbench.md").read_text(encoding="utf-8")
    section = _markdown_section(
        contents,
        "### Connection Refused from Robust MCP Server",
    )
    guidance = " ".join(section.replace("`", "").replace("*", "").split()).lower()
    sentences = re.split(r"(?<=[.!?])\s+", guidance)

    assert any(
        any(prohibition in sentence for prohibition in ("do not", "must not", "never"))
        and "bridge" in sentence
        and any(
            boundary in sentence
            for boundary in (
                "0.0.0.0",  # noqa: S104 - intentional unsafe-address assertion
                "non-loopback",
                "non loopback",
            )
        )
        for sentence in sentences
    ), "Troubleshooting must prohibit exposing the bridge on non-loopback addresses"
    assert any(
        "linux" in sentence
        and "mcp server" in sentence
        and "host" in sentence
        and any(action in sentence for action in ("run", "start"))
        for sentence in sentences
    ), "Linux troubleshooting must recommend running the MCP server on the host"
