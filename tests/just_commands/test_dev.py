"""Tests for dev module just commands.

These tests verify that development utility commands work correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestDevSyntax:
    """Syntax validation tests for dev commands."""

    DEV_COMMANDS: ClassVar[list[str]] = [
        "dev::install-deps",
        "dev::install-pre-commit",
        "dev::update-deps",
        "dev::clean",
        "dev::repl",
        "dev::tree",
        "dev::validate",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", DEV_COMMANDS)
    def test_dev_command_syntax(self, just: JustRunner, command: str) -> None:
        """Dev command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestDevRuntime:
    """Runtime tests for dev commands."""

    @pytest.mark.just_runtime
    def test_clean_runs(self, just: JustRunner) -> None:
        """Clean command should run successfully."""
        result = just.run("dev::clean", timeout=30)
        assert result.success, f"Clean failed: {result.stderr}"

    @pytest.mark.just_runtime
    def test_validate_runs(self, just: JustRunner) -> None:
        """Validate command should run successfully."""
        result = just.run("dev::validate", timeout=30)
        assert result.success, f"Validate failed: {result.stderr}"

    @pytest.mark.just_runtime
    @pytest.mark.slow
    def test_install_deps_runs(self, just: JustRunner) -> None:
        """Install-deps command should run (may take a while)."""
        result = just.run("dev::install-deps", timeout=300)
        assert result.success, f"Install-deps failed: {result.stderr}"

    @pytest.mark.just_runtime
    def test_install_pre_commit_runs(self, just: JustRunner) -> None:
        """Install-pre-commit should run successfully."""
        result = just.run("dev::install-pre-commit", timeout=60)
        assert result.success, f"Install-pre-commit failed: {result.stderr}"
