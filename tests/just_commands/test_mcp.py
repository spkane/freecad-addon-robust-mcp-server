"""Tests for mcp module just commands.

These tests verify that MCP server commands work correctly.
Note: Most MCP commands require FreeCAD to be running.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.just_commands.conftest import assert_command_executed

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestMCPSyntax:
    """Syntax validation tests for MCP commands."""

    MCP_COMMANDS: ClassVar[list[str]] = [
        "mcp::check",
        "mcp::run",
        "mcp::run-debug",
        "mcp::run-http",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", MCP_COMMANDS)
    def test_mcp_command_syntax(self, just: JustRunner, command: str) -> None:
        """MCP command should have valid syntax."""
        # run-http can take an optional port argument
        if command == "mcp::run-http":
            result = just.dry_run(command, "8080")
        else:
            result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestMCPRuntime:
    """Runtime tests for MCP commands.

    Note: Most MCP commands require FreeCAD MCP bridge to be running.
    The check command can run without FreeCAD and will fail gracefully.
    """

    @pytest.mark.just_runtime
    def test_check_runs_and_reports_status(self, just: JustRunner) -> None:
        """Check command should run and report bridge status.

        This will likely fail (no bridge running) but should not crash.
        """
        result = just.run("mcp::check", timeout=30)
        # Command may fail if no bridge running, but should run without missing deps
        assert_command_executed(result, "mcp::check")
        # Should produce some output (verifies the command actually ran and
        # reported something, without being brittle to specific wording)
        assert result.output.strip(), "mcp::check produced no output"
