"""Post-execution checks for just commands.

These tests verify that just commands don't have unintended side effects,
such as creating files in the wrong directories.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner

# Get project root (where justfile is located)
PROJECT_ROOT = Path(__file__).parent.parent.parent
JUST_DIR = PROJECT_ROOT / "just"


class TestNoUnexpectedFilesInJustDir:
    """Test that no unexpected files are created in the just/ directory.

    The just/ directory should only contain .just module files.
    Any other files (like .coverage, __pycache__, etc.) indicate that
    a just recipe is running from the wrong directory.
    """

    # Files that are expected to exist in the just/ directory
    EXPECTED_FILES: ClassVar[set[str]] = {
        "coderabbit.just",
        "dev.just",
        "docker.just",
        "documentation.just",
        "freecad.just",
        "install.just",
        "mcp.just",
        "quality.just",
        "release.just",
        "testing.just",
    }

    # Patterns for files that should NEVER be in the just/ directory
    FORBIDDEN_PATTERNS: ClassVar[list[str]] = [
        ".coverage",  # pytest-cov coverage data
        ".pytest_cache",  # pytest cache
        "__pycache__",  # Python bytecode cache
        "*.pyc",  # Compiled Python files
        "htmlcov",  # Coverage HTML reports
        ".mypy_cache",  # mypy cache
        ".ruff_cache",  # ruff cache
        "node_modules",  # Node.js modules
        ".env",  # Environment files
        "*.log",  # Log files
        "*.tmp",  # Temporary files
        "*.bak",  # Backup files
    ]

    @pytest.mark.just_syntax
    def test_just_dir_contains_only_expected_files(self) -> None:
        """The just/ directory should only contain .just module files."""
        if not JUST_DIR.exists():
            pytest.skip("just/ directory does not exist")

        actual_files = set()
        for item in JUST_DIR.iterdir():
            # Skip hidden files that git might create
            if item.name.startswith(".git"):
                continue
            actual_files.add(item.name)

        unexpected_files = actual_files - self.EXPECTED_FILES
        assert not unexpected_files, (
            f"Unexpected files found in just/ directory: {unexpected_files}\n"
            f"This usually means a just recipe is running from the wrong directory.\n"
            f"Expected only: {self.EXPECTED_FILES}"
        )

    @pytest.mark.just_syntax
    def test_no_forbidden_files_in_just_dir(self) -> None:
        """The just/ directory should not contain any forbidden file patterns."""
        if not JUST_DIR.exists():
            pytest.skip("just/ directory does not exist")

        forbidden_found: list[str] = []
        for item in JUST_DIR.iterdir():
            name = item.name
            # Check each pattern using fnmatch for proper glob support
            for pattern in self.FORBIDDEN_PATTERNS:
                if fnmatch.fnmatch(name, pattern):
                    forbidden_found.append(name)
                    break

        assert not forbidden_found, (
            f"Forbidden files found in just/ directory: {forbidden_found}\n"
            f"This indicates just recipes are running from the wrong directory.\n"
            f"Fix the recipe to use 'cd {{{{project_root}}}}' or absolute paths."
        )

    @pytest.mark.just_runtime
    def test_cov_command_does_not_pollute_just_dir(self, just: JustRunner) -> None:
        """Running coverage should not create files in the just/ directory."""
        # Record files before running command
        files_before = set(JUST_DIR.iterdir()) if JUST_DIR.exists() else set()

        # Run the coverage command (with minimal test collection to speed up)
        just.run(
            "testing::cov",
            timeout=120,
            env={"PYTEST_ADDOPTS": "--collect-only -q"},
        )

        # Check for new files
        files_after = set(JUST_DIR.iterdir()) if JUST_DIR.exists() else set()
        new_files = files_after - files_before

        # Filter out any git-related files
        new_files = {f for f in new_files if not f.name.startswith(".git")}

        assert not new_files, (
            f"New files created in just/ directory after running 'testing::cov': "
            f"{[f.name for f in new_files]}\n"
            f"This indicates the cov recipe is running from the wrong directory."
        )


class TestProjectRootIntegrity:
    """Test that commands create files in the correct locations."""

    @pytest.mark.just_runtime
    def test_coverage_file_location(self, just: JustRunner) -> None:
        """Coverage file should be created in project root, not elsewhere."""
        # Clean up any existing coverage file first
        coverage_file = PROJECT_ROOT / ".coverage"
        coverage_in_just = JUST_DIR / ".coverage"

        # Remove existing files to ensure clean state
        if coverage_file.exists():
            coverage_file.unlink()
        if coverage_in_just.exists():
            coverage_in_just.unlink()

        try:
            # Run coverage with minimal test collection
            result = just.run(
                "testing::cov",
                timeout=120,
                env={"PYTEST_ADDOPTS": "--collect-only -q"},
            )

            # Check results
            # Coverage file should NOT be in just/ directory
            assert not coverage_in_just.exists(), (
                ".coverage file was created in just/ directory instead of "
                "project root.\n"
                "Fix the testing::cov recipe to run from the correct directory."
            )

            # If the command succeeded, coverage file should be in project root
            # (It may not exist if --collect-only was used, so we only check on
            # success)
            if result.success and coverage_file.exists():
                # This is the expected location - test passes
                pass
        finally:
            # Clean up coverage files created during test
            if coverage_file.exists():
                coverage_file.unlink()
            if coverage_in_just.exists():
                coverage_in_just.unlink()
