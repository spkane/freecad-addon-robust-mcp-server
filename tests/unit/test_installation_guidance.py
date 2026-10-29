"""Protect the documented workbench installation layout."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "relative_path",
    [
        "docs/guide/workbench.md",
        "docs/getting-started/quickstart.md",
        "docs/getting-started/configuration.md",
    ],
)
def test_headless_guidance_uses_source_package_layout(relative_path: str) -> None:
    """Direct headless examples must use the package built by the installer."""
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    assert "Mod/RobustMCPBridge/freecad/RobustMCPBridge/" in text
    assert "Mod/freecad/RobustMCPBridge/" not in text


def test_installation_guide_distinguishes_archive_and_source_layouts() -> None:
    """The source installer's directory and archive root are not interchangeable."""
    text = (ROOT / "docs/getting-started/installation.md").read_text(encoding="utf-8")
    assert "Mod/RobustMCPBridge/package.xml" in text
    assert "archive's top-level package directory" in text
    assert "not currently in the public Addon Manager catalog" in text


def test_public_guidance_avoids_obsolete_installation_instructions() -> None:
    """Check user-facing commands and wiki paths against current packaging."""
    readme = (ROOT / "Documentation/README.md").read_text(encoding="utf-8")
    wiki = (ROOT / "freecad/RobustMCPBridge/wiki-source.txt").read_text(
        encoding="utf-8"
    )
    overview = (ROOT / "Resources/Documents/Overview.md").read_text(encoding="utf-8")
    assert "--test-connection" not in readme
    assert "--check" in readme
    assert "Via Addon Manager (recommended)" not in wiki
    assert "Mod/FreecadRobustMCPBridge/" not in wiki
    assert "releases?q=robust-mcp-workbench" in wiki
    assert "pip install freecad-robust-mcp" not in overview
    assert "pip install freecad-robust-mcp" not in wiki
    assert "uv run freecad-mcp --pair-bridge" in wiki
