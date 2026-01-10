"""Shared fixtures and utilities for just command tests.

This module provides:
- Fixtures for running just commands
- Helper functions for command validation
- Markers for test categorization
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Get project root (where justfile is located)
PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass(frozen=True)
class JustResult:
    """Result of running a just command.

    This dataclass is frozen (immutable) since results should not be modified
    after creation - they represent a snapshot of command execution.
    """

    command: str
    returncode: int
    stdout: str
    stderr: str
    success: bool

    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        return f"{self.stdout}\n{self.stderr}".strip()


def assert_command_executed(result: JustResult, command_name: str) -> None:
    """Assert that a command actually executed (didn't timeout or have missing deps).

    This checks for:
    - Timeout (returncode -1)
    - Missing command/dependency (returncode 127)
    - "command not found" in stderr

    It does NOT check for success - the command may legitimately fail
    due to linting issues, type errors, etc.
    """
    assert result.returncode != -1, f"{command_name} timed out: {result.stderr}"
    assert result.returncode != 127, (
        f"{command_name} missing dependency (exit 127): {result.stderr}"
    )
    assert "command not found" not in result.output.lower(), (
        f"{command_name} has missing tool: {result.output}"
    )


class JustRunner:
    """Helper class for running just commands in tests."""

    def __init__(self, project_root: Path) -> None:
        """Initialize the runner with project root path."""
        self.project_root = project_root
        just_path = shutil.which("just")
        if not just_path:
            raise RuntimeError("just command not found in PATH")
        self._just_path: str = just_path

    def run(
        self,
        command: str,
        *args: str,
        timeout: int = 60,
        env: dict[str, str] | None = None,
        input_text: str | None = None,
        check: bool = False,
    ) -> JustResult:
        """Run a just command and return the result.

        Args:
            command: The just command to run (e.g., "quality::lint")
            *args: Additional arguments to pass to the command
            timeout: Timeout in seconds
            env: Additional environment variables
            input_text: Text to pass to stdin
            check: If True, raise CalledProcessError on non-zero exit

        Returns:
            JustResult with command output and status
        """
        cmd: list[str] = [self._just_path, command, *args]

        # Merge environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        try:
            # S603: subprocess call is safe here - we're running `just` with
            # controlled arguments in a test context
            result = subprocess.run(  # noqa: S603
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=run_env,
                input=input_text,
                check=check,
            )
            return JustResult(
                command=command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                success=result.returncode == 0,
            )
        except subprocess.TimeoutExpired as e:
            stdout_val = ""
            if hasattr(e, "stdout") and e.stdout is not None:
                stdout_val = (
                    e.stdout if isinstance(e.stdout, str) else e.stdout.decode()
                )
            return JustResult(
                command=command,
                returncode=-1,
                stdout=stdout_val,
                stderr=f"Command timed out after {timeout}s",
                success=False,
            )
        except subprocess.CalledProcessError as e:
            return JustResult(
                command=command,
                returncode=e.returncode,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                success=False,
            )

    def dry_run(self, command: str, *args: str, timeout: int = 30) -> JustResult:
        """Run a just command in dry-run mode (syntax check only).

        This validates that just can parse the command without executing it.
        """
        cmd: list[str] = [self._just_path, "--dry-run", command, *args]

        # S603: subprocess call is safe here - we're running `just` with
        # controlled arguments in a test context
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return JustResult(
            command=command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            success=result.returncode == 0,
        )

    def list_commands(self, module: str | None = None) -> list[str]:
        """List available just commands, optionally for a specific module."""
        cmd: list[str] = [self._just_path, "--list"]
        if module:
            cmd.append(module)

        # S603: subprocess call is safe here - we're running `just` with
        # controlled arguments in a test context
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        # Parse the output to extract command names
        commands = []
        for raw_line in result.stdout.splitlines():
            # Skip empty lines and headers
            stripped_line = raw_line.strip()
            if not stripped_line or stripped_line.startswith("Available"):
                continue
            # Extract command name (first word before any description)
            parts = stripped_line.split()
            if parts:
                commands.append(parts[0])

        return commands


@pytest.fixture
def just() -> JustRunner:
    """Fixture providing a JustRunner instance."""
    return JustRunner(PROJECT_ROOT)


@pytest.fixture
def project_root() -> Path:
    """Fixture providing the project root path."""
    return PROJECT_ROOT


# Register custom markers
def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "just_syntax: marks tests as just syntax checks (dry-run only)"
    )
    config.addinivalue_line(
        "markers", "just_runtime: marks tests as just runtime tests (actually execute)"
    )
    config.addinivalue_line(
        "markers",
        "just_release: marks tests as release command tests (require special handling)",
    )
    config.addinivalue_line(
        "markers", "requires_freecad: marks tests that require FreeCAD to be installed"
    )
    config.addinivalue_line(
        "markers",
        "requires_docker: marks tests that require Docker to be running",
    )
    config.addinivalue_line(
        "markers",
        "requires_coderabbit: marks tests that require CodeRabbit CLI to be installed",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )


# Cleanup fixtures for release tests
@pytest.fixture
def git_tag_cleanup() -> Generator[list[str], None, None]:
    """Fixture that tracks and cleans up git tags created during tests.

    Usage:
        def test_create_tag(git_tag_cleanup):
            git_tag_cleanup.append("test-tag-v0.0.0")
            # Create the tag...
            # Tag will be deleted after test
    """
    tags_to_cleanup: list[str] = []
    yield tags_to_cleanup

    # Cleanup: delete all tracked tags (only test- prefixed tags for safety)
    for tag in tags_to_cleanup:
        # Safety guard: only delete tags starting with "test-" to prevent
        # accidental deletion of real release tags
        if not tag.startswith("test-"):
            # Log and skip non-test tags
            continue

        # Delete local tag
        # S603, S607: git is a well-known command, safe in test cleanup context
        subprocess.run(  # noqa: S603
            ["git", "tag", "-d", tag],  # noqa: S607
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
        )
        # Delete remote tag (already guarded by the startswith check above)
        subprocess.run(  # noqa: S603
            ["git", "push", "origin", "--delete", tag],  # noqa: S607
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
        )


@pytest.fixture
def docker_image_cleanup() -> Generator[list[str], None, None]:
    """Fixture that tracks and cleans up Docker images created during tests."""
    images_to_cleanup: list[str] = []
    yield images_to_cleanup

    # Cleanup: delete all tracked images
    for image in images_to_cleanup:
        # S603, S607: docker is a well-known command, safe in test cleanup context
        subprocess.run(  # noqa: S603
            ["docker", "rmi", "-f", image],  # noqa: S607
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
        )
