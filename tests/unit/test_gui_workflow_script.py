"""Regression checks for the GUI workflow's nested shell script."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.integration import gui_probe


def test_gui_container_script_has_no_unescaped_single_quotes() -> None:
    """A single quote would end the host shell's quoted container script."""
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/test-gui.yaml"
    ).read_text(encoding="utf-8")
    script = workflow.split("/bin/bash -c '\n", 1)[1].split("\n            '", 1)[0]
    assert "'" not in script


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"success": True, "result": True}, True),
        ({"success": True, "result": False}, False),
        ({"success": False, "result": True}, False),
        ({"success": True}, False),
    ],
)
def test_gui_probe_checks_execution_and_gui_result(
    monkeypatch: pytest.MonkeyPatch, response: object, expected: bool
) -> None:
    """A successful request alone must not establish that the GUI is active."""
    proxy = MagicMock()
    proxy.execute.return_value = response
    monkeypatch.setattr(gui_probe, "integration_proxy", lambda: proxy)
    assert gui_probe.gui_is_ready() is expected
