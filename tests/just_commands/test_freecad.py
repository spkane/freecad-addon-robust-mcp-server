"""Tests for freecad module just commands.

These tests verify that FreeCAD-related commands work correctly.
Note: Most FreeCAD commands require FreeCAD to be installed.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from tests.just_commands.conftest import JustRunner

# MCP bridge default ports
_XMLRPC_PORT = 9875
_SOCKET_PORT = 9876


def freecad_available() -> bool:
    """Check if FreeCAD is available."""
    # Check for common FreeCAD command locations
    if shutil.which("freecad") or shutil.which("FreeCAD"):
        return True
    return bool(shutil.which("freecadcmd") or shutil.which("FreeCADCmd"))


def _is_port_in_use(port: int) -> bool:
    """Check whether a TCP port is already bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("localhost", port)) == 0


def _is_freecad_process_running() -> bool:
    """Check if any FreeCAD process is currently running.

    Uses ``ps aux`` instead of ``pgrep`` for portability across
    systems that may not ship GNU/BSD pgrep.
    """
    try:
        result = subprocess.run(
            ["ps", "aux"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        for line in result.stdout.lower().splitlines():
            # Skip the ps/grep header or our own grep invocation
            if "freecad" in line and "grep" not in line:
                return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def _kill_freecad_processes() -> None:
    """Force-stop any FreeCAD processes and free bridge ports.

    Kills processes listening on the MCP bridge ports, then kills any
    remaining FreeCAD processes by name.  Used for test teardown to
    clean up orphaned freecadcmd processes that survive subprocess
    timeout (the timeout kills the parent `just` but not the child).
    """
    for port in (_XMLRPC_PORT, _SOCKET_PORT):
        try:
            # S603, S607: lsof is a well-known command, safe in test context
            pidOutput = subprocess.run(  # noqa: S603
                ["lsof", "-ti", f":{port}"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if pidOutput.stdout.strip():
                for pid in pidOutput.stdout.strip().split("\n"):
                    subprocess.run(  # noqa: S603
                        ["kill", "-9", pid.strip()],  # noqa: S607
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Kill any remaining FreeCAD processes by name.
    # Prefer pkill when available; fall back to psutil for portability.
    if shutil.which("pkill"):
        try:
            subprocess.run(
                ["pkill", "-9", "-i", "freecad"],  # noqa: S607
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            import psutil

            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    procName = (proc.info.get("name") or "").lower()
                    cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                    if "freecad" in procName or "freecad" in cmdline:
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            pass

    # Brief pause to let the OS release ports
    time.sleep(1)


def _wait_for_freecad_exit(timeout: int = 60) -> None:
    """Block until ports are free AND no FreeCAD process is running.

    Ports may be released before the FreeCAD process fully exits.
    Starting a second FreeCAD while the first is still alive causes
    SIGSEGV on macOS ("Tried to run initApplication() twice!").

    Uses a 60s default because during release-test, the standalone
    shutdown test (Step 3) launches its own FreeCAD which may still
    be exiting when Step 5 (just-all) reaches this test.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        portsFree = not _is_port_in_use(_XMLRPC_PORT) and not _is_port_in_use(
            _SOCKET_PORT
        )
        processGone = not _is_freecad_process_running()
        if portsFree and processGone:
            return
        time.sleep(1)
    pytest.fail(
        f"FreeCAD still present after {timeout}s "
        f"(ports in use: {_is_port_in_use(_XMLRPC_PORT)}/{_is_port_in_use(_SOCKET_PORT)}, "
        f"process running: {_is_freecad_process_running()}). "
        "A previous FreeCAD instance may not have fully exited."
    )


class TestFreecadSyntax:
    """Syntax validation tests for FreeCAD commands."""

    FREECAD_COMMANDS: ClassVar[list[str]] = [
        "freecad::run-headless",
        "freecad::run-headless-custom",
        "freecad::run-gui",
        "freecad::run-gui-custom",
    ]

    @pytest.mark.just_syntax
    @pytest.mark.parametrize("command", FREECAD_COMMANDS)
    def test_freecad_command_syntax(self, just: JustRunner, command: str) -> None:
        """FreeCAD command should have valid syntax."""
        # Commands with required arguments
        if command == "freecad::run-headless-custom":
            result = just.dry_run(command, "/path/to/freecadcmd")
        elif command == "freecad::run-gui-custom":
            result = just.dry_run(command, "/path/to/freecad")
        else:
            result = just.dry_run(command)
        assert result.success, f"Syntax error in '{command}': {result.stderr}"


@pytest.mark.requires_freecad
class TestFreecadRuntime:
    """Runtime tests for FreeCAD commands (require FreeCAD)."""

    @pytest.fixture(autouse=True)
    def skip_if_no_freecad(self) -> Generator[None, None, None]:
        """Skip if FreeCAD unavailable; kill orphaned processes on teardown."""
        if not freecad_available():
            pytest.skip("FreeCAD not available")
        yield
        # Teardown: kill any FreeCAD processes started by the test.
        # just.run() with a timeout kills the parent `just` process but
        # the child freecadcmd survives as an orphan holding bridge ports.
        _kill_freecad_processes()

    @pytest.mark.just_runtime
    def test_run_headless_starts(self, just: JustRunner) -> None:
        """run-headless should start FreeCAD (we just verify it doesn't crash immediately)."""
        # Wait for ports AND FreeCAD process to be gone — a prior
        # release-test step may still be shutting down when this test runs.
        _wait_for_freecad_exit()

        # Start headless and kill after short timeout
        result = just.run("freecad::run-headless", timeout=10)

        # Check for missing executable first (exit code 127)
        if result.returncode == 127:
            pytest.fail(
                "FreeCAD executable not found (exit code 127). "
                "Ensure FreeCAD is installed and in PATH. "
                f"Output: {result.output}"
            )

        # Will timeout (expected) - we just want to verify it started
        # returncode -1 means timeout, which is expected
        # returncode 0 means it exited cleanly
        # Any other exit code indicates a problem
        assert result.returncode in (-1, 0), (
            f"FreeCAD failed unexpectedly (exit {result.returncode}): {result.output}"
        )
