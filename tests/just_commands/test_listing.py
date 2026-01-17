"""Tests for just command listing functionality.

These tests verify that all listing commands work correctly and
that all expected modules are accessible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestListCommands:
    """Test just command listing functionality."""

    @pytest.mark.just_syntax
    def test_default_lists_commands(self, just: JustRunner) -> None:
        """Default command should list available commands."""
        result = just.run("default", timeout=10)
        assert result.success, f"Failed: {result.stderr}"
        # Should show at least some commands
        assert "setup" in result.stdout or "all" in result.stdout

    @pytest.mark.just_syntax
    def test_list_all_shows_all_modules(self, just: JustRunner) -> None:
        """list-all should show commands from all modules."""
        result = just.run("list-all", timeout=10)
        assert result.success, f"Failed: {result.stderr}"
        # Should include module headers (e.g., "quality:" or "testing:")
        assert "quality:" in result.stdout or "testing:" in result.stdout

    @pytest.mark.just_syntax
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
    def test_list_module_commands(self, just: JustRunner, module: str) -> None:
        """Each module listing command should work."""
        result = just.run(f"list-{module}", timeout=10)
        assert result.success, f"list-{module} failed: {result.stderr}"
        # Output should not be empty
        assert result.stdout.strip(), f"list-{module} returned empty output"


class TestModulesExist:
    """Test that all expected modules and commands exist."""

    # Map of modules to their expected commands (subset for validation)
    EXPECTED_COMMANDS: ClassVar[dict[str, list[str]]] = {
        "quality": ["check", "format", "lint", "typecheck", "security"],
        "testing": ["unit", "cov", "quick", "integration"],
        "dev": ["install-deps", "install-pre-commit", "clean"],
        "docker": ["build", "run", "clean"],
        "documentation": ["build", "serve", "open"],
        "install": [
            "mcp-server",
            "mcp-bridge-workbench",
            "status",
            "uninstall",
            "cleanup",
        ],
        "mcp": ["run", "check"],
        "freecad": ["run-gui", "run-headless"],
        "release": ["status", "list-tags", "latest-versions"],
        "coderabbit": ["install", "review"],
    }

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("module,commands", EXPECTED_COMMANDS.items())
    def test_module_has_expected_commands(
        self, just: JustRunner, module: str, commands: list[str]
    ) -> None:
        """Each module should have its expected commands."""
        # Use list_commands to get parsed command names
        available_commands = just.list_commands(module)
        assert available_commands, f"No commands found in {module} module"

        for cmd in commands:
            assert cmd in available_commands, (
                f"Command '{cmd}' not found in {module} module. "
                f"Available: {available_commands}"
            )


class TestSyntaxValidation:
    """Test that all commands have valid syntax (dry-run)."""

    # Commands that can be safely dry-run tested
    SAFE_DRY_RUN_COMMANDS: ClassVar[list[str]] = [
        # Main justfile
        "setup",
        "all",
        # Quality commands
        "quality::check",
        "quality::format",
        "quality::lint",
        "quality::typecheck",
        "quality::security",
        "quality::scan",
        "quality::markdown-lint",
        # Testing commands
        "testing::unit",
        "testing::cov",
        "testing::quick",
        "testing::verbose",
        # Dev commands
        "dev::install-deps",
        "dev::install-pre-commit",
        "dev::clean",
        "dev::validate",
        # Documentation commands
        "documentation::build",
        "documentation::build-strict",
        "documentation::serve",
        "documentation::open",
        # Docker commands (dry-run safe)
        "docker::build",
        "docker::run",
        "docker::shell",
        "docker::inspect",
        "docker::clean",
        # Install commands
        "install::mcp-server",
        "install::mcp-bridge-workbench",
        "install::status",
        # MCP commands
        "mcp::check",
        "mcp::run",
        # FreeCAD commands
        "freecad::run-gui",
        "freecad::run-headless",
        # Release commands (read-only ones)
        "release::status",
        "release::list-tags",
        "release::latest-versions",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", SAFE_DRY_RUN_COMMANDS)
    def test_command_syntax_valid(self, just: JustRunner, command: str) -> None:
        """Command should have valid syntax (just --dry-run succeeds)."""
        result = just.dry_run(command)
        assert result.success, (
            f"Syntax error in '{command}': {result.stderr}\n{result.stdout}"
        )
