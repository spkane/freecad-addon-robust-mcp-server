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

    # Basic documentation commands
    DOC_COMMANDS: ClassVar[list[str]] = [
        "documentation::build",
        "documentation::build-strict",
        "documentation::serve",
        "documentation::open",
    ]

    # Versioned documentation commands (mike-based)
    VERSIONED_DOC_COMMANDS: ClassVar[list[str]] = [
        "documentation::list-versions",
        "documentation::serve-versioned",
    ]

    # Commands that require arguments
    DOC_COMMANDS_WITH_ARGS: ClassVar[list[tuple[str, str]]] = [
        ("documentation::deploy-version", "1.0.0"),
        ("documentation::deploy-latest", "1.0.0"),
        ("documentation::delete-version", "1.0.0"),
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", DOC_COMMANDS)
    def test_documentation_command_syntax(self, just: JustRunner, command: str) -> None:
        """Documentation command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", VERSIONED_DOC_COMMANDS)
    def test_versioned_doc_command_syntax(self, just: JustRunner, command: str) -> None:
        """Versioned documentation command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"

    @pytest.mark.just_syntax
    def test_deploy_dev_syntax(self, just: JustRunner) -> None:
        """Deploy-dev command should have valid syntax."""
        result = just.dry_run("documentation::deploy-dev")
        assert result.success, f"Syntax error in 'deploy-dev': {result.stderr}"

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command,arg", DOC_COMMANDS_WITH_ARGS)
    def test_doc_command_with_args_syntax(
        self, just: JustRunner, command: str, arg: str
    ) -> None:
        """Documentation commands with arguments should have valid syntax."""
        result = just.dry_run(command, arg)
        assert result.success, f"Syntax error in '{command} {arg}': {result.stderr}"


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

    # Note: list-versions, serve-versioned, deploy-*, and delete-version commands
    # are not tested at runtime because they:
    # 1. Require a gh-pages branch to exist (list-versions, serve-versioned)
    # 2. Modify git state by creating/updating gh-pages branch (deploy-*)
    # 3. Delete deployed versions (delete-version)
    # These commands are validated via syntax tests only.
