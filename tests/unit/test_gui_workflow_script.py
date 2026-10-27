"""Regression checks for the GUI workflow's nested shell script."""

from pathlib import Path


def test_gui_container_script_has_no_unescaped_single_quotes() -> None:
    """A single quote would end the host shell's quoted container script."""
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/test-gui.yaml"
    ).read_text(encoding="utf-8")
    script = workflow.split("/bin/bash -c '\n", 1)[1].split("\n            '", 1)[0]
    assert "'" not in script
