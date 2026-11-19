"""Regression tests for the isolated FreeCAD probe's failure diagnostics."""

import io
import subprocess
from unittest.mock import MagicMock

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
