"""Regression tests for the isolated FreeCAD probe's failure diagnostics."""

import ast
import contextlib
import io
import json
import os
import subprocess
import traceback
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.research.approval_freecad_host_probe import (
    attach_stderr,
    finish_failed_process,
)


def test_diagnostics_include_late_invalid_utf8_without_masking_error() -> None:
    """A child shutdown message is collected and invalid bytes are replaced."""
    log = io.BytesIO()
    process = MagicMock()
    process.wait.side_effect = lambda **_kwargs: log.write(b"late-\xff")
    error = RuntimeError("original error")

    finish_failed_process(process)
    attach_stderr(error, log)

    assert str(error) == "original error"
    assert "late-\ufffd" in error.__notes__[0]
    process.terminate.assert_not_called()


def test_diagnostic_read_failure_retains_original_error() -> None:
    """An unreadable log does not replace the failure being diagnosed."""
    error = RuntimeError("original error")
    log = io.BytesIO()
    log.close()
    attach_stderr(error, log)
    assert str(error) == "original error"
    assert "Could not read FreeCAD probe stderr" in error.__notes__[0]


def test_failed_child_is_terminated_and_reaped_after_timeout() -> None:
    """A child that ignores shutdown is terminated and, if needed, killed."""
    process = MagicMock()
    process.wait.side_effect = [
        subprocess.TimeoutExpired("freecad", 2),
        subprocess.TimeoutExpired("freecad", 5),
        0,
    ]
    finish_failed_process(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 3


def test_startup_cleanup_survives_diagnostic_write_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unavailable stderr cannot prevent startup error cleanup."""
    macro = (
        Path(__file__).resolve().parents[1]
        / "research"
        / "approval_freecad_host.FCMacro"
    )
    tree = ast.parse(macro.read_text())
    functions: list[ast.stmt] = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"report_traceback", "start"}
    ]
    fake_plugin = MagicMock()
    gui = MagicMock()
    result = MagicMock()
    namespace: dict[str, Any] = {
        "contextlib": contextlib,
        "os": os,
        "traceback": traceback,
        "plugin": fake_plugin,
        "FreeCADGui": gui,
        "result_path": result,
        "json": json,
    }
    exec(  # noqa: S102 - execute only functions parsed from the local test fixture
        compile(ast.Module(body=functions, type_ignores=[]), str(macro), "exec"),
        namespace,
    )
    monkeypatch.delenv("FREECAD_USER_DATA", raising=False)
    monkeypatch.setattr(traceback, "print_exc", MagicMock(side_effect=OSError("full")))

    namespace["start"]()

    result.write_text.assert_called_once()
    fake_plugin.stop.assert_called_once()
    gui.getMainWindow.return_value.close.assert_called_once()
