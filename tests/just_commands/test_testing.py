"""Tests for testing module just commands.

These tests verify that test commands work correctly.
Note: We avoid running integration tests here to prevent recursion.
"""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.just_commands.conftest import assert_command_executed

if TYPE_CHECKING:
    from tests.just_commands.conftest import JustRunner


class TestTestingSyntax:
    """Syntax validation tests for testing commands."""

    TESTING_COMMANDS: ClassVar[list[str]] = [
        "testing::unit",
        "testing::cov",
        "testing::quick",
        "testing::integration",
        "testing::verbose",
        "testing::all",
        "testing::watch",
        "testing::check-deps",
        "testing::integration-freecad-auto",
        "testing::just-syntax",
        "testing::just-runtime",
        "testing::just-all",
        "testing::just-release",
        "testing::release-test",
        "testing::integration-headless-release",
        "testing::integration-gui-release",
        "testing::kill-bridge",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", TESTING_COMMANDS)
    def test_testing_command_syntax(self, just: JustRunner, command: str) -> None:
        """Testing command should have valid syntax."""
        result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


class TestTestingRuntime:
    """Runtime tests for testing commands.

    Note: We use --collect-only or run minimal tests to avoid
    long execution times and recursion issues.
    """

    @pytest.mark.just_runtime
    @pytest.mark.parametrize("mode", ["gui", "headless"])
    def test_missing_freecad_executable_reports_error(
        self, tmp_path: Path, mode: str
    ) -> None:
        """Executable discovery must report a clear error when PATH is empty."""
        helper = Path(__file__).resolve().parents[2] / "scripts/bridge-helpers.sh"
        result = subprocess.run(  # noqa: S603
            [
                "/bin/bash",
                "-c",
                '. "$1"; find_freecad_executable "$2"',
                "bash",
                str(helper),
                mode,
            ],
            env={"PATH": str(tmp_path), "OSTYPE": "linux-gnu"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
        assert f"FreeCAD {mode} executable not found" in result.stderr

    @pytest.mark.just_runtime
    @pytest.mark.parametrize(
        "command",
        [
            "testing::integration-headless-release",
            "testing::integration-gui-release",
            "testing::integration-freecad-auto",
        ],
    )
    @pytest.mark.parametrize("port", [9875, 9876])
    def test_release_integration_refuses_occupied_port(
        self, just: JustRunner, command: str, port: int
    ) -> None:
        """An unrelated listener must be left running before release tests start."""
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                pytest.skip(f"Port {port} is already occupied")
            listener.listen()
            result = just.run(command, timeout=15)
            assert not result.success
            assert "already" in result.output and "port" in result.output
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                pass

    @pytest.mark.just_syntax
    @pytest.mark.parametrize(
        "command",
        [
            "testing::integration-headless-release",
            "testing::integration-gui-release",
            "testing::integration-freecad-auto",
        ],
    )
    def test_integration_cleanup_targets_started_process(
        self, just: JustRunner, command: str
    ) -> None:
        """Automatic test runners must not terminate arbitrary port owners."""
        result = just.dry_run(command)
        assert result.success
        assert 'stop_owned_freecad "$FREECAD_PID"' in result.output
        assert "graceful_kill_bridge_ports" not in result.output
        assert "kill_port" not in result.output
        assert result.output.index("require_bridge_pairing") < result.output.index(
            "FREECAD_CMD=$(find_freecad_executable"
        )

    @pytest.mark.just_runtime
    def test_kill_bridge_runs(self, just: JustRunner) -> None:
        """Kill-bridge command should run (even if nothing to kill)."""
        result = just.run("testing::kill-bridge", timeout=30)
        # Should succeed even if no processes to kill
        assert result.success, f"Kill-bridge failed: {result.stderr}"

    @pytest.mark.just_runtime
    def test_unit_command_recognizes_pytest(self, just: JustRunner) -> None:
        """Unit test command should at least recognize pytest."""
        # Run with --collect-only to just validate pytest setup
        result = just.run(
            "testing::unit",
            timeout=60,
            env={"PYTEST_ADDOPTS": "--collect-only -q"},
        )
        # Should at least find some tests or run without error
        assert_command_executed(result, "testing::unit")

    @pytest.mark.just_runtime
    def test_quick_command_recognizes_markers(self, just: JustRunner) -> None:
        """Quick test command should recognize the 'not slow' marker."""
        result = just.run(
            "testing::quick",
            timeout=60,
            env={"PYTEST_ADDOPTS": "--collect-only -q"},
        )
        assert_command_executed(result, "testing::quick")

    @pytest.mark.just_runtime
    def test_gui_release_sequencing(self, just: JustRunner) -> None:
        """Verify integration-gui-release shutdown sequencing and standalone test selection."""
        dryRunResult = just.dry_run("testing::integration-gui-release")
        assert dryRunResult.success, (
            f"Dry-run failed for integration-gui-release: {dryRunResult.stderr}"
        )

        # just --dry-run writes the expanded script to stderr
        scriptText = dryRunResult.output

        # --- Verify first pytest run filters out standalone tests ---
        assert '-m "not standalone_freecad"' in scriptText, (
            "First pytest run must exclude standalone_freecad tests"
        )

        # --- Verify shutdown sequence order ---
        # Find positions of critical operations after stopping FreeCAD.
        # Use the "Stopping FreeCAD" marker to anchor past the function
        # definition, trap registrations, and comments that also mention cleanup.
        stopMarker = "Stopping FreeCAD for standalone tests"
        stopPos = scriptText.find(stopMarker)
        assert stopPos != -1, "Recipe must log 'Stopping FreeCAD for standalone tests'"

        cleanupPos = scriptText.find("cleanup", stopPos)
        assert cleanupPos != -1, "cleanup call not found after stop marker"

        startedFalsePos = scriptText.find('FREECAD_PID=""', stopPos)
        assert startedFalsePos != -1, "FREECAD_PID reset not found after stop marker"

        portsPos = scriptText.find("wait_for_ports_free", stopPos)
        assert portsPos != -1, "wait_for_ports_free not found after stop marker"

        exitPos = scriptText.find("wait_for_freecad_exit", stopPos)
        assert exitPos != -1, "wait_for_freecad_exit not found after stop marker"

        assert cleanupPos < startedFalsePos, (
            "cleanup must be called before resetting FREECAD_PID"
        )
        assert startedFalsePos < portsPos, (
            "FREECAD_PID must be reset before wait_for_ports_free"
        )
        assert portsPos < exitPos, (
            "wait_for_ports_free must be called before wait_for_freecad_exit"
        )

        # --- Verify standalone tests are conditional on prior success ---
        standaloneGuard = 'if [ "$TEST_EXIT_CODE" -eq 0 ]'
        assert standaloneGuard in scriptText, (
            "Standalone tests must be guarded by TEST_EXIT_CODE == 0 check"
        )

        # The standalone pytest must target test_shutdown_crash.py specifically
        assert "test_shutdown_crash.py" in scriptText, (
            "Standalone pytest must target test_shutdown_crash.py"
        )

        # The guard must appear after wait_for_freecad_exit
        guardPos = scriptText.find(standaloneGuard)
        assert guardPos != -1, "TEST_EXIT_CODE guard not found in scriptText"
        assert guardPos > exitPos, (
            "Standalone test guard must come after wait_for_freecad_exit"
        )
