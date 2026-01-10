"""Tests for coderabbit module just commands.

These tests verify that CodeRabbit CLI commands work correctly.
Note: Most commands require CodeRabbit CLI to be installed and authenticated.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


def coderabbit_available() -> bool:
    """Check if CodeRabbit CLI is available."""
    return shutil.which("coderabbit") is not None


class TestCoderabbitSyntax:
    """Syntax validation tests for CodeRabbit commands."""

    CODERABBIT_COMMANDS: ClassVar[list[str]] = [
        "coderabbit::install",
        "coderabbit::check-installed",
        "coderabbit::login",
        "coderabbit::logout",
        "coderabbit::auth-status",
        "coderabbit::review",
        "coderabbit::review-fix",
        "coderabbit::review-all",
        "coderabbit::review-last",
        "coderabbit::review-since",
        "coderabbit::review-branch",
        "coderabbit::prompt-only",
        "coderabbit::review-json",
        "coderabbit::help",
        "coderabbit::version",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", CODERABBIT_COMMANDS)
    def test_coderabbit_command_syntax(self, just: JustRunner, command: str) -> None:
        """CodeRabbit command should have valid syntax."""
        # Commands with required arguments
        if command == "coderabbit::review-since":
            result = just.dry_run(command, "HEAD~5")
        else:
            result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestCoderabbitRuntime:
    """Runtime tests for CodeRabbit commands."""

    @pytest.mark.just_runtime
    def test_check_installed_reports_status(self, just: JustRunner) -> None:
        """check-installed should report installation status."""
        result = just.run("coderabbit::check-installed", timeout=10)
        if coderabbit_available():
            assert result.success
        else:
            # Should fail with helpful message
            assert not result.success
            assert "not installed" in result.output.lower()

    @pytest.mark.just_runtime
    def test_version_runs(self, just: JustRunner) -> None:
        """version command should run if CodeRabbit is installed."""
        if not coderabbit_available():
            pytest.skip("CodeRabbit CLI not installed")
        result = just.run("coderabbit::version", timeout=10)
        assert result.success, f"Version failed: {result.stderr}"
