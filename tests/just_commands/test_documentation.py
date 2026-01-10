"""Tests for documentation module just commands.

These tests verify that documentation commands work correctly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestDocumentationSyntax:
    """Syntax validation tests for documentation commands."""

    DOC_COMMANDS: ClassVar[list[str]] = [
        "documentation::build",
        "documentation::build-strict",
        "documentation::serve",
        "documentation::open",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", DOC_COMMANDS)
    def test_documentation_command_syntax(self, just: JustRunner, command: str) -> None:
        """Documentation command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestDocumentationRuntime:
    """Runtime tests for documentation commands."""

    @pytest.mark.just_runtime
    def test_build_runs(self, just: JustRunner) -> None:
        """Documentation build should run successfully."""
        result = just.run("documentation::build", timeout=120)
        assert result.success, f"Documentation build failed: {result.stderr}"

    @pytest.mark.just_runtime
    def test_build_strict_runs(self, just: JustRunner) -> None:
        """Documentation build-strict should run successfully."""
        result = just.run("documentation::build-strict", timeout=120)
        assert result.success, f"Documentation build-strict failed: {result.stderr}"
