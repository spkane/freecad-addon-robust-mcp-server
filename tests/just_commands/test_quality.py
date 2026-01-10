"""Tests for quality module just commands.

These tests verify that code quality commands work correctly.
Note: Some tests may be slow as they run actual linters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.just_commands.conftest import assert_command_executed

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestQualitySyntax:
    """Syntax validation tests for quality commands."""

    QUALITY_COMMANDS: ClassVar[list[str]] = [
        "quality::check",
        "quality::format",
        "quality::lint",
        "quality::typecheck",
        "quality::security",
        "quality::spellcheck",
        "quality::scan",
        "quality::scan-gitleaks",
        "quality::scan-gitleaks-history",
        "quality::scan-detect",
        "quality::scan-audit",
        "quality::scan-baseline-update",
        "quality::scan-trufflehog",
        "quality::markdown-lint",
        "quality::markdown-fix",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", QUALITY_COMMANDS)
    def test_quality_command_syntax(self, just: JustRunner, command: str) -> None:
        """Quality command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestQualityRuntime:
    """Runtime tests for quality commands."""

    @pytest.mark.just_runtime
    def test_lint_runs(self, just: JustRunner) -> None:
        """Lint command should run successfully on the codebase."""
        result = just.run("quality::lint", timeout=120)
        # Lint may find issues, so we don't require success
        # But it should at least run without crashing or missing deps
        assert_command_executed(result, "quality::lint")

    @pytest.mark.just_runtime
    def test_typecheck_runs(self, just: JustRunner) -> None:
        """Typecheck command should run successfully."""
        result = just.run("quality::typecheck", timeout=180)
        # Type checking may find issues, but should run without missing deps
        assert_command_executed(result, "quality::typecheck")

    @pytest.mark.just_runtime
    def test_spellcheck_runs(self, just: JustRunner) -> None:
        """Spellcheck command should run."""
        result = just.run("quality::spellcheck", timeout=60)
        assert_command_executed(result, "quality::spellcheck")

    @pytest.mark.just_runtime
    def test_scan_gitleaks_runs(self, just: JustRunner) -> None:
        """Gitleaks scanner should run."""
        result = just.run("quality::scan-gitleaks", timeout=120)
        # May find false positives, but should run without missing deps
        assert_command_executed(result, "quality::scan-gitleaks")

    @pytest.mark.just_runtime
    def test_scan_detect_runs(self, just: JustRunner) -> None:
        """detect-secrets scanner should run."""
        result = just.run("quality::scan-detect", timeout=60)
        assert_command_executed(result, "quality::scan-detect")

    @pytest.mark.just_runtime
    def test_markdown_lint_runs(self, just: JustRunner) -> None:
        """Markdown linter should run."""
        result = just.run("quality::markdown-lint", timeout=60)
        # May find issues, but should run without missing deps
        assert_command_executed(result, "quality::markdown-lint")

    @pytest.mark.just_runtime
    @pytest.mark.slow
    def test_full_check_runs(self, just: JustRunner) -> None:
        """Full quality check should run (may take a while)."""
        result = just.run("quality::check", timeout=600)
        # This runs all pre-commit hooks - should run without missing deps
        assert_command_executed(result, "quality::check")
