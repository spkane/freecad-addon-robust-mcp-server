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
