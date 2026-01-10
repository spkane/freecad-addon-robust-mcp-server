"""Tests for freecad module just commands.

These tests verify that FreeCAD-related commands work correctly.
Note: Most FreeCAD commands require FreeCAD to be installed.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


def freecad_available() -> bool:
    """Check if FreeCAD is available."""
    # Check for common FreeCAD command locations
    if shutil.which("freecad") or shutil.which("FreeCAD"):
        return True
    return bool(shutil.which("freecadcmd") or shutil.which("FreeCADCmd"))


class TestFreecadSyntax:
    """Syntax validation tests for FreeCAD commands."""

    FREECAD_COMMANDS: ClassVar[list[str]] = [
        "freecad::run-headless",
        "freecad::run-headless-custom",
        "freecad::run-gui",
        "freecad::run-gui-custom",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", FREECAD_COMMANDS)
    def test_freecad_command_syntax(self, just: JustRunner, command: str) -> None:
        """FreeCAD command should have valid syntax."""
        # Commands with required arguments
        if command == "freecad::run-headless-custom":
            result = just.dry_run(command, "/path/to/freecadcmd")
        elif command == "freecad::run-gui-custom":
            result = just.dry_run(command, "/path/to/freecad")
        else:
            result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


@pytest.mark.requires_freecad
class TestFreecadRuntime:
    """Runtime tests for FreeCAD commands (require FreeCAD)."""

    @pytest.fixture(autouse=True)
    def skip_if_no_freecad(self) -> None:
        """Skip tests if FreeCAD is not available."""
        if not freecad_available():
            pytest.skip("FreeCAD not available")

    @pytest.mark.just_runtime
    def test_run_headless_starts(self, just: JustRunner) -> None:
        """run-headless should start FreeCAD (we just verify it doesn't crash immediately).

        Note: This test starts FreeCAD headless and lets it run briefly.
        In CI, this should work with Xvfb.
        """
        # Start headless and kill after short timeout
        result = just.run("freecad::run-headless", timeout=10)

        # Check for missing executable first (exit code 127)
        if result.returncode == 127:
            pytest.fail(
                "FreeCAD executable not found (exit code 127). "
                "Ensure FreeCAD is installed and in PATH. "
                f"Output: {result.output}"
            )

        # Will timeout (expected) - we just want to verify it started
        # returncode -1 means timeout, which is expected
        # returncode 0 means it exited cleanly
        # Any other exit code indicates a problem
        assert result.returncode in (-1, 0), (
            f"FreeCAD failed unexpectedly (exit {result.returncode}): {result.output}"
        )
