"""Tests for main justfile commands.

These tests verify that the top-level commands in the main justfile work correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestMainSyntax:
    """Syntax validation tests for main justfile commands."""

    MAIN_COMMANDS: ClassVar[list[str]] = [
        "default",
        "setup",
        "all",
        "all-with-integration",
        "list-all",
        "list-coderabbit",
        "list-dev",
        "list-docker",
        "list-documentation",
        "list-freecad",
        "list-install",
        "list-mcp",
        "list-quality",
        "list-release",
        "list-testing",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", MAIN_COMMANDS)
    def test_main_command_syntax(self, just: JustRunner, command: str) -> None:
        """Main justfile command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestMainRuntime:
    """Runtime tests for main justfile commands."""

    @pytest.mark.just_runtime
    def test_default_shows_help(self, just: JustRunner) -> None:
        """Default command should show available commands."""
        result = just.run("default", timeout=10)
        assert result.success, f"Default failed: {result.stderr}"
        # Should show some commands
        assert "setup" in result.stdout or "all" in result.stdout

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "module",
        [
            "coderabbit",
            "dev",
            "docker",
            "documentation",
            "freecad",
            "install",
            "mcp",
            "quality",
            "release",
            "testing",
        ],
    )
    def test_list_module_shows_commands(self, just: JustRunner, module: str) -> None:
        """Each list-<module> command should show module commands."""
        result = just.run(f"list-{module}", timeout=10)
        assert result.success, f"list-{module} failed: {result.stderr}"
        # Should have some output
        assert result.stdout.strip()

    @pytest.mark.just_runtime
    def test_list_all_comprehensive(self, just: JustRunner) -> None:
        """list-all should show commands from multiple modules."""
        result = just.run("list-all", timeout=10)
        assert result.success, f"list-all failed: {result.stderr}"
        # Should include module headers (using : separator for headers)
        module_headers = ["quality:", "testing:", "dev:", "docker:"]
        found_modules = sum(1 for header in module_headers if header in result.stdout)
        assert found_modules >= 2, "list-all should show commands from multiple modules"
