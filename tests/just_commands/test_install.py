"""Tests for install module just commands.

These tests verify that installation commands work correctly.
Note: Some tests may modify local installations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestInstallSyntax:
    """Syntax validation tests for install commands."""

    INSTALL_COMMANDS: ClassVar[list[str]] = [
        "install::mcp-server",
        "install::mcp-server-clean",
        "install::uninstall-mcp-server",
        "install::mcp-bridge-workbench",
        "install::uninstall-mcp-bridge-workbench",
        "install::status",
        "install::uninstall",
        "install::cleanup",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", INSTALL_COMMANDS)
    def test_install_command_syntax(self, just: JustRunner, command: str) -> None:
        """Install command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestInstallRuntime:
    """Runtime tests for install commands."""

    @pytest.mark.just_runtime
    def test_status_runs(self, just: JustRunner) -> None:
        """Status command should run and show installation status."""
        result = just.run("install::status", timeout=60)
        assert result.success, f"Status failed: {result.stderr}"
        # Should contain some expected output
        assert "Installation Status" in result.stdout

    @pytest.mark.just_runtime
    def test_freecad_dirs_helper_runs(self, just: JustRunner) -> None:
        """Private _freecad-dirs helper should work."""
        result = just.run("install::_freecad-dirs", timeout=10)
        assert result.success, f"_freecad-dirs failed: {result.stderr}"
        # Should output shell code to set directories
        assert "MOD_DIR" in result.stdout
        assert "MACRO_DIR" in result.stdout

    @pytest.mark.just_runtime
    @pytest.mark.slow
    def test_mcp_server_install_uninstall(self, just: JustRunner) -> None:
        """MCP server install and uninstall should work."""
        # Install
        result = just.run("install::mcp-server", timeout=300)
        assert result.success, f"MCP server install failed: {result.stderr}"

        # Verify installation
        status_result = just.run("install::status", timeout=60)
        assert "Robust MCP Server" in status_result.stdout

        # Uninstall
        uninstall_result = just.run("install::uninstall-mcp-server", timeout=60)
        assert uninstall_result.success, (
            f"MCP server uninstall failed: {uninstall_result.stderr}"
        )

    @pytest.mark.just_runtime
    def test_uninstall_runs(self, just: JustRunner) -> None:
        """Uninstall command should run without error.

        This command uninstalls all components. It may complete with warnings
        if nothing is installed, but should not error.
        """
        result = just.run("install::uninstall", timeout=120)
        # Command should succeed even if nothing was installed
        assert result.success, f"Uninstall failed: {result.stderr}"

    @pytest.mark.just_runtime
    def test_cleanup_runs(self, just: JustRunner) -> None:
        """Cleanup command should run without error.

        This command cleans up caches and temporary files.
        """
        result = just.run("install::cleanup", timeout=60)
        assert result.success, f"Cleanup failed: {result.stderr}"
