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
