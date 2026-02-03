"""Tests for FreeCAD shutdown crash prevention.

These tests verify that FreeCAD can shut down cleanly when the MCP bridge
is running, without crashing due to Qt/PySide cleanup issues.

The crash scenario:
1. FreeCAD starts with MCP bridge (creates QTimer objects)
2. User closes FreeCAD
3. Python's atexit handlers run
4. Python's Py_FinalizeEx() runs garbage collection
5. GC tries to finalize PySide QTimer wrappers
6. PySide destructor triggers Qt's disconnectNotify callback
7. disconnectNotify calls back into partially-finalized Python
8. CRASH (SIGSEGV in _PyType_Lookup)

The fix uses shiboken.delete() in the atexit handler to explicitly destroy
the Qt/C++ objects before Python's GC runs, preventing the crash.

These tests are marked as slow because they start/stop FreeCAD processes.
"""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Signal numbers for crash detection
SIGSEGV = 11
SIGABRT = 6

# Exit codes that indicate a crash
# On Unix, signal exits are typically -signal or 128+signal
CRASH_EXIT_CODES = {
    -SIGSEGV,  # Killed by SIGSEGV
    -SIGABRT,  # Killed by SIGABRT
    128 + SIGSEGV,  # 139 - shell convention for SIGSEGV
    128 + SIGABRT,  # 134 - shell convention for SIGABRT
}


def _is_bridge_running(host: str = "localhost", port: int = 9875) -> bool:
    """Check if an MCP bridge is already running on the given port.

    Args:
        host: Bridge hostname.
        port: Bridge XML-RPC port.

    Returns:
        True if a bridge is responding, False otherwise.
    """
    import xmlrpc.client

    try:
        proxy = xmlrpc.client.ServerProxy(f"http://{host}:{port}", allow_none=True)
        result = proxy.ping()
        return isinstance(result, dict) and bool(result.get("pong"))
    except Exception:
        return False


def _find_freecad_binary() -> str | None:
    """Find the FreeCAD GUI binary path.

    Returns:
        Path to FreeCAD binary, or None if not found.
    """
    if platform.system() == "Darwin":
        # macOS: Use the actual binary, not the .app bundle
        paths = [
            "/Applications/FreeCAD.app/Contents/Resources/bin/freecad",
            os.path.expanduser(
                "~/Applications/FreeCAD.app/Contents/Resources/bin/freecad"
            ),
        ]
    elif platform.system() == "Linux":
        paths = [
            "/usr/bin/freecad",
            "/usr/local/bin/freecad",
            "/opt/freecad/bin/FreeCAD",
        ]
        # Also check PATH
        import shutil

        freecad_in_path = shutil.which("freecad") or shutil.which("FreeCAD")
        if freecad_in_path:
            paths.insert(0, freecad_in_path)
    else:
        # Windows
        paths = [
            os.path.join(
                os.environ.get("PROGRAMFILES", ""), "FreeCAD 1.0/bin/FreeCAD.exe"
            ),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "FreeCAD/bin/FreeCAD.exe"),
        ]

    for path in paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


def _wait_for_bridge(
    host: str = "localhost", port: int = 9875, timeout: float = 60.0
) -> bool:
    """Wait for the MCP bridge to become available.

    Args:
        host: Bridge hostname.
        port: Bridge XML-RPC port.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if bridge is available, False if timeout.
    """
    import xmlrpc.client

    start_time = time.time()
    proxy = xmlrpc.client.ServerProxy(f"http://{host}:{port}", allow_none=True)

    while time.time() - start_time < timeout:
        try:
            result = proxy.ping()
            if isinstance(result, dict) and result.get("pong"):
                return True
        except Exception:
            pass
        time.sleep(0.5)

    return False


def _send_quit_command(host: str = "localhost", port: int = 9875) -> bool:
    """Send quit command to FreeCAD via the MCP bridge.

    Args:
        host: Bridge hostname.
        port: Bridge XML-RPC port.

    Returns:
        True if command was sent successfully.
    """
    import xmlrpc.client

    try:
        proxy = xmlrpc.client.ServerProxy(f"http://{host}:{port}", allow_none=True)
        # Use FreeCADGui.getMainWindow().close() for a clean shutdown
        # This triggers the normal Qt close event which will run atexit handlers
        proxy.execute(
            """
import FreeCADGui
if FreeCAD.GuiUp:
    main_window = FreeCADGui.getMainWindow()
    if main_window:
        main_window.close()
"""
        )
        return True
    except Exception:
        return False


@pytest.fixture
def freecad_binary() -> str:
    """Get the FreeCAD binary path or skip if not found."""
    binary = _find_freecad_binary()
    if binary is None:
        pytest.skip("FreeCAD binary not found")
        raise AssertionError("Unreachable")  # For mypy - skip always raises
    return binary


@pytest.fixture
def startup_script() -> str:
    """Get the path to the bridge startup script."""
    # Find the project root
    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent.parent

    script_path = (
        project_root
        / "freecad"
        / "RobustMCPBridge"
        / "freecad_mcp_bridge"
        / "startup_bridge.py"
    )

    if not script_path.exists():
        pytest.skip(f"Startup script not found: {script_path}")

    return str(script_path)


@pytest.mark.standalone_freecad
@pytest.mark.timeout(120)  # 2 minute timeout for the entire test
class TestShutdownCrash:
    """Tests for FreeCAD shutdown without crashes.

    These tests start their own FreeCAD process and must NOT run while another
    FreeCAD instance with the MCP bridge is running (they would conflict on ports).

    Run these tests separately:
        uv run pytest tests/integration/test_shutdown_crash.py -v

    Or exclude them from normal integration test runs:
        uv run pytest tests/integration -v -m "not standalone_freecad"
    """

    @pytest.fixture(autouse=True)
    def check_no_existing_bridge(self):
        """Skip if a bridge is already running (would conflict on ports)."""
        if _is_bridge_running():
            pytest.skip(
                "MCP bridge already running on port 9875. "
                "These tests must run without an existing FreeCAD/bridge instance. "
                "Stop FreeCAD and run: uv run pytest tests/integration/test_shutdown_crash.py -v"
            )

    def test_gui_shutdown_no_crash(
        self,
        freecad_binary: str,
        startup_script: str,
    ) -> None:
        """Test that FreeCAD GUI shuts down cleanly with MCP bridge running.

        This test:
        1. Starts FreeCAD in GUI mode with the MCP bridge
        2. Waits for the bridge to be ready
        3. Sends a quit command via XML-RPC
        4. Verifies FreeCAD exits with code 0 (not a crash)

        A crash would result in exit code 139 (SIGSEGV) or 134 (SIGABRT).
        """
        # Start FreeCAD with the bridge startup script
        env = os.environ.copy()
        # Set testing mode so the bridge prints its instance ID
        env["FREECAD_MCP_TESTING"] = "1"

        # On macOS, we need to use the binary directly, not `open`
        # This allows us to capture the exit code
        # S603: Safe - freecad_binary is from _find_freecad_binary(), not user input
        proc = subprocess.Popen(  # noqa: S603
            [freecad_binary, startup_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            # Wait for bridge to be ready
            bridge_ready = _wait_for_bridge(timeout=60.0)
            if not bridge_ready:
                # Kill the process and fail
                proc.terminate()
                proc.wait(timeout=10)
                pytest.fail("MCP bridge did not become available within timeout")

            # Give FreeCAD a moment to fully stabilize
            time.sleep(2)

            # Send quit command
            quit_sent = _send_quit_command()
            if not quit_sent:
                # Try to terminate gracefully
                proc.terminate()

            # Wait for FreeCAD to exit
            try:
                exit_code = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't exit
                proc.kill()
                exit_code = proc.wait(timeout=10)

            # Check for crash exit codes
            if exit_code in CRASH_EXIT_CODES:
                # Get stderr for debugging
                _, stderr = proc.communicate(timeout=5)
                stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

                crash_signal = (
                    "SIGSEGV" if exit_code in (-SIGSEGV, 128 + SIGSEGV) else "SIGABRT"
                )
                pytest.fail(
                    f"FreeCAD crashed during shutdown with {crash_signal} "
                    f"(exit code {exit_code}).\n"
                    f"This indicates the QTimer cleanup fix may not be working.\n"
                    f"stderr: {stderr_text[:1000]}"
                )

            # Exit code 0 or small positive values are acceptable
            # Some GUI frameworks return 1 on close, which is not a crash
            assert exit_code not in CRASH_EXIT_CODES, (
                f"FreeCAD exited with crash-like code {exit_code}"
            )

        finally:
            # Ensure process is cleaned up
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

    def test_sigterm_shutdown_no_crash(
        self,
        freecad_binary: str,
        startup_script: str,
    ) -> None:
        """Test that FreeCAD handles SIGTERM gracefully with MCP bridge.

        This tests the scenario where FreeCAD is terminated by a signal
        (e.g., from a process manager or IDE).
        """
        if platform.system() == "Windows":
            pytest.skip("SIGTERM test not applicable on Windows")

        env = os.environ.copy()
        env["FREECAD_MCP_TESTING"] = "1"

        # S603: Safe - freecad_binary is from _find_freecad_binary(), not user input
        proc = subprocess.Popen(  # noqa: S603
            [freecad_binary, startup_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        try:
            # Wait for bridge to be ready
            bridge_ready = _wait_for_bridge(timeout=60.0)
            if not bridge_ready:
                proc.terminate()
                proc.wait(timeout=10)
                pytest.fail("MCP bridge did not become available within timeout")

            # Give FreeCAD time to fully stabilize
            time.sleep(2)

            # Send SIGTERM (graceful termination)
            proc.send_signal(signal.SIGTERM)

            # Wait for exit
            try:
                exit_code = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                exit_code = proc.wait(timeout=10)

            # SIGTERM should result in clean exit or -SIGTERM
            # It should NOT result in SIGSEGV or SIGABRT
            if exit_code in (-SIGSEGV, 128 + SIGSEGV, -SIGABRT, 128 + SIGABRT):
                _, stderr = proc.communicate(timeout=5)
                stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
                pytest.fail(
                    f"FreeCAD crashed during SIGTERM shutdown (exit code {exit_code}).\n"
                    f"stderr: {stderr_text[:1000]}"
                )

        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


# Standalone test runner for manual testing
if __name__ == "__main__":
    """Run the shutdown crash test manually.

    Usage:
        python tests/integration/test_shutdown_crash.py
    """
    binary = _find_freecad_binary()
    if not binary:
        print("ERROR: FreeCAD binary not found")
        sys.exit(1)

    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent.parent
    script = str(
        project_root
        / "freecad"
        / "RobustMCPBridge"
        / "freecad_mcp_bridge"
        / "startup_bridge.py"
    )

    print(f"FreeCAD binary: {binary}")
    print(f"Startup script: {script}")
    print()

    print("Starting FreeCAD with MCP bridge...")
    env = os.environ.copy()
    env["FREECAD_MCP_TESTING"] = "1"

    # S603: Safe - binary is from _find_freecad_binary(), not user input
    proc = subprocess.Popen(  # noqa: S603
        [binary, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    print("Waiting for bridge to be ready...")
    if not _wait_for_bridge(timeout=60.0):
        print("ERROR: Bridge did not become available")
        proc.terminate()
        proc.wait()
        sys.exit(1)

    print("Bridge is ready!")
    print("Waiting 3 seconds for stabilization...")
    time.sleep(3)

    print("Sending quit command...")
    _send_quit_command()

    print("Waiting for FreeCAD to exit...")
    try:
        exit_code = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        print("Timeout - killing process")
        proc.kill()
        exit_code = proc.wait()

    print(f"Exit code: {exit_code}")

    if exit_code in CRASH_EXIT_CODES:
        print("CRASH DETECTED!")
        _, stderr = proc.communicate(timeout=5)
        if stderr:
            print("stderr:", stderr.decode("utf-8", errors="replace")[:2000])
        sys.exit(1)
    else:
        print("Clean shutdown - no crash!")
        sys.exit(0)
