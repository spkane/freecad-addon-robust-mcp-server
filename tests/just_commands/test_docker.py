"""Tests for docker module just commands.

These tests verify that Docker-related commands work correctly.
Some tests require Docker to be running.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.just_commands.conftest import assert_command_executed

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner

# Docker image name used in tests - defined once for maintainability
DOCKER_IMAGE_NAME = "freecad-robust-mcp"

# Mapping of commands to their required arguments for dry-run testing
COMMAND_ARG_MAP: dict[str, tuple[str, ...]] = {
    "docker::build-tag": ("test",),
    "docker::build-push": ("test",),
    "docker::scan-sarif": ("test.sarif",),
    "docker::run-env": ("-e", "TEST=1"),
    "docker::gui-test-cmd": ("echo", "test"),
}


def docker_available() -> bool:
    """Check if Docker is available and running."""
    if not shutil.which("docker"):
        return False
    try:
        # S603, S607: docker is a well-known command, safe in test context
        result = subprocess.run(
            ["docker", "info"],  # noqa: S607
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


class TestDockerSyntax:
    """Syntax validation tests for docker commands."""

    DOCKER_COMMANDS: ClassVar[list[str]] = [
        "docker::build",
        "docker::build-tag",
        "docker::build-multi",
        "docker::build-push",
        "docker::build-load",
        "docker::run",
        "docker::run-env",
        "docker::shell",
        "docker::inspect",
        "docker::clean",
        "docker::clean-all",
        "docker::scan",
        "docker::scan-strict",
        "docker::scan-sarif",
        "docker::setup-buildx",
        "docker::test",
        "docker::build-gui-test",
        "docker::gui-test-shell",
        "docker::gui-test-run",
        "docker::gui-test-cmd",
        "docker::gui-test",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", DOCKER_COMMANDS)
    def test_docker_command_syntax(self, just: JustRunner, command: str) -> None:
        """Docker command should have valid syntax."""
        # Get args from mapping, or empty tuple for commands without required args
        args = COMMAND_ARG_MAP.get(command, ())
        result = just.dry_run(command, *args)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


@pytest.mark.requires_docker
class TestDockerRuntime:
    """Runtime tests for docker commands (require Docker)."""

    @pytest.fixture(autouse=True)
    def skip_if_no_docker(self) -> None:
        """Skip tests if Docker is not available."""
        if not docker_available():
            pytest.skip("Docker not available")

    @pytest.mark.just_runtime
    @pytest.mark.slow
    def test_build_runs(
        self, just: JustRunner, docker_image_cleanup: list[str]
    ) -> None:
        """Docker build should run successfully."""
        docker_image_cleanup.append(DOCKER_IMAGE_NAME)
        # 10 minute timeout: Docker builds can be slow, especially on first run
        # when base images need to be pulled and dependencies compiled
        result = just.run("docker::build", timeout=600)
        assert result.success, f"Docker build failed: {result.stderr}"

    @pytest.mark.just_runtime
    def test_inspect_runs(self, just: JustRunner) -> None:
        """Docker inspect should run (may fail if no image)."""
        result = just.run("docker::inspect", timeout=30)
        # May fail if image doesn't exist, but should run without missing deps
        assert_command_executed(result, "docker::inspect")

    @pytest.mark.just_runtime
    def test_clean_runs(self, just: JustRunner) -> None:
        """Docker clean should run."""
        result = just.run("docker::clean", timeout=60)
        # May fail if no images to clean, but should run without missing deps
        assert_command_executed(result, "docker::clean")

    @pytest.mark.just_runtime
    def test_setup_buildx_runs(self, just: JustRunner) -> None:
        """Setup buildx should run."""
        result = just.run("docker::setup-buildx", timeout=120)
        assert result.success, f"Setup buildx failed: {result.stderr}"
