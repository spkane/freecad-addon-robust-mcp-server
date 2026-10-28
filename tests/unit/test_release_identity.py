"""Validate release metadata against the project's canonical public identity."""

import tomllib
from pathlib import Path


def test_package_project_urls_use_current_repository() -> None:
    """Published metadata must not point to the repository's former name."""
    root = Path(__file__).resolve().parents[2]
    with (root / "pyproject.toml").open("rb") as source:
        urls = tomllib.load(source)["project"]["urls"]
    assert urls["Repository"] == (
        "https://github.com/spkane/freecad-addon-robust-mcp-server.git"
    )
    assert urls["Issues"] == (
        "https://github.com/spkane/freecad-addon-robust-mcp-server/issues"
    )
    assert urls["Documentation"] == (
        "https://spkane.github.io/freecad-addon-robust-mcp-server/latest/"
    )
    assert all("freecad-robust-mcp-and-more" not in url for url in urls.values())
