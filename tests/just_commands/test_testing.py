"""Tests for testing module just commands.

These tests verify that test commands work correctly.
Note: We avoid running integration tests here to prevent recursion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.just_commands.conftest import assert_command_executed

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestTestingSyntax:
    """Syntax validation tests for testing commands."""

    TESTING_COMMANDS: ClassVar[list[str]] = [
        "testing::unit",
        "testing::cov",
        "testing::quick",
        "testing::integration",
        "testing::verbose",
        "testing::all",
        "testing::watch",
        "testing::check-deps",
        "testing::integration-freecad-auto",
        "testing::just-syntax",
        "testing::just-runtime",
        "testing::just-all",
        "testing::just-release",
        "testing::release-test",
        "testing::integration-headless-release",
        "testing::integration-gui-release",
        "testing::kill-bridge",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", TESTING_COMMANDS)
    def test_testing_command_syntax(self, just: JustRunner, command: str) -> None:
        """Testing command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestTestingRuntime:
    """Runtime tests for testing commands.

    Note: We use --collect-only or run minimal tests to avoid
    long execution times and recursion issues.
    """

    @pytest.mark.just_runtime
    def test_kill_bridge_runs(self, just: JustRunner) -> None:
        """Kill-bridge command should run (even if nothing to kill)."""
        result = just.run("testing::kill-bridge", timeout=30)
        # Should succeed even if no processes to kill
        assert result.success, f"Kill-bridge failed: {result.stderr}"

    @pytest.mark.just_runtime
    def test_unit_command_recognizes_pytest(self, just: JustRunner) -> None:
        """Unit test command should at least recognize pytest."""
        # Run with --collect-only to just validate pytest setup
        result = just.run(
            "testing::unit",
            timeout=60,
            env={"PYTEST_ADDOPTS": "--collect-only -q"},
        )
        # Should at least find some tests or run without error
        assert_command_executed(result, "testing::unit")

    @pytest.mark.just_runtime
    def test_quick_command_recognizes_markers(self, just: JustRunner) -> None:
        """Quick test command should recognize the 'not slow' marker."""
        result = just.run(
            "testing::quick",
            timeout=60,
            env={"PYTEST_ADDOPTS": "--collect-only -q"},
        )
        assert_command_executed(result, "testing::quick")

    @pytest.mark.just_runtime
    def test_gui_release_sequencing(self, just: JustRunner) -> None:
        """integration-gui-release recipe follows the correct shutdown sequence.

        After stopping FreeCAD, the recipe must:
        1. Call cleanup (graceful_kill_bridge_ports)
        2. Set STARTED_FREECAD=false
        3. Call wait_for_ports_free
        4. Call wait_for_freecad_exit
        5. Only run standalone tests when TEST_EXIT_CODE is 0
        6. Target test_shutdown_crash.py specifically for standalone tests
        7. Use -m "not standalone_freecad" for the first pytest run
        """
        result = just.dry_run("testing::integration-gui-release")
        assert result.success, (
            f"Dry-run failed for integration-gui-release: {result.stderr}"
        )

        # just --dry-run writes the expanded script to stderr
        script = result.output

        # --- Verify first pytest run filters out standalone tests ---
        assert '-m "not standalone_freecad"' in script, (
            "First pytest run must exclude standalone_freecad tests"
        )

        # --- Verify shutdown sequence order ---
        # Find positions of critical operations after stopping FreeCAD.
        # Use the "Stopping FreeCAD" marker to anchor past the function
        # definition, trap registrations, and comments that also mention cleanup.
        stopMarker = "Stopping FreeCAD for standalone tests"
        assert stopMarker in script, (
            "Recipe must log 'Stopping FreeCAD for standalone tests'"
        )
        stopPos = script.index(stopMarker)
        cleanupPos = script.index("cleanup", stopPos)
        startedFalsePos = script.index("STARTED_FREECAD=false", stopPos)
        portsPos = script.index("wait_for_ports_free", stopPos)
        exitPos = script.index("wait_for_freecad_exit", stopPos)

        assert cleanupPos < startedFalsePos, (
            "cleanup must be called before STARTED_FREECAD=false"
        )
        assert startedFalsePos < portsPos, (
            "STARTED_FREECAD=false must be set before wait_for_ports_free"
        )
        assert portsPos < exitPos, (
            "wait_for_ports_free must be called before wait_for_freecad_exit"
        )

        # --- Verify standalone tests are conditional on prior success ---
        standaloneGuard = 'if [ "$TEST_EXIT_CODE" -eq 0 ]'
        assert standaloneGuard in script, (
            "Standalone tests must be guarded by TEST_EXIT_CODE == 0 check"
        )

        # The standalone pytest must target test_shutdown_crash.py specifically
        assert "test_shutdown_crash.py" in script, (
            "Standalone pytest must target test_shutdown_crash.py"
        )

        # The guard must appear after wait_for_freecad_exit
        guardPos = script.index(standaloneGuard)
        assert guardPos > exitPos, (
            "Standalone test guard must come after wait_for_freecad_exit"
        )
